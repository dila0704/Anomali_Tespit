import pandas as pd
import sqlite3
import joblib
import warnings
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

warnings.filterwarnings("ignore")

# 1. Veritabanına Bağlan ve Veriyi Çek
baglanti = sqlite3.connect("log_veritabani.db")
df = pd.read_sql("SELECT * FROM ozellikli_loglar", baglanti)

# 2. Özellik Seçimi
ozellik_kolonlari = [
    'Saat', 'Hafta_Sonu', 'Mesai_Disi', 
    'Basarisiz_Giris_Mi', 'Onceki_Islem_Farki_Sn', 
    'Son_10Dk_Basarisiz_Deneme', 'Son_10Dk_IP_Islem_Sayisi'
]
X = df[ozellik_kolonlari]

# 3. Veri Standardizasyonu (Özelliklerin aynı matematiksel ağırlıkta olmasını sağlar)
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# 4. Gelişmiş İzolasyon Ormanı Modeli
model = IsolationForest(
    n_estimators=200,          # Ağaç sayısı artırıldı (daha hassas karar)
    max_samples='auto',        # Örneklem boyutu otomatik optime edilir
    contamination=0.02,        # Anomali oranı tahmini (%2)
    bootstrap=True,            # Aşırı öğrenmeyi (overfitting) engeller
    random_state=42,
    n_jobs=1                  # İşlemi hızlandırmak için tüm CPU çekirdeklerini kullanır
)

# Eğit ve Tahmin Et
df['Anomali_Skoru'] = model.fit_predict(X_scaled)
df['Anomali_Durumu'] = df['Anomali_Skoru'].apply(lambda x: 1 if x == -1 else 0)

# 5. Unsupervised (Denetimsiz) Model Değerlendirmesi
# Silhouette skoru: Anomalilerin normal verilerden ne kadar iyi ayrıştığını ölçer (-1 ile 1 arası)
ayrisma_skoru = silhouette_score(X_scaled, df['Anomali_Skoru'])

# 6. Modeli ve Scaler'ı Dışa Aktarma (İleride API veya Arayüzden çağırabilmek için)
joblib.dump(model, 'isolation_forest_model.pkl')
joblib.dump(scaler, 'scaler.pkl')

# 7. Sonuçları Veritabanına Kaydet
df.to_sql("model_sonuclari", baglanti, if_exists="replace", index=False)
baglanti.close()

print("--- GELİŞMİŞ MODEL EĞİTİM SONUÇLARI ---")
print(f"İncelenen Toplam Log Sayısı: {len(df)}")
print(f"Tespit Edilen Anomali Sayısı: {df['Anomali_Durumu'].sum()}")
print(f"Kümeleme Ayrışma Kalitesi (Silhouette Skoru): {ayrisma_skoru:.4f}")
print("\nEğitilen model ('isolation_forest_model.pkl') ve ölçekleyici ('scaler.pkl') başarıyla dışa aktarıldı.")
