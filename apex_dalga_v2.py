"""
Apex 3 TKL - tusa basinca bolgesel dalga efekti (OpenRGB'siz, v2)

Gerekenler:
    - apex_hid.py bu dosyayla AYNI klasorde olmali
    - pip install keyboard   (zaten kurulu)

Calistirmadan once SteelSeries GG ve OpenRGB KAPALI olsun.
Calistir:  python apex_dalga_v2.py        Durdur: Ctrl+C
"""

import colorsys
import math
import threading
import time

import keyboard

from apex_hid import ApexKlavye

# ---------------- AYARLAR (istedigin gibi oynat) ----------------
FPS = 25               # kare hizi; takilma olursa 15'e dusur, rahatsa 40 dene
HIZ = 8.0              # dalganin yayilma hizi (bolge/saniye)
OMUR = 0.55            # dalganin sonme suresi (saniye)
KALINLIK = 1.6         # dalga halkasinin kalinligi (bolge)
PARLAKLIK = 1.0        # 0.0 - 1.0
MAX_DALGA = 8          # ayni anda en fazla kac dalga
RENK_MODU = "gokkusagi"      # "gokkusagi" ya da "sabit"
SABIT_RENK = (0, 180, 255)   # RENK_MODU = "sabit" ise (R, G, B)
ARKAPLAN = (0, 0, 0)         # bos durumdaki renk, ornek: (10, 0, 20)
BOLGE_SAYISI = 8
TOPLAM_GENISLIK = 18.5  # klavyenin tus genisligi cinsinden toplam genisligi
SOL_BOSLUK = 0.0
# ----------------------------------------------------------------

# Tusun fiziksel konumu (scan code'a gore; Turkce/Ingilizce Q duzeninde ayni calisir)
KONUM = {}
KONUM[1] = 0.5  # Esc
for i, sc in enumerate(range(59, 69)):  # F1-F10
    KONUM[sc] = 2.5 + i * 1.0 + (i // 4) * 0.5
KONUM[87] = 12.5  # F11
KONUM[88] = 13.5  # F12
KONUM[41] = 0.5  # `
for sc in range(2, 14):  # 1 2 3 ... - =
    KONUM[sc] = 1.5 + (sc - 2)
KONUM[14] = 14.0  # Backspace
KONUM[15] = 0.75  # Tab
for sc in range(16, 28):  # Q W E ... [ ]
    KONUM[sc] = 2.0 + (sc - 16)
KONUM[28] = 14.0  # Enter
KONUM[58] = 0.9  # Caps
for sc in range(30, 42):  # A S D ... ; '
    KONUM[sc] = 2.25 + (sc - 30)
KONUM[43] = 14.0
KONUM[42] = 1.1  # Sol Shift
KONUM[86] = 2.0  # < > tusu
for sc in range(44, 54):  # Z X C ... . /
    KONUM[sc] = 2.75 + (sc - 44)
KONUM[54] = 13.0  # Sag Shift
KONUM[29] = 0.7  # Ctrl
KONUM[56] = 3.5  # Alt
KONUM[57] = 7.0  # Space
KONUM[75] = 15.5  # Sol ok
KONUM[80] = 16.5  # Asagi ok
KONUM[77] = 17.5  # Sag ok
KONUM[72] = 16.5  # Yukari ok

kilit = threading.Lock()
dalgalar = []  # (merkez_bolge, baslangic_zamani, renk)
hue_sayac = [0.0]


def bolge_bul(scan_code):
    x = KONUM.get(scan_code)
    if x is None:
        return None
    oran = (x - SOL_BOSLUK) / TOPLAM_GENISLIK
    return min(max(oran * BOLGE_SAYISI, 0), BOLGE_SAYISI - 1e-6)


def renk_sec():
    if RENK_MODU == "sabit":
        return SABIT_RENK
    hue_sayac[0] = (hue_sayac[0] + 0.06) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue_sayac[0], 1.0, 1.0)
    return (int(r * 255), int(g * 255), int(b * 255))


def kare_hesapla(aktif, simdi):
    """Verilen dalgalar icin 8 bolgenin (R,G,B) degerlerini hesaplar."""
    n = BOLGE_SAYISI
    toplam = [list(map(float, ARKAPLAN)) for _ in range(n)]
    for merkez, basla, (r, g, b) in aktif:
        yas = simdi - basla
        yaricap = yas * HIZ
        sonum = math.exp(-yas / OMUR)
        for z in range(n):
            mesafe = abs((z + 0.5) - merkez)
            fark = abs(mesafe - yaricap)
            siddet = max(0.0, 1.0 - fark / KALINLIK)
            if yas < 0.08 and mesafe < 0.8:  # basilan yer ilk anda parlasin
                siddet = 1.0
            v = siddet * sonum * PARLAKLIK
            toplam[z][0] += r * v
            toplam[z][1] += g * v
            toplam[z][2] += b * v
    return tuple(
        (min(255, int(c[0])), min(255, int(c[1])), min(255, int(c[2]))) for c in toplam
    )


def main():
    kb = ApexKlavye()
    if not kb.baglan():
        print("Klavye kontrol arayuzu acilamadi.")
        print("SteelSeries GG ve OpenRGB tamamen kapali mi? Kablo takili mi?")
        return
    print("Klavyeye dogrudan baglanildi (OpenRGB gerekmiyor).")

    def tus_basildi(olay):
        if olay.event_type != "down":
            return
        merkez = bolge_bul(olay.scan_code)
        if merkez is None:
            return
        with kilit:
            dalgalar.append((merkez, time.time(), renk_sec()))
            del dalgalar[:-MAX_DALGA]

    keyboard.hook(tus_basildi)
    print("Calisiyor! Yazmaya basla. Cikmak icin Ctrl+C.")

    aralik = 1.0 / FPS
    son_gonderilen = None
    try:
        while True:
            t0 = time.time()
            with kilit:
                dalgalar[:] = [d for d in dalgalar if t0 - d[1] < OMUR * 2.5]
                aktif = list(dalgalar)

            kare = kare_hesapla(aktif, t0)

            # Sadece isiklar degistiyse gonder
            if kare != son_gonderilen:
                if kb.renk_gonder(list(kare)):
                    son_gonderilen = kare
                else:
                    print("Gonderilemedi, yeniden baglaniliyor...")
                    son_gonderilen = None
                    time.sleep(0.5)

            gecen = time.time() - t0
            if gecen < aralik:
                time.sleep(aralik - gecen)
    except KeyboardInterrupt:
        pass
    finally:
        keyboard.unhook_all()
        try:
            kb.renk_gonder([(0, 0, 0)] * BOLGE_SAYISI)
        except Exception:
            pass
        kb.kapat()
        print("Kapatildi.")


if __name__ == "__main__":
    main()
