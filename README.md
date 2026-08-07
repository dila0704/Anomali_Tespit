# 🛡️ Anomali Tespit Merkezi

Samba kimlik doğrulama (audit) loglarını **kural tabanlı** ve **yapay zeka destekli (FAISS vektör veritabanı ile k-NN / LOF)** yöntemleri birleştirerek analiz eden hibrit bir anomali/tehdit tespit sistemi. Uçtan uca veri işleme hattı SQLite üzerinde çalışır, **artımlı (delta) okuma mimarisi** sayesinde sadece yeni loglar işlenir ve sonuçlar hem SOC (Güvenlik Operasyon Merkezi) temalı interaktif bir **Streamlit** panelinde hem de arka planda sürekli çalışan, sade bir **canlı anomali izleme** sayfasında görselleştirilir.

---

## 📌 Genel Bakış

Sistem, brute-force girişimleri, mesai dışı şüpheli girişleri ve bot/script davranışlarını hem sabit kurallarla hem de denetimsiz öğrenme (unsupervised learning) modelleriyle tespit eder. İki yaklaşımın ortak "evet" dediği kayıtlar **"Kesin Tehdit"** olarak işaretlenir, bu da yalnızca kural ya da yalnızca modele dayanan sistemlere göre yanlış pozitifleri azaltır.

Boru hattı (pipeline), her çalıştırmada tüm veriyi baştan işlemek yerine **delta modunda** sadece son çalıştırmadan bu yana eklenen logları işleyip mevcut tablolara ekler (append); bu da hem `pipeline_calistir.py`'ı hem de Streamlit panelindeki "Yeni Logları İncele" butonunu saniyeler içinde tamamlanabilir hale getirir. Panel de kendi tarafında yalnızca son 50.000 kaydı çekerek arayüzü hızlı tutar.

Gerçek dünyada etiketli anomali verisi bulunmadığından proje, modelin başarısını ölçmek için **sentetik (etiketli) saldırı verisi enjekte edip** Precision / Recall / F1 metrikleriyle değerlendirme yapan ayrı bir mekanizma da içerir.

## ✨ Özellikler

- **Hibrit tespit motoru:** Kural tabanlı skorlama + FAISS (vektör veritabanı) tabanlı k-NN anomali skoru birleşimi
- **Delta (artımlı) okuma mimarisi:** `bookmark.txt` ile log dosyasındaki son okunan byte konumu takip edilir; her adım (`log_parser.py`, `ozellik_cikarimi.py`, `model_egitimi.py`, `kural_tabanli_tespit.py`) sadece yeni kayıtları işleyip veritabanına **ekler (append)**, tüm veriyi yeniden işlemez
- **Kısa devre (short-circuit) mantığı:** İşlenecek yeni log yoksa betikler `exit code 99` ile çıkar, `pipeline_calistir.py` bu durumu yakalayıp kalan adımları atlayarak süreci güvenle sonlandırır
- **Gerçek artımlı (incremental) anomali tespiti — vektör veritabanı:** `model_egitimi.py`, `ozellikli_loglar`'daki her log satırını 8 boyutlu bir özellik vektörüne çevirip bir **FAISS** indeksinde tutar. Scaler ve indeks yalnızca ilk kurulumda (bootstrap) bir kez oluşturulur; sonraki her turda **hiçbir yeniden eğitim yapılmaz** — o turun yeni logları, mevcut indeksteki en yakın komşularına olan uzaklığa göre anında skorlanır ve indekse eklenir. Bu sayede hem "tüm veriyle sıfırdan çalışma" ortadan kalkar hem de her yeni log, üretildiği an (milisaniyeler içinde) işlenmiş olur — eskiden ~50 saniye süren bir "eğitim turu" artık yoktur
- **Model durumu izlenebilirliği:** Her tur, `model_egitim_gecmisi` tablosuna (zaman, indeksteki toplam vektör sayısı, o turda eklenen vektör sayısı, kullanılan eşik değeri) kaydedilir
- **Sürekli çalışan canlı izleme sayfası:** `canli_izleme.py`, arka planda `pipeline_calistir.py`'ı düzenli aralıklarla kendiliğinden çalıştırır ve ekranda sadece anomalileri gösterir; bir anomali bir kez görüldükten sonra tekrar "yeni" olarak flaşlanmaz, sadece gerçekten yeni tespitler öne çıkar
- **Pipeline gözlemlenebilirliği:** Her pipeline adımının süresi ve durumu (`Başarılı` / `Yeni Veri Yok` / `Hata`) `pipeline_calismalari` tablosuna otomatik loglanır
- **Eşzamanlı erişim güvenliği:** Tüm veritabanı bağlantılarında SQLite WAL modu + zaman aşımı (timeout) kullanılır; arka plan izleme döngüsü ile manuel bir tarama aynı anda çalışsa bile "database is locked" hatası alınmaz
- **Davranışsal özellik mühendisliği:** Kullanıcı/IP bazlı 10 dakikalık kayan pencere (rolling window) istatistikleri ve hızlı IP değişimi (impossible travel) tespiti
- **Model karşılaştırması:** Üretimdeki FAISS/k-NN sonuçları ile Local Outlier Factor (LOF) sonuçlarının kıyaslanması
- **Sentetik veri ile objektif değerlendirme:** Bilinen saldırı örnekleri enjekte edilip, birden fazla komşu sayısı (`k`) × birden fazla eşik persentili üzerinden ızgara taramasıyla Precision/Recall/F1 ve karmaşıklık matrisi hesaplanır — üretimde gerçekten çalışan yöntemin ta kendisi test edilir
- **Canlı log simülatörü:** Her döngüde ağırlıklı rastgele bir senaryo üreten sürekli çalışan bir simülatör — normal başarılı trafik (çoğunluk), brute-force, hesap kilitlenmesi, bot/script taraması, IP sıçraması (impossible travel), olası hesap ele geçirme ve hareketsiz hesap aktivasyonu
- **Kullanıcı bazlı terminal sorgulama:** `kullanici_sorgula.py` ile belirli bir kullanıcının davranış profili (rutin saat aralığı, en sık IP'ler, başarı oranları, saatlik yoğunluk grafiği) ve log/anomali kayıtları terminalde görüntülenebilir
- **SOC temalı, sekmeli Streamlit paneli:**
  - **Genel Tehdit Pano** sekmesi: filtrelenebilir tablo, ihlal türü/zaman dağılım grafikleri
  - **Derinlemesine Profil (UBA)** sekmesi: seçilen kullanıcı/IP için dijital ayak izi (toplam işlem, farklı IP sayısı, rutin çalışma saati, riskli hareket sayısı), saatlik yoğunluk grafiği ve normal/anomali durum dağılımı
  - **Nokta Atışı İzleme:** belirli bir kullanıcı veya kaynak IP seçip odaklı inceleme yapma
  - Tek tıkla "🚀 Yeni Logları İncele (Delta)" butonu ile arka planda pipeline'ı delta modunda tetikleme
- **Performans odaklı tasarım:** Panel son 50.000 kaydı çeker, tablo satır limiti ayarlanabilir slider ile kontrol edilir
- **Tek komutla uçtan uca çalıştırma:** `pipeline_calistir.py` ile tüm adımların otomatik sırayla koşturulması (varsayılan: delta modu, `--tam-tarama` ile tam yeniden işleme)

## 🧭 Mimari / Veri Akışı

```mermaid
flowchart TD
    A["log_uretici.py\n(Samba audit log simülatörü)"] -->|"JSON log satırları"| B["samba_audit_user_anomaly_dataset_large.log"]
    BM["bookmark.txt\n(son okunan byte offset)"] -.->|"--delta modunda okunur ve güncellenir"| C
    B --> C["log_parser.py\nJSON -> DataFrame\n(--delta: sadece yeni satırlar)"]
    C -->|"append/replace: anomali_loglari"| D["ozellik_cikarimi.py\nZaman + davranışsal özellikler\n(--delta: sadece yeni satırlar)"]
    D -->|"append/replace: ozellikli_loglar"| E["model_egitimi.py\nFAISS vektör indeksi (k-NN)\n(bootstrap: 1 kez kurulum · sonra: sadece yeni vektör ekle)"]
    E -->|"append/replace: model_sonuclari"| F["kural_tabanli_tespit.py\nHibritGuvenlikSistemi\n(--delta: sadece yeni satırlar)"]
    F -->|"append/replace: hibrit_tespit_sonuclari"| G["app.py\nSOC Streamlit Paneli"]
    F -->|"append/replace: hibrit_tespit_sonuclari"| G2["canli_izleme.py\nSürekli döngü + sade uyarı sayfası"]
    E -->|"append: model_egitim_gecmisi"| E

    D --> H["lof_model_denemesi.py\nLOF (karşılaştırma)"]
    E --> H
    H -->|"tablo: lof_model_sonuclari"| H

    D --> I["sentetik_anomali_uretici.py\nEtiketli sahte saldırı ekle"]
    I -->|"tablo: ozellikli_loglar_sentetikli"| J["metrikleri_hesapla.py\nPrecision / Recall / F1"]
```

**Özet akış:**

1. **Üretim / Alım:** `log_uretici.py` gerçekçi Samba audit logları üretir (veya gerçek bir Samba audit log dosyası kullanılabilir).
2. **Ayrıştırma:** `log_parser.py`, delta modunda `bookmark.txt`'teki byte konumundan itibaren dosyayı okuyup sadece yeni JSON satırlarını ayrıştırır ve SQLite'a (`anomali_loglari`) **ekler**; tam taramada dosyayı baştan okuyup tabloyu yeniden yazar.
3. **Özellik Mühendisliği:** `ozellik_cikarimi.py` zaman bazlı (saat, hafta sonu, mesai dışı) ve davranışsal (kayan pencere) özellikler üretir → `ozellikli_loglar`; delta modunda sadece yeni satırları işleyip ekler.
4. **Gerçek Artımlı Anomali Tespiti (Vektör Veritabanı):** `model_egitimi.py`, ilk çalıştırmada (bootstrap) `ozellikli_loglar`'daki tüm satırları özellik vektörüne çevirip bir kez bir `StandardScaler` fit eder ve bir **FAISS** k-NN indeksi kurar; bu indeks ve scaler diske kaydedilir. Sonraki her turda bunlar **yeniden eğitilmez** — sadece o turun yeni satırları (delta) mevcut indekse karşı skorlanır (en yakın komşularına olan ortalama uzaklık) ve ardından indekse eklenir → `model_sonuclari`. "Tüm veriyle sıfırdan çalışma" hiç olmaz; her log kendi başına, üretildiği an işlenir.
5. **Kural Motoru & Hibrit Karar:** `kural_tabanli_tespit.py`, sabit kurallarla model çıktısını birleştirip nihai risk skorunu hesaplar; delta modunda sadece yeni satırları işleyip `hibrit_tespit_sonuclari` tablosuna ekler.
6. **Görselleştirme:** `app.py`, bu son tabloyu okuyup SOC temalı, sekmeli bir Streamlit panelinde (Genel Pano + Kullanıcı/IP bazlı UBA profili) sunar. `canli_izleme.py` ise bağımsız, ikinci bir arayüz olarak aynı tabloyu izler; arka planda pipeline'ı sürekli döngüde kendiliğinden tetikler ve ekranda sadece (yeni/görülmüş ayrımı yapılmış) anomalileri gösterir.
7. **Kısa devre:** Herhangi bir adımda işlenecek yeni veri yoksa ilgili betik `exit code 99` ile çıkar; `pipeline_calistir.py` bunu algılayıp kalan adımları atlayarak süreci hatasız sonlandırır. Her adımın süresi ve sonucu ayrıca `pipeline_calismalari` tablosuna loglanır.
8. **Ayrıca (paralel/değerlendirme amaçlı):**
   - `lof_model_denemesi.py`: Üretimdeki FAISS/k-NN sonuçlarını LOF ile kıyaslar.
   - `sentetik_anomali_uretici.py` + `metrikleri_hesapla.py`: Bilinen etiketli saldırılar enjekte edilerek üretimdeki FAISS/k-NN yönteminin gerçek başarı oranı, birden fazla `k` (komşu sayısı) × eşik persentili denemesiyle Precision/Recall/F1 üzerinden ölçülür.

## 📂 Proje Yapısı

| Dosya | Açıklama |
|---|---|
| `app.py` | SOC temalı, sekmeli (Genel Pano / UBA Profili) Streamlit analiz paneli |
| `canli_izleme.py` | Arka planda pipeline'ı sürekli döngüde kendiliğinden çalıştıran, sadece (yeni/görülmüş ayrımı yapılmış) anomalileri gösteren sade, bağımsız izleme sayfası |
| `kullanici_sorgula.py` | Belirli bir kullanıcının davranış profilini ve log/anomali kayıtlarını terminalde (renkli tablo) gösteren CLI aracı |
| `log_uretici.py` | Normal trafik, brute-force, hesap kilitlenmesi, bot taraması, IP sıçraması, hesap ele geçirme ve hareketsiz hesap senaryolarını ağırlıklı rastgele üreten sürekli log üretici |
| `log_parser.py` | Ham JSON Samba audit loglarını ayrıştırıp SQLite'a yazar; `--delta` ile `bookmark.txt` üzerinden sadece yeni satırları okur |
| `bookmark.txt` | Delta modunda log dosyasında en son okunan byte konumunu tutan takip dosyası (tam taramada sıfırlanır) |
| `ozellik_cikarimi.py` | Zaman ve davranışsal (rolling window) özellik mühendisliği; `--delta` ile sadece yeni satırları işler |
| `sentetik_anomali_uretici.py` | Değerlendirme amaçlı etiketli (bilinen) sahte saldırı kayıtları üretir |
| `model_egitimi.py` | İlk turda (bootstrap) `StandardScaler`'ı bir kez fit edip bir FAISS k-NN indeksi kurar; sonraki her turda hiçbir şeyi yeniden eğitmeden sadece o turun yeni satırlarını skorlayıp indekse ekler (gerçek artımlı öğrenme) |
| `lof_model_denemesi.py` | Karşılaştırma amaçlı Local Outlier Factor (LOF) modeli |
| `metrikleri_hesapla.py` | Sentetik veriyle, üretimdeki FAISS/k-NN yöntemini birden fazla `k` × eşik persentili denemesiyle ölçüp Precision / Recall / F1 / karmaşıklık matrisi hesaplar |
| `kural_tabanli_tespit.py` | Kural motoru + kural/YZ hibrit karar mantığı (`HibritGuvenlikSistemi` sınıfı); `--delta` ile sadece yeni satırları işleyip ekler |
| `pipeline_calistir.py` | Tüm adımları sırasıyla çalıştıran orkestrasyon betiği; varsayılan delta modu, `--tam-tarama` ile tam yeniden işleme, `exit 99` kısa devre yönetimi, her adımın süresini/durumunu `pipeline_calismalari` tablosuna loglar |
| `faiss_index.bin` | Bootstrap'ta kurulup her turda yeni vektörlerle güncellenen kalıcı FAISS k-NN indeksi |
| `scaler.pkl` | Bootstrap'ta bir kez fit edilen ve hiç yeniden eğitilmeyen `StandardScaler` nesnesi |

## ⚙️ Kurulum

```bash
git clone https://github.com/dila0704/Anomali_Tespit.git
cd Anomali_Tespit

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

## ▶️ Kullanım

### 1. Log verisi üretin (veya kendi Samba audit log dosyanızı kullanın)

```bash
python log_uretici.py
# Hızlı test için:
python log_uretici.py --test
```

Bu betik, `samba_audit_user_anomaly_dataset_large.log` dosyasına sürekli olarak JSON formatlı log satırları ekler (`Ctrl+C` ile durdurulabilir).

### 2. Analiz hattını (pipeline) çalıştırın

İlk çalıştırmada henüz eğitilmiş bir model, `bookmark.txt` ve dolu tablolar olmadığı için **tam tarama** ile başlamanız gerekir:

```bash
python pipeline_calistir.py --tam-tarama
```

Bu komut sırasıyla `log_parser.py → ozellik_cikarimi.py → model_egitimi.py → kural_tabanli_tespit.py` betiklerini **tam tarama modunda** çalıştırır, `scaler.pkl`'ı bir kez fit edip `faiss_index.bin` FAISS indeksini sıfırdan kurar ve sonuçları `log_veritabani.db` içine yazar. Bu bootstrap adımı, sistemin ömrü boyunca yalnızca **bir kez** gerçekleşir — sonraki her çalıştırma bu indeksi yeniden kurmaz, sadece üzerine ekler.

> Sıralama önemlidir: `kural_tabanli_tespit.py`, `model_egitimi.py`'ın ürettiği `model_sonuclari` tablosunu okur; bu yüzden model adımı kurallardan **önce** çalışmalıdır. Aksi halde kurallar bir önceki turdan kalma bayat model verisiyle çalışır.

Sonraki çalıştırmalarda argümansız komut varsayılan olarak **delta (artımlı) modda** çalışır; sadece `log_uretici.py`'ın ürettiği yeni loglar işlenir ve mevcut tablolara eklenir:

```bash
python pipeline_calistir.py
```

İşlenecek yeni log yoksa betikler `exit code 99` ile çıkar ve pipeline, hata vermeden "Kısa Devre" mesajıyla kalan adımları atlar.

### 3. Paneli açın

```bash
streamlit run app.py
```

Panel içindeki **"🚀 Yeni Logları İncele (Delta)"** butonu, `pipeline_calistir.py` dosyasını arka planda delta modunda tekrar çalıştırıp panoyu otomatik günceller. Panelde:

- **📈 Genel Tehdit Pano** sekmesinde metrikler, ihlal/zaman dağılım grafikleri ve son log tablosu,
- **🕵️‍♂️ Derinlemesine Profil (UBA)** sekmesinde ise "🎯 Nokta Atışı İzleme" alanından seçilen bir kullanıcı veya IP'nin dijital ayak izi, saatlik davranış grafiği ve normal/anomali dağılımı görüntülenir.

### 3b. (Alternatif) Sürekli çalışan canlı izleme sayfasını açın

```bash
streamlit run canli_izleme.py
```

Bu sayfa `app.py`'deki zengin panodan bağımsızdır ve elle tetiklemeye ihtiyaç duymaz: açılır açılmaz arka planda bir thread üzerinden `pipeline_calistir.py`'ı **sürekli** çalıştırır — bir tur biter bitmez bir sonraki tur hemen başlar, sabit bir "X saniyede bir tara" beklemesi yoktur. İşlenecek yeni log yoksa bir tur zaten anında kısa devre ile biter (bkz. Kısa Devre); yeni log varsa FAISS indeksine anında (milisaniyeler içinde) skorlanıp eklenir (bkz. Gerçek Artımlı Anomali Tespiti) — artık ~50 saniyelik bir "eğitim turu" beklenmez. Sayfanın kendisi de düzenli aralıklarla (varsayılan 5 saniye) yenilenip en güncel sonuçları gösterir. Ekranda sadece o an var olan anomaliler listelenir; anomali yoksa "sistem temiz" mesajı gösterilir. Bir anomali bu sayfada bir kez gösterildikten sonra "görülmüş" sayılır — aynı kayıt her yenilemede tekrar alarm olarak flaşlanmaz, sadece gerçekten yeni tespitler "🆕 YENİ" etiketiyle öne çıkar. İlk çalıştırmadan önce en az bir kez `python pipeline_calistir.py --tam-tarama` ile eğitilmiş bir model bulunmalıdır.

### 4. (Opsiyonel) Bir kullanıcıyı terminalde sorgulayın

```bash
python kullanici_sorgula.py <kullanici_adi>
python kullanici_sorgula.py <kullanici_adi> --sadece-anomali --limit 20
```

Terminalde kullanıcının özet bilgisi, davranış profili (rutin saat aralığı, en sık kullanılan IP'ler, başarısız giriş/mesai dışı/hafta sonu oranları), saatlik aktivite grafiği ve ayrıntılı log tablosu renkli olarak listelenir.

### 5. (Opsiyonel) Model başarısını objektif ölçün

```bash
python sentetik_anomali_uretici.py
python metrikleri_hesapla.py
```

Bu adım, veriye bilinen 100 sahte saldırı kaydı ekleyip, üretimdeki FAISS/k-NN yönteminin bunları ne oranda yakaladığını birden fazla `k` (komşu sayısı) × eşik persentili kombinasyonuyla Precision/Recall/F1 üzerinden raporlar; en iyi kombinasyonu önerir (ayarları otomatik değiştirmez).

### 6. (Opsiyonel) FAISS/k-NN yöntemini LOF ile kıyaslayın

```bash
python lof_model_denemesi.py
```

## 🔁 Delta (Artımlı) Okuma Mimarisi

Sistem, her seferinde tüm log geçmişini yeniden işlemek yerine yalnızca yeni verileri işleyerek hem `pipeline_calistir.py`'ı hem de panel yenilemesini hızlı tutar:

- **Byte-offset takibi:** `log_parser.py`, `--delta` bayrağıyla çalıştığında `bookmark.txt` içindeki son okunan byte konumundan (`file.seek`) devam eder ve okuma bitince yeni konumu tekrar `bookmark.txt`'e yazar.
- **Satır sayısı farkı ile delta tespiti:** `ozellik_cikarimi.py` ve `kural_tabanli_tespit.py`, önceki adımdaki tablo ile mevcut tablo arasındaki satır sayısı farkına (`toplam_satir - mevcut_satir`) bakarak yalnızca yeni satırları işleyip hedef tabloya **append** eder. `kural_tabanli_tespit.py` bu farkı `model_sonuclari` tablosuna göre hesapladığı için, `model_egitimi.py` pipeline'da ondan **önce** çalışmak zorundadır — aksi halde bayat veri okunur ve pipeline yanlışlıkla "yeni veri yok" sanıp erken durur.
- **Gerçek artımlı öğrenme (vektör veritabanı):** `model_egitimi.py`, `model_sonuclari` tablosundaki satır sayısını `ozellikli_loglar`'la karşılaştırarak ilk çalıştırma mı (bootstrap) yoksa artımlı bir tur mu olduğuna karar verir. Bootstrap'ta `StandardScaler` bir kez fit edilir ve bir FAISS indeksi sıfırdan kurulur; bu **yalnızca sistemin ömründe bir kez** olur. Sonraki her turda scaler ve indeks **diskten yüklenir, hiçbiri yeniden eğitilmez** — sadece o turun yeni satırları mevcut indekse karşı skorlanıp (en yakın `k` komşuya ortalama uzaklık) ardından indekse eklenir. Bu sayede bir turun süresi artık toplam veri hacmine değil, **o turdaki yeni satır sayısına** bağlıdır — pratikte milisaniyeler mertebesinde (eski Isolation Forest yaklaşımında ~50 saniyeydi).
- **Kısa devre (short-circuit):** İşlenecek yeni veri olmayan bir adım `exit code 99` ile çıkar; `pipeline_calistir.py` bu kodu özel olarak yakalayıp geri kalan adımları atlar ve süreci hatasız olarak sonlandırır. `--tam-tarama` çalıştırıldığında ise tüm tablolar baştan yazılır (`replace`) ve `bookmark.txt` sıfırlanır.
- **Eşzamanlı erişim güvenliği:** Tüm `sqlite3.connect` çağrılarında `PRAGMA journal_mode=WAL` ve `timeout=15` kullanılır; böylece `canli_izleme.py`'ın arka plan döngüsü ile `app.py`'daki manuel tetikleme veya elle çalıştırılan bir `pipeline_calistir.py` aynı anda veritabanına erişse bile anında "database is locked" hatası alınmaz, kısa bir süre beklenip devam edilir.

## 🧠 Kural Motoru (Hibrit Karar Mantığı)

`kural_tabanli_tespit.py` içindeki `HibritGuvenlikSistemi` sınıfı aşağıdaki kuralları uygular:

| Kural | Koşul | Risk Skoru |
|---|---|---|
| Brute-Force Şüphesi | Son 10 dk içinde 5'ten fazla başarısız giriş | +50 |
| Mesai Dışı Başarısız Giriş | Mesai dışı veya hafta sonu + başarısız giriş **ve** son 10 dk içinde en az 2 başarısız deneme | +30 |
| Bot/Script Şüphesi | Aynı IP'den 1 sn'den kısa aralıklarla 50'den fazla istek | +40 |
| Uzun Aradan Sonra Ani Aktivite | Kullanıcının bir önceki işleminden bu yana 4 saatten uzun sessizlik | +20 |
| IP Sıçraması Şüphesi | Kullanıcı, önceki işleminden 5 dk içinde farklı bir IP'den görülüyor (impossible travel) | +35 |
| Olası Hesap Ele Geçirme | Son 10 dk içinde 3'ten fazla başarısız denemenin ardından başarılı giriş | +60 |
| Hibrit Onay (YZ + Kural) | Kural skoru > 0 **ve** FAISS/k-NN modeli de anomali demiş | +100 |

> Not: "Mesai Dışı Başarısız Giriş" kuralına tekrar şartı (≥2 başarısız deneme) eklenmiştir; tek seferlik bir şifre yanlışı (insan hatası) artık anomali sayılmaz. Aksi halde mesai dışı zaman diliminin genişliği (günün ~%54'ü) yüzünden kural aşırı geniş tetikleniyor ve diğer daha spesifik örüntüleri gürültüye boğuyordu.

## 🗄️ Veritabanı Şeması (SQLite: `log_veritabani.db`)

| Tablo | Üreten Betik | İçerik |
|---|---|---|
| `anomali_loglari` | `log_parser.py` | Ayrıştırılmış ham log kayıtları (delta modunda append edilir) |
| `ozellikli_loglar` | `ozellik_cikarimi.py` | Zaman + davranışsal özellikler eklenmiş veri (delta modunda append edilir) |
| `model_sonuclari` | `model_egitimi.py` | FAISS/k-NN anomali skorları ve kararları (delta modunda append edilir) |
| `hibrit_tespit_sonuclari` | `kural_tabanli_tespit.py` | Nihai hibrit karar (panelde kullanılır, delta modunda append edilir) |
| `lof_model_sonuclari` | `lof_model_denemesi.py` | LOF karşılaştırma sonuçları |
| `ozellikli_loglar_sentetikli` | `sentetik_anomali_uretici.py` | Etiketli sentetik saldırı verisiyle zenginleştirilmiş veri |
| `model_egitim_gecmisi` | `model_egitimi.py` | Her turun zamanı, indeksteki toplam vektör sayısı, o turda eklenen vektör sayısı ve kullanılan anomali eşiği |
| `pipeline_calismalari` | `pipeline_calistir.py` | Her pipeline adımının çalışma zamanı, süresi (sn) ve durumu (`Başarılı` / `Yeni Veri Yok` / `Hata`) — pipeline'ın kendi sağlığını izlemek için |

> `bookmark.txt`, bir SQLite tablosu değildir; delta modunda `log_parser.py`'ın log dosyasında en son okuduğu byte konumunu tutan ayrı bir takip dosyasıdır.

## 🛠️ Kullanılan Teknolojiler

- **Python 3**
- **Streamlit** — interaktif, sekmeli SOC paneli
- **Plotly Express** — grafikler
- **pandas / numpy** — veri işleme
- **FAISS** (Facebook AI Similarity Search) — vektör veritabanı / k-NN benzerlik araması, artımlı anomali skorlaması
- **scikit-learn** — Local Outlier Factor (karşılaştırma), standardizasyon (`StandardScaler`) ve değerlendirme metrikleri
- **SQLite** — hafif veri deposu
- **joblib** — model/scaler serileştirme
- **rich** — `kullanici_sorgula.py` CLI aracındaki renkli terminal tabloları/panelleri

## 📈 Yol Haritası Fikirleri

- ~~Model yeniden eğitimini zamanlanmış (scheduled) hale getirmek~~ ✅ artık zamanlamaya bile gerek yok — FAISS ile gerçek artımlı öğrenmeye geçildi
- ~~`requirements.txt` eklemek~~ ✅ eklendi
- ~~Veri büyüdükçe her turun `fit` süresinin uzaması~~ ✅ FAISS'e geçişle çözüldü: bir turun süresi artık toplam veriye değil, o turdaki yeni satır sayısına bağlı
- Otomatik testler eklemek
- Dosya tabanlı simülasyon yerine gerçek zamanlı log akışı (syslog / Filebeat entegrasyonu) ile delta mimarisini gerçek kaynaklara bağlamak
- E-posta/Slack üzerinden "Kesin Tehdit" bildirimleri (`canli_izleme.py`'daki YENİ tespit mantığı üzerine kurulabilir)
- Veri milyonlarca satıra ulaşırsa FAISS'in tam tarama (`IndexFlatL2`) yerine yaklaşık (`IndexIVFFlat` / `IndexHNSWFlat`) indeks türlerine geçirilmesi değerlendirilebilir

## 📄 Lisans

Bu proje için henüz bir lisans dosyası tanımlanmamıştır.
