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

# Nilai default isian form (bisa disesuaikan)
JUMLAH_DESA = "17"
JUMLAH_BHABIN = "17"
JUMLAH_PIKET = "4"
JUMLAH_HADIR_DEFAULT = "30"
TEKS_UPAYA_BHABIN = "Mengoptimalkan peran Bhabinkamtibmas di setiap desa dan kelurahan"
TEKS_PIHAK_IKUT = "Personel Polsek Jatisrono dan warga masyarakat"
TEKS_KOMUNITAS = "Warga masyarakat Kec. Jatisrono"
TEKS_MATERI_POLIDIK = "Penyuluhan kamtibmas dan pencegahan penyalahgunaan narkoba"
TEKS_NAMA_MITRA = "Perangkat Desa dan UMKM Kec. Jatisrono"

# 4 Kegiatan Rutin Harian Kapolsek (Setiap Hari)
KEGIATAN_HARIAN_QW7 = [
    {"kode": "QW7.1", "tab": "Polres Kuat, Polsek Tangguh", "nama": "Satu desa satu Bhabinkamtibmas"},
    {"kode": "QW7.2", "tab": "Polres Kuat, Polsek Tangguh", "nama": "Penataan personel"},
    {"kode": "QW7.3", "tab": "Polres Kuat, Polsek Tangguh", "nama": "Polsek siaga 24 jam"},
    {"kode": "QW7.4", "tab": "Polres Kuat, Polsek Tangguh", "nama": "Perkara ringan dan rembuk masyarakat"},
]

# Jadwal Mingguan QW1 Berdasarkan Hari (0=Senin s/d 6=Minggu)
JADWAL_MINGGUAN_QW1 = {
    0: [  # Senin
        {"kode": "QW1.1", "tab": "Ruang Publik Aman", "nama": "Gatur pagi (pengaturan lalu lintas Senin pagi)"},
        {"kode": "QW1.2", "tab": "Ruang Publik Aman", "nama": "Polisi peduli pendidikan (Polidik)"},
    ],
    1: [  # Selasa (Analisis dan evaluasi - hanya QW7 di menu Kapolsek)
    ],
    2: [  # Rabu
        {"kode": "QW1.4", "tab": "Ruang Publik Aman", "nama": "Kumpul bersama masyarakat"},
    ],
    3: [  # Kamis
        {"kode": "QW1.3", "tab": "Ruang Publik Aman", "nama": "Polisi peduli pengangguran (Poliran)"},
    ],
    4: [  # Jumat
        {"kode": "QW1.5", "tab": "Ruang Publik Aman", "nama": "Green policing"},
        {"kode": "QW1.6", "tab": "Ruang Publik Aman", "nama": "Jumat keliling (Jumling)"},
    ],
    5: [  # Sabtu
        {"kode": "QW1.7", "tab": "Ruang Publik Aman", "nama": "Subuh keliling (Suling)"},
    ],
    6: [  # Minggu
        {"kode": "QW1.8", "tab": "Ruang Publik Aman", "nama": "Minggu kasih"},
    ],
}

NAMA_HARI_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


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


def ambil_foto_harian(page, folder_url, jumlah_giat):
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


def tutup_entri_opsional(page):
    """Menutup kartu 'Saran atau keluhan 1' dan 'Permintaan 1' (Tutup x) agar tidak menghalangi validasi."""
    try:
        # Tutup kartu Permintaan pertolongan (QW7.3)
        btn_tutup = page.locator("button", has_text="Tutup")
        for i in range(btn_tutup.count()):
            if btn_tutup.nth(i).is_visible():
                btn_tutup.nth(i).scroll_into_view_if_needed()
                btn_tutup.nth(i).click()
                page.wait_for_timeout(400)

        # Tutup kartu Saran atau keluhan (tombol ×)
        tombol_x = page.locator("xpath=//*[contains(text(), 'Saran atau keluhan')]/following::button[normalize-space()='×'][1]")
        if tombol_x.count() > 0 and tombol_x.first.is_visible():
            tombol_x.first.scroll_into_view_if_needed()
            tombol_x.first.click()
            page.wait_for_timeout(400)
    except Exception:
        pass


def pilih_pelaksana_kapolsek(page):
    try:
        btn_kapolsek = page.get_by_role("button", name="Kapolsek", exact=True)
        for i in range(btn_kapolsek.count()):
            if btn_kapolsek.nth(i).is_visible():
                btn_kapolsek.nth(i).scroll_into_view_if_needed()
                btn_kapolsek.nth(i).click()
                page.wait_for_timeout(400)
                break
    except Exception:
        pass


def klik_semua_tombol_teks(page, teks, exact=True):
    """Mengklik semua tombol yang sesuai teks (contoh: 'Ya' atau 'Ada')."""
    try:
        btns = page.get_by_role("button", name=teks, exact=exact)
        for i in range(btns.count()):
            if btns.nth(i).is_visible():
                btns.nth(i).scroll_into_view_if_needed()
                btns.nth(i).click()
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
                page.wait_for_timeout(400)
    except Exception:
        pass


def pilih_semua_dropdown_form(page):
    """Memilih opsi pertama pada semua dropdown 'Pilih' di dalam form laporan."""
    try:
        selects = page.locator("select")
        # Lewati select pertama (index 0) karena itu adalah dropdown Jabatan di bagian atas
        for i in range(1, selects.count()):
            sel = selects.nth(i)
            if sel.is_visible():
                opsi_count = sel.locator("option").count()
                if opsi_count > 1:
                    sel.scroll_into_view_if_needed()
                    sel.select_option(index=1)
                    page.wait_for_timeout(400)
    except Exception:
        pass


def isi_input_berdasarkan_placeholder(page, potongan_placeholder, nilai):
    try:
        inputs = page.locator(f"input[placeholder*='{potongan_placeholder}'], textarea[placeholder*='{potongan_placeholder}']")
        for i in range(inputs.count()):
            if inputs.nth(i).is_visible():
                inputs.nth(i).scroll_into_view_if_needed()
                inputs.nth(i).fill(nilai)
    except Exception:
        pass


def isi_angka_kosong(page, nilai_default="0"):
    try:
        num_inputs = page.locator("input[type='number']")
        for i in range(num_inputs.count()):
            el = num_inputs.nth(i)
            if el.is_visible():
                val = (el.input_value() or "").strip()
                if val == "":
                    el.scroll_into_view_if_needed()
                    el.fill(str(nilai_default))
    except Exception:
        pass


def isi_link_foto_drive(page, link_foto):
    try:
        inputs_drive = page.locator("input[placeholder*='Google Drive'], input[placeholder*='drive.google.com']")
        for i in range(inputs_drive.count()):
            if inputs_drive.nth(i).is_visible():
                # Jangan isi kolom MoU/kemitraan dengan link foto jika tidak diperlukan
                placeholder_text = (inputs_drive.nth(i).get_attribute("placeholder") or "").lower()
                if "mou" not in placeholder_text:
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


def isi_form_sesuai_kode(page, kode, link_foto):
    """Mengisi seluruh field spesifik berdasarkan kode kegiatan (QW1.1 - QW1.8 & QW7.1 - QW7.4)."""
    # 1. Klik tombol pembuka form (Ada / Ya) terlebih dahulu agar sub-kolom muncul
    if kode in ["QW1.1", "QW1.3", "QW1.6", "QW1.7", "QW1.8"]:
        klik_semua_tombol_teks(page, "Ada", exact=True)
    elif kode in ["QW7.1", "QW7.3"]:
        klik_semua_tombol_teks(page, "Ya", exact=True)

    # 2. Pilih Pelaksana: Kapolsek
    pilih_pelaksana_kapolsek(page)

    # 3. Tutup kartu opsional (Permintaan 1 & Saran/Keluhan 1)
    tutup_entri_opsional(page)

    # 4. Isi Lokasi, Koordinat, Jam, dan Dropdown
    isi_lokasi_dan_koordinat(page)
    klik_jam_sekarang(page)
    pilih_semua_dropdown_form(page)

    # 5. Penanganan spesifik per kode kegiatan
    if kode == "QW1.1":  # Gatur pagi (Senin)
        isi_angka_kosong(page, "1")

    elif kode == "QW1.2":  # Polisi peduli pendidikan (Senin)
        klik_semua_tombol_teks(page, "Penyuluhan", exact=True)
        isi_input_berdasarkan_placeholder(page, "Materi", TEKS_MATERI_POLIDIK)
        # Jika ada textarea/input materi tanpa placeholder spesifik
        textareas = page.locator("textarea")
        for i in range(textareas.count()):
            if textareas.nth(i).is_visible() and not (textareas.nth(i).input_value() or "").strip():
                textareas.nth(i).fill(TEKS_MATERI_POLIDIK)
        isi_angka_kosong(page, JUMLAH_HADIR_DEFAULT)

    elif kode == "QW1.3":  # Polisi peduli pengangguran (Kamis)
        klik_semua_tombol_teks(page, "Merekrut", exact=False)
        isi_input_berdasarkan_placeholder(page, "mitra", TEKS_NAMA_MITRA)
        isi_input_berdasarkan_placeholder(page, "Mitra", TEKS_NAMA_MITRA)
        isi_angka_kosong(page, "5")

    elif kode == "QW1.4":  # Kumpul bersama masyarakat (Rabu)
        isi_input_berdasarkan_placeholder(page, "paguyuban", TEKS_KOMUNITAS)
        isi_angka_kosong(page, JUMLAH_HADIR_DEFAULT)

    elif kode == "QW1.5":  # Green policing (Jumat)
        klik_semua_tombol_teks(page, "Kerja bakti kebersihan", exact=True)
        isi_input_berdasarkan_placeholder(page, "Dinas Lingkungan Hidup", TEKS_PIHAK_IKUT)
        isi_angka_kosong(page, JUMLAH_HADIR_DEFAULT)

    elif kode in ["QW1.6", "QW1.7"]:  # Jumling (Jumat) & Suling (Sabtu)
        klik_semua_tombol_teks(page, "Jamaah", exact=True)
        isi_angka_kosong(page, JUMLAH_HADIR_DEFAULT)

    elif kode == "QW1.8":  # Minggu kasih (Minggu)
        klik_semua_tombol_teks(page, "Menyampaikan pesan kamtibmas", exact=True)
        isi_angka_kosong(page, JUMLAH_HADIR_DEFAULT)

    elif kode == "QW7.1":  # Satu desa satu Bhabinkamtibmas
        num_inputs = page.locator("input[type='number']")
        vis_nums = [num_inputs.nth(i) for i in range(num_inputs.count()) if num_inputs.nth(i).is_visible()]
        if len(vis_nums) >= 2:
            vis_nums[0].fill(JUMLAH_DESA)
            vis_nums[1].fill(JUMLAH_BHABIN)
        isi_input_berdasarkan_placeholder(page, "mengusulkan", TEKS_UPAYA_BHABIN)
        isi_angka_kosong(page, JUMLAH_DESA)

    elif kode == "QW7.2":  # Penataan personel
        isi_angka_kosong(page, "0")

    elif kode == "QW7.3":  # Polsek siaga 24 jam
        klik_semua_tombol_teks(page, "Ya", exact=True)
        isi_angka_kosong(page, JUMLAH_PIKET)

    elif kode == "QW7.4":  # Perkara ringan dan rembuk masyarakat
        isi_angka_kosong(page, "0")

    # 6. Pastikan lagi kartu saran tertutup dan isi link foto Google Drive
    tutup_entri_opsional(page)
    isi_link_foto_drive(page, link_foto)


def jalankan_robot_kapolsek():
    wib_sekarang = datetime.now(timezone(timedelta(hours=7)))
    idx_hari = wib_sekarang.weekday()  # 0=Senin ... 6=Minggu
    nama_hari = NAMA_HARI_ID[idx_hari]

    # Gabungkan kegiatan jadwal hari ini (QW1) + kegiatan wajib harian (QW7)
    giat_hari_ini = JADWAL_MINGGUAN_QW1.get(idx_hari, []) + KEGIATAN_HARIAN_QW7
     daftar_kode_str = ", ".join([g["kode"] for g in giat_hari_ini])

    kirim_notif_telegram(
        f"🤖 Robot Kapolsek Posko PBM mulai berjalan...\n"
        f"📅 Hari/Tanggal: {nama_hari}, {wib_sekarang.strftime('%d-%m-%Y')}\n"
        f"👮 Pelapor: {NAMA_PELAPOR}\n"
        f"📋 Target ({len(giat_hari_ini)} Giat): {daftar_kode_str}"
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
            foto_harian = ambil_foto_harian(page, FOLDER_URL_KAPOLSEK, len(giat_hari_ini))

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

            # 3. Eksekusi seluruh kegiatan hari ini (QW1 sesuai hari + QW7 harian)
            for idx, item in enumerate(giat_hari_ini):
                kode = item["kode"]
                nama_tab = item["tab"]
                nama_giat = item["nama"]
                link_foto, no_foto, tot_foto = foto_harian[idx]

                # Buka tab Quick Wins (QW1 atau QW7) jika sub-kegiatan belum tampil
                if not page.get_by_text(kode).first.is_visible():
                    tab_el = page.locator("button", has_text=nama_tab).last
                    tab_el.scroll_into_view_if_needed()
                    tab_el.click()
                    page.wait_for_timeout(1500)

                # Klik sub-kegiatan berdasarkan kode
                giat_el = page.get_by_text(kode).last
                giat_el.scroll_into_view_if_needed()
                giat_el.click()
                page.wait_for_timeout(2500)

                # Isi seluruh kolom form sesuai kode kegiatan
                isi_form_sesuai_kode(page, kode, link_foto)

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
                    f"✅ Laporan Kapolsek {kode} ({nama_hari}) berhasil dikirim!\n\n"
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
