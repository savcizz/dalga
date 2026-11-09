"""
DALGA v0.4 - Apex 3 TKL icin tusa basinca bolgesel dalga efekti (arayuzlu)

Gerekenler:
    - apex_hid.py bu dosyayla AYNI klasorde olmali
    - pip install keyboard   (zaten kurulu)

Calistirmadan once SteelSeries GG ve OpenRGB KAPALI olsun.
Calistir:  python dalga.py
Ayarlar, ayni klasordeki ayarlar.json dosyasina otomatik kaydedilir.
"""

import colorsys
import json
import math
import os
import re
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import colorchooser

import keyboard

from apex_hid import ApexKlavye

SURUM = "v0.4"
KLASOR = os.path.dirname(os.path.abspath(__file__))
AYAR_DOSYASI = os.path.join(KLASOR, "ayarlar.json")

BOLGE_SAYISI = 8
TOPLAM_GENISLIK = 18.5  # klavyenin tus genisligi cinsinden toplam genisligi
SOL_BOSLUK = 0.0
MIN_KALINLIK = 0.8      # bunun altinda titreme yapiyor

VARSAYILAN = {
    "hiz": 8.0,                 # dalganin yayilma hizi (bolge/saniye)
    "kalinlik": 1.6,            # dalga halkasinin kalinligi (bolge), en az 0.8
    "parlaklik": 100,           # dalga parlakligi, yuzde 5-100
    "mod": "gokkusagi",         # "gokkusagi" ya da "sabit"
    "renk": "#00d4ff",          # sabit mod rengi
    "bekleme_acik": False,      # bekleme isigi acik mi
    "bekleme_renk": "#3b1fa3",  # bekleme isigi rengi
    "bekleme_parlaklik": 35,    # bekleme isigi parlakligi, yuzde 1-100
    "omur": 0.55,               # dalganin sonme suresi (saniye)  [sadece dosyadan]
    "fps": 25,                  # kare hizi                       [sadece dosyadan]
    "max_dalga": 8,             # ayni anda en fazla dalga        [sadece dosyadan]
}

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


# ---------------------------- AYARLAR ----------------------------
def ayar_temizle(ayar):
    """Dosyadan gelen bozuk / eski degerleri duzeltir."""
    for k, alt, ust in (
        ("hiz", 2.0, 20.0),
        ("kalinlik", MIN_KALINLIK, 4.0),
        ("parlaklik", 5, 100),
        ("bekleme_parlaklik", 1, 100),
    ):
        try:
            v = float(ayar[k])
        except Exception:
            v = VARSAYILAN[k]
        v = max(alt, min(ust, v))
        ayar[k] = int(round(v)) if k.endswith("parlaklik") else round(v, 2)
    for k in ("renk", "bekleme_renk"):
        if not (isinstance(ayar[k], str) and HEX.match(ayar[k])):
            ayar[k] = VARSAYILAN[k]
    if ayar["mod"] not in ("gokkusagi", "sabit"):
        ayar["mod"] = VARSAYILAN["mod"]
    ayar["bekleme_acik"] = bool(ayar["bekleme_acik"])
    return ayar


def ayar_yukle():
    ayar = dict(VARSAYILAN)
    try:
        with open(AYAR_DOSYASI, "r", encoding="utf-8") as f:
            kayitli = json.load(f)
        for k in VARSAYILAN:
            if k in kayitli:
                ayar[k] = kayitli[k]
    except Exception:
        pass
    return ayar_temizle(ayar)


def ayar_kaydet(ayar):
    try:
        with open(AYAR_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(ayar, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_hex(r, g, b):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in (r, g, b))


def lerp(c1, c2, t):
    t = max(0.0, min(1.0, t))
    a, b = hex_rgb(c1), hex_rgb(c2)
    return rgb_hex(*(a[i] + (b[i] - a[i]) * t for i in range(3)))


# ------------------------- TUS KONUMLARI -------------------------
# Tusun fiziksel konumu (scan code'a gore; Turkce/Ingilizce Q duzeninde ayni calisir)
KONUM = {}
KONUM[1] = 0.5  # Esc
for _i, _sc in enumerate(range(59, 69)):  # F1-F10
    KONUM[_sc] = 2.5 + _i * 1.0 + (_i // 4) * 0.5
KONUM[87] = 12.5  # F11
KONUM[88] = 13.5  # F12
KONUM[41] = 0.5  # `
for _sc in range(2, 14):  # 1 2 3 ... - =
    KONUM[_sc] = 1.5 + (_sc - 2)
KONUM[14] = 14.0  # Backspace
KONUM[15] = 0.75  # Tab
for _sc in range(16, 28):  # Q W E ... [ ]
    KONUM[_sc] = 2.0 + (_sc - 16)
KONUM[28] = 14.0  # Enter
KONUM[58] = 0.9  # Caps
for _sc in range(30, 42):  # A S D ... ; '
    KONUM[_sc] = 2.25 + (_sc - 30)
KONUM[43] = 14.0
KONUM[42] = 1.1  # Sol Shift
KONUM[86] = 2.0  # < > tusu
for _sc in range(44, 54):  # Z X C ... . /
    KONUM[_sc] = 2.75 + (_sc - 44)
KONUM[54] = 13.0  # Sag Shift
KONUM[29] = 0.7  # Ctrl
KONUM[56] = 3.5  # Alt
KONUM[57] = 7.0  # Space
KONUM[75] = 15.5  # Sol ok
KONUM[80] = 16.5  # Asagi ok
KONUM[77] = 17.5  # Sag ok
KONUM[72] = 16.5  # Yukari ok


def bolge_bul(scan_code):
    x = KONUM.get(scan_code)
    if x is None:
        return None
    oran = (x - SOL_BOSLUK) / TOPLAM_GENISLIK
    return min(max(oran * BOLGE_SAYISI, 0), BOLGE_SAYISI - 1e-6)


def bekleme_rengi(ayar):
    """Bekleme isigi aciksa (R,G,B) float, kapaliysa siyah."""
    if not ayar.get("bekleme_acik"):
        return (0.0, 0.0, 0.0)
    r, g, b = hex_rgb(ayar["bekleme_renk"])
    k = max(0.0, min(1.0, float(ayar["bekleme_parlaklik"]) / 100.0))
    return (r * k, g * k, b * k)


def kare_hesapla(aktif, simdi, ayar):
    """Verilen dalgalar icin 8 bolgenin (R,G,B) degerlerini hesaplar."""
    n = BOLGE_SAYISI
    hiz = float(ayar["hiz"])
    kalinlik = max(MIN_KALINLIK, float(ayar["kalinlik"]))
    omur = max(0.05, float(ayar["omur"]))
    parlaklik = max(0.0, min(1.0, float(ayar["parlaklik"]) / 100.0))
    taban = bekleme_rengi(ayar)
    toplam = [list(taban) for _ in range(n)]
    for merkez, basla, (r, g, b) in aktif:
        yas = simdi - basla
        yaricap = yas * hiz
        sonum = math.exp(-yas / omur)
        for z in range(n):
            mesafe = abs((z + 0.5) - merkez)
            fark = abs(mesafe - yaricap)
            siddet = max(0.0, 1.0 - fark / kalinlik)
            if yas < 0.08 and mesafe < 0.8:  # basilan yer ilk anda parlasin
                siddet = 1.0
            v = siddet * sonum * parlaklik
            toplam[z][0] += r * v
            toplam[z][1] += g * v
            toplam[z][2] += b * v
    return tuple(
        (min(255, int(c[0])), min(255, int(c[1])), min(255, int(c[2]))) for c in toplam
    )


# ------------------------------ MOTOR ------------------------------
class Motor:
    """Tus dinler, dalgalari hesaplar, klavyeye gonderir (arka planda)."""

    def __init__(self, ayar):
        self.ayar = ayar
        self.kb = ApexKlavye()
        self.kilit = threading.Lock()
        self.dalgalar = []
        self.hue = 0.0
        self.durdur_ev = threading.Event()
        self.thread = None
        self._hook = None
        self.calisiyor = False
        self.durum = "Durdu"
        self.durum_hata = False

    def _renk_sec(self):
        if self.ayar["mod"] == "sabit":
            return hex_rgb(self.ayar["renk"])
        self.hue = (self.hue + 0.06) % 1.0
        r, g, b = colorsys.hsv_to_rgb(self.hue, 1.0, 1.0)
        return (int(r * 255), int(g * 255), int(b * 255))

    def _tus(self, olay):
        if olay.event_type != "down":
            return
        merkez = bolge_bul(olay.scan_code)
        if merkez is None:
            return
        with self.kilit:
            self.dalgalar.append((merkez, time.time(), self._renk_sec()))
            del self.dalgalar[: -max(1, int(self.ayar["max_dalga"]))]

    def baslat(self):
        if self.calisiyor:
            return True
        if not self.kb.baglan():
            self.durum = "Klavye bulunamadı. GG / OpenRGB kapalı mı?"
            self.durum_hata = True
            return False
        with self.kilit:
            self.dalgalar.clear()
        self.durdur_ev.clear()
        self._hook = keyboard.hook(self._tus)
        self.thread = threading.Thread(target=self._dongu, daemon=True)
        self.thread.start()
        self.calisiyor = True
        self.durum = "Çalışıyor"
        self.durum_hata = False
        return True

    def durdur(self):
        if not self.calisiyor:
            return
        self.durdur_ev.set()
        if self.thread is not None:
            self.thread.join(timeout=2)
        try:
            keyboard.unhook(self._hook)
        except Exception:
            pass
        self._hook = None
        try:
            self.kb.renk_gonder([(0, 0, 0)] * BOLGE_SAYISI)
        except Exception:
            pass
        self.kb.kapat()
        self.calisiyor = False
        self.durum = "Durdu"
        self.durum_hata = False

    def _dongu(self):
        son_gonderilen = None
        while not self.durdur_ev.is_set():
            t0 = time.time()
            aralik = 1.0 / max(5, int(self.ayar["fps"]))
            omur = max(0.05, float(self.ayar["omur"]))
            with self.kilit:
                self.dalgalar[:] = [d for d in self.dalgalar if t0 - d[1] < omur * 2.5]
                aktif = list(self.dalgalar)

            kare = kare_hesapla(aktif, t0, self.ayar)

            if kare != son_gonderilen:  # sadece isiklar degistiyse gonder
                if self.kb.renk_gonder(list(kare)):
                    son_gonderilen = kare
                    self.durum = "Çalışıyor"
                    self.durum_hata = False
                else:
                    self.durum = "Bağlantı koptu, yeniden deneniyor..."
                    self.durum_hata = True
                    son_gonderilen = None
                    self.durdur_ev.wait(0.5)

            gecen = time.time() - t0
            if gecen < aralik:
                self.durdur_ev.wait(aralik - gecen)


# ----------------------------- TASARIM -----------------------------
BG = "#0a0a12"
KART = "#13131f"
KENAR = "#232338"
TRACK = "#25253a"
DEVRE = "#3a3a52"
FG = "#eceaf8"
DIM = "#7c7a99"
C1 = "#00d4ff"   # camgobegi
C2 = "#8b5cff"   # mor
DUR1 = "#ff6b8a"
DUR2 = "#ff2d6f"
YESIL = "#3ddc97"
HATA = "#ff5d73"
FONT = "Segoe UI"

OLCEK = 1.0  # ekran olcegi (main icinde ayarlanir)


def px(v):
    return int(round(v * OLCEK))


def yuvarlak(c, x1, y1, x2, y2, r, **kw):
    """Yuvarlatilmis koseli dikdortgen (smooth polygon)."""
    pts = [
        x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1,
        x2, y1 + r, x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2,
        x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2, x1, y2,
        x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1,
    ]
    return c.create_polygon(pts, smooth=True, **kw)


def ikon_ciz(c, ad, cx, cy, s, renk, bg):
    """Vektor simgeler (resim dosyasi gerekmez)."""
    kal = max(1, px(2))
    if ad == "dalga":
        pts = []
        n = 24
        for i in range(n + 1):
            t = i / n
            pts += [cx - s + 2 * s * t, cy - s * 0.55 * math.sin(2 * math.pi * 1.5 * t)]
        c.create_line(*pts, smooth=True, width=kal, fill=renk, capstyle="round")
    elif ad == "hiz":
        rel = [(0.2, -1), (-0.6, 0.2), (-0.05, 0.2), (-0.2, 1), (0.6, -0.25), (0.05, -0.25)]
        pts = []
        for x, y in rel:
            pts += [cx + x * s * 0.95, cy + y * s * 0.95]
        c.create_polygon(*pts, fill=renk, outline="")
    elif ad == "kalinlik":
        for oy, hh in ((-0.7, 0.2), (0.0, 0.38), (0.75, 0.62)):
            y = cy + oy * s
            c.create_rectangle(cx - s, y - hh * s / 2, cx + s, y + hh * s / 2, fill=renk, outline="")
    elif ad == "parlaklik":
        r = s * 0.42
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=renk, outline="")
        for i in range(8):
            a = math.pi / 4 * i
            c.create_line(
                cx + math.cos(a) * s * 0.68, cy + math.sin(a) * s * 0.68,
                cx + math.cos(a) * s * 1.0, cy + math.sin(a) * s * 1.0,
                width=kal, fill=renk, capstyle="round",
            )
    elif ad == "ay":
        r = s * 0.85
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=renk, outline="")
        r2 = s * 0.72
        ox, oy = cx + s * 0.5, cy - s * 0.3
        c.create_oval(ox - r2, oy - r2, ox + r2, oy + r2, fill=bg, outline="")
    elif ad == "renk":
        r = s * 0.95
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=renk, width=kal)
        for a in (-math.pi / 2, math.pi / 6, 5 * math.pi / 6):
            dx, dy = cx + math.cos(a) * s * 0.5, cy + math.sin(a) * s * 0.5
            rr = s * 0.17
            c.create_oval(dx - rr, dy - rr, dx + rr, dy + rr, fill=renk, outline="")
    elif ad == "klavye":
        c.create_rectangle(cx - s, cy - s * 0.6, cx + s, cy + s * 0.6, outline=renk, width=kal)
        for row in (-0.25, 0.25):
            for col in (-0.55, 0.0, 0.55):
                kx, ky = cx + col * s, cy + row * s
                q = s * 0.12
                c.create_rectangle(kx - q, ky - q, kx + q, ky + q, fill=renk, outline="")
    elif ad == "oynat":
        c.create_polygon(cx - s * 0.55, cy - s * 0.8, cx + s * 0.8, cy, cx - s * 0.55, cy + s * 0.8,
                         fill=renk, outline="")
    elif ad == "durdur":
        q = s * 0.65
        c.create_rectangle(cx - q, cy - q, cx + q, cy + q, fill=renk, outline="")


class Ikon(tk.Canvas):
    def __init__(self, ebeveyn, ad, renk, bg, boyut=22):
        b = px(boyut)
        super().__init__(ebeveyn, width=b, height=b, bg=bg, highlightthickness=0, bd=0)
        ikon_ciz(self, ad, b / 2, b / 2, b * 0.38, renk, bg)


class Baslik(tk.Canvas):
    """Ust kisim: rozet + gradyan 'DALGA' + surum."""

    def __init__(self, ebeveyn, bg):
        super().__init__(ebeveyn, height=px(98), bg=bg, highlightthickness=0, bd=0)
        self.bind("<Configure>", lambda e: self.ciz())

    def ciz(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 2:
            return
        pad = px(22)
        b = px(52)
        cy = px(40)
        self.create_oval(pad, cy - b / 2, pad + b, cy + b / 2, fill=KART, outline=C1, width=2)
        self.create_oval(pad + px(4), cy - b / 2 + px(4), pad + b - px(4), cy + b / 2 - px(4),
                         fill=KART, outline=C2, width=1)
        ikon_ciz(self, "dalga", pad + b / 2, cy, b * 0.27, C1, KART)

        font = tkfont.Font(family=FONT, size=30, weight="bold")
        x = pad + b + px(16)
        for i, ch in enumerate("DALGA"):
            self.create_text(x, cy, text=ch, font=font, fill=lerp(C1, C2, i / 4), anchor="w")
            x += font.measure(ch)
        asc = font.metrics("ascent")
        desc = font.metrics("descent")
        taban = cy + (asc - desc) / 2
        self.create_text(x + px(8), taban, text=SURUM, font=(FONT, 11), fill=DIM, anchor="sw")
        self.create_text(pad, px(84), text="Her tuşa bastığında ışık dalgası yayılır",
                         font=(FONT, 9), fill=DIM, anchor="w")
        self.create_line(pad, h - 1, w - pad, h - 1, fill=KENAR)


class Kaydirici(tk.Canvas):
    """Gradyan dolgulu, parlayan topuzlu kaydirici."""

    def __init__(self, ebeveyn, alt, ust, adim, deger, komut, bg):
        super().__init__(ebeveyn, height=px(30), bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.alt, self.ust, self.adim = alt, ust, adim
        self.deger = deger
        self.komut = komut
        self.bgc = bg
        self.aktif = True
        self.bind("<Configure>", lambda e: self.ciz())
        self.bind("<Button-1>", self._tikla)
        self.bind("<B1-Motion>", self._tikla)

    def ciz(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 2:
            return
        k = px(12)
        y = h / 2
        kal = px(6)
        x0, x1 = k, w - k
        oran = (self.deger - self.alt) / float(self.ust - self.alt)
        oran = max(0.0, min(1.0, oran))
        xv = x0 + (x1 - x0) * oran
        c1, c2 = (C1, C2) if self.aktif else (DEVRE, DEVRE)

        self.create_line(x0, y, x1, y, width=kal, capstyle="round", fill=TRACK)
        if xv > x0 + 1:
            n = max(2, int((xv - x0) / px(5)))
            for i in range(n):
                a = x0 + (xv - x0) * i / n
                b = x0 + (xv - x0) * (i + 1) / n
                self.create_line(a, y, b + 1, y, width=kal, fill=lerp(c1, c2, (i + 0.5) / n))
            self.create_oval(x0 - kal / 2, y - kal / 2, x0 + kal / 2, y + kal / 2, fill=c1, outline="")
        r = px(9)
        topuz = lerp(c1, c2, oran)
        self.create_oval(xv - r - px(4), y - r - px(4), xv + r + px(4), y + r + px(4),
                         fill=lerp(self.bgc, topuz, 0.22), outline="")
        self.create_oval(xv - r, y - r, xv + r, y + r, fill="#ffffff" if self.aktif else "#9a9ab0",
                         outline=topuz, width=2)

    def _tikla(self, e):
        if not self.aktif:
            return
        w = self.winfo_width()
        k = px(12)
        oran = (e.x - k) / float(max(1, w - 2 * k))
        oran = max(0.0, min(1.0, oran))
        ham = self.alt + oran * (self.ust - self.alt)
        v = self.alt + round((ham - self.alt) / self.adim) * self.adim
        v = round(max(self.alt, min(self.ust, v)), 2)
        if v != self.deger:
            self.deger = v
            self.ciz()
            self.komut(v)


class Anahtar(tk.Canvas):
    """Ac/kapa anahtari."""

    def __init__(self, ebeveyn, deger, komut, bg):
        self.gen, self.yuk = px(48), px(26)
        super().__init__(ebeveyn, width=self.gen, height=self.yuk, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.deger = bool(deger)
        self.komut = komut
        self.bind("<Button-1>", self._tikla)
        self.ciz()

    def ciz(self):
        self.delete("all")
        w, h = self.gen, self.yuk
        if self.deger:
            # gradyan kapsul
            self.create_oval(0, 0, h, h, fill=C1, outline="")
            self.create_oval(w - h, 0, w, h, fill=C2, outline="")
            x, xe = int(h / 2), int(w - h / 2)
            for i in range(x, xe, 2):
                self.create_line(i, 0, i, h, fill=lerp(C1, C2, (i - x) / max(1, xe - x)), width=3)
        else:
            yuvarlak(self, 0, 0, w, h, h / 2, fill=TRACK, outline="")
        r = h / 2 - px(3)
        kx = w - h / 2 if self.deger else h / 2
        self.create_oval(kx - r, h / 2 - r, kx + r, h / 2 + r,
                         fill="#ffffff" if self.deger else "#8a8aa6", outline="")

    def _tikla(self, e):
        self.deger = not self.deger
        self.ciz()
        self.komut(self.deger)


class Segment(tk.Canvas):
    """Iki secenekli kapsul secici."""

    def __init__(self, ebeveyn, secenekler, secili, komut, bg):
        super().__init__(ebeveyn, height=px(38), bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.secenekler = secenekler
        self.secili = secili
        self.komut = komut
        self.bind("<Configure>", lambda e: self.ciz())
        self.bind("<Button-1>", self._tikla)

    def ciz(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 2:
            return
        yuvarlak(self, 0, 0, w, h, h / 2, fill=TRACK, outline="")
        n = len(self.secenekler)
        pw = w / float(n)
        for i, (metin, deger) in enumerate(self.secenekler):
            x1, x2 = i * pw + px(3), (i + 1) * pw - px(3)
            sec = deger == self.secili
            if sec:
                yuvarlak(self, x1, px(3), x2, h - px(3), (h - px(6)) / 2,
                         fill=lerp(C1, C2, 0.2 + 0.6 * (i / max(1, n - 1))), outline="")
            self.create_text((x1 + x2) / 2, h / 2, text=metin, font=(FONT, 10, "bold"),
                             fill="#ffffff" if sec else DIM)

    def _tikla(self, e):
        w = max(1, self.winfo_width())
        i = max(0, min(len(self.secenekler) - 1, int(e.x / (w / float(len(self.secenekler))))))
        deger = self.secenekler[i][1]
        if deger != self.secili:
            self.secili = deger
            self.ciz()
            self.komut(deger)


class Dugme(tk.Canvas):
    """Gradyan kapsul dugme (istege bagli simgeli)."""

    def __init__(self, ebeveyn, metin, komut, bg, c1, c2, yukseklik=46, genislik=None,
                 ikon=None, font=None, yazi="#ffffff"):
        kw = {"width": px(genislik)} if genislik else {}
        super().__init__(ebeveyn, height=px(yukseklik), bg=bg, highlightthickness=0, bd=0,
                         cursor="hand2", **kw)
        self.metin, self.komut, self.bgc = metin, komut, bg
        self.c1, self.c2, self.ikon = c1, c2, ikon
        self.font = font or (FONT, 12, "bold")
        self.yazi = yazi
        self.hover = False
        self.aktif = True
        self.bind("<Configure>", lambda e: self.ciz())
        self.bind("<Enter>", self._gir)
        self.bind("<Leave>", self._cik)
        self.bind("<Button-1>", self._tikla)

    def ayarla(self, metin=None, c1=None, c2=None, ikon=None):
        if metin is not None:
            self.metin = metin
        if c1 is not None:
            self.c1 = c1
        if c2 is not None:
            self.c2 = c2
        if ikon is not None:
            self.ikon = ikon
        self.ciz()

    def ciz(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 2:
            return
        c1, c2 = self.c1, self.c2
        if not self.aktif:
            c1 = c2 = DEVRE
        elif self.hover:
            c1, c2 = lerp(c1, "#ffffff", 0.14), lerp(c2, "#ffffff", 0.14)
        self.create_oval(0, 0, h, h, fill=c1, outline="")
        self.create_oval(w - h, 0, w, h, fill=c2, outline="")
        x, xe = int(h / 2), int(w - h / 2)
        span = max(1, xe - x)
        for i in range(x, xe, 2):
            self.create_line(i, 0, i, h, fill=lerp(c1, c2, (i - x) / span), width=3)

        yazi = self.yazi if self.aktif else "#7a7a92"
        tw = tkfont.Font(font=self.font).measure(self.metin)
        s = px(8)
        bosluk = px(10)
        toplam = tw + (2 * s + bosluk if self.ikon else 0)
        bx = (w - toplam) / 2
        if self.ikon:
            ikon_ciz(self, self.ikon, bx + s, h / 2, s, yazi, c1)
            bx += 2 * s + bosluk
        self.create_text(bx, h / 2, text=self.metin, font=self.font, fill=yazi, anchor="w")

    def _gir(self, e):
        self.hover = True
        self.ciz()

    def _cik(self, e):
        self.hover = False
        self.ciz()

    def _tikla(self, e):
        if self.aktif and self.komut:
            self.komut()


class Ornek(tk.Canvas):
    """Renk ornegi (yuvarlak). Gokkusagi modunda gokkusagi diski gosterir."""

    def __init__(self, ebeveyn, renk, komut, bg, boyut=36):
        self.b = px(boyut)
        super().__init__(ebeveyn, width=self.b, height=self.b, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.renk, self.komut = renk, komut
        self.gokkusagi = False
        self.aktif = True
        self.bind("<Button-1>", self._tikla)
        self.ciz()

    def ciz(self):
        self.delete("all")
        b, m = self.b, px(4)
        if self.gokkusagi:
            for i in range(12):
                r, g, bl = colorsys.hsv_to_rgb(i / 12.0, 1.0, 1.0)
                self.create_arc(m, m, b - m, b - m, start=i * 30, extent=30,
                                fill=rgb_hex(r * 255, g * 255, bl * 255), outline="")
        else:
            self.create_oval(m, m, b - m, b - m, fill=self.renk if self.aktif else DEVRE, outline="")
        self.create_oval(1, 1, b - 1, b - 1, outline="#3a3a58", width=2)

    def _tikla(self, e):
        if self.aktif and not self.gokkusagi and self.komut:
            self.komut()


# ----------------------------- ARAYUZ -----------------------------
class Uygulama:
    def __init__(self, root):
        self.root = root
        self.ayar = ayar_yukle()
        self.motor = Motor(self.ayar)
        self._kayit_zamanlayici = None

        root.title(f"DALGA {SURUM}")
        root.configure(bg=BG)
        root.resizable(False, False)

        Baslik(root, BG).pack(fill="x")

        govde = tk.Frame(root, bg=BG)
        govde.pack(fill="both", expand=True, padx=px(20), pady=(px(14), px(20)))
        govde.columnconfigure(0, weight=1, uniform="k")
        govde.columnconfigure(1, weight=1, uniform="k")
        sol = tk.Frame(govde, bg=BG)
        sol.grid(row=0, column=0, sticky="nsew", padx=(0, px(9)))
        sag = tk.Frame(govde, bg=BG)
        sag.grid(row=0, column=1, sticky="nsew", padx=(px(9), 0))

        # ===== SOL: efekt karti + baslat =====
        k1 = self._kart(sol, "EFEKT")
        self._kaydirici_satiri(k1, "hiz", "Hız", "hiz", 2, 20, 0.5,
                               lambda v: f"{float(v):.1f}", False)
        self._kaydirici_satiri(k1, "kalinlik", "Kalınlık", "kalinlik", MIN_KALINLIK, 4.0, 0.1,
                               lambda v: f"{float(v):.1f}", False)
        self._kaydirici_satiri(k1, "parlaklik", "Parlaklık", "parlaklik", 5, 100, 1,
                               lambda v: f"%{int(float(v))}", True)
        tk.Frame(k1, height=px(14), bg=KART).pack()

        self.ana = Dugme(sol, "BAŞLAT", self._ac_kapat, BG, C1, C2, yukseklik=54, ikon="oynat")
        self.ana.pack(fill="x", pady=(px(16), 0))

        durum_satiri = tk.Frame(sol, bg=BG)
        durum_satiri.pack(fill="x", pady=(px(12), 0))
        Ikon(durum_satiri, "klavye", DIM, BG, boyut=20).pack(side="left")
        self.nokta = tk.Label(durum_satiri, text="●", font=(FONT, 9), fg=DIM, bg=BG)
        self.nokta.pack(side="left", padx=(px(8), px(2)))
        self.durum = tk.Label(durum_satiri, text="Durdu", font=(FONT, 9), fg=DIM, bg=BG)
        self.durum.pack(side="left")

        # ===== SAG: renk karti + bekleme karti =====
        k2 = self._kart(sag, "RENK")
        satir = tk.Frame(k2, bg=KART)
        satir.pack(fill="x", padx=px(16), pady=(px(10), 0))
        Ikon(satir, "renk", C1, KART).pack(side="left")
        tk.Label(satir, text="Dalga rengi", font=(FONT, 10, "bold"), fg=FG, bg=KART).pack(
            side="left", padx=(px(8), 0))
        self.segment = Segment(
            k2, [("Gökkuşağı", "gokkusagi"), ("Sabit renk", "sabit")],
            self.ayar["mod"], self._mod_degisti, KART)
        self.segment.pack(fill="x", padx=px(16), pady=(px(10), 0))
        renk_satir = tk.Frame(k2, bg=KART)
        renk_satir.pack(fill="x", padx=px(16), pady=(px(12), px(16)))
        self.ornek = Ornek(renk_satir, self.ayar["renk"], self._renk_sec, KART)
        self.ornek.pack(side="left")
        self.renk_dugme = Dugme(renk_satir, "Renk seç", self._renk_sec, KART, TRACK, TRACK,
                                yukseklik=34, genislik=110, font=(FONT, 10, "bold"), yazi=FG)
        self.renk_dugme.pack(side="left", padx=(px(12), 0))

        k3 = self._kart(sag, "BEKLEME IŞIĞI", ust_bosluk=px(16))
        satir = tk.Frame(k3, bg=KART)
        satir.pack(fill="x", padx=px(16), pady=(px(10), 0))
        Ikon(satir, "ay", C2, KART).pack(side="left")
        tk.Label(satir, text="Bekleme ışığı", font=(FONT, 10, "bold"), fg=FG, bg=KART).pack(
            side="left", padx=(px(8), 0))
        self.bek_anahtar = Anahtar(satir, self.ayar["bekleme_acik"], self._bek_ac, KART)
        self.bek_anahtar.pack(side="right")
        bek_satir = tk.Frame(k3, bg=KART)
        bek_satir.pack(fill="x", padx=px(16), pady=(px(12), 0))
        self.bek_ornek = Ornek(bek_satir, self.ayar["bekleme_renk"], self._bek_renk_sec, KART)
        self.bek_ornek.pack(side="left")
        self.bek_dugme = Dugme(bek_satir, "Renk seç", self._bek_renk_sec, KART, TRACK, TRACK,
                               yukseklik=34, genislik=110, font=(FONT, 10, "bold"), yazi=FG)
        self.bek_dugme.pack(side="left", padx=(px(12), 0))
        self.bek_slider, _ = self._kaydirici_satiri(
            k3, "parlaklik", "Parlaklık", "bekleme_parlaklik", 1, 100, 1,
            lambda v: f"%{int(float(v))}", True)
        tk.Frame(k3, height=px(14), bg=KART).pack()

        self._gorunum_senkron()

        root.update_idletasks()
        root.geometry(f"{px(780)}x{root.winfo_reqheight()}")
        root.protocol("WM_DELETE_WINDOW", self._kapat)
        self._durum_guncelle()

    # --- yapi tasi ---
    def _kart(self, ebeveyn, baslik, ust_bosluk=0):
        kart = tk.Frame(ebeveyn, bg=KART, highlightbackground=KENAR, highlightcolor=KENAR,
                        highlightthickness=1)
        kart.pack(fill="x", pady=(ust_bosluk, 0))
        tk.Label(kart, text=baslik, font=(FONT, 8, "bold"), fg=DIM, bg=KART, anchor="w").pack(
            fill="x", padx=px(16), pady=(px(12), 0))
        return kart

    def _kaydirici_satiri(self, kart, ikon_ad, ad, anahtar, alt, ust, adim, bicim, tamsayi):
        cerceve = tk.Frame(kart, bg=KART)
        cerceve.pack(fill="x", padx=px(16), pady=(px(10), 0))
        ust_satir = tk.Frame(cerceve, bg=KART)
        ust_satir.pack(fill="x")
        Ikon(ust_satir, ikon_ad, C1, KART).pack(side="left")
        tk.Label(ust_satir, text=ad, font=(FONT, 10, "bold"), fg=FG, bg=KART).pack(
            side="left", padx=(px(8), 0))
        deger = tk.Label(ust_satir, text=bicim(self.ayar[anahtar]), font=(FONT, 10, "bold"),
                         fg=C1, bg=KART)
        deger.pack(side="right")

        def degisti(v):
            v = int(round(v)) if tamsayi else round(float(v), 2)
            self.ayar[anahtar] = v
            deger.config(text=bicim(v))
            self._kaydet_planla()

        k = Kaydirici(cerceve, alt, ust, adim, self.ayar[anahtar], degisti, KART)
        k.pack(fill="x", pady=(px(2), 0))
        return k, deger

    # --- gorunum / olaylar ---
    def _gorunum_senkron(self):
        sabit = self.ayar["mod"] == "sabit"
        self.ornek.gokkusagi = not sabit
        self.ornek.renk = self.ayar["renk"]
        self.ornek.ciz()
        self.renk_dugme.aktif = sabit
        self.renk_dugme.ciz()
        acik = self.ayar["bekleme_acik"]
        self.bek_ornek.aktif = acik
        self.bek_ornek.renk = self.ayar["bekleme_renk"]
        self.bek_ornek.ciz()
        self.bek_dugme.aktif = acik
        self.bek_dugme.ciz()
        self.bek_slider.aktif = acik
        self.bek_slider.ciz()

    def _kaydet_planla(self):
        if self._kayit_zamanlayici is not None:
            self.root.after_cancel(self._kayit_zamanlayici)
        self._kayit_zamanlayici = self.root.after(400, lambda: ayar_kaydet(self.ayar))

    def _mod_degisti(self, deger):
        self.ayar["mod"] = deger
        self._gorunum_senkron()
        self._kaydet_planla()

    def _renk_sec(self):
        sonuc = colorchooser.askcolor(color=self.ayar["renk"], title="Dalga rengi")
        if sonuc and sonuc[1]:
            self.ayar["renk"] = sonuc[1]
            self._gorunum_senkron()
            self._kaydet_planla()

    def _bek_ac(self, deger):
        self.ayar["bekleme_acik"] = bool(deger)
        self._gorunum_senkron()
        self._kaydet_planla()

    def _bek_renk_sec(self):
        if not self.ayar["bekleme_acik"]:
            return
        sonuc = colorchooser.askcolor(color=self.ayar["bekleme_renk"], title="Bekleme ışığı rengi")
        if sonuc and sonuc[1]:
            self.ayar["bekleme_renk"] = sonuc[1]
            self._gorunum_senkron()
            self._kaydet_planla()

    def _ac_kapat(self):
        if self.motor.calisiyor:
            self.motor.durdur()
        else:
            self.motor.baslat()
        if self.motor.calisiyor:
            self.ana.ayarla(metin="DURDUR", c1=DUR1, c2=DUR2, ikon="durdur")
        else:
            self.ana.ayarla(metin="BAŞLAT", c1=C1, c2=C2, ikon="oynat")

    def _durum_guncelle(self):
        if self.motor.durum_hata:
            renk = HATA
        elif self.motor.calisiyor:
            renk = YESIL
        else:
            renk = DIM
        self.nokta.config(fg=renk)
        self.durum.config(text=self.motor.durum, fg=HATA if self.motor.durum_hata else FG if self.motor.calisiyor else DIM)
        self.root.after(500, self._durum_guncelle)

    def _kapat(self):
        try:
            self.motor.durdur()
        finally:
            ayar_kaydet(self.ayar)
            self.root.destroy()


def main():
    global OLCEK
    try:  # net (bulanik olmayan) yazi icin Windows DPI farkindaligi
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    OLCEK = root.winfo_fpixels("1i") / 96.0
    Uygulama(root)
    root.mainloop()


if __name__ == "__main__":
    main()