import subprocess
import sys

def run_script(script_name):
    print(f"⏳ [{script_name}] çalıştırılıyor...")
    try:
        # Scripti çalıştır ve varsa standart çıktılarını terminalde göster
        subprocess.run([sys.executable, script_name], check=True, text=True)
        print(f"✅ [{script_name}] başarıyla tamamlandı.\n")
    except subprocess.CalledProcessError as e:
        print(f"❌ [{script_name}] çalıştırılırken bir hata oluştu!")
        print(f"Hata Kodu: {e.returncode}")
        sys.exit(1) # Kritik bir hata olursa pipeline'ı güvenli şekilde durdur

def main():
    print("🚀 Anomali Tespiti Analiz Pipeline'ı Başlatılıyor...\n")
    print("-" * 50)
    
    # Orijinal dosyalarının sırayla çalıştırılacağı zincir
    adimlar = [
        "log_parser.py",
        "ozellik_cikarimi.py",
        "kural_tabanli_tespit.py",
        "model_egitimi.py" # Model bu dosyadaysa veya değerlendirmeyi yapan başka betiğin varsa buraya eklenebilir.
    ]
    
    for script in adimlar:
        run_script(script)
        
    print("-" * 50)
    print("🎉 Tüm analiz boru hattı başarıyla tamamlandı! Sonuçlar SQLite veritabanına yazıldı.")

if __name__ == "__main__":
    main()