import pandas as pd
import sqlite3
import warnings
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

warnings.filterwarnings("ignore")

# 1. Veritabanına Bağlan ve Orijinal Logları Çek
baglanti = sqlite3.connect("log_veritabani.db")
df = pd.read_sql("SELECT * FROM ozellikli_loglar", baglanti)

# 2. Özellik Seçimi (Isolation Forest ile aynı şartlarda yarışmaları için aynı sütunları veriyoruz)
ozellik_kolonlari = [
    'Saat', 'Hafta_Sonu', 'Mesai_Disi', 
    'Basarisiz_Giris_Mi', 'Onceki_Islem_Farki_Sn', 
    'Son_10Dk_Basarisiz_Deneme', 'Son_10Dk_IP_Islem_Sayisi'
]
X = df[ozellik_kolonlari]

# 3. Veri Standardizasyonu
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# 4. LOF (Local Outlier Factor) Modelini Kur
print("LOF Modeli eğitiliyor, lütfen bekleyin...")
lof_model = LocalOutlierFactor(
    n_neighbors=20,        # Komşuluk sayısı (Genelde 20 en ideal sonuçları verir)
    contamination=0.02,    # Anomali oranı beklentimiz (Adil kıyas için yine %2 verdik)
    n_jobs=1               # İşlemciyi kilitlememek için tek çekirdekte çalıştırıyoruz
)

# Eğit ve Tahmin Et (-1 Anomali, 1 Normal)
df['LOF_Anomali_Skoru'] = lof_model.fit_predict(X_scaled)
df['LOF_Anomali_Durumu'] = df['LOF_Anomali_Skoru'].apply(lambda x: 1 if x == -1 else 0)

# 5. Model Performansı Değerlendirme (Silhouette Skoru)
lof_ayrisma_skoru = silhouette_score(X_scaled, df['LOF_Anomali_Skoru'])

# 6. Eski Isolation Forest Sonuçlarıyla Karşılaştırma
df_eski = pd.read_sql("SELECT Anomali_Durumu FROM model_sonuclari", baglanti)
if_anomali_sayisi = df_eski['Anomali_Durumu'].sum()
lof_anomali_sayisi = df['LOF_Anomali_Durumu'].sum()

print("\n--- 🤖 YAPAY ZEKA ALGORİTMALARI KAPIŞMASI 🤖 ---")
print(f"Toplam İncelenen Log: {len(df)}")
print(f"🌲 Isolation Forest'ın Bulduğu Anomali: {if_anomali_sayisi}")
print(f"🎯 LOF'un Bulduğu Anomali: {lof_anomali_sayisi}")
print(f"LOF Kümeleme Ayrışma Kalitesi (Silhouette Skoru): {lof_ayrisma_skoru:.4f}")

# İki modelin de anomali dediği (Ortak Karar) kayıtları bulalım
ortak_tehditler = (df_eski['Anomali_Durumu'] == 1) & (df['LOF_Anomali_Durumu'] == 1)
print(f"🤝 Her İki Modelin Ortak Yakaladığı Kesin Anomali Sayısı: {ortak_tehditler.sum()}")

# 7. LOF Sonuçlarını Yeni Tablo Olarak Kaydet
df.to_sql("lof_model_sonuclari", baglanti, if_exists="replace", index=False)
baglanti.close()

print("\n[BİLGİ] LOF sonuçları 'lof_model_sonuclari' tablosuna kaydedildi.")