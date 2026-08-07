import pandas as pd
import numpy as np
import sqlite3
import joblib
import warnings
import sys
import os
import faiss
from datetime import datetime
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

scaler_dosyasi = 'scaler.pkl'
faiss_index_dosyasi = 'faiss_index.bin'

# Anomali skorunda bakılacak en yakın komşu sayısı ve bu skorun "anomali"
# sayılacağı eşik (bootstrap sırasında verinin bu persentil'i üzerinde
# kalan mesafeler anomali kabul edilir — Isolation Forest'taki eski
# contamination=0.02 ile aynı ruhta, ~%2 anomali beklentisi).
KOMSU_SAYISI = 5
ESIK_PERSENTIL = 98

# 1. Veritabanına Bağlan ve Veriyi Çek
# timeout + WAL: pipeline'ın diğer adımlarıyla veya canlı izleme betiğiyle
# eşzamanlı erişimde "database is locked" hatasını önlemek için.
baglanti = sqlite3.connect("log_veritabani.db", timeout=15)
baglanti.execute("PRAGMA journal_mode=WAL;")
df = pd.read_sql("SELECT * FROM ozellikli_loglar", baglanti)

if df.empty:
    print("Modelin işleyeceği özellikli veri bulunamadı.")
    sys.exit(0)

# 2. Özellik Seçimi
ozellik_kolonlari = [
    'Saat', 'Hafta_Sonu', 'Mesai_Disi',
    'Basarisiz_Giris_Mi', 'Onceki_Islem_Farki_Sn',
    'Son_10Dk_Basarisiz_Deneme', 'Son_10Dk_IP_Islem_Sayisi',
    'IP_Degisti_Hizli'
]
mevcut_kolonlar = [col for col in ozellik_kolonlari if col in df.columns]

# =====================================================================
# 3. BOOTSTRAP MU, ARTIMLI (INCREMENTAL) TUR MU?
# =====================================================================
# model_sonuclari'nda şu ana kadar kaç satır işlenmiş, oradan öğreniyoruz.
# Bu değer, kural_tabanli_tespit.py'ın da kullandığı delta-fark mantığıyla
# birebir aynı: iki tablo arasındaki satır farkı = işlenecek yeni satırlar.
try:
    mevcut_satir = pd.read_sql("SELECT COUNT(*) AS n FROM model_sonuclari", baglanti).iloc[0]["n"]
except Exception:
    mevcut_satir = 0

index_dosyalari_var = os.path.exists(scaler_dosyasi) and os.path.exists(faiss_index_dosyasi)
bootstrap_gerekli = (mevcut_satir == 0) or not index_dosyalari_var

if bootstrap_gerekli:
    # ---------------------------------------------------------------
    # BOOTSTRAP: scaler'ı BİR KEZ fit et, FAISS indeksini sıfırdan kur.
    # Bundan sonraki her çalıştırmada bu scaler ve indeks yeniden
    # eğitilmez / sıfırdan kurulmaz — sadece yeni vektörler eklenir.
    # ---------------------------------------------------------------
    print(f"🏗️  [Bootstrap] Scaler ve FAISS indeksi {len(df)} kayıtla sıfırdan kuruluyor (bu yalnızca bir kez olur)...")

    X = df[mevcut_kolonlar].to_numpy(dtype="float32")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X).astype("float32")

    boyut = X_scaled.shape[1]
    index = faiss.IndexFlatL2(boyut)
    index.add(X_scaled)

    # Eşiği belirlemek için: her noktanın kendi indeksteki en yakın K
    # komşusuna (kendisi hariç) olan ortalama mesafesini hesapla.
    k_sorgu = min(KOMSU_SAYISI + 1, index.ntotal)
    mesafeler, _ = index.search(X_scaled, k_sorgu)
    komsu_mesafeleri = mesafeler[:, 1:]  # ilk sütun kendisi (mesafe 0), at
    skorlar = komsu_mesafeleri.mean(axis=1)

    esik_degeri = float(np.percentile(skorlar, ESIK_PERSENTIL))

    joblib.dump(scaler, scaler_dosyasi)
    faiss.write_index(index, faiss_index_dosyasi)

    # Bootstrap = sistemin sıfırdan kurulduğu tek an; eski (Isolation Forest
    # dönemine ait olabilecek) model_egitim_gecmisi tablosu varsa yeni şemayla
    # baştan kurulur. Sonraki turlarda bu tabloya sadece INSERT yapılır.
    baglanti.execute("DROP TABLE IF EXISTS model_egitim_gecmisi")

    df['Anomali_Skoru'] = skorlar
    df['Anomali_Durumu'] = (skorlar > esik_degeri).astype(int)

    yeni_eklenen = len(df)
    toplam_vektor = index.ntotal
    yazma_modu = "replace"

else:
    # ---------------------------------------------------------------
    # ARTIMLI TUR: scaler ve FAISS indeksi diskten yüklenir, HİÇBİRİ
    # yeniden eğitilmez. Sadece bu turun yeni satırları skorlanıp
    # indekse eklenir — tüm geçmiş veri asla yeniden işlenmez.
    # ---------------------------------------------------------------
    yeni_satir_sayisi = len(df) - mevcut_satir
    if yeni_satir_sayisi <= 0:
        print("İşlenecek yeni özellikli log bulunamadı.")
        baglanti.close()
        sys.exit(0)

    yeni_df = df.tail(yeni_satir_sayisi).copy()
    print(f"⚡ [Artımlı] {len(yeni_df)} yeni kayıt, mevcut FAISS indeksine (sıfırdan eğitim yapılmadan) skorlanıp ekleniyor...")

    scaler = joblib.load(scaler_dosyasi)
    index = faiss.read_index(faiss_index_dosyasi)

    # Son kullanılan eşiği geçmiş tablosundan oku (eşik de bootstrap'ta
    # bir kez belirlenir, her turda yeniden hesaplanmaz).
    try:
        esik_degeri = float(
            pd.read_sql("SELECT esik_degeri FROM model_egitim_gecmisi ORDER BY id DESC LIMIT 1", baglanti)
            .iloc[0]["esik_degeri"]
        )
    except Exception:
        esik_degeri = 0.0  # Beklenmeyen durum: pratikte bootstrap her zaman önce çalışır

    X_yeni = yeni_df[mevcut_kolonlar].to_numpy(dtype="float32")
    X_yeni_scaled = scaler.transform(X_yeni).astype("float32")

    # Bu satırlar henüz indekste olmadığı için kendisiyle eşleşme riski yok,
    # doğrudan en yakın KOMSU_SAYISI komşuya bakılır.
    k_sorgu = min(KOMSU_SAYISI, index.ntotal)
    mesafeler, _ = index.search(X_yeni_scaled, k_sorgu)
    skorlar = mesafeler.mean(axis=1)

    # Skorlandıktan SONRA indekse eklenir (bir sonraki turun karşılaştırma
    # kümesine dahil olsun diye) — bu, tek gerçek "güncelleme" adımıdır.
    index.add(X_yeni_scaled)
    faiss.write_index(index, faiss_index_dosyasi)

    yeni_df['Anomali_Skoru'] = skorlar
    yeni_df['Anomali_Durumu'] = (skorlar > esik_degeri).astype(int)

    df = yeni_df  # geri kalan kod (kaydetme/raporlama) tek bir df üzerinden çalışsın
    yeni_eklenen = len(yeni_df)
    toplam_vektor = index.ntotal
    yazma_modu = "append"

# 4. Bu turu geçmişe kaydet (izlenebilirlik: ne zaman, kaç vektör eklendi, eşik neydi)
baglanti.execute("""
    CREATE TABLE IF NOT EXISTS model_egitim_gecmisi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zaman TEXT,
        toplam_vektor_sayisi INTEGER,
        yeni_eklenen_vektor_sayisi INTEGER,
        esik_degeri REAL
    )
""")
baglanti.execute(
    "INSERT INTO model_egitim_gecmisi (zaman, toplam_vektor_sayisi, yeni_eklenen_vektor_sayisi, esik_degeri) VALUES (?, ?, ?, ?)",
    (datetime.now().isoformat(timespec="seconds"), int(toplam_vektor), int(yeni_eklenen), float(esik_degeri)),
)
baglanti.commit()

# 5. Sonuçları Veritabanına Kaydet
df.to_sql("model_sonuclari", baglanti, if_exists=yazma_modu, index=False)
baglanti.close()

print("\n--- MODEL İŞLEM SONUÇLARI ---")
print(f"Çalışma Modu: {'Bootstrap (tek seferlik kuruluş)' if bootstrap_gerekli else 'Artımlı (yalnızca yeni kayıtlar)'}")
print(f"Bu Turda İşlenen Kayıt: {yeni_eklenen}")
print(f"İndeksteki Toplam Vektör: {toplam_vektor}")
print(f"Tespit Edilen Anomali Sayısı (bu tur): {int(df['Anomali_Durumu'].sum())}")
print(f"Kullanılan Eşik Değeri: {esik_degeri:.4f}")
