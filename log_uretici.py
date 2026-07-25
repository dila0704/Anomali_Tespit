import json
import time
import random
import argparse
from datetime import datetime, timedelta

LOG_DOSYASI = "samba_audit_user_anomaly_dataset_large.log"
KULLANICILAR = ["dila.alpay", "admin", "test_user", "developer", "guest"]
IP_HAVUZU = ["192.168.1.10", "192.168.1.15", "192.168.1.20", "10.0.0.5", "192.168.1.55"]

# KRİTİK DEĞİŞİKLİK: Saat kuralını aşmak için simülasyonu Sabah 09:00'dan başlatıyoruz
simule_zaman = datetime.now().replace(hour=9, minute=0, second=0)

def log_uret(test_modu=False):
    global simule_zaman
    
    # Her üretimde saati 30 ila 90 dakika ileri sarıyoruz ki gündüz-gece döngüsü oluşsun
    simule_zaman += timedelta(minutes=random.randint(30, 90))
    yeni_loglar = []
    
    # --- TEHDİT 1: BRUTE FORCE (Aynı IP'den 1 saniye arayla 8 hatalı şifre) ---
    kullanici_bf = random.choice(KULLANICILAR)
    ip_bf = random.choice(IP_HAVUZU)
    for _ in range(8):
        simule_zaman += timedelta(seconds=1)
        yeni_loglar.append({
            "timestamp": simule_zaman.isoformat() + "Z",
            "Authentication.clientAccount": kullanici_bf,
            "Authentication.remoteAddress": f"ipv4:{ip_bf}:445",
            "Authentication.status": "NT_STATUS_WRONG_PASSWORD",
            "Authentication.eventId": 4625
        })

    # --- TEHDİT 2: KİLİTLENME VE SÜRE DOLMASI ---
    simule_zaman += timedelta(minutes=3)
    yeni_loglar.append({
        "timestamp": simule_zaman.isoformat() + "Z",
        "Authentication.clientAccount": random.choice(KULLANICILAR),
        "Authentication.remoteAddress": f"ipv4:{random.choice(IP_HAVUZU)}:445",
        "Authentication.status": "NT_STATUS_ACCOUNT_LOCKED_OUT",
        "Authentication.eventId": 4625
    })
    
    simule_zaman += timedelta(seconds=15)
    yeni_loglar.append({
        "timestamp": simule_zaman.isoformat() + "Z",
        "Authentication.clientAccount": random.choice(KULLANICILAR),
        "Authentication.remoteAddress": f"ipv4:{random.choice(IP_HAVUZU)}:445",
        "Authentication.status": "NT_STATUS_PASSWORD_EXPIRED",
        "Authentication.eventId": 4625
    })

    # --- TEHDİT 3: BOT / SCRİPT ŞÜPHESİ (Aynı IP'nin Saliseler İçinde Tüm Kullanıcıları Taraması) ---
    simule_zaman += timedelta(minutes=10)
    ip_bot = random.choice(IP_HAVUZU)
    for kul in KULLANICILAR: 
        simule_zaman += timedelta(milliseconds=200) # Salise farkıyla saldırı
        yeni_loglar.append({
            "timestamp": simule_zaman.isoformat() + "Z",
            "Authentication.clientAccount": kul,
            "Authentication.remoteAddress": f"ipv4:{ip_bot}:445",
            "Authentication.status": "NT_STATUS_LOGON_FAILURE", # Farklı bir hata durumu
            "Authentication.eventId": 4625
        })

    with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
        for log in yeni_loglar:
            f.write(json.dumps(log) + "\n")
            
    print(f"[*] Simüle Edilen Saat: {simule_zaman.strftime('%H:%M')} -> Çeşitli Tehditler (Brute-Force, Bot, Kilitlenme) Üretildi!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    print("\n[!] Karmaşık Log Simülasyonu başlatıldı...")
    try:
        while True:
            log_uret(test_modu=args.test)
            bekleme = random.randint(5, 8) if args.test else 60
            print(f"[-] {bekleme} saniye bekleniyor...\n")
            time.sleep(bekleme)
    except KeyboardInterrupt:
        print("\n[!] Durduruldu.")