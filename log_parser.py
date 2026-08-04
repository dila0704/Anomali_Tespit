import pandas as pd
import json
import sqlite3
import warnings
import sys
import os

# Konsoldaki gereksiz Pandas uyarılarını kapatıyorum
warnings.filterwarnings("ignore") 
dosya_yolu = "samba_audit_user_anomaly_dataset_large.log"
bookmark_dosyasi = "bookmark.txt" # Kaldığımız yeri (byte) tutacağımız dosya

def log_ayristir(dosya_yolu, delta_modu=False):
    veri = []
    baslangic_bayti = 0

    # 1. Delta modu aktifse hafızaya bak, nerede kalmıştık?
    if delta_modu and os.path.exists(bookmark_dosyasi):
        with open(bookmark_dosyasi, "r") as bf:
            try:
                baslangic_bayti = int(bf.read().strip())
            except ValueError:
                baslangic_bayti = 0

    yeni_bayt_konumu = baslangic_bayti

    # 2. Log dosyasını okuma işlemi
    with open(dosya_yolu, "r", encoding="utf-8") as f:
        # Eğer Delta (Yeni Log) okuyacaksak dosyayı baştan değil, son kaldığımız byte'tan başlat
        if delta_modu:
            f.seek(baslangic_bayti) 
        
        for satir in f:
            if satir.strip(): 
                try:
                    veri.append(json.loads(satir))
                except json.JSONDecodeError:
                    continue 
        
        # Okuma bitti, dosyanın en sonundaki yeni byte konumunu öğren
        yeni_bayt_konumu = f.tell()

    # Eğer eklenecek yeni log yoksa boş dön
    if not veri:
        return pd.DataFrame(), yeni_bayt_konumu

    # 3. JSON'ı DataFrame'e çevir
    df = pd.json_normalize(veri)

    # 4. Gerekli Sütunları Seç (Eksik sütun hatasını önlemek için mevcutları filtreliyoruz)
    gerekli_sutunlar = [
        'timestamp', 
        'Authentication.clientAccount', 
        'Authentication.remoteAddress', 
        'Authentication.status',
        'Authentication.eventId'
    ]
    mevcut_sutunlar = [col for col in gerekli_sutunlar if col in df.columns]
    df = df[mevcut_sutunlar]

    # 5. Sütun isimlerini sadeleştir
    sutun_haritasi = {
        'timestamp': 'Zaman',
        'Authentication.clientAccount': 'Kullanici',
        'Authentication.remoteAddress': 'IP_Adresi',
        'Authentication.status': 'Durum',
        'Authentication.eventId': 'Olay_ID'
    }
    df.rename(columns=sutun_haritasi, inplace=True)

    # 6. RegEx ve Zaman Temizliği
    if 'IP_Adresi' in df.columns:
        df['IP_Adresi'] = df['IP_Adresi'].astype(str).str.extract(r'ipv4:(.*?):')
    
    if 'Zaman' in df.columns:
        df['Zaman'] = pd.to_datetime(df['Zaman'], utc=True, errors='coerce')
        
    return df, yeni_bayt_konumu

# ÇALIŞTIRMA VE KAYDETME KISMI
if __name__ == "__main__":
    # Orkestra şefinden (pipeline_calistir.py) delta argümanı geldi mi kontrol et
    delta_modu = "--delta" in sys.argv
    mod_ismi = "Delta (Sadece Yeni Loglar)" if delta_modu else "Tam Tarama (Tüm Loglar)"
    
    print(f"[{mod_ismi}] Loglar okunuyor...")
    
    sonuc_df, yeni_konum = log_ayristir(dosya_yolu, delta_modu)
    
    if sonuc_df.empty:
        print("Sistemde işlenecek yeni bir log bulunamadı. Parse işlemi atlanıyor.")
        sys.exit(99) # Başarıyla çıkış yap, hata verme
    
    print(f"\nAyrıştırılmış Yeni Log Sayısı: {len(sonuc_df)}")
    
    # 7. Veriyi SQLite veritabanına kaydetme
    baglanti = sqlite3.connect("log_veritabani.db")
    
    if 'Zaman' in sonuc_df.columns:
        sonuc_df['Zaman'] = sonuc_df['Zaman'].astype(str)
    
    # KRİTİK NOKTA: Delta modundaysak veritabanının üzerine YAZMA, sonuna EKLE (append)
    kayit_modu = "append" if delta_modu else "replace"
    sonuc_df.to_sql("anomali_loglari", baglanti, if_exists=kayit_modu, index=False)
    baglanti.close()
    
    # 8. Başarıyla işlendiyse, bir sonraki tarama için kalınan yeri kaydet.
    # KRİTİK: Tam tarama sonrası bookmark'ı SİLMEK yerine dosyanın o anki son
    # byte konumuyla YENİDEN YAZIYORUZ. Aksi halde tam taramadan hemen sonra
    # çalışacak bir delta taraması bookmark'ı bulamaz, dosyayı baştan (byte 0)
    # okur ve tüm logları mükerrer (duplicate) şekilde tekrar ekler.
    with open(bookmark_dosyasi, "w") as bf:
        bf.write(str(yeni_konum))
            
    print(f"İşlem Tamamlandı! {len(sonuc_df)} adet yeni satır SQLite 'log_veritabani.db' dosyasına {kayit_modu.upper()} yöntemiyle aktarıldı.")