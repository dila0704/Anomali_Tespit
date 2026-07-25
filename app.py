import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import sys
import subprocess
import time
from datetime import datetime

# ============================================================
# 1. SAYFA AYARLARI
# ============================================================
st.set_page_config(
    page_title="Anomali Tespit Merkezi",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# 2. KURUMSAL CSS TEMASI
# ============================================================
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .main-header {
        background: linear-gradient(90deg, #1a1c24 0%, #23262f 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        border-left: 5px solid #ff4b4b;
        margin-bottom: 1.5rem;
    }
    .main-header h1 { color: #fafafa; margin: 0; font-size: 1.8rem; font-weight: 700; }
    .main-header p { color: #9ca3af; margin: 0.3rem 0 0 0; font-size: 0.9rem; }
    div[data-testid="stMetric"] {
        background-color: #1a1c24;
        border: 1px solid #2d3039;
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }
    div[data-testid="stMetric"] label { color: #9ca3af !important; font-weight: 500; }
    section[data-testid="stSidebar"] { background-color: #14161c; border-right: 1px solid #2d3039; }
    h2, h3 { color: #fafafa !important; border-bottom: 1px solid #2d3039; padding-bottom: 0.4rem; }
    .footer-note { color: #6b7280; font-size: 0.8rem; text-align: center; margin-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 3. BAŞLIK BLOĞU
# ============================================================
st.markdown(f"""
<div class="main-header">
    <h1>🛡️ Anomali Tespit Merkezi</h1>
    <p>Hibrit Kural Tabanlı + YZ Destekli Log Analiz Paneli · Son güncelleme: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# 4. VERİ ÇEKME VE SIRALAMA (YENİ)
# ============================================================
@st.cache_data(ttl=300, show_spinner="Veriler yükleniyor...")
def veriyi_getir():
    baglanti = sqlite3.connect("log_veritabani.db")
    df = pd.read_sql("SELECT * FROM hibrit_tespit_sonuclari", baglanti)
    baglanti.close()
    
    if 'Zaman' in df.columns:
        df['Zaman'] = pd.to_datetime(df['Zaman'], errors='coerce')
        # KRİTİK DÜZELTME: En yeni logları en üstte görmek için tarihe göre tersten sıralıyoruz
        df = df.sort_values(by='Zaman', ascending=False).reset_index(drop=True)
        
    return df

df = veriyi_getir()

if df.empty:
    st.warning("Veritabanında görüntülenecek kayıt bulunamadı.")
    st.stop()

# ============================================================
# 5. SIDEBAR - KONTROL PANELİ
# ============================================================
with st.sidebar:
    st.markdown("## ⚙️ Kontrol Paneli")
    
    if st.button("🔄 Logları Yenile ve Analiz Et", use_container_width=True):
        with st.spinner("Yeni loglar analiz ediliyor..."):
            try:
                subprocess.run([sys.executable, "pipeline_calistir.py"], check=True)
                st.cache_data.clear()
                st.success("Analiz tamamlandı!")
                time.sleep(1)
                st.rerun()
            except subprocess.CalledProcessError:
                st.error("Analiz motoru hatası. Terminali kontrol edin.")
    
    st.markdown("---")
    
    st.markdown("### 🕒 Zaman Aralığı")
    zaman_dilimi = st.radio(
        "Görüntüleme Periyodu:",
        options=["Günlük (Son 24 Saat)", "Haftalık (Son 7 Gün)", "Aylık (Son 30 Gün)"]
    )
    
    st.markdown("---")
    st.markdown("### 🔍 İhlal Filtresi")
    kurallar = df[df['Kural_Ihlali'] != 'Yok']['Kural_Ihlali'].unique()
    secilen_kural = st.multiselect("Kural İhlali Türü:", options=kurallar, default=list(kurallar))

    st.markdown("---")
    st.markdown("### 🖥️ Performans Ayarları")
    max_satir = st.slider(
        "Tabloda gösterilecek maksimum satır:",
        min_value=100, max_value=min(20000, max(len(df), 100)), value=min(2000, len(df)), step=100
    )

# --- 30 DAKİKALIK ZAMAN FİLTRESİ ---
son_tarih = df['Zaman'].max()

if zaman_dilimi == "Günlük (Son 24 Saat)":
    baslangic = son_tarih - pd.Timedelta(days=1)
    df = df[df['Zaman'] >= baslangic]
    # YENİ: Tam 30 dakikalık dilimlere yuvarlama (20:00, 20:30, 21:00 vb.)
    df['Zaman_Ekseni'] = df['Zaman'].dt.floor('30min').dt.strftime('%H:%M')
    zaman_etiketi = "Saat (30 Dk Periyot)"
elif zaman_dilimi == "Haftalık (Son 7 Gün)":
    baslangic = son_tarih - pd.Timedelta(days=7)
    df = df[df['Zaman'] >= baslangic]
    df['Zaman_Ekseni'] = df['Zaman'].dt.strftime('%Y-%m-%d')
    zaman_etiketi = "Gün"
else:
    baslangic = son_tarih - pd.Timedelta(days=30)
    df = df[df['Zaman'] >= baslangic]
    df['Zaman_Ekseni'] = df['Zaman'].dt.strftime('%Y - %W. Hafta')
    zaman_etiketi = "Hafta"

if secilen_kural:
    filtrelenmis_df = df[df['Kural_Ihlali'].isin(secilen_kural)]
else:
    filtrelenmis_df = df[df['Kural_Skoru'] > 0]

# ============================================================
# 6. ÜST METRİK KARTLARI
# ============================================================
col1, col2, col3, col4 = st.columns(4)
with col1: st.metric(label=f"📊 Toplam Log ({zaman_dilimi.split(' ')[0]})", value=f"{len(df):,}")
with col2: st.metric(label="🎯 Seçili Filtredeki Şüpheliler", value=f"{len(filtrelenmis_df):,}")
with col3:
    kesin_tehdit = len(filtrelenmis_df[filtrelenmis_df['Anomali_Durumu'] == 1])
    st.metric(label="🚨 Kesin Tehdit", value=f"{kesin_tehdit:,}", delta="Alarm" if kesin_tehdit > 0 else "Temiz", delta_color="inverse" if kesin_tehdit > 0 else "off")
with col4:
    st.metric(label="⚠️ En Yüksek Skor", value=int(filtrelenmis_df['Kural_Skoru'].max() if not filtrelenmis_df.empty else 0))

st.markdown("---")

# ============================================================
# 7. GRAFİKLER
# ============================================================
st.markdown("### 📈 Tehdit Analizi ve Dağılım Grafikleri")
grafik_col1, grafik_col2 = st.columns(2)
renk_paleti = ["#ff4b4b", "#ff8a3d", "#ffc93d", "#4bafff", "#7c4bff", "#4bff8a"]

with grafik_col1:
    st.markdown("**İhlal Türlerine Göre Dağılım**")
    ihlal_sayilari = filtrelenmis_df['Kural_Ihlali'].value_counts().reset_index()
    ihlal_sayilari.columns = ['Ihlal_Turu', 'Adet']
    if not ihlal_sayilari.empty:
        fig1 = px.bar(ihlal_sayilari, x='Adet', y='Ihlal_Turu', orientation='h', color='Ihlal_Turu', color_discrete_sequence=renk_paleti, text='Adet')
        fig1.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#fafafa', showlegend=False, yaxis_title="", xaxis_title="Kayıt Sayısı", margin=dict(l=10, r=10, t=20, b=10), height=380)
        
        # Sütun kalınlık kontrolü
        satir_sayisi = len(ihlal_sayilari)
        if satir_sayisi == 1: fig1.update_traces(textposition='outside', width=0.2)
        elif satir_sayisi == 2: fig1.update_traces(textposition='outside', width=0.4)
        else: fig1.update_traces(textposition='outside')
            
        st.plotly_chart(fig1, use_container_width=True)

with grafik_col2:
    st.markdown(f"**Tehdit Aktivitesi ({zaman_etiketi})**")
    if 'Zaman_Ekseni' in filtrelenmis_df.columns and not filtrelenmis_df.empty:
        zaman_dagilimi = filtrelenmis_df['Zaman_Ekseni'].value_counts().sort_index().reset_index()
        zaman_dagilimi.columns = ['Zaman_Ekseni', 'Adet']
        fig2 = px.area(zaman_dagilimi, x='Zaman_Ekseni', y='Adet', markers=True, color_discrete_sequence=["#ff4b4b"])
        fig2.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#fafafa', xaxis_title=zaman_etiketi, yaxis_title="Kayıt Sayısı", margin=dict(l=10, r=10, t=20, b=10), height=380)
        
        # Grafiğin X eksenini string sırasına göre değil, kategorik sıraya göre dizmeye zorlama
        fig2.update_xaxes(type='category')
        
        st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ============================================================
# 8. DETAYLI VERİ TABLOSU
# ============================================================
# ============================================================
# 8. DETAYLI VERİ TABLOSU (KULLANICI DOSTU GÖRÜNÜM)
# ============================================================
st.markdown(f"### 🗂️ Detaylı Anomali Özellikleri - {zaman_dilimi.split(' ')[0]} Görünüm")
st.caption("Not: En yeni üretilen kayıtlar her zaman en üstte gösterilir.")

# Kullanıcıya göstereceğimiz tablo için verinin kopyasını alıyoruz
tablo_df = filtrelenmis_df.head(max_satir).copy()

# 1. Karmaşık durum kodlarını emojili Türkçe metinlere çeviriyoruz
durum_sozlugu = {
    'NT_STATUS_WRONG_PASSWORD': '❌ Hatalı Şifre',
    'NT_STATUS_OK': '✅ Başarılı Giriş',
    'NT_STATUS_ACCOUNT_LOCKED_OUT': '🔒 Hesap Kilitlendi',
    'NT_STATUS_PASSWORD_EXPIRED': '⏳ Şifre Süresi Doldu',
    'NT_STATUS_LOGON_FAILURE': '🚫 Giriş Başarısız'
}
if 'Durum' in tablo_df.columns:
    tablo_df['Durum'] = tablo_df['Durum'].replace(durum_sozlugu)

# 2. Yapay Zeka (Anomali) durumunu 0-1 yerine şık bir etikete çeviriyoruz
if 'Anomali_Durumu' in tablo_df.columns:
    tablo_df['Anomali_Durumu'] = tablo_df['Anomali_Durumu'].apply(
        lambda x: '🚨 Kesin Tehdit' if x == 1 else '➖ İncelemede'
    )

# 3. Tarih formatını saniyelerle birlikte temiz bir görünüme sokuyoruz
if 'Zaman' in tablo_df.columns:
    tablo_df['Zaman'] = tablo_df['Zaman'].dt.strftime('%d.%m.%Y %H:%M:%S')

# 4. Sadece analistin işine yarayacak kritik sütunları seçip, isimlerini Türkçeleştiriyoruz
gosterilecek_sutunlar = []
yeni_isimler = {}

sutun_haritasi = {
    'Zaman': '📅 Tarih / Saat',
    'Kullanici': '👤 Kullanıcı',
    'IP_Adresi': '🌐 Kaynak IP',
    'Durum': 'Durum',
    'Olay_ID': '🏷️ Olay ID',
    'Kural_Ihlali': '⚠️ Tetiklenen Kural',
    'Kural_Skoru': '📈 Risk Skoru',
    'Anomali_Durumu': '🤖 YZ Kararı'
}

for ham_isim, yeni_isim in sutun_haritasi.items():
    if ham_isim in tablo_df.columns:
        gosterilecek_sutunlar.append(ham_isim)
        yeni_isimler[ham_isim] = yeni_isim

# Tabloyu son haline getir (Filtrele ve Yeniden İsimlendir)
if gosterilecek_sutunlar:
    tablo_df = tablo_df[gosterilecek_sutunlar].rename(columns=yeni_isimler)

# Tabloyu Streamlit üzerinde daha şık (indeks numaraları gizlenmiş şekilde) çizdir
st.dataframe(
    tablo_df,
    use_container_width=True,
    height=450,
    hide_index=True # Soldaki 41126 gibi kafa karıştıran satır numaralarını gizler
)

st.markdown("<div class='footer-note'>Anomali Tespit Merkezi · Hibrit Tespit Motoru</div>", unsafe_allow_html=True)