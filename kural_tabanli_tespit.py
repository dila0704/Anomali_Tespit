import pandas as pd
import sqlite3

class HibritGuvenlikSistemi:
    def __init__(self, db_yolu="log_veritabani.db"):
        # Sınıf başlatıldığında veritabanı yolu tanımlanır
        self.db_yolu = db_yolu

    def veriyi_getir(self, tablo_adi="model_sonuclari"):
        # Veritabanından veriyi çeken bağımsız fonksiyon
        baglanti = sqlite3.connect(self.db_yolu)
        df = pd.read_sql(f"SELECT * FROM {tablo_adi}", baglanti)
        baglanti.close()
        return df

    def kurallari_uygula(self, df):
        # Kural mantığını işleten ana motor
        df['Kural_Ihlali'] = "Yok"
        df['Kural_Skoru'] = 0

        # KURAL 1: Brute-Force
        brute_force_sarti = df['Son_10Dk_Basarisiz_Deneme'] > 5
        df.loc[brute_force_sarti, 'Kural_Ihlali'] = "Brute-Force Şüphesi"
        df.loc[brute_force_sarti, 'Kural_Skoru'] += 50

        # KURAL 2: Mesai Dışı / Hafta Sonu
        mesai_disi_sarti = ((df['Mesai_Disi'] == 1) | (df['Hafta_Sonu'] == 1)) & (df['Basarisiz_Giris_Mi'] == 1)
        df.loc[mesai_disi_sarti, 'Kural_Ihlali'] = "Mesai Dışı Başarısız Giriş"
        df.loc[mesai_disi_sarti, 'Kural_Skoru'] += 30

        # KURAL 3: Bot veya Script Şüphesi
        bot_sarti = (df['Onceki_Islem_Farki_Sn'] < 1) & (df['Son_10Dk_IP_Islem_Sayisi'] > 50)
        df.loc[bot_sarti, 'Kural_Ihlali'] = "Bot/Script Şüphesi"
        df.loc[bot_sarti, 'Kural_Skoru'] += 40

        # KURAL 4: HİBRİT TESPİT (Yapay Zeka + Kural Ortak Kararı)
        kesin_tehdit_sarti = (df['Kural_Skoru'] > 0) & (df['Anomali_Durumu'] == 1)
        df.loc[kesin_tehdit_sarti, 'Kural_Ihlali'] = df.loc[kesin_tehdit_sarti, 'Kural_Ihlali'] + " (+ YZ Onaylı)"
        df.loc[kesin_tehdit_sarti, 'Kural_Skoru'] += 100

        return df

    def sonuclari_raporla(self, df):
        # Ekrana rapor basma işlemini izole ettik
        kurala_takilanlar = df[df['Kural_Skoru'] > 0]
        kesin_tehdit_sarti = (df['Kural_Skoru'] > 0) & (df['Anomali_Durumu'] == 1)

        print("--- 🛡️ HİBRİT GÜVENLİK SİSTEMİ RAPORU 🛡️ ---")
        print(f"Toplam İncelenen Log: {len(df)}")
        print(f"Sadece Yapay Zekanın Bulduğu: {df['Anomali_Durumu'].sum()}")
        print(f"Kurallara Takılan: {len(kurala_takilanlar)}")
        print(f"Kesin Tehdit (YZ + Kural): {len(df[kesin_tehdit_sarti])}")
        
        print("\n🚨 İhlal Türlerine Göre Dağılım:")
        print(kurala_takilanlar['Kural_Ihlali'].value_counts())

    def veritabanina_kaydet(self, df, tablo_adi="hibrit_tespit_sonuclari"):
        # Kayıt işlemini yöneten fonksiyon
        baglanti = sqlite3.connect(self.db_yolu)
        df.to_sql(tablo_adi, baglanti, if_exists="replace", index=False)
        baglanti.close()
        print(f"\n[BİLGİ] Tüm analizler '{tablo_adi}' tablosuna başarıyla kaydedildi.")

    def calistir(self):
        # Sistemin tüm parçalarını sırasıyla orkestra eden ana metod
        df = self.veriyi_getir()
        df_islenmis = self.kurallari_uygula(df)
        self.sonuclari_raporla(df_islenmis)
        self.veritabanina_kaydet(df_islenmis)


# Bu dosya doğrudan çalıştırıldığında burası tetiklenir
if __name__ == "__main__":
    # Sınıfımızdan bir nesne (object) üretiyoruz
    sistem = HibritGuvenlikSistemi()
    
    # Sistemin motorunu tek bir komutla ateşliyoruz
    sistem.calistir()