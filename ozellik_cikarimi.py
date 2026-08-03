import pandas as pd
import sqlite3
import warnings
import sys

warnings.filterwarnings("ignore")

# --- DELTA MODU KONTROLÜ ---
delta_modu = "--delta" in sys.argv

# 1. Veritabanına bağlan
baglanti = sqlite3.connect("log_veritabani.db")

# Delta modundaysak, hedef tabloda şu an kaç satır olduğunu öğrenelim
mevcut_satir_sayisi = 0
if delta_modu:
    try:
        imlec = baglanti.execute("SELECT COUNT(*) FROM ozellikli_loglar")
        mevcut_satir_sayisi = imlec.fetchone()[0]
    except sqlite3.OperationalError:
        mevcut_satir_sayisi = 0 # Tablo henüz yoksa 0 kabul et

df = pd.read_sql("SELECT * FROM anomali_loglari", baglanti)

# Yeni işlenecek satır sayısını hesapla
toplam_satir = len(df)
yeni_satir_sayisi = toplam_satir - mevcut_satir_sayisi

if delta_modu and yeni_satir_sayisi <= 0:
    print("İşlenecek yeni log bulunamadı (Özellik Çıkarımı atlanıyor).")
    sys.exit(99)

# Zaman sütununu datetime formatına çevir ve kronolojik olarak sırala
df['Zaman'] = pd.to_datetime(df['Zaman'], errors='coerce')
df = df.sort_values(by='Zaman')

# --- TEMEL ZAMAN ÖZELLİKLERİ ---
df['Saat'] = df['Zaman'].dt.hour
df['Haftanin_Gunu'] = df['Zaman'].dt.dayofweek
df['Hafta_Sonu'] = df['Haftanin_Gunu'].apply(lambda x: 1 if x >= 5 else 0)
df['Mesai_Disi'] = df['Saat'].apply(lambda x: 0 if 8 <= x <= 18 else 1)

# --- GELİŞMİŞ DAVRANIŞSAL ÖZELLİKLER ---
df['Basarisiz_Giris_Mi'] = df['Durum'].apply(lambda x: 0 if x == 'NT_STATUS_OK' else 1)
df['Onceki_Islem_Farki_Sn'] = df.groupby('Kullanici')['Zaman'].diff().dt.total_seconds().fillna(0)

# --- ZAMAN PENCERESİ (ROLLING WINDOW) ÖZELLİKLERİ ---
df.set_index('Zaman', inplace=True)
df['Son_10Dk_Basarisiz_Deneme'] = df.groupby('Kullanici')['Basarisiz_Giris_Mi'].transform(lambda x: x.rolling('10min').sum())
df['Son_10Dk_IP_Islem_Sayisi'] = df.groupby('IP_Adresi')['Olay_ID'].transform(lambda x: x.rolling('10min').count())
df.reset_index(inplace=True)

sayisal_sutunlar = ['Onceki_Islem_Farki_Sn', 'Son_10Dk_Basarisiz_Deneme', 'Son_10Dk_IP_Islem_Sayisi']
df[sayisal_sutunlar] = df[sayisal_sutunlar].fillna(0)

# 4. Veritabanına Kaydetme (DELTA MANTIĞI BURADA ÇALIŞIYOR)
df['Zaman'] = df['Zaman'].astype(str)

if delta_modu and mevcut_satir_sayisi > 0:
    # Sadece en sondaki yeni satırları kesip al
    yeni_df = df.tail(yeni_satir_sayisi)
    yeni_df.to_sql("ozellikli_loglar", baglanti, if_exists="append", index=False)
    print(f"[{yeni_satir_sayisi}] adet yeni özellikli log veritabanına EKLENDİ (Append).")
else:
    # Tam taramada tabloyu sıfırdan oluştur
    df.to_sql("ozellikli_loglar", baglanti, if_exists="replace", index=False)
    print(f"Tüm özellikli loglar ({toplam_satir} adet) BAŞTAN YAZILDI (Replace).")

baglanti.close()