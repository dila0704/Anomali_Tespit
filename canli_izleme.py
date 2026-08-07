"""
Canlı Anomali İzleme — sürekli çalışan, sade uyarı sayfası.

app.py'deki zengin SOC panosundan ayrı, ikinci ve bağımsız bir arayüzdür:
- Arka planda `pipeline_calistir.py`'ı (delta modunda) sürekli bir döngüde
  çalıştırarak yeni logları otomatik analiz eder (buton tıklamaya gerek yok).
- Ekranda sadece o an var olan anomalileri listeler; anomali yoksa "sistem
  temiz" mesajı gösterir.
- Bir anomali bu sayfada bir kez gösterildikten sonra "görülmüş" sayılır;
  aynı kayıt her yenilemede tekrar alarm olarak flaşlanmaz, sadece gerçekten
  yeni tespit edilenler "🆕 YENİ" olarak öne çıkar.

Çalıştırmadan önce en az bir kez tam tarama yapılmış olmalı:
    python pipeline_calistir.py --tam-tarama

Çalıştırma:
    streamlit run canli_izleme.py
"""

import streamlit as st
import sqlite3
import pandas as pd
import subprocess
import sys
import threading
import time
from datetime import datetime

DB_YOLU = "log_veritabani.db"
YENILEME_SANIYE = 5      # sayfanın kendini yenileme sıklığı
# Analiz motoru artık sabit bir bekleme süresiyle "aralıklarla" değil, sürekli
# çalışıyor: her tur bitince hemen yeni turu başlatıyor. Aşağıdaki değer bir
# "tarama periyodu" değil, boşta (işlenecek yeni log yokken) CPU'yu sıfır
# beklemeyle boşuna meşgul etmemek için bırakılan minik bir güvenlik payı.
ANALIZ_DONGU_MIN_BEKLEME_SN = 1

st.set_page_config(page_title="Canlı Anomali İzleme", page_icon="🚨", layout="centered")


# ============================================================
# VERİTABANI BAĞLANTISI (WAL modu + zaman aşımı)
# ============================================================
def veritabani_baglantisi():
    # timeout: pipeline arka planda yazarken sayfa okuma yapmaya çalışırsa
    # anında "database is locked" hatası vermek yerine birkaç saniye bekler.
    baglanti = sqlite3.connect(DB_YOLU, timeout=15)
    # WAL modu bir kez ayarlansa da dosyada kalıcıdır; her bağlantıda tekrar
    # istemek ucuz ve zararsızdır, script'in tek başına da güvenle çalışmasını sağlar.
    baglanti.execute("PRAGMA journal_mode=WAL;")
    return baglanti


# ============================================================
# ARKA PLANDA SÜREKLİ ÇALIŞAN ANALİZ MOTORU
# ============================================================
def arka_plan_analiz_dongusu():
    while True:
        try:
            subprocess.run([sys.executable, "pipeline_calistir.py"], check=False)
        except Exception as hata:
            print(f"[Canlı İzleme] Analiz döngüsünde hata: {hata}")
        # Yeni veri varken bu döngü zaten bir sonraki turu hemen başlatıyor
        # (aradaki süre, o turun işlenme/eğitim süresi kadar). Yeni log yoksa
        # log_parser.py anında kısa devre yapıp döner; bu durumda döngünün
        # CPU'yu boşuna meşgul eden bir spin-loop'a dönüşmemesi için minik
        # bir bekleme bırakılıyor — bu bir "tarama aralığı" değildir.
        time.sleep(ANALIZ_DONGU_MIN_BEKLEME_SN)


@st.cache_resource(show_spinner=False)
def analiz_motorunu_baslat():
    # st.cache_resource sayesinde bu thread, sayfa her yenilendiğinde değil,
    # sunucu sürecinde yalnızca bir kez başlatılır.
    thread = threading.Thread(target=arka_plan_analiz_dongusu, daemon=True)
    thread.start()
    return thread


analiz_motorunu_baslat()


# ============================================================
# SON ANOMALİLERİ VERİTABANINDAN ÇEK
# ============================================================
def son_anomalileri_getir(limit=50):
    try:
        baglanti = veritabani_baglantisi()
        df = pd.read_sql(
            """
            SELECT rowid AS id, Zaman, Kullanici, IP_Adresi, Durum, Kural_Ihlali, Kural_Skoru, Anomali_Durumu
            FROM hibrit_tespit_sonuclari
            WHERE Kural_Skoru > 0
            ORDER BY rowid DESC
            LIMIT ?
            """,
            baglanti,
            params=(limit,),
        )
        baglanti.close()
        return df
    except Exception:
        return pd.DataFrame()


df = son_anomalileri_getir()
mevcut_idler = set(df["id"]) if not df.empty else set()

# İlk açılışta o an tabloda duran kayıtları "geçmiş" say; alarmı sadece
# bu ilk anlık görüntüden SONRA eklenen kayıtlar için patlat.
if "gorulen_idler" not in st.session_state:
    st.session_state["gorulen_idler"] = set(mevcut_idler)

yeni_idler = mevcut_idler - st.session_state["gorulen_idler"]

# ============================================================
# SADE ARAYÜZ
# ============================================================
st.markdown("## 🚨 Canlı Anomali İzleme")
st.caption(
    f"Son kontrol: {datetime.now().strftime('%H:%M:%S')} · "
    f"Analiz motoru arka planda sürekli çalışıyor (yeni log geldiği an işleniyor)"
)


def anomali_karti(satir, yeni_mi):
    kesin_mi = satir["Anomali_Durumu"] == 1
    ikon = "🚨" if kesin_mi else "⚠️"
    etiket = "🆕 **YENİ**  " if yeni_mi else ""
    with st.container(border=True):
        st.markdown(f"{etiket}{ikon} **{satir['Kural_Ihlali']}**  ·  Risk Skoru: {int(satir['Kural_Skoru'])}")
        st.caption(f"👤 {satir['Kullanici']}   🌐 {satir['IP_Adresi']}   🕒 {satir['Zaman']}")


if df.empty:
    st.success("✅ Sistem temiz. Şu anda tespit edilmiş bir anomali yok.")
else:
    yeni_df = df[df["id"].isin(yeni_idler)]
    gecmis_df = df[~df["id"].isin(yeni_idler)]

    if not yeni_df.empty:
        kesin_tehdit_sayisi = len(yeni_df[yeni_df["Anomali_Durumu"] == 1])
        if kesin_tehdit_sayisi > 0:
            st.error(f"🚨 {kesin_tehdit_sayisi} adet YZ onaylı YENİ KESİN TEHDİT tespit edildi!")
        else:
            st.warning(f"⚠️ {len(yeni_df)} adet YENİ şüpheli aktivite tespit edildi.")
        for _, satir in yeni_df.iterrows():
            anomali_karti(satir, yeni_mi=True)
    else:
        st.success("✅ Yeni bir anomali yok. Sistem izleniyor.")

    if not gecmis_df.empty:
        with st.expander(f"🕘 Daha önce görülen anomaliler ({len(gecmis_df)})"):
            for _, satir in gecmis_df.iterrows():
                anomali_karti(satir, yeni_mi=False)

# Bu turda gösterilen her şey artık "görülmüş" sayılır.
st.session_state["gorulen_idler"] |= mevcut_idler

time.sleep(YENILEME_SANIYE)
st.rerun()
