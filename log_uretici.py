import json
import time
import random
import argparse
from datetime import datetime, timedelta

LOG_DOSYASI = "samba_audit_user_anomaly_dataset_large.log"
KULLANICILAR = ["dila.alpay", "admin", "test_user", "developer", "guest"]
IP_HAVUZU = ["192.168.1.10", "192.168.1.15", "192.168.1.20", "10.0.0.5", "192.168.1.55"]
# Impossible-travel / hesap ele geçirme senaryoları için "olağan dışı" IP havuzu
# (RFC 5737 dokümantasyon aralığı — gerçek dış IP değil, sadece "iç ağ dışı" temsili)
IP_HAVUZU_YABANCI = ["203.0.113.44", "198.51.100.23", "45.33.21.156"]

# KRİTİK DEĞİŞİKLİK: Saat kuralını aşmak için simülasyonu Sabah 09:00'dan başlatıyoruz
simule_zaman = datetime.now().replace(hour=9, minute=0, second=0)


def olay_uret(kullanici, ip, durum):
    """Tek bir authentication olayı sözlüğü üretir. simule_zaman çağrıdan önce ilerletilmelidir."""
    event_id = 4624 if durum == "NT_STATUS_OK" else 4625
    return {
        "timestamp": simule_zaman.isoformat() + "Z",
        "Authentication.clientAccount": kullanici,
        "Authentication.remoteAddress": f"ipv4:{ip}:445",
        "Authentication.status": durum,
        "Authentication.eventId": event_id
    }


def normal_trafik():
    """Sıradan başarılı giriş trafiği — veri setinin çoğunluğu bu olmalı ki
    kurallar/model gerçek bir 'normal' temeline karşı anomali tespit edebilsin."""
    global simule_zaman
    olaylar = []
    for _ in range(random.randint(3, 6)):
        simule_zaman += timedelta(minutes=random.randint(2, 20))
        kullanici = random.choice(KULLANICILAR)
        ip = random.choice(IP_HAVUZU)
        olaylar.append(olay_uret(kullanici, ip, "NT_STATUS_OK"))
    return olaylar


def brute_force():
    """Aynı IP'den 1 saniye arayla art arda hatalı şifre denemeleri."""
    global simule_zaman
    olaylar = []
    kullanici = random.choice(KULLANICILAR)
    ip = random.choice(IP_HAVUZU)
    for _ in range(8):
        simule_zaman += timedelta(seconds=1)
        olaylar.append(olay_uret(kullanici, ip, "NT_STATUS_WRONG_PASSWORD"))
    return olaylar


def hesap_kilitleme():
    """Hesap kilitlenmesi ve ardından şifre süresi dolması."""
    global simule_zaman
    olaylar = []
    simule_zaman += timedelta(minutes=3)
    olaylar.append(olay_uret(random.choice(KULLANICILAR), random.choice(IP_HAVUZU), "NT_STATUS_ACCOUNT_LOCKED_OUT"))
    simule_zaman += timedelta(seconds=15)
    olaylar.append(olay_uret(random.choice(KULLANICILAR), random.choice(IP_HAVUZU), "NT_STATUS_PASSWORD_EXPIRED"))
    return olaylar


def bot_taramasi():
    """Aynı IP'nin saliseler içinde tüm kullanıcıları taraması (script/bot şüphesi)."""
    global simule_zaman
    olaylar = []
    ip_bot = random.choice(IP_HAVUZU)
    for kullanici in KULLANICILAR:
        simule_zaman += timedelta(milliseconds=200)
        olaylar.append(olay_uret(kullanici, ip_bot, "NT_STATUS_LOGON_FAILURE"))
    return olaylar


def impossible_travel():
    """Aynı kullanıcının çok kısa sürede birbirinden çok farklı IP'lerden
    (bazıları olağan dışı/yabancı) başarılı giriş yapması — 'imkansız seyahat'."""
    global simule_zaman
    olaylar = []
    kullanici = random.choice(KULLANICILAR)
    ip_seti = random.sample(IP_HAVUZU_YABANCI, k=2) + [random.choice(IP_HAVUZU)]
    random.shuffle(ip_seti)
    for ip in ip_seti:
        simule_zaman += timedelta(seconds=random.randint(20, 90))
        olaylar.append(olay_uret(kullanici, ip, "NT_STATUS_OK"))
    return olaylar


def hesap_ele_gecirme():
    """Birkaç hatalı şifre denemesinin hemen ardından BAŞARILI giriş —
    olası hesap ele geçirme (brute-force başarıya ulaştı) örüntüsü."""
    global simule_zaman
    olaylar = []
    kullanici = random.choice(KULLANICILAR)
    ip = random.choice(IP_HAVUZU_YABANCI)
    for _ in range(random.randint(4, 6)):
        simule_zaman += timedelta(seconds=random.randint(1, 3))
        olaylar.append(olay_uret(kullanici, ip, "NT_STATUS_WRONG_PASSWORD"))
    simule_zaman += timedelta(seconds=2)
    olaylar.append(olay_uret(kullanici, ip, "NT_STATUS_OK"))
    return olaylar


def hareketsiz_hesap_aktivasyonu():
    """Uzun süre sessiz kalan bir hesabın (guest) aniden aktifleşmesi."""
    global simule_zaman
    olaylar = []
    kullanici = "guest"
    simule_zaman += timedelta(hours=random.randint(5, 12))
    ip = random.choice(IP_HAVUZU)
    for _ in range(random.randint(2, 4)):
        simule_zaman += timedelta(seconds=random.randint(5, 20))
        durum = random.choice(["NT_STATUS_OK", "NT_STATUS_WRONG_PASSWORD"])
        olaylar.append(olay_uret(kullanici, ip, durum))
    return olaylar


# Her döngüde hangi senaryonun üretileceği ağırlıklı olarak seçilir.
# Ağırlık ne kadar yüksekse o senaryo o kadar sık üretilir; normal trafik
# çoğunlukta olacak şekilde ayarlandı ki anomaliler gerçekten "anomali" kalsın.
SENARYOLAR = [
    (normal_trafik, 45),
    (brute_force, 15),
    (hesap_kilitleme, 10),
    (bot_taramasi, 10),
    (impossible_travel, 10),
    (hesap_ele_gecirme, 5),
    (hareketsiz_hesap_aktivasyonu, 5),
]


def log_uret(test_modu=False):
    fonksiyonlar = [f for f, _ in SENARYOLAR]
    agirliklar = [w for _, w in SENARYOLAR]
    secilen_fonksiyon = random.choices(fonksiyonlar, weights=agirliklar, k=1)[0]

    yeni_loglar = secilen_fonksiyon()

    with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
        for log in yeni_loglar:
            f.write(json.dumps(log) + "\n")

    print(f"[*] Simüle Edilen Saat: {simule_zaman.strftime('%H:%M')} -> [{secilen_fonksiyon.__name__}] {len(yeni_loglar)} log üretildi!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    print("\n[!] Karmaşık Log Simülasyonu başlatıldı...")
    try:
        while True:
            log_uret(test_modu=args.test)
            bekleme = random.randint(5, 8) if args.test else 20
            print(f"[-] {bekleme} saniye bekleniyor...\n")
            time.sleep(bekleme)
    except KeyboardInterrupt:
        print("\n[!] Durduruldu.")
