import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
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
    /* Genel arka plan ve font */
    .main {
        background-color: #0e1117;
    }
    /* Başlık alanı */
    .main-header {
        background: linear-gradient(90deg, #1a1c24 0%, #23262f 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        border-left: 5px solid #ff4b4b;
        margin-bottom: 1.5rem;
    }
    .main-header h1 {
        color: #fafafa;
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .main-header p {
        color: #9ca3af;
        margin: 0.3rem 0 0 0;
        font-size: 0.9rem;
    }
    /* Metrik kartları */
    div[data-testid="stMetric"] {
        background-color: #1a1c24;
        border: 1px solid #2d3039;
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }
    div[data-testid="stMetric"] label {
        color: #9ca3af !important;
        font-weight: 500;
    }
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #14161c;
        border-right: 1px solid #2d3039;
    }
    /* Alt bölüm başlıkları */
    h2, h3 {
        color: #fafafa !important;
        border-bottom: 1px solid #2d3039;
        padding-bottom: 0.4rem;
    }
    /* Bilgi kutuları */
    .footer-note {
        color: #6b7280;
        font-size: 0.8rem;
        text-align: center;
        margin-top: 2rem;
    }
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
# 4. VERİ ÇEKME
# ============================================================
@st.cache_data(ttl=300, show_spinner="Veriler yükleniyor...")
def veriyi_getir():
    baglanti = sqlite3.connect("log_veritabani.db")
    df = pd.read_sql("SELECT * FROM hibrit_tespit_sonuclari", baglanti)
    baglanti.close()
    return df

df = veriyi_getir()

if df.empty:
    st.warning("Veritabanında görüntülenecek kayıt bulunamadı.")
    st.stop()

# ============================================================
# 5. SIDEBAR - GELİŞMİŞ FİLTRELER
# ============================================================
with st.sidebar:
    st.markdown("## ⚙️ Kontrol Paneli")
    st.markdown("---")

    st.markdown("### 🔍 Filtreler")
    kurallar = df[df['Kural_Ihlali'] != 'Yok']['Kural_Ihlali'].unique()
    secilen_kural = st.multiselect(
        "Kural İhlali Türü:",
        options=kurallar,
        default=list(kurallar)
    )

    st.markdown("---")
    st.markdown("### 🖥️ Performans Ayarları")
    st.caption("Büyük veri setlerinde VM kaynaklarını korumak için tablo/grafik satır sayısını sınırlayın.")
    max_satir = st.slider(
        "Tabloda gösterilecek maksimum satır:",
        min_value=100,
        max_value=min(20000, max(len(df), 100)),
        value=min(2000, len(df)),
        step=100
    )

    st.markdown("---")
    st.caption(f"Toplam ham kayıt: **{len(df):,}**")

# Veriyi seçime göre filtrele
if secilen_kural:
    filtrelenmis_df = df[df['Kural_Ihlali'].isin(secilen_kural)]
else:
    filtrelenmis_df = df[df['Kural_Skoru'] > 0]

# ============================================================
# 6. ÜST METRİK KARTLARI
# ============================================================
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="📊 Toplam Log Sayısı", value=f"{len(df):,}")

with col2:
    st.metric(label="🎯 Seçili Filtredeki Şüpheliler", value=f"{len(filtrelenmis_df):,}")

with col3:
    kesin_tehdit = len(filtrelenmis_df[filtrelenmis_df['Anomali_Durumu'] == 1])
    st.metric(
        label="🚨 Kesin Tehdit (YZ Onaylı)",
        value=f"{kesin_tehdit:,}",
        delta="Kritik Alarm" if kesin_tehdit > 0 else "Temiz",
        delta_color="inverse" if kesin_tehdit > 0 else "off"
    )

with col4:
    max_skor = filtrelenmis_df['Kural_Skoru'].max() if not filtrelenmis_df.empty else 0
    st.metric(label="⚠️ En Yüksek Tehdit Skoru", value=int(max_skor))

st.markdown("---")

# ============================================================
# 7. GRAFİKLER
# ============================================================
st.markdown("### 📈 Tehdit Analizi ve Dağılım Grafikleri")

grafik_col1, grafik_col2 = st.columns(2)

renk_paleti = ["#ff4b4b", "#ff8a3d", "#ffc93d", "#4bafff", "#7c4bff", "#4bff8a"]

with grafik_col1:
    st.markdown("**İhlal Türlerine Göre Dağılım**")
    ihlal_sayilari = (
        filtrelenmis_df['Kural_Ihlali']
        .value_counts()
        .reset_index()
    )
    ihlal_sayilari.columns = ['Ihlal_Turu', 'Adet']

    if not ihlal_sayilari.empty:
        fig1 = px.bar(
            ihlal_sayilari,
            x='Adet', y='Ihlal_Turu',
            orientation='h',
            color='Ihlal_Turu',
            color_discrete_sequence=renk_paleti,
            text='Adet'
        )
        fig1.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#fafafa',
            showlegend=False,
            yaxis_title="",
            xaxis_title="Kayıt Sayısı",
            margin=dict(l=10, r=10, t=20, b=10),
            height=380
        )
        fig1.update_traces(textposition='outside')
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("Görüntülenecek veri yok.")

with grafik_col2:
    st.markdown("**Saatlik Tehdit Aktivitesi**")
    if 'Saat' in filtrelenmis_df.columns:
        saatlik_dagilim = (
            filtrelenmis_df['Saat']
            .value_counts()
            .sort_index()
            .reset_index()
        )
        saatlik_dagilim.columns = ['Saat', 'Adet']

        fig2 = px.area(
            saatlik_dagilim,
            x='Saat', y='Adet',
            markers=True,
            color_discrete_sequence=["#ff4b4b"]
        )
        fig2.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#fafafa',
            xaxis_title="Saat",
            yaxis_title="Kayıt Sayısı",
            margin=dict(l=10, r=10, t=20, b=10),
            height=380
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Log verilerinde 'Saat' kolonu bulunamadı.")

st.markdown("---")
# ============================================================
# 7.5 RİSKLİ IP PANOSU
# ============================================================
st.markdown("### 🎯 En Riskli Kaynaklar (Top 10 IP)")

# Verisetindeki olası IP kolonu ismini otomatik buluyoruz
ip_kolonu = None
olasi_isimler = ['IP', 'IP_Adresi', 'Client_IP', 'Source_IP', 'Kullanici_IP']
for kolon in olasi_isimler:
    if kolon in filtrelenmis_df.columns:
        ip_kolonu = kolon
        break

if ip_kolonu:
    # En çok ihlal yapan 10 IP'yi bul
    riskli_ipler = filtrelenmis_df[ip_kolonu].value_counts().head(10).reset_index()
    riskli_ipler.columns = ['IP_Adresi', 'İhlal_Sayisi']
    
    # Şık bir Donut (Halka) grafik çiziyoruz
    fig_ip = px.pie(
        riskli_ipler, 
        names='IP_Adresi', 
        values='İhlal_Sayisi', 
        hole=0.4,
        color_discrete_sequence=px.colors.sequential.Reds_r # Kırmızı güvenlik teması
    )
    fig_ip.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#fafafa',
        margin=dict(t=20, b=20, l=20, r=20),
        height=350
    )
    st.plotly_chart(fig_ip, use_container_width=True)
else:
    st.info("Log verilerinde IP adresi kolonu tespit edilemediği için bu pano oluşturulamadı.")

st.markdown("---")
# ============================================================
# 8. DETAYLI VERİ TABLOSU
# ============================================================
st.markdown("### 🗂️ Detaylı Anomali Özellikleri")

gosterilecek_df = filtrelenmis_df.head(max_satir)

if len(filtrelenmis_df) > max_satir:
    st.caption(
        f"⚠️ Performans nedeniyle {len(filtrelenmis_df):,} kayıttan ilk "
        f"{max_satir:,} tanesi gösteriliyor. Daha fazlasını görmek için "
        f"sol menüden 'Maksimum satır' değerini artırabilirsiniz."
    )

st.dataframe(
    gosterilecek_df,
    use_container_width=True,
    height=450
)

# ============================================================
# 9. FOOTER
# ============================================================
st.markdown(
    "<div class='footer-note'>Anomali Tespit Merkezi · Hibrit Tespit Motoru</div>",
    unsafe_allow_html=True
)