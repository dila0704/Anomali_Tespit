import pandas as pd
import sqlite3
import joblib
import warnings
import sys
import os
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

warnings.filterwarnings("ignore")

# --- KAN-38: ÇALIŞMA MODU BELİRLEME ---
# Eğer pipeline'dan --delta geldiyse sistemi yormamak için "Tahmin" moduna geçeceğiz.
delta_modu = "--delta" in sys.argv
model_dosyasi = 'isolation_forest_model.pkl'
scaler_dosyasi = 'scaler.pkl'

# 1. Veritabanına Bağlan ve Veriyi Çek
baglanti = sqlite3.connect("log_veritabani.db")
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

# =====================================================================
# 3. ve 4. ADIM: EĞİTİM (TRAIN) VEYA TAHMİN (INFERENCE) SEÇİMİ
# =====================================================================
if delta_modu and os.path.exists(model_dosyasi) and os.path.exists(scaler_dosyasi):
    print("🧠 [Tahmin Modu] Eğitilmiş model hafızaya yükleniyor... (Sıfırdan eğitim atlandı)")
    
    # A. Daha önce eğitilmiş modeli ve scaler'ı diskten yükle
    scaler = joblib.load(scaler_dosyasi)
    model = joblib.load(model_dosyasi)
    
    # B. SADECE TRANSFORM VE PREDICT (Fit yok - Hız kazancı burada!)
    X_scaled = scaler.transform(X)
    df['Anomali_Skoru'] = model.predict(X_scaled)
    
    ayrisma_skoru_metni = "Tahmin modunda hesaplanmaz (Performans için atlandı)"

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

# 5. Anomali Durumunu Belirle (-1 anomali, 1 normal)
df['Anomali_Durumu'] = df['Anomali_Skoru'].apply(lambda x: 1 if x == -1 else 0)

# 6. Sonuçları Veritabanına Kaydet
df.to_sql("model_sonuclari", baglanti, if_exists="replace", index=False)
baglanti.close()

print("\n--- MODEL İŞLEM SONUÇLARI ---")
print(f"Çalışma Modu: {'Tahmin (Inference)' if delta_modu else 'Eğitim (Training)'}")
print(f"İncelenen Toplam Log Sayısı: {len(df)}")
print(f"Tespit Edilen Anomali Sayısı: {df['Anomali_Durumu'].sum()}")
print(f"Kümeleme Ayrışma Kalitesi: {ayrisma_skoru_metni}")