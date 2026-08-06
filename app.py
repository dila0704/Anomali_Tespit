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
# 2. KURUMSAL SOC (GÜVENLİK MERKEZİ) CSS TEMASI
# ============================================================
st.markdown("""
<style>
    /* Arka Plan ve Genel Metin */
    .main { background-color: #0b0f19; }
    
    /* Ana Başlık Kartı */
    .main-header {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 2rem;
        border-radius: 16px;
        border: 1px solid #334155;
        border-left: 6px solid #3b82f6;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        margin-bottom: 2rem;
    }
    .main-header h1 { color: #f8fafc; margin: 0; font-size: 2.2rem; font-weight: 800; letter-spacing: -0.5px;}
    .main-header p { color: #94a3b8; margin: 0.5rem 0 0 0; font-size: 1rem; }
    
    /* Metrik Kartları (Glassmorphism ve Hover) */
    div[data-testid="stMetric"] {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.2rem;
        box-shadow: inset 0 2px 4px 0 rgba(255, 255, 255, 0.02);
        transition: all 0.3s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        border-color: #3b82f6;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2);
    }
    div[data-testid="stMetric"] label { color: #94a3b8 !important; font-weight: 600; font-size: 0.95rem; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #f8fafc; font-weight: 700; }
    
    /* Sidebar Tasarımı */
    section[data-testid="stSidebar"] { 
        background-color: #0f172a; 
        border-right: 1px solid #1e293b; 
    }
    
    /* Sekmeler (Tabs) */
    .stTabs [data-baseweb="tab-list"] { gap: 2rem; border-bottom: 2px solid #1e293b; }
    .stTabs [data-baseweb="tab"] { 
        height: 55px; 
        white-space: pre-wrap; 
        font-size: 1.15rem; 
        font-weight: 600;
        color: #94a3b8;
    }
    .stTabs [aria-selected="true"] { color: #3b82f6 !important; }
    
    /* Arama/Filtre Kutusu */
    .search-box {
        background-color: #1e293b;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #334155;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    h2, h3, h4 { color: #f1f5f9 !important; }
    hr { border-color: #334155 !important; }
    .footer-note { color: #64748b; font-size: 0.85rem; text-align: center; margin-top: 3rem; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 3. BAŞLIK BLOĞU
# ============================================================
st.markdown(f"""
<div class="main-header">
    <h1>🛡️ Merkezi Siber Tehdit Analiz Paneli</h1>
    <p>Hibrit Karar Motoru (Kural + YZ) · Gerçek Zamanlı İzleme · Son güncelleme: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# 4. VERİ ÇEKME VE SIRALAMA (PERFORMANS OPTİMİZASYONU)
# ============================================================
@st.cache_data(ttl=300, show_spinner="Veriler getiriliyor...")
def veriyi_getir():
    # timeout + WAL: pipeline arka planda (canli_izleme.py döngüsü ya da
    # elle tetiklenen taramalar) yazarken panel okuma yaparsa anında
    # "database is locked" hatası almak yerine kısa süre beklenir.
    baglanti = sqlite3.connect("log_veritabani.db", timeout=15)
    baglanti.execute("PRAGMA journal_mode=WAL;")
    df = pd.read_sql("SELECT * FROM hibrit_tespit_sonuclari ORDER BY Zaman DESC LIMIT 50000", baglanti)
    baglanti.close()
    
    if 'Zaman' in df.columns:
        df['Zaman'] = pd.to_datetime(df['Zaman'], errors='coerce')
        
        # 🐛 HATA ÇÖZÜMÜ: Eğer verilerde Timezone (Zaman Dilimi) varsa, onu temizle
        if df['Zaman'].dt.tz is not None:
            df['Zaman'] = df['Zaman'].dt.tz_localize(None)
            
        df = df.sort_values(by='Zaman', ascending=False).reset_index(drop=True)
        
    return df
      

df_orijinal = veriyi_getir()

if df_orijinal.empty:
    st.warning("Veritabanında görüntülenecek kayıt bulunamadı. Lütfen analiz motorunu çalıştırın.")
    st.stop()

# ============================================================
# 5. SIDEBAR - SİSTEM KONTROLLERİ
# ============================================================
with st.sidebar:
    st.markdown("## ⚙️ Operasyon Merkezi")
    
    if st.button("🚀 Yeni Logları İncele (Delta)", use_container_width=True):
        # ÖNEMLİ: st.rerun() bu blok içinde çağrıldığı için script bu turda
        # aşağıdaki "Zaman Aralığı" radio widget'ına hiç ulaşmadan kesiliyor.
        # Bu yüzden kullanıcının seçtiği periyodu (session_state) burada
        # elle koruyup rerun'dan sonra geri yazıyoruz; aksi halde seçim
        # sessizce "Günlük" varsayılanına dönüyordu.
        secili_periyot = st.session_state.get("zaman_dilimi_hafizasi")
        with st.spinner("Model tahmin modunda çalışıyor..."):
            try:
                subprocess.run([sys.executable, "pipeline_calistir.py"], check=True)
                st.cache_data.clear()
                if secili_periyot:
                    st.session_state["zaman_dilimi_hafizasi"] = secili_periyot
                st.success("Tarama tamamlandı!")
                time.sleep(1)
                st.rerun()
            except subprocess.CalledProcessError:
                st.error("Analiz motoru hatası. Terminali kontrol edin.")
    
    st.markdown("---")
    st.markdown("### 🕒 Zaman Aralığı")
    zaman_dilimi = st.radio(
        "Görüntüleme Periyodu:",
        options=["Günlük (Son 24 Saat)", "Haftalık (Son 7 Gün)", "Aylık (Son 30 Gün)"],
        key="zaman_dilimi_hafizasi"
    )
    
    st.markdown("---")
    st.markdown("### ⚠️ Alarm Filtresi")
    kurallar = df_orijinal[df_orijinal['Kural_Ihlali'] != 'Yok']['Kural_Ihlali'].unique()
    secilen_kural = st.multiselect("Tehdit Vektörü Seçin:", options=kurallar, default=list(kurallar))

    st.markdown("---")
    st.markdown("### 🖥️ Arayüz Performansı")
    max_satir = st.slider(
        "Tablo Satır Sınırı:",
        min_value=100, max_value=2000, value=500, step=100
    )

# ============================================================
# 6. ANA EKRAN - HEDEF ODAKLI İNCELEME
# ============================================================
st.markdown("<div class='search-box'>", unsafe_allow_html=True)
st.markdown("### 🎯 Nokta Atışı İzleme")
arama_col1, arama_col2 = st.columns(2)

with arama_col1:
    kullanicilar = ["Tümü"] + list(df_orijinal['Kullanici'].dropna().unique())
    secilen_kullanici = st.selectbox("👤 Kullanıcı / Hesap Araştırması:", options=kullanicilar)

with arama_col2:
    ipler = ["Tümü"] + list(df_orijinal['IP_Adresi'].dropna().unique())
    secilen_ip = st.selectbox("🌐 Kaynak IP Araştırması:", options=ipler)
st.markdown("</div>", unsafe_allow_html=True)

# ============================================================
# 7. FİLTRELERİ UYGULAMA (ZAMAN PARADOKSU ÇÖZÜLDÜ)
# ============================================================
df_filtrelenmis = df_orijinal.copy()

if secilen_kullanici != "Tümü":
    df_filtrelenmis = df_filtrelenmis[df_filtrelenmis['Kullanici'] == secilen_kullanici]
if secilen_ip != "Tümü":
    df_filtrelenmis = df_filtrelenmis[df_filtrelenmis['IP_Adresi'] == secilen_ip]

# NOT: Gerçek bilgisayar saati (pd.Timestamp.now()) yerine veritabanındaki
# EN SON log zamanı baz alınıyor. log_uretici.py simüle saati gerçek zamandan
# çok daha hızlı ilerlettiği için (30-90 sim-dakika / birkaç saniyede bir),
# veriler gerçek "şimdi"nin ilerisine geçebiliyor. Gerçek saat referans alınırsa
# tüm kayıtlar her zaman "günlük/haftalık/aylık" eşiklerinin üstünde kalır ve
# periyot filtresi hiçbir şeyi değiştirmiyormuş gibi görünür.
su_an = df_orijinal['Zaman'].max()

if zaman_dilimi == "Günlük (Son 24 Saat)":
    baslangic = su_an - pd.Timedelta(days=1)
    df_filtrelenmis = df_filtrelenmis[df_filtrelenmis['Zaman'] >= baslangic]
    df_filtrelenmis['Zaman_Ekseni'] = df_filtrelenmis['Zaman'].dt.floor('30min').dt.strftime('%H:%M')
    zaman_etiketi = "Saat (30 Dk Periyot)"
    metrik_baslik = "Günlük"
elif zaman_dilimi == "Haftalık (Son 7 Gün)":
    baslangic = su_an - pd.Timedelta(days=7)
    df_filtrelenmis = df_filtrelenmis[df_filtrelenmis['Zaman'] >= baslangic]
    df_filtrelenmis['Zaman_Ekseni'] = df_filtrelenmis['Zaman'].dt.strftime('%Y-%m-%d')
    zaman_etiketi = "Gün"
    metrik_baslik = "Haftalık"
else:
    baslangic = su_an - pd.Timedelta(days=30)
    df_filtrelenmis = df_filtrelenmis[df_filtrelenmis['Zaman'] >= baslangic]
    df_filtrelenmis['Zaman_Ekseni'] = df_filtrelenmis['Zaman'].dt.strftime('%Y - %W. Hafta')
    zaman_etiketi = "Hafta"
    metrik_baslik = "Aylık"

if secilen_kural:
    df_gorsel_tablo = df_filtrelenmis[df_filtrelenmis['Kural_Ihlali'].isin(secilen_kural)]
else:
    df_gorsel_tablo = df_filtrelenmis[df_filtrelenmis['Kural_Skoru'] > 0]

durum_sozlugu = {
    'NT_STATUS_WRONG_PASSWORD': '❌ Hatalı Şifre',
    'NT_STATUS_OK': '✅ Başarılı Giriş',
    'NT_STATUS_ACCOUNT_LOCKED_OUT': '🔒 Hesap Kilitlendi',
    'NT_STATUS_PASSWORD_EXPIRED': '⏳ Şifre Süresi Doldu',
    'NT_STATUS_LOGON_FAILURE': '🚫 Giriş Başarısız'
}

# ============================================================
# 8. SEKMELİ YAPI (TABS)
# ============================================================
tab1, tab2 = st.tabs(["📈 Genel Tehdit Pano", "🕵️‍♂️ Derinlemesine Profil (UBA)"])

# ----------------- SEKME 1: GENEL PANO -----------------
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    # Dinamik başlık eklendi
    with col1: st.metric(label=f"📊 İşlenen Log ({metrik_baslik})", value=f"{len(df_filtrelenmis):,}")
    with col2: st.metric(label="🎯 Şüpheli Aktivite Sayısı", value=f"{len(df_gorsel_tablo):,}")
    with col3:
        kesin_tehdit = len(df_gorsel_tablo[df_gorsel_tablo['Anomali_Durumu'] == 1])
        st.metric(label="🚨 Yapay Zeka Onaylı Tehdit", value=f"{kesin_tehdit:,}", delta="Kritik Alarm" if kesin_tehdit > 0 else "Temiz", delta_color="inverse" if kesin_tehdit > 0 else "off")
    with col4:
        st.metric(label="⚠️ Zirve Risk Skoru", value=int(df_gorsel_tablo['Kural_Skoru'].max() if not df_gorsel_tablo.empty else 0))

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📈 Tehdit Vektörü ve Zamansal Dağılım")
    grafik_col1, grafik_col2 = st.columns(2)
    renk_paleti = ["#ef4444", "#f97316", "#eab308", "#3b82f6", "#8b5cf6", "#10b981"]

    with grafik_col1:
        st.markdown("**İhlal Türlerine Göre Risk Dağılımı**")
        ihlal_sayilari = df_gorsel_tablo['Kural_Ihlali'].value_counts().reset_index()
        ihlal_sayilari.columns = ['Ihlal_Turu', 'Adet']
        if not ihlal_sayilari.empty:
            fig1 = px.bar(ihlal_sayilari, x='Adet', y='Ihlal_Turu', orientation='h', color='Ihlal_Turu', color_discrete_sequence=renk_paleti, text='Adet')
            fig1.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#f1f5f9', showlegend=False, yaxis_title="", xaxis_title="Olay Sayısı", margin=dict(l=10, r=10, t=20, b=10), height=340)
            fig1.update_traces(textposition='outside')
            st.plotly_chart(fig1, use_container_width=True)

    with grafik_col2:
        st.markdown(f"**Zamana Bağlı Atak Grafiği ({zaman_etiketi})**")
        if 'Zaman_Ekseni' in df_gorsel_tablo.columns and not df_gorsel_tablo.empty:
            zaman_dagilimi = df_gorsel_tablo['Zaman_Ekseni'].value_counts().sort_index().reset_index()
            zaman_dagilimi.columns = ['Zaman_Ekseni', 'Adet']
            fig2 = px.area(zaman_dagilimi, x='Zaman_Ekseni', y='Adet', markers=True, color_discrete_sequence=["#ef4444"])
            fig2.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#f1f5f9', xaxis_title=zaman_etiketi, yaxis_title="Olay Sayısı", margin=dict(l=10, r=10, t=20, b=10), height=340)
            fig2.update_xaxes(type='category')
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(f"### 🗂️ Canlı Sistem Kayıtları (Tehdit Logları)")
    tablo_df = df_gorsel_tablo.head(max_satir).copy()
    if 'Durum' in tablo_df.columns: tablo_df['Durum'] = tablo_df['Durum'].replace(durum_sozlugu)
    if 'Anomali_Durumu' in tablo_df.columns: tablo_df['Anomali_Durumu'] = tablo_df['Anomali_Durumu'].apply(lambda x: '🚨 YZ Onaylı Tehdit' if x == 1 else '➖ Manuel İnceleme')
    if 'Zaman' in tablo_df.columns: tablo_df['Zaman'] = tablo_df['Zaman'].dt.strftime('%d.%m.%Y %H:%M:%S')

    gosterilecek_sutunlar = [col for col in ['Zaman', 'Kullanici', 'IP_Adresi', 'Durum', 'Kural_Ihlali', 'Kural_Skoru', 'Anomali_Durumu'] if col in tablo_df.columns]
    yeni_isimler = {'Zaman': '📅 Tarih/Saat', 'Kullanici': '👤 Hedef Hesap', 'IP_Adresi': '🌐 Saldırgan IP', 'Kural_Ihlali': '⚠️ İhlal Edilen Kural', 'Kural_Skoru': '📈 Risk Skoru', 'Anomali_Durumu': '🤖 Sistem Kararı'}
    
    if gosterilecek_sutunlar:
        st.dataframe(tablo_df[gosterilecek_sutunlar].rename(columns=yeni_isimler), use_container_width=True, height=400, hide_index=True)


# ----------------- SEKME 2: PROFİL VE DAVRANIŞ (UBA) -----------------
with tab2:
    if secilen_kullanici == "Tümü" and secilen_ip == "Tümü":
        st.info("👆 Lütfen Davranış Analizi (UBA) yapmak için yukarıdaki **Nokta Atışı İzleme** menüsünden spesifik bir Kullanıcı veya Kaynak IP seçin.")
    else:
        if secilen_kullanici != "Tümü" and secilen_ip != "Tümü":
            profil_baslik = f"{secilen_kullanici} Hesabı ve {secilen_ip} Ağı"
        elif secilen_kullanici != "Tümü":
            profil_baslik = f"👤 {secilen_kullanici} Hesabı"
        else:
            profil_baslik = f"🌐 {secilen_ip} IP Adresi"
            
        st.markdown(f"### {profil_baslik} İçin Dijital Ayak İzi")
        
        kullanici_verisi = df_orijinal.copy()
        if secilen_kullanici != "Tümü":
            kullanici_verisi = kullanici_verisi[kullanici_verisi['Kullanici'] == secilen_kullanici]
        if secilen_ip != "Tümü":
            kullanici_verisi = kullanici_verisi[kullanici_verisi['IP_Adresi'] == secilen_ip]
        
        toplam_islem = len(kullanici_verisi)
        essiz_ip_sayisi = kullanici_verisi['IP_Adresi'].nunique() if not kullanici_verisi.empty else 0
        
        kullanici_verisi['Saat'] = kullanici_verisi['Zaman'].dt.hour
        if not kullanici_verisi.empty:
            alt_sinir = int(kullanici_verisi['Saat'].quantile(0.10))
            ust_sinir = int(kullanici_verisi['Saat'].quantile(0.90))
            if alt_sinir == ust_sinir:
                saat_araligi = f"{alt_sinir:02d}:00 - {(ust_sinir+1):02d}:00"
            else:
                saat_araligi = f"{alt_sinir:02d}:00 - {ust_sinir:02d}:00"
        else:
            saat_araligi = "Veri Yetersiz"
            
        ihlal_sayisi = len(kullanici_verisi[kullanici_verisi['Kural_Ihlali'] != 'Yok'])
        
        p_col1, p_col2, p_col3, p_col4 = st.columns(4)
        p_col1.metric("Toplam Sistem İzi", f"{toplam_islem:,}")
        p_col2.metric("Sıçrama Tahtası (Farklı IP)", f"{essiz_ip_sayisi} Adet")
        p_col3.metric("Rutin Operasyon Saati", saat_araligi)
        p_col4.metric("Riskli Hareket Sayısı", ihlal_sayisi, delta="İnceleme Gerektirir" if ihlal_sayisi > 0 else "Normal", delta_color="inverse")
        
        st.markdown("<hr>", unsafe_allow_html=True)
        
        graf_col1, graf_col2 = st.columns(2)
        
        with graf_col1:
            st.markdown("**🕒 Saatlik Etkileşim Yoğunluğu (Profil Sapması)**")
            if not kullanici_verisi.empty:
                saatlik = kullanici_verisi['Saat'].value_counts().sort_index().reset_index()
                saatlik.columns = ['Saat', 'İşlem Sayısı']
                fig_saat = px.bar(saatlik, x='Saat', y='İşlem Sayısı', color_discrete_sequence=['#3b82f6'])
                fig_saat.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#f1f5f9', xaxis=dict(tickmode='linear', tick0=0, dtick=1), height=300)
                st.plotly_chart(fig_saat, use_container_width=True)
                
        with graf_col2:
            st.markdown("**📊 Operasyon Karakteristiği (Normal vs Anomali)**")
            if not kullanici_verisi.empty:
                kullanici_verisi['Durum_Gorsel'] = kullanici_verisi['Durum'].replace(durum_sozlugu)
                durum_dagilimi = kullanici_verisi['Durum_Gorsel'].value_counts().reset_index()
                durum_dagilimi.columns = ['Durum', 'Adet']
                fig_durum = px.pie(durum_dagilimi, values='Adet', names='Durum', hole=0.45, color_discrete_sequence=renk_paleti)
                fig_durum.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#f1f5f9', height=300)
                st.plotly_chart(fig_durum, use_container_width=True)

        st.markdown("<hr>", unsafe_allow_html=True)

        st.markdown(f"#### ⚡ Çapraz Davranış Kesiti (Normal & Şüpheli Harmanı)")
        
        normal_loglar = kullanici_verisi[kullanici_verisi['Kural_Ihlali'] == 'Yok'].head(5)
        riskli_loglar = kullanici_verisi[kullanici_verisi['Kural_Ihlali'] != 'Yok'].head(5)
        
        son_hareketler = pd.concat([normal_loglar, riskli_loglar]).sort_values(by='Zaman', ascending=False)
        
        if son_hareketler.empty:
            son_hareketler = kullanici_verisi.head(10)
            
        if 'Durum' in son_hareketler.columns: son_hareketler['Durum'] = son_hareketler['Durum'].replace(durum_sozlugu)
        if 'Zaman' in son_hareketler.columns: son_hareketler['Zaman'] = son_hareketler['Zaman'].dt.strftime('%d.%m.%Y %H:%M:%S')
        if 'Anomali_Durumu' in son_hareketler.columns: son_hareketler['Anomali_Durumu'] = son_hareketler['Anomali_Durumu'].apply(lambda x: '🚨 YZ Onaylı' if x == 1 else ('➖ Manuel' if x == 0 else '✅ Temiz'))
        
        if 'Kural_Ihlali' in son_hareketler.columns:
            son_hareketler['Kural_Ihlali'] = son_hareketler['Kural_Ihlali'].replace('Yok', '✔️ Normal Davranış')

        son_hareketler_sutunlar = [col for col in ['Zaman', 'IP_Adresi', 'Durum', 'Kural_Ihlali', 'Anomali_Durumu'] if col in son_hareketler.columns]
        son_isimler = {'Zaman': '📅 Tarih/Saat', 'IP_Adresi': '🌐 Bağlantı Adresi', 'Kural_Ihlali': '⚠️ Tetiklenen Kural', 'Anomali_Durumu': '🤖 Karar Mekanizması'}
        
        st.dataframe(son_hareketler[son_hareketler_sutunlar].rename(columns=son_isimler), use_container_width=True, hide_index=True)

st.markdown("<div class='footer-note'>🛡️ Merkezi Siber Tehdit Analiz ve Anomali Tespit Modülü</div>", unsafe_allow_html=True)