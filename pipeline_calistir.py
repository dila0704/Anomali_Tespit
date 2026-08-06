import subprocess
import sys
import sqlite3
import time
import argparse
from datetime import datetime

DB_YOLU = "log_veritabani.db"


def denetim_tablosunu_hazirla(baglanti):
    baglanti.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_calismalari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            calisma_zamani TEXT,
            adim TEXT,
            sure_sn REAL,
            durum TEXT,
            detay TEXT
        )
    """)


def calismayi_logla(adim, sure_sn, durum, detay=""):
    # Denetim kaydı ana analiz sonucunu asla engellememeli: loglama başarısız
    # olursa (örn. veritabanı o an kilitliyse) sessizce yutulur, pipeline durmaz.
    try:
        baglanti = sqlite3.connect(DB_YOLU, timeout=15)
        baglanti.execute("PRAGMA journal_mode=WAL;")
        denetim_tablosunu_hazirla(baglanti)
        baglanti.execute(
            "INSERT INTO pipeline_calismalari (calisma_zamani, adim, sure_sn, durum, detay) VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), adim, sure_sn, durum, detay),
        )
        baglanti.commit()
        baglanti.close()
    except Exception as hata:
        print(f"⚠️ [Denetim Kaydı] '{adim}' adımı loglanamadı: {hata}")


def run_script(script_name, args=None):
    if args is None:
        args = []

    komut = [sys.executable, script_name] + args
    print(f"⏳ [{' '.join([script_name] + args)}] çalıştırılıyor...")
    baslangic = time.perf_counter()
    try:
        subprocess.run(komut, check=True, text=True)
        sure_sn = time.perf_counter() - baslangic
        print(f"✅ [{script_name}] başarıyla tamamlandı. ({sure_sn:.2f} sn)\n")
        calismayi_logla(script_name, sure_sn, "Başarılı")
    except subprocess.CalledProcessError as e:
        sure_sn = time.perf_counter() - baslangic
        # Eğer log parser 99 koduyla çıkarsa, yeni veri yoktur. Süreci başarıyla durdur.
        if e.returncode == 99:
            print(f"ℹ️ [{script_name}] Yeni log bulunamadı. Diğer analiz adımları atlanıyor (Kısa Devre).")
            calismayi_logla(script_name, sure_sn, "Yeni Veri Yok")
            sys.exit(0)
        else:
            print(f"❌ [{script_name}] çalıştırılırken bir hata oluştu!")
            print(f"Hata Kodu: {e.returncode}")
            calismayi_logla(script_name, sure_sn, "Hata", detay=f"return_code={e.returncode}")
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Anomali Tespit Pipeline")
    parser.add_argument('--tam-tarama', action='store_true', help="Tüm logları baştan okur")
    komut_satiri_arg = parser.parse_args()

    print("🚀 Anomali Tespiti Analiz Pipeline'ı Başlatılıyor...\n")
    print("-" * 50)
    
    parser_args = [] if komut_satiri_arg.tam_tarama else ["--delta"]

    # KRİTİK DÜZELTME: parser_args (yani --delta komutu) artık sadece parser'a değil,
    # özellik çıkarımına, kurallara ve en önemlisi modele de iletiliyor!
    # SIRALAMA ÖNEMLİ: kural_tabanli_tespit.py, model_egitimi.py'ın ürettiği
    # "model_sonuclari" tablosunu okur. Model adımı önce çalışmazsa kurallar
    # bir önceki turdan kalma bayat veriyi görür ve "yeni veri yok" sanıp
    # pipeline'ı erken durdurur.
    adimlar = [
        ("log_parser.py", parser_args),
        ("ozellik_cikarimi.py", parser_args),
        ("model_egitimi.py", parser_args),
        ("kural_tabanli_tespit.py", parser_args)
    ]
    
    pipeline_baslangic = time.perf_counter()
    for script, script_args in adimlar:
        run_script(script, script_args)

    toplam_sure = time.perf_counter() - pipeline_baslangic
    calismayi_logla("pipeline_calistir.py (TOPLAM)", toplam_sure, "Başarılı")

    print("-" * 50)
    print(f"🎉 Tüm analiz boru hattı başarıyla tamamlandı! (Toplam süre: {toplam_sure:.2f} sn)")

if __name__ == "__main__":
    main()