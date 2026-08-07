import pandas as pd
import numpy as np
import sqlite3
import warnings
import faiss
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

warnings.filterwarnings("ignore")

# --- NEDEN k-NN / FAISS DEĞERLENDİRİLİYOR? ---
# Üretimde artık Isolation Forest değil, FAISS tabanlı k-NN mesafe eşiği
# çalışıyor (bkz. model_egitimi.py). Bu script'in eski hâli hâlâ bağımsız
# bir Isolation Forest eğitip ölçüyordu — bu da üretimde çalışmayan bir
# algoritmayı test etmek anlamına gelirdi. Şimdi gerçekte çalışan yöntemin
# aynısını (k komşu sayısı + persentil eşiği) ızgara taramasıyla ölçüyoruz.
# Not: k-NN mesafesi (rastgele orman gibi) tohuma bağlı değildir — aynı veri
# ve aynı k için her zaman aynı sonucu verir. Bu yüzden artık "çoklu tohum"
# ortalaması gerekmiyor; bu, yöntemin bir dezavantajı değil, doğal bir
# avantajıdır (sonuç şansa bağlı değil).
KOMSU_SAYISI_ADAYLARI = [3, 5, 7, 10, 15]
ESIK_PERSENTIL_ADAYLARI = [95, 97, 98, 99]

# 1. İçinde sentetik verilerin de olduğu yeni tabloyu çekiyoruz
baglanti = sqlite3.connect("log_veritabani.db", timeout=15)
baglanti.execute("PRAGMA journal_mode=WAL;")
df_orijinal = pd.read_sql("SELECT * FROM ozellikli_loglar", baglanti)
df_birlesik = pd.read_sql("SELECT * FROM ozellikli_loglar_sentetikli", baglanti)
baglanti.close()

# 2. Özellik Hazırlama
ozellik_kolonlari = [
    'Saat', 'Hafta_Sonu', 'Mesai_Disi',
    'Basarisiz_Giris_Mi', 'Onceki_Islem_Farki_Sn',
    'Son_10Dk_Basarisiz_Deneme', 'Son_10Dk_IP_Islem_Sayisi'
]
y_gercek = df_birlesik['Is_Synthetic']

# Üretimdeki bootstrap mantığının birebir aynısı: scaler ve FAISS indeksi
# yalnızca GERÇEK (sentetiksiz) veriyle kurulur — sentetik saldırganlar daha
# sonra bu bilinen-normal indekse karşı SORGULANIR, indekse hiç eklenmez.
# Bu, "modelin daha önce hiç görmediği yeni bir saldırıyı tanıyabiliyor mu?"
# sorusuna gerçekçi bir cevap verir.
scaler = StandardScaler()
X_normal_scaled = scaler.fit_transform(df_orijinal[ozellik_kolonlari]).astype("float32")
X_tum_scaled = scaler.transform(df_birlesik[ozellik_kolonlari]).astype("float32")


def bir_deneme_calistir(k, persentil):
    index = faiss.IndexFlatL2(X_normal_scaled.shape[1])
    index.add(X_normal_scaled)

    # Eşik: normal verinin kendi içindeki k-NN mesafe dağılımının persentili
    # (kendisiyle eşleşmeyi hariç tutmak için k+1 sorgulanır).
    k_esik = min(k + 1, index.ntotal)
    mesafeler_normal, _ = index.search(X_normal_scaled, k_esik)
    skorlar_normal = mesafeler_normal[:, 1:].mean(axis=1)
    esik = np.percentile(skorlar_normal, persentil)

    # Tüm veri (normal + sentetik saldırganlar) aynı indekse karşı sorgulanır.
    k_sorgu = min(k, index.ntotal)
    mesafeler_tum, _ = index.search(X_tum_scaled, k_sorgu)
    skorlar_tum = mesafeler_tum.mean(axis=1)

    tahmin = (skorlar_tum > esik).astype(int)
    return {
        "precision": precision_score(y_gercek, tahmin, zero_division=0),
        "recall": recall_score(y_gercek, tahmin, zero_division=0),
        "f1": f1_score(y_gercek, tahmin, zero_division=0),
    }


# 3. K x PERSENTİL IZGARA TARAMASI
print(f"FAISS/k-NN yöntemi, {len(KOMSU_SAYISI_ADAYLARI)} farklı komşu sayısı x "
      f"{len(ESIK_PERSENTIL_ADAYLARI)} farklı eşik persentili ile "
      f"({len(KOMSU_SAYISI_ADAYLARI) * len(ESIK_PERSENTIL_ADAYLARI)} deneme) test ediliyor...\n")

sonuclar = []
for k in KOMSU_SAYISI_ADAYLARI:
    for persentil in ESIK_PERSENTIL_ADAYLARI:
        metrikler = bir_deneme_calistir(k, persentil)
        sonuclar.append({"k": k, "persentil": persentil, **metrikler})

sonuc_df = pd.DataFrame(sonuclar)

print("--- 📈 IZGARA TARAMASI SONUÇLARI ---")
for _, satir in sonuc_df.sort_values("f1", ascending=False).iterrows():
    print(
        f"k={int(satir['k']):<3} persentil={int(satir['persentil']):<3} | "
        f"F1: {satir['f1'] * 100:5.2f}%  | "
        f"Precision: {satir['precision'] * 100:5.2f}%  | "
        f"Recall: {satir['recall'] * 100:5.2f}%"
    )

en_iyi = sonuc_df.loc[sonuc_df["f1"].idxmax()]
print(f"\n🏆 En yüksek F1: k={int(en_iyi['k'])}, persentil={int(en_iyi['persentil'])} "
      f"(F1 = %{en_iyi['f1'] * 100:.2f}, Precision = %{en_iyi['precision'] * 100:.2f}, "
      f"Recall = %{en_iyi['recall'] * 100:.2f})")
print(f"ℹ️  model_egitimi.py içindeki KOMSU_SAYISI (şu an 5) ve ESIK_PERSENTIL (şu an 98) "
      f"değerleri bu sonuca göre gözden geçirilebilir; bu script değerleri otomatik değiştirmez, "
      f"karar insana bırakılır.")

# 4. En iyi (k, persentil) kombinasyonu için karmaşıklık matrisi
index_final = faiss.IndexFlatL2(X_normal_scaled.shape[1])
index_final.add(X_normal_scaled)
k_esik = min(int(en_iyi["k"]) + 1, index_final.ntotal)
mesafeler_normal, _ = index_final.search(X_normal_scaled, k_esik)
esik_final = np.percentile(mesafeler_normal[:, 1:].mean(axis=1), en_iyi["persentil"])
k_sorgu = min(int(en_iyi["k"]), index_final.ntotal)
mesafeler_tum, _ = index_final.search(X_tum_scaled, k_sorgu)
tahmin_final = (mesafeler_tum.mean(axis=1) > esik_final).astype(int)
karmasiklik_matrisi = confusion_matrix(y_gercek, tahmin_final)

print(f"\nKarmaşıklık Matrisi (k={int(en_iyi['k'])}, persentil={int(en_iyi['persentil'])}):")
print("[[Gerçek Negatif(TN)  Yanlış Pozitif(FP)]")
print(" [Yanlış Negatif(FN)  Gerçek Pozitif(TP)]]")
print(karmasiklik_matrisi)
