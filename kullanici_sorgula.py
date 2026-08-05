import argparse
import sqlite3
import sys
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

DB_YOLU = "log_veritabani.db"
HEDEF_TABLO = "hibrit_tespit_sonuclari"

DURUM_SOZLUGU = {
    'NT_STATUS_WRONG_PASSWORD': 'Hatalı Şifre',
    'NT_STATUS_OK': 'Başarılı Giriş',
    'NT_STATUS_ACCOUNT_LOCKED_OUT': 'Hesap Kilitlendi',
    'NT_STATUS_PASSWORD_EXPIRED': 'Şifre Süresi Doldu',
    'NT_STATUS_LOGON_FAILURE': 'Giriş Başarısız'
}

console = Console()


def davranis_profili_goster(df):
    """Kullanıcının 'normal' davranış temelini (baseline) özetler: rutin saat
    aralığı, en sık kullanılan IP'ler, başarı/başarısızlık oranları vb."""
    essiz_ip = df['IP_Adresi'].nunique()
    en_sik_ipler = df['IP_Adresi'].value_counts().head(3)

    alt_sinir = int(df['Saat'].quantile(0.10))
    ust_sinir = int(df['Saat'].quantile(0.90))
    if alt_sinir == ust_sinir:
        rutin_saat = f"{alt_sinir:02d}:00 - {(ust_sinir + 1) % 24:02d}:00"
    else:
        rutin_saat = f"{alt_sinir:02d}:00 - {ust_sinir:02d}:00"

    basarisiz_oran = df['Basarisiz_Giris_Mi'].mean() * 100
    hafta_sonu_oran = df['Hafta_Sonu'].mean() * 100
    mesai_disi_oran = df['Mesai_Disi'].mean() * 100

    gecerli_aralar = df.loc[df['Onceki_Islem_Farki_Sn'] > 0, 'Onceki_Islem_Farki_Sn']
    medyan_ara_sure = gecerli_aralar.median() if not gecerli_aralar.empty else None
    if medyan_ara_sure is None or pd.isna(medyan_ara_sure):
        ara_sure_metni = "Yetersiz veri"
    else:
        dk, sn = divmod(int(medyan_ara_sure), 60)
        ara_sure_metni = f"{dk} dk {sn} sn" if dk > 0 else f"{sn} sn"

    en_sik_durum_serisi = df['Durum'].replace(DURUM_SOZLUGU).mode()
    en_sik_durum_metni = en_sik_durum_serisi.iloc[0] if not en_sik_durum_serisi.empty else "-"

    ip_satirlari = "\n".join(
        f"    {ip}  →  {adet} kayıt (%{adet / len(df) * 100:.0f})"
        for ip, adet in en_sik_ipler.items()
    )

    profil_metni = (
        f"[bold]Rutin çalışma saat aralığı[/bold]  : {rutin_saat}  [dim](kayıtların ~%80'i bu aralıkta)[/dim]\n"
        f"[bold]En sık görülen durum[/bold]        : {en_sik_durum_metni}\n"
        f"[bold]Farklı IP sayısı[/bold]            : {essiz_ip}\n"
        f"[bold]En sık kullanılan IP'ler[/bold]    :\n{ip_satirlari}\n"
        f"[bold]Başarısız giriş oranı[/bold]       : %{basarisiz_oran:.1f}\n"
        f"[bold]Mesai dışı işlem oranı[/bold]      : %{mesai_disi_oran:.1f}\n"
        f"[bold]Hafta sonu işlem oranı[/bold]      : %{hafta_sonu_oran:.1f}\n"
        f"[bold]Medyan işlemler arası süre[/bold]  : {ara_sure_metni}"
    )
    console.print(Panel(profil_metni, title="📊 Davranış Profili (Normal Baseline)", border_style="green", expand=False))


def saatlik_grafik_ciz(df):
    """0-23 saat aralığında basit ASCII/blok karakterli bir yoğunluk grafiği çizer."""
    saatlik = df['Saat'].value_counts().reindex(range(24), fill_value=0).sort_index()
    maks = int(saatlik.max())
    if maks == 0:
        return

    console.print("\n[bold]⏱  Saatlik Aktivite Yoğunluğu[/bold]")
    genislik = 40
    for saat, adet in saatlik.items():
        bar_uzunlugu = round((adet / maks) * genislik)
        bar = "█" * bar_uzunlugu
        if adet == maks:
            renk = "bold red"
        elif saat < 8 or saat > 18:
            renk = "yellow"
        else:
            renk = "cyan"
        console.print(f"  {saat:02d}:00 │ [{renk}]{bar}[/{renk}] {adet}")


def main():
    parser = argparse.ArgumentParser(description="Belirli bir kullanıcının ayrıştırılmış log ve anomali kayıtlarını terminalde gösterir.")
    parser.add_argument("kullanici", help="Sorgulanacak kullanıcı adı (Kullanici sütunu)")
    parser.add_argument("--sadece-anomali", action="store_true", help="Sadece YZ tarafından anomali/kural ihlali işaretlenen kayıtları göster")
    parser.add_argument("--limit", type=int, default=50, help="Gösterilecek maksimum kayıt sayısı (varsayılan: 50)")
    args = parser.parse_args()

    baglanti = sqlite3.connect(DB_YOLU)
    try:
        df = pd.read_sql(
            f"SELECT * FROM {HEDEF_TABLO} WHERE Kullanici = ? ORDER BY Zaman DESC",
            baglanti,
            params=(args.kullanici,)
        )
    except sqlite3.OperationalError as e:
        console.print(f"[bold red]Veritabanı hatası:[/bold red] {e}")
        sys.exit(1)
    finally:
        baglanti.close()

    if df.empty:
        console.print(f"[bold red]'{args.kullanici}' kullanıcısına ait kayıt bulunamadı.[/bold red]")
        baglanti = sqlite3.connect(DB_YOLU)
        benzerler = pd.read_sql(f"SELECT DISTINCT Kullanici FROM {HEDEF_TABLO}", baglanti)
        baglanti.close()
        console.print("\n[bold]Veritabanındaki kullanıcılar:[/bold]")
        console.print(", ".join(sorted(benzerler['Kullanici'].dropna().unique())))
        sys.exit(0)

    df['Zaman'] = pd.to_datetime(df['Zaman'], errors='coerce')

    toplam = len(df)
    ihlalli = len(df[df['Kural_Ihlali'] != 'Yok'])
    yz_onayli = len(df[df['Anomali_Durumu'] == 1])

    ozet_metni = (
        f"[bold]Toplam kayıt[/bold]        : {toplam}\n"
        f"[bold]Kural ihlali sayısı[/bold] : [yellow]{ihlalli}[/yellow]\n"
        f"[bold]YZ onaylı anomali[/bold]   : [bold red]{yz_onayli}[/bold red]\n"
        f"[bold]İlk işlem[/bold]           : {df['Zaman'].min()}\n"
        f"[bold]Son işlem[/bold]           : {df['Zaman'].max()}"
    )
    console.print(Panel(ozet_metni, title=f"🛡️ {args.kullanici} — Kullanıcı Özeti", border_style="cyan", expand=False))

    davranis_profili_goster(df)
    saatlik_grafik_ciz(df)
    console.print()

    gosterilecek = df if not args.sadece_anomali else df[(df['Kural_Ihlali'] != 'Yok') | (df['Anomali_Durumu'] == 1)]

    if gosterilecek.empty:
        console.print("[yellow]Bu filtreye uyan kayıt yok.[/yellow]")
        sys.exit(0)

    eslesme_sayisi = len(gosterilecek)
    gosterilecek = gosterilecek.head(args.limit).copy()
    gosterilecek['Durum'] = gosterilecek['Durum'].replace(DURUM_SOZLUGU)
    gosterilecek['Zaman'] = gosterilecek['Zaman'].dt.strftime('%d.%m.%Y %H:%M:%S')

    baslik = f"Kayıtlar (en fazla {args.limit} satır — toplam {eslesme_sayisi} eşleşme var)"
    tablo = Table(title=baslik, box=box.ROUNDED, header_style="bold white on dark_blue", show_lines=False)
    tablo.add_column("Tarih/Saat", style="dim", no_wrap=True)
    tablo.add_column("IP Adresi", no_wrap=True)
    tablo.add_column("Durum", no_wrap=True, overflow="ellipsis", max_width=18)
    tablo.add_column("Kural İhlali", no_wrap=True, overflow="ellipsis", max_width=26)
    tablo.add_column("Skor", justify="right", no_wrap=True)
    tablo.add_column("Karar", justify="center", no_wrap=True)

    for _, satir in gosterilecek.iterrows():
        anomali_mi = satir['Anomali_Durumu'] == 1
        ihlal_mi = satir['Kural_Ihlali'] != 'Yok'

        karar_metni = "[bold red]🚨 YZ Onaylı[/bold red]" if anomali_mi else "[dim]➖ Manuel[/dim]"
        kural_metni = f"[yellow]{satir['Kural_Ihlali']}[/yellow]" if ihlal_mi else "[dim]Yok[/dim]"
        durum_stili = "[red]" + str(satir['Durum']) + "[/red]" if "Hatalı" in str(satir['Durum']) or "Başarısız" in str(satir['Durum']) or "Kilitlendi" in str(satir['Durum']) else str(satir['Durum'])
        skor_metni = f"[bold]{satir['Kural_Skoru']}[/bold]" if satir['Kural_Skoru'] > 0 else "0"

        tablo.add_row(
            satir['Zaman'],
            satir['IP_Adresi'],
            durum_stili,
            kural_metni,
            skor_metni,
            karar_metni
        )

    console.print(tablo)


if __name__ == "__main__":
    main()
