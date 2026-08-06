import pandas as pd
import sqlite3
import joblib
import warnings
import sys
import os
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

warnings.filterwarnings("ignore")

# --- KAN-38: ÇALIŞMA MODU BELİRLEME ---
# Eğer pipeline'dan --delta geldiyse sistemi yormamak için "Tahmin" moduna geçeceğiz.
delta_modu = "--delta" in sys.argv
model_dosyasi = 'isolation_forest_model.pkl'
scaler_dosyasi = 'scaler.pkl'

# --- OTOMATİK YENİDEN EĞİTİM EŞİĞİ ---
# Model sonsuza kadar donuk kalmasın diye (concept drift): son eğitimden bu yana
# birikmiş yeni satır sayısı bu eşiği aşarsa, --delta ile çağrılmış olsa bile
# pipeline model_sonuclari'nı yine de sıfırdan eğitir (tahmin yerine).
RETRAIN_ESIK_SATIR = 5000

# 1. Veritabanına Bağlan ve Veriyi Çek
# timeout + WAL: pipeline'ın diğer adımlarıyla veya canlı izleme betiğiyle
# eşzamanlı erişimde "database is locked" hatasını önlemek için.
baglanti = sqlite3.connect("log_veritabani.db", timeout=15)
baglanti.execute("PRAGMA journal_mode=WAL;")
# (Tahmin işlemi çok hızlı olduğu için veritabanındaki tüm özellikleri okuyup üzerinden geçmek sistemi yormaz)
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
X = df[mevcut_kolonlar]

# --- SON EĞİTİMDEN BU YANA BİRİKEN SATIR SAYISINI ÖĞREN ---
try:
    son_kayit = pd.read_sql(
        "SELECT egitim_satir_sayisi FROM model_egitim_gecmisi ORDER BY id DESC LIMIT 1", baglanti
    )
    son_egitim_satiri = int(son_kayit.iloc[0]["egitim_satir_sayisi"]) if not son_kayit.empty else 0
except Exception:
    son_egitim_satiri = 0  # Tablo henüz yok: hiç eğitim yapılmamış demektir

model_dosyalari_var = os.path.exists(model_dosyasi) and os.path.exists(scaler_dosyasi)
yeni_satir_birikimi = len(df) - son_egitim_satiri
otomatik_yeniden_egitim_gerekli = (
    delta_modu and model_dosyalari_var and yeni_satir_birikimi >= RETRAIN_ESIK_SATIR
)

# =====================================================================
# 3. ve 4. ADIM: EĞİTİM (TRAIN) VEYA TAHMİN (INFERENCE) SEÇİMİ
# =====================================================================
if delta_modu and model_dosyalari_var and not otomatik_yeniden_egitim_gerekli:
    print("🧠 [Tahmin Modu] Eğitilmiş model hafızaya yükleniyor... (Sıfırdan eğitim atlandı)")
    
    # A. Daha önce eğitilmiş modeli ve scaler'ı diskten yükle
    scaler = joblib.load(scaler_dosyasi)
    model = joblib.load(model_dosyasi)
    
    # B. SADECE TRANSFORM VE PREDICT (Fit yok - Hız kazancı burada!)
    X_scaled = scaler.transform(X)
    df['Anomali_Skoru'] = model.predict(X_scaled)
    
    ayrisma_skoru_metni = "Tahmin modunda hesaplanmaz (Performans için atlandı)"

else:
    if otomatik_yeniden_egitim_gerekli:
        print(
            f"🔁 [Otomatik Yeniden Eğitim] Son eğitimden bu yana {yeni_satir_birikimi} yeni "
            f"kayıt birikti (eşik: {RETRAIN_ESIK_SATIR}) — model sıfırdan yeniden eğitiliyor..."
        )
    else:
        print("🏋️‍♂️ [Eğitim Modu] Model verilerle sıfırdan eğitiliyor...")

    # A. Modeli ve Scaler'ı sıfırdan oluştur ve eğit
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Ufak bir performans dokunuşu: n_jobs=1 yerine 2 yapılarak çökme önlendi
    model = IsolationForest(
        n_estimators=200,
        max_samples='auto',
        contamination=0.02,
        bootstrap=True,
        random_state=42,
        n_jobs=2  
    )

    df['Anomali_Skoru'] = model.fit_predict(X_scaled)
    
    # B. Gelecekteki delta (hızlı) okumaları için modeli diske kaydet
    joblib.dump(model, model_dosyasi)
    joblib.dump(scaler, scaler_dosyasi)
    
    # C. Sadece eğitim yapıldığında başarı skorunu hesapla
    ayrisma_skoru = silhouette_score(X_scaled, df['Anomali_Skoru'])
    ayrisma_skoru_metni = f"{ayrisma_skoru:.4f}"

    # D. Bu eğitimi geçmişe kaydet: hangi eşiğe göre tekrar eğitim gerektiğini
    # bir sonraki çalıştırmada buradan öğreneceğiz + zamanla model kalitesinin
    # (ayrışma skoru) nasıl seyrettiğini izlemek için kalıcı bir kayıt oluşur.
    baglanti.execute("""
        CREATE TABLE IF NOT EXISTS model_egitim_gecmisi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            egitim_zamani TEXT,
            egitim_satir_sayisi INTEGER,
            ayrisma_skoru REAL
        )
    """)
    baglanti.execute(
        "INSERT INTO model_egitim_gecmisi (egitim_zamani, egitim_satir_sayisi, ayrisma_skoru) VALUES (?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), len(df), float(ayrisma_skoru)),
    )
    baglanti.commit()

# 5. Anomali Durumunu Belirle (-1 anomali, 1 normal)
df['Anomali_Durumu'] = df['Anomali_Skoru'].apply(lambda x: 1 if x == -1 else 0)

# 6. Sonuçları Veritabanına Kaydet
df.to_sql("model_sonuclari", baglanti, if_exists="replace", index=False)
baglanti.close()

if delta_modu and model_dosyalari_var and not otomatik_yeniden_egitim_gerekli:
    calisma_modu_metni = "Tahmin (Inference)"
elif otomatik_yeniden_egitim_gerekli:
    calisma_modu_metni = "Otomatik Yeniden Eğitim (Concept Drift Eşiği Aşıldı)"
else:
    calisma_modu_metni = "Eğitim (Training)"

print("\n--- MODEL İŞLEM SONUÇLARI ---")
print(f"Çalışma Modu: {calisma_modu_metni}")
print(f"İncelenen Toplam Log Sayısı: {len(df)}")
print(f"Tespit Edilen Anomali Sayısı: {df['Anomali_Durumu'].sum()}")
print(f"Kümeleme Ayrışma Kalitesi: {ayrisma_skoru_metni}")