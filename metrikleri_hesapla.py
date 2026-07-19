import pandas as pd
import sqlite3
import warnings
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

warnings.filterwarnings("ignore")

# 1. İçinde sentetik verilerin de olduğu yeni tabloyu çekiyoruz
baglanti = sqlite3.connect("log_veritabani.db")
df = pd.read_sql("SELECT * FROM ozellikli_loglar_sentetikli", baglanti)

# 2. Modeli Eğitmek İçin Özellikleri Hazırlama
ozellik_kolonlari = [
    'Saat', 'Hafta_Sonu', 'Mesai_Disi', 
    'Basarisiz_Giris_Mi', 'Onceki_Islem_Farki_Sn', 
    'Son_10Dk_Basarisiz_Deneme', 'Son_10Dk_IP_Islem_Sayisi'
]
X = df[ozellik_kolonlari]

# Standardizasyon
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# 3. Modeli Yeniden Eğit ve Tahmin Yaptır (Aynı ayarlarla)
print("Yapay Zeka sentetik verilerle test ediliyor...")
model = IsolationForest(n_estimators=200, contamination=0.02, n_jobs=1, random_state=42)
df['YZ_Tahmini'] = model.fit_predict(X_scaled)

# Isolation Forest -1'leri anomali kabul eder. Biz bunu 1 yapalım (Tehdit=1, Temiz=0)
df['YZ_Tahmini'] = df['YZ_Tahmini'].apply(lambda x: 1 if x == -1 else 0)

# 4. METRİKLERİ HESAPLAMA (Karne Vakti)
# Cevap Anahtarı: Bizim kendi ellerimizle koyduğumuz sentetik loglar (Is_Synthetic == 1)
y_gercek = df['Is_Synthetic']
y_tahmin = df['YZ_Tahmini']

kesinlik = precision_score(y_gercek, y_tahmin, zero_division=0)
duyarlilik = recall_score(y_gercek, y_tahmin, zero_division=0)
f1 = f1_score(y_gercek, y_tahmin, zero_division=0)
karmasiklik_matrisi = confusion_matrix(y_gercek, y_tahmin)

print("\n--- 📈 YAPAY ZEKA PERFORMANS KARNESİ 📈 ---")
print(f"Sisteme Eklenen Sentetik Saldırgan Sayısı: {y_gercek.sum()}")
print(f"Yapay Zekanın Toplam Anomali Dediği Sayı : {y_tahmin.sum()}")

print(f"\n🎯 Duyarlılık (Recall) : %{duyarlilik * 100:.2f}  <-- (Bizim koyduğumuz 100 hedefin kaçını bulabildi?)")
print(f"🔪 Kesinlik (Precision): %{kesinlik * 100:.2f}  <-- (Anomali dediklerinin yüzde kaçı BİZİM koyduğumuz sahte veriler?)")
print(f"⚖️ F1 Skoru            : %{f1 * 100:.2f}  <-- (Genel başarı puanı)")

print("\nKarmaşıklık Matrisi (Confusion Matrix):")
print("[[Gerçek Negatif(TN)  Yanlış Pozitif(FP)]")
print(" [Yanlış Negatif(FN)  Gerçek Pozitif(TP)]]")
print(karmasiklik_matrisi)

baglanti.close()