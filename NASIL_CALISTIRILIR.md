# 🚀 Nasıl Çalıştırılır — Sürekli Çalışan Sürüm

Bu doküman, sistemi en güncel hâliyle (sürekli izleme + sürekli eğitim) baştan sona çalıştırmak için adım adım bir kılavuzdur.

---

## 1. Bu sürümde ne değişti?

Mentör geri bildirimine göre iki temel davranış değiştirildi:

| Önceki davranış | Şimdiki davranış |
|---|---|
| Analiz motoru 10 saniyede bir "tur" atıyordu | Analiz motoru **sürekli** çalışıyor: bir tur biter bitmez diğeri başlıyor, sabit bir bekleme yok |
| Model, belirli bir miktar (5000 satır) yeni veri birikince yeniden eğitiliyordu | Model, işlenecek yeni veri olduğu **her turda** sıfırdan yeniden eğitiliyor — birikim beklemiyor |

Yani sistem artık hem log izleme hem de model eğitimi açısından gerçek anlamda sürekli çalışıyor.

> **Not (dürüstlük payı):** "Sürekli" derken kastedilen, sabit bir zamanlayıcı yerine "bir iş biter bitmez diğerine geç" mantığıdır. Model her turda **tüm** veriyle sıfırdan eğitildiği için (Isolation Forest bu şekilde çalışır, parça parça öğrenemez), veri arttıkça bir eğitim turu da uzar — şu an ~53 bin satırda bir tur ortalama 45-55 saniye sürüyor. Bu, "beklenmeyen bir gecikme" değil, algoritmanın doğası; ileride gerçek online/incremental öğrenmeye geçilirse bu süre sabitlenebilir (yol haritasında not edildi).

---

## 2. Ön koşullar

```bash
git clone https://github.com/dila0704/Anomali_Tespit.git
cd Anomali_Tespit

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

---

## 3. İlk kurulum (yalnızca ilk defa)

Henüz eğitilmiş bir model ve dolu tablolar yoksa, sistemi bir kez **tam tarama** ile başlatmanız gerekir:

```bash
python pipeline_calistir.py --tam-tarama
```

Bu komut modeli sıfırdan eğitir, `isolation_forest_model.pkl` / `scaler.pkl` dosyalarını oluşturur ve tüm tabloları doldurur.

---

## 4. Sürekli sistemi başlatma (2 ayrı terminal)

### Terminal 1 — Log üretici (sürekli log akışı)

```bash
python log_uretici.py
```

Bu betik, gerçekçi Samba audit loglarını (normal trafik, brute-force, bot taraması, IP sıçraması vb. senaryoları karışık şekilde) sürekli üretmeye devam eder. `Ctrl+C` ile durdurulur.

### Terminal 2 — Canlı izleme sayfası (sürekli analiz + sade arayüz)

```bash
streamlit run canli_izleme.py
```

Bu sayfa açıldığı anda:
- Arka planda **sürekli** çalışan bir döngü başlar: yeni log var mı diye bakar, varsa hemen işler ve modeli hemen yeniden eğitir, bitince aynı anda tekrar bakmaya başlar.
- Ekranda yalnızca anomaliler listelenir; anomali yoksa "✅ Sistem temiz" mesajı gösterilir.
- Bir anomali bir kez gösterildikten sonra tekrar "yeni" olarak flaşlanmaz — sadece gerçekten yeni tespitler "🆕 YENİ" etiketiyle öne çıkar.

**Elle hiçbir şey tetiklemenize gerek yok.** İki terminal açık kaldığı sürece sistem kendi kendine loglar üretir, analiz eder ve modelini günceller.

---

## 5. (Opsiyonel) Detaylı SOC panosu

Yukarıdaki sade sayfanın yanında, filtreleme/grafik/kullanıcı profili gibi daha ayrıntılı bir inceleme arayüzü de istenirse ayrı bir terminalde açılabilir:

```bash
streamlit run app.py
```

Bu panoda "🚀 Yeni Logları İncele (Delta)" butonuna basarak da elle bir analiz turu tetiklenebilir, ama artık buna ihtiyaç yok — arka plandaki sürekli döngü zaten aynı işi otomatik yapıyor.

---

## 6. Sistemin kendi kaydını nereden görebilirsiniz?

Her şey aynı SQLite veritabanında (`log_veritabani.db`) tutuluyor:

| Ne görmek istiyorsunuz? | Hangi tablo |
|---|---|
| Ham loglar | `anomali_loglari` |
| Zaman/davranış özellikleri çıkarılmış veri | `ozellikli_loglar` |
| Modelin tahminleri | `model_sonuclari` |
| Nihai hibrit karar (kural + YZ) | `hibrit_tespit_sonuclari` |
| Model ne zaman, kaç satırla, ne kalitede eğitildi | `model_egitim_gecmisi` |
| Pipeline'ın her adımı ne zaman/ne kadar sürede/başarılı mı çalıştı | `pipeline_calismalari` |

Örnek: son 5 eğitimi görmek için

```bash
python -c "import sqlite3, pandas as pd; print(pd.read_sql('SELECT * FROM model_egitim_gecmisi ORDER BY id DESC LIMIT 5', sqlite3.connect('log_veritabani.db')))"
```

---

## 7. Bilinen sınırlamalar (mentörle konuşulacak noktalar)

- **Eğitim süresi veri büyüdükçe uzuyor.** Isolation Forest her turda tüm veri üzerinde sıfırdan eğitildiği için, veri arttıkça bir turun süresi de artıyor (şu an ~50 saniye). Gerçek "online learning" (veri geldikçe modeli parça parça güncellemek) için farklı bir algoritmaya (örn. River kütüphanesindeki HalfSpaceTrees) geçmek gerekir — bu, mevcut yol haritasında bir sonraki adım olarak not edildi.
- **`--tam-tarama` hâlâ elle tetiklenen ayrı bir mod.** Bu, ham log dosyasını baştan okuyup tüm tabloları sıfırlar; günlük kullanımda gerekmez, sadece ilk kurulumda veya veritabanını sıfırlamak istendiğinde kullanılır.
