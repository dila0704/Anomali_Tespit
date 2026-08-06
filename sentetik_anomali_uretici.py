import pandas as pd
import sqlite3
import numpy as np

# 1. Veritabanına Bağlan ve Orijinal Logları Çek
baglanti = sqlite3.connect("log_veritabani.db", timeout=15)
baglanti.execute("PRAGMA journal_mode=WAL;")
df_orijinal = pd.read_sql("SELECT * FROM ozellikli_loglar", baglanti)

# Orijinal verilerimize "Is_Synthetic" (Sentetik mi?) adında bir etiket ekleyelim ve hepsine 0 diyelim.
# Bu bizim "Cevap Anahtarımız" olacak.
if 'Is_Synthetic' not in df_orijinal.columns:
    df_orijinal['Is_Synthetic'] = 0

print(f"Mevcut orijinal log sayısı: {len(df_orijinal)}")

# 2. Sentetik (Sahte) Anomali Üretimi
np.random.seed(42) # Sonuçların her çalışmada aynı çıkması için
sentetik_log_sayisi = 100 # 100 adet kesin saldırı logu üretiyoruz

# Tam bir 'Brute-Force' ve 'Bot' davranışı simüle ediyoruz
sentetik_anomaliler = pd.DataFrame({
    'Saat': np.random.randint(1, 4, sentetik_log_sayisi), # Gece yarısı 1-4 arası
    'Hafta_Sonu': np.random.choice([0, 1], sentetik_log_sayisi, p=[0.2, 0.8]),
    'Mesai_Disi': 1,
    'Basarisiz_Giris_Mi': 1,
    'Onceki_Islem_Farki_Sn': np.random.uniform(0.01, 0.2, sentetik_log_sayisi), # İnsanüstü bir hız
    'Son_10Dk_Basarisiz_Deneme': np.random.randint(80, 150, sentetik_log_sayisi), # Peş peşe hata
    'Son_10Dk_IP_Islem_Sayisi': np.random.randint(300, 600, sentetik_log_sayisi), # Aynı IP'den saldırı
    'Is_Synthetic': 1 # İşte cevap anahtarımız! (Bunlar kesinlikle saldırgan)
})

# Orijinal veritabanında olan ancak sentetik veride olmayan diğer kolonları eksiksiz dolduralım (NaN kalmasın)
for kolon in df_orijinal.columns:
    if kolon not in sentetik_anomaliler.columns:
        # Metin kolonlarına 'Sentetik_IP' veya 'Sentetik_User' gibi değerler atayalım
        if df_orijinal[kolon].dtype == 'object':
            sentetik_anomaliler[kolon] = f"Sentetik_Veri_{kolon}"
        else:
            sentetik_anomaliler[kolon] = 0

# Orijinal verilerle sentetik verileri birleştiriyoruz
df_birlesik = pd.concat([df_orijinal, sentetik_anomaliler], ignore_index=True)

# 3. Yeni Veriyi Veritabanına Kaydet
# Modeli yeniden eğitirken bu yeni tabloyu kullanacağız
df_birlesik.to_sql("ozellikli_loglar_sentetikli", baglanti, if_exists="replace", index=False)
baglanti.close()

print(f"Üretilen sentetik anomali sayısı: {len(sentetik_anomaliler)}")
print(f"Toplam yeni log sayısı: {len(df_birlesik)}")
print("\n[BİLGİ] İçine 100 adet 'kırmızı bültenli' saldırgan gizlenmiş yeni veriseti 'ozellikli_loglar_sentetikli' tablosuna kaydedildi.")