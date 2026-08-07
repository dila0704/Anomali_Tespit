import pandas as pd
import sqlite3
import joblib
import warnings
import sys
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

warnings.filterwarnings("ignore")

model_dosyasi = 'isolation_forest_model.pkl'
scaler_dosyasi = 'scaler.pkl'

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
X = df[mevcut_kolonlar]

# =====================================================================
# 3. SÜREKLİ EĞİTİM: HER ÇALIŞMADA MODEL SIFIRDAN YENİDEN EĞİTİLİR
# =====================================================================
# Not: pipeline_calistir.py, işlenecek yeni log yoksa log_parser.py'ın attığı
# exit code 99 ile daha bu betiğe hiç gelmeden kısa devre yapıyor. Yani bu
# satıra ulaşıldıysa mutlaka yeni veri vardır — "belirli bir birikim olunca
# eğit" gibi bir eşik beklemeden, her turda güncel veriyle sıfırdan eğitiyoruz.
print(f"🏋️‍♂️ [Sürekli Eğitim] Model, güncel {len(df)} kayıtla sıfırdan yeniden eğitiliyor...")

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

# Modeli diske kaydet (kullanici_sorgula.py gibi başka araçlar için referans)
joblib.dump(model, model_dosyasi)
joblib.dump(scaler, scaler_dosyasi)

ayrisma_skoru = silhouette_score(X_scaled, df['Anomali_Skoru'])

# Bu eğitimi geçmişe kaydet: zamanla model kalitesinin (ayrışma skoru) nasıl
# seyrettiğini izlemek için kalıcı bir kayıt oluşturur.
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

# 4. Anomali Durumunu Belirle (-1 anomali, 1 normal)
df['Anomali_Durumu'] = df['Anomali_Skoru'].apply(lambda x: 1 if x == -1 else 0)

# 5. Sonuçları Veritabanına Kaydet
df.to_sql("model_sonuclari", baglanti, if_exists="replace", index=False)
baglanti.close()

print("\n--- MODEL İŞLEM SONUÇLARI ---")
print("Çalışma Modu: Sürekli Eğitim (her pipeline turunda sıfırdan fit)")
print(f"İncelenen Toplam Log Sayısı: {len(df)}")
print(f"Tespit Edilen Anomali Sayısı: {df['Anomali_Durumu'].sum()}")
print(f"Kümeleme Ayrışma Kalitesi: {ayrisma_skoru:.4f}")
