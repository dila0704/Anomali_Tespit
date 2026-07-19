import pandas as pd
import sqlite3
import warnings

warnings.filterwarnings("ignore")

# 1. Veritabanına bağlan ve temiz veriyi oku
baglanti = sqlite3.connect("log_veritabani.db")
df = pd.read_sql("SELECT * FROM anomali_loglari", baglanti)

# Zaman sütununu datetime formatına çevir ve kronolojik olarak sırala
df['Zaman'] = pd.to_datetime(df['Zaman'])
df = df.sort_values(by='Zaman')

# --- TEMEL ZAMAN ÖZELLİKLERİ ---
df['Saat'] = df['Zaman'].dt.hour
df['Haftanin_Gunu'] = df['Zaman'].dt.dayofweek
df['Hafta_Sonu'] = df['Haftanin_Gunu'].apply(lambda x: 1 if x >= 5 else 0)
df['Mesai_Disi'] = df['Saat'].apply(lambda x: 0 if 8 <= x <= 18 else 1)

# --- GELİŞMİŞ DAVRANIŞSAL ÖZELLİKLER ---

# Başarısız giriş bayrağı (Samba'da başarılı girişler genelde NT_STATUS_OK'dir)
df['Basarisiz_Giris_Mi'] = df['Durum'].apply(lambda x: 0 if x == 'NT_STATUS_OK' else 1)

# Kullanıcının bir önceki log kaydı ile arasındaki süre farkı (saniye cinsinden)
df['Onceki_Islem_Farki_Sn'] = df.groupby('Kullanici')['Zaman'].diff().dt.total_seconds().fillna(0)

# --- ZAMAN PENCERESİ (ROLLING WINDOW) ÖZELLİKLERİ ---
# Zaman serisi analizleri için index'i zaman yapıyoruz
df.set_index('Zaman', inplace=True)

# 1. Kullanıcının son 10 dakikadaki başarısız giriş sayısı (Brute-force tespiti)
df['Son_10Dk_Basarisiz_Deneme'] = df.groupby('Kullanici')['Basarisiz_Giris_Mi'].transform(lambda x: x.rolling('10min').sum())

# 2. IP adresinden son 10 dakikada gelen toplam istek sayısı (Bot/DDoS tespiti)
df['Son_10Dk_IP_Islem_Sayisi'] = df.groupby('IP_Adresi')['Olay_ID'].transform(lambda x: x.rolling('10min').count())

# Index'i eski haline getir
df.reset_index(inplace=True)

# Boş (NaN) değerleri 0 ile doldur
# Sadece matematiksel işlem yaptığımız sütunlardaki boşlukları 0 ile dolduruyoruz
sayisal_sutunlar = ['Onceki_Islem_Farki_Sn', 'Son_10Dk_Basarisiz_Deneme', 'Son_10Dk_IP_Islem_Sayisi']
df[sayisal_sutunlar] = df[sayisal_sutunlar].fillna(0)

# Çıktı Kontrolü
print("Gelişmiş Özelliklerle İlk 5 Satır:")
print(df[['Kullanici', 'IP_Adresi', 'Onceki_Islem_Farki_Sn', 'Son_10Dk_Basarisiz_Deneme', 'Son_10Dk_IP_Islem_Sayisi']].head())

# 4. Yeni tabloyu veritabanına kaydet
df['Zaman'] = df['Zaman'].astype(str)
df.to_sql("ozellikli_loglar", baglanti, if_exists="replace", index=False)
baglanti.close()

print("\nGelişmiş özellik çıkarımı tamamlandı ve 'ozellikli_loglar' tablosuna kaydedildi!")