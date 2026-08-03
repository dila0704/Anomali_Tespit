import pandas as pd
import sqlite3
import sys

class HibritGuvenlikSistemi:
    def __init__(self, db_yolu="log_veritabani.db"):
        self.db_yolu = db_yolu
        # Delta modunda olup olmadığımızı kontrol ediyoruz
        self.delta_modu = "--delta" in sys.argv
        self.hedef_tablo = "hibrit_tespit_sonuclari"

    def mevcut_satir_sayisini_bul(self):
        if not self.delta_modu:
            return 0
        try:
            baglanti = sqlite3.connect(self.db_yolu)
            imlec = baglanti.execute(f"SELECT COUNT(*) FROM {self.hedef_tablo}")
            sayi = imlec.fetchone()[0]
            baglanti.close()
            return sayi
        except sqlite3.OperationalError:
            return 0 # Tablo henüz oluşturulmadıysa 0 döndür

    def veriyi_getir(self, tablo_adi="model_sonuclari"):
        baglanti = sqlite3.connect(self.db_yolu)
        df = pd.read_sql(f"SELECT * FROM {tablo_adi}", baglanti)
        baglanti.close()
        return df

    def kurallari_uygula(self, df):
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
        kurala_takilanlar = df[df['Kural_Skoru'] > 0]
        kesin_tehdit_sarti = (df['Kural_Skoru'] > 0) & (df['Anomali_Durumu'] == 1)

        print("--- 🛡️ HİBRİT GÜVENLİK SİSTEMİ RAPORU 🛡️ ---")
        print(f"Toplam İncelenen Log: {len(df)}")
        print(f"Sadece Yapay Zekanın Bulduğu: {df['Anomali_Durumu'].sum()}")
        print(f"Kurallara Takılan: {len(kurala_takilanlar)}")
        print(f"Kesin Tehdit (YZ + Kural): {len(df[kesin_tehdit_sarti])}")

    def veritabanina_kaydet(self, df):
        mevcut_satir = self.mevcut_satir_sayisini_bul()
        toplam_satir = len(df)
        yeni_satir_sayisi = toplam_satir - mevcut_satir

        baglanti = sqlite3.connect(self.db_yolu)

        if self.delta_modu and mevcut_satir > 0 and yeni_satir_sayisi > 0:
            # Sadece yeni satırları kesip ekle
            yeni_df = df.tail(yeni_satir_sayisi)
            yeni_df.to_sql(self.hedef_tablo, baglanti, if_exists="append", index=False)
            print(f"\n[BİLGİ] {yeni_satir_sayisi} yeni analiz '{self.hedef_tablo}' tablosuna EKLENDİ.")
        else:
            # Tam taramaysa baştan yaz
            df.to_sql(self.hedef_tablo, baglanti, if_exists="replace", index=False)
            print(f"\n[BİLGİ] Tüm analizler ({toplam_satir} adet) '{self.hedef_tablo}' tablosuna BAŞTAN YAZILDI.")
            
        baglanti.close()

    def calistir(self):
        # 1. Delta kontrolü
        mevcut_satir = self.mevcut_satir_sayisini_bul()
        df = self.veriyi_getir()
        
        yeni_satir = len(df) - mevcut_satir
        
        if self.delta_modu and yeni_satir <= 0:
            print("İşlenecek yeni model sonucu bulunamadı (Kurallar atlanıyor).")
            sys.exit(99)
            
        # 2. Kuralları işlet ve kaydet
        df_islenmis = self.kurallari_uygula(df)
        
        # Sadece son işlenen yepyeni verilerin ufak raporunu gösterelim
        if self.delta_modu and mevcut_satir > 0:
             self.sonuclari_raporla(df_islenmis.tail(yeni_satir))
        else:
             self.sonuclari_raporla(df_islenmis)
             
        self.veritabanina_kaydet(df_islenmis)


if __name__ == "__main__":
    sistem = HibritGuvenlikSistemi()
    sistem.calistir()