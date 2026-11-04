import os
import re
from datetime import datetime, date, timedelta, timezone
import requests
from playwright.sync_api import sync_playwright

EMAIL = os.environ.get("POSKO_EMAIL", "").strip()
PASSWORD = os.environ.get("POSKO_PASSWORD", "").strip()
TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

NAMA_PELAPOR = "AKP AGUS SUYANTO, S.H., M.H."
FOLDER_URL_KAPOLSEK = "https://drive.google.com/drive/folders/1q2wd72u-Hx3cEcMe2aBCykG8HjtuyBO2"
DEFAULT_LINK = "https://drive.google.com/file/d/17KmVFmPU-OZk0dBdbVgF7AZ6ayhGWPyl/view?usp=drivesdk"
TANGGAL_PATOKAN = date(2026, 10, 28)

LOKASI_KAPOLSEK = "MAKO POLSEK JATISRONO, KEC. JATISRONO"
KOORDINAT_KAPOLSEK = "(-7.8273937, 111.1285440)"

# 4 Kegiatan Harian Kapolsek (QW7.1 s/d QW7.4)
DAFTAR_KEGIATAN_KAPOLSEK = [
    {
        "kode": "QW7.1",
        "tab": "Polres Kuat, Polsek Tangguh",
        "nama": "Satu desa satu Bhabinkamtibmas"
    },
    {
        "kode": "QW7.2",
        "tab": "Polres Kuat, Polsek Tangguh",
        "nama": "Penataan personel"
    },
    {
        "kode": "QW7.3",
        "tab": "Polres Kuat, Polsek Tangguh",
        "nama": "Polsek siaga 24 jam"
    },
    {
        "kode": "QW7.4",
        "tab": "Polres Kuat, Polsek Tangguh",
        "nama": "Perkara ringan dan rembuk masyarakat"
    },
]

def kirim_notif_telegram(pesan, foto_path=None):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    daftar_chat_id = [cid.strip() for cid in TG_CHAT_ID.split(",") if cid.strip()]
    for cid in daftar_chat_id:
        try:
            if foto_path and os.path.exists(foto_path):
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
                with open(foto_path, "rb") as f:
                    requests.post(url, data={"chat_id": cid, "caption": pesan[:1000]}, files={"photo": f}, timeout=20)
            else:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                requests.post(url, data={"chat_id": cid, "text": pesan[:4000]}, timeout=20)
        except Exception as e:
            print(f"Gagal kirim ke Telegram ({cid}):", e)

def ambil_foto_harian(page, folder_url):
    jumlah_giat = len(DAFTAR_KEGIATAN_KAPOLSEK)
    wib_sekarang = datetime.now(timezone(timedelta(hours=7))).date()
    selisih_hari = max(0, (wib_sekarang - TANGGAL_PATOKAN).days)

    kode_utama = folder_url.rstrip("/").split("/")[-1].split("?")[0]
    embed_url = f"https://drive.google.com/embeddedfolderview?id={kode_utama}#list"

    file_links = []
    seen = set()
    try:
        res = requests.get(embed_url, timeout=20)
        ids = re.findall(r"/file/d/([a-zA-Z0-9_-]{25,})/", res.text)
        if not ids:
            ids = re.findall(r'id="entry-([a-zA-Z0-9_-]{25,})"', res.text)

        for item_id in ids:
            if item_id != kode_utama and item_id not in seen:
                seen.add(item_id)
                file_links.append(f"https://drive.google.com/file/d/{item_id}/view?usp=drivesdk")

        if not file_links:
            page.goto(embed_url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            html = page.content()
            ids2 = re.findall(r"/file/d/([a-zA-Z0-9_-]{25,})/", html)
            if not ids2:
                ids2 = re.findall(r'id="entry-([a-zA-Z0-9_-]{25,})"', html)
            for item_id in ids2:
                if item_id != kode_utama and item_id not in seen:
                    seen.add(item_id)
                    file_links.append(f"https://drive.google.com/file/d/{item_id}/view?usp=drivesdk")
    except Exception as e:
        print("Gagal memindai folder Google Drive:", e)

    if file_links:
        total_foto = len(file_links)
        base_idx = selisih_hari * jumlah_giat
        hasil_foto = []
        for i in range(jumlah_giat):
            idx_terpilih = (base_idx + i) % total_foto
            hasil_foto.append((file_links[idx_terpilih], idx_terpilih + 1, total_foto))
        return hasil_foto

    return [(DEFAULT_LINK, i + 1, 1) for i in range(jumlah_giat)]

def tutup_saran_jika_ada(page):
    try:
        tombol_x = page.locator("xpath=//*[contains(text(), 'Saran atau keluhan')]/following::button[normalize-space()='×'][1]")
        if tombol_x.count() > 0 and tombol_x.first.is_visible():
            tombol_x.first.scroll_into_view_if_needed()
            tombol_x.first.click()
            page.wait_for_timeout(500)
    except Exception:
        pass

def pilih_pelaksana_kapolsek(page):
    try:
        btn_kapolsek = page.get_by_role("button", name="Kapolsek", exact=True)
        if btn_kapolsek.count() > 0 and btn_kapolsek.first.is_visible():
            btn_kapolsek.first.scroll_into_view_if_needed()
            btn_kapolsek.first.click()
            page.wait_for_timeout(500)
    except Exception:
        pass

def klik_tombol_ya_atau_tidak(page, pilihan="Ya"):
    try:
        btn = page.get_by_role("button", name=pilihan, exact=True)
        if btn.count() > 0 and btn.first.is_visible():
            btn.first.scroll_into_view_if_needed()
            btn.first.click()
            page.wait_for_timeout(500)
    except Exception:
        pass

def isi_lokasi_dan_koordinat(page):
    try:
        inp_tempat = page.locator("input[placeholder*='Nama tempat']")
        for i in range(inp_tempat.count()):
            if inp_tempat.nth(i).is_visible():
                inp_tempat.nth(i).scroll_into_view_if_needed()
                inp_tempat.nth(i).fill(LOKASI_KAPOLSEK)

        inp_koord = page.locator("input[placeholder*='Tempel koordinat']")
        for i in range(inp_koord.count()):
            if inp_koord.nth(i).is_visible():
                inp_koord.nth(i).scroll_into_view_if_needed()
                inp_koord.nth(i).fill(KOORDINAT_KAPOLSEK)
    except Exception:
        pass

def klik_jam_sekarang(page):
    try:
        btn_jam = page.get_by_role("button", name="Isi jam sekarang")
        for i in range(btn_jam.count()):
            if btn_jam.nth(i).is_visible():
                btn_jam.nth(i).scroll_into_view_if_needed()
                btn_jam.nth(i).click()
                page.wait_for_timeout(500)
    except Exception:
        pass

def isi_angka_kosong_dengan_nol(page):
    try:
        num_inputs = page.locator("input[type='number']")
        for i in range(num_inputs.count()):
            el = num_inputs.nth(i)
            if el.is_visible():
                val = (el.input_value() or "").strip()
                if val == "":
                    el.scroll_into_view_if_needed()
                    el.fill("0")
    except Exception:
        pass

def isi_link_foto_drive(page, link_foto):
    try:
        inputs_drive = page.locator("input[placeholder*='Google Drive'], input[placeholder*='drive.google.com']")
        for i in range(inputs_drive.count()):
            if inputs_drive.nth(i).is_visible():
                inputs_drive.nth(i).scroll_into_view_if_needed()
                inputs_drive.nth(i).fill(link_foto)
    except Exception:
        pass

def klik_tetap_kirim_jika_ada(page):
    try:
        btn_tetap = page.get_by_role("button", name="Tetap kirim")
        if btn_tetap.count() > 0 and btn_tetap.first.is_visible():
            btn_tetap.first.scroll_into_view_if_needed()
            btn_tetap.first.click()
            page.wait_for_timeout(3000)
    except Exception:
        pass

def jalankan_robot_kapolsek():
    kirim_notif_telegram(
        f"🤖 Robot Kapolsek Posko PBM mulai berjalan...\n"
        f"👮 Pelapor: {NAMA_PELAPOR}\n"
        f"📋 Target: 4 Kegiatan Harian QW7"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            viewport={"width": 412, "height": 915},
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        )
        page = context.new_page()

        try:
            foto_harian = ambil_foto_harian(page, FOLDER_URL_KAPOLSEK)

            page.goto("https://poskopbm.polri.go.id/input", timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # 1. Login jika diminta
            if page.locator("input[type='password']").count() > 0:
                page.locator("input[type='email'], input[type='text']").first.fill(EMAIL)
                page.locator("input[type='password']").first.fill(PASSWORD)
                page.get_by_role("button", name="Masuk").click()
                page.wait_for_timeout(5000)

            # 2. Isi Nama Pelapor & Pilih Jabatan Kapolsek/Wakapolsek
            page.get_by_label("Nama dan pangkat pelapor").fill(NAMA_PELAPOR)
            select_jabatan = page.locator("select").first
            opsi_kapolsek = select_jabatan.locator("option", has_text="Kapolsek").first
            teks_jabatan = (opsi_kapolsek.text_content() or "").strip()
            select_jabatan.select_option(label=teks_jabatan)
            page.wait_for_timeout(2500)

            # 3. Eksekusi 4 Kegiatan Harian Kapolsek (QW7.1 s/d QW7.4)
            for idx, item in enumerate(DAFTAR_KEGIATAN_KAPOLSEK):
                kode = item["kode"]
                nama_tab = item["tab"]
                nama_giat = item["nama"]
                link_foto, no_foto, tot_foto = foto_harian[idx]

                # Buka tab Quick Wins jika belum tampil
                if not page.get_by_text(kode).first.is_visible():
                    tab_el = page.locator("button", has_text=nama_tab).last
                    tab_el.scroll_into_view_if_needed()
                    tab_el.click()
                    page.wait_for_timeout(1500)

                # Klik sub-kegiatan berdasarkan kode (QW7.1, QW7.2, dst.)
                giat_el = page.get_by_text(kode).last
                giat_el.scroll_into_view_if_needed()
                giat_el.click()
                page.wait_for_timeout(2500)

                # Pilih Pelaksana: Kapolsek
                pilih_pelaksana_kapolsek(page)

                # Logika khusus per kegiatan QW7
                if kode == "QW7.1":
                    klik_tombol_ya_atau_tidak(page, "Ya")
                elif kode == "QW7.2":
                    pass # Hanya isi angka di bawah
                elif kode == "QW7.3":
                    klik_jam_sekarang(page)
                    klik_tombol_ya_atau_tidak(page, "Ya")
                elif kode == "QW7.4":
                    isi_lokasi_dan_koordinat(page)
                    klik_jam_sekarang(page)

                # Tutup kotak saran dan isi angka nol
                tutup_saran_jika_ada(page)
                isi_angka_kosong_dengan_nol(page)
                isi_link_foto_drive(page, link_foto)

                # Kirim laporan
                page.wait_for_timeout(1000)
                btn_kirim = page.get_by_role("button", name="Kirim laporan")
                btn_kirim.scroll_into_view_if_needed()
                btn_kirim.click()
                page.wait_for_timeout(2000)

                klik_tetap_kirim_jika_ada(page)
                page.wait_for_timeout(4000)

                btn_kirim.scroll_into_view_if_needed()
                ss_path = f"bukti_{kode.replace('.', '_')}.png"
                page.screenshot(path=ss_path)
                kirim_notif_telegram(
                    f"✅ Laporan Kapolsek {kode} berhasil dikirim!\n\n"
                    f"📌 Kegiatan: {nama_giat}\n"
                    f"👮 Pelapor: {NAMA_PELAPOR}\n"
                    f"📸 Foto ke-{no_foto} dari {tot_foto}\n"
                    f"🔗 Link: {link_foto}",
                    ss_path
                )

        except Exception as e:
            err_ss = "error_kapolsek.png"
            try:
                page.screenshot(path=err_ss)
                kirim_notif_telegram(f"⚠️ Gagal mengirim laporan Kapolsek:\n{str(e)}", err_ss)
            except Exception:
                kirim_notif_telegram(f"⚠️ Gagal membuka web Kapolsek:\n{str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    jalankan_robot_kapolsek()
