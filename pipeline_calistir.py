import subprocess
import sys
import argparse

def run_script(script_name, args=None):
    if args is None:
        args = []
        
    komut = [sys.executable, script_name] + args
    print(f"⏳ [{' '.join([script_name] + args)}] çalıştırılıyor...")
    try:
        subprocess.run(komut, check=True, text=True)
        print(f"✅ [{script_name}] başarıyla tamamlandı.\n")
    except subprocess.CalledProcessError as e:
        # Eğer log parser 99 koduyla çıkarsa, yeni veri yoktur. Süreci başarıyla durdur.
        if e.returncode == 99:
            print(f"ℹ️ [{script_name}] Yeni log bulunamadı. Diğer analiz adımları atlanıyor (Kısa Devre).")
            sys.exit(0) 
        else:
            print(f"❌ [{script_name}] çalıştırılırken bir hata oluştu!")
            print(f"Hata Kodu: {e.returncode}")
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
    adimlar = [
        ("log_parser.py", parser_args),
        ("ozellik_cikarimi.py", parser_args),
        ("kural_tabanli_tespit.py", parser_args),
        ("model_egitimi.py", parser_args) 
    ]
    
    for script, script_args in adimlar:
        run_script(script, script_args)
        
    print("-" * 50)
    print("🎉 Tüm analiz boru hattı başarıyla tamamlandı!")

if __name__ == "__main__":
    main()