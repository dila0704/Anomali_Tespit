import pandas as pd
import json
import sqlite3
import warnings

# Konsoldaki gereksiz Pandas uyarılarını kapatıyorum
warnings.filterwarnings("ignore") 
dosya_yolu = "samba_audit_user_anomaly_dataset_large.log"

def log_ayristir(dosya_yolu):
    veri = []
    
    # 1. Belleği (RAM) yormamak için log dosyasını satır satır okuyorum
    with open(dosya_yolu, "r", encoding="utf-8") as f:
        for satir in f:
            if satir.strip(): 
                try:
                    # Gelen metni JSON nesnesine çevir
                    veri.append(json.loads(satir))
                except json.JSONDecodeError:
                    continue # Hatalı formatlı satırları atla

    # 2. İç içe (nested) JSON yapısını düz bir tabloya (DataFrame) çeviriyorum
    df = pd.json_normalize(veri)

    # 3. Modelde gürültüyü azaltmak için sadece anomali tespitine yarayacak sütunları seçiyorum
    gerekli_sutunlar = [
        'timestamp', 
        'Authentication.clientAccount', 
        'Authentication.remoteAddress', 
        'Authentication.status',
        'Authentication.eventId'
    ]
    df = df[gerekli_sutunlar]

    # 4. Daha rahat kod yazabilmek için sütun isimlerini sadeleştiriyorum
    df.columns = ['Zaman', 'Kullanici', 'IP_Adresi', 'Durum', 'Olay_ID']

    # 5. RegEx ile IP adresini port numarasından arındırıp temizliyorum (örn: ipv4:10.0.0.1:4545 -> 10.0.0.1)
    df['IP_Adresi'] = df['IP_Adresi'].str.extract(r'ipv4:(.*?):')

    # 6. Saat/zaman analizi yapabilmek için metin formatındaki tarihi DateTime objesine dönüştürüyorum
    df['Zaman'] = pd.to_datetime(df['Zaman'])

    return df

# ÇALIŞTIRMA VE KAYDETME KISMI
if __name__ == "__main__":
    print("Loglar okunuyor ve ayrıştırılıyor. Dosya büyük olduğu için biraz sürebilir...")
    
    # "ornek.log" yerine yukarıda tanımladığımız dosya_yolu değişkenini kullanıyoruz
    sonuc_df = log_ayristir(dosya_yolu)
    
    print("\nAyrıştırılmış İlk 5 Log Satırı:")
    print(sonuc_df.head())
    
    # 7. Veriyi SQLite veritabanına kaydetme
    print("\nVeriler SQLite veritabanına yazılıyor...")
    baglanti = sqlite3.connect("log_veritabani.db")
    
    # Zaman (datetime) objelerini SQLite'a yazarken hata almamak için metne (string) çeviriyoruz
    sonuc_df['Zaman'] = sonuc_df['Zaman'].astype(str)
    
    sonuc_df.to_sql("anomali_loglari", baglanti, if_exists="replace", index=False)
    baglanti.close()
    
    print("İşlem Tamamlandı! Veriler 'log_veritabani.db' dosyasına kaydedildi.")