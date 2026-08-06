import pandas as pd
import numpy as np
import sqlite3
import warnings
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

warnings.filterwarnings("ignore")

# --- NEDEN ÇOKLU TOHUM (SEED) VE ÇOKLU CONTAMINATION? ---
# Eski sürüm modeli TEK bir random_state (42) ve TEK bir contamination (0.02)
# ile bir kez eğitip tek bir F1 skoru veriyordu. Bu, "şansa" bağlı, gürültülü
# bir ölçümdür: farklı bir tohumla model biraz farklı ayrılabilir. Burada aynı
# sentetik veri kümesi üzerinde birkaç tohumla tekrarlanan, ortalama + standart
# sapma raporlayan ve birkaç contamination değerini karşılaştıran küçük bir
# deney kurgusuna geçiyoruz; bu, tek noktalık bir sayıdan çok daha güvenilir
# bir performans tahmini verir.
TOHUMLAR = [42, 7, 123, 2024, 99]
CONTAMINATION_ADAYLARI = [0.01, 0.02, 0.03, 0.05, 0.1]

# 1. İçinde sentetik verilerin de olduğu yeni tabloyu çekiyoruz
baglanti = sqlite3.connect("log_veritabani.db", timeout=15)
baglanti.execute("PRAGMA journal_mode=WAL;")
df = pd.read_sql("SELECT * FROM ozellikli_loglar_sentetikli", baglanti)
baglanti.close()

# 2. Modeli Eğitmek İçin Özellikleri Hazırlama
ozellik_kolonlari = [
    'Saat', 'Hafta_Sonu', 'Mesai_Disi',
    'Basarisiz_Giris_Mi', 'Onceki_Islem_Farki_Sn',
    'Son_10Dk_Basarisiz_Deneme', 'Son_10Dk_IP_Islem_Sayisi'
]
X = df[ozellik_kolonlari]
y_gercek = df['Is_Synthetic']

# Standardizasyon (tüm denemeler için aynı ölçeklenmiş veri kullanılır)
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)


def bir_deneme_calistir(contamination, tohum):
    model = IsolationForest(n_estimators=200, contamination=contamination, n_jobs=1, random_state=tohum)
    tahmin = model.fit_predict(X_scaled)
    tahmin = np.where(tahmin == -1, 1, 0)  # -1 (anomali) -> 1 (Tehdit), 1 -> 0 (Temiz)
    return {
        "precision": precision_score(y_gercek, tahmin, zero_division=0),
        "recall": recall_score(y_gercek, tahmin, zero_division=0),
        "f1": f1_score(y_gercek, tahmin, zero_division=0),
    }


# 3. ÇOKLU TOHUM x ÇOKLU CONTAMINATION IZGARA TARAMASI
print(f"Yapay Zeka, {len(TOHUMLAR)} farklı tohum x {len(CONTAMINATION_ADAYLARI)} farklı "
      f"contamination değeriyle ({len(TOHUMLAR) * len(CONTAMINATION_ADAYLARI)} deneme) test ediliyor...\n")

sonuclar = []
for contamination in CONTAMINATION_ADAYLARI:
    for tohum in TOHUMLAR:
        metrikler = bir_deneme_calistir(contamination, tohum)
        sonuclar.append({"contamination": contamination, "tohum": tohum, **metrikler})

sonuc_df = pd.DataFrame(sonuclar)

# Her contamination değeri için tohumlar arası ortalama + standart sapma
ozet = sonuc_df.groupby("contamination")[["precision", "recall", "f1"]].agg(["mean", "std"])

print("--- 📈 IZGARA TARAMASI ÖZETİ (Tohumlar Arası Ortalama ± Std) ---")
for contamination, satir in ozet.iterrows():
    print(
        f"contamination={contamination:<5} | "
        f"F1: {satir[('f1', 'mean')] * 100:5.2f}% ± {satir[('f1', 'std')] * 100:4.2f}  | "
        f"Precision: {satir[('precision', 'mean')] * 100:5.2f}%  | "
        f"Recall: {satir[('recall', 'mean')] * 100:5.2f}%"
    )

en_iyi_contamination = ozet[("f1", "mean")].idxmax()
en_iyi_f1_ortalama = ozet.loc[en_iyi_contamination, ("f1", "mean")]
en_iyi_f1_std = ozet.loc[en_iyi_contamination, ("f1", "std")]

print(f"\n🏆 En yüksek ortalama F1: contamination={en_iyi_contamination} "
      f"(F1 = %{en_iyi_f1_ortalama * 100:.2f} ± {en_iyi_f1_std * 100:.2f})")
print(f"ℹ️  model_egitimi.py içindeki contamination değeri (şu an 0.02) bu sonuca göre "
      f"gözden geçirilebilir; bu script değeri otomatik değiştirmez, karar insana bırakılır.")

# 4. Karmaşıklık matrisini, en iyi contamination + ilk tohumla (42) tek bir
# örnek üzerinden göstermeye devam edelim (yorumlanabilirlik için).
ornek_tahmin = IsolationForest(
    n_estimators=200, contamination=en_iyi_contamination, n_jobs=1, random_state=42
).fit_predict(X_scaled)
ornek_tahmin = np.where(ornek_tahmin == -1, 1, 0)
karmasiklik_matrisi = confusion_matrix(y_gercek, ornek_tahmin)

print(f"\nKarmaşıklık Matrisi (contamination={en_iyi_contamination}, tohum=42 örneği):")
print("[[Gerçek Negatif(TN)  Yanlış Pozitif(FP)]")
print(" [Yanlış Negatif(FN)  Gerçek Pozitif(TP)]]")
print(karmasiklik_matrisi)