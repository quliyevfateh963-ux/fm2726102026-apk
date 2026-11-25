import pygame
import sys
import random
import os
import json
import unicodedata
transfer_index = 0
transfer_sekme = "AL"

# --- SİSTEM AYARLARI ---
transfer_finans_kilidi = False  # [YENI] Transfer mali hareketlerinin cift sayilmasini onler
pygame.init()
WIDTH, HEIGHT = 1280, 720 
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED | pygame.FULLSCREEN)
pygame.display.set_caption("FM 2027 - Ultimate Manager")

# --- KLAVYE GEZİNTİSİ / KEYBOARD NAVIGATION ---
last_input_method = "mouse"
focused_index = 0
focusable_items = []
_focus_context = None
_focus_frame_context = None
_focus_frame_items = []
_focus_pending = None
_focus_frame_interrupted = False
_focus_directions = {
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1),
    pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0),
    pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
}
_focus_confirm_keys = {pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER}


def _focus_reset(context=None):
    global focused_index, focusable_items, _focus_context, _focus_pending
    focused_index = 0
    focusable_items = []
    _focus_context = context
    _focus_pending = None


def _focus_begin_frame(context):
    global _focus_frame_context, _focus_frame_interrupted
    if context != _focus_context:
        _focus_reset(context)
    _focus_frame_context = context
    _focus_frame_interrupted = False
    _focus_frame_items.clear()


def register_button(rect, action):
    """Register the drawn hitbox and its keyboard activation callback."""
    _focus_frame_items.append((rect.copy(), action))


def _focus_publish(context):
    global focused_index, focusable_items, _focus_pending
    # A queued activation is valid for one draw pass only. A changing view may
    # still be drawing its old buttons, so don't expose that mixed frame.
    _focus_pending = None
    if _focus_frame_interrupted or context != _focus_frame_context:
        _focus_reset()
        return
    old_rect = focusable_items[focused_index][0] if focusable_items else None
    focusable_items = _focus_frame_items[:]
    focused_index = next((i for i, (rect, _) in enumerate(focusable_items)
                          if rect == old_rect), 0)


def _focus_polled_click(rect, mouse_clicked):
    """Let the existing inline click branch handle a one-shot activation."""
    global _focus_pending
    token = (_focus_frame_context, tuple(rect))

    def queue_click():
        global _focus_pending
        _focus_pending = token

    register_button(rect, queue_click)
    keyboard_clicked = _focus_pending == token
    if keyboard_clicked:
        _focus_pending = None
    return mouse_clicked or keyboard_clicked


def _focus_event_button(rect):
    # Event-driven controls get a private click at the center, not a posted
    # mouse event: no pointer warp, mouse-mode switch, or cross-screen click.
    register_button(rect, lambda: pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1))


def handle_keyboard_input(event, text_entry=False, can_activate=True):
    global last_input_method, focused_index
    direction = _focus_directions.get(event.key)
    if direction is None and event.key not in _focus_confirm_keys:
        return None
    last_input_method = "keyboard"
    if text_entry or not focusable_items:
        return None

    if direction is not None:
        cx, cy = focusable_items[focused_index][0].center
        dx, dy = direction
        candidates = []
        for i, (rect, _) in enumerate(focusable_items):
            rx, ry = rect.centerx - cx, rect.centery - cy
            forward = rx * dx + ry * dy
            if forward > 0:
                # Prefer the same column/row, then the closest in that direction.
                candidates.append((abs(rx * dy - ry * dx), forward, i))
        if candidates:
            focused_index = min(candidates)[2]
    elif can_activate and not getattr(event, "repeat", False):
        return focusable_items[focused_index][1]()
    return None


def _focus_events(text_entry=None, events=None):
    global last_input_method, _focus_pending
    activated = False
    for event in pygame.event.get() if events is None else events:
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION):
            last_input_method = "mouse"
            if event.type == pygame.MOUSEBUTTONDOWN:
                _focus_pending = None
        elif event.type == pygame.KEYDOWN:
            typing = text_entry is not None and text_entry()
            synthetic_click = handle_keyboard_input(event, typing, not activated)
            if synthetic_click is not None:
                activated = True
                yield synthetic_click
                continue
            if _focus_pending is not None:
                activated = True
        yield event


def _focus_open_screen(action, *args):
    # A nested screen owns its own focus and cannot leave a queued click in
    # the caller. The caller will rebuild and start at index 0 on its next frame.
    global _focus_frame_context, _focus_frame_interrupted
    context = _focus_frame_context
    _focus_reset()
    try:
        return action(*args)
    finally:
        _focus_reset()
        _focus_frame_context = context
        _focus_frame_interrupted = True
        _focus_frame_items.clear()


def draw_focus_indicator(surface):
    if last_input_method != "keyboard" or not focusable_items:
        return
    rect = focusable_items[focused_index][0]
    padded = rect.inflate(4, 4)
    size = min(rect.size)
    inward = max(10, min(14, size // 5))
    outward = max(6, min(8, size // 12))
    for x, dx in ((padded.left, 1), (padded.right - 1, -1)):
        for y, dy in ((padded.top, 1), (padded.bottom - 1, -1)):
            pygame.draw.line(surface, (255, 255, 255), (x - dx * outward, y),
                             (x + dx * inward, y), 2)
            pygame.draw.line(surface, (255, 255, 255), (x, y - dy * outward),
                             (x, y + dy * inward), 2)


# Renkler
ARKA_PLAN = (20, 30, 48); SAHA_YESILI = (34, 139, 34); BEYAZ = (255, 255, 255)
ALTIN = (255, 215, 0); BUTON_RENGI = (44, 62, 80); MAVI = (52, 152, 219)
YESIL = (46, 204, 113); KIRMIZI = (231, 76, 60); SIYAH = (0, 0, 0)

# Fontlar
font_baslik = pygame.font.SysFont("Arial", 40, bold=True)
font_buton = pygame.font.SysFont("Arial", 32, bold=True)
font_liste = pygame.font.SysFont("Courier New", 22, bold=True)
font_oyuncu = pygame.font.SysFont("Arial", 18, bold=True)
font_skor = pygame.font.SysFont("Arial", 100, bold=True)
font_log = pygame.font.SysFont("Arial", 22, bold=True)
font_agac = pygame.font.SysFont("Arial", 14, bold=True)  # [YENI EKLENEN] UCL turnuva agaci icin kucuk font

# --- [YENI] MEVKI UYUMLULUGU / POSITION COMPATIBILITY ---------------------
# Renkler TEK kaynaktan: hem sahadaki "!" rozeti hem asagidaki lejand
# bu sabitleri kullanir, boylece birbirinden ayrisamazlar.
UYARI_KIRMIZI = (200, 30, 30)     # "!" rozetinin dolgusu (saha ile ayni)
UYARI_HALKA = (255, 255, 255)     # "!" rozetinin halkasi (saha ile ayni)
UYARI_FONT_MIN = 14               # rozetteki "!" icin en kucuk punto

NATURAL_POSITIONS = {
    "KL":  {"KL"},
    "CB":  {"CB"},
    "LB":  {"LB", "CB"},
    "RB":  {"RB", "CB"},
    "MDO": {"MDO", "MO"},
    "MO":  {"MO", "MDO", "MOO"},
    "MOO": {"MOO", "MO", "LW", "RW"},
    "LW":  {"LW", "MOO", "ST"},
    "RW":  {"RW", "MOO", "ST"},
    "ST":  {"ST", "MOO", "LW", "RW"},
}


# --- [YENI] COKLU MEVKI / MULTI-POSITION ----------------------------------
# Her oyuncunun bir ESAS mevkisi ("mevki") ve istege bagli DIGER mevkileri
# ("diger_mevkiler", liste) vardir. Ornek: mevki="RW", diger_mevkiler=["LW", "RB"]
# Slot, esas mevkiye veya diger mevkilerden birine uyuyorsa "!" cikmaz.
#
# Bir oyuncuya elle mevki vermek icin:
#   1) Oyuncu sozlugune ekle:  {"isim": "...", "mevki": "RW", "diger_mevkiler": ["LW", "RB"], ...}
#   2) veya asagidaki OYUNCU_DIGER_MEVKILERI tablosuna ismini yaz.
# "diger_mevkiler" anahtari olmayan oyuncular (eski kayitlar dahil) otomatik
# olarak mantikli bir liste alir ve bu liste oyuncuyla birlikte kaydedilir.
import zlib

GECERLI_MEVKILER = {"KL", "CB", "LB", "RB", "MDO", "MO", "MOO", "LW", "RW", "ST"}

# Elle belirlenen oyuncular (isim -> diger mevkiler). Istedigin kadar ekle.
OYUNCU_DIGER_MEVKILERI = {
    "L.Sane": ["LW", "RB"],
    "B.Yılmaz": ["LW"],
    "Y.Akgün": ["LW"],
    "R.Sallai": ["RW", "LB"],
    "W.Singo": ["RW"],
    "M.Greenwood": ["LW", "ST"],
}

# Esas mevkiye gore olasi ek mevkiler (zaten "dogal" sayilanlar haric)
DIGER_MEVKI_ADAYLARI = {
    "KL":  [],
    "CB":  ["RB", "LB", "MDO"],
    "LB":  ["RB", "LW", "MDO"],
    "RB":  ["LB", "RW", "MDO"],
    "MDO": ["CB", "RB", "LB"],
    "MO":  ["LW", "RW"],
    "MOO": ["MDO"],
    "LW":  ["RW", "LB", "MO"],
    "RW":  ["LW", "RB", "MO"],
    "ST":  ["MO"],
}


def _diger_mevkileri_uret(player):
    """Oyuncu icin sabit (her calistirmada ayni) mantikli ek mevkiler uretir."""
    esas = player.get("mevki")
    adaylar = DIGER_MEVKI_ADAYLARI.get(esas, [])
    if not adaylar:
        return []
    h = zlib.crc32(str(player.get("isim", "")).encode("utf-8"))
    sayi = 0 if h % 100 < 55 else (1 if h % 100 < 85 else 2)
    sayi = min(sayi, len(adaylar))
    kopya = list(adaylar)
    secilen = []
    for _ in range(sayi):
        secilen.append(kopya.pop((h // 100) % len(kopya)))
        h //= 7
    return secilen


def diger_mevkiler_getir(player):
    """Oyuncunun diger mevkilerini doner (liste). Eksikse olusturup oyuncuya yazar."""
    if not isinstance(player, dict):
        return []
    liste = player.get("diger_mevkiler")
    if not isinstance(liste, list):
        liste = OYUNCU_DIGER_MEVKILERI.get(player.get("isim"))
        liste = list(liste) if liste is not None else _diger_mevkileri_uret(player)
        player["diger_mevkiler"] = liste
    return liste


def can_play_position(player, slot_position):
    """True: slot esas mevki veya diger mevkilerden biri (uyari yok)."""
    if not player or not slot_position:
        return True
    esas = player.get("mevki")
    natural = NATURAL_POSITIONS.get(esas, {esas})
    return slot_position in natural or slot_position in diger_mevkiler_getir(player)


def is_natural_position(player, slot_position):
    """True if player can play slot_position without a warning."""
    return can_play_position(player, slot_position)


_UYARI_FONT_CACHE = {}


def _uyari_font_getir(boyut):
    """[YENI] '!' fontunu boyuta gore onbellekler (her karede SysFont cagirmamak icin)."""
    f = _UYARI_FONT_CACHE.get(boyut)
    if f is None:
        f = pygame.font.SysFont("Arial", boyut, bold=True)
        _UYARI_FONT_CACHE[boyut] = f
    return f


def draw_position_warning(surface, center, radius):
    """Draw a red '!' badge at the bottom-right of a player circle."""
    cx, cy = center
    # sit the badge on the bottom-right edge of the circle
    wx = int(cx + radius * 0.72)
    wy = int(cy + radius * 0.72)
    # badge size scales with the circle; tune 0.55 if you want bigger/smaller
    badge_r = max(9, int(radius * 0.55))
    # red disc + white ring, then the '!' on top
    pygame.draw.circle(surface, UYARI_KIRMIZI, (wx, wy), badge_r)
    pygame.draw.circle(surface, UYARI_HALKA, (wx, wy), badge_r, 2)
    f = _uyari_font_getir(max(UYARI_FONT_MIN, int(badge_r * 1.7)))
    txt = f.render("!", True, UYARI_HALKA)
    surface.blit(txt, txt.get_rect(center=(wx, wy)))


# Slot mevki kodlari: dizilis adi -> 11 slotun MEVKI kodu (sadece mevcut kodlar)
DIZILIS_SLOT_MEVKILERI = {
    "4-3-3": ["KL", "LB", "CB", "CB", "RB", "MO", "MDO", "MO", "LW", "ST", "RW"],
    "4-4-2": ["KL", "LB", "CB", "CB", "RB", "LW", "MO", "MO", "RW", "ST", "ST"],
    "3-5-2": ["KL", "CB", "CB", "CB", "LB", "MO", "MDO", "MO", "RB", "ST", "ST"],
}
DIZILIS_SIRA = ("4-3-3", "4-4-2", "3-5-2")


def _dizilis_slot_mevkisi(dizilis, index):
    """dizilis: ad ("4-3-3") veya indeks (0/1/2). Slotun mevki kodunu doner."""
    if isinstance(dizilis, int):
        kodlar = DIZILIS_SLOT_MEVKILERI[DIZILIS_SIRA[dizilis % len(DIZILIS_SIRA)]]
    else:
        kodlar = DIZILIS_SLOT_MEVKILERI.get(dizilis) or DIZILIS_SLOT_MEVKILERI["4-3-3"]
    if 0 <= index < len(kodlar):
        return kodlar[index]
    return None


# --- [YENI] EN IYI ILK 11 (UNLEMSIZ) / BEST XI WITHOUT "!" -----------------
# Hem rakip takimin maca cikacagi kadro hem de kadro ekranindaki "OTO DIZ"
# bu fonksiyonlari kullanir. Her slot icin can_play_position() ile uyumlu
# (unlemsiz) oyuncu secilir; toplam yetenek en yuksek olacak sekilde.
UNLEM_CEZASI = 1000     # mevki disi oyuncu: neredeyse hic secilmesin
SAKAT_CEZASI = 5000     # sakat oyuncu: sadece baska care yoksa secilsin
ESAS_MEVKI_BONUS = 3    # esit durumda esas mevkisinde oynayan tercih edilir


def _minimum_maliyet_atama(c):
    """Macar algoritmasi. c: n x m (n <= m). Her satira bir sutun doner."""
    n, m = len(c), len(c[0])
    INF = float("inf")
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    p = [0] * (m + 1)
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = INF
            j1 = 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = c[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    atama = [None] * n
    for j in range(1, m + 1):
        if p[j]:
            atama[p[j] - 1] = j - 1
    return atama


def en_iyi_ilk11_kur(oyuncular, formasyon):
    """Verilen dizilis icin en iyi ilk 11'i slot sirasinda doner:
    (ilk11_listesi, unlem_sayisi, toplam_yetenek). 11 oyuncu yoksa None."""
    oyuncular = list(oyuncular)
    if len(oyuncular) < 11:
        return None
    slotlar = [_dizilis_slot_mevkisi(formasyon, i) for i in range(11)]
    maliyet = []
    for slot in slotlar:
        satir = []
        for o in oyuncular:
            c = -float(o.get("yetenek", 70) or 70)
            if not can_play_position(o, slot):
                c += UNLEM_CEZASI
            if o.get("mevki") == slot:
                c -= ESAS_MEVKI_BONUS
            if o.get("sakat_gun", 0) > 0:
                c += SAKAT_CEZASI
            satir.append(c)
        maliyet.append(satir)
    atama = _minimum_maliyet_atama(maliyet)
    ilk11 = [oyuncular[j] for j in atama]
    unlem = sum(1 for o, slot in zip(ilk11, slotlar) if not can_play_position(o, slot))
    toplam = sum(float(o.get("yetenek", 70) or 70) for o in ilk11)
    return ilk11, unlem, toplam


def en_iyi_formasyon_ve_ilk11(oyuncular, tercih_idx=None):
    """(formasyon_idx, ilk11, unlem_sayisi) doner. tercih_idx verilirse once o
    dizilis denenir; unlem cikarsa unlemsiz bir dizilis varsa ona gecilir."""
    sonuclar = {}
    for idx in range(len(DIZILIS_SIRA)):
        r = en_iyi_ilk11_kur(oyuncular, idx)
        if r is None:
            return None
        sonuclar[idx] = r
    if tercih_idx is not None:
        tercih_idx %= len(DIZILIS_SIRA)
        if sonuclar[tercih_idx][1] == 0:
            return tercih_idx, sonuclar[tercih_idx][0], 0
    sirali = sorted(sonuclar, key=lambda i: (sonuclar[i][1], -sonuclar[i][2], i != tercih_idx, i))
    en_iyi = sirali[0]
    return en_iyi, sonuclar[en_iyi][0], sonuclar[en_iyi][1]


# --- [YENI] MEVKI RENK LEJANDI / POSITION COLOUR LEGEND -------------------
_MEVKI_LEJAND_ARKA = (18, 26, 40)
_MEVKI_LEJAND_CERCEVE = (95, 115, 145)
_MEVKI_LEJAND_CACHE = {}
_MEVKI_LEJAND_SATIRLAR = (
    ("DOĞAL MEVKİ", "dogal"),
    ("MEVKİ DIŞI (!)", "uyari"),
    ("SAKAT", "sakat"),
)
# Dar alanlar (mac ici kadro / canli mac) icin kisa etiketler
_MEVKI_LEJAND_SATIRLAR_KISA = (
    ("DOĞAL", "dogal"),
    ("DIŞI !", "uyari"),
    ("SAKAT", "sakat"),
)


def _mevki_lejand_olcu(olcek, baslik, kisa=False):
    """Lejand olculerini hesaplar ve onbellekler (her karede font olcmez)."""
    anahtar = (round(olcek, 2), bool(baslik), bool(kisa))
    if anahtar in _MEVKI_LEJAND_CACHE:
        return _MEVKI_LEJAND_CACHE[anahtar]
    ikon_r = max(7, int(13 * olcek))
    rozet_r = max(5, int(ikon_r * 0.55))   # saha: max(9, int(radius * 0.55))
    yazi = _uyari_font_getir(max(11, int(14 * olcek)))
    pad = max(6, int(10 * olcek))
    ara = max(8, int(14 * olcek))
    bosluk = max(4, int(6 * olcek))
    baslik_yazi = "MEVKİ UYUMU:" if baslik else ""
    baslik_w = yazi.size(baslik_yazi)[0] if baslik else 0
    kaynak = _MEVKI_LEJAND_SATIRLAR_KISA if kisa else _MEVKI_LEJAND_SATIRLAR
    satirlar = [(ad, yazi.size(ad)[0], tip) for ad, tip in kaynak]
    ikon_w = int(ikon_r * 1.72 + rozet_r)   # rozet saga tasar, payi ekle
    gen = pad + (baslik_w + ara if baslik else 0)
    for i, (_ad, tw, _tip) in enumerate(satirlar):
        gen += ikon_w + bosluk + tw
        if i < len(satirlar) - 1:
            gen += ara
    gen += pad
    yuk = max(ikon_r * 2, yazi.get_height()) + pad * 2
    veri = {"ikon_r": ikon_r, "rozet_r": rozet_r, "yazi": yazi, "pad": pad,
            "ara": ara, "bosluk": bosluk, "satirlar": satirlar,
            "baslik": baslik_yazi, "baslik_w": baslik_w, "ikon_w": ikon_w,
            "w": gen, "h": yuk}
    _MEVKI_LEJAND_CACHE[anahtar] = veri
    return veri


def mevki_lejandi_ciz(surface, x, y, olcek=1.0, baslik=True, kisa=False):
    """Mevki uyumluluk renklerinin aciklamasi. (x, y) sol-ust kosedir.

    Renkler sahadaki cizimle birebir ayni sabitlerden gelir:
      DOĞAL MEVKİ -> BEYAZ halka + takim rengi  (is_natural_position True)
      MEVKİ DIŞI  -> UYARI_KIRMIZI "!" rozeti    (saha: radius*0.55)
      SAKAT       -> KIRMIZI halka               (saha: sakat_gun > 0)
    """
    d = _mevki_lejand_olcu(olcek, baslik, kisa)
    rect = pygame.Rect(int(x), int(y), d["w"], d["h"])
    pygame.draw.rect(surface, _MEVKI_LEJAND_ARKA, rect, border_radius=10)
    pygame.draw.rect(surface, _MEVKI_LEJAND_CERCEVE, rect, 2, border_radius=10)

    imlec = rect.x + d["pad"]
    cy = rect.centery
    if baslik:
        b = d["yazi"].render(d["baslik"], True, ALTIN)
        surface.blit(b, b.get_rect(midleft=(imlec, cy)))
        imlec += d["baslik_w"] + d["ara"]

    ir, rr = d["ikon_r"], d["rozet_r"]
    for ad, tw, tip in d["satirlar"]:
        cx = imlec + ir
        if tip == "sakat":
            # saha: halka_renk = KIRMIZI, ic SIYAH -> 4px kirmizi halka
            pygame.draw.circle(surface, KIRMIZI, (cx, cy), ir)
            pygame.draw.circle(surface, SIYAH, (cx, cy), max(2, ir - 4))
        else:
            pygame.draw.circle(surface, MAVI, (cx, cy), ir)
            pygame.draw.circle(surface, UYARI_HALKA, (cx, cy), ir, 2)
            pygame.draw.circle(surface, SIYAH, (cx, cy), max(2, int(ir * 0.55)))
        if tip == "uyari":
            bx = int(cx + ir * 0.72)
            by = int(cy + ir * 0.72)
            pygame.draw.circle(surface, UYARI_KIRMIZI, (bx, by), rr)
            pygame.draw.circle(surface, UYARI_HALKA, (bx, by), rr, 2)
            f = _uyari_font_getir(max(10, int(rr * 1.7)))
            g = f.render("!", True, UYARI_HALKA)
            surface.blit(g, g.get_rect(center=(bx, by)))
        ts = d["yazi"].render(ad, True, BEYAZ)
        surface.blit(ts, ts.get_rect(midleft=(imlec + d["ikon_w"] + d["bosluk"], cy)))
        imlec += d["ikon_w"] + d["bosluk"] + tw + d["ara"]
    return rect

# --- VERİLER ---
TAKIM_OYUNCULARI = {

"Galatasaray": [
        {"isim": "U.Çakır", "mevki": "KL", "yetenek": 80, "yas": 29, "deger": 13, "face": "IMG-20260331-WA0017.jpg", "kulup": "Galatasaray", "ulke": "Türkiye"},
        {"isim": "İ.Jakobs", "mevki": "LB", "yetenek": 75, "yas": 26, "deger": 8, "face": "IMG-20260331-WA0009.jpg", "kulup": "Galatasaray", "ulke": "Senegal"},
        {"isim": "D.Sanchez", "mevki": "CB", "yetenek": 80, "yas": 29, "deger": 16, "face": "IMG-20260331-WA0015.jpg", "kulup": "Galatasaray", "ulke": "Kolombiya"},
        {"isim": "A.Bardakcı", "mevki": "CB", "yetenek": 79, "yas": 31, "deger": 5.5, "face": "IMG-20260331-WA0011.jpg", "kulup": "Galatasaray", "ulke": "Türkiye"},
        {"isim": "W.Singo", "mevki": "RB", "yetenek": 78, "yas": 25, "deger": 20, "face": "IMG-20260331-WA0007.jpg", "kulup": "Galatasaray", "ulke": "Fildişi Sahili"},
        {"isim": "G.Sara", "mevki": "MO", "yetenek": 80, "yas": 26, "deger": 27, "face": "IMG-20260331-WA0012.jpg", "kulup": "Galatasaray", "ulke": "Brezilya"},
        {"isim": "L.Torreira", "mevki": "MDO", "yetenek": 81, "yas": 30, "deger": 9, "kulup": "Galatasaray", "ulke": "Uruguay"},
        {"isim": "I.Gündoğan", "mevki": "MO", "yetenek": 78, "yas": 35, "deger": 1.5, "face": "IMG-20260331-WA0008.jpg", "kulup": "Galatasaray", "ulke": "Almanya"},
        {"isim": "Rafael Leão", "mevki": "LW", "yetenek": 83, "yas": 27, "deger": 40, "kulup": "Galatasaray", "ulke": "Portekiz"},
        {"isim": "Osimhen", "mevki": "ST", "yetenek": 85, "yas": 27, "deger": 65, "face": "IMG-20260331-WA0013.jpg", "kulup": "Galatasaray", "ulke": "Nijerya"},
        {"isim": "L.Sane", "mevki": "RW", "yetenek": 80, "yas": 30, "deger": 15, "face": "IMG-20260331-WA0016.jpg", "kulup": "Galatasaray", "ulke": "Almanya"},
        {"isim": "Jankat Yılmaz", "mevki": "KL", "yetenek": 66, "yas": 22, "deger": 2, "kulup": "Galatasaray", "ulke": "Türkiye"},
        {"isim": "G.Günay", "mevki": "KL", "yetenek": 72, "yas": 34, "deger": 0.2, "kulup": "Galatasaray", "ulke": "Türkiye"},
        {"isim": "Arda Yılmaz", "mevki": "KL", "yetenek": 60, "yas": 18, "deger": 0.05, "kulup": "Galatasaray", "ulke": "Türkiye"},
        {"isim": "Enes Emre Büyük", "mevki": "KL", "yetenek": 62, "yas": 20, "deger": 0.05, "kulup": "Galatasaray", "ulke": "Türkiye"},
        {"isim": "El Chadaille Bitshiabu", "mevki": "CB", "yetenek": 75, "yas": 21, "deger": 18, "kulup": "Galatasaray", "ulke": "Fransa"},
        {"isim": "K.Ayhan", "mevki": "MDO", "yetenek": 73, "yas": 31, "deger": 1, "kulup": "Galatasaray", "ulke": "Türkiye"},
        {"isim": "Arda Ü.", "mevki": "CB", "yetenek": 65, "yas": 18, "deger": 1, "kulup": "Galatasaray", "ulke": "Türkiye"},
        {"isim": "E.Elmalı", "mevki": "LB", "yetenek": 75, "yas": 25, "deger": 5, "kulup": "Galatasaray", "ulke": "Türkiye"},
        {"isim": "Kazımcan Karataş", "mevki": "LB", "yetenek": 67, "yas": 23, "deger": 2.5, "kulup": "Galatasaray", "ulke": "Türkiye"},
        {"isim": "R.Sallai", "mevki": "RB", "yetenek": 78, "yas": 28, "deger": 12, "kulup": "Galatasaray", "ulke": "Macaristan"},
        {"isim": "Lesley Ugochukwu", "mevki": "MDO", "yetenek": 76, "yas": 22, "deger": 22, "kulup": "Galatasaray", "ulke": "Fransa"},
        {"isim": "M.Lemina", "mevki": "MDO", "yetenek": 78, "yas": 32, "deger": 3.5, "face": "IMG-20260331-WA0014.jpg", "kulup": "Galatasaray", "ulke": "Gabon"},
        {"isim": "E.Aydın", "mevki": "MO", "yetenek": 64, "yas": 23, "deger": 0.7, "kulup": "Galatasaray", "ulke": "Türkiye"},
        {"isim": "Renato Nhaga", "mevki": "MO", "yetenek": 64, "yas": 19, "deger": 6, "kulup": "Galatasaray", "ulke": "Gine-Bissau"},
        {"isim": "Aleksey Batrakov", "mevki": "MOO", "yetenek": 55, "yas": 21, "deger": 28, "kulup": "Galatasaray", "ulke": "Rusya"},
        {"isim": "B.Yılmaz", "mevki": "RW", "yetenek": 80, "yas": 25, "deger": 30, "kulup": "Galatasaray", "ulke": "Türkiye"},
        {"isim": "Berat Luş", "mevki": "LW", "yetenek": 62, "yas": 19, "deger": 1, "kulup": "Galatasaray", "ulke": "Türkiye"},
        {"isim": "Y.Akgün", "mevki": "RW", "yetenek": 79, "yas": 25, "deger": 18, "kulup": "Galatasaray", "ulke": "Türkiye"},
        {"isim": "Armando Güner", "mevki": "RW", "yetenek": 64, "yas": 18, "deger": 0.5, "kulup": "Galatasaray", "ulke": "Arjantin"},
        {"isim": "Deniz Gül", "mevki": "ST", "yetenek": 72, "yas": 22, "deger": 10, "kulup": "Galatasaray", "ulke": "Türkiye"},
        {"isim": "Ada Yüzgeç", "mevki": "ST", "yetenek": 59, "yas": 17, "deger": 0.1, "kulup": "Galatasaray", "ulke": "Türkiye"},
     ],
"Fenerbahçe": [
        {"isim": "Ederson", "mevki": "KL", "yetenek": 82, "yas": 32, "deger": 8, "face": "IMG-20260331-WA0027.jpg", "kulup": "Fenerbahçe", "ulke": "Brezilya"},
        {"isim": "A.Brown", "mevki": "LB", "yetenek": 73, "yas": 23, "deger": 18, "face": "IMG-20260331-WA0026.jpg", "kulup": "Fenerbahçe", "ulke": "İngiltere"},
        {"isim": "Skriniar", "mevki": "CB", "yetenek": 81, "yas": 31, "deger": 8, "face": "IMG-20260331-WA0029.jpg", "kulup": "Fenerbahçe", "ulke": "Slovakya"},
        {"isim": "N.Ake", "mevki": "CB", "yetenek": 80, "yas": 29, "deger": 10, "kulup": "Fenerbahçe", "ulke": "Hollanda"},
        {"isim": "N.Semedo", "mevki": "RB", "yetenek": 77, "yas": 32, "deger": 4, "face": "IMG-20260331-WA0031.jpg", "kulup": "Fenerbahçe", "ulke": "Portekiz"},
        {"isim": "M.Guendouzi", "mevki": "MO", "yetenek": 81, "yas": 26, "deger": 27, "face": "IMG-20260331-WA0022.jpg", "kulup": "Fenerbahçe", "ulke": "Fransa"},
        {"isim": "N.Kante", "mevki": "MDO", "yetenek": 83, "yas": 34, "deger": 4, "face": "IMG-20260331-WA0023.jpg", "kulup": "Fenerbahçe", "ulke": "Fransa"},
        {"isim": "Asensio", "mevki": "MOO", "yetenek": 82, "yas": 30, "deger": 12, "face": "IMG-20260331-WA0030.jpg", "kulup": "Fenerbahçe", "ulke": "İspanya"},
        {"isim": "A.Kerem", "mevki": "LW", "yetenek": 79, "yas": 27, "deger": 18, "face": "IMG-20260331-WA0025.jpg", "kulup": "Fenerbahçe", "ulke": "Türkiye"},
        {"isim": "R.Lukaku", "mevki": "ST", "yetenek": 82, "yas": 32, "deger": 6, "kulup": "Fenerbahçe", "ulke": "Belçika"},
        {"isim": "M.Greenwood", "mevki": "RW", "yetenek": 83, "yas": 24, "deger": 40, "face": "Masongreenwood.png", "kulup": "Fenerbahçe", "ulke": "İngiltere"},
        {"isim": "Tarık Çetin", "mevki": "KL", "yetenek": 69, "yas": 29, "deger": 0.6, "kulup": "Fenerbahçe", "ulke": "Türkiye"},
        {"isim": "M.Günok", "mevki": "KL", "yetenek": 73, "yas": 37, "deger": 0.3, "face": "IMG-20260330-WA00.jpg", "kulup": "Fenerbahçe", "ulke": "Türkiye"},
        {"isim": "Kuzey Sapaz", "mevki": "KL", "yetenek": 60, "yas": 18, "deger": 0.05, "kulup": "Fenerbahçe", "ulke": "Türkiye"},
        {"isim": "Oosterwolde", "mevki": "CB", "yetenek": 76, "yas": 24, "deger": 17, "face": "IMG-20260331-WA0028.jpg", "kulup": "Fenerbahçe", "ulke": "Hollanda", "diger_mevkiler": ["LB"]},
        {"isim": "Kojo Oppong", "mevki": "CB", "yetenek": 74, "yas": 22, "deger": 12, "kulup": "Fenerbahçe", "ulke": "Gana"},
        {"isim": "Y.Efe Demir", "mevki": "CB", "yetenek": 65, "yas": 22, "deger": 4, "face": "IMG-20260330-WA00.jpg", "kulup": "Fenerbahçe", "ulke": "Türkiye"},
        {"isim": "L.Mercan", "mevki": "LB", "yetenek": 73, "yas": 25, "deger": 5, "face": "IMG-20260330-WA00.jpg", "kulup": "Fenerbahçe", "ulke": "Türkiye"},
        {"isim": "M.Müldür", "mevki": "RB", "yetenek": 73, "yas": 26, "deger": 7, "face": "IMG-20260330-WA00.jpg", "kulup": "Fenerbahçe", "ulke": "Türkiye"},
        {"isim": "Ognjen Mimović", "mevki": "RB", "yetenek": 72, "yas": 22, "deger": 2.5, "kulup": "Fenerbahçe", "ulke": "Sırbistan"},
        {"isim": "I.Yüksek", "mevki": "MDO", "yetenek": 77, "yas": 27, "deger": 15, "face": "IMG-20260330-WA00.jpg", "kulup": "Fenerbahçe", "ulke": "Türkiye"},
        {"isim": "Bartuğ Elmaz", "mevki": "MDO", "yetenek": 66, "yas": 23, "deger": 3, "kulup": "Fenerbahçe", "ulke": "Türkiye"},
        {"isim": "I.Kahveci", "mevki": "RW", "yetenek": 74, "yas": 31, "deger": 2.5, "kulup": "Fenerbahçe", "ulke": "Türkiye", "diger_mevkiler": ["MOO", "MO"]},
        {"isim": "Mert Hakan Yandaş", "mevki": "MOO", "yetenek": 67, "yas": 32, "deger": 0.2, "kulup": "Fenerbahçe", "ulke": "Türkiye"},
        {"isim": "O.Aydın", "mevki": "LW", "yetenek": 74, "yas": 25, "deger": 9, "kulup": "Fenerbahçe", "ulke": "Türkiye"},
        {"isim": "Amara Diouf", "mevki": "LW", "yetenek": 60, "yas": 18, "deger": 0.8, "kulup": "Fenerbahçe", "ulke": "Senegal"},
        {"isim": "Alaettin Ekici", "mevki": "LW", "yetenek": 61, "yas": 17, "deger": 0.3, "kulup": "Fenerbahçe", "ulke": "Türkiye"},
        {"isim": "D.Nene", "mevki": "RW", "yetenek": 75, "yas": 23, "deger": 20, "face": "IMG-20260330-WA00.jpg", "kulup": "Fenerbahçe", "ulke": "Mali"},
        {"isim": "V.Muriqi", "mevki": "ST", "yetenek": 81, "yas": 29, "deger": 7, "kulup": "Fenerbahçe", "ulke": "Kosova"},
        {"isim": "Çağrı Balta", "mevki": "ST", "yetenek": 60, "yas": 18, "deger": 0.05, "kulup": "Fenerbahçe", "ulke": "Türkiye"},
    ],
"Eyüpspor": [
        {"isim": "Horațiu Moldovan", "mevki": "KL", "yetenek": 70, "yas": 28, "deger": 1.5, "kulup": "Eyüpspor", "ulke": "Romanya"},
        {"isim": "Simone Giordano", "mevki": "LB", "yetenek": 69, "yas": 24, "deger": 0.7, "kulup": "Eyüpspor", "ulke": "İtalya"},
        {"isim": "Jawad El Yamiq", "mevki": "CB", "yetenek": 69, "yas": 34, "deger": 0.3, "kulup": "Eyüpspor", "ulke": "Fas"},
        {"isim": "Zak Jules", "mevki": "CB", "yetenek": 63, "yas": 29, "deger": 0.3, "kulup": "Eyüpspor", "ulke": "İskoçya"},
        {"isim": "Talha Ülvan", "mevki": "RB", "yetenek": 60, "yas": 25, "deger": 0.8, "kulup": "Eyüpspor", "ulke": "Türkiye"},
        {"isim": "Charles-André Raux-Yao", "mevki": "MO", "yetenek": 62, "yas": 25, "deger": 2, "kulup": "Eyüpspor", "ulke": "Fildişi Sahili"},
        {"isim": "Chandrel Massanga", "mevki": "MDO", "yetenek": 68, "yas": 27, "deger": 0.5, "kulup": "Eyüpspor", "ulke": "Kongo Cumhuriyeti"},
        {"isim": "Abdelhamid Sabiri", "mevki": "MOO", "yetenek": 71, "yas": 29, "deger": 0.7, "kulup": "Eyüpspor", "ulke": "Fas"},
        {"isim": "Konrad Michalak", "mevki": "LW", "yetenek": 67, "yas": 29, "deger": 0.5, "kulup": "Eyüpspor", "ulke": "Polonya"},
        {"isim": "Yusuf Barası", "mevki": "ST", "yetenek": 64, "yas": 23, "deger": 0.8, "kulup": "Eyüpspor", "ulke": "Türkiye"},
        {"isim": "Bilal Boutobba", "mevki": "RW", "yetenek": 69, "yas": 28, "deger": 1.2, "kulup": "Eyüpspor", "ulke": "Fransa"},
        {"isim": "E.Bilgin", "mevki": "KL", "yetenek": 64, "yas": 22, "deger": 0.4, "face": "images (52).jpeg", "kulup": "Eyüpspor", "ulke": "Türkiye"},
        {"isim": "Umut Keseci", "mevki": "KL", "yetenek": 52, "yas": 22, "deger": 0.2, "kulup": "Eyüpspor", "ulke": "Türkiye"},
        {"isim": "Anıl Yaşar", "mevki": "CB", "yetenek": 63, "yas": 24, "deger": 0.3, "kulup": "Eyüpspor", "ulke": "Türkiye"},
        {"isim": "Yiğit Demir", "mevki": "CB", "yetenek": 63, "yas": 23, "deger": 0.15, "kulup": "Eyüpspor", "ulke": "Türkiye"},
        {"isim": "Kutlay Şatlı", "mevki": "CB", "yetenek": 62, "yas": 20, "deger": 0.05, "kulup": "Eyüpspor", "ulke": "Türkiye"},
        {"isim": "Diabel Ndoye", "mevki": "CB", "yetenek": 56, "yas": 19, "deger": 0.05, "kulup": "Eyüpspor", "ulke": "Senegal"},
        {"isim": "Arda Yavuz", "mevki": "LB", "yetenek": 55, "yas": 20, "deger": 0.05, "kulup": "Eyüpspor", "ulke": "Türkiye"},
        {"isim": "Ahmet Ceyhan", "mevki": "RB", "yetenek": 57, "yas": 19, "deger": 0.05, "kulup": "Eyüpspor", "ulke": "Türkiye"},
        {"isim": "Taşkın İlter", "mevki": "MDO", "yetenek": 63, "yas": 32, "deger": 0.1, "kulup": "Eyüpspor", "ulke": "Türkiye"},
        {"isim": "Hamza Akman", "mevki": "MO", "yetenek": 57, "yas": 22, "deger": 0.4, "kulup": "Eyüpspor", "ulke": "Türkiye"},
        {"isim": "David Costa", "mevki": "MOO", "yetenek": 60, "yas": 22, "deger": 0.8, "kulup": "Eyüpspor", "ulke": "Yeşil Burun Adaları"},
        {"isim": "Lenny Pintor", "mevki": "LW", "yetenek": 66, "yas": 26, "deger": 0.2, "kulup": "Eyüpspor", "ulke": "Fransa"},
        {"isim": "Mete Demir", "mevki": "RW", "yetenek": 63, "yas": 28, "deger": 0.3, "kulup": "Eyüpspor", "ulke": "Türkiye"},
        {"isim": "Christ Sadia", "mevki": "RW", "yetenek": 58, "yas": 19, "deger": 0.1, "kulup": "Eyüpspor", "ulke": "Fildişi Sahili"},
        {"isim": "Musa Eren Karakaş", "mevki": "RW", "yetenek": 64, "yas": 22, "deger": 0.1, "kulup": "Eyüpspor", "ulke": "Türkiye"},
        {"isim": "Ahmed Abdullahi", "mevki": "ST", "yetenek": 58, "yas": 22, "deger": 1.5, "kulup": "Eyüpspor", "ulke": "Nijerya"},
        {"isim": "Abdou Khadre Sy", "mevki": "ST", "yetenek": 60, "yas": 18, "deger": 0.1, "kulup": "Eyüpspor", "ulke": "Senegal"},
    ],
"Beşiktaş": [
        {"isim": "Alexander Nübel", "mevki": "KL", "yetenek": 80, "yas": 30, "deger": 10, "kulup": "Beşiktaş", "ulke": "Almanya"},
        {"isim": "R.Yılmaz", "mevki": "LB", "yetenek": 72, "yas": 25, "deger": 7, "face": "images (45).jpeg", "kulup": "Beşiktaş", "ulke": "Türkiye"},
        {"isim": "E.Agbadou", "mevki": "CB", "yetenek": 77, "yas": 28, "deger": 14, "face": "Screenshot_2026-03-31-20-56-16-988_com.android.chrome-edit.jpg", "kulup": "Beşiktaş", "ulke": "Fildişi Sahili"},
        {"isim": "E.Topçu", "mevki": "CB", "yetenek": 74, "yas": 25, "deger": 9, "face": "Screenshot_2026-03-31-20-52-10-710_com.android.chrome-edit.jpg", "kulup": "Beşiktaş", "ulke": "Türkiye"},
        {"isim": "A.Murillo", "mevki": "RB", "yetenek": 74, "yas": 28, "deger": 7, "face": "images (46).jpeg", "kulup": "Beşiktaş", "ulke": "Panama"},
        {"isim": "Orkun", "mevki": "MO", "yetenek": 82, "yas": 25, "deger": 28, "face": "images (48).jpeg", "kulup": "Beşiktaş", "ulke": "Türkiye"},
        {"isim": "W.Ndidi", "mevki": "MDO", "yetenek": 75, "yas": 29, "deger": 6, "face": "images (47).jpeg", "kulup": "Beşiktaş", "ulke": "Nijerya"},
        {"isim": "Fabio Miretti", "mevki": "MO", "yetenek": 75, "yas": 23, "deger": 15, "kulup": "Beşiktaş", "ulke": "İtalya"},
        {"isim": "Leandro Trossard", "mevki": "LW", "yetenek": 82, "yas": 31, "deger": 18, "kulup": "Beşiktaş", "ulke": "Belçika"},
        {"isim": "Dušan Vlahović", "mevki": "ST", "yetenek": 81, "yas": 26, "deger": 32, "kulup": "Beşiktaş", "ulke": "Sırbistan"},
        {"isim": "V.Cerny", "mevki": "RW", "yetenek": 77, "yas": 28, "deger": 7, "face": "images (51).jpeg", "kulup": "Beşiktaş", "ulke": "Çekya"},
        {"isim": "D.Alemdar", "mevki": "KL", "yetenek": 68, "yas": 23, "deger": 2, "kulup": "Beşiktaş", "ulke": "Türkiye"},
        {"isim": "Emir Yaşar", "mevki": "KL", "yetenek": 58, "yas": 20, "deger": 0.1, "kulup": "Beşiktaş", "ulke": "Türkiye"},
        {"isim": "T.Djaló", "mevki": "CB", "yetenek": 74, "yas": 26, "deger": 8, "kulup": "Beşiktaş", "ulke": "Portekiz"},
        {"isim": "Ümit Akdağ", "mevki": "CB", "yetenek": 69, "yas": 23, "deger": 8, "kulup": "Beşiktaş", "ulke": "Türkiye"},
        {"isim": "Yasin Özcan", "mevki": "CB", "yetenek": 70, "yas": 20, "deger": 5, "kulup": "Beşiktaş", "ulke": "Türkiye"},
        {"isim": "Azem Yortaç", "mevki": "CB", "yetenek": 60, "yas": 18, "deger": 0.05, "kulup": "Beşiktaş", "ulke": "Türkiye"},
        {"isim": "Kassoum Ouattara", "mevki": "LB", "yetenek": 72, "yas": 22, "deger": 12, "kulup": "Beşiktaş", "ulke": "Fildişi Sahili"},
        {"isim": "T.Bulut", "mevki": "RB", "yetenek": 67, "yas": 28, "deger": 5, "kulup": "Beşiktaş", "ulke": "Almanya"},
        {"isim": "Salih Özcan", "mevki": "MDO", "yetenek": 74, "yas": 28, "deger": 6, "kulup": "Beşiktaş", "ulke": "Türkiye"},
        {"isim": "K.Yilmaz", "mevki": "MO", "yetenek": 69, "yas": 25, "deger": 2, "kulup": "Beşiktaş", "ulke": "Türkiye"},
        {"isim": "Junior Olaitan", "mevki": "MO", "yetenek": 71, "yas": 24, "deger": 12, "kulup": "Beşiktaş", "ulke": "Benin"},
        {"isim": "İlhan Fakılı", "mevki": "LW", "yetenek": 64, "yas": 20, "deger": 7, "kulup": "Beşiktaş", "ulke": "Türkiye"},
        {"isim": "Ozan Sevim", "mevki": "LW", "yetenek": 61, "yas": 19, "deger": 0.05, "kulup": "Beşiktaş", "ulke": "Türkiye"},
        {"isim": "Ernest Poku", "mevki": "RW", "yetenek": 76, "yas": 22, "deger": 22, "kulup": "Beşiktaş", "ulke": "Hollanda"},
        {"isim": "M.Rashica", "mevki": "LW", "yetenek": 74, "yas": 29, "deger": 2.5, "kulup": "Beşiktaş", "ulke": "Kosova"},
        {"isim": "Can Keles", "mevki": "RW", "yetenek": 66, "yas": 25, "deger": 0.8, "kulup": "Beşiktaş", "ulke": "Avusturya"},
        {"isim": "H.Gyu Oh", "mevki": "ST", "yetenek": 75, "yas": 25, "deger": 15, "face": "", "kulup": "Beşiktaş", "ulke": "Güney Kore"},
        {"isim": "Semih Kılıçsoy", "mevki": "ST", "yetenek": 73, "yas": 21, "deger": 8, "kulup": "Beşiktaş", "ulke": "Türkiye"},
        {"isim": "H.Mustafa", "mevki": "ST", "yetenek": 67, "yas": 19, "deger": 5, "kulup": "Beşiktaş", "ulke": "Türkiye"},
        {"isim": "Ahmet Sami Bircan", "mevki": "ST", "yetenek": 60, "yas": 19, "deger": 0.1, "kulup": "Beşiktaş", "ulke": "Türkiye"},
    ],
"Trabzonspor": [
        {"isim": "A.Onana", "mevki": "KL", "yetenek": 78, "yas": 30, "deger": 8, "face": "images (53).jpeg", "kulup": "Trabzonspor", "ulke": "Kamerun"},
        {"isim": "Sidny Lopes Cabral", "mevki": "LB", "yetenek": 71, "yas": 24, "deger": 10, "kulup": "Trabzonspor", "ulke": "Yeşil Burun Adaları"},
        {"isim": "A.Batagov", "mevki": "CB", "yetenek": 76, "yas": 24, "deger": 10, "kulup": "Trabzonspor", "ulke": "Ukrayna"},
        {"isim": "S.Sávic", "mevki": "CB", "yetenek": 76, "yas": 35, "deger": 0.4, "face": "images (55).jpeg", "kulup": "Trabzonspor", "ulke": "Karadağ"},
        {"isim": "W.Pina", "mevki": "RB", "yetenek": 72, "yas": 24, "deger": 12, "kulup": "Trabzonspor", "ulke": "Yeşil Burun Adaları"},
        {"isim": "E.Muçi", "mevki": "MOO", "yetenek": 75, "yas": 25, "deger": 11, "face": "images (45)(1).jpeg", "kulup": "Trabzonspor", "ulke": "Arnavutluk"},
        {"isim": "Fabinho", "mevki": "MDO", "yetenek": 82, "yas": 33, "deger": 8, "kulup": "Trabzonspor", "ulke": "Brezilya"},
        {"isim": "Ruslan Malinovskyi", "mevki": "MO", "yetenek": 75, "yas": 33, "deger": 2, "kulup": "Trabzonspor", "ulke": "Ukrayna"},
        {"isim": "Aral Şimşir", "mevki": "LW", "yetenek": 76, "yas": 24, "deger": 15, "kulup": "Trabzonspor", "ulke": "Türkiye"},
        {"isim": "P.Onuachu", "mevki": "ST", "yetenek": 77, "yas": 31, "deger": 6, "face": "images (47)(1).jpeg", "kulup": "Trabzonspor", "ulke": "Nijerya"},
        {"isim": "M.Salah", "mevki": "RW", "yetenek": 87, "yas": 33, "deger": 17, "kulup": "Trabzonspor", "ulke": "Mısır"},
        {"isim": "Ç.Onuralp", "mevki": "KL", "yetenek": 62, "yas": 20, "deger": 0.8, "kulup": "Trabzonspor", "ulke": "Türkiye"},
        {"isim": "Ahmet Yıldırım", "mevki": "KL", "yetenek": 57, "yas": 20, "deger": 0.5, "kulup": "Trabzonspor", "ulke": "Türkiye"},
        {"isim": "Erol Can Çolak", "mevki": "KL", "yetenek": 62, "yas": 20, "deger": 0.05, "kulup": "Trabzonspor", "ulke": "Türkiye"},
        {"isim": "C.Nwaiwu", "mevki": "CB", "yetenek": 72, "yas": 25, "deger": 18, "kulup": "Trabzonspor", "ulke": "Nijerya"},
        {"isim": "Cenk Özkacar", "mevki": "CB", "yetenek": 72, "yas": 26, "deger": 3, "kulup": "Trabzonspor", "ulke": "Türkiye"},
        {"isim": "Samet Akaydin", "mevki": "CB", "yetenek": 72, "yas": 32, "deger": 1, "kulup": "Trabzonspor", "ulke": "Türkiye"},
        {"isim": "M.Eskihellaç", "mevki": "RB", "yetenek": 72, "yas": 28, "deger": 4, "kulup": "Trabzonspor", "ulke": "Türkiye"},
        {"isim": "Batista Mendy", "mevki": "MDO", "yetenek": 75, "yas": 26, "deger": 5, "kulup": "Trabzonspor", "ulke": "Fransa"},
        {"isim": "Melih Kabasakal", "mevki": "MDO", "yetenek": 68, "yas": 30, "deger": 1, "kulup": "Trabzonspor", "ulke": "Türkiye"},
        {"isim": "O.Yokuşlu", "mevki": "MO", "yetenek": 72, "yas": 32, "deger": 0.8, "kulup": "Trabzonspor", "ulke": "Türkiye"},
        {"isim": "Folcarelli", "mevki": "MO", "yetenek": 72, "yas": 24, "deger": 7, "kulup": "Trabzonspor", "ulke": "Fransa"},
        {"isim": "Bouchouari", "mevki": "MO", "yetenek": 68, "yas": 24, "deger": 3.5, "kulup": "Trabzonspor", "ulke": "Fas"},
        {"isim": "O.Tufan", "mevki": "MOO", "yetenek": 72, "yas": 31, "deger": 1.5, "face": "images (44)(1).jpeg", "kulup": "Trabzonspor", "ulke": "Türkiye"},
        {"isim": "Noah Saviolo", "mevki": "LW", "yetenek": 69, "yas": 22, "deger": 12, "kulup": "Trabzonspor", "ulke": "Portekiz"},
        {"isim": "Metehan Mimaroğlu", "mevki": "LW", "yetenek": 67, "yas": 32, "deger": 0.4, "kulup": "Trabzonspor", "ulke": "Türkiye"},
        {"isim": "Cihan Çanak", "mevki": "RW", "yetenek": 64, "yas": 21, "deger": 1.8, "kulup": "Trabzonspor", "ulke": "Türkiye"},
        {"isim": "Franculino", "mevki": "ST", "yetenek": 74, "yas": 22, "deger": 22, "kulup": "Trabzonspor", "ulke": "Gine-Bissau"},
        {"isim": "Ali Habeşoğlu", "mevki": "ST", "yetenek": 69, "yas": 22, "deger": 2.2, "kulup": "Trabzonspor", "ulke": "Türkiye"},
        {"isim": "Umut Nayir", "mevki": "ST", "yetenek": 69, "yas": 33, "deger": 0.4, "kulup": "Trabzonspor", "ulke": "Türkiye"},
    ],
"Başakşehir": [
        {"isim": "Muhammed Şengezer", "mevki": "KL", "yetenek": 72, "yas": 29, "deger": 3.5, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "C.Operi", "mevki": "LB", "yetenek": 73, "yas": 28, "deger": 3, "kulup": "Başakşehir", "ulke": "Fildişi Sahili"},
        {"isim": "J.Opoku", "mevki": "CB", "yetenek": 72, "yas": 27, "deger": 7, "kulup": "Başakşehir", "ulke": "Gana"},
        {"isim": "Emin Bayram", "mevki": "CB", "yetenek": 73, "yas": 23, "deger": 4, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "Michal Karbownik", "mevki": "RB", "yetenek": 70, "yas": 25, "deger": 1.8, "kulup": "Başakşehir", "ulke": "Polonya"},
        {"isim": "Fayzullayev", "mevki": "MO", "yetenek": 73, "yas": 22, "deger": 7, "kulup": "Başakşehir", "ulke": "Özbekistan"},
        {"isim": "Jakub Kaluzinski", "mevki": "MDO", "yetenek": 68, "yas": 24, "deger": 2.5, "kulup": "Başakşehir", "ulke": "Polonya"},
        {"isim": "O.Kemen", "mevki": "MO", "yetenek": 71, "yas": 29, "deger": 2, "kulup": "Başakşehir", "ulke": "Kamerun"},
        {"isim": "I.Brnic", "mevki": "LW", "yetenek": 69, "yas": 24, "deger": 2, "kulup": "Başakşehir", "ulke": "Hırvatistan"},
        {"isim": "Eldor Shomurodov", "mevki": "ST", "yetenek": 76, "yas": 31, "deger": 7, "kulup": "Başakşehir", "ulke": "Özbekistan"},
        {"isim": "Yusuf Sarı", "mevki": "RW", "yetenek": 73, "yas": 27, "deger": 4, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "Deniz Dilmen", "mevki": "KL", "yetenek": 65, "yas": 21, "deger": 1.5, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "Volkan Babacan", "mevki": "KL", "yetenek": 66, "yas": 38, "deger": 0.05, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "Luca Stancic", "mevki": "KL", "yetenek": 61, "yas": 19, "deger": 0.05, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "Ege Öztürk", "mevki": "KL", "yetenek": 60, "yas": 18, "deger": 0.05, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "Hamza Güreler", "mevki": "CB", "yetenek": 65, "yas": 20, "deger": 1.5, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "Ousseynou Ba", "mevki": "CB", "yetenek": 69, "yas": 31, "deger": 1, "kulup": "Başakşehir", "ulke": "Senegal"},
        {"isim": "Efe Arda Koyuncu", "mevki": "CB", "yetenek": 62, "yas": 21, "deger": 0.05, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "Saba Kharebashvili", "mevki": "LB", "yetenek": 66, "yas": 18, "deger": 2.5, "kulup": "Başakşehir", "ulke": "Gürcistan"},
        {"isim": "O.Bulut", "mevki": "RB", "yetenek": 67, "yas": 32, "deger": 0.4, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "Ömer Ali Şahiner", "mevki": "RB", "yetenek": 68, "yas": 34, "deger": 0.2, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "Onur Ergün", "mevki": "MDO", "yetenek": 66, "yas": 34, "deger": 0.15, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "Umut Güneş", "mevki": "MO", "yetenek": 69, "yas": 26, "deger": 3, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "Berkay Özcan", "mevki": "MO", "yetenek": 67, "yas": 28, "deger": 1, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "Andreas Skov Olsen", "mevki": "RW", "yetenek": 73, "yas": 26, "deger": 5, "kulup": "Başakşehir", "ulke": "Danimarka"},
        {"isim": "E.Visca", "mevki": "RW", "yetenek": 73, "yas": 36, "deger": 0.1, "kulup": "Başakşehir", "ulke": "Bosna-Hersek"},
        {"isim": "Bertuğ Yıldırım", "mevki": "ST", "yetenek": 70, "yas": 24, "deger": 8, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "Davie Selke", "mevki": "ST", "yetenek": 72, "yas": 31, "deger": 1.5, "kulup": "Başakşehir", "ulke": "Almanya"},
        {"isim": "Umut Bozok", "mevki": "ST", "yetenek": 69, "yas": 30, "deger": 1.5, "kulup": "Başakşehir", "ulke": "Türkiye"},
        {"isim": "Batuhan Çelik", "mevki": "ST", "yetenek": 60, "yas": 21, "deger": 0.9, "kulup": "Başakşehir", "ulke": "Türkiye"},
    ],
"Samsunspor": [
        {"isim": "Okan Kocuk", "mevki": "KL", "yetenek": 72, "yas": 31, "deger": 2, "kulup": "Samsunspor", "ulke": "Türkiye"},
        {"isim": "Tómasson", "mevki": "LB", "yetenek": 70, "yas": 25, "deger": 4, "kulup": "Samsunspor", "ulke": "İzlanda"},
        {"isim": "Strahinja Erakovic", "mevki": "CB", "yetenek": 68, "yas": 25, "deger": 6, "kulup": "Samsunspor", "ulke": "Sırbistan"},
        {"isim": "Gabriele Guarino", "mevki": "CB", "yetenek": 68, "yas": 22, "deger": 4, "kulup": "Samsunspor", "ulke": "İtalya"},
        {"isim": "Joe Mendes", "mevki": "RB", "yetenek": 69, "yas": 24, "deger": 4, "kulup": "Samsunspor", "ulke": "İsveç"},
        {"isim": "Antoine Sekongo", "mevki": "MO", "yetenek": 68, "yas": 22, "deger": 4, "kulup": "Samsunspor", "ulke": "Mali"},
        {"isim": "Elliot Watt", "mevki": "MDO", "yetenek": 72, "yas": 26, "deger": 2.5, "kulup": "Samsunspor", "ulke": "İskoçya"},
        {"isim": "Afonso Sousa", "mevki": "MOO", "yetenek": 71, "yas": 26, "deger": 2, "kulup": "Samsunspor", "ulke": "Portekiz"},
        {"isim": "E.Kılınç", "mevki": "LW", "yetenek": 70, "yas": 32, "deger": 0.8, "kulup": "Samsunspor", "ulke": "Türkiye"},
        {"isim": "Mohamed Bayo", "mevki": "ST", "yetenek": 74, "yas": 28, "deger": 4.5, "kulup": "Samsunspor", "ulke": "Gine"},
        {"isim": "Coulibaly", "mevki": "RW", "yetenek": 69, "yas": 26, "deger": 1.2, "kulup": "Samsunspor", "ulke": "Fransa"},
        {"isim": "Bilal Bayazıt", "mevki": "KL", "yetenek": 69, "yas": 27, "deger": 1.8, "kulup": "Samsunspor", "ulke": "Türkiye"},
        {"isim": "Efe Yiğit Üstün", "mevki": "KL", "yetenek": 60, "yas": 18, "deger": 0.05, "kulup": "Samsunspor", "ulke": "Türkiye"},
        {"isim": "Efe Berat Töruz", "mevki": "KL", "yetenek": 54, "yas": 20, "deger": 0.05, "kulup": "Samsunspor", "ulke": "Türkiye"},
        {"isim": "Igor Drapiński", "mevki": "CB", "yetenek": 68, "yas": 22, "deger": 2.5, "kulup": "Samsunspor", "ulke": "Polonya"},
        {"isim": "Yunus Emre Çift", "mevki": "CB", "yetenek": 65, "yas": 23, "deger": 0.6, "kulup": "Samsunspor", "ulke": "Türkiye"},
        {"isim": "Bedirhan Çetin", "mevki": "CB", "yetenek": 58, "yas": 20, "deger": 0.1, "kulup": "Samsunspor", "ulke": "Türkiye"},
        {"isim": "Kerem Fidan", "mevki": "CB", "yetenek": 62, "yas": 20, "deger": 0.05, "kulup": "Samsunspor", "ulke": "Türkiye"},
        {"isim": "Enes Albak", "mevki": "LB", "yetenek": 61, "yas": 21, "deger": 0.15, "kulup": "Samsunspor", "ulke": "Türkiye"},
        {"isim": "Mustafa Tan", "mevki": "RB", "yetenek": 57, "yas": 21, "deger": 0.2, "kulup": "Samsunspor", "ulke": "Türkiye"},
        {"isim": "Oskar Øhlenschlæger", "mevki": "MO", "yetenek": 68, "yas": 22, "deger": 3.5, "kulup": "Samsunspor", "ulke": "Danimarka"},
        {"isim": "Yalçın Kayan", "mevki": "MO", "yetenek": 68, "yas": 27, "deger": 1.2, "kulup": "Samsunspor", "ulke": "Türkiye"},
        {"isim": "Celil Yüksel", "mevki": "MO", "yetenek": 67, "yas": 28, "deger": 1, "kulup": "Samsunspor", "ulke": "Türkiye"},
        {"isim": "Samed Onur", "mevki": "MO", "yetenek": 61, "yas": 24, "deger": 1, "kulup": "Samsunspor", "ulke": "Türkiye"},
        {"isim": "Jaurès Assoumou", "mevki": "LW", "yetenek": 65, "yas": 24, "deger": 2, "kulup": "Samsunspor", "ulke": "Fildişi Sahili"},
        {"isim": "Elayis Tavsan", "mevki": "RW", "yetenek": 68, "yas": 25, "deger": 1.5, "kulup": "Samsunspor", "ulke": "Türkiye"},
        {"isim": "Saikuba Jarju", "mevki": "RW", "yetenek": 62, "yas": 18, "deger": 1.5, "kulup": "Samsunspor", "ulke": "Gambiya"},
        {"isim": "Fatih Kaya", "mevki": "ST", "yetenek": 68, "yas": 27, "deger": 0.8, "kulup": "Samsunspor", "ulke": "Almanya"},
     ],
"Kasımpaşa": [
        {"isim": "Gianniotis", "mevki": "KL", "yetenek": 70, "yas": 34, "deger": 0.2, "kulup": "Kasımpaşa", "ulke": "Yunanistan"},
        {"isim": "Frimpong", "mevki": "LB", "yetenek": 68, "yas": 25, "deger": 1.5, "kulup": "Kasımpaşa", "ulke": "Hollanda"},
        {"isim": "Matei Ilie", "mevki": "CB", "yetenek": 70, "yas": 23, "deger": 2.5, "kulup": "Kasımpaşa", "ulke": "Romanya"},
        {"isim": "Kévin Mouanga", "mevki": "CB", "yetenek": 69, "yas": 26, "deger": 2.5, "kulup": "Kasımpaşa", "ulke": "Kongo Cumhuriyeti"},
        {"isim": "C.Winck", "mevki": "RB", "yetenek": 71, "yas": 32, "deger": 0.7, "kulup": "Kasımpaşa", "ulke": "Brezilya"},
        {"isim": "Hajradinovic", "mevki": "MO", "yetenek": 73, "yas": 32, "deger": 0.7, "kulup": "Kasımpaşa", "ulke": "Bosna-Hersek"},
        {"isim": "K.Demirbay", "mevki": "MDO", "yetenek": 73, "yas": 33, "deger": 0.8, "kulup": "Kasımpaşa", "ulke": "Almanya"},
        {"isim": "Baldursson", "mevki": "MO", "yetenek": 65, "yas": 24, "deger": 3, "kulup": "Kasımpaşa", "ulke": "İzlanda"},
        {"isim": "Mortadha Ben Ouanes", "mevki": "LW", "yetenek": 74, "yas": 32, "deger": 1, "kulup": "Kasımpaşa", "ulke": "Tunus"},
        {"isim": "Adrian Benedyczak", "mevki": "ST", "yetenek": 72, "yas": 26, "deger": 7, "kulup": "Kasımpaşa", "ulke": "Polonya"},
        {"isim": "Jesurun Rak-Sakyi", "mevki": "RW", "yetenek": 70, "yas": 24, "deger": 5, "kulup": "Kasımpaşa", "ulke": "Gana"},
        {"isim": "A.Emre", "mevki": "KL", "yetenek": 61, "yas": 28, "deger": 0.1, "kulup": "Kasımpaşa", "ulke": "Türkiye"},
        {"isim": "Ege Albayrak", "mevki": "KL", "yetenek": 61, "yas": 19, "deger": 0.05, "kulup": "Kasımpaşa", "ulke": "Türkiye"},
        {"isim": "Adem Arous", "mevki": "CB", "yetenek": 63, "yas": 22, "deger": 4, "kulup": "Kasımpaşa", "ulke": "Tunus"},
        {"isim": "Ahmet Taha Dağbaşı", "mevki": "CB", "yetenek": 62, "yas": 21, "deger": 0.05, "kulup": "Kasımpaşa", "ulke": "Türkiye"},
        {"isim": "Salih Arıcı", "mevki": "CB", "yetenek": 60, "yas": 18, "deger": 0.05, "kulup": "Kasımpaşa", "ulke": "Türkiye"},
        {"isim": "Jakob Jessen", "mevki": "LB", "yetenek": 64, "yas": 22, "deger": 1, "kulup": "Kasımpaşa", "ulke": "Danimarka"},
        {"isim": "Ömer Bayram", "mevki": "LB", "yetenek": 63, "yas": 35, "deger": 0.05, "kulup": "Kasımpaşa", "ulke": "Türkiye"},
        {"isim": "Ayberk Karapo", "mevki": "RB", "yetenek": 60, "yas": 22, "deger": 2.5, "kulup": "Kasımpaşa", "ulke": "Türkiye"},
        {"isim": "A.Çörekçi", "mevki": "RB", "yetenek": 66, "yas": 34, "deger": 0.05, "kulup": "Kasımpaşa", "ulke": "Türkiye"},
        {"isim": "Elson Mendes", "mevki": "MDO", "yetenek": 60, "yas": 21, "deger": 1.8, "kulup": "Kasımpaşa", "ulke": "Yeşil Burun Adaları"},
        {"isim": "Emirhan Boz", "mevki": "MDO", "yetenek": 61, "yas": 20, "deger": 0.7, "kulup": "Kasımpaşa", "ulke": "Türkiye"},
        {"isim": "A.Müjde", "mevki": "MOO", "yetenek": 60, "yas": 20, "deger": 0.15, "kulup": "Kasımpaşa", "ulke": "Türkiye"},
        {"isim": "Thiemoko Diarra", "mevki": "LW", "yetenek": 67, "yas": 23, "deger": 2, "kulup": "Kasımpaşa", "ulke": "Mali"},
        {"isim": "Marcus Rafferty", "mevki": "LW", "yetenek": 67, "yas": 22, "deger": 1.8, "kulup": "Kasımpaşa", "ulke": "İsveç"},
        {"isim": "A.Yavuz", "mevki": "LW", "yetenek": 63, "yas": 25, "deger": 0.5, "kulup": "Kasımpaşa", "ulke": "Türkiye"},
        {"isim": "Sercan Deniz", "mevki": "LW", "yetenek": 58, "yas": 19, "deger": 0.3, "kulup": "Kasımpaşa", "ulke": "Türkiye"},
        {"isim": "F.Diabaté", "mevki": "LW", "yetenek": 67, "yas": 31, "deger": 0.8, "kulup": "Kasımpaşa", "ulke": "Mali"},
        {"isim": "Emirhan Yiğit", "mevki": "RW", "yetenek": 62, "yas": 20, "deger": 0.1, "kulup": "Kasımpaşa", "ulke": "Türkiye"},
        {"isim": "Güven Yalçın", "mevki": "ST", "yetenek": 68, "yas": 27, "deger": 1, "kulup": "Kasımpaşa", "ulke": "Türkiye"},
        {"isim": "Muhammed Emin Bektaş", "mevki": "ST", "yetenek": 63, "yas": 20, "deger": 0.2, "kulup": "Kasımpaşa", "ulke": "Türkiye"},
        {"isim": "Sinan Alkaş", "mevki": "ST", "yetenek": 63, "yas": 20, "deger": 0.15, "kulup": "Kasımpaşa", "ulke": "Türkiye"},
    ],

     #AZE Premier liqası
"Qarabağ": [
        {"isim": "Martin Zlomislic", "mevki": "KL", "yetenek": 70, "yas": 28, "deger": 2, "kulup": "Qarabağ", "ulke": "Bosna-Hersek"},
        {"isim": "E.Cəfərquliyev", "mevki": "LB", "yetenek": 69, "yas": 25, "deger": 2, "kulup": "Qarabağ", "ulke": "Azerbaycan"},
        {"isim": "M.Bəhlul", "mevki": "CB", "yetenek": 67, "yas": 29, "deger": 1, "kulup": "Qarabağ", "ulke": "Azerbaycan"},
        {"isim": "Badavi Hüseynov", "mevki": "CB", "yetenek": 67, "yas": 35, "deger": 0.1, "kulup": "Qarabağ", "ulke": "Azerbaycan"},
        {"isim": "Cebrail Makreckis", "mevki": "RB", "yetenek": 72, "yas": 26, "deger": 1, "kulup": "Qarabağ", "ulke": "Letonya"},
        {"isim": "P.Bicalho", "mevki": "MO", "yetenek": 71, "yas": 23, "deger": 2, "kulup": "Qarabağ", "ulke": "Brezilya"},
        {"isim": "Diego Rosa", "mevki": "MDO", "yetenek": 69, "yas": 24, "deger": 1.5, "kulup": "Qarabağ", "ulke": "Brezilya"},
        {"isim": "Kady Borges", "mevki": "MOO", "yetenek": 74, "yas": 30, "deger": 2, "kulup": "Qarabağ", "ulke": "Brezilya"},
        {"isim": "Renaldo Cephas", "mevki": "LW", "yetenek": 72, "yas": 26, "deger": 0.9, "kulup": "Qarabağ", "ulke": "Jamaika"},
        {"isim": "Musa Qurbanly", "mevki": "ST", "yetenek": 66, "yas": 24, "deger": 0.75, "kulup": "Qarabağ", "ulke": "Azerbaycan"},
        {"isim": "Oleksiy Kashchuk", "mevki": "RW", "yetenek": 69, "yas": 26, "deger": 1.5, "kulup": "Qarabağ", "ulke": "Ukrayna"},
        {"isim": "Shahrudin Mahammadaliyev", "mevki": "KL", "yetenek": 68, "yas": 32, "deger": 0.6, "kulup": "Qarabağ", "ulke": "Azerbaycan"},
        {"isim": "Bence Várkonyi", "mevki": "CB", "yetenek": 65, "yas": 24, "deger": 0.5, "kulup": "Qarabağ", "ulke": "Macaristan"},
        {"isim": "Bruno Langa", "mevki": "LB", "yetenek": 71, "yas": 29, "deger": 1, "kulup": "Qarabağ", "ulke": "Mozambik"},
        {"isim": "Jérémie Gnali", "mevki": "LB", "yetenek": 64, "yas": 24, "deger": 0.4, "kulup": "Qarabağ", "ulke": "Fransa"},
        {"isim": "Matheus Silva", "mevki": "RB", "yetenek": 69, "yas": 29, "deger": 1.2, "kulup": "Qarabağ", "ulke": "Brezilya"},
        {"isim": "Abbas Hüseynov", "mevki": "RB", "yetenek": 65, "yas": 31, "deger": 0.4, "kulup": "Qarabağ", "ulke": "Azerbaycan"},
        {"isim": "M.Jankovic", "mevki": "MO", "yetenek": 70, "yas": 31, "deger": 0.8, "kulup": "Qarabağ", "ulke": "Karadağ"},
        {"isim": "Samuel Lobato", "mevki": "MO", "yetenek": 64, "yas": 25, "deger": 0.45, "kulup": "Qarabağ", "ulke": "Portekiz"},
        {"isim": "Reda Khadra", "mevki": "MOO", "yetenek": 71, "yas": 25, "deger": 1.2, "kulup": "Qarabağ", "ulke": "Lübnan"},
        {"isim": "J.Montiel", "mevki": "MOO", "yetenek": 68, "yas": 25, "deger": 0.8, "kulup": "Qarabağ", "ulke": "İspanya"},
        {"isim": "Hikmat Cabrayilzada", "mevki": "MOO", "yetenek": 59, "yas": 19, "deger": 0.175, "kulup": "Qarabağ", "ulke": "Azerbaycan"},
        {"isim": "Taofeek Ismaheel", "mevki": "LW", "yetenek": 68, "yas": 26, "deger": 1.5, "kulup": "Qarabağ", "ulke": "Nijerya"},
        {"isim": "Jaly Mouaddib", "mevki": "LW", "yetenek": 63, "yas": 26, "deger": 0.55, "kulup": "Qarabağ", "ulke": "Fransa"},
        {"isim": "Zakaria Sawo", "mevki": "ST", "yetenek": 62, "yas": 26, "deger": 0.75, "kulup": "Qarabağ", "ulke": "Gambiya"},
        ],
"Neftçi PFK": [
        {"isim": "Rza Cafarov", "mevki": "KL", "yetenek": 65, "yas": 23, "deger": 0.6, "kulup": "Neftçi PFK", "ulke": "Azerbaycan"},
        {"isim": "Rüfat Abbasov", "mevki": "LB", "yetenek": 66, "yas": 21, "deger": 1.2, "kulup": "Neftçi PFK", "ulke": "Azerbaycan"},
        {"isim": "Andreaw Gravillon", "mevki": "CB", "yetenek": 71, "yas": 28, "deger": 0.5, "kulup": "Neftçi PFK", "ulke": "Guadeloupe"},
        {"isim": "Igor Ribeiro", "mevki": "CB", "yetenek": 67, "yas": 30, "deger": 0.85, "kulup": "Neftçi PFK", "ulke": "Brezilya"},
        {"isim": "Falaye Sacko", "mevki": "RB", "yetenek": 70, "yas": 31, "deger": 1, "kulup": "Neftçi PFK", "ulke": "Mali"},
        {"isim": "E.Mahmudov", "mevki": "MO", "yetenek": 68, "yas": 33, "deger": 0.45, "kulup": "Neftçi PFK", "ulke": "Azerbaycan"},
        {"isim": "Vicko Sevelj", "mevki": "MDO", "yetenek": 67, "yas": 26, "deger": 0.65, "kulup": "Neftçi PFK", "ulke": "Hırvatistan"},
        {"isim": "Ifeanyi Mathew", "mevki": "MO", "yetenek": 69, "yas": 29, "deger": 0.65, "kulup": "Neftçi PFK", "ulke": "Nijerya"},
        {"isim": "Andriy Shtogrin", "mevki": "LW", "yetenek": 76, "yas": 27, "deger": 0.35, "kulup": "Neftçi PFK", "ulke": "Ukrayna"},
        {"isim": "Lubomir Tupta", "mevki": "ST", "yetenek": 68, "yas": 28, "deger": 0.6, "kulup": "Neftçi PFK", "ulke": "Slovakya"},
        {"isim": "Dragoljub Savic", "mevki": "RW", "yetenek": 70, "yas": 25, "deger": 0.8, "kulup": "Neftçi PFK", "ulke": "Sırbistan"},
        {"isim": "Emil Balayev", "mevki": "KL", "yetenek": 62, "yas": 32, "deger": 0.15, "kulup": "Neftçi PFK", "ulke": "Azerbaycan"},
        {"isim": "Elvin Badalov", "mevki": "CB", "yetenek": 64, "yas": 31, "deger": 0.6, "kulup": "Neftçi PFK", "ulke": "Azerbaycan"},
        {"isim": "Murad Khachayev", "mevki": "CB", "yetenek": 64, "yas": 28, "deger": 0.45, "kulup": "Neftçi PFK", "ulke": "Azerbaycan"},
        {"isim": "Albert Gomez", "mevki": "CB", "yetenek": 62, "yas": 20, "deger": 0.05, "kulup": "Neftçi PFK", "ulke": "Gambiya"},
        {"isim": "Moustapha Seck", "mevki": "LB", "yetenek": 65, "yas": 30, "deger": 0.5, "kulup": "Neftçi PFK", "ulke": "İspanya"},
        {"isim": "Sessi D'Almeida", "mevki": "MDO", "yetenek": 66, "yas": 31, "deger": 0.4, "kulup": "Neftçi PFK", "ulke": "Benin"},
        {"isim": "Emil Safarov", "mevki": "MO", "yetenek": 66, "yas": 24, "deger": 0.5, "kulup": "Neftçi PFK", "ulke": "Azerbaycan"},
        {"isim": "Gustavo Klismahn", "mevki": "MO", "yetenek": 66, "yas": 27, "deger": 0.5, "kulup": "Neftçi PFK", "ulke": "Brezilya"},
        {"isim": "Freddy Vargas", "mevki": "LW", "yetenek": 67, "yas": 27, "deger": 0.9, "kulup": "Neftçi PFK", "ulke": "Venezuela"},
        {"isim": "Alen Skribek", "mevki": "LW", "yetenek": 64, "yas": 25, "deger": 0.4, "kulup": "Neftçi PFK", "ulke": "Macaristan"},
        {"isim": "Breno Almeida", "mevki": "RW", "yetenek": 67, "yas": 28, "deger": 0.6, "kulup": "Neftçi PFK", "ulke": "Brezilya"},
        {"isim": "Denzel Jubitana", "mevki": "ST", "yetenek": 66, "yas": 27, "deger": 0.6, "kulup": "Neftçi PFK", "ulke": "Surinam"},
        {"isim": "Bassala Sambou", "mevki": "ST", "yetenek": 65, "yas": 29, "deger": 0.4, "kulup": "Neftçi PFK", "ulke": "İngiltere"},
        {"isim": "Adeleke Akinyemi", "mevki": "ST", "yetenek": 63, "yas": 28, "deger": 0.25, "kulup": "Neftçi PFK", "ulke": "Nijerya"},
       ],
   #ENG Premier league
"Man. City": [
        {"isim": "G.Donnarumma", "mevki": "KL", "yetenek": 89, "yas": 27, "deger": 45, "kulup": "Man. City", "ulke": "İtalya"},
        {"isim": "J.Gvardiol", "mevki": "LB", "yetenek": 85, "yas": 24, "deger": 75, "kulup": "Man. City", "ulke": "Hırvatistan"},
        {"isim": "R.Dias", "mevki": "CB", "yetenek": 87, "yas": 28, "deger": 50, "kulup": "Man. City", "ulke": "Portekiz"},
        {"isim": "M.Guehi", "mevki": "CB", "yetenek": 85, "yas": 25, "deger": 75, "kulup": "Man. City", "ulke": "İngiltere"},
        {"isim": "Matheus Nunes", "mevki": "RB", "yetenek": 83, "yas": 28, "deger": 45, "kulup": "Man. City", "ulke": "Portekiz"},
        {"isim": "E.Fernandez", "mevki": "MO", "yetenek": 86, "yas": 25, "deger": 120, "kulup": "Man. City", "ulke": "Arjantin"},
        {"isim": "Elliot Anderson", "mevki": "MDO", "yetenek": 84, "yas": 24, "deger": 120, "kulup": "Man. City", "ulke": "İngiltere"},
        {"isim": "Mateo Kovacic", "mevki": "MO", "yetenek": 81, "yas": 32, "deger": 10, "kulup": "Man. City", "ulke": "Hırvatistan"},
        {"isim": "R.Cherki", "mevki": "LW", "yetenek": 86, "yas": 22, "deger": 110, "kulup": "Man. City", "ulke": "Fransa"},
        {"isim": "E.Haaland", "mevki": "ST", "yetenek": 91, "yas": 25, "deger": 220, "kulup": "Man. City", "ulke": "Norveç"},
        {"isim": "P.Foden", "mevki": "RW", "yetenek": 84, "yas": 25, "deger": 65, "kulup": "Man. City", "ulke": "İngiltere"},
        {"isim": "Gerónimo Rulli", "mevki": "KL", "yetenek": 80, "yas": 34, "deger": 5, "kulup": "Man. City", "ulke": "Arjantin"},
        {"isim": "Marcus Bettinelli", "mevki": "KL", "yetenek": 69, "yas": 34, "deger": 0.3, "kulup": "Man. City", "ulke": "İngiltere"},
        {"isim": "Abdukodir Khusanov", "mevki": "CB", "yetenek": 82, "yas": 22, "deger": 50, "kulup": "Man. City", "ulke": "Özbekistan"},
        {"isim": "Vitor Reis", "mevki": "CB", "yetenek": 76, "yas": 20, "deger": 30, "kulup": "Man. City", "ulke": "Brezilya"},
        {"isim": "Nico O'Reilly", "mevki": "LB", "yetenek": 83, "yas": 21, "deger": 70, "kulup": "Man. City", "ulke": "İngiltere"},
        {"isim": "Rayan Aït-Nouri", "mevki": "LB", "yetenek": 81, "yas": 25, "deger": 35, "kulup": "Man. City", "ulke": "Cezayir"},
        {"isim": "R.Lewis", "mevki": "RB", "yetenek": 77, "yas": 21, "deger": 25, "kulup": "Man. City", "ulke": "İngiltere"},
        {"isim": "Ayyoub Bouaddi", "mevki": "MDO", "yetenek": 80, "yas": 19, "deger": 90, "kulup": "Man. City", "ulke": "Fas"},
        {"isim": "Jérémy Doku", "mevki": "LW", "yetenek": 84, "yas": 24, "deger": 75, "kulup": "Man. City", "ulke": "Belçika"},
        {"isim": "Iliman Ndiaye", "mevki": "LW", "yetenek": 82, "yas": 26, "deger": 65, "kulup": "Man. City", "ulke": "Senegal"},
        {"isim": "Antoine Semenyo", "mevki": "RW", "yetenek": 85, "yas": 26, "deger": 80, "kulup": "Man. City", "ulke": "Gana"},
        {"isim": "Allan", "mevki": "RW", "yetenek": 77, "yas": 22, "deger": 30, "kulup": "Man. City", "ulke": "Brezilya"},
        {"isim": "Ryan McAidoo", "mevki": "RW", "yetenek": 66, "yas": 18, "deger": 8, "kulup": "Man. City", "ulke": "İngiltere"},
    ],
    "Man. Utd": [
        {"isim": "A.Lammens", "mevki": "KL", "yetenek": 82, "yas": 23, "deger": 35, "kulup": "Man. Utd", "ulke": "Belçika"},
        {"isim": "P.Dorgu", "mevki": "LB", "yetenek": 78, "yas": 21, "deger": 35, "kulup": "Man. Utd", "ulke": "Danimarka"},
        {"isim": "M.De Ligt", "mevki": "CB", "yetenek": 82, "yas": 26, "deger": 25, "kulup": "Man. Utd", "ulke": "Hollanda"},
        {"isim": "L.Martinez", "mevki": "CB", "yetenek": 82, "yas": 28, "deger": 45, "kulup": "Man. Utd", "ulke": "Arjantin"},
        {"isim": "Noussair Mazraoui", "mevki": "RB", "yetenek": 80, "yas": 29, "deger": 18, "kulup": "Man. Utd", "ulke": "Fas"},
        {"isim": "B.Fernandes", "mevki": "MOO", "yetenek": 89, "yas": 31, "deger": 35, "kulup": "Man. Utd", "ulke": "Portekiz"},
        {"isim": "Y.Tielemans", "mevki": "MO", "yetenek": 85, "yas": 28, "deger": 40, "kulup": "Man. Utd", "ulke": "Belçika"},
        {"isim": "K.Mainoo", "mevki": "MO", "yetenek": 81, "yas": 20, "deger": 75, "kulup": "Man. Utd", "ulke": "İngiltere"},
        {"isim": "Marcus Rashford", "mevki": "LW", "yetenek": 82, "yas": 29, "deger": 35, "kulup": "Man. Utd", "ulke": "İngiltere"},
        {"isim": "M.Cunha", "mevki": "ST", "yetenek": 84, "yas": 26, "deger": 75, "kulup": "Man. Utd", "ulke": "Brezilya"},
        {"isim": "B.Mbeumo", "mevki": "RW", "yetenek": 84, "yas": 26, "deger": 75, "kulup": "Man. Utd", "ulke": "Kamerun"},
        {"isim": "Karl Darlow", "mevki": "KL", "yetenek": 76, "yas": 36, "deger": 0.2, "kulup": "Man. Utd", "ulke": "Galler"},
        {"isim": "Tom Heaton", "mevki": "KL", "yetenek": 67, "yas": 40, "deger": 0.1, "kulup": "Man. Utd", "ulke": "İngiltere"},
        {"isim": "Dermot Mee", "mevki": "KL", "yetenek": 59, "yas": 24, "deger": 0.2, "kulup": "Man. Utd", "ulke": "Kuzey İrlanda"},
        {"isim": "Leny Yoro", "mevki": "CB", "yetenek": 78, "yas": 21, "deger": 45, "kulup": "Man. Utd", "ulke": "Fransa"},
        {"isim": "Ayden Heaven", "mevki": "CB", "yetenek": 75, "yas": 20, "deger": 30, "kulup": "Man. Utd", "ulke": "İngiltere"},
        {"isim": "Harry Maguire", "mevki": "CB", "yetenek": 82, "yas": 33, "deger": 8, "kulup": "Man. Utd", "ulke": "İngiltere"},
        {"isim": "Luke Shaw", "mevki": "LB", "yetenek": 79, "yas": 31, "deger": 8, "kulup": "Man. Utd", "ulke": "İngiltere"},
        {"isim": "Harry Amass", "mevki": "LB", "yetenek": 69, "yas": 19, "deger": 5, "kulup": "Man. Utd", "ulke": "İngiltere"},
        {"isim": "D.Dalot", "mevki": "RB", "yetenek": 78, "yas": 27, "deger": 30, "kulup": "Man. Utd", "ulke": "Portekiz"},
        {"isim": "C.Baleba", "mevki": "MDO", "yetenek": 80, "yas": 22, "deger": 65, "kulup": "Man. Utd", "ulke": "Kamerun"},
        {"isim": "Andrey Santos", "mevki": "MDO", "yetenek": 80, "yas": 22, "deger": 45, "kulup": "Man. Utd", "ulke": "Brezilya"},
        {"isim": "M.Ugarte", "mevki": "MDO", "yetenek": 77, "yas": 24, "deger": 20, "kulup": "Man. Utd", "ulke": "Uruguay"},
        {"isim": "Tyler Fletcher", "mevki": "MO", "yetenek": 65, "yas": 19, "deger": 2.5, "kulup": "Man. Utd", "ulke": "İskoçya"},
        {"isim": "Mason Mount", "mevki": "MOO", "yetenek": 78, "yas": 27, "deger": 25, "kulup": "Man. Utd", "ulke": "İngiltere"},
        {"isim": "Amad Diallo", "mevki": "RW", "yetenek": 79, "yas": 24, "deger": 45, "kulup": "Man. Utd", "ulke": "Fildişi Sahili"},
        {"isim": "Shea Lacey", "mevki": "RW", "yetenek": 65, "yas": 19, "deger": 12, "kulup": "Man. Utd", "ulke": "İngiltere"},
        {"isim": "B.Sesko", "mevki": "ST", "yetenek": 82, "yas": 22, "deger": 75, "kulup": "Man. Utd", "ulke": "Slovenya"},
        {"isim": "Joshua Zirkzee", "mevki": "ST", "yetenek": 77, "yas": 25, "deger": 20, "kulup": "Man. Utd", "ulke": "Hollanda"},
    ],
    "Arsenal": [
        {"isim": "D.Raya", "mevki": "KL", "yetenek": 88, "yas": 30, "deger": 30, "kulup": "Arsenal", "ulke": "İspanya"},
        {"isim": "R.Calafiori", "mevki": "LB", "yetenek": 82, "yas": 23, "deger": 65, "kulup": "Arsenal", "ulke": "İtalya"},
        {"isim": "Gabriel", "mevki": "CB", "yetenek": 89, "yas": 28, "deger": 75, "kulup": "Arsenal", "ulke": "Brezilya"},
        {"isim": "W.Saliba", "mevki": "CB", "yetenek": 88, "yas": 25, "deger": 100, "kulup": "Arsenal", "ulke": "Fransa"},
        {"isim": "Jurriën Timber", "mevki": "RB", "yetenek": 84, "yas": 25, "deger": 70, "kulup": "Arsenal", "ulke": "Hollanda"},
        {"isim": "M.Odegaard", "mevki": "MOO", "yetenek": 86, "yas": 27, "deger": 80, "kulup": "Arsenal", "ulke": "Norveç"},
        {"isim": "D.Rice", "mevki": "MDO", "yetenek": 88, "yas": 27, "deger": 120, "kulup": "Arsenal", "ulke": "İngiltere"},
        {"isim": "M.Zubimendi", "mevki": "MO", "yetenek": 84, "yas": 27, "deger": 65, "kulup": "Arsenal", "ulke": "İspanya"},
        {"isim": "E.Eze", "mevki": "LW", "yetenek": 84, "yas": 27, "deger": 60, "kulup": "Arsenal", "ulke": "İngiltere"},
        {"isim": "V.Gyökeres", "mevki": "ST", "yetenek": 86, "yas": 27, "deger": 55, "kulup": "Arsenal", "ulke": "İsveç"},
        {"isim": "B.Saka", "mevki": "RW", "yetenek": 87, "yas": 24, "deger": 110, "kulup": "Arsenal", "ulke": "İngiltere"},
        {"isim": "Illan Meslier", "mevki": "KL", "yetenek": 71, "yas": 26, "deger": 6, "kulup": "Arsenal", "ulke": "Fransa"},
        {"isim": "Kepa Arrizabalaga", "mevki": "KL", "yetenek": 78, "yas": 32, "deger": 5, "kulup": "Arsenal", "ulke": "İspanya"},
        {"isim": "Piero Hincapié", "mevki": "CB", "yetenek": 84, "yas": 24, "deger": 50, "kulup": "Arsenal", "ulke": "Ekvador"},
        {"isim": "E.Konsa", "mevki": "CB", "yetenek": 84, "yas": 28, "deger": 50, "kulup": "Arsenal", "ulke": "İngiltere"},
        {"isim": "Cristhian Mosquera", "mevki": "CB", "yetenek": 78, "yas": 22, "deger": 40, "kulup": "Arsenal", "ulke": "İspanya"},
        {"isim": "B.White", "mevki": "RB", "yetenek": 81, "yas": 28, "deger": 35, "kulup": "Arsenal", "ulke": "İngiltere"},
        {"isim": "Myles Lewis-Skelly", "mevki": "MDO", "yetenek": 78, "yas": 20, "deger": 65, "kulup": "Arsenal", "ulke": "İngiltere"},
        {"isim": "B.Guimaraes", "mevki": "MDO", "yetenek": 86, "yas": 28, "deger": 75, "kulup": "Arsenal", "ulke": "Brezilya"},
        {"isim": "Mikel Merino", "mevki": "MO", "yetenek": 83, "yas": 30, "deger": 25, "kulup": "Arsenal", "ulke": "İspanya"},
        {"isim": "Christos Tzolis", "mevki": "LW", "yetenek": 82, "yas": 24, "deger": 40, "kulup": "Arsenal", "ulke": "Yunanistan"},
        {"isim": "Max Dowman", "mevki": "RW", "yetenek": 70, "yas": 16, "deger": 50, "kulup": "Arsenal", "ulke": "İngiltere"},
        {"isim": "Noni Madueke", "mevki": "RW", "yetenek": 80, "yas": 24, "deger": 45, "kulup": "Arsenal", "ulke": "İngiltere"},
        {"isim": "K.Havertz", "mevki": "ST", "yetenek": 81, "yas": 26, "deger": 60, "kulup": "Arsenal", "ulke": "Almanya"},
    ],
    "Liverpool": [
        {"isim": "Alisson", "mevki": "KL", "yetenek": 87, "yas": 33, "deger": 15, "kulup": "Liverpool", "ulke": "Brezilya"},
        {"isim": "M.Kerkez", "mevki": "LB", "yetenek": 81, "yas": 22, "deger": 35, "kulup": "Liverpool", "ulke": "Macaristan"},
        {"isim": "V.Van Dijk", "mevki": "CB", "yetenek": 88, "yas": 34, "deger": 15, "kulup": "Liverpool", "ulke": "Hollanda"},
        {"isim": "Ronald Araújo", "mevki": "CB", "yetenek": 80, "yas": 27, "deger": 25, "kulup": "Liverpool", "ulke": "Uruguay"},
        {"isim": "J.Frimpong", "mevki": "RB", "yetenek": 81, "yas": 25, "deger": 30, "kulup": "Liverpool", "ulke": "Hollanda"},
        {"isim": "F.Wirtz", "mevki": "MOO", "yetenek": 86, "yas": 22, "deger": 85, "kulup": "Liverpool", "ulke": "Almanya"},
        {"isim": "Ryan Gravenberch", "mevki": "MDO", "yetenek": 85, "yas": 24, "deger": 75, "kulup": "Liverpool", "ulke": "Hollanda"},
        {"isim": "Szoboszlai", "mevki": "MOO", "yetenek": 86, "yas": 25, "deger": 100, "kulup": "Liverpool", "ulke": "Macaristan"},
        {"isim": "Bradley Barcola", "mevki": "LW", "yetenek": 85, "yas": 24, "deger": 100, "kulup": "Liverpool", "ulke": "Fransa"},
        {"isim": "H.Ekitike", "mevki": "ST", "yetenek": 85, "yas": 23, "deger": 80, "kulup": "Liverpool", "ulke": "Fransa"},
        {"isim": "Federico Chiesa", "mevki": "RW", "yetenek": 80, "yas": 29, "deger": 10, "kulup": "Liverpool", "ulke": "İtalya"},
        {"isim": "G.Mamardashvili", "mevki": "KL", "yetenek": 83, "yas": 25, "deger": 28, "kulup": "Liverpool", "ulke": "Gürcistan"},
        {"isim": "Vítězslav Jaroš", "mevki": "KL", "yetenek": 72, "yas": 25, "deger": 5, "kulup": "Liverpool", "ulke": "Çekya"},
        {"isim": "Freddie Woodman", "mevki": "KL", "yetenek": 71, "yas": 29, "deger": 3, "kulup": "Liverpool", "ulke": "İngiltere"},
        {"isim": "Harvey Davies", "mevki": "KL", "yetenek": 61, "yas": 23, "deger": 0.5, "kulup": "Liverpool", "ulke": "İngiltere"},
        {"isim": "Jérémy Jacquet", "mevki": "CB", "yetenek": 77, "yas": 21, "deger": 65, "kulup": "Liverpool", "ulke": "Fransa"},
        {"isim": "Giovanni Leoni", "mevki": "CB", "yetenek": 71, "yas": 19, "deger": 25, "kulup": "Liverpool", "ulke": "İtalya"},
        {"isim": "Joe Gomez", "mevki": "CB", "yetenek": 79, "yas": 29, "deger": 11, "kulup": "Liverpool", "ulke": "İngiltere"},
        {"isim": "Konstantinos Tsimikas", "mevki": "LB", "yetenek": 76, "yas": 30, "deger": 4.5, "kulup": "Liverpool", "ulke": "Yunanistan"},
        {"isim": "Luke Chambers", "mevki": "LB", "yetenek": 66, "yas": 22, "deger": 1, "kulup": "Liverpool", "ulke": "İngiltere"},
        {"isim": "Conor Bradley", "mevki": "RB", "yetenek": 79, "yas": 23, "deger": 20, "kulup": "Liverpool", "ulke": "Kuzey İrlanda"},
        {"isim": "Wataru Endo", "mevki": "MDO", "yetenek": 78, "yas": 33, "deger": 3, "kulup": "Liverpool", "ulke": "Japonya"},
        {"isim": "A.Mac Allister", "mevki": "MO", "yetenek": 84, "yas": 27, "deger": 70, "kulup": "Liverpool", "ulke": "Arjantin"},
        {"isim": "Trey Nyoni", "mevki": "MO", "yetenek": 67, "yas": 19, "deger": 18, "kulup": "Liverpool", "ulke": "İngiltere"},
        {"isim": "James McConnell", "mevki": "MO", "yetenek": 68, "yas": 22, "deger": 1.5, "kulup": "Liverpool", "ulke": "İngiltere"},
        {"isim": "Cody Gakpo", "mevki": "LW", "yetenek": 82, "yas": 27, "deger": 75, "kulup": "Liverpool", "ulke": "Hollanda"},
        {"isim": "Rio Ngumoha", "mevki": "LW", "yetenek": 75, "yas": 18, "deger": 50, "kulup": "Liverpool", "ulke": "İngiltere"},
        {"isim": "Víctor Muñoz", "mevki": "LW", "yetenek": 79, "yas": 23, "deger": 40, "kulup": "Liverpool", "ulke": "İspanya"},
        {"isim": "A.Isak", "mevki": "ST", "yetenek": 86, "yas": 26, "deger": 90, "kulup": "Liverpool", "ulke": "İsveç"},
        {"isim": "Lewis Koumas", "mevki": "ST", "yetenek": 69, "yas": 21, "deger": 8, "kulup": "Liverpool", "ulke": "Galler"},
        {"isim": "Jayden Danns", "mevki": "ST", "yetenek": 65, "yas": 20, "deger": 0.8, "kulup": "Liverpool", "ulke": "İngiltere"},
    ], 
"Chelsea": [
        {"isim": "E.Martinez", "mevki": "KL", "yetenek": 85, "yas": 33, "deger": 10, "kulup": "Chelsea", "ulke": "Arjantin"},
        {"isim": "Pep Chavarría", "mevki": "LB", "yetenek": 79, "yas": 28, "deger": 18, "kulup": "Chelsea", "ulke": "İspanya"},
        {"isim": "L.Colwill", "mevki": "CB", "yetenek": 80, "yas": 23, "deger": 50, "kulup": "Chelsea", "ulke": "İngiltere"},
        {"isim": "Maxence Lacroix", "mevki": "CB", "yetenek": 82, "yas": 26, "deger": 60, "kulup": "Chelsea", "ulke": "Fransa"},
        {"isim": "R.James", "mevki": "RB", "yetenek": 84, "yas": 26, "deger": 60, "kulup": "Chelsea", "ulke": "İngiltere"},
        {"isim": "C.Palmer", "mevki": "MOO", "yetenek": 85, "yas": 24, "deger": 110, "kulup": "Chelsea", "ulke": "İngiltere"},
        {"isim": "M.Caicedo", "mevki": "MDO", "yetenek": 86, "yas": 24, "deger": 100, "kulup": "Chelsea", "ulke": "Ekvador"},
        {"isim": "Valentín Barco", "mevki": "MO", "yetenek": 79, "yas": 22, "deger": 40, "kulup": "Chelsea", "ulke": "Arjantin"},
        {"isim": "Morgan Rogers", "mevki": "LW", "yetenek": 84, "yas": 24, "deger": 120, "kulup": "Chelsea", "ulke": "İngiltere"},
        {"isim": "J.Pedro", "mevki": "ST", "yetenek": 83, "yas": 24, "deger": 100, "kulup": "Chelsea", "ulke": "Brezilya"},
        {"isim": "Estevao", "mevki": "RW", "yetenek": 80, "yas": 19, "deger": 80, "kulup": "Chelsea", "ulke": "Brezilya"},
        {"isim": "Mike Penders", "mevki": "KL", "yetenek": 78, "yas": 21, "deger": 25, "kulup": "Chelsea", "ulke": "Belçika"},
        {"isim": "Gabriel Slonina", "mevki": "KL", "yetenek": 68, "yas": 22, "deger": 3, "kulup": "Chelsea", "ulke": "Amerika Birleşik Devletleri"},
        {"isim": "Teddy Sharman-Lowe", "mevki": "KL", "yetenek": 64, "yas": 23, "deger": 0.5, "kulup": "Chelsea", "ulke": "İngiltere"},
        {"isim": "Wesley Fofana", "mevki": "CB", "yetenek": 79, "yas": 25, "deger": 32, "kulup": "Chelsea", "ulke": "Fransa"},
        {"isim": "Josh Acheampong", "mevki": "CB", "yetenek": 75, "yas": 20, "deger": 30, "kulup": "Chelsea", "ulke": "İngiltere"},
        {"isim": "Aarón Anselmino", "mevki": "CB", "yetenek": 72, "yas": 21, "deger": 10, "kulup": "Chelsea", "ulke": "Arjantin"},
        {"isim": "J.Hato", "mevki": "CB", "yetenek": 78, "yas": 20, "deger": 45, "kulup": "Chelsea", "ulke": "Hollanda"},
        {"isim": "Marco Palestra", "mevki": "RB", "yetenek": 78, "yas": 21, "deger": 45, "kulup": "Chelsea", "ulke": "İtalya"},
        {"isim": "Malo Gusto", "mevki": "RB", "yetenek": 79, "yas": 23, "deger": 35, "kulup": "Chelsea", "ulke": "Fransa"},
        {"isim": "Roméo Lavia", "mevki": "MDO", "yetenek": 78, "yas": 22, "deger": 25, "kulup": "Chelsea", "ulke": "Belçika"},
        {"isim": "Mahdi Nicoll-Jazuli", "mevki": "MO", "yetenek": 69, "yas": 16, "deger": 2, "kulup": "Chelsea", "ulke": "İngiltere"},
        {"isim": "Jordan Henderson", "mevki": "MO", "yetenek": 78, "yas": 36, "deger": 1.2, "kulup": "Chelsea", "ulke": "İngiltere"},
        {"isim": "Jamie Gittens", "mevki": "LW", "yetenek": 77, "yas": 22, "deger": 25, "kulup": "Chelsea", "ulke": "İngiltere"},
        {"isim": "Pedro Neto", "mevki": "RW", "yetenek": 81, "yas": 26, "deger": 60, "kulup": "Chelsea", "ulke": "Portekiz"},
        {"isim": "Geovany Quenda", "mevki": "RW", "yetenek": 76, "yas": 19, "deger": 42, "kulup": "Chelsea", "ulke": "Portekiz"},
        {"isim": "Emmanuel Emegha", "mevki": "ST", "yetenek": 78, "yas": 23, "deger": 20, "kulup": "Chelsea", "ulke": "Hollanda"},
        {"isim": "Danny Welbeck", "mevki": "ST", "yetenek": 80, "yas": 35, "deger": 3, "kulup": "Chelsea", "ulke": "İngiltere"},
    ],
"Tottenham": [
        {"isim": "Antonín Kinský", "mevki": "KL", "yetenek": 77, "yas": 23, "deger": 18, "kulup": "Tottenham", "ulke": "Çekya"},
        {"isim": "D.Udogie", "mevki": "LB", "yetenek": 79, "yas": 23, "deger": 25, "kulup": "Tottenham", "ulke": "İtalya"},
        {"isim": "Marcos Senesi", "mevki": "CB", "yetenek": 82, "yas": 29, "deger": 20, "kulup": "Tottenham", "ulke": "Arjantin"},
        {"isim": "Micky van de Ven", "mevki": "CB", "yetenek": 81, "yas": 25, "deger": 50, "kulup": "Tottenham", "ulke": "Hollanda"},
        {"isim": "P.Porro", "mevki": "RB", "yetenek": 83, "yas": 26, "deger": 45, "kulup": "Tottenham", "ulke": "İspanya"},
        {"isim": "S.Tonali", "mevki": "MO", "yetenek": 85, "yas": 25, "deger": 90, "kulup": "Tottenham", "ulke": "İtalya"},
        {"isim": "Rodrigo Bentancur", "mevki": "MDO", "yetenek": 79, "yas": 29, "deger": 17, "kulup": "Tottenham", "ulke": "Uruguay"},
        {"isim": "J.Maddison", "mevki": "MOO", "yetenek": 82, "yas": 29, "deger": 17, "kulup": "Tottenham", "ulke": "İngiltere"},
        {"isim": "Sávio", "mevki": "LW", "yetenek": 80, "yas": 22, "deger": 50, "kulup": "Tottenham", "ulke": "Brezilya"},
        {"isim": "O.Marmoush", "mevki": "ST", "yetenek": 82, "yas": 27, "deger": 50, "kulup": "Tottenham", "ulke": "Mısır"},
        {"isim": "M.Kudus", "mevki": "RW", "yetenek": 81, "yas": 25, "deger": 45, "kulup": "Tottenham", "ulke": "Gana"},
        {"isim": "Martin Dúbravka", "mevki": "KL", "yetenek": 77, "yas": 37, "deger": 0.5, "kulup": "Tottenham", "ulke": "Slovakya"},
        {"isim": "Brandon Austin", "mevki": "KL", "yetenek": 67, "yas": 27, "deger": 0.5, "kulup": "Tottenham", "ulke": "İngiltere"},
        {"isim": "J.Van Hecke", "mevki": "CB", "yetenek": 81, "yas": 25, "deger": 60, "kulup": "Tottenham", "ulke": "Hollanda"},
        {"isim": "Tosin Adarabioyo", "mevki": "CB", "yetenek": 77, "yas": 29, "deger": 13, "kulup": "Tottenham", "ulke": "İngiltere"},
        {"isim": "Ben Davies", "mevki": "CB", "yetenek": 74, "yas": 33, "deger": 3, "kulup": "Tottenham", "ulke": "Galler"},
        {"isim": "Andrew Robertson", "mevki": "LB", "yetenek": 80, "yas": 32, "deger": 7, "kulup": "Tottenham", "ulke": "İskoçya"},
        {"isim": "Archie Gray", "mevki": "RB", "yetenek": 77, "yas": 20, "deger": 35, "kulup": "Tottenham", "ulke": "İngiltere"},
        {"isim": "Mateus Fernandes", "mevki": "MO", "yetenek": 80, "yas": 22, "deger": 70, "kulup": "Tottenham", "ulke": "Portekiz"},
        {"isim": "Lucas Bergvall", "mevki": "MO", "yetenek": 78, "yas": 20, "deger": 40, "kulup": "Tottenham", "ulke": "İsveç"},
        {"isim": "Conor Gallagher", "mevki": "MO", "yetenek": 78, "yas": 26, "deger": 32, "kulup": "Tottenham", "ulke": "İngiltere"},
        {"isim": "X.Simons", "mevki": "MOO", "yetenek": 81, "yas": 23, "deger": 40, "kulup": "Tottenham", "ulke": "Hollanda"},
        {"isim": "Dejan Kulusevski", "mevki": "MOO", "yetenek": 81, "yas": 26, "deger": 13, "kulup": "Tottenham", "ulke": "İsveç"},
        {"isim": "Mathys Tel", "mevki": "LW", "yetenek": 78, "yas": 21, "deger": 22, "kulup": "Tottenham", "ulke": "Fransa"},
        {"isim": "Wilson Odobert", "mevki": "LW", "yetenek": 78, "yas": 21, "deger": 18, "kulup": "Tottenham", "ulke": "Fransa"},
        {"isim": "Mykhaylo Mudryk", "mevki": "LW", "yetenek": 75, "yas": 25, "deger": 15, "kulup": "Tottenham", "ulke": "Ukrayna"},
        {"isim": "D.Solanke", "mevki": "ST", "yetenek": 79, "yas": 29, "deger": 25, "kulup": "Tottenham", "ulke": "İngiltere"},
        {"isim": "Richarlison", "mevki": "ST", "yetenek": 78, "yas": 29, "deger": 15, "kulup": "Tottenham", "ulke": "Brezilya"},
    ],
"Aston Villa": [
        {"isim": "Zion Suzuki", "mevki": "KL", "yetenek": 76, "yas": 24, "deger": 30, "kulup": "Aston Villa", "ulke": "Japonya"},
        {"isim": "I.Maatsen", "mevki": "LB", "yetenek": 79, "yas": 24, "deger": 35, "kulup": "Aston Villa", "ulke": "Hollanda"},
        {"isim": "P.Torres", "mevki": "CB", "yetenek": 81, "yas": 29, "deger": 20, "kulup": "Aston Villa", "ulke": "İspanya"},
        {"isim": "Victor Lindelöf", "mevki": "CB", "yetenek": 77, "yas": 32, "deger": 5, "kulup": "Aston Villa", "ulke": "İsveç"},
        {"isim": "M.Cash", "mevki": "RB", "yetenek": 81, "yas": 28, "deger": 22, "kulup": "Aston Villa", "ulke": "Polonya"},
        {"isim": "Boubacar Kamara", "mevki": "MDO", "yetenek": 84, "yas": 27, "deger": 50, "kulup": "Aston Villa", "ulke": "Fransa"},
        {"isim": "A.Onana", "mevki": "MDO", "yetenek": 81, "yas": 24, "deger": 40, "kulup": "Aston Villa", "ulke": "Belçika"},
        {"isim": "Leon Goretzka", "mevki": "MO", "yetenek": 81, "yas": 31, "deger": 10, "kulup": "Aston Villa", "ulke": "Almanya"},
        {"isim": "A.Garnacho", "mevki": "LW", "yetenek": 77, "yas": 21, "deger": 22, "kulup": "Aston Villa", "ulke": "Arjantin"},
        {"isim": "T.Abraham", "mevki": "ST", "yetenek": 77, "yas": 28, "deger": 18, "kulup": "Aston Villa", "ulke": "İngiltere"},
        {"isim": "John McGinn", "mevki": "RW", "yetenek": 83, "yas": 32, "deger": 13, "kulup": "Aston Villa", "ulke": "İskoçya"},
        {"isim": "Marco Bizot", "mevki": "KL", "yetenek": 77, "yas": 35, "deger": 1.5, "kulup": "Aston Villa", "ulke": "Hollanda"},
        {"isim": "James Wright", "mevki": "KL", "yetenek": 61, "yas": 21, "deger": 0.2, "kulup": "Aston Villa", "ulke": "İngiltere"},
        {"isim": "Taylor Harwood-Bellis", "mevki": "CB", "yetenek": 75, "yas": 24, "deger": 25, "kulup": "Aston Villa", "ulke": "İngiltere"},
        {"isim": "Modou Kéba Cissé", "mevki": "CB", "yetenek": 68, "yas": 21, "deger": 6, "kulup": "Aston Villa", "ulke": "Senegal"},
        {"isim": "Tyrone Mings", "mevki": "CB", "yetenek": 77, "yas": 33, "deger": 3, "kulup": "Aston Villa", "ulke": "İngiltere"},
        {"isim": "Matteo Ruggeri", "mevki": "LB", "yetenek": 78, "yas": 24, "deger": 28, "kulup": "Aston Villa", "ulke": "İtalya"},
        {"isim": "Aaron Wan-Bissaka", "mevki": "RB", "yetenek": 78, "yas": 28, "deger": 15, "kulup": "Aston Villa", "ulke": "Kongo Demokratik Cumhuriyeti"},
        {"isim": "Lamare Bogarde", "mevki": "MDO", "yetenek": 74, "yas": 22, "deger": 18, "kulup": "Aston Villa", "ulke": "Hollanda"},
        {"isim": "João Gomes", "mevki": "MO", "yetenek": 78, "yas": 25, "deger": 40, "kulup": "Aston Villa", "ulke": "Brezilya"},
        {"isim": "Ross Barkley", "mevki": "MO", "yetenek": 77, "yas": 32, "deger": 4, "kulup": "Aston Villa", "ulke": "İngiltere"},
        {"isim": "Johan Manzambi", "mevki": "MOO", "yetenek": 80, "yas": 21, "deger": 65, "kulup": "Aston Villa", "ulke": "İsviçre"},
        {"isim": "Emiliano Buendía", "mevki": "MOO", "yetenek": 80, "yas": 29, "deger": 16, "kulup": "Aston Villa", "ulke": "Arjantin"},
        {"isim": "George Hemmings", "mevki": "LW", "yetenek": 65, "yas": 19, "deger": 15, "kulup": "Aston Villa", "ulke": "İngiltere"},
        {"isim": "Ibrahim Mbaye", "mevki": "RW", "yetenek": 76, "yas": 18, "deger": 50, "kulup": "Aston Villa", "ulke": "Senegal"},
        {"isim": "Alysson", "mevki": "RW", "yetenek": 70, "yas": 20, "deger": 15, "kulup": "Aston Villa", "ulke": "Brezilya"},
        {"isim": "Nicolas Jackson", "mevki": "ST", "yetenek": 79, "yas": 25, "deger": 45, "kulup": "Aston Villa", "ulke": "Senegal"},
        {"isim": "Brian Madjo", "mevki": "ST", "yetenek": 65, "yas": 17, "deger": 22, "kulup": "Aston Villa", "ulke": "İngiltere"},
    ],
"Newcastle Utd.": [
        {"isim": "Nick Pope", "mevki": "KL", "yetenek": 78, "yas": 34, "deger": 3, "kulup": "Newcastle Utd.", "ulke": "İngiltere"},
        {"isim": "L.Hall", "mevki": "LB", "yetenek": 83, "yas": 21, "deger": 55, "kulup": "Newcastle Utd.", "ulke": "İngiltere"},
        {"isim": "S.Botman", "mevki": "CB", "yetenek": 81, "yas": 26, "deger": 35, "kulup": "Newcastle Utd.", "ulke": "Hollanda"},
        {"isim": "M.Thiaw", "mevki": "CB", "yetenek": 81, "yas": 24, "deger": 50, "kulup": "Newcastle Utd.", "ulke": "Almanya"},
        {"isim": "T.Livramento", "mevki": "RB", "yetenek": 81, "yas": 23, "deger": 45, "kulup": "Newcastle Utd.", "ulke": "İngiltere"},
        {"isim": "Joelinton", "mevki": "MO", "yetenek": 80, "yas": 30, "deger": 20, "kulup": "Newcastle Utd.", "ulke": "Brezilya"},
        {"isim": "Nicolás González Iglesias", "mevki": "MDO", "yetenek": 81, "yas": 24, "deger": 50, "kulup": "Newcastle Utd.", "ulke": "İspanya"},
        {"isim": "J.Ramsey", "mevki": "MO", "yetenek": 78, "yas": 24, "deger": 35, "kulup": "Newcastle Utd.", "ulke": "İngiltere"},
        {"isim": "Harvey Barnes", "mevki": "LW", "yetenek": 80, "yas": 28, "deger": 35, "kulup": "Newcastle Utd.", "ulke": "İngiltere"},
        {"isim": "Y.Wissa", "mevki": "ST", "yetenek": 80, "yas": 29, "deger": 25, "kulup": "Newcastle Utd.", "ulke": "Kongo Demokratik Cumhuriyeti"},
        {"isim": "Jacob Murphy", "mevki": "RW", "yetenek": 79, "yas": 31, "deger": 10, "kulup": "Newcastle Utd.", "ulke": "İngiltere"},
        {"isim": "Lukas Hornicek", "mevki": "KL", "yetenek": 77, "yas": 24, "deger": 27, "kulup": "Newcastle Utd.", "ulke": "Çekya"},
        {"isim": "Ewen Jaouen", "mevki": "KL", "yetenek": 70, "yas": 20, "deger": 18, "kulup": "Newcastle Utd.", "ulke": "Fransa"},
        {"isim": "Mark Gillespie", "mevki": "KL", "yetenek": 62, "yas": 34, "deger": 0.1, "kulup": "Newcastle Utd.", "ulke": "İngiltere"},
        {"isim": "Dan Burn", "mevki": "CB", "yetenek": 79, "yas": 34, "deger": 4, "kulup": "Newcastle Utd.", "ulke": "İngiltere"},
        {"isim": "Fabian Schär", "mevki": "CB", "yetenek": 81, "yas": 34, "deger": 3, "kulup": "Newcastle Utd.", "ulke": "İsviçre"},
        {"isim": "Amar Dedic", "mevki": "RB", "yetenek": 76, "yas": 24, "deger": 30, "kulup": "Newcastle Utd.", "ulke": "Bosna-Hersek"},
        {"isim": "Aladji Bamba", "mevki": "MDO", "yetenek": 72, "yas": 20, "deger": 25, "kulup": "Newcastle Utd.", "ulke": "Fransa"},
        {"isim": "Lewis Miley", "mevki": "MO", "yetenek": 77, "yas": 20, "deger": 30, "kulup": "Newcastle Utd.", "ulke": "İngiltere"},
        {"isim": "Sean Steur", "mevki": "MO", "yetenek": 72, "yas": 18, "deger": 22, "kulup": "Newcastle Utd.", "ulke": "Hollanda"},
        {"isim": "Joe Willock", "mevki": "MO", "yetenek": 76, "yas": 27, "deger": 18, "kulup": "Newcastle Utd.", "ulke": "İngiltere"},
        {"isim": "Bazoumana Touré", "mevki": "LW", "yetenek": 78, "yas": 20, "deger": 50, "kulup": "Newcastle Utd.", "ulke": "Fildişi Sahili"},
        {"isim": "Anthony Elanga", "mevki": "RW", "yetenek": 79, "yas": 24, "deger": 35, "kulup": "Newcastle Utd.", "ulke": "İsveç"},
        {"isim": "Matias Fernandez-Pardo", "mevki": "ST", "yetenek": 78, "yas": 21, "deger": 55, "kulup": "Newcastle Utd.", "ulke": "Belçika"},
        {"isim": "William Osula", "mevki": "ST", "yetenek": 75, "yas": 23, "deger": 32, "kulup": "Newcastle Utd.", "ulke": "Danimarka"},
    ],
"Brighton": [
        {"isim": "B.Verbruggen", "mevki": "KL", "yetenek": 81, "yas": 23, "deger": 40, "kulup": "Brighton", "ulke": "Hollanda"},
        {"isim": "M.De Cuyper", "mevki": "LB", "yetenek": 78, "yas": 25, "deger": 30, "kulup": "Brighton", "ulke": "Belçika"},
        {"isim": "Luka Vuskovic", "mevki": "CB", "yetenek": 81, "yas": 19, "deger": 65, "kulup": "Brighton", "ulke": "Hırvatistan"},
        {"isim": "O.Boscagli", "mevki": "CB", "yetenek": 78, "yas": 28, "deger": 20, "kulup": "Brighton", "ulke": "Fransa"},
        {"isim": "F.Kadioglu", "mevki": "RB", "yetenek": 80, "yas": 26, "deger": 40, "face": "ferdikadıoğlu.jpeg", "kulup": "Brighton", "ulke": "Türkiye"},
        {"isim": "P.Gross", "mevki": "MO", "yetenek": 79, "yas": 34, "deger": 2.5, "kulup": "Brighton", "ulke": "Almanya"},
        {"isim": "Jack Hinshelwood", "mevki": "MDO", "yetenek": 77, "yas": 21, "deger": 35, "kulup": "Brighton", "ulke": "İngiltere"},
        {"isim": "Yasin Ayari", "mevki": "MO", "yetenek": 79, "yas": 23, "deger": 45, "kulup": "Brighton", "ulke": "İsveç"},
        {"isim": "K.Mitoma", "mevki": "LW", "yetenek": 81, "yas": 28, "deger": 22, "kulup": "Brighton", "ulke": "Japonya"},
        {"isim": "Promise David", "mevki": "ST", "yetenek": 76, "yas": 25, "deger": 20, "kulup": "Brighton", "ulke": "Kanada"},
        {"isim": "Y.Minteh", "mevki": "RW", "yetenek": 80, "yas": 21, "deger": 55, "kulup": "Brighton", "ulke": "Gambiya"},
        {"isim": "Jason Steele", "mevki": "KL", "yetenek": 73, "yas": 36, "deger": 0.5, "kulup": "Brighton", "ulke": "İngiltere"},
        {"isim": "Tom McGill", "mevki": "KL", "yetenek": 62, "yas": 26, "deger": 0.5, "kulup": "Brighton", "ulke": "Kanada"},
        {"isim": "Pascal Struijk", "mevki": "CB", "yetenek": 76, "yas": 27, "deger": 22, "kulup": "Brighton", "ulke": "Hollanda"},
        {"isim": "Michael Svoboda", "mevki": "CB", "yetenek": 72, "yas": 28, "deger": 5, "kulup": "Brighton", "ulke": "Avusturya"},
        {"isim": "Lewis Dunk", "mevki": "CB", "yetenek": 77, "yas": 35, "deger": 3.5, "kulup": "Brighton", "ulke": "İngiltere"},
        {"isim": "Jaouen Hadjam", "mevki": "LB", "yetenek": 74, "yas": 23, "deger": 10, "kulup": "Brighton", "ulke": "Cezayir"},
        {"isim": "Mats Wieffer", "mevki": "RB", "yetenek": 79, "yas": 27, "deger": 25, "kulup": "Brighton", "ulke": "Hollanda"},
        {"isim": "Costinha", "mevki": "RB", "yetenek": 75, "yas": 26, "deger": 10, "kulup": "Brighton", "ulke": "Portekiz"},
        {"isim": "Chema Andrés", "mevki": "MDO", "yetenek": 74, "yas": 21, "deger": 24, "kulup": "Brighton", "ulke": "İspanya"},
        {"isim": "Diego Gómez", "mevki": "MO", "yetenek": 78, "yas": 23, "deger": 30, "kulup": "Brighton", "ulke": "Paraguay"},
        {"isim": "Malick Yalcouyé", "mevki": "MO", "yetenek": 70, "yas": 21, "deger": 22, "kulup": "Brighton", "ulke": "Fildişi Sahili"},
        {"isim": "Matt O'Riley", "mevki": "MO", "yetenek": 77, "yas": 26, "deger": 18, "kulup": "Brighton", "ulke": "Danimarka"},
        {"isim": "Ibrahim Osman", "mevki": "LW", "yetenek": 72, "yas": 21, "deger": 12, "kulup": "Brighton", "ulke": "Gana"},
        {"isim": "Zadok Yohanna", "mevki": "RW", "yetenek": 67, "yas": 19, "deger": 25, "kulup": "Brighton", "ulke": "Nijerya"},
        {"isim": "Femi Azeez", "mevki": "RW", "yetenek": 75, "yas": 25, "deger": 15, "kulup": "Brighton", "ulke": "Nijerya"},
        {"isim": "Charalampos Kostoulas", "mevki": "ST", "yetenek": 73, "yas": 19, "deger": 40, "kulup": "Brighton", "ulke": "Yunanistan"},
        {"isim": "G.Rutter", "mevki": "MOO", "yetenek": 77, "yas": 23, "deger": 30, "kulup": "Brighton", "ulke": "Fransa"},
        {"isim": "S.Tzimas", "mevki": "ST", "yetenek": 73, "yas": 20, "deger": 18, "kulup": "Brighton", "ulke": "Yunanistan"},
        {"isim": "Evan Ferguson", "mevki": "ST", "yetenek": 74, "yas": 22, "deger": 15, "kulup": "Brighton", "ulke": "İrlanda"},
    ],
"Nottingham Frst.": [
        {"isim": "Matz Sels", "mevki": "KL", "yetenek": 81, "yas": 34, "deger": 3.5, "kulup": "Nottingham Frst.", "ulke": "Belçika"},
        {"isim": "L.Netz", "mevki": "LB", "yetenek": 73, "yas": 22, "deger": 8, "kulup": "Nottingham Frst.", "ulke": "Almanya"},
        {"isim": "Murillo", "mevki": "CB", "yetenek": 82, "yas": 23, "deger": 50, "kulup": "Nottingham Frst.", "ulke": "Brezilya"},
        {"isim": "N.Milenkovic", "mevki": "CB", "yetenek": 80, "yas": 28, "deger": 28, "kulup": "Nottingham Frst.", "ulke": "Sırbistan"},
        {"isim": "Daniel Muñoz", "mevki": "RB", "yetenek": 82, "yas": 30, "deger": 22, "kulup": "Nottingham Frst.", "ulke": "Kolombiya"},
        {"isim": "M.Gibbs-White", "mevki": "MOO", "yetenek": 83, "yas": 26, "deger": 80, "kulup": "Nottingham Frst.", "ulke": "İngiltere"},
        {"isim": "I.Sangare", "mevki": "MDO", "yetenek": 78, "yas": 28, "deger": 20, "kulup": "Nottingham Frst.", "ulke": "Fildişi Sahili"},
        {"isim": "Nicolás Domínguez", "mevki": "MO", "yetenek": 78, "yas": 28, "deger": 13, "kulup": "Nottingham Frst.", "ulke": "Arjantin"},
        {"isim": "C.Hudson-Odoi", "mevki": "LW", "yetenek": 78, "yas": 25, "deger": 25, "kulup": "Nottingham Frst.", "ulke": "İngiltere"},
        {"isim": "C.Wood", "mevki": "ST", "yetenek": 81, "yas": 34, "deger": 4, "kulup": "Nottingham Frst.", "ulke": "Yeni Zelanda"},
        {"isim": "Dan Ndoye", "mevki": "RW", "yetenek": 77, "yas": 26, "deger": 35, "kulup": "Nottingham Frst.", "ulke": "İsviçre"},
        {"isim": "John Victor", "mevki": "KL", "yetenek": 71, "yas": 30, "deger": 3.5, "kulup": "Nottingham Frst.", "ulke": "Brezilya"},
        {"isim": "Steven Benda", "mevki": "KL", "yetenek": 68, "yas": 28, "deger": 1, "kulup": "Nottingham Frst.", "ulke": "Almanya"},
        {"isim": "Ousmane Diomande", "mevki": "CB", "yetenek": 81, "yas": 22, "deger": 42, "kulup": "Nottingham Frst.", "ulke": "Fildişi Sahili"},
        {"isim": "Jair Cunha", "mevki": "CB", "yetenek": 75, "yas": 21, "deger": 25, "kulup": "Nottingham Frst.", "ulke": "Brezilya"},
        {"isim": "N.Williams", "mevki": "RB", "yetenek": 80, "yas": 24, "deger": 32, "kulup": "Nottingham Frst.", "ulke": "Galler"},
        {"isim": "Ola Aina", "mevki": "RB", "yetenek": 79, "yas": 30, "deger": 18, "kulup": "Nottingham Frst.", "ulke": "Nijerya"},
        {"isim": "Nicolò Savona", "mevki": "RB", "yetenek": 75, "yas": 23, "deger": 15, "kulup": "Nottingham Frst.", "ulke": "İtalya"},
        {"isim": "J.McAtee", "mevki": "MOO", "yetenek": 73, "yas": 23, "deger": 22, "kulup": "Nottingham Frst.", "ulke": "İngiltere"},
        {"isim": "Xaver Schlager", "mevki": "MO", "yetenek": 78, "yas": 29, "deger": 15, "kulup": "Nottingham Frst.", "ulke": "Avusturya"},
        {"isim": "Ryan Yates", "mevki": "MO", "yetenek": 75, "yas": 29, "deger": 7, "kulup": "Nottingham Frst.", "ulke": "İngiltere"},
        {"isim": "Liam Delap", "mevki": "ST", "yetenek": 77, "yas": 23, "deger": 40, "kulup": "Nottingham Frst.", "ulke": "İngiltere"},
        {"isim": "Igor Jesus", "mevki": "ST", "yetenek": 77, "yas": 25, "deger": 25, "kulup": "Nottingham Frst.", "ulke": "Brezilya"},
        {"isim": "Arnaud Kalimuendo", "mevki": "ST", "yetenek": 78, "yas": 24, "deger": 20, "kulup": "Nottingham Frst.", "ulke": "Fransa"},
    ],
    #Bundesliga
    "Bayern Munchen": [
        {"isim": "M.Neuer", "mevki": "GK", "yetenek": 81, "yas": 37, "deger": 4, "kulup": "Bayern Munchen", "ulke": "Almanya"},
        {"isim": "A.Davies", "mevki": "LB", "yetenek": 82, "yas": 32, "deger": 45, "kulup": "Bayern Munchen", "ulke": "Kanada"},
        {"isim": "J.Tah", "mevki": "CB", "yetenek": 87, "yas": 29, "deger": 28, "kulup": "Bayern Munchen", "ulke": "Almanya"},
        {"isim": "Dayot Upamecano", "mevki": "CB", "yetenek": 87, "yas": 28, "deger": 75, "kulup": "Bayern Munchen", "ulke": "Fransa"},
        {"isim": "J.Kimmich", "mevki": "RB", "yetenek": 88, "yas": 29, "deger": 35, "kulup": "Bayern Munchen", "ulke": "Almanya"},
        {"isim": "Jamal Musiala", "mevki": "MOO", "yetenek": 87, "yas": 23, "deger": 80, "kulup": "Bayern Munchen", "ulke": "Almanya"},
        {"isim": "Aleksandar Pavlovic", "mevki": "MDO", "yetenek": 83, "yas": 22, "deger": 90, "kulup": "Bayern Munchen", "ulke": "Almanya"},
        {"isim": "Ismael Saibari", "mevki": "MOO", "yetenek": 83, "yas": 25, "deger": 55, "kulup": "Bayern Munchen", "ulke": "Fas"},
        {"isim": "L.Diaz", "mevki": "LW", "yetenek": 88, "yas": 30, "deger": 70, "kulup": "Bayern Munchen", "ulke": "Kolombiya"},
        {"isim": "Harry Kane", "mevki": "ST", "yetenek": 90, "yas": 33, "deger": 60, "kulup": "Bayern Munchen", "ulke": "İngiltere"},
        {"isim": "M.Olise", "mevki": "RW", "yetenek": 90, "yas": 24, "deger": 180, "kulup": "Bayern Munchen", "ulke": "Fransa"},
        {"isim": "Jonas Urbig", "mevki": "KL", "yetenek": 79, "yas": 23, "deger": 18, "kulup": "Bayern Munchen", "ulke": "Almanya"},
        {"isim": "Sven Ulreich", "mevki": "KL", "yetenek": 73, "yas": 38, "deger": 0.5, "kulup": "Bayern Munchen", "ulke": "Almanya"},
        {"isim": "Min-jae Kim", "mevki": "CB", "yetenek": 83, "yas": 30, "deger": 20, "kulup": "Bayern Munchen", "ulke": "Güney Kore"},
        {"isim": "Hiroki Ito", "mevki": "CB", "yetenek": 78, "yas": 27, "deger": 18, "kulup": "Bayern Munchen", "ulke": "Japonya"},
        {"isim": "Nathaniel Brown", "mevki": "LB", "yetenek": 81, "yas": 23, "deger": 50, "kulup": "Bayern Munchen", "ulke": "Almanya"},
        {"isim": "Josip Stanisic", "mevki": "RB", "yetenek": 80, "yas": 26, "deger": 40, "kulup": "Bayern Munchen", "ulke": "Hırvatistan"},
        {"isim": "Konrad Laimer", "mevki": "RB", "yetenek": 85, "yas": 29, "deger": 32, "kulup": "Bayern Munchen", "ulke": "Avusturya"},
        {"isim": "S.Boey", "mevki": "RB", "yetenek": 75, "yas": 25, "deger": 7, "kulup": "Bayern Munchen", "ulke": "Fransa"},
        {"isim": "Tom Bischof", "mevki": "MO", "yetenek": 79, "yas": 21, "deger": 45, "kulup": "Bayern Munchen", "ulke": "Almanya"},
        {"isim": "Bara Sapoko Ndiaye", "mevki": "MO", "yetenek": 64, "yas": 18, "deger": 8, "kulup": "Bayern Munchen", "ulke": "Senegal"},
        {"isim": "Karl", "mevki": "MOO", "yetenek": 77, "yas": 18, "deger": 60, "kulup": "Bayern Munchen", "ulke": "Almanya"},
        {"isim": "Serge Gnabry", "mevki": "ST", "yetenek": 83, "yas": 31, "deger": 18, "kulup": "Bayern Munchen", "ulke": "Almanya"},
    ],
    #LaLiga Santander
"Real Madrid": [
        {"isim": "Cuortois", "mevki": "KL", "yetenek": 90, "yas": 33, "deger": 15, "kulup": "Real Madrid", "ulke": "Belçika"},
        {"isim": "M.Cucurella", "mevki": "LB", "yetenek": 86, "yas": 27, "deger": 60, "kulup": "Real Madrid", "ulke": "İspanya"},
        {"isim": "E.Militao", "mevki": "CB", "yetenek": 84, "yas": 28, "deger": 18, "kulup": "Real Madrid", "ulke": "Brezilya"},
        {"isim": "I.Konate", "mevki": "CB", "yetenek": 84, "yas": 26, "deger": 45, "kulup": "Real Madrid", "ulke": "Fransa"},
        {"isim": "T. A. Arnold", "mevki": "RB", "yetenek": 84, "yas": 27, "deger": 60, "kulup": "Real Madrid", "ulke": "İngiltere"},
        {"isim": "J.Bellingham", "mevki": "MO", "yetenek": 90, "yas": 22, "deger": 160, "kulup": "Real Madrid", "ulke": "İngiltere"},
        {"isim": "Fede Valverde", "mevki": "MDO", "yetenek": 87, "yas": 27, "deger": 90, "kulup": "Real Madrid", "ulke": "Uruguay"},
        {"isim": "Arda Güler", "mevki": "MOO", "yetenek": 83, "yas": 21, "deger": 100, "kulup": "Real Madrid", "ulke": "Türkiye"},
        {"isim": "Vinicius", "mevki": "LW", "yetenek": 89, "yas": 25, "deger": 130, "kulup": "Real Madrid", "ulke": "Brezilya"},
        {"isim": "K.Mbappe", "mevki": "ST", "yetenek": 91, "yas": 27, "deger": 200, "kulup": "Real Madrid", "ulke": "Fransa"},
        {"isim": "Rodrygo", "mevki": "RW", "yetenek": 84, "yas": 25, "deger": 45, "kulup": "Real Madrid", "ulke": "Brezilya"},
        {"isim": "Andriy Lunin", "mevki": "KL", "yetenek": 80, "yas": 27, "deger": 12, "kulup": "Real Madrid", "ulke": "Ukrayna"},
        {"isim": "D.Huijsen", "mevki": "CB", "yetenek": 81, "yas": 20, "deger": 60, "kulup": "Real Madrid", "ulke": "İspanya"},
        {"isim": "Raúl Asencio", "mevki": "CB", "yetenek": 78, "yas": 23, "deger": 18, "kulup": "Real Madrid", "ulke": "İspanya"},
        {"isim": "Antonio Rüdiger", "mevki": "CB", "yetenek": 83, "yas": 33, "deger": 6, "kulup": "Real Madrid", "ulke": "Almanya"},
        {"isim": "A.Carrerias", "mevki": "LB", "yetenek": 81, "yas": 22, "deger": 50, "kulup": "Real Madrid", "ulke": "İspanya"},
        {"isim": "Ferland Mendy", "mevki": "LB", "yetenek": 80, "yas": 31, "deger": 4, "kulup": "Real Madrid", "ulke": "Fransa"},
        {"isim": "Denzel Dumfries", "mevki": "RB", "yetenek": 83, "yas": 30, "deger": 25, "kulup": "Real Madrid", "ulke": "Hollanda"},
        {"isim": "Aurélien Tchouaméni", "mevki": "MDO", "yetenek": 84, "yas": 26, "deger": 70, "kulup": "Real Madrid", "ulke": "Fransa"},
        {"isim": "Eduardo Camavinga", "mevki": "MO", "yetenek": 81, "yas": 24, "deger": 50, "kulup": "Real Madrid", "ulke": "Fransa"},
        {"isim": "Thiago Pitarch", "mevki": "MO", "yetenek": 70, "yas": 19, "deger": 20, "kulup": "Real Madrid", "ulke": "İspanya"},
        {"isim": "B.Silva", "mevki": "MOO", "yetenek": 84, "yas": 31, "deger": 22, "kulup": "Real Madrid", "ulke": "Portekiz"},
        {"isim": "Yan Diomande", "mevki": "RW", "yetenek": 84, "yas": 20, "deger": 120, "kulup": "Real Madrid", "ulke": "Fildişi Sahili"},
        {"isim": "Brahim Díaz", "mevki": "RW", "yetenek": 81, "yas": 27, "deger": 35, "kulup": "Real Madrid", "ulke": "Fas"},
        {"isim": "Endrick", "mevki": "ST", "yetenek": 79, "yas": 20, "deger": 40, "kulup": "Real Madrid", "ulke": "Brezilya"},
        {"isim": "Carlos Espí", "mevki": "ST", "yetenek": 77, "yas": 21, "deger": 40, "kulup": "Real Madrid", "ulke": "İspanya"},
    ],
    #SERI A ITALY
"Juventus": [
        {"isim": "Kamil Grabara", "mevki": "KL", "yetenek": 81, "yas": 27, "deger": 12, "kulup": "Juventus", "ulke": "Polonya"},
        {"isim": "Andrea Cambiaso", "mevki": "LB", "yetenek": 80, "yas": 26, "deger": 15, "kulup": "Juventus", "ulke": "İtalya"},
        {"isim": "Bremer", "mevki": "CB", "yetenek": 86, "yas": 29, "deger": 35, "kulup": "Juventus", "ulke": "Brezilya"},
        {"isim": "F.Gatti", "mevki": "CB", "yetenek": 79, "yas": 27, "deger": 10, "kulup": "Juventus", "ulke": "İtalya"},
        {"isim": "Zeki Çelik", "mevki": "RB", "yetenek": 79, "yas": 29, "deger": 14, "kulup": "Juventus", "ulke": "Türkiye"},
        {"isim": "M.Locatelli", "mevki": "MDO", "yetenek": 84, "yas": 28, "deger": 25, "kulup": "Juventus", "ulke": "İtalya"},
        {"isim": "McKennie", "mevki": "MDO", "yetenek": 80, "yas": 27, "deger": 30, "kulup": "Juventus", "ulke": "Amerika Birleşik Devletleri"},
        {"isim": "K.Thuram", "mevki": "MO", "yetenek": 81, "yas": 24, "deger": 35, "kulup": "Juventus", "ulke": "Fransa"},
        {"isim": "Kenan Yıldız", "mevki": "LW", "yetenek": 84, "yas": 20, "deger": 75, "kulup": "Juventus", "ulke": "Türkiye"},
        {"isim": "N.Woltemade", "mevki": "ST", "yetenek": 80, "yas": 24, "deger": 50, "kulup": "Juventus", "ulke": "Almanya"},
        {"isim": "Conceicao", "mevki": "RW", "yetenek": 80, "yas": 23, "deger": 30, "kulup": "Juventus", "ulke": "Portekiz"},
        {"isim": "G.Vicario", "mevki": "KL", "yetenek": 80, "yas": 29, "deger": 12, "kulup": "Juventus", "ulke": "İtalya"},
        {"isim": "Neto", "mevki": "KL", "yetenek": 72, "yas": 37, "deger": 0.9, "kulup": "Juventus", "ulke": "Brezilya"},
        {"isim": "Carlo Pinsoglio", "mevki": "KL", "yetenek": 68, "yas": 36, "deger": 0.2, "kulup": "Juventus", "ulke": "İtalya"},
        {"isim": "Pierre Kalulu", "mevki": "CB", "yetenek": 81, "yas": 26, "deger": 32, "kulup": "Juventus", "ulke": "Fransa"},
        {"isim": "Lloyd Kelly", "mevki": "CB", "yetenek": 77, "yas": 28, "deger": 23, "kulup": "Juventus", "ulke": "İngiltere"},
        {"isim": "Jhon Lucumí", "mevki": "CB", "yetenek": 76, "yas": 28, "deger": 22, "kulup": "Juventus", "ulke": "Kolombiya"},
        {"isim": "Daniele Rugani", "mevki": "CB", "yetenek": 74, "yas": 32, "deger": 2, "kulup": "Juventus", "ulke": "İtalya"},
        {"isim": "Juan Cabal", "mevki": "LB", "yetenek": 74, "yas": 25, "deger": 7, "kulup": "Juventus", "ulke": "Kolombiya"},
        {"isim": "Pape Matar Sarr", "mevki": "MO", "yetenek": 79, "yas": 24, "deger": 30, "kulup": "Juventus", "ulke": "Senegal"},
        {"isim": "Douglas Luiz", "mevki": "MO", "yetenek": 78, "yas": 28, "deger": 18, "kulup": "Juventus", "ulke": "Brezilya"},
        {"isim": "Teun Koopmeiners", "mevki": "MO", "yetenek": 78, "yas": 28, "deger": 14, "kulup": "Juventus", "ulke": "Hollanda"},
        {"isim": "Kerim Alajbegovic", "mevki": "LW", "yetenek": 71, "yas": 19, "deger": 32, "kulup": "Juventus", "ulke": "Bosna-Hersek"},
        {"isim": "Nicolás Iván González", "mevki": "LW", "yetenek": 79, "yas": 28, "deger": 22, "kulup": "Juventus", "ulke": "Arjantin"},
        {"isim": "Jérémie Boga", "mevki": "LW", "yetenek": 78, "yas": 29, "deger": 8, "kulup": "Juventus", "ulke": "Fildişi Sahili"},
        {"isim": "Edon Zhegrova", "mevki": "RW", "yetenek": 78, "yas": 27, "deger": 10, "kulup": "Juventus", "ulke": "Kosova"},
        {"isim": "R.Kolo Muani", "mevki": "ST", "yetenek": 77, "yas": 27, "deger": 30, "kulup": "Juventus", "ulke": "Fransa"},
        {"isim": "Jeff Ekhator", "mevki": "ST", "yetenek": 68, "yas": 20, "deger": 18, "kulup": "Juventus", "ulke": "İtalya"},
        {"isim": "Arkadiusz Milik", "mevki": "ST", "yetenek": 76, "yas": 32, "deger": 1.5, "kulup": "Juventus", "ulke": "Polonya"},
    ]



}

def avrupa_kulubu_olustur(ad, ekstra=None):
    kulup = {"ad": ad, "p": 0, "attigi_gol": 0, "yedigi_gol": 0, "elenme_durumu": "Aktif"}
    if ekstra:
        kulup.update(ekstra)
        kulup.setdefault("p", 0)
        kulup.setdefault("attigi_gol", 0)
        kulup.setdefault("yedigi_gol", 0)
        kulup.setdefault("elenme_durumu", "Aktif")
    return kulup


TEMEL_AVRUPA_KULUP_ADLARI = [
    "Atletich Club",
    "Frankfurt",
    "Ajax",
    "Bodø/Glimt",
    "Union SG",
    "PSV",
    "Losc Lille",
    "Fenerbahçe",
    "Newcastle Utd.",
    "Club Brugge",
    "Benfica",
    "Monaco",
    "Villarreal",
    "Kairat Almaty",
    "Slavia Prag",
    "Copenhagen",
    "Pafos",
    "Tottenham",
    "B. Dortmund",
    "Sporting CP",
    "PSG",
    "Chealse",
    "Atalanta",
    "Bayern Munchen",
    "Arsenal",
    "Napoli",
    "Milan",
    "Inter Milan",
    "Sabah",
    "Real Madrid",
    "Man. City",
    "Liverpool",
    "Barcelona",
    "Atletico Madrid",
    "Juventus",
    "Galatasaray"
]

AVRUPA_KULUPLER = [avrupa_kulubu_olustur(ad) for ad in TEMEL_AVRUPA_KULUP_ADLARI]
#(kulup": "", "deger": 28)
# --- LİG VE KULÜP VERİLERİ (YENİ YAPI) ---
TUM_LIGLER = {
    "Trendyol Süper Lig": [
        {"ad": "Fenerbahçe", "p": 0, "butce": 80, "file": "250px-Fenerbahçe_SK.png"},
        {"ad": "Galatasaray", "p": 0, "butce": 60, "file": "250px-Galatasaray_SK_football_logo.png"},
        {"ad": "Beşiktaş", "p": 0, "butce": 32, "file": "114.png"},
        {"ad": "Trabzonspor", "p": 0, "butce": 36, "file": "449.png"},
        {"ad": "Eyüpspor", "p": 0, "butce": 13, "file": "7160.png"},
        {"ad": "Başakşehir", "p": 0, "butce": 14, "file": "6890.png"},
        {"ad": "Kasımpaşa", "p": 0, "butce": 16, "file": "10484.png"},
        {"ad": "Konyaspor", "p": 0, "butce": 12, "file": "2293.png"},
        {"ad": "Gençlerbirliği", "p": 0, "butce": 10, "file": "74474.png"},
        {"ad": "Samsunspor", "p": 0, "butce": 28, "file": "152.png"},
        {"ad": "Alanyaspor", "p": 0, "butce": 8, "file": "11282.png"},
        {"ad": "Göztepe", "p": 0, "butce": 10, "file": "1467.png"},
        {"ad": "Çaykur Rizespor", "p": 0, "butce": 8, "file": "126.png"},
        {"ad": "Kocaelispor", "p": 0, "butce": 10, "file": "120.png"},
        {"ad": "Gaziantep", "p": 0, "butce": 7, "file": "2832.png"},
        {"ad": "Antalyaspor", "p": 0, "butce": 9, "file": "589.png"}
    ],
    "Bundesliga": [
        {"ad": "Bayern Munchen", "p": 0, "butce": 170},
        {"ad": "Frankfurt", "p": 0, "butce": 40},
        {"ad": "Shalcke 04", "p": 0, "butce": 30},
        {"ad": "Stuttgart", "p": 0, "butce": 50},
        {"ad": "Bayer Leverkusen", "p": 0, "butce": 70},
        {"ad": "Borussia Dortmund", "p": 0, "butce": 110}
        ],
    "Misli Premier Lig": [
        {"ad": "Qarabağ", "p": 0, "butce": 25},
        {"ad": "Neftçi PFK", "p": 0, "butce": 20},
        {"ad": "Sabah FK", "p": 0, "butce": 8},
        {"ad": "Şamaxı", "p": 0, "butce": 3},
        {"ad": "Qebele", "p": 0, "butce": 4},
        {"ad": "Sumqayıt FK", "p": 0, "butce": 5},
        {"ad": "Turan Tovuz", "p": 0, "butce": 6},
        {"ad": "Araz-Naxçıvan", "p": 0, "butce": 2},
        {"ad": "Karvan", "p": 0, "butce": 1},
        {"ad": "Sebail", "p": 0, "butce": 1},
        {"ad": "Zire FK", "p": 0, "butce": 7}
    ],
    "ENG Premier Leauge": [
        {"ad": "Man. City", "p": 0, "butce": 180},
        {"ad": "Man. Utd", "p": 0, "butce": 100},
        {"ad": "Aston Villa", "p": 0, "butce": 70},
        {"ad": "Newcastle Utd.", "p": 0, "butce": 90},
        {"ad": "Bournemouth", "p": 0, "butce": 180},
        {"ad": "Sunderland", "p": 0, "butce": 100},
        {"ad": "Leeds", "p": 0, "butce": 180},
        {"ad": "Fulham", "p": 0, "butce": 100},
        {"ad": "Everton", "p": 0, "butce": 70},
        {"ad": "Brentford", "p": 0, "butce": 90},
        {"ad": "Arsenal", "p": 0, "butce": 130},
        {"ad": "Liverpool", "p": 0, "butce": 280},
        {"ad": "Chealse", "p": 0, "butce": 80},
        {"ad": "Brighton", "p": 0, "butce": 60},
        {"ad": "Tottenham", "p": 0, "butce": 130},
        {"ad": "Nottingham Frst.", "p": 0, "butce": 80}
    ],
    "LaLiga Santander": [
        {"ad": "Real Madrid", "p": 0, "butce": 200},
        {"ad": "Barcelona", "p": 0, "butce": 100},
        {"ad": "Atletico Madrid", "p": 0, "butce": 180},
        {"ad": "Getafe", "p": 0, "butce": 180},
        {"ad": "Villarreal", "p": 0, "butce": 100},
        {"ad": "Atletich Club", "p": 0, "butce": 180},
        {"ad": "Real Sociedad", "p": 0, "butce": 100},
        {"ad": "Celta Vigo", "p": 0, "butce": 180},
        {"ad": "Girona", "p": 0, "butce": 100},
        {"ad": "Real Betis", "p": 0, "butce": 180},
        {"ad": "Valencia", "p": 0, "butce": 100},
        {"ad": "Sevilla", "p": 0, "butce": 100},
        {"ad": "Espanyol", "p": 0, "butce": 180},
        {"ad": "Alavés", "p": 0, "butce": 100},
        {"ad": "Osasuna", "p": 0, "butce": 180},
        {"ad": "Elche CF", "p": 0, "butce": 100}
],
	"SERI A ITALY": [
        {"ad": "Inter Milan", "p": 0, "butce": 180},
        {"ad": "Como 1907", "p": 0, "butce": 100},
        {"ad": "Bologno", "p": 0, "butce": 180},
        {"ad": "Atalanta", "p": 0, "butce": 180},
        {"ad": "Juventus", "p": 0, "butce": 100},
        {"ad": "Milan", "p": 0, "butce": 180},
        {"ad": "Roma", "p": 0, "butce": 180},
        {"ad": "Napoli", "p": 0, "butce": 100},
        {"ad": "Lazio", "p": 0, "butce": 180},
        {"ad": "Sassuolo", "p": 0, "butce": 100},
        {"ad": "Udinese", "p": 0, "butce": 180},
        {"ad": "Parma", "p": 0, "butce": 180},
        {"ad": "Fiorentina", "p": 0, "butce": 100},
        {"ad": "Torino", "p": 0, "butce": 180},
        {"ad": "Lecce", "p": 0, "butce": 180},
        {"ad": "Cagliari", "p": 0, "butce": 100}
]
}
# Başlangıçta boş, seçim yapıldığında o ligin takımlarıyla dolacak
KULUPLER = [] 


# --- TRANSFER PAZARI: DIŞ KULÜPLER VE SERBEST OYUNCULAR ---
TRANSFER_PAZARI = [
    {"isim": "L.Yamal", "mevki": "RW", "yetenek": 90, "yas": 19, "deger": 220, "kulup": "FC Barcelona", "ulke": "İspanya"},
    {"isim": "Pedri", "mevki": "MO", "yetenek": 90, "yas": 23, "deger": 150, "kulup": "FC Barcelona", "ulke": "İspanya"},
    {"isim": "A.Lookman", "mevki": "LW", "yetenek": 83, "yas": 29, "deger": 40, "kulup": "Atlético de Madrid", "ulke": "Nijerya"},
    {"isim": "M.Oyarzabal", "mevki": "ST", "yetenek": 84, "yas": 28, "deger": 25, "kulup": "Real Sociedad", "ulke": "İspanya"},
    {"isim": "Kevin De Bruyne", "mevki": "MOO", "yetenek": 85, "yas": 32, "deger": 8, "kulup": "SSC Napoli", "ulke": "Belçika"},
    {"isim": "J.Duran", "mevki": "ST", "yetenek": 78, "yas": 22, "deger": 15, "kulup": "SL Benfica", "ulke": "Kolombiya"},
    {"isim": "Noa Lang", "mevki": "LW", "yetenek": 79, "yas": 26, "deger": 20, "face": "IMG-20260331-WA0010.jpg", "kulup": "SSC Napoli", "ulke": "Hollanda"},
    {"isim": "Icardi", "mevki": "ST", "yetenek": 78, "yas": 33, "deger": 3, "face": "", "kulup": "Serbest", "ulke": "Arjantin"},
    {"isim": "A.Musaba", "mevki": "RW", "yetenek": 73, "yas": 25, "deger": 7, "face": "IMG-20260331-WA0021.jpg", "kulup": "Norwich City", "ulke": "Kongo Demokratik Cumhuriyeti"},
    {"isim": "Ç.Söyüncü", "mevki": "CB", "yetenek": 74, "yas": 29, "deger": 2.5, "face": "IMG-20260330-WA00.jpg", "kulup": "Corum FK", "ulke": "Türkiye"},
    {"isim": "Fred", "mevki": "MO", "yetenek": 77, "yas": 33, "deger": 4.5, "face": "IMG-20260330-WA00.jpg", "kulup": "Clube Atlético Mineiro", "ulke": "Brezilya"},
    {"isim": "Talisca", "mevki": "ST", "yetenek": 81, "yas": 32, "deger": 7, "face": "IMG-20260413-WA0000.jpg", "kulup": "Al-Jazira Club", "ulke": "Brezilya"},
    {"isim": "E.Alvarez", "mevki": "MDO", "yetenek": 77, "yas": 29, "deger": 12, "kulup": "West Ham United", "ulke": "Meksika"},
    {"isim": "S.Cherif", "mevki": "ST", "yetenek": 72, "yas": 19, "deger": 22, "kulup": "Coventry City", "ulke": "Fransa"},
    {"isim": "Felipe", "mevki": "KL", "yetenek": 69, "yas": 30, "deger": 1, "kulup": "Corum FK", "ulke": "Brezilya"},
    {"isim": "L.Claro", "mevki": "LB", "yetenek": 64, "yas": 35, "deger": 0.1, "kulup": "Esenler Erokspor", "ulke": "Brezilya"},
    {"isim": "O.Emir", "mevki": "KL", "yetenek": 62, "yas": 22, "deger": 0.6, "kulup": "Kocaelispor", "ulke": "Türkiye"},
    {"isim": "E.Destanoğlu", "mevki": "KL", "yetenek": 73, "yas": 25, "deger": 4, "face": "images (44).jpeg", "kulup": "Al-Jazira Club", "ulke": "Türkiye"},
    {"isim": "Sazdağı", "mevki": "RB", "yetenek": 69, "yas": 31, "deger": 0.8, "face": "Screenshot_2026-03-31-20-57-48-947_com.android.chrome-edit.jpg", "kulup": "Corum FK", "ulke": "Türkiye"},
    {"isim": "S.Uçan", "mevki": "MO", "yetenek": 69, "yas": 32, "deger": 0.5, "face": "images (49).jpeg", "kulup": "Genclerbirligi Ankara", "ulke": "Türkiye"},
    {"isim": "J.Silva", "mevki": "LW", "yetenek": 73, "yas": 33, "deger": 9, "face": "", "kulup": "Olympiacos Piraeus", "ulke": "Portekiz"},
    {"isim": "N.Uysal", "mevki": "MDO", "yetenek": 66, "yas": 35, "deger": 0.025, "kulup": "Emekli", "ulke": "Türkiye"},
    {"isim": "C.Ünder", "mevki": "RW", "yetenek": 73, "yas": 28, "deger": 3, "kulup": "Corum FK", "ulke": "Türkiye"},
    {"isim": "T.El Bilal", "mevki": "ST", "yetenek": 72, "yas": 24, "deger": 13, "kulup": "Parma Calcio 1913", "ulke": "Mali"},
    {"isim": "M.Løvik", "mevki": "LB", "yetenek": 66, "yas": 22, "deger": 3.5, "face": "images (54).jpeg", "kulup": "Molde FK", "ulke": "Norveç"},
    {"isim": "Nwakaeme", "mevki": "LW", "yetenek": 66, "yas": 37, "deger": 0.1, "face": "images (46)(1).jpeg", "kulup": "Serbest", "ulke": "Nijerya"},
    {"isim": "R.Baniya", "mevki": "CB", "yetenek": 68, "yas": 27, "deger": 1, "kulup": "Konyaspor", "ulke": "Türkiye"},
    {"isim": "Inao Oulaï", "mevki": "MOO", "yetenek": 72, "yas": 23, "deger": 28, "kulup": "ACF Fiorentina", "ulke": "Fildişi Sahili"},
    {"isim": "O.Zubkov", "mevki": "RW", "yetenek": 76, "yas": 29, "deger": 5, "kulup": "AEK Athens", "ulke": "Ukrayna"},
    {"isim": "F.Augosto", "mevki": "ST", "yetenek": 81, "yas": 25, "deger": 15, "kulup": "Zenit St. Petersburg", "ulke": "Brezilya"},
    {"isim": "Lea Duarte", "mevki": "CB", "yetenek": 72, "yas": 24, "deger": 2, "kulup": "Clube Atlético Mineiro", "ulke": "Brezilya"},
    {"isim": "M.Crespo", "mevki": "MO", "yetenek": 72, "yas": 29, "deger": 2, "kulup": "Al-Khaleej FC", "ulke": "Portekiz"},
    {"isim": "N.Da Costa", "mevki": "ST", "yetenek": 69, "yas": 35, "deger": 0.35, "kulup": "Antalyaspor", "ulke": "Yeşil Burun Adaları"},
    {"isim": "I.Eğribayat", "mevki": "KL", "yetenek": 71, "yas": 28, "deger": 1.2, "kulup": "Genclerbirligi Ankara", "ulke": "Türkiye"},
    {"isim": "L.Setka", "mevki": "CB", "yetenek": 70, "yas": 31, "deger": 1.3, "kulup": "Omonia Nicosia", "ulke": "Slovakya"},
    {"isim": "Drongelen", "mevki": "CB", "yetenek": 75, "yas": 28, "deger": 6, "kulup": "Panathinaikos", "ulke": "Hollanda"},
    {"isim": "Ntcham", "mevki": "MO", "yetenek": 71, "yas": 30, "deger": 1.2, "kulup": "Serbest", "ulke": "Kamerun"},
    {"isim": "Makoumbu", "mevki": "MO", "yetenek": 72, "yas": 28, "deger": 2.5, "kulup": "UC Sampdoria", "ulke": "Kongo Cumhuriyeti"},
    {"isim": "Ndiaye", "mevki": "ST", "yetenek": 69, "yas": 30, "deger": 5, "kulup": "PAOK Thessaloniki", "ulke": "Senegal"},
    {"isim": "R.Becão", "mevki": "CB", "yetenek": 71, "yas": 30, "deger": 2, "kulup": "Rodina Moscow", "ulke": "Brezilya"},
    {"isim": "A.Szalai", "mevki": "CB", "yetenek": 69, "yas": 28, "deger": 1.5, "kulup": "Pogon Szczecin", "ulke": "Macaristan"},
    {"isim": "Cafu", "mevki": "MO", "yetenek": 66, "yas": 33, "deger": 0.2, "kulup": "AEL Limassol", "ulke": "Portekiz"},
    {"isim": "C.Tosun", "mevki": "ST", "yetenek": 67, "yas": 35, "deger": 0.3, "kulup": "Fatih Karagümrük", "ulke": "Türkiye"},
    {"isim": "N.Opoku", "mevki": "CB", "yetenek": 68, "yas": 29, "deger": 1, "kulup": "UD Las Palmas", "ulke": "Gana"},
    {"isim": "M.Fall", "mevki": "ST", "yetenek": 69, "yas": 35, "deger": 0.275, "kulup": "Istanbulspor", "ulke": "Senegal"},
    {"isim": "H.Guéye", "mevki": "ST", "yetenek": 69, "yas": 27, "deger": 1, "kulup": "Esenler Erokspor", "ulke": "Senegal"},
    {"isim": "T.Emre", "mevki": "CB", "yetenek": 65, "yas": 24, "deger": 0.1, "kulup": "Mardin 1969 Spor", "ulke": "Türkiye"},
    {"isim": "Kochalski", "mevki": "KL", "yetenek": 74, "yas": 25, "deger": 2.5, "kulup": "Wieczysta Krakow", "ulke": "Polonya"},
    {"isim": "K.Medina", "mevki": "CB", "yetenek": 67, "yas": 34, "deger": 0.4, "kulup": "Johor Darul Ta'zim", "ulke": "Kolombiya"},
    {"isim": "D.Bolt", "mevki": "RB", "yetenek": 67, "yas": 25, "deger": 1, "kulup": "Johor Darul Ta'zim", "ulke": "Brezilya"},
    {"isim": "A.Zoubir", "mevki": "LW", "yetenek": 74, "yas": 34, "deger": 0.35, "kulup": "Al-Orobah FC", "ulke": "Fransa"},
    {"isim": "C.Duran", "mevki": "ST", "yetenek": 70, "yas": 22, "deger": 6, "kulup": "Celtic FC", "ulke": "Kolombiya"},
    {"isim": "L.Andrade", "mevki": "RW", "yetenek": 73, "yas": 26, "deger": 4, "kulup": "Polissya Zhytomyr", "ulke": "Yeşil Burun Adaları"},
    {"isim": "T.Bayramov", "mevki": "LB", "yetenek": 72, "yas": 25, "deger": 1.8, "kulup": "Bursaspor", "ulke": "Azerbaycan"},
    {"isim": "Kenan Piric", "mevki": "KL", "yetenek": 68, "yas": 31, "deger": 0.5, "kulup": "Riga FC", "ulke": "Bosna-Hersek"},
    {"isim": "Y.Lauwal", "mevki": "RB", "yetenek": 65, "yas": 23, "deger": 0.15, "kulup": "Al-Wefaq Ajdabiya SC", "ulke": "Nijerya"},
    {"isim": "Robert Bauer", "mevki": "CB", "yetenek": 67, "yas": 30, "deger": 0.4, "kulup": "Mosul SC", "ulke": "Almanya"},
    {"isim": "Y.Matias", "mevki": "CB", "yetenek": 69, "yas": 31, "deger": 0.8, "kulup": "Ajman Club", "ulke": "Brezilya"},
    {"isim": "R.Məmmədov", "mevki": "LB", "yetenek": 66, "yas": 23, "deger": 0.225, "kulup": "Turan-Tovuz IK", "ulke": "Azerbaycan"},
    {"isim": "R.Almeida", "mevki": "MO", "yetenek": 65, "yas": 37, "deger": 0.1, "kulup": "EC XV de Piracicaba", "ulke": "Azerbaycan"},
    {"isim": "Andre Shinyashiki", "mevki": "LW", "yetenek": 69, "yas": 28, "deger": 0.7, "kulup": "Serbest", "ulke": "Brezilya"},
    {"isim": "Ramil Şeydayev", "mevki": "RW", "yetenek": 68, "yas": 30, "deger": 0.5, "kulup": "FC Sochi", "ulke": "Azerbaycan"},
    {"isim": "V.Aboubakar", "mevki": "ST", "yetenek": 73, "yas": 34, "deger": 0.5, "kulup": "Bodrum FK", "ulke": "Kamerun"},
    {"isim": "D.Panyukov", "mevki": "ST", "yetenek": 64, "yas": 31, "deger": 0.35, "kulup": "Serbest", "ulke": "Rusya"},
    {"isim": "Rodri", "mevki": "MDO", "yetenek": 90, "yas": 29, "deger": 60, "kulup": "FC Barcelona", "ulke": "İspanya"},
    {"isim": "T.Reijnders", "mevki": "MO", "yetenek": 84, "yas": 27, "deger": 50, "kulup": "Al-Qadsiah FC", "ulke": "Hollanda"},
    {"isim": "F.Jorgensen", "mevki": "KL", "yetenek": 77, "yas": 23, "deger": 15, "kulup": "RC Strasbourg Alsace", "ulke": "Danimarka"},
    {"isim": "C.Romero", "mevki": "CB", "yetenek": 82, "yas": 28, "deger": 40, "kulup": "Atlético de Madrid", "ulke": "Arjantin"},
    {"isim": "K.Danso", "mevki": "CB", "yetenek": 79, "yas": 27, "deger": 20, "kulup": "Sunderland AFC", "ulke": "Avusturya"},
    {"isim": "J.Palhinha", "mevki": "MDO", "yetenek": 82, "yas": 30, "deger": 15, "kulup": "SL Benfica", "ulke": "Portekiz"},
    {"isim": "H.Elliott", "mevki": "MOO", "yetenek": 77, "yas": 23, "deger": 18, "kulup": "Valencia CF", "ulke": "İngiltere"},
    {"isim": "J.Sancho", "mevki": "LW", "yetenek": 78, "yas": 26, "deger": 10, "kulup": "Serbest", "ulke": "İngiltere"},
    {"isim": "O.Watkins", "mevki": "ST", "yetenek": 83, "yas": 30, "deger": 25, "kulup": "Al-Hilal SFC", "ulke": "İngiltere"},
    {"isim": "A.Ramsdale", "mevki": "KL", "yetenek": 77, "yas": 27, "deger": 8, "kulup": "Southampton FC", "ulke": "İngiltere"},
    {"isim": "A.Gordon", "mevki": "LW", "yetenek": 82, "yas": 25, "deger": 80, "kulup": "FC Barcelona", "ulke": "İngiltere"},
    {"isim": "S.Ortega", "mevki": "KL", "yetenek": 78, "yas": 33, "deger": 3.5, "kulup": "Olympiacos Piraeus", "ulke": "Almanya"},
    {"isim": "Di Gregerio", "mevki": "KL", "yetenek": 80, "yas": 28, "deger": 8, "kulup": "AFC Bournemouth", "ulke": "İtalya"},
    {"isim": "F.Kostic", "mevki": "LB", "yetenek": 77, "yas": 33, "deger": 2, "kulup": "PSV Eindhoven", "ulke": "Sırbistan"},
    {"isim": "Holm", "mevki": "RB", "yetenek": 75, "yas": 25, "deger": 10, "kulup": "Bologna FC 1909", "ulke": "İsveç"},
    {"isim": "J.David", "mevki": "ST", "yetenek": 80, "yas": 26, "deger": 30, "kulup": "Atlético de Madrid", "ulke": "Kanada"},
]


POS_433_LIST = [(120, 300), (380, 150), (380, 250), (380, 350), (380, 450), (680, 180), (680, 300), (680, 420), (1000, 200), (1000, 300), (1000, 400)]
POS_523_LIST = [(120, 300), (380, 150), (380, 250), (380, 350), (380, 450), (680, 180), (680, 300), (680, 420), (1000, 200), (1000, 300), (1000, 400)]
POS_352_LIST = [(120, 300), (380, 150), (380, 250), (380, 350), (380, 450), (680, 180), (680, 300), (680, 420), (1000, 200), (1000, 300), (1000, 400)]

try:
    # Gönderdiğin basın toplantısı fotoğrafının tam dosya adını buraya yazıyoruz.
    BASIN_FOTO = pygame.image.load("IMG-20260406-WA0017.jpg").convert_alpha()
    BASIN_FOTO = pygame.transform.smoothscale(BASIN_FOTO, (WIDTH, HEIGHT)) # Boyutu tam ekran yap
except pygame.error as e:
    print(f"Basın toplantısı fotoğrafı yüklenemedi: {e}")
    BASIN_FOTO = None
except FileNotFoundError:
    print(f"Basın toplantısı fotoğraf dosyası bulunamadı.")
    BASIN_FOTO = None

BASIN_SORULARI = [
    {
        "kategori": "taktik",
        "soru": "Bugünkü ofansif taktiğiniz çok riskli değil miydi?",
        "secenekler": [
            {"metin": "Hücum bizim kimliğimiz, asla geri adım atmayacağız!", "etki": 5},
            {"metin": "Haklısınız, savunmada daha dengeli olmalıydık.", "etki": -3}
        ]
    },
    {
        "kategori": "lig_durumu",
        "soru": "Ligdeki konumunuz taraftarı pek memnun etmiyor. Ne düşünüyorsunuz?",
        "secenekler": [
            {"metin": "Sabırlı olsunlar, bu takım şampiyon olacak!", "etki": 7},
            {"metin": "Hedeflerimizin uzağındayız, sorumluluk benim.", "etki": -2}
        ]
    },
    {
        "kategori": "performans",
        "soru": "Takım bugün sahada ruhsuz gibiydi. Kondisyon sorunu mu var?",
        "secenekler": [
            {"metin": "Hayır, sadece kötü bir gündü. Gelecek maç telafi edeceğiz.", "etki": 3},
            {"metin": "Oyuncularım yorgun, yoğun fikstür bizi zorluyor.", "etki": -5}
        ]
    },
    {
        "kategori": "taktik",
        "soru": "Yaptığınız oyuncu değişiklikleri maçın kaderini değiştirdi. Dahi misiniz?",
        "secenekler": [
            {"metin": "Bu bir ekip işi, sadece işimi yapıyorum.", "etki": 4},
            {"metin": "Her hamleyi önceden planlamıştım, şans değil.", "etki": 6}
        ]
    },
    {
        "kategori": "mac_sonu",
        "soru": "Bugünkü galibiyeti taktiksel disipline mi yoksa bireysel yeteneklere mi bağlıyorsunuz?",
        "secenekler": [
            {"metin": "Tamamen takım oyunu ve disiplin kazandırdı.", "etki": 5},
            {"metin": "Yıldız oyuncularımız kalitelerini konuşturdu.", "etki": 3}
        ]
    },
    {
        "kategori": "mac_sonu",
        "soru": "Rakibin sert savunmasını aşmakta neden bu kadar zorlandınız?",
        "secenekler": [
            {"metin": "Kilidi açacak sabra sahibiz, sonuç önemliydi.", "etki": 4},
            {"metin": "Yeterince üretken değildik, bunu geliştirmeliyiz.", "etki": -2}
        ]
    },
    {
        "kategori": "transfer",
        "soru": "Transfer listesinde olduğunuz iddia edilen oyuncular hakkında ne diyeceksiniz?",
        "secenekler": [
            {"metin": "İyi oyuncularla her zaman ilgileniriz.", "etki": 2},
            {"metin": "Şu an sadece elimizdeki kadroya odaklıyız.", "etki": 4}
        ]
    },
    {
        "kategori": "performans",
        "soru": "Yıldız oyuncunuzun düşük reytingi takımdaki geleceğini etkiler mi?",
        "secenekler": [
            {"metin": "Her oyuncu form düşüklüğü yaşayabilir, arkasındayız.", "etki": 6},
            {"metin": "Forma adaletine inanırım, performansını artırmalı.", "etki": -3}
        ]
    },
    {
        "kategori": "oyuncu_durumu",
        "soru": "Tecrübeli oyuncunuzun sezon sonu emekli olacağı doğru mu?",
        "secenekler": [
            {"metin": "O bizim için bir efsane, kararına saygı duyarız.", "etki": 5},
            {"metin": "Henüz net bir durum yok, zamanı gelince konuşuruz.", "etki": 1}
        ]
    },
    {
        "kategori": "mac_sonu",
        "soru": "Hakemin tartışmalı penaltı kararı maçın sonucunu değiştirdi mi?",
        "secenekler": [
            {"metin": "Hakem hataları oyunun bir parçası, bahane üretmiyoruz.", "etki": 3},
            {"metin": "Emeğimizin çalındığını düşünüyorum, skandal bir karar!", "etki": -4}
        ]
    },
    {
        "kategori": "mac_sonu",
        "soru": "Son dakikalarda yediğiniz golleri konsantrasyon eksikliğine mi bağlıyorsunuz?",
        "secenekler": [
            {"metin": "Ders çıkaracağız, son düdüğe kadar odaklanmalıyız.", "etki": -2},
            {"metin": "Şanssız bir andı, takımın mücadelesinden memnunum.", "etki": 2}
        ]
    },
    {
        "kategori": "moral",
        "soru": "Yedek kalan oyuncuların huzursuz olduğu söyleniyor. Ne dersiniz?",
        "secenekler": [
            {"metin": "Herkes sırasını beklemeli, burası bir takım.", "etki": -3},
            {"metin": "Tüm oyuncularım kıymetli, şans bulacaklar.", "etki": 5}
        ]
    },
    {
        "kategori": "strateji",
        "soru": "Genç oyuncu politikanızın meyvelerini ne zaman alacaksınız?",
        "secenekler": [
            {"metin": "Geleceği inşa ediyoruz, meyveleri yakında göreceksiniz.", "etki": 6},
            {"metin": "Zamana ihtiyacımız var, sabır en önemli anahtar.", "etki": 3}
        ]
    },
    {
        "kategori": "yonetim",
        "soru": "Yönetimin size olan desteğinin azaldığı iddialarına katılıyor musunuz?",
        "secenekler": [
            {"metin": "Yönetimle uyum içindeyiz, dedikodulara kulak asmıyoruz.", "etki": 4},
            {"metin": "Ben işimi yapıyorum, gerisi yönetimin takdiri.", "etki": -5}
        ]
    },
    {
        "kategori": "taktik",
        "soru": "Bugünkü sürpriz ilk 11 tercihiniz riskli değil miydi?",
        "secenekler": [
            {"metin": "Planımıza sadık kaldık ve işe yaradı.", "etki": 5},
            {"metin": "Risk almadan büyük zaferler kazanılmaz.", "etki": 4}
        ]
    },
    {
        "kategori": "transfer",
        "soru": "Yeni transferin uyum süreci beklediğinizden yavaş mı ilerliyor?",
        "secenekler": [
            {"metin": "Ona güvenimiz tam, kısa sürede takıma alışacak.", "etki": 4},
            {"metin": "Alışma süreci zordur, biraz daha zaman gerekiyor.", "etki": 1}
        ]
    },
    {
        "kategori": "taraftar",
        "soru": "Taraftarların tepkili tutumu oyuncuları nasıl etkiliyor?",
        "secenekler": [
            {"metin": "Onları sahada alacağımız sonuçlarla susturacağız.", "etki": -2},
            {"metin": "Taraftar haklı, onlara layık bir futbol oynamalıyız.", "etki": 5}
        ]
    },
    {
        "kategori": "mac_oncesi",
        "soru": "Önümüzdeki derbi maçı öncesi takımdaki hava nasıl?",
        "secenekler": [
            {"metin": "Kazanmaktan başka bir şey düşünmüyoruz.", "etki": 7},
            {"metin": "Zor maç olacak ama biz hazırız.", "etki": 3}
        ]
    },
    {
        "kategori": "taktik",
        "soru": "Eksik oyuncuların yokluğunda B planınız hazır mı?",
        "secenekler": [
            {"metin": "Geniş bir kadromuz var, eksikleri aratmayacağız.", "etki": 5},
            {"metin": "Eksiklerimiz önemli ama elimizden geleni yapacağız.", "etki": 2}
        ]
    },
    {
        "kategori": "sozlesme",
        "soru": "Sözleşmesi biten oyuncularla anlaşma sağlanabilecek mi?",
        "secenekler": [
            {"metin": "Görüşmeler sürüyor, kulübün menfaatleri önceliğimiz.", "etki": 3},
            {"metin": "Herkes kalmak istiyor, orta yolu bulacağız.", "etki": 4}
        ]
    },
    {
        "kategori": "kondisyon",
        "soru": "Yoğun fikstürün takımı yorduğu görülüyor. Rotasyon yapacak mısınız?",
        "secenekler": [
            {"metin": "Zinde kalmak için her türlü önlemi alıyoruz.", "etki": 4},
            {"metin": "Yorgunluk bir bahane olamaz, profesyoneliz.", "etki": 2}
        ]
    },
    {
        "kategori": "mac_sonu",
        "soru": "Maçın dönüm noktası sizce hangi andı?",
        "secenekler": [
            {"metin": "Attığımız ilk gol tüm dengeleri değiştirdi.", "etki": 3},
            {"metin": "Oyuncu değişikliklerimiz oyuna tempo kazandırdı.", "etki": 5}
        ]
    },
    {
        "kategori": "lig_durumu",
        "soru": "Rakiplerin puan kaybettiği haftada gelen bu galibiyet ne ifade ediyor?",
        "secenekler": [
            {"metin": "Şampiyonluk yürüyüşümüzün en önemli adımlarından biri.", "etki": 5},
            {"metin": "Sadece bir maç kazandık, önümüzde çok yol var.", "etki": 7}
        ]
    },
    {
        "kategori": "mac_sonu",
        "soru": "Geriye düşmenize rağmen maçı çevirmeyi nasıl başardınız?",
        "secenekler": [
            {"metin": "Vazgeçmemek bizim ruhumuzda var.", "etki": 6},
            {"metin": "Devre arasında yaptığımız uyarılar etkili oldu.", "etki": 4}
        ]
    }
]

# --- TARAFTAR + SEZON ÖDÜL SİSTEMİ ---
BALLON_DOR_AYARLARI = {
    "aday_sayisi": 10,
    "rastgelelik_esigi": 0.05,
    "kazanan_moral": 10,
    "aday_moral_min": 2,
    "aday_moral_max": 3,
    "kazanan_populerlik": 15,
    "deger_artis_min": 0.10,
    "deger_artis_max": 0.25,
}

kariyer_verisi = {
    "isim": "",
    "kulup": None,
    "kadro": [],
    "gun": 1,
    "mac_gunu": 7,
    "taraftar": 50,
    "oynanan_mac": 0,
    "sezon": 2027,
    "ballon_dor_gecmisi": [],
    "son_ballon_dor": None,
    "avrupa_lig_katilim": False,
    "avrupa_mac_sayisi": 0,
    "genel_mac_index": 0,
    "ucl_hafta": 1,
    "ucl_tur": "Lig",
    "ucl_eslesmeler": {},
    "ucl_tum_turlar": {},
    "ucl_son16_dogrudan": [],
    "ucl_mac_index": 0,
    "kendi_ucl_maci_var": False,
    "oynanan_ucl_rakipleri": [],
    "siradaki_ucl_rakip": None,
    "ucl_aktif_eslesme": None,
    "ucl_sampiyonu": None,
    "mesajlar": [],
    "sezon_gelir": 0,
    "sezon_gider": 0,
}


# ============================================================
# [YENI] MALİ DURUM TAKİBİ (Gelir / Gider)
# Transfer sekmesindeki "Mali Durum" karti icin kullanilir.
# Mevcut butce mantigini DEGISTIRMEZ; sadece hareketleri kaydeder.
# ============================================================
def butce_arttir(miktar, kaynak="Gelir"):
    """Kulup butcesine para ekler ve sezonluk geliri gunceller."""
    global transfer_finans_kilidi
    if not isinstance(kariyer_verisi.get("kulup"), dict):
        return
    kariyer_verisi["kulup"]["butce"] = kariyer_verisi["kulup"].get("butce", 0) + miktar
    kariyer_verisi["sezon_gelir"] = kariyer_verisi.get("sezon_gelir", 0) + miktar
    if kaynak == "Transfer" and transfer_finans_kilidi:
        kariyer_verisi["sezon_gelir"] -= miktar
        transfer_finans_kilidi = False


def butce_azalt(miktar, kaynak="Gider"):
    """Kulup butcesinden para duser ve sezonluk gideri gunceller."""
    global transfer_finans_kilidi
    if not isinstance(kariyer_verisi.get("kulup"), dict):
        return
    kariyer_verisi["kulup"]["butce"] = kariyer_verisi["kulup"].get("butce", 0) - miktar
    kariyer_verisi["sezon_gider"] = kariyer_verisi.get("sezon_gider", 0) + miktar
    if kaynak == "Transfer" and transfer_finans_kilidi:
        kariyer_verisi["sezon_gider"] -= miktar
        transfer_finans_kilidi = False

KAYIT_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fm2027_kayit.json")
KARIYER_VERISI_VARSAYILAN = json.loads(json.dumps(kariyer_verisi, ensure_ascii=False))


def kayit_var_mi():
    return os.path.exists(KAYIT_DOSYASI)


def oyunu_kaydet():
    try:
        kayit_verisi = {
            "surum": 1,
            "transfer_index": transfer_index,
            "transfer_sekme": transfer_sekme,
            "secili_degisim_id": secili_degisim_id if "secili_degisim_id" in globals() else -1,
            "son_tiklama_zamani": son_tiklama_zamani if "son_tiklama_zamani" in globals() else 0,
            "tiklanan_oyuncu_id": tiklanan_oyuncu_id if "tiklanan_oyuncu_id" in globals() else -1,
            "KULUPLER": KULUPLER,
            "TRANSFER_PAZARI": TRANSFER_PAZARI,
            "TAKIM_OYUNCULARI": TAKIM_OYUNCULARI,
            "AVRUPA_KULUPLER": AVRUPA_KULUPLER,
            "kariyer_verisi": kariyer_verisi,
        }
        with open(KAYIT_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(kayit_verisi, f, ensure_ascii=False, indent=2)
        return True, "Oyun kaydedildi."
    except Exception as hata:
        return False, f"Kaydetme hatası: {hata}"


def oyunu_yukle():
    global transfer_index, transfer_sekme, secili_degisim_id, son_tiklama_zamani, tiklanan_oyuncu_id

    if not kayit_var_mi():
        return False, "Kayıt dosyası bulunamadı."

    try:
        with open(KAYIT_DOSYASI, "r", encoding="utf-8") as f:
            kayit_verisi = json.load(f)

        KULUPLER[:] = kayit_verisi.get("KULUPLER", [])
        TRANSFER_PAZARI[:] = kayit_verisi.get("TRANSFER_PAZARI", [])

        TAKIM_OYUNCULARI.clear()
        TAKIM_OYUNCULARI.update(kayit_verisi.get("TAKIM_OYUNCULARI", {}))

        AVRUPA_KULUPLER[:] = kayit_verisi.get("AVRUPA_KULUPLER", AVRUPA_KULUPLER)

        varsayilan_kariyer = json.loads(json.dumps(KARIYER_VERISI_VARSAYILAN, ensure_ascii=False))
        varsayilan_kariyer.update(kayit_verisi.get("kariyer_verisi", {}))
        kariyer_verisi.clear()
        kariyer_verisi.update(varsayilan_kariyer)

        transfer_index = int(kayit_verisi.get("transfer_index", 0) or 0)
        transfer_sekme = kayit_verisi.get("transfer_sekme", "AL")
        secili_degisim_id = int(kayit_verisi.get("secili_degisim_id", -1) or -1)
        son_tiklama_zamani = int(kayit_verisi.get("son_tiklama_zamani", 0) or 0)
        tiklanan_oyuncu_id = int(kayit_verisi.get("tiklanan_oyuncu_id", -1) or -1)

        kulup_bilgisi = kariyer_verisi.get("kulup") if isinstance(kariyer_verisi.get("kulup"), dict) else None
        kulup_adi = kulup_bilgisi.get("ad") if kulup_bilgisi else None
        if kulup_adi:
            eslesen_kulup = next((k for k in KULUPLER if k.get("ad") == kulup_adi), None)
            if eslesen_kulup is None:
                eslesen_kulup = dict(kulup_bilgisi)
                KULUPLER.append(eslesen_kulup)
            else:
                eslesen_kulup.update(kulup_bilgisi)
            kariyer_verisi["kulup"] = eslesen_kulup

        _yuklenen_oyunculari_birlestir(kulup_adi)
        return True, "Kayıt başarıyla yüklendi."
    except Exception as hata:
        return False, f"Yükleme hatası: {hata}"


def isim_normalize_et(isim):
    if not isim:
        return ""
    temiz = unicodedata.normalize("NFKD", str(isim))
    temiz = "".join(ch for ch in temiz if not unicodedata.combining(ch))
    temiz = temiz.casefold().replace("ı", "i")
    for karakter in [".", "'", "’", "-", "_"]:
        temiz = temiz.replace(karakter, " ")
    temiz = " ".join(temiz.split())
    # Mevcut ve eski kayıtlar için bilinen ad varyantları; görünen adı değiştirme.
    return {"a guler": "arda guler", "mamardashvili": "g mamardashvili",
            "orkun k": "orkun"}.get(temiz, temiz)


def transfer_pazar_kaydi_bul(oyuncu):
    aranan_isim = isim_normalize_et(oyuncu.get("isim", ""))
    if not aranan_isim:
        return None
    eslesenler = (
        p for p in TRANSFER_PAZARI
        if p is not oyuncu and isim_normalize_et(p.get("isim", "")) == aranan_isim
    )
    return max(eslesenler, key=lambda p: (
        p.get("isim", "").casefold() == oyuncu.get("isim", "").casefold(),
        (p.get("deger") or 0) > 0,
    ), default=None)


def _oyun_ici_kulup_adi(kulup_adi):
    anahtar = isim_normalize_et(kulup_adi)
    anahtar = {"chealse": "chelsea", "bayern": "bayern munchen"}.get(anahtar, anahtar)
    return next((k for k in TAKIM_OYUNCULARI if isim_normalize_et(k) == anahtar), None)


def tum_oyuncu_havuzunu_olustur():
    """Kulüp kadroları öncelikli, ada göre tekilleştirilmiş canlı oyuncu listesi."""
    havuz = []
    gorulen = set()
    oyun_ici_kulupler = {isim_normalize_et(k) for k in TAKIM_OYUNCULARI}
    for kulup_adi, oyuncular in TAKIM_OYUNCULARI.items():
        for p in oyuncular:
            isim_norm = isim_normalize_et(p.get("isim", ""))
            if not isim_norm:
                continue
            p["kulup"] = kulup_adi
            if isim_norm not in gorulen:
                gorulen.add(isim_norm)
                havuz.append(p)

    for p in TRANSFER_PAZARI:
        isim_norm = isim_normalize_et(p.get("isim", ""))
        if not isim_norm or isim_norm in gorulen:
            continue
        kulup_norm = isim_normalize_et(p.get("kulup", ""))
        kulup_norm = {"chealse": "chelsea", "bayern": "bayern munchen"}.get(kulup_norm, kulup_norm)
        if kulup_norm in oyun_ici_kulupler:
            continue
        gorulen.add(isim_norm)
        havuz.append(p)
    return havuz


def oyuncuyu_koleksiyonlardan_cikar(oyuncu):
    # Sözlük eşitliğine değil kimliğe bak: aynı adlı iki kadro satırı olabilir.
    koleksiyonlar = [kariyer_verisi["kadro"], TRANSFER_PAZARI, *TAKIM_OYUNCULARI.values()]
    for liste in koleksiyonlar:
        liste[:] = [p for p in liste if p is not oyuncu]


def oyuncuyu_kulube_tasi(oyuncu, hedef_kulup):
    oyuncuyu_koleksiyonlardan_cikar(oyuncu)
    kendi_kulup = (kariyer_verisi.get("kulup") or {}).get("ad")
    oyun_ici_kulup = _oyun_ici_kulup_adi(hedef_kulup)
    for alan in ("teklif_miktari", "teklif_hakki", "ceza_maci", "son_durum",
                  "teklif_suresi", "aktif_teklif", "teklif_yapan"):
        oyuncu.pop(alan, None)
    oyuncu["transfer_listesinde"] = False
    if oyun_ici_kulup is not None or (kendi_kulup and hedef_kulup == kendi_kulup):
        kulup_adi = oyun_ici_kulup or hedef_kulup
        oyuncu["kulup"] = kulup_adi
        TAKIM_OYUNCULARI.setdefault(kulup_adi, []).append(oyuncu)
        if kulup_adi == kendi_kulup:
            kariyer_verisi["kadro"].append(oyuncu)
    else:
        oyuncu["kulup"] = hedef_kulup or "Serbest"
        TRANSFER_PAZARI.append(oyuncu)


def _yuklenen_oyunculari_birlestir(kendi_kulup_adi):
    # JSON aynı referansı iki ayrı sözlük olarak yükler. Canlı kariyer
    # kadrosunu esas al; eski satın almalardaki rakip kopyasını kaldır.
    if kendi_kulup_adi:
        kadro = kariyer_verisi["kadro"]
        onceki_adlar = {isim_normalize_et(p.get("isim", ""))
                       for p in TAKIM_OYUNCULARI.get(kendi_kulup_adi, [])}
        alinan_adlar = {isim_normalize_et(p.get("isim", "")) for p in kadro} - onceki_adlar - {""}
        for kulup_adi, oyuncular in TAKIM_OYUNCULARI.items():
            if kulup_adi != kendi_kulup_adi:
                oyuncular[:] = [p for p in oyuncular if isim_normalize_et(p.get("isim", "")) not in alinan_adlar]
        TAKIM_OYUNCULARI[kendi_kulup_adi] = kadro.copy()

    # Eski pazarda yer alan, ancak hiçbir kadroda bulunmayan oyun içi
    # oyuncuları doğru takıma taşı; eşleşen eski pazar kopyalarını taşıma.
    kadro_adlari = {isim_normalize_et(p.get("isim", ""))
                   for oyuncular in TAKIM_OYUNCULARI.values() for p in oyuncular}
    for p in TRANSFER_PAZARI[:]:
        ad = isim_normalize_et(p.get("isim", ""))
        hedef = _oyun_ici_kulup_adi(p.get("kulup"))
        if ad and ad not in kadro_adlari and hedef is not None:
            oyuncuyu_kulube_tasi(p, hedef)
            kadro_adlari.add(ad)

    havuz = tum_oyuncu_havuzunu_olustur()
    for p in havuz:
        _pazar_eksik_alanlarini_tamamla(p)
    kimlikler = {id(p) for p in havuz}
    TRANSFER_PAZARI[:] = [p for p in TRANSFER_PAZARI if id(p) in kimlikler]


def mantikli_random_deger_uret(oyuncu):
    yetenek = int(oyuncu.get("yetenek", 70) or 70)
    yas = int(oyuncu.get("yas", 27) or 27)
    mevki = str(oyuncu.get("mevki", "")).upper()

    temel_deger = 2 + max(0, yetenek - 60) * 1.18
    if yetenek >= 85:
        temel_deger += (yetenek - 84) * 2.2
    elif yetenek >= 80:
        temel_deger += (yetenek - 79) * 1.1

    if yas <= 20:
        yas_carpani = 1.35
    elif yas <= 23:
        yas_carpani = 1.22
    elif yas <= 26:
        yas_carpani = 1.10
    elif yas <= 29:
        yas_carpani = 1.00
    elif yas <= 32:
        yas_carpani = 0.90
    elif yas <= 35:
        yas_carpani = 0.78
    else:
        yas_carpani = 0.65

    mevki_carpanlari = {
        "ST": 1.12,
        "LW": 1.09,
        "RW": 1.09,
        "MOO": 1.08,
        "MO": 1.03,
        "MDO": 0.98,
        "CB": 0.96,
        "LB": 0.93,
        "RB": 0.93,
        "KL": 0.90,
    }
    mevki_carpani = mevki_carpanlari.get(mevki, 1.0)

    dalgalanma = random.uniform(0.92, 1.12)
    tahmini_deger = temel_deger * yas_carpani * mevki_carpani * dalgalanma

    alt_sinir = max(1, round(yetenek * 0.22, 1))
    ust_sinir = max(alt_sinir + 2, round((yetenek * 0.95) + 18, 1))
    sonuc = round(max(alt_sinir, min(ust_sinir, tahmini_deger)), 1)
    return int(sonuc) if float(sonuc).is_integer() else sonuc


def _pazar_eksik_alanlarini_tamamla(oyuncu):
    if (oyuncu.get("deger") or 0) > 0 and oyuncu.get("yas") and oyuncu.get("face"):
        return
    pazar_kaydi = transfer_pazar_kaydi_bul(oyuncu)
    if pazar_kaydi is None:
        return
    if (oyuncu.get("deger") or 0) <= 0 and (pazar_kaydi.get("deger") or 0) > 0:
        oyuncu["deger"] = pazar_kaydi["deger"]
        oyuncu["deger_kaynagi"] = "transfer_pazari"
    for alan in ("yas", "face"):
        if not oyuncu.get(alan) and pazar_kaydi.get(alan):
            oyuncu[alan] = pazar_kaydi[alan]


def oyuncu_transfer_degerini_belirle(oyuncu):
    _pazar_eksik_alanlarini_tamamla(oyuncu)
    if (oyuncu.get("deger") or 0) > 0:
        oyuncu.setdefault("deger_kaynagi", "mevcut")
        return oyuncu["deger"]

    oyuncu["deger"] = mantikli_random_deger_uret(oyuncu)
    oyuncu["deger_kaynagi"] = "random"
    return oyuncu["deger"]


def oyuncu_sezon_verisini_hazirla(p, kulup_adi=None):
    if kulup_adi:
        p["kulup"] = kulup_adi
    elif not p.get("kulup"):
        p["kulup"] = "Serbest"

    p.setdefault("enerji", 100)
    p.setdefault("gol", 0)
    p.setdefault("asist", 0)
    p.setdefault("mac", 0)
    p.setdefault("verimlilik", p.get("yetenek", 70))
    p.setdefault("sakat_gun", 0)
    p.setdefault("moral", 50)
    p.setdefault("populerlik", 50)
    p.setdefault("oduller", [])
    p.setdefault("kariyer_notlari", [])
    p.setdefault("ballon_dor_sayisi", 0)
    p.setdefault("ballon_dor_adayliklari", 0)
    p.setdefault("sezon_reyting_toplami", 0.0)
    p.setdefault("sezon_reyting_mac", 0)
    p.setdefault("ortalama_rating", 0.0)
    p.setdefault("son_mac_rating", 0.0)
    p.setdefault("ballon_dor_puani", 0.0)
    p.setdefault("ballon_dor_takim_bonus", 0)
    p.setdefault("ballon_dor_aday", False)
    oyuncu_transfer_degerini_belirle(p)
    return p


def oyuncuya_mac_isle(p, rating=None, kulup_adi=None):
    oyuncu_sezon_verisini_hazirla(p, kulup_adi)
    p["mac"] = p.get("mac", 0) + 1
    if rating is not None:
        rating = max(1.0, min(10.0, round(float(rating), 1)))
        p["sezon_reyting_toplami"] = round(p.get("sezon_reyting_toplami", 0.0) + rating, 2)
        p["sezon_reyting_mac"] = p.get("sezon_reyting_mac", 0) + 1
        p["ortalama_rating"] = round(p["sezon_reyting_toplami"] / max(1, p["sezon_reyting_mac"]), 2)
        p["son_mac_rating"] = rating
    return p


def tum_oyunculari_topla():
    havuz = tum_oyuncu_havuzunu_olustur()
    for p in havuz:
        oyuncu_sezon_verisini_hazirla(p, p.get("kulup"))
    return havuz


def takim_bonus_hesapla(kulup_adi, lig_siralama_haritasi=None, avrupa_siralama_haritasi=None):
    bonus = 0
    if lig_siralama_haritasi and kulup_adi in lig_siralama_haritasi:
        sira = lig_siralama_haritasi[kulup_adi]
        if sira == 1:
            bonus += 20
        elif sira <= 3:
            bonus += 5

    if avrupa_siralama_haritasi and kulup_adi in avrupa_siralama_haritasi:
        if avrupa_siralama_haritasi[kulup_adi] == 1:
            bonus += 10

    return bonus


def ballon_dor_sistemini_calistir():
    mevcut_sezon = kariyer_verisi.get("sezon", 2027)
    if kariyer_verisi.get("ballon_dor_islenen_sezon") == mevcut_sezon and kariyer_verisi.get("son_ballon_dor"):
        return kariyer_verisi.get("son_ballon_dor")

    tum_oyuncular = tum_oyunculari_topla()
    if not tum_oyuncular:
        return None

    lig_sirasi = sorted(KULUPLER, key=lambda x: x.get("p", 0), reverse=True) if KULUPLER else []
    lig_siralama_haritasi = {takim["ad"]: i + 1 for i, takim in enumerate(lig_sirasi)}

    avrupa_siralama_haritasi = {}
    if AVRUPA_KULUPLER:
        avrupa_sirasi = ucl_sirali_takimlar()
        avrupa_siralama_haritasi = {takim["ad"]: i + 1 for i, takim in enumerate(avrupa_sirasi)}

    for p in tum_oyuncular:
        oyuncu_sezon_verisini_hazirla(p)
        mac = p.get("mac", 0)
        ort_rating = p.get("ortalama_rating", 0.0)
        if ort_rating <= 0 and mac > 0:
            ort_rating = round(6.0 + min(2.2, max(0, p.get("yetenek", 70) - 70) * 0.04), 2)
            p["ortalama_rating"] = ort_rating
        takim_bonus = takim_bonus_hesapla(p.get("kulup"), lig_siralama_haritasi, avrupa_siralama_haritasi)
        performans_puani = (
            p.get("gol", 0) * 4
            + p.get("asist", 0) * 3
            + ort_rating * 10
            + mac
            + takim_bonus
        )
        p["ballon_dor_takim_bonus"] = takim_bonus
        p["ballon_dor_puani"] = round(performans_puani, 2)
        p["ballon_dor_aday"] = False

    sirali_oyuncular = sorted(
        tum_oyuncular,
        key=lambda oyuncu: (
            oyuncu.get("ballon_dor_puani", 0),
            oyuncu.get("gol", 0),
            oyuncu.get("asist", 0),
            oyuncu.get("ortalama_rating", 0),
            oyuncu.get("yetenek", 0),
        ),
        reverse=True,
    )

    if not sirali_oyuncular:
        return None

    aday_sayisi = min(BALLON_DOR_AYARLARI["aday_sayisi"], len(sirali_oyuncular))
    if len(sirali_oyuncular) >= 5:
        aday_sayisi = max(5, aday_sayisi)
    adaylar = sirali_oyuncular[:aday_sayisi]

    for aday in adaylar:
        aday["ballon_dor_aday"] = True
        aday["ballon_dor_adayliklari"] = aday.get("ballon_dor_adayliklari", 0) + 1

    kazanan = adaylar[0]
    rastgele_secim = False
    fark_yuzde = 100.0
    if len(adaylar) > 1:
        ilk, ikinci = adaylar[0], adaylar[1]
        taban = max(1.0, ilk.get("ballon_dor_puani", 0))
        fark_yuzde = abs(ilk.get("ballon_dor_puani", 0) - ikinci.get("ballon_dor_puani", 0)) / taban
        if fark_yuzde < BALLON_DOR_AYARLARI["rastgelelik_esigi"]:
            kazanan = random.choice([ilk, ikinci])
            rastgele_secim = True

    artis_orani = random.uniform(
        BALLON_DOR_AYARLARI["deger_artis_min"],
        BALLON_DOR_AYARLARI["deger_artis_max"],
    )
    kazanan["moral"] = min(100, kazanan.get("moral", 50) + BALLON_DOR_AYARLARI["kazanan_moral"])
    kazanan["deger"] = round(max(1, kazanan.get("deger", 1)) * (1 + artis_orani), 2)
    kazanan["populerlik"] = min(100, kazanan.get("populerlik", 50) + BALLON_DOR_AYARLARI["kazanan_populerlik"])
    kazanan["ballon_dor_sayisi"] = kazanan.get("ballon_dor_sayisi", 0) + 1

    etiket = f"{mevcut_sezon} Ballon d'Or kazananı"
    if etiket not in kazanan["oduller"]:
        kazanan["oduller"].append(etiket)
    if etiket not in kazanan["kariyer_notlari"]:
        kazanan["kariyer_notlari"].append(etiket)

    for aday in adaylar:
        if aday is not kazanan:
            aday["moral"] = min(
                100,
                aday.get("moral", 50) + random.randint(
                    BALLON_DOR_AYARLARI["aday_moral_min"],
                    BALLON_DOR_AYARLARI["aday_moral_max"],
                ),
            )

    sonuc = {
        "sezon": mevcut_sezon,
        "kazanan_isim": kazanan.get("isim", "Bilinmiyor"),
        "kulup": kazanan.get("kulup", "Serbest"),
        "puan": round(kazanan.get("ballon_dor_puani", 0), 2),
        "deger_artis_orani": round(artis_orani * 100, 1),
        "rastgele_secim": rastgele_secim,
        "fark_yuzde": round(fark_yuzde * 100, 2),
        "adaylar": [
            {
                "isim": aday.get("isim", "Bilinmiyor"),
                "kulup": aday.get("kulup", "Serbest"),
                "puan": round(aday.get("ballon_dor_puani", 0), 2),
                "gol": aday.get("gol", 0),
                "asist": aday.get("asist", 0),
                "mac": aday.get("mac", 0),
                "rating": round(aday.get("ortalama_rating", 0.0), 2),
                "takim_bonus": aday.get("ballon_dor_takim_bonus", 0),
            }
            for aday in adaylar
        ],
    }

    gecmis = kariyer_verisi.setdefault("ballon_dor_gecmisi", [])
    if not any(kayit.get("sezon") == mevcut_sezon for kayit in gecmis):
        gecmis.append(sonuc.copy())

    kariyer_verisi["son_ballon_dor"] = sonuc
    kariyer_verisi["ballon_dor_islenen_sezon"] = mevcut_sezon
    mesaj_ekle("Ballon d'Or", f"{mevcut_sezon} Ballon d'Or ödülünü {kazanan.get('isim', 'Bilinmiyor')} ({sonuc.get('kulup', '-')}) kazandı.")
    return sonuc


def sezonluk_istatistikleri_sifirla():
    for p in tum_oyunculari_topla():
        oyuncu_sezon_verisini_hazirla(p)
        p["gol"] = 0
        p["asist"] = 0
        p["mac"] = 0
        p["sezon_reyting_toplami"] = 0.0
        p["sezon_reyting_mac"] = 0
        p["ortalama_rating"] = 0.0
        p["son_mac_rating"] = 0.0
        p["ballon_dor_puani"] = 0.0
        p["ballon_dor_takim_bonus"] = 0
        p["ballon_dor_aday"] = False

# --- YARDIMCI FONKSİYONLAR ---
def diger_maclari_simule_et(haric_takimlar=None):
    kendi_takimim = kariyer_verisi["kulup"]["ad"]
    haric_takimlar = set(haric_takimlar or [])
    haric_takimlar.add(kendi_takimim)

    for takim_adi, oyuncular in TAKIM_OYUNCULARI.items():
        if takim_adi in haric_takimlar:
            continue

        gercek_kadro = []
        for p in oyuncular:
            oyuncu_sezon_verisini_hazirla(p, takim_adi)
            if p.get("kulup") == takim_adi:
                gercek_kadro.append(p)

        if len(gercek_kadro) == 0:
            continue

        sirali_kadro = sorted(gercek_kadro, key=lambda x: x.get("yetenek", 70), reverse=True)
        ilk_onbir = sirali_kadro[:11]
        takim_gucu = sum([p.get("yetenek", 70) for p in ilk_onbir]) / max(1, len(ilk_onbir))
        mac_oncesi_katki = {id(p): (p.get("gol", 0), p.get("asist", 0)) for p in ilk_onbir}

        if takim_gucu >= 85:
            toplam_gol = random.choices([0, 1, 2, 3, 4], weights=[10, 20, 30, 25, 15], k=1)[0]
        elif takim_gucu >= 80:
            toplam_gol = random.choices([0, 1, 2, 3], weights=[15, 30, 35, 20], k=1)[0]
        elif takim_gucu >= 75:
            toplam_gol = random.choices([0, 1, 2, 3], weights=[25, 40, 25, 10], k=1)[0]
        else:
            toplam_gol = random.choices([0, 1, 2], weights=[40, 40, 20], k=1)[0]

        for _ in range(toplam_gol):
            gol_adaylari = [p for p in ilk_onbir if p.get("mevki") != "KL"]
            if not gol_adaylari:
                gol_adaylari = ilk_onbir

            agirliklar = []
            for p in gol_adaylari:
                mevkisi = p.get("mevki", "")
                if mevkisi in ["ST", "RW", "LW", "SNT", "KANAT"]:
                    agirliklar.append(60)
                elif mevkisi in ["MO", "MOO", "MDO", "OS", "DOS"]:
                    agirliklar.append(30)
                elif mevkisi in ["LB", "RB", "CB", "DEF"]:
                    agirliklar.append(10)
                else:
                    agirliklar.append(5)

            golcu = random.choices(gol_adaylari, weights=agirliklar, k=1)[0]
            golcu["gol"] = golcu.get("gol", 0) + 1

            potansiyel_asistciler = [p for p in gol_adaylari if p["isim"] != golcu["isim"]]
            if potansiyel_asistciler and random.random() < 0.75:
                asist_yapan = random.choice(potansiyel_asistciler)
                asist_yapan["asist"] = asist_yapan.get("asist", 0) + 1

        for p in ilk_onbir:
            onceki_gol, onceki_asist = mac_oncesi_katki.get(id(p), (0, 0))
            mac_golu = max(0, p.get("gol", 0) - onceki_gol)
            mac_asisti = max(0, p.get("asist", 0) - onceki_asist)
            rating = (
                6.0
                + ((p.get("yetenek", 70) - 70) * 0.03)
                + random.uniform(-0.6, 0.8)
                + mac_golu * 1.25
                + mac_asisti * 0.80
                + (0.3 if toplam_gol >= 3 else 0)
            )
            oyuncuya_mac_isle(p, rating, takim_adi)

def kadro_doldur(kulup_ad):
    ana_liste = TAKIM_OYUNCULARI.get(kulup_ad, []).copy()
    while len(ana_liste) < 22:
        ana_liste.append({"isim": f"Genc {len(ana_liste)}", "mevki": "YD", "yetenek": random.randint(65, 75), "kulup": kulup_ad})

    for p in ana_liste:
        oyuncu_sezon_verisini_hazirla(p, kulup_ad)
        p.update({"enerji": 100, "sakat_gun": 0, "verimlilik": p.get("yetenek", 70)})
    TAKIM_OYUNCULARI[kulup_ad] = ana_liste.copy()
    return ana_liste

def takim_istatistik_siralamasi(kadro):
    return sorted(
        kadro,
        key=lambda oyuncu: (
            -oyuncu.get("gol", 0),
            -oyuncu.get("asist", 0),
            oyuncu.get("isim", "")
        )
    )

def mesaj_ekle(baslik, ozet):
    """Oyun içi olayları mesaj listesine ekler (en yeni en başta)."""
    if not isinstance(kariyer_verisi.get("mesajlar"), list):
        kariyer_verisi["mesajlar"] = []
    kariyer_verisi["mesajlar"].insert(0, {
        "baslik": str(baslik),
        "ozet": str(ozet),
        "gun": kariyer_verisi.get("gun", 1),
        "sezon": kariyer_verisi.get("sezon", 2027),
    })
    if len(kariyer_verisi["mesajlar"]) > 50:
        kariyer_verisi["mesajlar"] = kariyer_verisi["mesajlar"][:50]


def buton_ciz(yazi, x, y, w, h, renk=BUTON_RENGI, *, focusable=True):
    fare = pygame.mouse.get_pos()
    rect = pygame.Rect(x, y, w, h)
    uzerinde = rect.collidepoint(fare)
    pygame.draw.rect(screen, MAVI if uzerinde else renk, rect, border_radius=10)
    pygame.draw.rect(screen, BEYAZ, rect, 1, border_radius=10)
    txt = font_buton.render(yazi, True, BEYAZ)
    screen.blit(txt, txt.get_rect(center=rect.center))
    if not focusable:
        return uzerinde and pygame.mouse.get_pressed()[0]
    return _focus_polled_click(rect, uzerinde and pygame.mouse.get_pressed()[0])

def panel_ciz(x, y, w, h, dolgu=BUTON_RENGI, cerceve=ALTIN, yaricap=18, golge=True):
    rect = pygame.Rect(x, y, w, h)
    if golge:
        golge_rect = rect.move(0, 4)
        pygame.draw.rect(screen, (10, 18, 30), golge_rect, border_radius=yaricap)
    pygame.draw.rect(screen, dolgu, rect, border_radius=yaricap)
    pygame.draw.rect(screen, cerceve, rect, 2, border_radius=yaricap)
    return rect


def etiket_ciz(metin, x, y, arka_renk, yazi_renk=BEYAZ, padding_x=12, yukseklik=28):
    txt = font_oyuncu.render(metin, True, yazi_renk)
    rect = pygame.Rect(x, y, txt.get_width() + padding_x * 2, yukseklik)
    pygame.draw.rect(screen, arka_renk, rect, border_radius=14)
    screen.blit(txt, txt.get_rect(center=rect.center))
    return rect


def metni_kisalt(metin, limit=30):
    metin = str(metin)
    return metin if len(metin) <= limit else metin[:limit - 3] + '...'


# ============================================================
# [YENI] ANA YÖNETİM PANELİ - ORTAK UI YARDIMCILARI
# (Sadece yeni panel arayuzunde kullanilir; diger ekranlara dokunulmadi)
# ============================================================
SEKME_AKTIF = (108, 52, 199)      # Mor / violet (aktif sekme)
SEKME_AKTIF_ALT = (154, 98, 235)  # Acik mor
SEKME_PASIF = (92, 168, 222)      # Soft mavi / cyan (pasif sekme)
SEKME_PASIF_ALT = (140, 205, 240) # Acik cyan
PANEL_KOYU = (26, 40, 62)
PANEL_ACIK = (245, 247, 252)


def metni_ortalaya_ciz(yuzey, metin, font, renk, rect):
    """Metni verilen dikdortgenin tam ortasina cizer."""
    yazi = font.render(str(metin), True, renk)
    yuzey.blit(yazi, yazi.get_rect(center=rect.center))
    return yazi


def buyuk_buton_ciz(yazi, x, y, w, h, renk, yazi_renk=BEYAZ, font=None, cerceve_renk=SIYAH):
    """Taslaklardaki gibi kalin cerceveli, ortalanmis buyuk buton. Tiklandiysa True doner."""
    if font is None:
        font = font_buton
    fare = pygame.mouse.get_pos()
    rect = pygame.Rect(x, y, w, h)
    uzerinde = rect.collidepoint(fare)
    cizim_renk = renk
    if uzerinde:
        cizim_renk = (min(255, renk[0] + 35), min(255, renk[1] + 35), min(255, renk[2] + 35))
    golge_rect = rect.move(0, 4)
    pygame.draw.rect(screen, (10, 16, 26), golge_rect, border_radius=14)
    pygame.draw.rect(screen, cizim_renk, rect, border_radius=14)
    pygame.draw.rect(screen, cerceve_renk, rect, 3, border_radius=14)
    metni_ortalaya_ciz(screen, yazi, font, yazi_renk, rect)
    return _focus_polled_click(rect, uzerinde and pygame.mouse.get_pressed()[0])


def ust_sekme_cubugu_ciz(aktif_sekme):
    """Ekranin en ustundeki 4 sekmeli gezinti cubugu. Tiklanan sekmenin adini dondurur."""
    sekmeler = ["Ana Menü", "Transfer", "Kadro", "Sosyal Medya"]
    bar_y, bar_h = 8, 60
    bosluk = 14
    toplam_bosluk = bosluk * (len(sekmeler) + 1)
    sekme_w = (WIDTH - toplam_bosluk) // len(sekmeler)
    tiklanan = None
    for i, ad in enumerate(sekmeler):
        x = bosluk + i * (sekme_w + bosluk)
        rect = pygame.Rect(x, bar_y, sekme_w, bar_h)
        aktif = (ad == aktif_sekme)
        renk = SEKME_AKTIF if aktif else SEKME_PASIF
        fare = pygame.mouse.get_pos()
        uzerinde = rect.collidepoint(fare)
        if uzerinde and not aktif:
            renk = SEKME_PASIF_ALT
        if uzerinde and aktif:
            renk = SEKME_AKTIF_ALT
        golge = rect.move(0, 3)
        pygame.draw.rect(screen, (10, 16, 26), golge, border_radius=12)
        pygame.draw.rect(screen, renk, rect, border_radius=12)
        pygame.draw.rect(screen, BEYAZ if aktif else (200, 225, 245), rect, 2, border_radius=12)
        metni_ortalaya_ciz(screen, ad, font_buton, BEYAZ if aktif else (16, 32, 52), rect)
        if aktif:
            # Aktif sekmenin altina vurgu cizgisi
            pygame.draw.rect(screen, ALTIN, (rect.x + 20, rect.bottom - 7, rect.width - 40, 5), border_radius=3)
        if not aktif and _focus_polled_click(rect, uzerinde and pygame.mouse.get_pressed()[0]):
            tiklanan = ad
    return tiklanan


def mini_saha_ciz(saha_rect, takim_adi):
    """Kadro sekmesinin sol paneli: cizgili futbol sahasi + ilk 11 ikonlari.
    Tiklaninca True doner (detayli Kadro Ekrani acilir)."""
    pygame.draw.rect(screen, (24, 100, 32), saha_rect, border_radius=12)
    # Saha cim seritleri
    serit_sayisi = 6
    for s in range(serit_sayisi):
        if s % 2 == 0:
            serit = pygame.Rect(saha_rect.x, saha_rect.y + s * (saha_rect.height // serit_sayisi),
                                saha_rect.width, saha_rect.height // serit_sayisi + 1)
            pygame.draw.rect(screen, (32, 122, 42), serit)
    cizgi = BEYAZ
    # Dis cizgiler
    pygame.draw.rect(screen, cizgi, saha_rect.inflate(-16, -16), 2, border_radius=4)
    ic = saha_rect.inflate(-16, -16)
    # Orta saha cizgisi ve orta yuvarlak
    pygame.draw.line(screen, cizgi, (ic.centerx, ic.top), (ic.centerx, ic.bottom), 2)
    pygame.draw.circle(screen, cizgi, ic.center, 42, 2)
    pygame.draw.circle(screen, cizgi, ic.center, 4)
    # Ceza sahalar
    ceza_w, ceza_h = 52, int(ic.height * 0.55)
    pygame.draw.rect(screen, cizgi, (ic.left, ic.centery - ceza_h // 2, ceza_w, ceza_h), 2)
    pygame.draw.rect(screen, cizgi, (ic.right - ceza_w, ic.centery - ceza_h // 2, ceza_w, ceza_h), 2)
    kale_h = int(ic.height * 0.28)
    pygame.draw.rect(screen, cizgi, (ic.left, ic.centery - kale_h // 2, 22, kale_h), 2)
    pygame.draw.rect(screen, cizgi, (ic.right - 22, ic.centery - kale_h // 2, 22, kale_h), 2)

    # --- Ilk 11 yerlesimi (aktif dizilise gore) ---
    dizilisler = ["4-3-3", "4-4-2", "3-5-2"]
    dizilis_idx = kariyer_verisi.get("dizilis_idx", 0) % len(dizilisler)
    aktif_dizilis = dizilisler[dizilis_idx]
    # Normalize edilmis (0-1) pozisyonlar; dikey hucum yonunde (asagidan yukari)
    if aktif_dizilis == "4-4-2":
        norm = [(0.50, 0.93), (0.15, 0.70), (0.38, 0.72), (0.62, 0.72), (0.85, 0.70),
                (0.15, 0.45), (0.38, 0.47), (0.62, 0.47), (0.85, 0.45), (0.35, 0.20), (0.65, 0.20)]
    elif aktif_dizilis == "3-5-2":
        norm = [(0.50, 0.93), (0.25, 0.72), (0.50, 0.74), (0.75, 0.72),
                (0.12, 0.48), (0.31, 0.50), (0.50, 0.45), (0.69, 0.50), (0.88, 0.48),
                (0.35, 0.20), (0.65, 0.20)]
    else:  # 4-3-3
        norm = [(0.50, 0.93), (0.15, 0.70), (0.38, 0.72), (0.62, 0.72), (0.85, 0.70),
                (0.28, 0.47), (0.50, 0.42), (0.72, 0.47), (0.18, 0.20), (0.50, 0.16), (0.82, 0.20)]

    kadro = kariyer_verisi.get("kadro", [])
    fare = pygame.mouse.get_pos()
    tiklandi = False
    for i in range(min(11, len(kadro))):
        nx, ny = norm[i]
        px = ic.left + int(nx * ic.width)
        py = ic.top + int(ny * ic.height)
        p = kadro[i]
        renk = KIRMIZI if p.get("sakat_gun", 0) > 0 else ALTIN
        dist2 = (fare[0] - px) ** 2 + (fare[1] - py) ** 2
        if dist2 < 18 * 18:
            renk = YESIL if p.get("sakat_gun", 0) <= 0 else KIRMIZI
        pygame.draw.circle(screen, renk, (px, py), 13)
        pygame.draw.circle(screen, SIYAH, (px, py), 13, 2)
        mevki = font_agac.render(p.get("mevki", ""), True, SIYAH)
        screen.blit(mevki, mevki.get_rect(center=(px, py)))
        isim_yazi = font_agac.render(metni_kisalt(p.get("isim", ""), 10), True, BEYAZ)
        isim_rect = isim_yazi.get_rect(center=(px, py + 22))
        arka = isim_rect.inflate(6, 2)
        pygame.draw.rect(screen, (15, 60, 22), arka, border_radius=4)
        screen.blit(isim_yazi, isim_rect)
        # [YENI] Mevki uyumsuzlugu uyarisi (mini saha / ilk 11)
        if not is_natural_position(p, _dizilis_slot_mevkisi(aktif_dizilis, i)):
            draw_position_warning(screen, (px, py), 13)
        if dist2 < 18 * 18 and pygame.mouse.get_pressed()[0]:
            tiklandi = True

    # Saha ustune tiklama kontrolu
    if _focus_polled_click(saha_rect, saha_rect.collidepoint(fare) and pygame.mouse.get_pressed()[0]):
        tiklandi = True
    # Dizilis etiketi
    etiket = font_log.render(aktif_dizilis, True, ALTIN)
    etiket_rect = etiket.get_rect(topright=(saha_rect.right - 12, saha_rect.y + 8))
    pygame.draw.rect(screen, (15, 60, 22), etiket_rect.inflate(10, 4), border_radius=6)
    screen.blit(etiket, etiket_rect)
    return tiklandi


# --- EKRANLAR --- 
# --- YENİ EKLENEN FOTOĞRAF YÜKLEME KISMI (Sistem Ayarları Altına Ekleyin) ---
try:
    # Gönderdiğin fotoğrafın tam dosya adını buraya yazıyoruz. Boyutlandırma yok.
    KAYIT_FOTO = pygame.image.load("816Bb-0cx7L.jpg").convert_alpha()
except pygame.error as e:
    print(f"Kayıt ekranı fotoğrafı yüklenemedi: {e}")
    KAYIT_FOTO = None 
except FileNotFoundError:
    print(f"Fotoğraf dosyası bulunamadı.")
    KAYIT_FOTO = None


# --- YENİLENEN KAYIT EKRANI KODU ---
def kayit_ekrani():
    global KULUPLER
    isim = ""
    secili_lig = None
    secili_k_idx = -1
    input_aktif = False
    imlec_timer = 0
    
    # --- KAYDIRMA (SCROLL) DEĞİŞKƏNLƏRİ ---
    kayit_index = 0
    gorunur_sayi = 6
    
    input_rect = pygame.Rect(100, 150, 450, 70)

    while True:
        _focus_begin_frame(("kayit", secili_lig))
        # --- YENİ EKLENEN FOTOĞRAF ÇİZİMİ ---
        # Boyutu HİÇBİR ŞEKİLDE değiştirilmeden (0, 0) koordinatından çizilir.
        # Böylece butonlar ve arayüz fotoğrafın üzerine (ön plana) tam oturur.
        if KAYIT_FOTO:
            screen.blit(KAYIT_FOTO, (0, 0))
        else:
            screen.fill(ARKA_PLAN)
        # -----------------------------------

        imlec_timer += 1
        
        # --- 1. ADINIZI YAZIN ---
        pygame.draw.rect(screen, ALTIN if input_aktif else BUTON_RENGI, input_rect, border_radius=12)
        _focus_event_button(input_rect)
        
        imlec = "|" if input_aktif and (imlec_timer // 20) % 2 == 0 else ""
        text_surface = font_buton.render(isim + imlec, True, BEYAZ)
        screen.blit(text_surface, (115, 165))
        screen.blit(font_log.render("MENECER ADI (YAZMAQ ÜÇÜN BURA TOXUN):", True, ALTIN), (100, 110))

        # --- 2. LİQA VƏ KLUB SEÇİMİ (KAYDIRMALI) ---
        baslik = "LİQA SEÇİN" if secili_lig is None else f"{secili_lig} KLUBLARI"
        screen.blit(font_baslik.render(baslik, True, BEYAZ), (700, 50))

        gosterilecek_liste = list(TUM_LIGLER.keys()) if secili_lig is None else TUM_LIGLER[secili_lig]

        for i in range(gorunur_sayi):
            gercek_idx = kayit_index + i
            if gercek_idx < len(gosterilecek_liste):
                eleman = gosterilecek_liste[gercek_idx]
                
                if secili_lig is None:
                    # Liqa düymələri
                    if buton_ciz(eleman, 700, 120 + (i*85), 400, 70, BUTON_RENGI):
                        secili_lig = eleman
                        kayit_index = 0
                        pygame.time.delay(150)
                else:
                    # Əgər klubu səhvən sadəcə ad olaraq (mətn) yazıbsa, onu ayır, xəta verməsin
                    if isinstance(eleman, str):
                        klub_adi = eleman
                    else:
                        klub_adi = eleman.get("ad", "Bilinmeyen")
                        
                    renk = ALTIN if secili_k_idx == gercek_idx else BUTON_RENGI
                    if buton_ciz(klub_adi, 700, 120 + (i*85), 400, 70, renk):
                        secili_k_idx = gercek_idx

        # --- YUKARI / AŞAĞI BUTONLARI ---
        if kayit_index > 0:
            if buton_ciz("YUKARI", 1120, 120, 130, 70, MAVI):
                kayit_index -= 1
                pygame.time.delay(120)
                
        if kayit_index + gorunur_sayi < len(gosterilecek_liste):
            if buton_ciz("AŞAĞI", 1120, 120 + ((gorunur_sayi - 1) * 85), 130, 70, MAVI):
                kayit_index += 1
                pygame.time.delay(120)

        if secili_lig is not None:
            if buton_ciz("< GERİ", 700, 650, 150, 50, KIRMIZI):
                secili_lig = None
                secili_k_idx = -1
                kayit_index = 0

        # --- 3. OYUNA BAŞLA BUTONU ---
        if isim.strip() != "" and secili_k_idx != -1:
            if buton_ciz("OYUNA BAŞLA", 100, 600, 450, 80, YESIL):
                
                # SİHİRLİ TOXUNUŞ: Əgər siyahıda sadəcə mətn ("Qarabağ") qalıbsa, 
                # avtomatik olaraq arxa planda oyun onu lüğətə ({"ad": "Qarabağ", "p": 0...}) çevirir!
                duzeldilmis_klublar = []
                for t in TUM_LIGLER[secili_lig]:
                    if isinstance(t, str):
                        duzeldilmis_klublar.append({"ad": t, "p": 0, "butce": 20})
                    else:
                        duzeldilmis_klublar.append(t)
                        
                KULUPLER[:] = duzeldilmis_klublar
                
                kariyer_verisi["isim"] = isim
                kariyer_verisi["kulup"] = KULUPLER[secili_k_idx]
                kariyer_verisi["kadro"] = kadro_doldur(KULUPLER[secili_k_idx]["ad"])
                kariyer_ucl_verisini_hazirla()
                kariyer_verisi["avrupa_lig_katilim"] = any(k.get("ad") == KULUPLER[secili_k_idx]["ad"] for k in AVRUPA_KULUPLER)
                if kariyer_verisi["avrupa_lig_katilim"]:
                    ucl_takimi_ekle_gerekiyorsa(KULUPLER[secili_k_idx]["ad"])
                return "ana_menu"

        # --- HADİSƏLƏR (MOBİL KLAVİATURA) ---
        _focus_publish(("kayit", secili_lig))
        for event in _focus_events(lambda: input_aktif):
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if input_rect.collidepoint(event.pos):
                    input_aktif = True
                    pygame.key.start_text_input()
                else:
                    input_aktif = False
                    pygame.key.stop_text_input()

            if input_aktif:
                if event.type == pygame.TEXTINPUT:
                    if len(isim) < 15:
                        isim += event.text
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_BACKSPACE:
                        isim = isim[:-1]
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        input_aktif = False
                        pygame.key.stop_text_input()

        draw_focus_indicator(screen)
        pygame.display.flip()





def gol_kralligi_ekrani():
    tum_oyuncular = []
    kendi_kulup_adi = kariyer_verisi["kulup"]["ad"] #
    # Transfer kontrolü için isim listesi
    kendi_kadro_isimler = [p["isim"] for p in kariyer_verisi["kadro"]] #

    # 1. Kendi oyuncularını ekle
    for p in kariyer_verisi["kadro"]:
        tum_oyuncular.append({
            "isim": p["isim"],
            "kulup": kendi_kulup_adi,
            "gol": p.get("gol", 0)
        }) #

    # 2. DÜNYADAKİ TÜM TAKIMLARI TARA (TAKIM_OYUNCULARI sözlüğünü gezer)
    # Bu döngü Real Madrid, Kasımpaşa, Bayern Münih gibi her takıma girer
    for kulup_adi, oyuncu_listesi in TAKIM_OYUNCULARI.items():
        # Eğer bu kulüp bizim kulübümüzse atla (zaten yukarıda ekledik)
        if kulup_adi == kendi_kulup_adi:
            continue
        
        for p in oyuncu_listesi:
            # KRİTİK: Eğer oyuncu bizde değilse listeye ekle (Transfer kontrolü)
            if p["isim"] not in kendi_kadro_isimler:
                tum_oyuncular.append({
                    "isim": p["isim"],
                    "kulup": kulup_adi,
                    "gol": p.get("gol", 0)
                }) #

    # 3. SIRALAMA: En çok gol atanı başa al
    sirali = sorted(tum_oyuncular, key=lambda x: x["gol"], reverse=True)[:10]

    while True:
        _focus_begin_frame(("gol_kralligi",))
        screen.fill(ARKA_PLAN)
        
        # Başlık
        screen.blit(font_baslik.render("DÜNYA GOL KRALLIĞI", True, ALTIN), (WIDTH//2 - 200, 30))
        
        # Tablo Çizimi
        for i, p in enumerate(sirali):
            y_konum = 150 + (i * 40)
            # Bizim oyuncular Yeşil, Diğerleri Beyaz
            renk = YESIL if p["isim"] in kendi_kadro_isimler else BEYAZ
            
            txt = f"{i+1}. {p['isim'][:18]} | {p['kulup'][:15]} | Gol: {p['gol']}"
            screen.blit(font_liste.render(txt, True, renk), (150, y_konum))

        # Geri Dönüş
        if buton_ciz("ANA MENU", 1100, 20, 150, 50, KIRMIZI):
            return "ana_menu"

        _focus_publish(("gol_kralligi",))
        for e in _focus_events():
            if e.type == pygame.QUIT: pygame.quit(); sys.exit()
        draw_focus_indicator(screen)
        pygame.display.flip()

# Başlangıçta verilerin boş kalmaması için bu listeleri kariyer_verisi içine eklediğinden emin ol
if "altyapi" not in kariyer_verisi: kariyer_verisi["altyapi"] = []
if "teknik_ekip" not in kariyer_verisi: kariyer_verisi["teknik_ekip"] = []
# --- İSİM HAVUZLARI (Global Alan) ---
ISIMLER = ["Arda", "Luca", "Mert", "Kevin", "Oğuz", "Marc", "Selim", "Diego", "Eren", "Kaan", "Leo"]
SOYISIMLER = ["Yılmaz", "Rossi", "Demir", "Müller", "Şahin", "Silva", "Aydın", "Yıldız", "Arslan", "Smith"]

def ekip_ekrani():
    ana_sekme = "altyapi"
    teknik_sekme = "aktif"
    
    # Veri yapılarını kontrol et ve başlat
    if "altyapi" not in kariyer_verisi: kariyer_verisi["altyapi"] = []
    if "teknik_ekip" not in kariyer_verisi: kariyer_verisi["teknik_ekip"] = []

    # EĞER ALTYAPI BOŞSA İLK KEZ OLUŞTUR (Bir daha rastgele değişmez)
    if len(kariyer_verisi["altyapi"]) == 0:
        mevkiler = ["KL", "CB", "LB", "RB", "MDO", "MO", "MOO", "LW", "RW", "ST"]
        for _ in range(6):
            tam_isim = f"{random.choice(ISIMLER)} {random.choice(SOYISIMLER)}"
            yeni_genc = {
                "isim": tam_isim,
                "yas": random.randint(15, 18),
                "yetenek": random.randint(45, 60),
                "potansiyel": random.randint(75, 95),
                "mevki": random.choice(mevkiler),
                "enerji": 100, "gol": 0, "asist": 0, "sakat_gun": 0
            }
            kariyer_verisi["altyapi"].append(yeni_genc)

    # Teknik ekip aday havuzu (Gerçekçi bütçe: 5-20 birim arası)
    aday_ekip_listesi = [
        {"isim": "Giovanni Rossi", "rol": "Antrenör", "seviye": 3, "maliyet": 15},
        {"isim": "Q.İltifat", "rol": "Yardımcı Antrenör", "seviye": 6, "maliyet": 0.1},
        {"isim": "Hans Müller", "rol": "Gözlemci", "seviye": 4, "maliyet": 25},
        {"isim": "Carlos Silva", "rol": "Kondisyoner", "seviye": 2, "maliyet": 10},
        {"isim": "Ahmet Demir", "rol": "Analizci", "seviye": 3, "maliyet": 18}
    ]

    while True:
        _focus_begin_frame(("ekip", ana_sekme, teknik_sekme if ana_sekme == "teknik" else None))
        screen.fill((255, 255, 255)) # Bembeyaz arka plan
        
        # --- ÜST SEKMELER ---
        if buton_ciz("ALTYAPI", 50, 20, 250, 50, MAVI if ana_sekme == "altyapi" else BUTON_RENGI):
            ana_sekme = "altyapi"
        if buton_ciz("TEKNİK EKİP", 320, 20, 250, 50, MAVI if ana_sekme == "teknik" else BUTON_RENGI):
            ana_sekme = "teknik"
        
        if buton_ciz("GERİ", 1050, 20, 180, 50, KIRMIZI): return "ana_menu"

        # --- ALTYAPI SEKMESİ ---
        if ana_sekme == "altyapi":
            txt = font_baslik.render("ALTYAPI (U19)", True, SIYAH)
            screen.blit(txt, (50, 90))
            
            for i, genc in enumerate(kariyer_verisi["altyapi"]):
                y_pos = 150 + i * 85
                pygame.draw.rect(screen, (240, 240, 240), (50, y_pos, 1180, 75), border_radius=10)
                
                bilgi = f"{genc['isim']} ({genc['yas']}) - {genc['mevki']} | Yetenek: {genc['yetenek']} | Pot: {genc['potansiyel']}"
                screen.blit(font_liste.render(bilgi, True, SIYAH), (70, y_pos + 25))
                
                if buton_ciz("KADROYA AL (ÜCRETSİZ)", 900, y_pos + 12, 310, 50, YESIL):
                    oyuncuyu_kulube_tasi(genc, kariyer_verisi["kulup"]["ad"])
                    kariyer_verisi["altyapi"].remove(genc)
                    break

        # --- TEKNİK EKİP SEKMESİ ---
        elif ana_sekme == "teknik":
            if buton_ciz("AKTİF EKİP", 50, 100, 250, 45, YESIL if teknik_sekme == "aktif" else BUTON_RENGI):
                teknik_sekme = "aktif"
            if buton_ciz("YENİ ÜYELER", 320, 100, 250, 45, YESIL if teknik_sekme == "yeni" else BUTON_RENGI):
                teknik_sekme = "yeni"

            if teknik_sekme == "aktif":
                txt = font_baslik.render("TEKNIK EKIP", True, SIYAH)
                for i, uye in enumerate(kariyer_verisi["teknik_ekip"]):
                    y_pos = 200 + i * 80
                    pygame.draw.rect(screen, (230, 240, 250), (50, y_pos, 1180, 70), border_radius=10)
                    bilgi = f"{uye['isim']} | {uye['rol']} | Seviye: {uye['seviye']}"
                    screen.blit(font_liste.render(bilgi, True, SIYAH), (70, y_pos + 20))
                    
                    if buton_ciz("KOV", 1050, y_pos + 10, 150, 50, KIRMIZI):
                        kariyer_verisi["teknik_ekip"].remove(uye)
                        break

            elif teknik_sekme == "yeni":
                # Sadece teknik ekipte olmayanları göster (Aynı adamı tekrar almamak için)
                mevcut_isimler = [u["isim"] for u in kariyer_verisi["teknik_ekip"]]
                aktif_adaylar = [a for a in aday_ekip_listesi if a["isim"] not in mevcut_isimler]
                
                for i, aday in enumerate(aktif_adaylar):
                    y_pos = 200 + i * 85
                    pygame.draw.rect(screen, (245, 245, 245), (50, y_pos, 1180, 75), border_radius=10)
                    bilgi = f"{aday['isim']} | {aday['rol']} | Seviye: {aday['seviye']} | Ücret: {aday['maliyet']}M €"
                    screen.blit(font_liste.render(bilgi, True, SIYAH), (70, y_pos + 25))
                    
                    if buton_ciz("İŞE AL", 1000, y_pos + 12, 200, 50, MAVI):
                        if kariyer_verisi["kulup"]["butce"] >= aday["maliyet"]:
                            kariyer_verisi["kulup"]["butce"] -= aday["maliyet"]
                            kariyer_verisi["teknik_ekip"].append(aday)
                            break

        _focus_publish(("ekip", ana_sekme, teknik_sekme if ana_sekme == "teknik" else None))
        for e in _focus_events():
            if e.type == pygame.QUIT: pygame.quit(); sys.exit()
        draw_focus_indicator(screen)
        pygame.display.flip()



def avrupa_kuluplerini_normallestir():
    global AVRUPA_KULUPLER
    yeni_liste = []
    gorulen = set()
    for kulup in AVRUPA_KULUPLER:
        if isinstance(kulup, dict):
            ad = kulup.get("ad")
            ekstra = kulup
        else:
            ad = str(kulup)
            ekstra = None
        if not ad or ad in gorulen:
            continue
        yeni_liste.append(avrupa_kulubu_olustur(ad, ekstra))
        gorulen.add(ad)
    AVRUPA_KULUPLER = yeni_liste


def kariyer_ucl_verisini_hazirla():
    avrupa_kuluplerini_normallestir()
    varsayilanlar = {
        "avrupa_lig_katilim": False,
        "avrupa_mac_sayisi": 0,
        "genel_mac_index": 0,
        "ucl_hafta": 1,
        "ucl_tur": "Lig",
        "ucl_mac_index": 0,
        "kendi_ucl_maci_var": False,
        "siradaki_ucl_rakip": None,
        "ucl_aktif_eslesme": None,
        "ucl_sampiyonu": None,
    }
    for anahtar, deger in varsayilanlar.items():
        kariyer_verisi.setdefault(anahtar, deger)
    for liste_anahtari in ("oynanan_ucl_rakipleri", "ucl_son16_dogrudan"):
        if liste_anahtari not in kariyer_verisi or not isinstance(kariyer_verisi[liste_anahtari], list):
            kariyer_verisi[liste_anahtari] = []
    for sozluk_anahtari in ("ucl_eslesmeler", "ucl_tum_turlar"):
        if sozluk_anahtari not in kariyer_verisi or not isinstance(kariyer_verisi[sozluk_anahtari], dict):
            kariyer_verisi[sozluk_anahtari] = {}
    if "mesajlar" not in kariyer_verisi or not isinstance(kariyer_verisi["mesajlar"], list):
        kariyer_verisi["mesajlar"] = []


def ucl_takim_bul(kulup_adi):
    for kulup in AVRUPA_KULUPLER:
        if kulup.get("ad") == kulup_adi:
            return kulup
    return None


def ucl_takimi_ekle_gerekiyorsa(kulup_adi):
    if kulup_adi and not ucl_takim_bul(kulup_adi):
        AVRUPA_KULUPLER.append(avrupa_kulubu_olustur(kulup_adi))


def ucl_sirali_takimlar():
    return sorted(
        AVRUPA_KULUPLER,
        key=lambda x: (
            x.get("p", 0),
            x.get("attigi_gol", 0) - x.get("yedigi_gol", 0),
            x.get("attigi_gol", 0),
            x.get("ad", "")
        ),
        reverse=True,
    )


def ucl_takim_gucu(kulup_adi):
    oyuncular = TAKIM_OYUNCULARI.get(kulup_adi, [])
    if oyuncular:
        ilk_onbir = sorted(oyuncular, key=lambda x: x.get("yetenek", 70), reverse=True)[:11]
        if ilk_onbir:
            return sum(p.get("yetenek", 70) for p in ilk_onbir) / len(ilk_onbir)
    for lig_takimi in KULUPLER:
        if lig_takimi.get("ad") == kulup_adi:
            return 68 + lig_takimi.get("butce", 20) * 0.15
    return 75


def ucl_rastgele_skor_uret(ev_sahibi, deplasman):
    ev_gucu = ucl_takim_gucu(ev_sahibi) + 2.5
    dep_gucu = ucl_takim_gucu(deplasman)
    fark = ev_gucu - dep_gucu
    ev_baz = max(0.25, min(3.8, 1.45 + fark / 18.0 + random.uniform(-0.35, 0.45)))
    dep_baz = max(0.20, min(3.3, 1.10 - fark / 20.0 + random.uniform(-0.40, 0.35)))
    ev_skor = int(max(0, round(ev_baz + random.uniform(-0.7, 0.8))))
    dep_skor = int(max(0, round(dep_baz + random.uniform(-0.7, 0.7))))
    if random.random() < 0.07:
        ev_skor += 1
    if random.random() < 0.05:
        dep_skor += 1
    return ev_skor, dep_skor


def ucl_takvim_sirasi_mi():
    kariyer_ucl_verisini_hazirla()
    return (
        kariyer_verisi.get("avrupa_lig_katilim", False)
        and kariyer_verisi.get("ucl_tur") != "Bitti"
        and kariyer_verisi.get("genel_mac_index", 0) % 2 == 1
    )


def ucl_takim_durumunu_ayarla(kulup_adi, durum):
    takim = ucl_takim_bul(kulup_adi)
    if takim:
        takim["elenme_durumu"] = durum


def ucl_eslesme_olustur(tur, eslesme_adi, takim1, takim2, tek_mac=False):
    maclar = [{"ev": takim1, "dep": takim2, "skor_ev": None, "skor_dep": None, "oynandi": False}]
    if not tek_mac:
        maclar.append({"ev": takim2, "dep": takim1, "skor_ev": None, "skor_dep": None, "oynandi": False})
    return {
        "tur": tur,
        "ad": eslesme_adi,
        "takim1": takim1,
        "takim2": takim2,
        "skor1": 0,
        "skor2": 0,
        "deplasman1": 0,
        "deplasman2": 0,
        "kazanan": None,
        "karar": None,
        "oynanan_mac": 0,
        "maclar": maclar,
        "tek_mac": tek_mac,
    }


def ucl_lig_asamasi_mac_ayarla():
    kariyer_ucl_verisini_hazirla()
    if not kariyer_verisi.get("avrupa_lig_katilim", False):
        kariyer_verisi["kendi_ucl_maci_var"] = False
        kariyer_verisi["siradaki_ucl_rakip"] = None
        return None
    if kariyer_verisi.get("ucl_tur") != "Lig" or kariyer_verisi.get("ucl_hafta", 1) > 8:
        kariyer_verisi["kendi_ucl_maci_var"] = False
        kariyer_verisi["siradaki_ucl_rakip"] = None
        return None

    kendi_takim = kariyer_verisi.get("kulup", {}).get("ad")
    ucl_takimi_ekle_gerekiyorsa(kendi_takim)
    oynananlar = kariyer_verisi.setdefault("oynanan_ucl_rakipleri", [])
    mevcut_rakip = kariyer_verisi.get("siradaki_ucl_rakip")
    if mevcut_rakip and mevcut_rakip not in oynananlar and mevcut_rakip != kendi_takim:
        kariyer_verisi["kendi_ucl_maci_var"] = True
        return mevcut_rakip

    uygunlar = [
        kulup["ad"]
        for kulup in AVRUPA_KULUPLER
        if kulup.get("ad") != kendi_takim and kulup.get("ad") not in oynananlar
    ]
    if not uygunlar:
        kariyer_verisi["kendi_ucl_maci_var"] = False
        kariyer_verisi["siradaki_ucl_rakip"] = None
        return None

    rakip = random.choice(uygunlar)
    kariyer_verisi["siradaki_ucl_rakip"] = rakip
    kariyer_verisi["kendi_ucl_maci_var"] = True
    return rakip


def ucl_lig_diger_maclarini_simule_et(haric_takimlar=None):
    kariyer_ucl_verisini_hazirla()
    haric_takimlar = set(haric_takimlar or [])
    takim_adlari = [k["ad"] for k in AVRUPA_KULUPLER if k.get("ad") not in haric_takimlar]
    random.shuffle(takim_adlari)
    for i in range(0, len(takim_adlari) - 1, 2):
        takim1 = ucl_takim_bul(takim_adlari[i])
        takim2 = ucl_takim_bul(takim_adlari[i + 1])
        if not takim1 or not takim2:
            continue
        gol1, gol2 = ucl_rastgele_skor_uret(takim1["ad"], takim2["ad"])
        takim1["attigi_gol"] += gol1
        takim1["yedigi_gol"] += gol2
        takim2["attigi_gol"] += gol2
        takim2["yedigi_gol"] += gol1
        if gol1 > gol2:
            takim1["p"] += 3
        elif gol2 > gol1:
            takim2["p"] += 3
        else:
            takim1["p"] += 1
            takim2["p"] += 1


def ucl_guncel_tur_eslesmeleri():
    return kariyer_verisi.get("ucl_tum_turlar", {}).get(kariyer_verisi.get("ucl_tur"), {})


def ucl_eleme_turu_mac_ayarla():
    kariyer_ucl_verisini_hazirla()
    tur = kariyer_verisi.get("ucl_tur")
    if tur in ("Lig", "Bitti"):
        kariyer_verisi["kendi_ucl_maci_var"] = False
        kariyer_verisi["ucl_aktif_eslesme"] = None
        return None

    kendi_takim = kariyer_verisi.get("kulup", {}).get("ad")
    eslesmeler = ucl_guncel_tur_eslesmeleri()
    mac_index = kariyer_verisi.get("ucl_mac_index", 0)
    for eslesme_adi in sorted(eslesmeler.keys()):
        eslesme = eslesmeler[eslesme_adi]
        if eslesme.get("kazanan"):
            continue
        if kendi_takim not in (eslesme.get("takim1"), eslesme.get("takim2")):
            continue
        kullanilacak_index = min(mac_index, len(eslesme.get("maclar", [])) - 1)
        mac = eslesme["maclar"][kullanilacak_index]
        if mac.get("oynandi"):
            continue
        rakip = mac["dep"] if mac["ev"] == kendi_takim else mac["ev"]
        kariyer_verisi["kendi_ucl_maci_var"] = True
        kariyer_verisi["ucl_aktif_eslesme"] = eslesme_adi
        return {
            "rakip": rakip,
            "mac_index": kullanilacak_index,
            "ev_sahibi": mac["ev"],
            "tur": tur,
            "tek_mac": eslesme.get("tek_mac", False),
        }
    kariyer_verisi["kendi_ucl_maci_var"] = False
    kariyer_verisi["ucl_aktif_eslesme"] = None
    return None


def ucl_eslesme_macini_kaydet(eslesme, mac_index, ev_skor, dep_skor):
    mac = eslesme["maclar"][mac_index]
    if mac.get("oynandi"):
        return
    mac["skor_ev"] = ev_skor
    mac["skor_dep"] = dep_skor
    mac["oynandi"] = True
    eslesme["oynanan_mac"] += 1

    if mac["ev"] == eslesme["takim1"]:
        eslesme["skor1"] += ev_skor
        eslesme["skor2"] += dep_skor
        eslesme["deplasman2"] += dep_skor
    else:
        eslesme["skor2"] += ev_skor
        eslesme["skor1"] += dep_skor
        eslesme["deplasman1"] += dep_skor


def ucl_eslesme_kazananini_belirle(eslesme):
    if eslesme.get("tek_mac"):
        mac = eslesme["maclar"][0]
        if mac["skor_ev"] > mac["skor_dep"]:
            eslesme["kazanan"] = mac["ev"]
            eslesme["karar"] = "90 Dakika"
        elif mac["skor_dep"] > mac["skor_ev"]:
            eslesme["kazanan"] = mac["dep"]
            eslesme["karar"] = "90 Dakika"
        else:
            eslesme["kazanan"] = random.choice([mac["ev"], mac["dep"]])
            eslesme["karar"] = "Penaltılar"
        return eslesme["kazanan"]

    if eslesme["skor1"] > eslesme["skor2"]:
        eslesme["kazanan"] = eslesme["takim1"]
        eslesme["karar"] = "Toplam Skor"
    elif eslesme["skor2"] > eslesme["skor1"]:
        eslesme["kazanan"] = eslesme["takim2"]
        eslesme["karar"] = "Toplam Skor"
    elif eslesme["deplasman1"] > eslesme["deplasman2"]:
        eslesme["kazanan"] = eslesme["takim1"]
        eslesme["karar"] = "Deplasman Golü"
    elif eslesme["deplasman2"] > eslesme["deplasman1"]:
        eslesme["kazanan"] = eslesme["takim2"]
        eslesme["karar"] = "Deplasman Golü"
    else:
        eslesme["kazanan"] = random.choice([eslesme["takim1"], eslesme["takim2"]])
        eslesme["karar"] = "Penaltılar"
    return eslesme["kazanan"]


def ucl_eleme_maclarini_simule_et(haric_takimlar=None):
    kariyer_ucl_verisini_hazirla()
    haric_takimlar = set(haric_takimlar or [])
    tur = kariyer_verisi.get("ucl_tur")
    if tur in ("Lig", "Bitti"):
        return
    eslesmeler = ucl_guncel_tur_eslesmeleri()
    mac_index = kariyer_verisi.get("ucl_mac_index", 0)
    for eslesme_adi in sorted(eslesmeler.keys()):
        eslesme = eslesmeler[eslesme_adi]
        if eslesme.get("kazanan"):
            continue
        if haric_takimlar.intersection({eslesme.get("takim1"), eslesme.get("takim2")}):
            continue
        kullanilacak_index = min(mac_index, len(eslesme.get("maclar", [])) - 1)
        mac = eslesme["maclar"][kullanilacak_index]
        if mac.get("oynandi"):
            continue
        skor_ev, skor_dep = ucl_rastgele_skor_uret(mac["ev"], mac["dep"])
        ucl_eslesme_macini_kaydet(eslesme, kullanilacak_index, skor_ev, skor_dep)
        if eslesme.get("tek_mac") or eslesme.get("oynanan_mac", 0) >= 2:
            kazanan = ucl_eslesme_kazananini_belirle(eslesme)
            kaybeden = eslesme["takim1"] if kazanan == eslesme["takim2"] else eslesme["takim2"]
            if tur == "Final":
                ucl_takim_durumunu_ayarla(kazanan, "Sampiyon")
                ucl_takim_durumunu_ayarla(kaybeden, "Elendi")
                kariyer_verisi["ucl_sampiyonu"] = kazanan
            else:
                sonraki = {"Playoff": "Son16", "Son16": "Ceyrek", "Ceyrek": "Yari", "Yari": "Final"}.get(tur, "Aktif")
                ucl_takim_durumunu_ayarla(kazanan, sonraki)
                ucl_takim_durumunu_ayarla(kaybeden, "Elendi")


def ucl_kazanan_listesi(tur):
    eslesmeler = kariyer_verisi.get("ucl_tum_turlar", {}).get(tur, {})
    sirali_anahtarlar = sorted(eslesmeler.keys(), key=lambda x: int(x.split("_")[-1]))
    return [eslesmeler[anahtar].get("kazanan") for anahtar in sirali_anahtarlar if eslesmeler[anahtar].get("kazanan")]


def ucl_tur_kontrol_ve_eslesme_uret():
    kariyer_ucl_verisini_hazirla()
    tur = kariyer_verisi.get("ucl_tur")

    if tur == "Lig" and kariyer_verisi.get("ucl_hafta", 1) > 8:
        sirali = ucl_sirali_takimlar()
        son16 = [kulup["ad"] for kulup in sirali[:8]]
        playoff = [kulup["ad"] for kulup in sirali[8:24]]
        elenenler = [kulup["ad"] for kulup in sirali[24:]]
        for kulup_adi in son16:
            ucl_takim_durumunu_ayarla(kulup_adi, "Son16")
        for kulup_adi in playoff:
            ucl_takim_durumunu_ayarla(kulup_adi, "Playoff")
        for kulup_adi in elenenler:
            ucl_takim_durumunu_ayarla(kulup_adi, "Elendi")
        kariyer_verisi["ucl_son16_dogrudan"] = son16[:]
        playoff_eslesmeleri = {}
        for i in range(8):
            takim1 = playoff[i]
            takim2 = playoff[-(i + 1)]
            playoff_eslesmeleri[f"eslesme_{i+1}"] = ucl_eslesme_olustur("Playoff", f"Playoff {i+1}", takim1, takim2)
        kariyer_verisi["ucl_tur"] = "Playoff"
        kariyer_verisi["ucl_mac_index"] = 0
        kariyer_verisi["ucl_eslesmeler"] = playoff_eslesmeleri
        kariyer_verisi.setdefault("ucl_tum_turlar", {})["Playoff"] = playoff_eslesmeleri
        ucl_eleme_turu_mac_ayarla()
        return

    if tur in ("Lig", "Bitti"):
        return

    eslesmeler = ucl_guncel_tur_eslesmeleri()
    if not eslesmeler:
        return

    iki_macli_tur = tur != "Final"
    if iki_macli_tur and kariyer_verisi.get("ucl_mac_index", 0) == 0:
        if all(es.get("maclar", [{}])[0].get("oynandi") for es in eslesmeler.values()):
            kariyer_verisi["ucl_mac_index"] = 1
            ucl_eleme_turu_mac_ayarla()
        return

    tur_tamamlandi = all(es.get("kazanan") for es in eslesmeler.values())
    if not tur_tamamlandi:
        ucl_eleme_turu_mac_ayarla()
        return

    if tur == "Final":
        final_eslesme = next(iter(eslesmeler.values()))
        kariyer_verisi["ucl_sampiyonu"] = final_eslesme.get("kazanan")
        kariyer_verisi["ucl_tur"] = "Bitti"
        kariyer_verisi["ucl_mac_index"] = 0
        kariyer_verisi["kendi_ucl_maci_var"] = False
        kariyer_verisi["ucl_aktif_eslesme"] = None
        return

    sonraki_tur = {"Playoff": "Son16", "Son16": "Ceyrek", "Ceyrek": "Yari", "Yari": "Final"}[tur]
    kazananlar = ucl_kazanan_listesi(tur)
    yeni_eslesmeler = {}

    if tur == "Playoff":
        seribaslari = kariyer_verisi.get("ucl_son16_dogrudan", [])
        for i, seribasi in enumerate(seribaslari):
            if i < len(kazananlar):
                yeni_eslesmeler[f"eslesme_{i+1}"] = ucl_eslesme_olustur("Son16", f"Son16 {i+1}", seribasi, kazananlar[i])
                ucl_takim_durumunu_ayarla(seribasi, "Son16")
    elif tur == "Yari":
        if len(kazananlar) >= 2:
            yeni_eslesmeler["eslesme_1"] = ucl_eslesme_olustur("Final", "Final", kazananlar[0], kazananlar[1], tek_mac=True)
    else:
        for i in range(0, len(kazananlar), 2):
            if i + 1 < len(kazananlar):
                yeni_eslesmeler[f"eslesme_{i//2 + 1}"] = ucl_eslesme_olustur(sonraki_tur, f"{sonraki_tur} {i//2 + 1}", kazananlar[i], kazananlar[i + 1], tek_mac=(sonraki_tur == "Final"))

    for kulup_adi in kazananlar:
        if tur != "Yari":
            ucl_takim_durumunu_ayarla(kulup_adi, sonraki_tur)

    kariyer_verisi["ucl_tur"] = sonraki_tur
    kariyer_verisi["ucl_mac_index"] = 0
    kariyer_verisi["ucl_eslesmeler"] = yeni_eslesmeler
    kariyer_verisi.setdefault("ucl_tum_turlar", {})[sonraki_tur] = yeni_eslesmeler
    # [YENI EKLENEN KOD] - Play Off bitisinde Son 16 gecis garantisi ve log
    if tur == "Playoff":
        # Kazananlar listesi ve seribaslari Son16 eslesmelerine yazildi;
        # burada durumlarin guncellendigini ve verinin eksiksiz oldugunu
        # ZORLA dogruluyoruz (veri eksikse bile sozluk anahtari olusur).
        for seribasi in kariyer_verisi.get("ucl_son16_dogrudan", []):
            ucl_takim_durumunu_ayarla(seribasi, "Son16")
        kariyer_verisi["ucl_tum_turlar"]["Son16"] = yeni_eslesmeler
        kariyer_verisi["ucl_eslesmeler"] = yeni_eslesmeler
        print(f"UYARI: Son 16 cizimleri guncellendi. ({len(yeni_eslesmeler)} eslesme olusturuldu)")
    # [EKLEME BURADA BITTI]
    ucl_eleme_turu_mac_ayarla()


def ucl_mac_sonucunu_isle(bizim_skor, rakip_skor, rakip_adi):
    kariyer_ucl_verisini_hazirla()
    kendi_takim = kariyer_verisi.get("kulup", {}).get("ad")
    kendi_kayit = ucl_takim_bul(kendi_takim)
    rakip_kayit = ucl_takim_bul(rakip_adi)
    if not kendi_kayit or not rakip_kayit:
        return

    if kariyer_verisi.get("ucl_tur") == "Lig":
        kendi_kayit["attigi_gol"] += bizim_skor
        kendi_kayit["yedigi_gol"] += rakip_skor
        rakip_kayit["attigi_gol"] += rakip_skor
        rakip_kayit["yedigi_gol"] += bizim_skor
        if bizim_skor > rakip_skor:
            kendi_kayit["p"] += 3
        elif rakip_skor > bizim_skor:
            rakip_kayit["p"] += 3
        else:
            kendi_kayit["p"] += 1
            rakip_kayit["p"] += 1

        if rakip_adi not in kariyer_verisi["oynanan_ucl_rakipleri"]:
            kariyer_verisi["oynanan_ucl_rakipleri"].append(rakip_adi)
        kariyer_verisi["ucl_hafta"] = kariyer_verisi.get("ucl_hafta", 1) + 1
        kariyer_verisi["siradaki_ucl_rakip"] = None
        kariyer_verisi["kendi_ucl_maci_var"] = False
        kariyer_verisi["avrupa_mac_sayisi"] = kariyer_verisi.get("avrupa_mac_sayisi", 0) + 1
        ucl_tur_kontrol_ve_eslesme_uret()
        return

    eslesme_adi = kariyer_verisi.get("ucl_aktif_eslesme")
    eslesmeler = ucl_guncel_tur_eslesmeleri()
    eslesme = eslesmeler.get(eslesme_adi)
    if not eslesme:
        return
    mac_index = min(kariyer_verisi.get("ucl_mac_index", 0), len(eslesme.get("maclar", [])) - 1)
    mac = eslesme["maclar"][mac_index]
    if mac["ev"] == kendi_takim:
        ev_skor, dep_skor = bizim_skor, rakip_skor
    else:
        ev_skor, dep_skor = rakip_skor, bizim_skor
    ucl_eslesme_macini_kaydet(eslesme, mac_index, ev_skor, dep_skor)

    if eslesme.get("tek_mac") or eslesme.get("oynanan_mac", 0) >= 2:
        kazanan = ucl_eslesme_kazananini_belirle(eslesme)
        kaybeden = eslesme["takim1"] if kazanan == eslesme["takim2"] else eslesme["takim2"]
        if kariyer_verisi.get("ucl_tur") == "Final":
            ucl_takim_durumunu_ayarla(kazanan, "Sampiyon")
            ucl_takim_durumunu_ayarla(kaybeden, "Elendi")
            kariyer_verisi["ucl_sampiyonu"] = kazanan
        else:
            sonraki = {"Playoff": "Son16", "Son16": "Ceyrek", "Ceyrek": "Yari", "Yari": "Final"}.get(kariyer_verisi.get("ucl_tur"), "Aktif")
            ucl_takim_durumunu_ayarla(kazanan, sonraki)
            ucl_takim_durumunu_ayarla(kaybeden, "Elendi")

    kariyer_verisi["kendi_ucl_maci_var"] = False
    kariyer_verisi["ucl_aktif_eslesme"] = None
    kariyer_verisi["avrupa_mac_sayisi"] = kariyer_verisi.get("avrupa_mac_sayisi", 0) + 1
    ucl_tur_kontrol_ve_eslesme_uret()


def ucl_agaci_ciz(x, y, genislik, yukseklik):
    # [GUNCELLEME - Son16 gorunmeme hatasi duzeltmesi]
    # Eski tek-sutun dikey cizimde Playoff (8 eslesme x 2 satir) dikey alani
    # tek basina doldurdugu icin fonksiyon erken 'return' ile cikiyor ve
    # Playoff sonrasi olusan Son16/Ceyrek/Yari/Final turlari EKRANA HIC
    # CIZILEMIYORDU. Simdi her tur kendi YATAY sutununda, kompakt satir
    # yuksekligiyle ciziliyor; boylece tum turlar ayni anda gorunur.
    turler = ["Playoff", "Son16", "Ceyrek", "Yari", "Final"]
    tum_turlar = kariyer_verisi.get("ucl_tum_turlar", {})
    mevcut_turler = [tur for tur in turler if tum_turlar.get(tur)]
    if not mevcut_turler:
        return
    sutun_genislik = max(95, genislik // len(mevcut_turler))
    alt_sinir = y + yukseklik - 8
    for sutun_no, tur in enumerate(mevcut_turler):
        eslesmeler = tum_turlar.get(tur, {})
        sutun_x = x + sutun_no * sutun_genislik
        satir_y = y
        screen.blit(font_agac.render(tur.upper(), True, ALTIN), (sutun_x, satir_y))
        satir_y += 20
        for eslesme_adi in sorted(eslesmeler.keys(), key=lambda z: int(z.split("_")[-1])):
            es = eslesmeler[eslesme_adi]
            skor = f"{es.get('skor1', 0)}-{es.get('skor2', 0)}"
            kazanan = es.get("kazanan") or "?"
            satir = f"{es.get('takim1', '')[:10]} {skor} {es.get('takim2', '')[:10]}"
            screen.blit(font_agac.render(satir, True, BEYAZ), (sutun_x, satir_y))
            satir_y += 16
            screen.blit(font_agac.render(f"->{kazanan[:12]}", True, YESIL if es.get("kazanan") else BEYAZ), (sutun_x + 6, satir_y))
            satir_y += 20
            if satir_y >= alt_sinir:
                break


def ucl_sampiyonunu_bul():
    if kariyer_verisi.get("ucl_sampiyonu"):
        return kariyer_verisi.get("ucl_sampiyonu")
    for kulup in AVRUPA_KULUPLER:
        if kulup.get("elenme_durumu") == "Sampiyon":
            return kulup.get("ad")
    final = kariyer_verisi.get("ucl_tum_turlar", {}).get("Final", {})
    if final:
        ilk = next(iter(final.values()))
        return ilk.get("kazanan")
    return None


def ucl_yeni_sezon_kuluplerini_olustur(lig_takimlari, katilanlar):
    global AVRUPA_KULUPLER
    lig_takimlari = set(lig_takimlari)
    yeni_adlar = [ad for ad in TEMEL_AVRUPA_KULUP_ADLARI if ad not in lig_takimlari]
    for takim in katilanlar:
        if takim and takim not in yeni_adlar:
            yeni_adlar.append(takim)
    AVRUPA_KULUPLER = [avrupa_kulubu_olustur(ad) for ad in yeni_adlar]


def ucl_yeni_sezonu_sifirla():
    kariyer_verisi["avrupa_mac_sayisi"] = 0
    kariyer_verisi["genel_mac_index"] = 0
    kariyer_verisi["ucl_hafta"] = 1
    kariyer_verisi["ucl_tur"] = "Lig"
    kariyer_verisi["ucl_eslesmeler"] = {}
    kariyer_verisi["ucl_tum_turlar"] = {}
    kariyer_verisi["ucl_son16_dogrudan"] = []
    kariyer_verisi["ucl_mac_index"] = 0
    kariyer_verisi["kendi_ucl_maci_var"] = False
    kariyer_verisi["oynanan_ucl_rakipleri"] = []
    kariyer_verisi["siradaki_ucl_rakip"] = None
    kariyer_verisi["ucl_aktif_eslesme"] = None
    kariyer_verisi["ucl_sampiyonu"] = None


kariyer_ucl_verisini_hazirla()


def ana_yonetim_paneli():
    """[YENI] Sekmeli Ana Yonetim Paneli.

    Taslak gorsellere (Ek 1/2/3) gore bastan tasarlanmistir.
    - Ustte 4 sekmeli gezinti cubugu: Ana Menu / Transfer / Kadro / Sosyal Medya
    - Aktif sekme mor, pasif sekmeler soft mavi.
    - Tum alt ekranlar (kadro, transfer, ekip, mesajlar, mac) mevcut
      state-machine uzerinden aynen calismaya devam eder.
    """
    global durum

    takim_adi = kariyer_verisi["kulup"]["ad"]

    # --- SIRADAKİ RAKİP MANTIĞI (UCL + LİG) — ORİJİNAL KODLA BİREBİR AYNI ---
    kariyer_ucl_verisini_hazirla()
    if kariyer_verisi.get("kulup") and takim_adi in [k.get("ad") for k in AVRUPA_KULUPLER]:
        kariyer_verisi["avrupa_lig_katilim"] = kariyer_verisi.get("avrupa_lig_katilim", False) or True
        ucl_takimi_ekle_gerekiyorsa(takim_adi)

    ucl_takviminde = ucl_takvim_sirasi_mi()
    ucl_mac_bilgisi = None
    if ucl_takviminde:
        if kariyer_verisi.get("ucl_tur") == "Lig" and kariyer_verisi.get("ucl_hafta", 1) <= 8:
            rakip = ucl_lig_asamasi_mac_ayarla()
            if rakip:
                ucl_mac_bilgisi = {"rakip": rakip, "tur": "Lig"}
        else:
            ucl_mac_bilgisi = ucl_eleme_turu_mac_ayarla()

    is_avrupa_sirasi = bool(ucl_mac_bilgisi and kariyer_verisi.get("kendi_ucl_maci_var", False))
    rakip_listesi = [k["ad"] for k in KULUPLER if k["ad"] != takim_adi]
    gelecek_rakip = rakip_listesi[kariyer_verisi.get("oynanan_mac", 0) % len(rakip_listesi)]

    # Fikstur kutusunda gosterilecek dinamik metinler
    lig_mac_metni = f"Sıradaki Rakip: {gelecek_rakip} (Lig Maçı)"
    ucl_mac_metni = None
    if kariyer_verisi.get("avrupa_lig_katilim", False) and kariyer_verisi.get("ucl_tur") != "Bitti":
        if ucl_mac_bilgisi:
            ucl_mac_metni = f"Sıradaki Rakip: {ucl_mac_bilgisi['rakip']} (UCL)"
        else:
            ucl_mac_metni = f"UCL {kariyer_verisi.get('ucl_tur', '')}: diğer eşleşmeler oynanıyor"

    # Maca Cik butonu icin kulvar bilgisi (orijinal mantik)
    if is_avrupa_sirasi:
        gelecek_rakip = ucl_mac_bilgisi["rakip"]

    # --- SEKME / POPUP DURUM YÖNETİMİ ---
    aktif_sekme = "Ana Menü"
    aktif_popup = None          # None | "tablo" | "fikstur"
    popup_tablo_modu = "LIG"    # "LIG" | "UCL" | "SONUC"
    popup_kaydirma = 0
    fikstur_kaydirma = 0
    tekerlek_delta = 0
    kayit_durum_mesaji = ""
    kayit_durum_renk = YESIL
    menu_acik = False

    while True:
        _focus_begin_frame(("yonetim", aktif_sekme, aktif_popup, popup_tablo_modu if aktif_popup == "tablo" else None, menu_acik))
        screen.fill(ARKA_PLAN)

        # ============================================================
        # A) ÜST GEZİNTİ ÇUBUĞU
        # ============================================================
        tiklanan_sekme = ust_sekme_cubugu_ciz(aktif_sekme)
        if tiklanan_sekme:
            aktif_sekme = tiklanan_sekme
            aktif_popup = None
            menu_acik = False
            pygame.time.delay(130)

        # ============================================================
        # B) SEKME İÇERİKLERİ
        # ============================================================
        if aktif_sekme == "Ana Menü":
            # --------------------------------------------------------
            # 1) LİG TABLOSU BÖLÜMÜ (Ek 3: sol ust kutu + nokta butonu)
            # --------------------------------------------------------
            tablo_rect = pygame.Rect(40, 88, 640, 470)
            panel_ciz(tablo_rect.x, tablo_rect.y, tablo_rect.width, tablo_rect.height,
                      dolgu=PANEL_KOYU, cerceve=ALTIN, yaricap=16)
            screen.blit(font_buton.render("Lig Tablosu", True, ALTIN), (tablo_rect.x + 22, tablo_rect.y + 14))

            # --- Nokta (•) butonu: tablo cercevesinin sag ust kosesi ---
            nokta_merkez = (tablo_rect.right - 34, tablo_rect.y + 34)
            fare = pygame.mouse.get_pos()
            nokta_uzerinde = (fare[0] - nokta_merkez[0]) ** 2 + (fare[1] - nokta_merkez[1]) ** 2 < 22 * 22
            pygame.draw.circle(screen, MAVI if nokta_uzerinde else ALTIN, nokta_merkez, 20)
            pygame.draw.circle(screen, SIYAH, nokta_merkez, 20, 2)
            nokta_yazi = font_buton.render("•", True, SIYAH)
            screen.blit(nokta_yazi, nokta_yazi.get_rect(center=(nokta_merkez[0], nokta_merkez[1] - 3)))
            if _focus_polled_click(pygame.Rect(nokta_merkez[0] - 20, nokta_merkez[1] - 20, 40, 40),
                                  nokta_uzerinde and pygame.mouse.get_pressed()[0]):
                # Lig bittiyse sonuclar ekrani, bitmediyse scroll'lu detayli tablo
                if kariyer_verisi.get("oynanan_mac", 0) >= 30:
                    popup_tablo_modu = "SONUC"
                else:
                    popup_tablo_modu = "LIG"
                popup_kaydirma = 0
                aktif_popup = "tablo"
                pygame.time.delay(160)

            # Tablo satirlari (veri akisi orijinalle ayni: KULUPLER + puan)
            sirali_lig = sorted(KULUPLER, key=lambda x: x["p"], reverse=True)
            max_satir = (tablo_rect.height - 76) // 27
            for i, t in enumerate(sirali_lig[:max_satir]):
                renk = YESIL if t["ad"] == takim_adi else BEYAZ
                satir = f"{i+1:>2}. {t['ad'][:18]:18} | {t['p']:>2} P"
                screen.blit(font_liste.render(satir, True, renk),
                            (tablo_rect.x + 24, tablo_rect.y + 58 + i * 27))
            if len(sirali_lig) > max_satir:
                ipucu = font_oyuncu.render("Tümü için köşedeki • butonuna dokun", True, (150, 170, 195))
                screen.blit(ipucu, (tablo_rect.x + 24, tablo_rect.bottom - 30))

            # --------------------------------------------------------
            # 2) FİKSTÜR BİLGİ KUTUSU (Ek 3: sag ust kutu, tiklanabilir)
            # --------------------------------------------------------
            fikstur_rect = pygame.Rect(700, 88, 540, 220)
            panel_ciz(fikstur_rect.x, fikstur_rect.y, fikstur_rect.width, fikstur_rect.height,
                      dolgu=(30, 45, 90) if is_avrupa_sirasi else PANEL_KOYU, cerceve=ALTIN, yaricap=16)
            screen.blit(font_buton.render("Fikstür", True, ALTIN), (fikstur_rect.x + 22, fikstur_rect.y + 14))
            screen.blit(font_log.render(lig_mac_metni, True, BEYAZ), (fikstur_rect.x + 22, fikstur_rect.y + 66))
            if ucl_mac_metni:
                screen.blit(font_log.render(ucl_mac_metni, True, ALTIN), (fikstur_rect.x + 22, fikstur_rect.y + 102))
            gor_buton_renk = MAVI
            gor_rect = pygame.Rect(fikstur_rect.x + 22, fikstur_rect.bottom - 62, fikstur_rect.width - 44, 46)
            fare2 = pygame.mouse.get_pos()
            if gor_rect.collidepoint(fare2):
                gor_buton_renk = SEKME_PASIF_ALT
            pygame.draw.rect(screen, gor_buton_renk, gor_rect, border_radius=10)
            pygame.draw.rect(screen, BEYAZ, gor_rect, 2, border_radius=10)
            metni_ortalaya_ciz(screen, "TÜM FİKSTÜRLERİ GÖR", font_log, SIYAH, gor_rect)
            if _focus_polled_click(gor_rect, (gor_rect.collidepoint(fare2) or fikstur_rect.collidepoint(fare2))
                                  and pygame.mouse.get_pressed()[0]):
                fikstur_kaydirma = 0
                aktif_popup = "fikstur"
                pygame.time.delay(160)

            # --------------------------------------------------------
            # 3) MAÇA ÇIK BUTONU (Ek 3: fikstur kutusunun altinda, genis)
            # --------------------------------------------------------
            if buyuk_buton_ciz("Maça Çık", 700, 326, 540, 232, YESIL, yazi_renk=SIYAH, font=font_baslik):
                # --- ORİJİNAL AVRUPA SİMÜLASYONU BLOĞU (dokunulmadi) ---
                if ucl_takviminde and kariyer_verisi.get("avrupa_lig_katilim", False) and kariyer_verisi.get("ucl_tur") != "Bitti":
                    if kariyer_verisi.get("ucl_tur") == "Lig":
                        haric = {takim_adi}
                        if is_avrupa_sirasi and ucl_mac_bilgisi:
                            haric.add(ucl_mac_bilgisi["rakip"])
                        ucl_lig_diger_maclarini_simule_et(haric)
                    else:
                        haric = {takim_adi} if is_avrupa_sirasi else set()
                        ucl_eleme_maclarini_simule_et(haric)
                        ucl_tur_kontrol_ve_eslesme_uret()
                return "mac_ekrani"

        elif aktif_sekme == "Transfer":
            # --------------------------------------------------------
            # MALİ DURUM KARTI (Ek 1: sol panel, yuvarlatilmis + daire)
            # --------------------------------------------------------
            mali_rect = pygame.Rect(60, 110, 700, 448)
            panel_ciz(mali_rect.x, mali_rect.y, mali_rect.width, mali_rect.height,
                      dolgu=PANEL_ACIK, cerceve=SIYAH, yaricap=30)
            baslik = font_baslik.render("Mali Durum", True, SIYAH)
            screen.blit(baslik, (mali_rect.x + 30, mali_rect.y + 22))

            butce = kariyer_verisi["kulup"].get("butce", 0)
            gelir = kariyer_verisi.get("sezon_gelir", 0)
            gider = kariyer_verisi.get("sezon_gider", 0)

            # Merkez daire
            daire_merkez = (mali_rect.centerx, mali_rect.centery + 26)
            pygame.draw.circle(screen, BEYAZ, daire_merkez, 118)
            pygame.draw.circle(screen, SIYAH, daire_merkez, 118, 10)
            butce_isaret = f"+{butce}M" if butce >= 0 else f"{butce}M"
            mb_yazi = font_log.render("Mevcut Bütçe", True, (70, 80, 95))
            screen.blit(mb_yazi, mb_yazi.get_rect(center=(daire_merkez[0], daire_merkez[1] - 34)))
            tutar_yazi = font_baslik.render(butce_isaret, True, SIYAH)
            screen.blit(tutar_yazi, tutar_yazi.get_rect(center=(daire_merkez[0], daire_merkez[1] + 14)))

            # Sol: Gelir (yesil)
            gelir_baslik = font_buton.render("Gelir", True, YESIL)
            screen.blit(gelir_baslik, gelir_baslik.get_rect(center=(mali_rect.x + 130, daire_merkez[1] - 70)))
            gelir_deger = font_baslik.render(f"{gelir}M", True, YESIL)
            screen.blit(gelir_deger, gelir_deger.get_rect(center=(mali_rect.x + 130, daire_merkez[1] - 14)))

            # Sag: Gider (kirmizi)
            gider_baslik = font_buton.render("Gider", True, KIRMIZI)
            screen.blit(gider_baslik, gider_baslik.get_rect(center=(mali_rect.right - 130, daire_merkez[1] + 60)))
            gider_deger = font_baslik.render(f"{gider}M", True, KIRMIZI)
            screen.blit(gider_deger, gider_deger.get_rect(center=(mali_rect.right - 130, daire_merkez[1] + 116)))

            # --------------------------------------------------------
            # SAG PANEL: EKİP EKRANI / TRANSFER EKRANI (Ek 1)
            # --------------------------------------------------------
            if buyuk_buton_ciz("Ekip Ekranı", 800, 110, 420, 200, (16, 24, 110), yazi_renk=BEYAZ, font=font_baslik):
                return "ekip_ekrani"
            if buyuk_buton_ciz("Transfer Ekranı", 800, 358, 420, 200, (235, 225, 20), yazi_renk=SIYAH, font=font_baslik):
                return "transfer_ekrani"

        elif aktif_sekme == "Kadro":
            # --------------------------------------------------------
            # SOL PANEL: SAHA GÖRSELLEŞTİRMESİ (Ek 2)
            # --------------------------------------------------------
            saha_rect = pygame.Rect(60, 100, 700, 470)
            if mini_saha_ciz(saha_rect, takim_adi):
                return "kadro_ekrani"
            ipucu = font_oyuncu.render("Sahaya veya oyuncuya dokun: detaylı Kadro Ekranı açılır", True, (170, 190, 215))
            screen.blit(ipucu, (saha_rect.x + 10, saha_rect.bottom + 12))
            # [YENI] Mevki renk lejandi (ana panel > Kadro sekmesi)
            mevki_lejandi_ciz(screen, saha_rect.x, saha_rect.bottom + 40)

            # --------------------------------------------------------
            # SAG PANEL: LİSTE / MESAJ (Ek 2)
            # --------------------------------------------------------
            if buyuk_buton_ciz("Liste", 800, 110, 420, 210, PANEL_ACIK, yazi_renk=SIYAH, font=font_baslik, cerceve_renk=(20, 90, 40)):
                return "kadro_ekrani"
            if buyuk_buton_ciz("Mesaj", 800, 368, 420, 210, PANEL_ACIK, yazi_renk=SIYAH, font=font_baslik, cerceve_renk=(20, 90, 40)):
                return "mesajlar"

        elif aktif_sekme == "Sosyal Medya":
            # --------------------------------------------------------
            # PEK YAKINDA (tam ortalanmis, kirmizi)
            # --------------------------------------------------------
            pek = font_skor.render("Pek Yakında", True, KIRMIZI)
            screen.blit(pek, pek.get_rect(center=(WIDTH // 2, 360)))

        # ============================================================
        # ALT BAR: KAYDET & ÇIK + SİSTEM MENÜSÜ (Mesajlar / İstifa)
        # ============================================================
        if kayit_durum_mesaji:
            ekran_mesaji = font_oyuncu.render(kayit_durum_mesaji, True, kayit_durum_renk)
            screen.blit(ekran_mesaji, (40, 676))

        if buyuk_buton_ciz("KAYDET & ÇIK", 990, 664, 190, 50, KIRMIZI, font=font_log):
            basarili, mesaj = oyunu_kaydet()
            kayit_durum_mesaji = mesaj
            kayit_durum_renk = YESIL if basarili else KIRMIZI
            if basarili:
                pygame.time.delay(250)
                pygame.quit()
                sys.exit()

        if buyuk_buton_ciz("☰", 1194, 664, 56, 50, BUTON_RENGI, font=font_buton):
            menu_acik = not menu_acik
            pygame.time.delay(150)
        if menu_acik:
            pygame.draw.rect(screen, BUTON_RENGI, (1005, 532, 245, 118), border_radius=10)
            pygame.draw.rect(screen, ALTIN, (1005, 532, 245, 118), 2, border_radius=10)
            if buton_ciz("MESAJLAR", 1015, 540, 225, 48, MAVI):
                return "mesajlar"
            if buton_ciz("İSTİFA", 1015, 594, 225, 48, KIRMIZI):
                return "istifa"

        # ============================================================
        # POPUP 1: DETAYLI LİG / UCL TABLOSU (scroll'lu) veya SONUÇLAR
        # ============================================================
        if aktif_popup == "tablo":
            _focus_frame_items.clear()  # The modal is the keyboard focus scope.
            karartma = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            karartma.fill((0, 0, 0, 170))
            screen.blit(karartma, (0, 0))
            pop = pygame.Rect(140, 80, 1000, 560)
            panel_ciz(pop.x, pop.y, pop.width, pop.height, dolgu=(16, 26, 42), cerceve=ALTIN, yaricap=18)

            if popup_tablo_modu == "SONUC":
                # Lig bitti: mevcut sirayla karsilasma sonuclari
                screen.blit(font_baslik.render("SEZON SONUÇLARI", True, ALTIN), (pop.x + 30, pop.y + 18))
                sonuclar = [m for m in kariyer_verisi.get("mesajlar", [])
                            if isinstance(m, dict) and m.get("baslik") == "Maç Sonucu"]
                if not sonuclar:
                    screen.blit(font_liste.render("Kayıtlı maç sonucu bulunamadı.", True, BEYAZ), (pop.x + 30, pop.y + 90))
                gorunur = 14
                popup_kaydirma = max(0, min(popup_kaydirma, max(0, len(sonuclar) - gorunur)))
                popup_kaydirma = max(0, popup_kaydirma - tekerlek_delta)
                for i in range(gorunur):
                    gi = popup_kaydirma + i
                    if gi >= len(sonuclar):
                        break
                    satir = metni_kisalt(sonuclar[gi].get("ozet", ""), 58)
                    screen.blit(font_log.render(satir, True, BEYAZ), (pop.x + 30, pop.y + 84 + i * 32))
                if popup_kaydirma > 0 and buton_ciz("^", pop.right - 70, pop.y + 16, 44, 40, MAVI):
                    popup_kaydirma -= 1; pygame.time.delay(90)
                if popup_kaydirma + gorunur < len(sonuclar) and buton_ciz("v", pop.right - 70, pop.bottom - 96, 44, 40, MAVI):
                    popup_kaydirma += 1; pygame.time.delay(90)
            else:
                # Lig / UCL secim sekmeleri (ayni scroll yapisi)
                if buton_ciz("LİG", pop.x + 24, pop.y + 16, 140, 44,
                             SEKME_AKTIF if popup_tablo_modu == "LIG" else SEKME_PASIF):
                    popup_tablo_modu = "LIG"; popup_kaydirma = 0; pygame.time.delay(110)
                if kariyer_verisi.get("avrupa_lig_katilim", False) and kariyer_verisi.get("ucl_tur") != "Bitti":
                    if buton_ciz("UCL", pop.x + 176, pop.y + 16, 140, 44,
                                 SEKME_AKTIF if popup_tablo_modu == "UCL" else SEKME_PASIF):
                        popup_tablo_modu = "UCL"; popup_kaydirma = 0; pygame.time.delay(110)

                if popup_tablo_modu == "LIG":
                    kaynak = sorted(KULUPLER, key=lambda x: x["p"], reverse=True)
                    baslik = "LİG TABLOSU (Detaylı)"
                else:
                    if kariyer_verisi.get("ucl_tur") == "Lig":
                        kaynak = ucl_sirali_takimlar()
                        baslik = "ŞAMPİYONLAR LİGİ - LİG AŞAMASI"
                    else:
                        kaynak = ucl_sirali_takimlar()
                        baslik = f"ŞAMPİYONLAR LİGİ ({kariyer_verisi.get('ucl_tur', '')})"
                screen.blit(font_buton.render(baslik, True, ALTIN), (pop.x + 340, pop.y + 22))

                gorunur = 15
                popup_kaydirma = max(0, min(popup_kaydirma, max(0, len(kaynak) - gorunur)))
                popup_kaydirma = max(0, popup_kaydirma - tekerlek_delta)
                for i in range(gorunur):
                    gi = popup_kaydirma + i
                    if gi >= len(kaynak):
                        break
                    t = kaynak[gi]
                    renk = YESIL if t["ad"] == takim_adi else BEYAZ
                    averaj = t.get("attigi_gol", 0) - t.get("yedigi_gol", 0)
                    satir = f"{gi+1:>2}. {t['ad'][:22]:22} | {t['p']:>2} P | AV {averaj:+d}"
                    screen.blit(font_liste.render(satir, True, renk), (pop.x + 30, pop.y + 84 + i * 30))
                if popup_kaydirma > 0 and buton_ciz("^", pop.right - 70, pop.y + 16, 44, 40, MAVI):
                    popup_kaydirma -= 1; pygame.time.delay(90)
                if popup_kaydirma + gorunur < len(kaynak) and buton_ciz("v", pop.right - 70, pop.bottom - 96, 44, 40, MAVI):
                    popup_kaydirma += 1; pygame.time.delay(90)

            if buyuk_buton_ciz("KAPAT", pop.centerx - 110, pop.bottom - 58, 220, 44, KIRMIZI, font=font_log):
                aktif_popup = None
                pygame.time.delay(130)

        # ============================================================
        # POPUP 2: TÜM FİKSTÜRLER (sezon sonuna kadar kalan maçlar)
        # ============================================================
        elif aktif_popup == "fikstur":
            _focus_frame_items.clear()  # The modal is the keyboard focus scope.
            karartma = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            karartma.fill((0, 0, 0, 170))
            screen.blit(karartma, (0, 0))
            pop = pygame.Rect(140, 80, 1000, 560)
            panel_ciz(pop.x, pop.y, pop.width, pop.height, dolgu=(16, 26, 42), cerceve=ALTIN, yaricap=18)
            screen.blit(font_baslik.render("KALAN FİKSTÜR", True, ALTIN), (pop.x + 30, pop.y + 18))

            fikstur = []
            toplam_lig_maci = 30
            for mac_no in range(kariyer_verisi.get("oynanan_mac", 0), toplam_lig_maci):
                rakip_ad = rakip_listesi[mac_no % len(rakip_listesi)] if rakip_listesi else "?"
                fikstur.append(f"Hafta {mac_no + 1:>2}  |  {takim_adi}  vs  {rakip_ad}  (Lig)")
            if kariyer_verisi.get("avrupa_lig_katilim", False) and kariyer_verisi.get("ucl_tur") != "Bitti":
                fikstur.append("─" * 46)
                if kariyer_verisi.get("ucl_tur") == "Lig":
                    kalan_ucl = max(0, 8 - kariyer_verisi.get("ucl_hafta", 1) + 1)
                    fikstur.append(f"UCL Lig Aşaması: {kalan_ucl} maç kaldı (hafta {kariyer_verisi.get('ucl_hafta', 1)}/8)")
                else:
                    fikstur.append(f"UCL {kariyer_verisi.get('ucl_tur', '')} turu devam ediyor")
                if ucl_mac_bilgisi:
                    fikstur.append(f"Sıradaki UCL Rakibi: {ucl_mac_bilgisi['rakip']}")

            gorunur = 14
            fikstur_kaydirma = max(0, min(fikstur_kaydirma, max(0, len(fikstur) - gorunur)))
            fikstur_kaydirma = max(0, fikstur_kaydirma - tekerlek_delta)
            for i in range(gorunur):
                gi = fikstur_kaydirma + i
                if gi >= len(fikstur):
                    break
                screen.blit(font_log.render(metni_kisalt(fikstur[gi], 62), True, BEYAZ),
                            (pop.x + 30, pop.y + 84 + i * 32))
            if fikstur_kaydirma > 0 and buton_ciz("^", pop.right - 70, pop.y + 16, 44, 40, MAVI):
                fikstur_kaydirma -= 1; pygame.time.delay(90)
            if fikstur_kaydirma + gorunur < len(fikstur) and buton_ciz("v", pop.right - 70, pop.bottom - 96, 44, 40, MAVI):
                fikstur_kaydirma += 1; pygame.time.delay(90)

            if buyuk_buton_ciz("KAPAT", pop.centerx - 110, pop.bottom - 58, 220, 44, KIRMIZI, font=font_log):
                aktif_popup = None
                pygame.time.delay(130)

        # ============================================================
        # OLAY DÖNGÜSÜ
        # ============================================================
        tekerlek_delta = 0
        _focus_publish(("yonetim", aktif_sekme, aktif_popup, popup_tablo_modu if aktif_popup == "tablo" else None, menu_acik))
        for e in _focus_events():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if e.type == pygame.MOUSEWHEEL:
                tekerlek_delta = e.y  # yukari=+1 (listeyi yukari kaydir)

        draw_focus_indicator(screen)
        pygame.display.flip()


def mesajlar_ekrani():
    """Oyun içi mesajların listelendiği sohbet ekranı."""
    global durum
    if not isinstance(kariyer_verisi.get("mesajlar"), list):
        kariyer_verisi["mesajlar"] = []
    mesaj_listesi = kariyer_verisi["mesajlar"]
    mesaj_index = 0
    gorunur_sayi = 5
    kutu_h = 100
    bosluk = 12

    while True:
        _focus_begin_frame(("mesajlar",))
        screen.fill(ARKA_PLAN)

        screen.blit(font_baslik.render("MESAJLAR", True, ALTIN), (50, 25))
        toplam_mesaj = len(mesaj_listesi)
        screen.blit(font_liste.render(f"Toplam: {toplam_mesaj} mesaj", True, BEYAZ), (950, 35))

        if toplam_mesaj == 0:
            screen.blit(font_liste.render("Henüz mesajınız yok. Maç, transfer ve sakatlık haberleri burada görünür.", True, BEYAZ), (50, 150))

        for i in range(gorunur_sayi):
            gercek_i = mesaj_index + i
            if gercek_i >= toplam_mesaj:
                break
            mesaj = mesaj_listesi[gercek_i]
            y = 110 + i * (kutu_h + bosluk)
            pygame.draw.rect(screen, BUTON_RENGI, (50, y, 1180, kutu_h), border_radius=12)
            pygame.draw.rect(screen, ALTIN, (50, y, 1180, kutu_h), 2, border_radius=12)
            baslik_metni = metni_kisalt(mesaj.get("baslik", "Mesaj"), 60)
            ozet_metni = metni_kisalt(mesaj.get("ozet", ""), 90)
            tarih_metni = f"Sezon {mesaj.get('sezon', 2027)} | Gün {mesaj.get('gun', 1)}"
            screen.blit(font_liste.render(baslik_metni, True, ALTIN), (70, y + 12))
            screen.blit(font_oyuncu.render(tarih_metni, True, MAVI), (1000, y + 16))
            screen.blit(font_log.render(ozet_metni, True, BEYAZ), (70, y + 50))

        if mesaj_index > 0:
            if buton_ciz("^", 1170, 60, 60, 40, MAVI):
                mesaj_index -= 1
                pygame.time.delay(100)
        if mesaj_index + gorunur_sayi < toplam_mesaj:
            if buton_ciz("v", 1170, 655, 60, 40, MAVI):
                mesaj_index += 1
                pygame.time.delay(100)

        if buton_ciz("GERİ DÖN", 50, 655, 220, 50, KIRMIZI):
            return "ana_menu"

        _focus_publish(("mesajlar",))
        for e in _focus_events():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        draw_focus_indicator(screen)
        pygame.display.flip()


def istifa_onay_ekrani():
    """İstifa öncesi onay diyaloğu."""
    global durum

    while True:
        _focus_begin_frame(("istifa",))
        screen.fill(ARKA_PLAN)

        panel_ciz(340, 200, 600, 300)
        txt = font_baslik.render("İSTİFA", True, KIRMIZI)
        screen.blit(txt, txt.get_rect(center=(WIDTH // 2, 250)))
        soru = font_buton.render("İstifa etmek istediğinize emin misiniz?", True, BEYAZ)
        screen.blit(soru, soru.get_rect(center=(WIDTH // 2, 320)))
        uyari = font_log.render("Kariyeriniz sona erecek ve ana menüye dönülecek.", True, ALTIN)
        screen.blit(uyari, uyari.get_rect(center=(WIDTH // 2, 365)))

        if buton_ciz("EVET", 390, 410, 220, 70, KIRMIZI):
            pygame.time.delay(150)
            kariyer_verisi.clear()
            kariyer_verisi.update(json.loads(json.dumps(KARIYER_VERISI_VARSAYILAN, ensure_ascii=False)))
            return "giris"

        if buton_ciz("HAYIR", 670, 410, 220, 70, YESIL):
            pygame.time.delay(150)
            return "ana_menu"

        _focus_publish(("istifa",))
        for e in _focus_events():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        draw_focus_indicator(screen)
        pygame.display.flip()


def basin_toplantisi_ekrani():
    global durum
    
    # --- KRİTİK HATA ÖNLEYİCİ --- (Hiçbir şeyi silmeden, hata giderilmiş hali koruyoruz)
    if "performans" not in kariyer_verisi:
        kariyer_verisi["performans"] = 50  # Başlangıç değeri
    
    # Maç sonu için rastgele bir soru seçiyoruz (Koru)
    soru_obj = random.choice(BASIN_SORULARI)
    soru_metni = soru_obj["soru"]
    secenek_a = soru_obj["secenekler"][0]
    secenek_b = soru_obj["secenekler"][1]
    
    cevap_verildi = False
    etki_mesaji = ""

    # Soru kutusu için koordinatlar
    mohaber_kafa_x = 640  # Ortadaki adamın tahmini kafa x'i
    mohaber_kafa_y = 350  # Ortadaki adamın tahmini kafa y'i
    soru_kutu_w = 400
    soru_kutu_h = 100
    soru_kutu_x = mohaber_kafa_x - soru_kutu_w // 2
    soru_kutu_y = mohaber_kafa_y - soru_kutu_h - 20 # Kafanın üzerinde

    # Cevap butonları için koordinatlar
    mikrofon_x = 640 # Mikrofonun tahmini x'i
    mikrofon_y = 600 # Mikrofonun tahmini y'i (masanın üzerinde)
    buton_w = 400
    buton_h = 80
    buton_a_x = mikrofon_x - buton_w - 50 # Mikrofonun solu
    buton_a_y = mikrofon_y - buton_h // 2
    buton_b_x = mikrofon_x + 50 # Mikrofonun sağı
    buton_b_y = mikrofon_y - buton_h // 2

    # Sonuç mesajı koordinatları
    sonuc_mesaj_x = WIDTH // 2
    sonuc_mesaj_y = 500

    # Devam et butonu koordinatları
    devam_buton_x = WIDTH // 2 - 150
    devam_buton_y = 650

    while True:
        _focus_begin_frame(("basin_eski", cevap_verildi))
        # screen.fill(ARKA_PLAN)  # Arka planı silme, fotoğrafı üzerine çiz

        # Arka Plan Fotoğrafını Çiz
        if BASIN_FOTO:
            # Fotoğrafın boyutu hiç bir şekilde değişmeyecek, olduğu gibi blit edilecek.
            # Konum: (0, 0) koordinatlarına blit et, ekranın arkasında bir kompozisyon gibi kalsın.
            screen.blit(BASIN_FOTO, (0, 0))
        else:
            screen.fill(ARKA_PLAN)
        
        # --- BAŞLIK (Fotoğrafın üzerine, üst tarafa) ---
        pygame.draw.rect(screen, BUTON_RENGI, (0, 0, WIDTH, 80))
        txt_baslik = font_baslik.render("MAÇ SONU BASIN TOPLANTISI", True, ALTIN)
        screen.blit(txt_baslik, (WIDTH//2 - txt_baslik.get_width()//2, 20))

        # --- SORU KUTUSU (Muhabirin kafasının üzerinde, okunabilir beyaz zemin üzerine) ---
        # Yarı-şeffaf arka plan
        soru_bg_surface = pygame.Surface((soru_kutu_w, soru_kutu_h), pygame.SRCALPHA)
        soru_bg_surface.fill((255, 255, 255, 180)) # Beyaz, alpha: 180
        screen.blit(soru_bg_surface, (soru_kutu_x, soru_kutu_y))
        pygame.draw.rect(screen, ALTIN, (soru_kutu_x, soru_kutu_y, soru_kutu_w, soru_kutu_h), 3, border_radius=10) # Çerçeve

        # Soru Metni (Kutuya sığdır)
        # Metni kutuya sığdırmak için basit bir satır bölme yapabilirim
        soru_satirlar = []
        tmp_satir = ""
        for kelime in soru_metni.split():
            # Eğer satır uzunluğu kutu genişliğini geçiyorsa yeni satıra geç
            if font_buton.size(tmp_satir + " " + kelime)[0] < soru_kutu_w - 20:
                tmp_satir += kelime + " "
            else:
                # Satırı temizle ve kelimeyi yeni satıra al
                soru_satirlar.append(tmp_satir.strip())
                tmp_satir = kelime + " "
        # Son satırı ekle
        if tmp_satir:
            soru_satirlar.append(tmp_satir.strip())

        # Satırları kutuya çiz
        for i, satir in enumerate(soru_satirlar):
            soru_render = font_buton.render(satir, True, SIYAH) # Metin rengi siyah
            screen.blit(soru_render, (soru_kutu_x + 10, soru_kutu_y + 10 + i * 35))

        # --- CEVAP ŞIKLARI (Mikrofonun solunda ve sağında, masadaki mikrofonla uyumlu butonlarda) ---
        if not cevap_verildi:
            # A ŞIKKI (Mikrofonun solu)
            # Buton çerçevesini ve metni çiz
            if buton_ciz(f"A) {secenek_a['metin']}", buton_a_x, buton_a_y, buton_w, buton_h, BUTON_RENGI):
                kariyer_verisi["performans"] += secenek_a["etki"]
                etki_mesaji = f"Takım Formu: {'+' if secenek_a['etki'] > 0 else ''}{secenek_a['etki']}% Değişti!"
                cevap_verildi = True
            
            # B ŞIKKI (Mikrofonun sağı)
            if buton_ciz(f"B) {secenek_b['metin']}", buton_b_x, buton_b_y, buton_w, buton_h, BUTON_RENGI):
                kariyer_verisi["performans"] += secenek_b["etki"]
                etki_mesaji = f"Takım Formu: {'+' if secenek_b['etki'] > 0 else ''}{secenek_b['etki']}% Değişti!"
                cevap_verildi = True
        else:
            # CEVAP VERİLDİKTEN SONRAKİ EKRAN
            # Sonuç mesajını masanın üzerinde, uygun, okunabilir bir yere yerleştiriyoruz (Örn: masanın ortası)
            renk = YESIL if "+" in etki_mesaji else KIRMIZI
            sonuc_txt = font_baslik.render(etki_mesaji, True, renk)
            screen.blit(sonuc_txt, (sonuc_mesaj_x - sonuc_txt.get_width()//2, sonuc_mesaj_y))
            
            # Performans sınırlarını koru (0-100 arası) (Koru)
            kariyer_verisi["performans"] = max(0, min(100, kariyer_verisi["performans"]))
            
            # "DEVAM ET" butonu düzenlenerek arka plana uygun bir yere yerleştirilir
            if buton_ciz("DEVAM ET", devam_buton_x, devam_buton_y, 300, 80, MAVI):
                return "ana_menu"

        # --- HADİSƏLƏR --- (Koru)
        _focus_publish(("basin_eski", cevap_verildi))
        for event in _focus_events():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
        
        draw_focus_indicator(screen)
        pygame.display.flip()







def mac_ici_kadro():
    global durum
    
    # --- 1. REYTİNQ MƏNTİQİ (HƏR GİRİŞDƏ DƏYİŞİR VƏ 6.0-DAN BAŞLAYIR) ---
    for p in kariyer_verisi["kadro"]:
        # Hər dəfə girdikdə fərqli olması üçün "canli_performans"ı hər dəfə yenidən hesablayırıq
        # Başlanğıc balı 6.0 olaraq təyin edildi
        baslangic_puan = 6.0
        
        # Yetenek faktoru: Yeteneği yüksək olanın performansı bir az daha yuxarıdan başlasın (məs: +0.5 qədər)
        yetenek_farki = (p.get("yetenek", 0) / 100) * 0.5
        
        # Hər girişdə dəyişməsi üçün təsadüfi dalğalanma (-0.4 ilə +0.4 arası)
        sans_faktoru = random.uniform(-0.4, 0.4)
        
        # Qol və Asist bonusları (Hər qol +1.0, hər asist +0.6)
        gol_bonusu = p.get("gol", 0) * 1.0
        asist_bonusu = p.get("asist", 0) * 0.6
        
        # Hesablama: 6.0 + yetenek + təsadüfi + maç içi uğurlar
        toplam_reyting = baslangic_puan + yetenek_farki + sans_faktoru + gol_bonusu + asist_bonusu
        
        # Maksimum 10.0 məhdudiyyəti
        p["canli_performans"] = min(10.0, round(toplam_reyting, 1))

    # --- 2. MOVCUD DƏYİŞƏNLƏR (TOXUNULMADI) ---
    son_tiklama_zamani = 0
    tiklanan_oyuncu_id = -1
    secili_degisim_id = -1
    sekme = "SAHA"
    uyari_mesaji = ""
    uyari_suresi = 0
    dizilisler = ["4-3-3", "4-4-2", "3-5-2"]
    
    if "dizilis_idx" not in kariyer_verisi:
        kariyer_verisi["dizilis_idx"] = 0
        
    pos_433 = [(120, 300), (380, 150), (380, 250), (380, 350), (380, 450), (680, 180), (680, 300), (680, 420), (1000, 200), (1000, 300), (1000, 400)]
    pos_442 = [(120, 300), (380, 150), (380, 250), (380, 350), (380, 450), (680, 150), (680, 250), (680, 350), (680, 450), (1000, 250), (1000, 350)]
    pos_352 = [(120, 300), (380, 200), (380, 300), (380, 400), (680, 100), (680, 200), (680, 300), (680, 400), (680, 500), (1000, 250), (1000, 350)]

    while True:
        _focus_begin_frame(("mac_kadro", sekme, kariyer_verisi["dizilis_idx"] if sekme == "SAHA" else None))
        screen.fill(ARKA_PLAN)
        
        if buton_ciz("SAHA", 50, 20, 150, 50, MAVI if sekme=="SAHA" else BUTON_RENGI): sekme = "SAHA"
        if buton_ciz("LİSTE", 210, 20, 150, 50, MAVI if sekme=="LISTE" else BUTON_RENGI): sekme = "LISTE"

        aktif_dizilis = dizilisler[kariyer_verisi["dizilis_idx"]]
        if sekme == "SAHA":
            if buton_ciz(f"DİZİLİŞ: {aktif_dizilis}", 370, 20, 200, 50, ALTIN):
                kariyer_verisi["dizilis_idx"] = (kariyer_verisi["dizilis_idx"] + 1) % len(dizilisler)
                pygame.time.delay(150)

        if uyari_suresi > 0:
            screen.blit(font_baslik.render(uyari_mesaji, True, KIRMIZI), (600, 25))
            uyari_suresi -= 1

        mouse_pos = pygame.mouse.get_pos()

        if sekme == "SAHA":
            if buton_ciz(f"TAKTİK", 700, 20, 300, 50, YESIL):
                _focus_open_screen(taktik_ayarlar_ekrani)
            pygame.draw.rect(screen, SAHA_YESILI, (50, 100, 1180, 420), border_radius=15)
            # [YENI] Mevki renk lejandi (Mac Ici Kadro > SAHA, cimin sol ustu)
            mevki_lejandi_ciz(screen, 58, 104, olcek=0.62, baslik=False, kisa=True)
            
            if aktif_dizilis == "4-3-3": aktif_pos_list = pos_433
            elif aktif_dizilis == "4-4-2": aktif_pos_list = pos_442
            else: aktif_pos_list = pos_352
            
            for i in range(min(11, len(kariyer_verisi["kadro"]))):
                pos = aktif_pos_list[i]
                p = kariyer_verisi["kadro"][i]
                
                c_renk = ALTIN if secili_degisim_id == i else BEYAZ
                if p.get("sakat_gun", 0) > 0: c_renk = KIRMIZI 
                
                pygame.draw.circle(screen, c_renk, pos, 25)
                
                # --- GÖSTERİM ---
                perf = p.get("canli_performans", 6.0)
                info_txt = f"{p.get('mevki', '??')} | {perf}"
                
                txt_surface = font_oyuncu.render(info_txt, True, SIYAH)
                txt_rect = txt_surface.get_rect(center=(pos[0], pos[1] - 40))
                
                bg_rect = txt_rect.inflate(10, 6)
                pygame.draw.rect(screen, BEYAZ, bg_rect, border_radius=5) 
                pygame.draw.rect(screen, c_renk, bg_rect, 2, border_radius=5)
                screen.blit(txt_surface, txt_rect)
                screen.blit(font_oyuncu.render(p["isim"], True, BEYAZ), (pos[0]-30, pos[1]+30))

                # [YENI] Mevki uyumsuzlugu uyarisi (Mac Ici Kadro / SAHA)
                if not is_natural_position(p, _dizilis_slot_mevkisi(aktif_dizilis, i)):
                    draw_position_warning(screen, pos, 25)

                dist = ((mouse_pos[0]-pos[0])**2 + (mouse_pos[1]-pos[1])**2)**0.5
                if _focus_polled_click(pygame.Rect(pos[0] - 25, pos[1] - 25, 50, 50),
                                       pygame.mouse.get_pressed()[0] and dist < 30):
                    simdiki_zaman = pygame.time.get_ticks()
                    if i == tiklanan_oyuncu_id and simdiki_zaman - son_tiklama_zamani < 300:
                        _focus_open_screen(oyuncu_detay_ekrani, p)
                        secili_degisim_id = -1
                    else:
                        if secili_degisim_id != -1 and secili_degisim_id < 11:
                            kariyer_verisi["kadro"][secili_degisim_id], kariyer_verisi["kadro"][i] = kariyer_verisi["kadro"][i], kariyer_verisi["kadro"][secili_degisim_id]
                            secili_degisim_id = -1
                        else:
                            secili_degisim_id = i
                    tiklanan_oyuncu_id = i
                    son_tiklama_zamani = simdiki_zaman
                    pygame.time.delay(150)
            
            # Alt panel (Yedekler)
            pygame.draw.rect(screen, BUTON_RENGI, (50, 540, 1180, 130), border_radius=15)
            for i in range(11, len(kariyer_verisi["kadro"])):
                p = kariyer_verisi["kadro"][i]
                sira_ici = i - 11
                x_pos = 120 + (sira_ici % 10) * 110 - 45
                y_pos = 580 if sira_ici < 10 else 630
                r = pygame.Rect(x_pos, y_pos, 90, 40)
                b_renk = ALTIN if secili_degisim_id == i else MAVI
                pygame.draw.rect(screen, b_renk, r, border_radius=5)
                screen.blit(font_oyuncu.render(p["isim"][:8], True, BEYAZ), (r.x+5, r.y+10))
                
                if _focus_polled_click(r, pygame.mouse.get_pressed()[0] and r.collidepoint(mouse_pos)):
                    if secili_degisim_id != -1:
                        kariyer_verisi["kadro"][secili_degisim_id], kariyer_verisi["kadro"][i] = kariyer_verisi["kadro"][i], kariyer_verisi["kadro"][secili_degisim_id]
                        secili_degisim_id = -1
                    else: secili_degisim_id = i
                    pygame.time.delay(150)
        
        else: # LİSTE SEKME
            for i, p in enumerate(kariyer_verisi["kadro"]):
                y_off = 100 + i * 30
                if y_off > 680: break
                perf = p.get("canli_performans", 6.0)
                txt = font_liste.render(f"{i+1}. {p['isim']:15} | {p['mevki']} | PERF: {perf}", True, YESIL)
                screen.blit(txt, (100, y_off))

        # [YENI] Degisiklikleri Kaydet + Maca Don butonlari (alt sag)
        if buton_ciz("DEĞİŞİKLİKLERİ KAYDET", 850, 672, 250, 42, YESIL):
            uyari_mesaji = "Kaydedildi!"
            uyari_suresi = 90
            pygame.time.delay(150)
        if buton_ciz("MAÇA DÖN", 1110, 672, 140, 42, KIRMIZI): return 
            
        _focus_publish(("mac_kadro", sekme, kariyer_verisi["dizilis_idx"] if sekme == "SAHA" else None))
        for e in _focus_events():
            if e.type == pygame.QUIT: pygame.quit(); sys.exit()
        draw_focus_indicator(screen)
        pygame.display.flip()






def mac_ekrani():
    import math

    test_mode = os.environ.get("FM_TEST_MODE") == "1"
    auto_finish_test = os.environ.get("FM_TEST_AUTO_FINISH") == "1"
    force_injury_minute = os.environ.get("FM_TEST_FORCE_INJURY_MINUTE")
    headless_mode = os.environ.get("SDL_VIDEODRIVER") == "dummy"

    dakika = 0
    s_biz = 0
    s_rak = 0
    logs = ["Maç başladı! Yeni maç motoru devrede."]
    bizim_gol_dakikalari = []
    rakip_gol_dakikalari = []
    clock = pygame.time.Clock()

    kendi_takimim = kariyer_verisi["kulup"]

    # Eski sistemlerle uyumluluk için taktik ustalığı belleğini koru.
    if "taktik_ustaligi" not in kariyer_verisi:
        kariyer_verisi["taktik_ustaligi"] = {}

    kariyer_ucl_verisini_hazirla()
    is_avrupa = False
    rakip_adi = None
    if kariyer_verisi.get("avrupa_lig_katilim", False) and ucl_takvim_sirasi_mi():
        if kariyer_verisi.get("ucl_tur") == "Lig":
            rakip = kariyer_verisi.get("siradaki_ucl_rakip") or ucl_lig_asamasi_mac_ayarla()
            if kariyer_verisi.get("kendi_ucl_maci_var") and rakip:
                is_avrupa = True
                rakip_adi = rakip
                mac_baslik = "UCL LİG AŞAMASI"
        else:
            mac_bilgisi = ucl_eleme_turu_mac_ayarla()
            if mac_bilgisi and kariyer_verisi.get("kendi_ucl_maci_var"):
                is_avrupa = True
                rakip_adi = mac_bilgisi["rakip"]
                ayak = "TEK MAÇ" if mac_bilgisi.get("tek_mac") else ("1. MAÇ" if kariyer_verisi.get("ucl_mac_index", 0) == 0 else "RÖVANŞ")
                mac_baslik = f"UCL {kariyer_verisi.get('ucl_tur', '').upper()} - {ayak}"

    if not is_avrupa:
        rakip_listesi = [k["ad"] for k in KULUPLER if k["ad"] != kendi_takimim["ad"]]
        rakip_adi = rakip_listesi[kariyer_verisi.get("oynanan_mac", 0) % max(1, len(rakip_listesi))]
        mac_baslik = "LİG MAÇI"

    rakip_dict = None
    if is_avrupa:
        for k in AVRUPA_KULUPLER:
            if k["ad"] == rakip_adi:
                rakip_dict = k
                break
    else:
        for k in KULUPLER:
            if k["ad"] == rakip_adi:
                rakip_dict = k
                break

    rakip_oyuncular = TAKIM_OYUNCULARI.get(rakip_adi, [])
    if rakip_oyuncular:
        for p in rakip_oyuncular:
            oyuncu_sezon_verisini_hazirla(p, rakip_adi)
        # [YENI] Rakip, kurabilecegi en iyi ve mevki disi (!) olmayan ilk 11 ile cikar
        _rakip_sonuc = en_iyi_formasyon_ve_ilk11(rakip_oyuncular)
        if _rakip_sonuc:
            rakip_formasyon_idx, rakip_ilk_onbir, _ = _rakip_sonuc
        else:
            rakip_formasyon_idx = 0
            rakip_ilk_onbir = sorted(rakip_oyuncular, key=lambda x: x.get("yetenek", 70), reverse=True)[:11]
        rakip_mac_oncesi_katki = {id(p): (p.get("gol", 0), p.get("asist", 0)) for p in rakip_ilk_onbir}
    else:
        rakip_formasyon_idx = 0
        rakip_ilk_onbir = []
        rakip_mac_oncesi_katki = {}

    for p in kariyer_verisi["kadro"]:
        oyuncu_sezon_verisini_hazirla(p, kendi_takimim["ad"])

    aktif_taktik = kariyer_verisi.get("aktif_taktik", "Gegenpressing")
    ustalik_seviyesi = kariyer_verisi["taktik_ustaligi"].get(aktif_taktik, 0)

    bizim_logo = None
    bizim_dosya = kendi_takimim.get("file")
    if bizim_dosya and os.path.exists(bizim_dosya):
        try:
            bizim_logo = pygame.transform.scale(pygame.image.load(bizim_dosya).convert_alpha(), (60, 60))
        except Exception:
            bizim_logo = None

    rakip_logo = None
    if rakip_dict:
        rakip_dosya = rakip_dict.get("file")
        if rakip_dosya and os.path.exists(rakip_dosya):
            try:
                rakip_logo = pygame.transform.scale(pygame.image.load(rakip_dosya).convert_alpha(), (60, 60))
            except Exception:
                rakip_logo = None

    saha_sol, saha_ust, saha_w, saha_h = 100, 120, 1080, 520
    saha_rect = pygame.Rect(saha_sol, saha_ust, saha_w, saha_h)
    sol_kale_x = saha_sol + 2
    sag_kale_x = saha_sol + saha_w - 2
    kale_ust = saha_ust + saha_h // 2 - 45
    kale_alt = saha_ust + saha_h // 2 + 45

    dakika_basina_saniye = 0.75 if not test_mode else 0.01
    dakika_akumulatoru = 0.0
    possession_last_team = None
    action_cooldown = 0.0
    last_click_time = 0
    final_state_logged = False
    match_over = False
    devre_arasi_animasyonu = False
    devre_arasi_mesaji = False
    devre_anim_timer = 0.0
    ikinci_yari_basladi = False
    sonraki_baslangic_takimi = "rakip"
    gecici_bilgi = ""
    gecici_bilgi_sure = 0.0
    son_yorum_satiri = ""
    mac_ici_degisim_sayisi = 0
    rakip_degisim_sayisi = 0
    injury_callback_called = False

    dizilis_haritasi = {
        0: [(0.08, 0.50), (0.22, 0.18), (0.25, 0.37), (0.25, 0.63), (0.22, 0.82), (0.44, 0.28), (0.47, 0.50), (0.44, 0.72), (0.72, 0.20), (0.78, 0.50), (0.72, 0.80)],
        1: [(0.08, 0.50), (0.22, 0.18), (0.25, 0.37), (0.25, 0.63), (0.22, 0.82), (0.44, 0.20), (0.46, 0.40), (0.46, 0.60), (0.44, 0.80), (0.76, 0.38), (0.76, 0.62)],
        2: [(0.08, 0.50), (0.21, 0.25), (0.24, 0.50), (0.21, 0.75), (0.42, 0.14), (0.44, 0.32), (0.47, 0.50), (0.44, 0.68), (0.42, 0.86), (0.76, 0.38), (0.76, 0.62)]
    }

    taktik_ayar = {
        "Gegenpressing": {"atak": 1.12, "savunma": 0.92, "pres": 1.18, "pas": 0.96, "yorgunluk": 1.28},
        "Tiki-Taka": {"atak": 1.04, "savunma": 1.02, "pres": 0.98, "pas": 1.18, "yorgunluk": 1.08},
        "Catenaccio": {"atak": 0.90, "savunma": 1.18, "pres": 0.86, "pas": 0.95, "yorgunluk": 0.92},
        "Otobüsü Çek": {"atak": 0.78, "savunma": 1.24, "pres": 0.74, "pas": 0.88, "yorgunluk": 0.82},
        "Uzun Top": {"atak": 1.06, "savunma": 0.95, "pres": 0.92, "pas": 0.90, "yorgunluk": 1.02},
        "Total Futbol": {"atak": 1.16, "savunma": 1.04, "pres": 1.08, "pas": 1.08, "yorgunluk": 1.18},
    }
    aktif_taktik_ayar = taktik_ayar.get(aktif_taktik, taktik_ayar["Gegenpressing"])

    def log_ekle(metin):
        nonlocal son_yorum_satiri
        if not metin:
            return
        logs.append(metin)
        son_yorum_satiri = metin
        if len(logs) > 120:
            del logs[:-120]

    def clamp(deger, alt, ust):
        return max(alt, min(ust, deger))

    def mesafe(ax, ay, bx, by):
        return math.hypot(ax - bx, ay - by)

    def lerp(a, b, t):
        return a + (b - a) * t

    def ad_kisalt(isim):
        isim = (isim or "???").replace(".", "").strip()
        if not isim:
            return "???"
        parcalar = isim.split()
        if len(parcalar) == 1:
            return parcalar[0][:3].upper()
        return (parcalar[0][:1] + parcalar[-1][:2]).upper()

    def mevki_grubu(mevki):
        mevki = (mevki or "").upper()
        if mevki == "KL":
            return "kaleci"
        if mevki in ["LB", "RB", "CB"]:
            return "savunma"
        if mevki in ["MDO", "MO", "MOO"]:
            return "orta"
        return "hucum"

    class OyuncuNesnesi:
        def __init__(self, oyuncu_dict, takim, takim_kodu, takim_adi, numara, renk):
            self.ref = oyuncu_dict
            self.takim = takim
            self.takim_kodu = takim_kodu
            self.takim_adi = takim_adi
            self.numara = numara
            self.renk = renk
            self.isim = oyuncu_dict.get("isim", f"Oyuncu {numara}")
            self.kisa_isim = ad_kisalt(self.isim)
            self.mevki = oyuncu_dict.get("mevki", "MO")
            self.grup = mevki_grubu(self.mevki)
            self.yetenek = float(oyuncu_dict.get("yetenek", 70))
            self.enerji = float(oyuncu_dict.get("enerji", 100))
            self.sakat_gun = oyuncu_dict.get("sakat_gun", 0)
            self.x = saha_sol + saha_w * (0.30 if takim_kodu == "bizim" else 0.70)
            self.y = saha_ust + saha_h * 0.50
            self.hedef_x = self.x
            self.hedef_y = self.y
            self.hiz = 120 + (self.yetenek - 60) * 2.0
            self.topa_sahip = False
            self.aktif = True
            self.katki = 0.0
            self.anlik_rating = oyuncu_dict.get("canli_performans", 6.0)
            self.son_pas = 0
            self.son_sut = 0
            self.son_mudahale = 0
            self.son_hata = 0

        def yetenek_katsayisi(self):
            return clamp(self.yetenek / 100.0, 0.45, 0.99)

        def enerji_katsayisi(self):
            return clamp(self.enerji / 100.0, 0.35, 1.0)

        def performans_hesapla(self):
            baz = 6.0 + (self.yetenek - 70) * 0.018
            enerji_cezasi = (100 - self.enerji) * 0.009
            self.anlik_rating = clamp(round(baz + self.katki - enerji_cezasi, 1), 4.8, 10.0)
            return self.anlik_rating

        def sync_to_ref(self):
            self.ref["enerji"] = round(clamp(self.enerji, 1, 100), 1)
            self.ref["canli_performans"] = self.performans_hesapla()
            self.ref.setdefault("sakat_gun", self.sakat_gun)

        def hedefe_yuru(self, dt):
            dx = self.hedef_x - self.x
            dy = self.hedef_y - self.y
            uzaklik = math.hypot(dx, dy)
            if uzaklik < 1:
                return
            efektif_hiz = self.hiz * (0.80 + 0.35 * self.enerji_katsayisi())
            adim = min(uzaklik, efektif_hiz * dt)
            self.x += (dx / uzaklik) * adim
            self.y += (dy / uzaklik) * adim

    class TopNesnesi:
        def __init__(self):
            self.x = saha_sol + saha_w / 2
            self.y = saha_ust + saha_h / 2
            self.vx = 0.0
            self.vy = 0.0
            self.sahip = None
            self.hedef = None
            self.durum = "durdu"
            self.hedefe_varma_suresi = 0.0
            self.son_pasor = None
            self.son_aksiyon = {}
            self.son_sahip_takim = None

        def sahip_yap(self, oyuncu):
            self.sahip = oyuncu
            self.hedef = None
            self.vx = 0.0
            self.vy = 0.0
            self.hedefe_varma_suresi = 0.0
            self.durum = "durdu"
            if oyuncu:
                self.son_sahip_takim = oyuncu.takim_kodu
                self.x = oyuncu.x + (10 if oyuncu.takim_kodu == "bizim" else -10)
                self.y = oyuncu.y
            for t in takimlar.values():
                for o in t.oyuncular:
                    o.topa_sahip = (o is oyuncu)

        def firlat(self, hedef_x, hedef_y, hiz, durum, hedef=None, aksiyon=None):
            self.sahip = None
            self.hedef = hedef
            self.durum = durum
            dx = hedef_x - self.x
            dy = hedef_y - self.y
            uzaklik = max(1.0, math.hypot(dx, dy))
            self.vx = (dx / uzaklik) * hiz
            self.vy = (dy / uzaklik) * hiz
            self.hedefe_varma_suresi = uzaklik / max(hiz, 1.0)
            self.son_aksiyon = aksiyon or {}
            for t in takimlar.values():
                for o in t.oyuncular:
                    o.topa_sahip = False

        def guncelle(self, dt):
            if self.sahip:
                self.x = self.sahip.x + (12 if self.sahip.takim_kodu == "bizim" else -12)
                self.y = self.sahip.y
                return False

            self.x += self.vx * dt
            self.y += self.vy * dt
            self.hedefe_varma_suresi -= dt
            self.x = clamp(self.x, saha_sol - 25, saha_sol + saha_w + 25)
            self.y = clamp(self.y, saha_ust - 25, saha_ust + saha_h + 25)
            if self.hedefe_varma_suresi <= 0:
                return True
            return False

    class TakimNesnesi:
        def __init__(self, ad, takim_kodu, renk, yon, formasyon_idx, oyuncular):
            self.ad = ad
            self.takim_kodu = takim_kodu
            self.renk = renk
            self.yon = yon
            self.formasyon_idx = formasyon_idx
            self.oyuncular = oyuncular
            self.istatistikler = {
                "pas": 0,
                "pas_deneme": 0,
                "sut": 0,
                "isabet": 0,
                "top_kaybi": 0,
                "kurtaris": 0,
                "faul": 0,
                "ofsayt": 0,
                "korner": 0,
                "penalti": 0,
                "frikik": 0,
            }
            self.possession_seconds = 0.0
            self.goller = 0
            self.degisim_sayisi = 0

        def kaleci(self):
            for oyuncu in self.oyuncular:
                if oyuncu.grup == "kaleci":
                    return oyuncu
            return self.oyuncular[0]

        def rakip_ceza_sahasi_x(self):
            return saha_sol + saha_w - 120 if self.yon == 1 else saha_sol + 120

        def kendi_kale_x(self):
            return saha_sol + 15 if self.yon == 1 else saha_sol + saha_w - 15

        def sut_bolgesi_mi(self, oyuncu):
            if self.yon == 1:
                return oyuncu.x > saha_sol + saha_w * 0.66
            return oyuncu.x < saha_sol + saha_w * 0.34

        def orta_saha_mi(self, oyuncu):
            return abs(oyuncu.x - (saha_sol + saha_w / 2)) < 120

        def en_yakin_oyuncu(self, x, y, yalnizca_aktif=True):
            adaylar = [o for o in self.oyuncular if (o.aktif if yalnizca_aktif else True)]
            if not adaylar:
                return None
            return min(adaylar, key=lambda o: mesafe(o.x, o.y, x, y))

    def oyuncu_nesnesi_olustur(oyuncu_dict, takim):
        return OyuncuNesnesi(
            oyuncu_dict,
            takim=takim["obj"],
            takim_kodu=takim["kod"],
            takim_adi=takim["ad"],
            numara=takim["numara"],
            renk=takim["renk"],
        )

    def takim_kur(ad, takim_kodu, renk, yon, formasyon_idx, oyuncu_listesi):
        meta = {"obj": None, "kod": takim_kodu, "ad": ad, "renk": renk, "numara": 1}
        oyuncular = []
        for sira, oyuncu_dict in enumerate(oyuncu_listesi[:11]):
            oyuncu = oyuncu_nesnesi_olustur(oyuncu_dict, meta)
            # [YENI] bu oyuncunun sahaya yerlestirildigi slotun mevki kodu
            oyuncu.slot_mevki = _dizilis_slot_mevkisi(formasyon_idx, sira)
            oyuncular.append(oyuncu)
            meta["numara"] += 1
        takim_obj = TakimNesnesi(ad, takim_kodu, renk, yon, formasyon_idx, oyuncular)
        meta["obj"] = takim_obj
        for oyuncu in oyuncular:
            oyuncu.takim = takim_obj
        return takim_obj

    def takim_ortalama_guc(takim):
        if not takim.oyuncular:
            return 70.0
        toplam = 0.0
        for oyuncu in takim.oyuncular:
            toplam += oyuncu.yetenek * (0.55 + 0.45 * oyuncu.enerji_katsayisi())
        return toplam / max(1, len(takim.oyuncular))

    def takimi_yeniden_kur():
        bizim_formasyon = kariyer_verisi.get("dizilis_idx", 0)
        bizim_ilk_onbir = kariyer_verisi["kadro"][:11]
        rakip_formasyon = rakip_formasyon_idx if len(rakip_ilk_onbir) >= 11 else 0
        takimlar["bizim"] = takim_kur(kendi_takimim["ad"], "bizim", MAVI, 1, bizim_formasyon, bizim_ilk_onbir)
        takimlar["rakip"] = takim_kur(rakip_adi, "rakip", KIRMIZI, -1, rakip_formasyon, rakip_ilk_onbir if rakip_ilk_onbir else [{"isim": f"Rakip {i+1}", "mevki": "MO", "yetenek": 72} for i in range(11)])

    takimlar = {}
    takimi_yeniden_kur()
    top = TopNesnesi()

    def base_position(formasyon_idx, takim_kodu, index):
        sablon = dizilis_haritasi.get(formasyon_idx, dizilis_haritasi[0])
        rx, ry = sablon[min(index, len(sablon) - 1)]
        if takim_kodu == "rakip":
            rx = 1.0 - rx
        return saha_sol + rx * saha_w, saha_ust + ry * saha_h

    def takim_pozisyonlarini_guncelle(takim, rakip, dt):
        top_x = top.x if top else saha_sol + saha_w / 2
        top_y = top.y if top else saha_ust + saha_h / 2
        top_bizde = top.sahip is not None and top.sahip.takim_kodu == takim.takim_kodu
        yatay_kaydirma = ((top_x - (saha_sol + saha_w / 2)) / saha_w) * 110
        dikey_kaydirma = ((top_y - (saha_ust + saha_h / 2)) / saha_h) * 90
        takim_bonusu = 60 if top_bizde else -45
        takim_bonusu *= (1.0 if takim.takim_kodu == "bizim" else -1.0)

        for index, oyuncu in enumerate(takim.oyuncular):
            bx, by = base_position(takim.formasyon_idx, takim.takim_kodu, index)
            rol = oyuncu.grup
            x_katki = 0.0
            y_katki = 0.0

            if rol == "kaleci":
                x_katki += (18 if top_bizde else -8) * takim.yon
                y_katki += dikey_kaydirma * 0.12
            elif rol == "savunma":
                x_katki += yatay_kaydirma * 0.30 + takim_bonusu * 0.45
                y_katki += dikey_kaydirma * 0.45
                if oyuncu.mevki == "LB":
                    y_katki -= 26
                elif oyuncu.mevki == "RB":
                    y_katki += 26
            elif rol == "orta":
                x_katki += yatay_kaydirma * 0.60 + takim_bonusu * 0.75
                y_katki += dikey_kaydirma * 0.65
                if takim.orta_saha_mi(oyuncu) and top_bizde:
                    x_katki += 18 * takim.yon
            else:
                x_katki += yatay_kaydirma * 0.82 + takim_bonusu
                y_katki += dikey_kaydirma * 0.55
                if oyuncu.mevki == "LW":
                    y_katki -= 22
                elif oyuncu.mevki == "RW":
                    y_katki += 22

            if top.sahip is oyuncu:
                x_katki += 40 * takim.yon
                y_katki += (top_y - by) * 0.08

            oyuncu.hedef_x = clamp(bx + x_katki, saha_sol + 25, saha_sol + saha_w - 25)
            oyuncu.hedef_y = clamp(by + y_katki, saha_ust + 25, saha_ust + saha_h - 25)
            oyuncu.hedefe_yuru(dt)
            oyuncu.sync_to_ref()

    def saha_ciz():
        pygame.draw.rect(screen, SAHA_YESILI, saha_rect, border_radius=18)
        pygame.draw.rect(screen, BEYAZ, saha_rect, 3, border_radius=18)
        pygame.draw.line(screen, BEYAZ, (saha_sol + saha_w // 2, saha_ust), (saha_sol + saha_w // 2, saha_ust + saha_h), 3)
        pygame.draw.circle(screen, BEYAZ, (saha_sol + saha_w // 2, saha_ust + saha_h // 2), 62, 3)
        pygame.draw.circle(screen, BEYAZ, (saha_sol + saha_w // 2, saha_ust + saha_h // 2), 4)

        # Ceza sahaları ve kale alanları
        pygame.draw.rect(screen, BEYAZ, (saha_sol, saha_ust + saha_h / 2 - 110, 135, 220), 3)
        pygame.draw.rect(screen, BEYAZ, (saha_sol + saha_w - 135, saha_ust + saha_h / 2 - 110, 135, 220), 3)
        pygame.draw.rect(screen, BEYAZ, (saha_sol, saha_ust + saha_h / 2 - 55, 55, 110), 3)
        pygame.draw.rect(screen, BEYAZ, (saha_sol + saha_w - 55, saha_ust + saha_h / 2 - 55, 55, 110), 3)
        pygame.draw.rect(screen, BEYAZ, (saha_sol - 8, saha_ust + saha_h / 2 - 38, 8, 76), 2)
        pygame.draw.rect(screen, BEYAZ, (saha_sol + saha_w, saha_ust + saha_h / 2 - 38, 8, 76), 2)

        # Penaltı noktaları ve yaylar
        pygame.draw.circle(screen, BEYAZ, (saha_sol + 95, saha_ust + saha_h // 2), 3)
        pygame.draw.circle(screen, BEYAZ, (saha_sol + saha_w - 95, saha_ust + saha_h // 2), 3)
        pygame.draw.arc(screen, BEYAZ, (saha_sol + 60, saha_ust + saha_h / 2 - 62, 90, 124), math.radians(305), math.radians(55), 2)
        pygame.draw.arc(screen, BEYAZ, (saha_sol + saha_w - 150, saha_ust + saha_h / 2 - 62, 90, 124), math.radians(125), math.radians(235), 2)

        # Köşe yayları
        pygame.draw.arc(screen, BEYAZ, (saha_sol - 12, saha_ust - 12, 24, 24), 0, math.pi / 2, 2)
        pygame.draw.arc(screen, BEYAZ, (saha_sol - 12, saha_ust + saha_h - 12, 24, 24), math.pi * 1.5, math.pi * 2, 2)
        pygame.draw.arc(screen, BEYAZ, (saha_sol + saha_w - 12, saha_ust - 12, 24, 24), math.pi / 2, math.pi, 2)
        pygame.draw.arc(screen, BEYAZ, (saha_sol + saha_w - 12, saha_ust + saha_h - 12, 24, 24), math.pi, math.pi * 1.5, 2)

    def oyuncu_ciz(oyuncu, secili=False):
        merkez = (int(oyuncu.x), int(oyuncu.y))
        kenar = ALTIN if secili or oyuncu.topa_sahip else BEYAZ
        pygame.draw.circle(screen, oyuncu.renk, merkez, 20)
        pygame.draw.circle(screen, kenar, merkez, 3)
        numara = font_oyuncu.render(str(oyuncu.numara), True, SIYAH)
        screen.blit(numara, numara.get_rect(center=merkez))
        isim = font_agac.render(oyuncu.kisa_isim, True, BEYAZ)
        screen.blit(isim, isim.get_rect(center=(merkez[0], merkez[1] + 28)))
        rating = font_agac.render(f"{oyuncu.performans_hesapla():.1f}", True, ALTIN if oyuncu.enerji < 45 else BEYAZ)
        screen.blit(rating, rating.get_rect(center=(merkez[0], merkez[1] - 28)))
        # [YENI] Mevki uyumsuzlugu uyarisi (canli mac sahasi)
        if not is_natural_position(getattr(oyuncu, "ref", None), getattr(oyuncu, "slot_mevki", None)):
            draw_position_warning(screen, merkez, 20)

    def top_ciz(top_nesnesi):
        pygame.draw.circle(screen, BEYAZ, (int(top_nesnesi.x), int(top_nesnesi.y)), 8)
        pygame.draw.circle(screen, SIYAH, (int(top_nesnesi.x), int(top_nesnesi.y)), 8, 1)

    def takim_paneli_ciz(takim, x, y, baslik_renk):
        panel_ciz(x, y, 235, 212, dolgu=(16, 23, 38), cerceve=baslik_renk, yaricap=16, golge=False)
        screen.blit(font_oyuncu.render(takim.ad[:16].upper(), True, baslik_renk), (x + 10, y + 8))
        sahip_toplam = takimlar["bizim"].possession_seconds + takimlar["rakip"].possession_seconds
        sahip_yuzde = 50.0 if sahip_toplam <= 0 else (takim.possession_seconds / sahip_toplam) * 100.0
        satirlar = [
            f"Pas: {takim.istatistikler['pas']} / {takim.istatistikler['pas_deneme']}",
            f"Şut: {takim.istatistikler['sut']} / {takim.istatistikler['isabet']}",
            f"Top Kaybı: {takim.istatistikler['top_kaybi']}",
            f"Kurtarış: {takim.istatistikler['kurtaris']}",
            f"Faul: {takim.istatistikler['faul']}",
            f"Ofsayt: {takim.istatistikler['ofsayt']}",
            f"Korner: {takim.istatistikler['korner']}",
            f"Topa Sahip Olma: {sahip_yuzde:.1f}%",
        ]
        for idx, satir in enumerate(satirlar):
            screen.blit(font_agac.render(satir, True, BEYAZ), (x + 10, y + 42 + idx * 21))

    def skorboard_ciz():
        panel_ciz(WIDTH // 2 - 335, 18, 670, 92, dolgu=(18, 26, 40), cerceve=ALTIN, yaricap=20, golge=False)
        txt_skor = font_skor.render(f"{s_biz} - {s_rak}", True, ALTIN)
        screen.blit(txt_skor, txt_skor.get_rect(center=(WIDTH // 2, 64)))
        screen.blit(font_buton.render(f"{dakika:02d}'", True, BEYAZ), (WIDTH // 2 - 44, 74))
        sol_baslik = font_oyuncu.render(kendi_takimim["ad"][:15].upper(), True, YESIL)
        sag_baslik = font_oyuncu.render(rakip_adi[:15].upper(), True, KIRMIZI)
        screen.blit(sol_baslik, (WIDTH // 2 - 300, 60))
        screen.blit(sag_baslik, (WIDTH // 2 + 180, 60))
        ust_yazi = font_agac.render(mac_baslik, True, ALTIN)
        screen.blit(ust_yazi, ust_yazi.get_rect(center=(WIDTH // 2, 28)))
        if bizim_logo:
            screen.blit(bizim_logo, (WIDTH // 2 - 320, 28))
        if rakip_logo:
            screen.blit(rakip_logo, (WIDTH // 2 + 250, 28))

    def olay_paneli_ciz():
        panel_ciz(90, 650, 1100, 60, dolgu=(14, 20, 30), cerceve=BEYAZ, yaricap=15, golge=False)
        son_alt = logs[-2:] if len(logs) >= 2 else logs
        for idx, log in enumerate(son_alt):
            renk = YESIL if ("GOL" in log and "Rakip" not in log) else (KIRMIZI if "Rakip" in log or "sakat" in log.lower() else ALTIN if "PENALTI" in log or "FRİKİK" in log else BEYAZ)
            screen.blit(font_log.render(log[:95], True, renk), (110, 660 + idx * 24))
        if gecici_bilgi and gecici_bilgi_sure > 0:
            etiket_ciz(gecici_bilgi, 900, 660, ALTIN, SIYAH, padding_x=10, yukseklik=28)

    def takim_taraftari_gucu(takim):
        guc = takim_ortalama_guc(takim)
        if takim.takim_kodu == "bizim":
            guc *= aktif_taktik_ayar["atak"] * (1.0 + min(ustalik_seviyesi * 0.01, 0.20))
        return guc

    def en_yakin_rakip(oyuncu):
        rakip = takimlar["rakip" if oyuncu.takim_kodu == "bizim" else "bizim"]
        return rakip.en_yakin_oyuncu(oyuncu.x, oyuncu.y)

    def bos_alan_puani(oyuncu):
        rakip = en_yakin_rakip(oyuncu)
        if not rakip:
            return 1.0
        return clamp(mesafe(oyuncu.x, oyuncu.y, rakip.x, rakip.y) / 220.0, 0.2, 1.2)

    def en_iyi_pas_hedefi(oyuncu):
        ayni_takim = takimlar[oyuncu.takim_kodu]
        adaylar = []
        agirliklar = []
        for aday in ayni_takim.oyuncular:
            if aday is oyuncu or not aday.aktif:
                continue
            uzaklik = mesafe(oyuncu.x, oyuncu.y, aday.x, aday.y)
            if uzaklik < 40 or uzaklik > 360:
                continue
            ileri_kazanc = (aday.x - oyuncu.x) * ayni_takim.yon
            aciklik = bos_alan_puani(aday)
            rol_bonus = 1.15 if aday.grup == "hucum" else (1.05 if aday.grup == "orta" else 0.95)
            agirlik = max(0.1, (1.0 + ileri_kazanc / 180.0) * aciklik * rol_bonus)
            adaylar.append(aday)
            agirliklar.append(agirlik)
        if not adaylar:
            return None
        return random.choices(adaylar, weights=agirliklar, k=1)[0]

    def yerden_dripling(oyuncu):
        takim = takimlar[oyuncu.takim_kodu]
        y_sapma = random.uniform(-30, 30)
        ileri = random.uniform(24, 52) * takim.yon
        oyuncu.x = clamp(oyuncu.x + ileri * 0.15, saha_sol + 20, saha_sol + saha_w - 20)
        oyuncu.y = clamp(oyuncu.y + y_sapma * 0.10, saha_ust + 20, saha_ust + saha_h - 20)
        oyuncu.katki += 0.02
        if random.random() < 0.14 * (1.18 - oyuncu.enerji_katsayisi()):
            rakip = en_yakin_rakip(oyuncu)
            if rakip and mesafe(oyuncu.x, oyuncu.y, rakip.x, rakip.y) < 52:
                top_kapma_deneme(rakip, oyuncu, zorunlu=True)

    def top_kapma_deneme(mudahaleci, top_sahibi, zorunlu=False):
        if top.sahip is not top_sahibi:
            return False
        baski = clamp((85 - mesafe(mudahaleci.x, mudahaleci.y, top_sahibi.x, top_sahibi.y)) / 85.0, 0.0, 1.0)
        basari = 0.20 + baski * 0.35 + mudahaleci.yetenek_katsayisi() * 0.18 - top_sahibi.yetenek_katsayisi() * 0.12
        if mudahaleci.takim_kodu == "rakip":
            basari *= aktif_taktik_ayar["savunma"]
        if zorunlu:
            basari += 0.08
        if random.random() < 0.08 and baski > 0.30:
            foul_yap(mudahaleci, top_sahibi)
            return True
        if random.random() < basari:
            top_sahibi.katki -= 0.14
            mudahaleci.katki += 0.10
            takimlar[top_sahibi.takim_kodu].istatistikler["top_kaybi"] += 1
            top.sahip_yap(mudahaleci)
            top.son_pasor = None
            log_ekle(f"{dakika}' {mudahaleci.isim} topu kaptı!")
            return True
        return False

    def ofsayt_kontrolu(pasor, hedef):
        rakipler = takimlar["rakip" if pasor.takim_kodu == "bizim" else "bizim"].oyuncular
        if len(rakipler) < 2:
            return False
        sirali = sorted([r.x for r in rakipler], reverse=(pasor.takim_kodu == "bizim"))
        cizgi = sirali[1] if len(sirali) > 1 else sirali[0]
        if pasor.takim_kodu == "bizim":
            return hedef.x > cizgi and hedef.x > pasor.x + 35
        return hedef.x < cizgi and hedef.x < pasor.x - 35

    def pas_at(pasor, hedef, ozel_tur="pas"):
        takim = takimlar[pasor.takim_kodu]
        takim.istatistikler["pas_deneme"] += 1
        mesafe_pas = mesafe(pasor.x, pasor.y, hedef.x, hedef.y)
        baski = 0.0
        rakip = en_yakin_rakip(pasor)
        if rakip:
            baski = clamp((120 - mesafe(pasor.x, pasor.y, rakip.x, rakip.y)) / 120.0, 0.0, 0.8)

        if ozel_tur == "pas" and ofsayt_kontrolu(pasor, hedef) and random.random() < 0.22:
            takim.istatistikler["ofsayt"] += 1
            takim.istatistikler["top_kaybi"] += 1
            top.sahip_yap(takimlar["rakip" if pasor.takim_kodu == "bizim" else "bizim"].kaleci())
            log_ekle(f"{dakika}' Ofsayt! {hedef.isim} çok erken kaçtı.")
            return

        basari_orani = 0.66 + pasor.yetenek_katsayisi() * 0.20 + pasor.enerji_katsayisi() * 0.08
        basari_orani += (aktif_taktik_ayar["pas"] - 1.0) * 0.25 if pasor.takim_kodu == "bizim" else 0.0
        basari_orani -= mesafe_pas / 820.0
        basari_orani -= baski * 0.22
        basari = random.random() < clamp(basari_orani, 0.18, 0.95)
        hiz = 460 if ozel_tur == "pas" else 510
        pasor.katki += 0.03 if basari else -0.08
        aksiyon = {
            "tip": ozel_tur,
            "pasor": pasor,
            "hedef": hedef,
            "basarili": basari,
        }
        top.son_pasor = pasor if basari else None
        top.firlat(hedef.x, hedef.y, hiz, ozel_tur, hedef=hedef, aksiyon=aksiyon)
        if basari:
            log_ekle(f"{dakika}' {pasor.isim} -> {hedef.isim} pası gönderdi.")
        else:
            log_ekle(f"{dakika}' {pasor.isim} pas hatası yaptı.")

    def sut_cek(sutoru, ozel_tur="sut"):
        takim = takimlar[sutoru.takim_kodu]
        rakip = takimlar["rakip" if sutoru.takim_kodu == "bizim" else "bizim"]
        kaleci = rakip.kaleci()
        hedef_x = sag_kale_x if takim.takim_kodu == "bizim" else sol_kale_x
        hedef_y = random.uniform(kale_ust + 5, kale_alt - 5)
        uzaklik = mesafe(sutoru.x, sutoru.y, hedef_x, hedef_y)
        takim.istatistikler["sut"] += 1
        if ozel_tur == "frikik":
            takim.istatistikler["frikik"] += 1
        elif ozel_tur == "penalti":
            takim.istatistikler["penalti"] += 1

        isabet = 0.30 + sutoru.yetenek_katsayisi() * 0.28 - uzaklik / 1150.0
        if ozel_tur == "penalti":
            isabet += 0.34
        elif ozel_tur == "frikik":
            isabet += 0.08
        elif takim.orta_saha_mi(sutoru):
            isabet -= 0.10
        isabetli = random.random() < clamp(isabet, 0.08, 0.92)
        if isabetli:
            takim.istatistikler["isabet"] += 1
        if not isabetli:
            hedef_y = random.uniform(saha_ust + 50, saha_ust + saha_h - 50)
            hedef_x += 40 * takim.yon

        save_sansi = 0.40 + kaleci.yetenek_katsayisi() * 0.24 - sutoru.yetenek_katsayisi() * 0.10
        if ozel_tur == "penalti":
            save_sansi -= 0.16
        kurtarir = isabetli and (random.random() < clamp(save_sansi, 0.05, 0.78))
        korner = kurtarir and random.random() < 0.25 and ozel_tur != "penalti"

        aksiyon = {
            "tip": ozel_tur,
            "sutoru": sutoru,
            "kaleci": kaleci,
            "isabetli": isabetli,
            "kurtaris": kurtarir,
            "korner": korner,
            "yardimci": top.son_pasor if top.son_pasor is not sutoru else None,
        }
        top.firlat(hedef_x, hedef_y, 700 if ozel_tur != "penalti" else 760, ozel_tur, aksiyon=aksiyon)
        if ozel_tur == "penalti":
            log_ekle(f"{dakika}' PENALTI! {sutoru.isim} topun başında.")
        elif ozel_tur == "frikik":
            log_ekle(f"{dakika}' FRİKİK! {sutoru.isim} kaleyi yokluyor.")
        elif takim.orta_saha_mi(sutoru):
            log_ekle(f"{dakika}' {sutoru.isim} orta sahadan sürpriz bir şut çıkardı!")
        else:
            log_ekle(f"{dakika}' {sutoru.isim} şutunu gönderdi!")
        sutoru.katki += 0.04

    def korner_kullan(takim):
        takim.istatistikler["korner"] += 1
        adaylar = [o for o in takim.oyuncular if o.grup != "kaleci"]
        ortaci = max(adaylar, key=lambda o: (o.yetenek, -abs(o.y - (saha_ust + saha_h / 2)))) if adaylar else takim.oyuncular[0]
        ceza_alani = [o for o in takim.oyuncular if o.grup in ["savunma", "hucum"]]
        hedef = random.choice(ceza_alani) if ceza_alani else ortaci
        log_ekle(f"{dakika}' {takim.ad} köşe vuruşu kullanıyor.")
        pas_at(ortaci, hedef, ozel_tur="pas")

    def en_iyi_frikikci(takim):
        return max(takim.oyuncular, key=lambda o: (o.yetenek, 0 if o.grup == "kaleci" else 1))

    def foul_yap(mudahaleci, top_sahibi):
        savunan = takimlar[mudahaleci.takim_kodu]
        hucum = takimlar[top_sahibi.takim_kodu]
        savunan.istatistikler["faul"] += 1
        mudahaleci.katki -= 0.05
        top_sahibi.katki += 0.03
        log_ekle(f"{dakika}' Faul! {mudahaleci.isim}, {top_sahibi.isim}'i durdurdu.")
        ceza_alani_ici = (top_sahibi.takim_kodu == "bizim" and top_sahibi.x > saha_sol + saha_w - 145) or (top_sahibi.takim_kodu == "rakip" and top_sahibi.x < saha_sol + 145)
        if ceza_alani_ici and random.random() < 0.38:
            sut_cek(en_iyi_frikikci(hucum), ozel_tur="penalti")
            return
        sut_cek(en_iyi_frikikci(hucum), ozel_tur="frikik")

    def topa_en_yakin_oyuncu():
        adaylar = takimlar["bizim"].oyuncular + takimlar["rakip"].oyuncular
        return min(adaylar, key=lambda o: mesafe(o.x, o.y, top.x, top.y)) if adaylar else None

    def top_hareket_sonu_coz():
        aksiyon = top.son_aksiyon or {}
        tip = aksiyon.get("tip", top.durum)
        if tip in ["pas", "frikik_pas"]:
            hedef = aksiyon.get("hedef")
            pasor = aksiyon.get("pasor")
            basarili = aksiyon.get("basarili", False)
            if basarili and hedef and hedef.aktif:
                takimlar[pasor.takim_kodu].istatistikler["pas"] += 1
                hedef.katki += 0.04
                pasor.katki += 0.06
                top.sahip_yap(hedef)
                return
            if pasor:
                takimlar[pasor.takim_kodu].istatistikler["top_kaybi"] += 1
                pasor.katki -= 0.10
            kazanan = topa_en_yakin_oyuncu()
            if kazanan:
                kazanan.katki += 0.05
                top.sahip_yap(kazanan)
            else:
                top.durum = "serbest"
            return

        if tip in ["sut", "frikik", "penalti"]:
            sutoru = aksiyon.get("sutoru")
            kaleci = aksiyon.get("kaleci")
            isabetli = aksiyon.get("isabetli", False)
            kurtaris = aksiyon.get("kurtaris", False)
            korner = aksiyon.get("korner", False)
            yardimci = aksiyon.get("yardimci")
            atan_takim = takimlar[sutoru.takim_kodu]
            savunan = takimlar["rakip" if sutoru.takim_kodu == "bizim" else "bizim"]

            if not isabetli:
                log_ekle(f"{dakika}' {sutoru.isim} çerçeveyi bulamadı.")
                top.sahip_yap(kaleci)
                sutoru.katki -= 0.03
                return

            if kurtaris:
                savunan.istatistikler["kurtaris"] += 1
                kaleci.katki += 0.10
                sutoru.katki += 0.04
                if korner:
                    log_ekle(f"{dakika}' Müthiş kurtarış! Top kornere çıktı.")
                    top.sahip_yap(None)
                    top.x = kaleci.x
                    top.y = kaleci.y
                    korner_kullan(atan_takim)
                else:
                    log_ekle(f"{dakika}' {kaleci.isim} gole izin vermedi.")
                    top.sahip_yap(kaleci)
                return

            gol_oldu(sutoru, yardimci)
            return

        kazanan = topa_en_yakin_oyuncu()
        if kazanan:
            top.sahip_yap(kazanan)

    def gol_oldu(golcu, asistci=None):
        nonlocal s_biz, s_rak, dakika
        takim = takimlar[golcu.takim_kodu]
        if golcu.takim_kodu == "bizim":
            s_biz += 1
            bizim_gol_dakikalari.append(dakika)
            sonraki_sahip = "rakip"
        else:
            s_rak += 1
            rakip_gol_dakikalari.append(dakika)
            sonraki_sahip = "bizim"
        takim.goller += 1
        golcu.ref["gol"] = golcu.ref.get("gol", 0) + 1
        golcu.katki += 1.15
        if asistci and asistci is not golcu:
            asistci.ref["asist"] = asistci.ref.get("asist", 0) + 1
            asistci.katki += 0.48
            log_ekle(f"{dakika}' GOL! {golcu.isim} attı, asist {asistci.isim}.")
        else:
            log_ekle(f"{dakika}' GOL! {golcu.isim} fileleri havalandırdı.")
        oyunu_baslat(sonraki_sahip, gol_sonrasi=True)

    def oyunu_baslat(sahip_takim_kodu="bizim", gol_sonrasi=False):
        nonlocal action_cooldown
        takim = takimlar[sahip_takim_kodu]
        rakip = takimlar["rakip" if sahip_takim_kodu == "bizim" else "bizim"]
        for t in takimlar.values():
            for index, oyuncu in enumerate(t.oyuncular):
                bx, by = base_position(t.formasyon_idx, t.takim_kodu, index)
                oyuncu.x = bx
                oyuncu.y = by
                oyuncu.hedef_x = bx
                oyuncu.hedef_y = by
        santra_adaylari = [o for o in takim.oyuncular if o.grup in ["hucum", "orta"]]
        santra = santra_adaylari[0] if santra_adaylari else takim.oyuncular[0]
        destek = en_iyi_pas_hedefi(santra)
        santra.x = saha_sol + saha_w / 2 - 20 * takim.yon
        santra.y = saha_ust + saha_h / 2
        if destek:
            destek.x = saha_sol + saha_w / 2 + 35 * takim.yon
            destek.y = saha_ust + saha_h / 2 + random.choice([-26, 26])
        top.x = saha_sol + saha_w / 2
        top.y = saha_ust + saha_h / 2
        top.sahip_yap(santra)
        top.son_pasor = None
        action_cooldown = 0.35 if not gol_sonrasi else 0.55
        rakip.kaleci().x = clamp(rakip.kaleci().x, saha_sol + 16, saha_sol + saha_w - 16)

    def oyuncu_aksiyonu_ver(oyuncu):
        takim = takimlar[oyuncu.takim_kodu]
        rakip_takim = takimlar["rakip" if oyuncu.takim_kodu == "bizim" else "bizim"]
        baskici = en_yakin_rakip(oyuncu)
        baski_mesafesi = mesafe(oyuncu.x, oyuncu.y, baskici.x, baskici.y) if baskici else 999
        sut_istegi = 0.14
        if takim.sut_bolgesi_mi(oyuncu):
            sut_istegi = 0.40 if oyuncu.grup == "hucum" else 0.24
        elif takim.orta_saha_mi(oyuncu):
            rakip_kaleci = rakip_takim.kaleci()
            if abs(rakip_kaleci.x - rakip_takim.kendi_kale_x()) > 16:
                sut_istegi = 0.18

        sut_istegi += (oyuncu.yetenek_katsayisi() - 0.70) * 0.18
        sut_istegi -= 0.12 if baski_mesafesi < 48 else 0.0
        sut_istegi = clamp(sut_istegi, 0.05, 0.65)

        if baskici and baski_mesafesi < 42 and top_kapma_deneme(baskici, oyuncu):
            return

        if random.random() < sut_istegi:
            sut_cek(oyuncu, "sut")
            return

        hedef = en_iyi_pas_hedefi(oyuncu)
        if hedef and random.random() < 0.78:
            pas_at(oyuncu, hedef, "pas")
            return

        yerden_dripling(oyuncu)

    def dakika_olayi_isle():
        nonlocal gecici_bilgi, gecici_bilgi_sure, injury_callback_called
        bizim = takimlar["bizim"]
        rakip = takimlar["rakip"]
        for oyuncu in bizim.oyuncular:
            yorgunluk = 0.30 * aktif_taktik_ayar["yorgunluk"]
            if oyuncu.grup == "hucum":
                yorgunluk *= 1.08
            oyuncu.enerji = clamp(oyuncu.enerji - yorgunluk, 1, 100)
            oyuncu.sync_to_ref()

        for oyuncu in rakip.oyuncular:
            yorgunluk = 0.28
            if oyuncu.grup == "hucum":
                yorgunluk *= 1.05
            oyuncu.enerji = clamp(oyuncu.enerji - yorgunluk, 1, 100)
            oyuncu.sync_to_ref()

        # Rastgele duran top üretimi
        for takim in [bizim, rakip]:
            rakibi = rakip if takim is bizim else bizim
            kalite_orani = takim_taraftari_gucu(takim) / max(1.0, takim_taraftari_gucu(rakibi))
            if random.random() < clamp(0.035 * kalite_orani, 0.018, 0.065):
                topa_sahip_adaylar = [o for o in takim.oyuncular if o.grup != "kaleci"]
                top.sahip_yap(random.choice(topa_sahip_adaylar))
            if random.random() < 0.010:
                savunan = random.choice([o for o in rakibi.oyuncular if o.grup != "kaleci"])
                hucum = random.choice([o for o in takim.oyuncular if o.grup != "kaleci"])
                hucum.x = clamp((saha_sol + saha_w - 120) if takim.takim_kodu == "bizim" else (saha_sol + 120), saha_sol + 40, saha_sol + saha_w - 40)
                hucum.y = clamp(random.uniform(saha_ust + 80, saha_ust + saha_h - 80), saha_ust + 25, saha_ust + saha_h - 25)
                top.sahip_yap(hucum)
                foul_yap(savunan, hucum)
                break

        # Sakatlık kontrolü
        riskli_oyuncular = [o for o in bizim.oyuncular if o.enerji < 66 and o.ref.get("sakat_gun", 0) == 0]
        zorunlu_sakatlik = force_injury_minute and dakika == int(force_injury_minute) and not injury_callback_called
        if (riskli_oyuncular and random.random() < 0.020) or zorunlu_sakatlik:
            kurban = random.choice(riskli_oyuncular or bizim.oyuncular)
            kurban.ref["sakat_gun"] = random.randint(1, 3)
            kurban.sakat_gun = kurban.ref["sakat_gun"]
            kurban.katki -= 0.12
            injury_callback_called = True
            log_ekle(f"{dakika}' SAKATLIK! {kurban.isim} oyuna devam edemiyor.")
            try:
                mesaj_ekle("Sakatlık Haberi", f"{kurban.isim} sakatlandı ve {kurban.ref['sakat_gun']} maç sahalardan uzak kalacak.")
            except Exception:
                pass
            if callable(mac_ici_kadro):
                try:
                    _focus_open_screen(mac_ici_kadro)
                except Exception:
                    if not headless_mode:
                        raise
            takimi_yeniden_kur()
            oyunu_baslat(top.son_sahip_takim or "bizim")
            gecici_bilgi = f"Sakatlık değişikliği yapıldı: {kurban.isim}"
            gecici_bilgi_sure = 2.4

    def duraklatma_ekrani():
        nonlocal mac_ici_degisim_sayisi
        secili_index = 0
        calisiyor = True
        while calisiyor:
            _focus_begin_frame(("duraklatma",))
            dt = clock.tick(60) / 1000.0
            screen.fill(ARKA_PLAN)
            panel_ciz(WIDTH // 2 - 430, 90, 860, 520, dolgu=(18, 24, 38), cerceve=ALTIN, yaricap=22, golge=False)
            screen.blit(font_baslik.render("MAÇ DURAKLATILDI", True, ALTIN), (WIDTH // 2 - 185, 110))
            screen.blit(font_oyuncu.render("Performans, enerji ve otomatik değişiklik önerileri", True, BEYAZ), (WIDTH // 2 - 225, 154))

            oneriler = []
            for idx, oyuncu in enumerate(takimlar["bizim"].oyuncular):
                if oyuncu.performans_hesapla() < 6.1:
                    oneriler.append(("performans", idx, f"Düşük reyting: {oyuncu.isim} ({oyuncu.performans_hesapla():.1f})"))
                if oyuncu.enerji < 45:
                    oneriler.append(("enerji", idx, f"Yorgun oyuncu: {oyuncu.isim} ({oyuncu.enerji:.0f}%)"))
                if oyuncu.ref.get("sakat_gun", 0) > 0:
                    oneriler.append(("sakat", idx, f"Sakatlık riski / sakat: {oyuncu.isim}"))

            if not oneriler:
                oneriler = [("bilgi", 0, "Şu an kritik bir öneri yok. Takım dengeli görünüyor.")]
            secili_index = clamp(secili_index, 0, len(oneriler) - 1)

            for idx, oyuncu in enumerate(takimlar["bizim"].oyuncular):
                y = 195 + idx * 22
                renk = ALTIN if idx == (oneriler[secili_index][1] if oneriler and oneriler[secili_index][0] != "bilgi" else -1) else BEYAZ
                satir = f"{idx+1:02d}. {oyuncu.isim[:16]:16} | {oyuncu.mevki:3} | Rt {oyuncu.performans_hesapla():.1f} | En {oyuncu.enerji:5.1f}%"
                screen.blit(font_agac.render(satir, True, renk), (WIDTH // 2 - 385, y))

            screen.blit(font_buton.render("Öneriler", True, ALTIN), (WIDTH // 2 + 130, 188))
            for idx, oneri in enumerate(oneriler[:8]):
                renk = YESIL if idx == secili_index else BEYAZ
                screen.blit(font_agac.render(f"{idx+1}. {oneri[2]}", True, renk), (WIDTH // 2 + 25, 220 + idx * 28))

            if buton_ciz("▲", WIDTH // 2 + 345, 220, 42, 42, MAVI):
                secili_index = (secili_index - 1) % len(oneriler)
            if buton_ciz("▼", WIDTH // 2 + 345, 268, 42, 42, MAVI):
                secili_index = (secili_index + 1) % len(oneriler)

            if buton_ciz("ÖNERİYİ UYGULA", WIDTH // 2 + 20, 500, 220, 48, KIRMIZI):
                tip, oyuncu_idx, _ = oneriler[secili_index]
                if tip != "bilgi" and mac_ici_degisim_sayisi < 5:
                    yedekler = [i for i in range(11, len(kariyer_verisi["kadro"])) if kariyer_verisi["kadro"][i].get("sakat_gun", 0) == 0]
                    if yedekler:
                        hedef_idx = yedekler[0]
                        kariyer_verisi["kadro"][oyuncu_idx], kariyer_verisi["kadro"][hedef_idx] = kariyer_verisi["kadro"][hedef_idx], kariyer_verisi["kadro"][oyuncu_idx]
                        mac_ici_degisim_sayisi += 1
                        log_ekle(f"{dakika}' Değişiklik: {kariyer_verisi['kadro'][oyuncu_idx]['isim']} oyuna girdi.")
                        takimi_yeniden_kur()
                        oyunu_baslat(top.son_sahip_takim or "bizim")
                        calisiyor = False

            if buton_ciz("KADROYA GİT", WIDTH // 2 - 120, 500, 120, 48, MAVI):
                try:
                    _focus_open_screen(mac_ici_kadro)
                except Exception:
                    if not headless_mode:
                        raise
                takimi_yeniden_kur()
                oyunu_baslat(top.son_sahip_takim or "bizim")
                calisiyor = False

            if buton_ciz("KAPAT", WIDTH // 2 + 260, 500, 120, 48, YESIL):
                calisiyor = False

            _focus_publish(("duraklatma",))
            for e in _focus_events():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    calisiyor = False

            draw_focus_indicator(screen)
            pygame.display.flip()

    def maci_tamamla(sonraki_durum):
        for i, p in enumerate(kariyer_verisi["kadro"]):
            if p.get("sakat_gun", 0) > 0:
                p["sakat_gun"] -= 1
            if p.get("transfer_listesinde", False) and p.get("teklif_suresi", 0) > 0:
                p["teklif_suresi"] -= 1
            if i < 11:
                p["enerji"] = min(100, p.get("enerji", 100) + 35)
                oyuncuya_mac_isle(p, p.get("canli_performans", 6.0), kendi_takimim["ad"])
            else:
                p["enerji"] = min(100, p.get("enerji", 100) + 50)

        for p in tum_oyuncu_havuzunu_olustur():
            if p.get("ceza_maci", 0) > 0:
                p["ceza_maci"] -= 1
                if p["ceza_maci"] == 0:
                    p["son_durum"] = "Cezanız bitti, tekrar teklif yapabilirsiniz."

        for rp in rakip_ilk_onbir:
            onceki_gol, onceki_asist = rakip_mac_oncesi_katki.get(id(rp), (0, 0))
            mac_golu = max(0, rp.get("gol", 0) - onceki_gol)
            mac_asisti = max(0, rp.get("asist", 0) - onceki_asist)
            rating = 5.9 + ((rp.get("yetenek", 70) - 70) * 0.03) + random.uniform(-0.5, 0.5) + mac_golu * 1.10 + mac_asisti * 0.65 + (0.4 if s_rak > s_biz else (0.1 if s_rak == s_biz else -0.1))
            oyuncuya_mac_isle(rp, rating, rakip_adi)

        diger_maclari_simule_et([kendi_takimim["ad"], rakip_adi])
        puan_biz = 3 if s_biz > s_rak else (1 if s_biz == s_rak else 0)
        puan_rakip = 3 if s_rak > s_biz else (1 if s_rak == s_biz else 0)

        if s_biz > s_rak:
            kariyer_verisi["taktik_ustaligi"][aktif_taktik] = ustalik_seviyesi + 1

        if is_avrupa:
            ucl_mac_sonucunu_isle(s_biz, s_rak, rakip_adi)
        else:
            kendi_takimim["p"] += puan_biz
            for k in KULUPLER:
                if k["ad"] == rakip_adi:
                    k["p"] += puan_rakip
                    break
            digerleri = [k for k in KULUPLER if k["ad"] != kendi_takimim["ad"] and k["ad"] != rakip_adi]
            random.shuffle(digerleri)
            for i in range(0, len(digerleri) - 1, 2):
                t1, t2 = digerleri[i], digerleri[i + 1]
                sans = random.random()
                if sans > 0.45:
                    t1["p"] += 3
                elif sans < 0.25:
                    t2["p"] += 3
                else:
                    t1["p"] += 1
                    t2["p"] += 1
            kariyer_verisi["oynanan_mac"] = kariyer_verisi.get("oynanan_mac", 0) + 1

        toplam_sahip = takimlar["bizim"].possession_seconds + takimlar["rakip"].possession_seconds
        bizim_sahip = 50.0 if toplam_sahip <= 0 else round(takimlar["bizim"].possession_seconds / toplam_sahip * 100.0, 2)
        rakip_sahip = round(100.0 - bizim_sahip, 2)
        mac_istatistikleri = {
            "pas": takimlar["bizim"].istatistikler["pas"],
            "sut": takimlar["bizim"].istatistikler["sut"],
            "kurtaris": takimlar["bizim"].istatistikler["kurtaris"],
            "top_kaybi": takimlar["bizim"].istatistikler["top_kaybi"],
            "penalti": takimlar["bizim"].istatistikler["penalti"],
            "frikik": takimlar["bizim"].istatistikler["frikik"],
            "bizim": dict(takimlar["bizim"].istatistikler, topa_sahip_yuzde=bizim_sahip),
            "rakip": dict(takimlar["rakip"].istatistikler, topa_sahip_yuzde=rakip_sahip),
        }

        son_mac_bilgisi = {
            "bizim_takim": kendi_takimim["ad"],
            "rakip": rakip_adi,
            "bizim_skor": s_biz,
            "rakip_skor": s_rak,
            "bizim_gol_dakikalari": bizim_gol_dakikalari[:],
            "rakip_gol_dakikalari": rakip_gol_dakikalari[:],
            "gec_gol_yedik": any(dk >= 80 for dk in rakip_gol_dakikalari),
            "gec_gol_attik": any(dk >= 80 for dk in bizim_gol_dakikalari),
            "ilk_yari_gol_yedik": any(dk <= 20 for dk in rakip_gol_dakikalari),
            "ilk_yari_gol_attik": any(dk <= 20 for dk in bizim_gol_dakikalari),
            "fark": s_biz - s_rak,
            "mac_turu": mac_baslik.strip(),
            "galibiyet": s_biz > s_rak,
            "beraberlik": s_biz == s_rak,
            "maglubiyet": s_biz < s_rak,
            "gol_yedik": s_rak > 0,
            "gol_attik": s_biz > 0,
            "clean_sheet": s_rak == 0,
            "mac_olayi_sayisi": len(logs),
            "istatistikler": mac_istatistikleri,
            "sonuc_ozeti": f"{kendi_takimim['ad']} {s_biz}-{s_rak} {rakip_adi}",
        }
        kariyer_verisi["son_mac_bilgisi"] = son_mac_bilgisi
        kariyer_verisi["genel_mac_index"] = kariyer_verisi.get("genel_mac_index", 0) + 1
        if s_biz > s_rak:
            yorum = "galip geldi"
        elif s_biz == s_rak:
            yorum = "berabere kaldı"
        else:
            yorum = "mağlup oldu"
        mesaj_ekle("Maç Sonucu", f"{kendi_takimim['ad']}, {rakip_adi} karşısında {s_biz}-{s_rak} {yorum}.")
        if kariyer_verisi.get("oynanan_mac", 0) >= 30:
            return "sezon_bitti"
        return sonraki_durum

    oyunu_baslat("bizim")

    while True:
        _focus_begin_frame(("mac", match_over, devre_arasi_animasyonu, devre_arasi_mesaji))
        dt = clock.tick(60) / 1000.0
        screen.fill(ARKA_PLAN)
        for e in _focus_events():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        if top.sahip:
            possession_last_team = top.sahip.takim_kodu
            takimlar[possession_last_team].possession_seconds += dt
        elif possession_last_team in takimlar:
            takimlar[possession_last_team].possession_seconds += dt * 0.35

        skorboard_ciz()
        takim_paneli_ciz(takimlar["bizim"], 20, 135, MAVI)
        takim_paneli_ciz(takimlar["rakip"], WIDTH - 255, 135, KIRMIZI)
        saha_ciz()
        # [YENI] Mevki renk lejandi (canli mac, skorbordu) saginda)
        mevki_lejandi_ciz(screen, 1005, 74, olcek=0.62, baslik=False, kisa=True)

        if not match_over:
            takim_pozisyonlarini_guncelle(takimlar["bizim"], takimlar["rakip"], dt)
            takim_pozisyonlarini_guncelle(takimlar["rakip"], takimlar["bizim"], dt)

            if devre_arasi_animasyonu:
                devre_anim_timer += dt
                tunel_x = saha_sol + saha_w / 2
                tunel_y = saha_ust - 28
                for takim in takimlar.values():
                    for oyuncu in takim.oyuncular:
                        oyuncu.hedef_x = lerp(oyuncu.hedef_x, tunel_x + random.uniform(-40, 40), 0.04)
                        oyuncu.hedef_y = lerp(oyuncu.hedef_y, tunel_y, 0.04)
                        oyuncu.hedefe_yuru(dt)
                if devre_anim_timer > 2.0:
                    devre_arasi_animasyonu = False
                    devre_arasi_mesaji = True
                    devre_anim_timer = 0.0
            elif devre_arasi_mesaji:
                devre_anim_timer += dt
                panel_ciz(WIDTH // 2 - 270, HEIGHT // 2 - 70, 540, 140, dolgu=SIYAH, cerceve=ALTIN, yaricap=18, golge=False)
                m1 = font_baslik.render("İLK YARI BİTTİ", True, ALTIN)
                m2 = font_liste.render("Oyuncular ikinci yarı için sahaya dönüyor...", True, BEYAZ)
                screen.blit(m1, m1.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 18)))
                screen.blit(m2, m2.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 24)))
                if devre_anim_timer > 2.0:
                    ikinci_yari_basladi = True
                    dakika = max(dakika, 46)
                    oyunu_baslat("rakip")
                    log_ekle("46' İkinci yarı başladı!")
                    devre_arasi_mesaji = False
                    devre_anim_timer = 0.0
            else:
                if top.sahip:
                    action_cooldown -= dt
                    sahibi = top.sahip
                    if action_cooldown <= 0:
                        oyuncu_aksiyonu_ver(sahibi)
                        action_cooldown = random.uniform(0.28, 0.55)
                else:
                    if top.guncelle(dt):
                        top_hareket_sonu_coz()

                if top.sahip:
                    yakin_rakip = en_yakin_rakip(top.sahip)
                    if yakin_rakip and mesafe(top.sahip.x, top.sahip.y, yakin_rakip.x, yakin_rakip.y) < 36:
                        top_kapma_deneme(yakin_rakip, top.sahip)

                dakika_akumulatoru += dt
                if dakika_akumulatoru >= dakika_basina_saniye:
                    dakika_akumulatoru -= dakika_basina_saniye
                    dakika += 1
                    dakika_olayi_isle()
                    if dakika == 45 and not ikinci_yari_basladi:
                        log_ekle("45' İlk yarı sona erdi. Takımlar soyunma odasına gidiyor.")
                        devre_arasi_animasyonu = True
                        devre_anim_timer = 0.0
                    if dakika >= 90:
                        match_over = True
                        if not final_state_logged:
                            log_ekle("90' Maç bitti!")
                            final_state_logged = True

        for takim in takimlar.values():
            for oyuncu in takim.oyuncular:
                oyuncu_ciz(oyuncu)
        top_ciz(top)
        olay_paneli_ciz()

        if gecici_bilgi_sure > 0:
            gecici_bilgi_sure -= dt
        else:
            gecici_bilgi = ""

        if ("mac", match_over, devre_arasi_animasyonu, devre_arasi_mesaji) != _focus_frame_context:
            _focus_begin_frame(("mac", match_over, devre_arasi_animasyonu, devre_arasi_mesaji))
        if not match_over and not devre_arasi_animasyonu and not devre_arasi_mesaji:
            if buton_ciz("KADRO / DEĞİŞİKLİK", WIDTH // 2 - 250, 590, 220, 46, MAVI):
                try:
                    _focus_open_screen(mac_ici_kadro)
                except Exception:
                    if not headless_mode:
                        raise
                takimi_yeniden_kur()
                oyunu_baslat(top.son_sahip_takim or "bizim")
                gecici_bilgi = "Kadro ekranından geri dönüldü"
                gecici_bilgi_sure = 2.0

            if buton_ciz("DURAKLAT / ÖNERİ", WIDTH // 2 + 30, 590, 220, 46, BUTON_RENGI):
                _focus_open_screen(duraklatma_ekrani)

        if match_over:
            toplam_sahip = takimlar["bizim"].possession_seconds + takimlar["rakip"].possession_seconds
            bizim_sahip = 50.0 if toplam_sahip <= 0 else round(takimlar["bizim"].possession_seconds / toplam_sahip * 100.0, 1)
            rakip_sahip = round(100.0 - bizim_sahip, 1)
            panel_ciz(WIDTH // 2 - 350, 215, 700, 190, dolgu=(8, 14, 24), cerceve=ALTIN, yaricap=20, golge=False)
            baslik = font_baslik.render(f"MAÇ SONU: {kendi_takimim['ad']} {s_biz}-{s_rak} {rakip_adi}", True, ALTIN)
            screen.blit(baslik, baslik.get_rect(center=(WIDTH // 2, 245)))
            screen.blit(font_liste.render(f"Topa sahip olma: % {bizim_sahip} - % {rakip_sahip}", True, BEYAZ), (WIDTH // 2 - 210, 285))
            ozet1 = f"Bizim: Pas {takimlar['bizim'].istatistikler['pas']}/{takimlar['bizim'].istatistikler['pas_deneme']} | Şut {takimlar['bizim'].istatistikler['sut']}/{takimlar['bizim'].istatistikler['isabet']} | Korner {takimlar['bizim'].istatistikler['korner']}"
            ozet2 = f"Rakip: Pas {takimlar['rakip'].istatistikler['pas']}/{takimlar['rakip'].istatistikler['pas_deneme']} | Şut {takimlar['rakip'].istatistikler['sut']}/{takimlar['rakip'].istatistikler['isabet']} | Korner {takimlar['rakip'].istatistikler['korner']}"
            screen.blit(font_agac.render(ozet1, True, YESIL), (WIDTH // 2 - 300, 326))
            screen.blit(font_agac.render(ozet2, True, KIRMIZI), (WIDTH // 2 - 300, 350))
            if son_yorum_satiri:
                screen.blit(font_agac.render(son_yorum_satiri[:96], True, ALTIN), (WIDTH // 2 - 300, 376))

            if auto_finish_test:
                _focus_publish(("mac", match_over, devre_arasi_animasyonu, devre_arasi_mesaji))
                draw_focus_indicator(screen)
                pygame.display.flip()
                return maci_tamamla("ana_menu")

            if buton_ciz("MAÇI BİTİR VE SONUÇLARI İŞLE", WIDTH // 2 - 340, 590, 320, 54, YESIL):
                _focus_publish(("mac", match_over, devre_arasi_animasyonu, devre_arasi_mesaji))
                draw_focus_indicator(screen)
                pygame.display.flip()
                return maci_tamamla("ana_menu")
            if buton_ciz("BASIN TOPLANTISI", WIDTH // 2 + 30, 590, 220, 54, MAVI):
                _focus_publish(("mac", match_over, devre_arasi_animasyonu, devre_arasi_mesaji))
                draw_focus_indicator(screen)
                pygame.display.flip()
                return maci_tamamla("basin_ekrani")

        _focus_publish(("mac", match_over, devre_arasi_animasyonu, devre_arasi_mesaji))
        draw_focus_indicator(screen)
        pygame.display.flip()


def sezon_sonu_ekrani():
    ballon_dor_sonucu = ballon_dor_sistemini_calistir()
    sirali_lig = sorted(KULUPLER, key=lambda x: x['p'], reverse=True)
    sampiyon = sirali_lig[0]
    ikinci = sirali_lig[1]
    ucuncu = sirali_lig[2]
    
    kendi_kulubum = kariyer_verisi["kulup"]["ad"]
    sira = 0
    for i, t in enumerate(sirali_lig):
        if t["ad"] == kendi_kulubum:
            sira = i + 1
            break

    while True:
        _focus_begin_frame(("sezon_sonu",))
        screen.fill(ARKA_PLAN)
        
        txt_baslik = font_skor.render("SEZON SONU", True, ALTIN)
        screen.blit(txt_baslik, txt_baslik.get_rect(center=(WIDTH//2, 80)))
        
        txt_samp = font_baslik.render(f"ŞAMPİYON: {sampiyon['ad'].upper()}", True, YESIL)
        screen.blit(txt_samp, txt_samp.get_rect(center=(WIDTH//2, 170)))

        if kariyer_verisi.get("ucl_tur") == "Bitti":
            ucl_sampiyonu = ucl_sampiyonunu_bul() or "Belirsiz"
            ucl_samp_txt = font_skor.render("UCL", True, ALTIN)
            screen.blit(ucl_samp_txt, ucl_samp_txt.get_rect(center=(WIDTH//2, 120)))
            ucl_detay_txt = font_liste.render(f"ŞAMPİYONLAR LİGİ ŞAMPİYONU: {ucl_sampiyonu}", True, ALTIN)
            screen.blit(ucl_detay_txt, ucl_detay_txt.get_rect(center=(WIDTH//2, 205)))

        # Avrupa Kupaları Yazıları
        ucl_txt = font_liste.render(f"1. {sampiyon['ad']} -> UEFA Champions League (UCL)", True, ALTIN)
        screen.blit(ucl_txt, (WIDTH//2 - 300, 220))
        
        uel_txt = font_liste.render(f"2. {ikinci['ad']} -> UEFA Champions League (UCL)", True, ALTIN)
        screen.blit(uel_txt, (WIDTH//2 - 300, 255))
        
        uecl_txt = font_liste.render(f"3. {ucuncu['ad']} -> Uefa Euoropa League (UEL)", True, MAVI)
        screen.blit(uecl_txt, (WIDTH//2 - 300, 290))

        lig_panel = pygame.Rect(80, 330, 500, 280)
        pygame.draw.rect(screen, BUTON_RENGI, lig_panel, border_radius=15)
        pygame.draw.rect(screen, ALTIN, lig_panel, 2, border_radius=15)
        screen.blit(font_buton.render("LİG SIRALAMASI", True, ALTIN), (lig_panel.x + 110, lig_panel.y + 12))
        for i, t in enumerate(sirali_lig[:8]):
            renk = YESIL if t["ad"] == kendi_kulubum else BEYAZ
            satir = f"{i+1}. {t['ad'][:15]} - {t['p']} Puan"
            screen.blit(font_liste.render(satir, True, renk), (lig_panel.x + 30, lig_panel.y + 55 + i*26))

        ballon_panel = pygame.Rect(700, 330, 500, 280)
        pygame.draw.rect(screen, BUTON_RENGI, ballon_panel, border_radius=15)
        pygame.draw.rect(screen, ALTIN, ballon_panel, 2, border_radius=15)
        screen.blit(font_buton.render("BALLON D'OR", True, ALTIN), (ballon_panel.x + 145, ballon_panel.y + 12))

        if ballon_dor_sonucu:
            kazanan_satiri = f"Kazanan: {metni_kisalt(ballon_dor_sonucu['kazanan_isim'], 22)}"
            screen.blit(font_liste.render(kazanan_satiri, True, YESIL), (ballon_panel.x + 24, ballon_panel.y + 58))
            detay_satiri = f"Kulüp: {metni_kisalt(ballon_dor_sonucu['kulup'], 20)} | Puan: {ballon_dor_sonucu['puan']}"
            screen.blit(font_oyuncu.render(detay_satiri, True, BEYAZ), (ballon_panel.x + 26, ballon_panel.y + 94))

            if ballon_dor_sonucu.get("rastgele_secim"):
                esik_txt = f"Yakın puan farkı nedeniyle random seçim kullanıldı (%{ballon_dor_sonucu['fark_yuzde']})"
                screen.blit(font_oyuncu.render(esik_txt, True, MAVI), (ballon_panel.x + 24, ballon_panel.y + 122))
            else:
                screen.blit(font_oyuncu.render("Kazanan tamamen performans puanına göre otomatik seçildi.", True, BEYAZ), (ballon_panel.x + 24, ballon_panel.y + 122))

            for i, aday in enumerate(ballon_dor_sonucu.get("adaylar", [])[:5]):
                satir = f"{i+1}. {metni_kisalt(aday['isim'], 16)} | {metni_kisalt(aday['kulup'], 12)} | {aday['puan']}"
                screen.blit(font_oyuncu.render(satir, True, BEYAZ if i else ALTIN), (ballon_panel.x + 26, ballon_panel.y + 162 + i*22))
        else:
            screen.blit(font_liste.render("Bu sezon için Ballon d'Or sonucu üretilemedi.", True, BEYAZ), (ballon_panel.x + 30, ballon_panel.y + 100))

        # --- YENİ SEZONA BAŞLA BUTONU ---
        if buton_ciz("YENİ SEZONA BAŞLA", WIDTH//2-200, 630, 400, 65, YESIL):
            prim = 100 if sira == 1 else (60 if sira == 2 else (30 if sira == 3 else 10))
            kariyer_verisi["kulup"]["butce"] += prim
            kariyer_verisi["sezon_gelir"] = kariyer_verisi.get("sezon_gelir", 0) + prim
            
            # --- AVRUPA KULÜPLERİNİ YENİ SEZON İÇİN GÜNCELLE ---
            ucl_yeni_sezon_kuluplerini_olustur([t["ad"] for t in KULUPLER], [sampiyon["ad"], ikinci["ad"]])

            # Kendi takımımız ilk 2'deyse Avrupa biletini al
            kariyer_verisi["avrupa_lig_katilim"] = (sira <= 2)

            # Her şeyi yeni sezon için sıfırla
            for k in KULUPLER:
                k["p"] = 0
            ucl_yeni_sezonu_sifirla()

            kariyer_verisi["gun"] = 1
            kariyer_verisi["oynanan_mac"] = 0

            # Oyuncuların yaşını tek kaynaktan ve bir kez ilerlet.
            tum_oyuncu_havuzu = tum_oyuncu_havuzunu_olustur()
            orijinal_yasi_olanlar = {id(p) for p in tum_oyuncu_havuzu if "yas" in p}
            for p in kariyer_verisi["kadro"]:
                p["enerji"] = 100
                p["sakat_gun"] = 0
            for p in tum_oyuncu_havuzu:
                p["yas"] = p.get("yas", 20) + 1

            # --- ANTRENMAN KOÇU BONUSU HESAPLAMA ---
            koc_seviyesi = 0
            for uye in kariyer_verisi.get("teknik_ekip", []):
                # Ekipteki Antrenör ve Yardımcıları bulup seviyelerini topluyoruz
                if uye.get("rol", "") in ["Antrenman Koçu", "Antrenör", "Yardımcı Antrenör"]:
                    koc_seviyesi += uye.get("seviye", 0)

            # Koçun yeteneklerine göre hesaplanan oranlar:
            sans_bonusu = koc_seviyesi * 0.05       # Gelişim ihtimalini artırır (Örn: Lvl 4 -> %20)
            ekstra_yetenek = koc_seviyesi // 2      # Alınan reyting artışına direkt bonus (Lvl 4 -> +2 ekstra puan)
            dusus_engeli = koc_seviyesi * 0.04      # Yaşlıların düşüş ihtimalini azaltır (Lvl 4 -> %16 koruma)
            # ----------------------------------------

            # --- YENİ EKLENTİ: GELİŞİM, DÜŞÜŞ VE EMEKLİLİK SİSTEMİ ---
            emekli_olanlar = []
            for p in tum_oyuncu_havuzu:
                # Sadece en başta (kodunda) özel olarak "yas" verisi girilmiş oyuncular bu döngüye girer
                if id(p) in orijinal_yasi_olanlar:
                    yas = p["yas"]
                    
                    # 1. Emeklilik (35 yaş ve üzeri için %30 ihtimalle futbolu bırakma)
                    if yas >= 35 and random.random() < 0.30:
                        emekli_olanlar.append(p)
                        continue
                        
                    # Oyuncu KENDİ kadromuzdaysa koç bonusundan faydalanır, rakipteyse faydalanamaz!
                    bizim_oyuncu = (p in kariyer_verisi["kadro"])
                    
                    # 2. Yetenek ve Değer Değişimleri
                    if yas < 24:
                        g_sans = 0.70 + (sans_bonusu if bizim_oyuncu else 0)
                        if random.random() < g_sans: # Koç varsa daha sık gelişir
                            artis = random.randint(1, 3) + (ekstra_yetenek if bizim_oyuncu else 0)
                            p["yetenek"] = min(99, p.get("yetenek", 70) + artis)
                            p["deger"] = p.get("deger", 5) + (artis * 2)
                            
                    elif 24 <= yas <= 29:
                        z_sans = 0.30 + (sans_bonusu if bizim_oyuncu else 0)
                        if random.random() < z_sans: # Zirve yaşı, koç varsa potansiyeli uzar
                            artis = 1 + (1 if bizim_oyuncu and ekstra_yetenek > 0 else 0)
                            p["yetenek"] = min(99, p.get("yetenek", 70) + artis)
                            p["deger"] = p.get("deger", 5) + (artis * 2)
                            
                    elif yas >= 30:
                        d_sans = 0.60 - (dusus_engeli if bizim_oyuncu else 0)
                        if random.random() < d_sans: # Koç varsa daha zor reyting düşer
                            dusus = random.randint(1, 2)
                            # Koç seviyesi >= 4 ise yaşlılar asla 2 düşmez, en fazla 1 düşer
                            if bizim_oyuncu and koc_seviyesi >= 4:
                                dusus = 1
                                
                            p["yetenek"] = max(40, p.get("yetenek", 70) - dusus)
                            p["deger"] = max(1, p.get("deger", 5) - (dusus * 1.5))
                            
            # Emekli olan oyuncuları bütün listelerden temizle
            for ep in emekli_olanlar:
                oyuncuyu_koleksiyonlardan_cikar(ep)
            # ----------------------------------------------------------

            sezonluk_istatistikleri_sifirla()
            kariyer_verisi["sezon"] = kariyer_verisi.get("sezon", 2027) + 1

            return "ana_menu"

        _focus_publish(("sezon_sonu",))
        for e in _focus_events():
            if e.type == pygame.QUIT: pygame.quit(); sys.exit()
        draw_focus_indicator(screen)
        pygame.display.flip()



# --- TAKTİK VE KADRO YARDIMCI DEĞİŞKENLERİ ---
secili_degisim_id = -1
son_tiklama_zamani = 0
tiklanan_oyuncu_id = -1
# --- TAKTİK YARDIMCI EKRANI ---
def taktik_ayarlar_ekrani():
    """6 gerçek dünya taktiğinin seçildiği ekran."""
    gercek_taktikler = [
        {"ad": "Gegenpressing", "desc": "Yoğun pres ve hızlı şok hücumlar."},
        {"ad": "Tiki-Taka", "desc": "Kısa paslarla oyuna hükmetme."},
        {"ad": "Catenaccio", "desc": "Adam adama markaj ve katı savunma."},
        {"ad": "Otobüsü Çek", "desc": "Tamamen savunma, geçit vermez yapı."},
        {"ad": "Uzun Top", "desc": "Defanstan forvete direkt paslar."},
        {"ad": "Total Futbol", "desc": "Akıcı pozisyonlar ve tam saha baskı."}
    ]
    
    if "aktif_taktik" not in kariyer_verisi:
        kariyer_verisi["aktif_taktik"] = "Gegenpressing"

    while True:
        _focus_begin_frame(("taktik",))
        screen.fill(ARKA_PLAN)
        # Panel
        pygame.draw.rect(screen, BUTON_RENGI, (WIDTH//2 - 400, 50, 800, 620), border_radius=20)
        pygame.draw.rect(screen, ALTIN, (WIDTH//2 - 400, 50, 800, 620), 3, border_radius=20)
        
        baslik = font_baslik.render("STRATEJİK TAKTİK MERKEZİ", True, ALTIN)
        screen.blit(baslik, (WIDTH//2 - baslik.get_width()//2, 70))

        for i, taktik in enumerate(gercek_taktikler):
            sutun = i % 2
            satir = i // 2
            x = WIDTH//2 - 380 + (sutun * 390)
            y = 150 + (satir * 140)
            kutu_rect = pygame.Rect(x, y, 370, 120)
            is_selected = kariyer_verisi["aktif_taktik"] == taktik["ad"]
            
            kart_renk = YESIL if is_selected else SIYAH
            pygame.draw.rect(screen, kart_renk, kutu_rect, border_radius=10)
            pygame.draw.rect(screen, BEYAZ, kutu_rect, 2, border_radius=10)
            
            t_ad = font_buton.render(taktik["ad"], True, ALTIN if not is_selected else SIYAH)
            t_desc = font_oyuncu.render(taktik["desc"], True, BEYAZ if not is_selected else SIYAH)
            screen.blit(t_ad, (x + 15, y + 15))
            screen.blit(t_desc, (x + 15, y + 65))

            if _focus_polled_click(kutu_rect, pygame.mouse.get_pressed()[0] and kutu_rect.collidepoint(pygame.mouse.get_pos())):
                kariyer_verisi["aktif_taktik"] = taktik["ad"]
                pygame.time.delay(100)

        if buton_ciz("KADROYA DÖN", WIDTH//2 - 150, 600, 300, 50, MAVI):
            return

        _focus_publish(("taktik",))
        for e in _focus_events():
            if e.type == pygame.QUIT: pygame.quit(); sys.exit()
        draw_focus_indicator(screen)
        pygame.display.flip()
def kadro_ekrani():
    global durum, son_tiklama_zamani, tiklanan_oyuncu_id

    sekme = "SAHA"
    secili = -1
    uyari_mesaji = ""
    uyari_suresi = 0
    dizilisler = ["4-3-3", "4-4-2", "3-5-2"]

    if "dizilis_idx" not in kariyer_verisi:
        kariyer_verisi["dizilis_idx"] = 0
    if "aktif_taktik" not in kariyer_verisi:
        kariyer_verisi["aktif_taktik"] = "Gegenpressing"

    saha_rect = pygame.Rect(140, 95, 670, 500)
    sag_panel = pygame.Rect(830, 95, 420, 500)
    alt_bilgi_rect = pygame.Rect(20, 610, 1230, 85)

    pos_433 = [(95, 250), (230, 90), (230, 185), (230, 315), (230, 410), (390, 145), (390, 250), (390, 355), (545, 120), (565, 250), (545, 380)]
    pos_442 = [(95, 250), (230, 90), (230, 185), (230, 315), (230, 410), (390, 120), (390, 220), (390, 320), (390, 420), (560, 185), (560, 315)]
    pos_352 = [(95, 250), (240, 145), (240, 250), (240, 355), (405, 95), (405, 175), (405, 250), (405, 325), (405, 405), (565, 185), (565, 315)]

    def aktif_pozisyonlari_getir():
        aktif = dizilisler[kariyer_verisi["dizilis_idx"]]
        if aktif == "4-3-3":
            return aktif, pos_433
        if aktif == "4-4-2":
            return aktif, pos_442
        return aktif, pos_352

    def oyuncu_durumu(indeks, oyuncu):
        if indeks < 11:
            bolge = "İLK 11"
        elif indeks < 18:
            bolge = "YEDEK"
        else:
            bolge = "REZERV"
        if oyuncu.get("sakat_gun", 0) > 0:
            bolge += f" | SAKAT {oyuncu.get('sakat_gun', 0)}"
        else:
            bolge += " | HAZIR"
        return bolge

    def otomatik_kadro_diz():
        nonlocal uyari_mesaji, uyari_suresi
        kadro = kariyer_verisi["kadro"]
        mevcut_idx = kariyer_verisi.get("dizilis_idx", 0) % len(dizilisler)
        sonuc = en_iyi_formasyon_ve_ilk11(kadro, mevcut_idx)
        if sonuc is None:
            # 11'den az oyuncu: eski davranis
            saglam = sorted([o for o in kadro if o.get("sakat_gun", 0) <= 0], key=lambda x: x.get("yetenek", 0), reverse=True)
            sakat = sorted([o for o in kadro if o.get("sakat_gun", 0) > 0], key=lambda x: x.get("yetenek", 0), reverse=True)
            kariyer_verisi["kadro"] = saglam + sakat
            return
        yeni_idx, ilk11, unlem = sonuc
        secilenler = {id(o) for o in ilk11}
        kalan = [o for o in kadro if id(o) not in secilenler]
        kalan = sorted(kalan, key=lambda x: (x.get("sakat_gun", 0) > 0, -x.get("yetenek", 0)))
        kariyer_verisi["kadro"] = ilk11 + kalan
        if yeni_idx != mevcut_idx:
            kariyer_verisi["dizilis_idx"] = yeni_idx
            uyari_mesaji = f"DİZİLİŞ {dizilisler[yeni_idx]} YAPILDI (MEVKİ DIŞI YOK)"
        elif unlem > 0:
            uyari_mesaji = f"{unlem} MEVKİ İÇİN UYGUN OYUNCU YOK!"
        else:
            uyari_mesaji = "EN İYİ İLK 11 KURULDU"
        uyari_suresi = 90

    def guvenli_degistir(a, b):
        nonlocal secili, uyari_mesaji, uyari_suresi
        if a == -1 or b == -1 or a == b:
            return
        kadro = kariyer_verisi["kadro"]
        if (a < 11 and kadro[b].get("sakat_gun", 0) > 0) or (b < 11 and kadro[a].get("sakat_gun", 0) > 0):
            uyari_mesaji = "SAKAT OYUNCUYU İLK 11'E ALAMAZSIN!"
            uyari_suresi = 75
            secili = -1
            return
        kadro[a], kadro[b] = kadro[b], kadro[a]
        secili = -1

    def oyuncu_etkilesimi(indeks, tiklama_rect):
        nonlocal secili, uyari_mesaji, uyari_suresi
        if not _focus_polled_click(tiklama_rect, pygame.mouse.get_pressed()[0] and tiklama_rect.collidepoint(mouse_pos)):
            return

        simdiki_zaman = pygame.time.get_ticks()
        oyuncu = kariyer_verisi["kadro"][indeks]
        if indeks == tiklanan_oyuncu_id and simdiki_zaman - son_tiklama_zamani < 320:
            _focus_open_screen(oyuncu_detay_ekrani, oyuncu)
            secili = -1
        else:
            if secili != -1 and secili != indeks:
                guvenli_degistir(secili, indeks)
            else:
                secili = -1 if secili == indeks else indeks

        globals()["tiklanan_oyuncu_id"] = indeks
        globals()["son_tiklama_zamani"] = simdiki_zaman
        pygame.time.delay(140)

    while True:
        _focus_begin_frame(("kadro", sekme, kariyer_verisi["dizilis_idx"] if sekme == "SAHA" else None))
        screen.fill(ARKA_PLAN)
        mouse_pos = pygame.mouse.get_pos()
        aktif_dizilis, aktif_pos_list = aktif_pozisyonlari_getir()
        aktif_taktik = kariyer_verisi["aktif_taktik"]
        yedekler = list(enumerate(kariyer_verisi["kadro"][11:18], start=11))
        rezervler = list(enumerate(kariyer_verisi["kadro"][18:], start=18))

        pygame.draw.rect(screen, BUTON_RENGI, (0, 0, WIDTH, 78))
        pygame.draw.line(screen, ALTIN, (0, 78), (WIDTH, 78), 3)

        if buton_ciz("SAHA", 20, 16, 130, 45, MAVI if sekme == "SAHA" else BUTON_RENGI):
            sekme = "SAHA"
        if buton_ciz("LİSTE", 160, 16, 130, 45, MAVI if sekme == "LISTE" else BUTON_RENGI):
            sekme = "LISTE"
        if buton_ciz("GERİ", 1110, 16, 140, 45, KIRMIZI):
            sakat_var_mi = any(p.get("sakat_gun", 0) > 0 for p in kariyer_verisi["kadro"][:11])
            if sakat_var_mi:
                uyari_mesaji = "İLK 11'DE SAKAT OYUNCU VAR! LÜTFEN DEĞİŞTİR."
                uyari_suresi = 90
            else:
                return "ana_menu"

        baslik = font_baslik.render(f"KADRO MERKEZİ | {kariyer_verisi['kulup']['ad']}", True, ALTIN)
        screen.blit(baslik, (320, 16))

        pygame.draw.rect(screen, BUTON_RENGI, (20, 95, 105, 500), border_radius=18)
        pygame.draw.rect(screen, ALTIN, (20, 95, 105, 500), 2, border_radius=18)

        if buton_ciz("TAKTİK", 30, 120, 85, 78, YESIL):
            _focus_open_screen(taktik_ayarlar_ekrani)
        if buton_ciz(aktif_dizilis, 30, 220, 85, 78, ALTIN):
            kariyer_verisi["dizilis_idx"] = (kariyer_verisi["dizilis_idx"] + 1) % len(dizilisler)
            pygame.time.delay(140)
        if buton_ciz("OTO DİZ", 30, 320, 85, 78, MAVI):
            otomatik_kadro_diz()
            secili = -1
            pygame.time.delay(140)
        if buton_ciz("DETAY", 30, 420, 85, 78, BUTON_RENGI):
            if 0 <= secili < len(kariyer_verisi["kadro"]):
                _focus_open_screen(oyuncu_detay_ekrani, kariyer_verisi["kadro"][secili])
                secili = -1
            else:
                uyari_mesaji = "ÖNCE BİR OYUNCU SEÇ."
                uyari_suresi = 60

        if uyari_suresi > 0:
            uyari_surface = font_oyuncu.render(uyari_mesaji, True, KIRMIZI)
            screen.blit(uyari_surface, (835, 66))
            uyari_suresi -= 1

        if sekme == "SAHA":
            pygame.draw.rect(screen, SAHA_YESILI, saha_rect, border_radius=22)
            pygame.draw.rect(screen, BEYAZ, saha_rect, 3, border_radius=22)

            for sira in range(7):
                renk = (32, 124, 42) if sira % 2 == 0 else (38, 150, 47)
                pygame.draw.rect(screen, renk, (saha_rect.x, saha_rect.y + sira * (saha_rect.height // 7), saha_rect.width, (saha_rect.height // 7) + 2))
            pygame.draw.line(screen, BEYAZ, (saha_rect.x + saha_rect.width // 2, saha_rect.y + 15), (saha_rect.x + saha_rect.width // 2, saha_rect.y + saha_rect.height - 15), 3)
            pygame.draw.circle(screen, BEYAZ, saha_rect.center, 55, 3)
            pygame.draw.rect(screen, BEYAZ, (saha_rect.x + 5, saha_rect.y + 140, 95, 220), 3, border_radius=8)
            pygame.draw.rect(screen, BEYAZ, (saha_rect.right - 100, saha_rect.y + 140, 95, 220), 3, border_radius=8)
            pygame.draw.rect(screen, BEYAZ, (saha_rect.x + 5, saha_rect.y + 195, 38, 110), 3, border_radius=6)
            pygame.draw.rect(screen, BEYAZ, (saha_rect.right - 43, saha_rect.y + 195, 38, 110), 3, border_radius=6)

            # [YENI] Mevki renk lejandi (Kadro Merkezi > SAHA, cimin sol ustu)
            mevki_lejandi_ciz(screen, saha_rect.x + 8, saha_rect.y + 4)

            for i in range(min(11, len(kariyer_verisi["kadro"]))):
                oyuncu = kariyer_verisi["kadro"][i]
                rel_x, rel_y = aktif_pos_list[i]
                x = saha_rect.x + rel_x
                y = saha_rect.y + rel_y
                halka_renk = ALTIN if secili == i else BEYAZ
                if oyuncu.get("sakat_gun", 0) > 0:
                    halka_renk = KIRMIZI

                click_rect = pygame.Rect(x - 36, y - 40, 128, 90)
                pygame.draw.circle(screen, halka_renk, (x, y), 24)
                pygame.draw.circle(screen, SIYAH, (x, y), 20)
                no_txt = font_oyuncu.render(str(i + 1), True, BEYAZ)
                screen.blit(no_txt, no_txt.get_rect(center=(x, y)))

                bilgi_rect = pygame.Rect(x + 18, y - 13, 78, 28)
                pygame.draw.rect(screen, BUTON_RENGI, bilgi_rect, border_radius=8)
                pygame.draw.rect(screen, halka_renk, bilgi_rect, 2, border_radius=8)
                bilgi_txt = font_oyuncu.render(f"{oyuncu.get('mevki', '??')} {oyuncu.get('yetenek', 0)}", True, BEYAZ)
                screen.blit(bilgi_txt, bilgi_txt.get_rect(center=bilgi_rect.center))

                isim_panel = pygame.Rect(x - 42, y + 30, 105, 24)
                pygame.draw.rect(screen, (12, 24, 35), isim_panel, border_radius=8)
                isim_txt = font_oyuncu.render(oyuncu["isim"][:11], True, BEYAZ)
                screen.blit(isim_txt, isim_txt.get_rect(center=isim_panel.center))

                if oyuncu.get("sakat_gun", 0) > 0:
                    sakat_txt = font_oyuncu.render(f"{oyuncu['sakat_gun']} maç", True, KIRMIZI)
                    screen.blit(sakat_txt, (x - 26, y + 56))

                # [YENI] Mevki uyumsuzlugu uyarisi (Kadro Merkezi / SAHA)
                if not is_natural_position(oyuncu, _dizilis_slot_mevkisi(aktif_dizilis, i)):
                    draw_position_warning(screen, (x, y), 24)

                oyuncu_etkilesimi(i, click_rect)

            pygame.draw.rect(screen, BUTON_RENGI, sag_panel, border_radius=20)
            pygame.draw.rect(screen, ALTIN, sag_panel, 2, border_radius=20)

            yedek_baslik = font_buton.render("YEDEKLER", True, ALTIN)
            rezerv_baslik = font_buton.render("REZERVLER", True, ALTIN)
            screen.blit(yedek_baslik, (sag_panel.x + 18, sag_panel.y + 15))
            screen.blit(rezerv_baslik, (sag_panel.x + 18, sag_panel.y + 265))

            def sag_kartlari_ciz(kaynak, bas_y, bos_mesaj):
                if not kaynak:
                    bos_txt = font_oyuncu.render(bos_mesaj, True, BEYAZ)
                    screen.blit(bos_txt, (sag_panel.x + 20, bas_y + 20))
                    return
                for sira, (gercek_indeks, oyuncu) in enumerate(kaynak):
                    col = sira % 2
                    row = sira // 2
                    kart = pygame.Rect(sag_panel.x + 18 + col * 195, bas_y + row * 56, 185, 46)
                    renk = ALTIN if secili == gercek_indeks else (70, 110, 155)
                    if oyuncu.get("sakat_gun", 0) > 0:
                        renk = KIRMIZI
                    pygame.draw.rect(screen, renk, kart, border_radius=10)
                    pygame.draw.rect(screen, BEYAZ, kart, 1, border_radius=10)
                    ust = font_oyuncu.render(f"{gercek_indeks + 1}. {oyuncu['isim'][:12]}", True, BEYAZ)
                    alt = font_oyuncu.render(f"{oyuncu.get('mevki', '??')} | GÜÇ {oyuncu.get('yetenek', 0)}", True, BEYAZ)
                    screen.blit(ust, (kart.x + 8, kart.y + 5))
                    screen.blit(alt, (kart.x + 8, kart.y + 24))
                    oyuncu_etkilesimi(gercek_indeks, kart)

            sag_kartlari_ciz(yedekler, sag_panel.y + 55, "Yedek kulübesi boş.")
            sag_kartlari_ciz(rezervler, sag_panel.y + 305, "Rezerv oyuncu yok.")

        else:
            liste_panel = pygame.Rect(140, 95, 760, 500)
            istatistik_panel = pygame.Rect(915, 95, 335, 500)
            liste_baslik_font = pygame.font.SysFont("Arial", 17, bold=True)
            istatistik_font = pygame.font.SysFont("Arial", 16, bold=True)

            pygame.draw.rect(screen, BUTON_RENGI, liste_panel, border_radius=20)
            pygame.draw.rect(screen, ALTIN, liste_panel, 2, border_radius=20)
            pygame.draw.rect(screen, (24, 39, 58), istatistik_panel, border_radius=20)
            pygame.draw.rect(screen, ALTIN, istatistik_panel, 2, border_radius=20)

            alt_aciklama = font_oyuncu.render("Tek tık: seç / değiştir   |   Çift tık: oyuncu detay ekranı", True, BEYAZ)
            screen.blit(alt_aciklama, (liste_panel.x + 20, liste_panel.y + 16))

            liste_baslik = font_oyuncu.render("KADRO LİSTESİ", True, ALTIN)
            screen.blit(liste_baslik, (liste_panel.x + 20, liste_panel.y + 46))

            sol_kolon_x = liste_panel.x + 20
            sag_kolon_x = liste_panel.x + 385
            kart_genislik = 355
            kart_yukseklik = 34
            kart_baslangic_y = liste_panel.y + 82
            kart_bosluk = 36

            for i, oyuncu in enumerate(kariyer_verisi["kadro"]):
                col = 0 if i < 11 else 1
                row = i if i < 11 else i - 11
                kart_x = sol_kolon_x if col == 0 else sag_kolon_x
                kart = pygame.Rect(kart_x, kart_baslangic_y + row * kart_bosluk, kart_genislik, kart_yukseklik)
                renk = ALTIN if secili == i else (46, 64, 83)
                if oyuncu.get("sakat_gun", 0) > 0:
                    renk = (130, 45, 45)
                pygame.draw.rect(screen, renk, kart, border_radius=8)
                pygame.draw.rect(screen, BEYAZ, kart, 1, border_radius=8)

                bolge = "İ11" if i < 11 else ("YDK" if i < 18 else "RZV")
                enerji = int(oyuncu.get("enerji", 100))
                satir = f"{i + 1:>2}. {oyuncu['isim'][:12]:12} {oyuncu.get('mevki', '??'):>3} G:{oyuncu.get('yetenek', 0):>2} E:{enerji:>3}% {bolge}"
                txt = liste_baslik_font.render(satir, True, BEYAZ)
                screen.blit(txt, (kart.x + 8, kart.y + 8))
                oyuncu_etkilesimi(i, kart)

            istatistik_baslik = font_oyuncu.render("TAKIM İSTATİSTİKLERİ", True, ALTIN)
            screen.blit(istatistik_baslik, (istatistik_panel.x + 18, istatistik_panel.y + 16))

            istatistik_alt = pygame.font.SysFont("Arial", 14, bold=False).render("Gol > Asist önceliğiyle tüm kadro", True, BEYAZ)
            screen.blit(istatistik_alt, (istatistik_panel.x + 18, istatistik_panel.y + 42))

            baslik_y = istatistik_panel.y + 76
            pygame.draw.line(screen, ALTIN, (istatistik_panel.x + 16, baslik_y + 24), (istatistik_panel.right - 16, baslik_y + 24), 1)
            screen.blit(istatistik_font.render("#", True, ALTIN), (istatistik_panel.x + 18, baslik_y))
            screen.blit(istatistik_font.render("OYUNCU", True, ALTIN), (istatistik_panel.x + 45, baslik_y))
            screen.blit(istatistik_font.render("G", True, ALTIN), (istatistik_panel.right - 74, baslik_y))
            screen.blit(istatistik_font.render("A", True, ALTIN), (istatistik_panel.right - 40, baslik_y))

            istatistikli_kadro = takim_istatistik_siralamasi(kariyer_verisi["kadro"])
            satir_y = baslik_y + 34
            satir_h = 17

            for idx, oyuncu in enumerate(istatistikli_kadro):
                arka = (38, 55, 76) if idx % 2 == 0 else (31, 47, 66)
                if idx < 3 and (oyuncu.get("gol", 0) > 0 or oyuncu.get("asist", 0) > 0):
                    arka = (78, 62, 22)
                satir_rect = pygame.Rect(istatistik_panel.x + 14, satir_y - 2, istatistik_panel.width - 28, satir_h + 6)
                pygame.draw.rect(screen, arka, satir_rect, border_radius=7)

                screen.blit(istatistik_font.render(str(idx + 1), True, BEYAZ), (istatistik_panel.x + 20, satir_y))
                screen.blit(istatistik_font.render(metni_kisalt(oyuncu["isim"], 16), True, BEYAZ), (istatistik_panel.x + 45, satir_y))
                screen.blit(istatistik_font.render(str(oyuncu.get("gol", 0)), True, BEYAZ), (istatistik_panel.right - 74, satir_y))
                screen.blit(istatistik_font.render(str(oyuncu.get("asist", 0)), True, BEYAZ), (istatistik_panel.right - 40, satir_y))

                satir_y += 21

        pygame.draw.rect(screen, BUTON_RENGI, alt_bilgi_rect, border_radius=16)
        pygame.draw.rect(screen, ALTIN, alt_bilgi_rect, 2, border_radius=16)

        if 0 <= secili < len(kariyer_verisi["kadro"]):
            secili_oyuncu = kariyer_verisi["kadro"][secili]
            bilgi = f"SEÇİLİ: {secili_oyuncu['isim']} | {secili_oyuncu.get('mevki', '??')} | GÜÇ {secili_oyuncu.get('yetenek', 0)} | {oyuncu_durumu(secili, secili_oyuncu)}"
        else:
            bilgi = "İpucu: Bir oyuncuyu tek tıklayıp başka oyuncuya tıklarsan yer değiştirir. Çift tıklarsan detay ekranı açılır."
        bilgi_surface = font_liste.render(bilgi, True, BEYAZ)
        screen.blit(bilgi_surface, (35, 640))

        _focus_publish(("kadro", sekme, kariyer_verisi["dizilis_idx"] if sekme == "SAHA" else None))
        for e in _focus_events():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        draw_focus_indicator(screen)
        pygame.display.flip()

# --- ANA KADRO EKRANI ---


def oyuncu_detay_ekrani(p):
    yuz_resmi = None
    dosya_adi = p.get("face")

    # --- TÜM KLASÖRLERİ TARAYARAK FOTOĞRAFI BULMA ---
    if dosya_adi:
        bulunan_yol = None
        # Mevcut dizinden başlayarak tüm alt klasörleri (os.walk) tarar
        for kok, dizinler, dosyalar in os.walk("."):
            if dosya_adi in dosyalar:
                bulunan_yol = os.path.join(kok, dosya_adi)
                break  # Dosya bulundu, aramayı durdur
        
        if bulunan_yol:
            try:
                # Resmi yükle ve detay ekranına uygun boyuta getir
                yuklenen_resim = pygame.image.load(bulunan_yol).convert_alpha()
                yuz_resmi = pygame.transform.scale(yuklenen_resim, (160, 160))
            except:
                yuz_resmi = None

    while True:
        _focus_begin_frame(("oyuncu_detay",))
        screen.fill(ARKA_PLAN)
        
        # Oyuncu Kartı (Senin dosmandaki ölçülere göre)
        pygame.draw.rect(screen, BUTON_RENGI, (WIDTH//2 - 250, 70, 500, 580), border_radius=20)
        pygame.draw.rect(screen, ALTIN, (WIDTH//2 - 250, 70, 500, 580), 3, border_radius=20)
        
        # Oyuncu Adı
        txt_ad = font_baslik.render(p.get('isim', 'BİLİNMİYOR').upper(), True, ALTIN)
        screen.blit(txt_ad, (WIDTH//2 - txt_ad.get_width()//2, 110))
        
        ulke = p.get('ulke') or 'Bilinmiyor'
        screen.blit(font_oyuncu.render(f"Ülke: {ulke}", True, BEYAZ), (WIDTH//2 - 220, 180))
        _dm = diger_mevkiler_getir(p)
        screen.blit(font_oyuncu.render("Diğer: " + (", ".join(_dm) if _dm else "-"), True, ALTIN),
                    (WIDTH//2 + 50, 180))

        # --- FOTOĞRAF ÇİZİMİ ---
        # Fotoğrafı kartın sağ tarafına istatistiklerin yanına yerleştiriyoruz
        foto_x, foto_y = WIDTH//2 + 50, 220
        if yuz_resmi:
            screen.blit(yuz_resmi, (foto_x, foto_y))
            pygame.draw.rect(screen, ALTIN, (foto_x - 5, foto_y - 5, 170, 170), 2, border_radius=10)
        else:
            # Fotoğraf bulunamazsa siyah bir kutu ve yazı göster
            pygame.draw.rect(screen, SIYAH, (foto_x, foto_y, 160, 160), border_radius=10)
            txt_yok = font_oyuncu.render("FOTO BULUNAMADI", True, BEYAZ)
            screen.blit(txt_yok, (foto_x + 10, foto_y + 70))

        # Oyuncu Bilgileri (Dosyandaki verilere tam uyumlu)
        oyuncu_sezon_verisini_hazirla(p)
        bilgiler = [
            f"MEVKİ: {p.get('mevki', '??')}",
            f"YETENEK: {p.get('yetenek', 0)}",
            f"YAŞ: {p.get('yas', '??')}",
            f"MAÇ: {p.get('mac', 0)}",
            f"GOL: {p.get('gol', 0)}",
            f"ASİST: {p.get('asist', 0)}",
            f"ORT. RATING: {p.get('ortalama_rating', 0.0):.2f}",
            f"MORAL: {p.get('moral', 50)}",
            f"POPÜLERLİK: {p.get('populerlik', 50)}",
            f"BALLON D'OR: {p.get('ballon_dor_sayisi', 0)}",
            f"ENERJİ: %{int(p.get('enerji', 100))}",
            f"SAKAT: {p.get('sakat_gun', 0)} GÜN"
        ]

        for i, metin in enumerate(bilgiler[:8]):
            txt = font_buton.render(metin, True, BEYAZ)
            screen.blit(txt, (WIDTH//2 - 220, 220 + (i * 41)))

        alt_bilgiler = bilgiler[8:]
        for i, metin in enumerate(alt_bilgiler):
            txt = font_oyuncu.render(metin, True, ALTIN if "BALLON" in metin else BEYAZ)
            screen.blit(txt, (WIDTH//2 - 220, 550 + (i * 24)))

        oduller = p.get('oduller', [])[-2:]
        for i, odul in enumerate(oduller):
            txt = font_oyuncu.render(metni_kisalt(odul, 34), True, ALTIN)
            screen.blit(txt, (WIDTH//2 + 10, 410 + (i * 26)))

        # Geri Dön Butonu
        if buton_ciz("GERİ DÖN", WIDTH//2 - 125, 660, 250, 50, KIRMIZI):
            return
        
        _focus_publish(("oyuncu_detay",))
        for e in _focus_events():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        
        draw_focus_indicator(screen)
        pygame.display.flip()








def transfer_ekrani():
    global transfer_index, transfer_sekme

    kart_x, kart_w = 40, 1200
    kart_h, kart_bosluk = 92, 14
    ust_baslangic = 165
    gorunur_sayi = 5

    while True:
        _focus_begin_frame(("transfer", transfer_sekme))
        screen.fill(ARKA_PLAN)
        butce = kariyer_verisi["kulup"].get("butce", 0)
        kendi_kulup_adi = kariyer_verisi["kulup"]["ad"]

        panel_ciz(20, 15, WIDTH - 40, 120, dolgu=(24, 37, 58), cerceve=ALTIN, yaricap=24)
        screen.blit(font_baslik.render("TRANSFER MERKEZİ", True, BEYAZ), (45, 35))
        screen.blit(font_oyuncu.render("Daha aydın, daha səliqəli və daha rahat bazarlıq görünüşü", True, (205, 220, 235)), (48, 82))

        butce_panel = panel_ciz(930, 28, 170, 54, dolgu=(18, 28, 42), cerceve=(90, 170, 255), yaricap=16, golge=False)
        screen.blit(font_buton.render(f"{butce}M$", True, ALTIN), (butce_panel.x + 22, butce_panel.y + 10))
        screen.blit(font_oyuncu.render("BÜDCƏ", True, (180, 200, 220)), (butce_panel.x + 23, butce_panel.y + 34))

        if buton_ciz("ALIŞ BAZARI", 45, 105, 210, 44, MAVI if transfer_sekme == "AL" else BUTON_RENGI):
            transfer_sekme = "AL"
            transfer_index = 0
            pygame.time.delay(120)
        if buton_ciz("SATIŞ / KADRO", 270, 105, 230, 44, MAVI if transfer_sekme == "SAT" else BUTON_RENGI):
            transfer_sekme = "SAT"
            transfer_index = 0
            pygame.time.delay(120)
        if buton_ciz("ANA MENÜ", 1110, 35, 130, 50, KIRMIZI):
            return "ana_menu"

        if transfer_sekme == "AL":
            oyuncu_havuzu = tum_oyuncu_havuzunu_olustur()
            gosterilecek_liste = sorted(
                (p for p in oyuncu_havuzu if p.get("kulup") != kendi_kulup_adi),
                key=lambda oyuncu: (oyuncu.get("yetenek", 0), oyuncu.get("deger") or 0),
                reverse=True
            )
            baslik = "Alış bazarı"
            alt_baslik = "Kulüblərlə danışıqlar və teklif idarəsi"
        else:
            gosterilecek_liste = sorted(
                kariyer_verisi["kadro"],
                key=lambda oyuncu: (oyuncu.get("transfer_listesinde", False), oyuncu.get("deger", 0), oyuncu.get("yetenek", 0)),
                reverse=True
            )
            baslik = "Satış və kadro idarəsi"
            alt_baslik = "Transfer listəsi, gelen tekliflər və sərbəst buraxma"

        toplam = len(gosterilecek_liste)
        max_index = max(0, toplam - gorunur_sayi)
        transfer_index = max(0, min(transfer_index, max_index))
        liste_parcasi = gosterilecek_liste[transfer_index: transfer_index + gorunur_sayi]
        aktif_sayfa = 1 if toplam == 0 else (transfer_index // gorunur_sayi) + 1
        toplam_sayfa = max(1, (toplam + gorunur_sayi - 1) // gorunur_sayi)

        screen.blit(font_buton.render(baslik, True, BEYAZ), (45, 145))
        screen.blit(font_oyuncu.render(alt_baslik, True, (185, 205, 225)), (48, 176))
        sayfa_metin = font_oyuncu.render(f"{aktif_sayfa}/{toplam_sayfa} SƏHİFƏ  •  {toplam} OYUNCU", True, ALTIN)
        screen.blit(sayfa_metin, (WIDTH - 280, 152))

        if not liste_parcasi:
            bos_panel = panel_ciz(40, 230, 1200, 150, dolgu=(28, 42, 62), cerceve=(70, 110, 150), yaricap=20)
            screen.blit(font_buton.render("Bu bölmədə göstəriləcək oyunçu yoxdur", True, BEYAZ), (bos_panel.x + 40, bos_panel.y + 48))
            screen.blit(font_oyuncu.render("Daha sonra yenidən bax və ya digər sekməyə keç.", True, (180, 200, 220)), (bos_panel.x + 42, bos_panel.y + 90))

        for i, p in enumerate(liste_parcasi):
            y_konum = ust_baslangic + i * (kart_h + kart_bosluk)
            panel_ciz(kart_x, y_konum, kart_w, kart_h, dolgu=(31, 46, 68), cerceve=(73, 106, 141), yaricap=18)

            deger = oyuncu_transfer_degerini_belirle(p)
            isim = p.get("isim", "Bilinməyən")
            yet = p.get("yetenek", 0)
            mevki = p.get("mevki", "??")
            kulup_adi = metni_kisalt(p.get("kulup", "SERBEST"), 24)
            yas = p.get("yas", "??")

            screen.blit(font_liste.render(metni_kisalt(isim, 28), True, BEYAZ), (65, y_konum + 14))
            etiket_ciz(mevki, 355, y_konum + 14, MAVI)
            etiket_ciz(f"GÜÇ {yet}", 430, y_konum + 14, YESIL, SIYAH)
            etiket_ciz(f"YAŞ {yas}", 525, y_konum + 14, (120, 90, 200))
            etiket_ciz(f"DƏYƏR {deger}M$", 610, y_konum + 14, (190, 135, 25))
            screen.blit(font_oyuncu.render(f"Kulüp: {kulup_adi}", True, (195, 215, 235)), (66, y_konum + 56))

            if transfer_sekme == "AL":
                p.setdefault("teklif_miktari", max(1, deger))
                p.setdefault("teklif_hakki", 3)
                p.setdefault("ceza_maci", 0)
                p.setdefault("son_durum", "Teklif gözlənilir")

                teklif = max(1, p["teklif_miktari"])
                p["teklif_miktari"] = teklif
                hak = p["teklif_hakki"]
                ceza = p["ceza_maci"]
                durum_mesaji = p["son_durum"]

                durum_renk = ALTIN if "gözlənilir" in durum_mesaji.lower() or "bekleniyor" in durum_mesaji.lower() else (KIRMIZI if "redded" in durum_mesaji.lower() or "masa" in durum_mesaji.lower() else YESIL)
                screen.blit(font_oyuncu.render(f"Durum: {metni_kisalt(durum_mesaji, 54)}", True, durum_renk), (260, y_konum + 56))
                etiket_ciz(f"HAQ {hak}", 1095, y_konum + 14, (70, 78, 104))

                if ceza > 0:
                    kilit_rect = pygame.Rect(830, y_konum + 22, 340, 42)
                    pygame.draw.rect(screen, (110, 45, 45), kilit_rect, border_radius=14)
                    pygame.draw.rect(screen, KIRMIZI, kilit_rect, 2, border_radius=14)
                    kilit_yazi = font_oyuncu.render(f"GÖRÜŞMƏLƏR DONUB • {ceza} MAÇ", True, BEYAZ)
                    screen.blit(kilit_yazi, kilit_yazi.get_rect(center=kilit_rect.center))
                else:
                    if buton_ciz("-", 805, y_konum + 20, 42, 46, KIRMIZI):
                        if p["teklif_miktari"] > 1:
                            p["teklif_miktari"] -= 1
                        pygame.time.delay(90)

                    teklif_rect = pygame.Rect(857, y_konum + 20, 118, 46)
                    pygame.draw.rect(screen, (18, 28, 42), teklif_rect, border_radius=14)
                    pygame.draw.rect(screen, ALTIN, teklif_rect, 2, border_radius=14)
                    teklif_txt = font_buton.render(f"{p['teklif_miktari']}M$", True, ALTIN)
                    screen.blit(teklif_txt, teklif_txt.get_rect(center=teklif_rect.center))

                    if buton_ciz("+", 985, y_konum + 20, 42, 46, YESIL):
                        p["teklif_miktari"] += 1
                        pygame.time.delay(90)

                    teklif = p["teklif_miktari"]
                    if butce >= teklif:
                        if buton_ciz("TEKLİF", 1040, y_konum + 20, 150, 46, MAVI):
                            p["teklif_hakki"] -= 1
                            oran = teklif / max(1, deger)
                            if oran >= 1.0:
                                sans = 100
                            elif oran >= 0.8:
                                sans = int((oran - 0.5) * 200)
                            elif oran >= 0.5:
                                sans = int((oran - 0.4) * 50)
                            else:
                                sans = 0

                            zar = random.randint(1, 100)
                            if zar <= sans:
                                kariyer_verisi["kulup"]["butce"] -= teklif
                                kariyer_verisi["sezon_gider"] = kariyer_verisi.get("sezon_gider", 0) + teklif
                                oyuncuyu_kulube_tasi(p, kendi_kulup_adi)
                                p.update({"enerji": 100, "deger": deger, "gol": 0, "sakat_gun": 0})
                                mesaj_ekle("Transfer Teklifi", f"{p.get('isim', 'Oyuncu')} {teklif}M$ karşılığında kadroya katıldı.")
                                pygame.time.delay(140)
                                break
                            else:
                                if p["teklif_hakki"] > 0:
                                    istenen_rakam = deger + random.randint(int(deger * 0.05), int(deger * 0.25))
                                    p["son_durum"] = f"Rədd edildi • ən az {istenen_rakam}M$ istəyirlər"
                                else:
                                    p["ceza_maci"] = 5
                                    p["teklif_hakki"] = 3
                                    p["son_durum"] = "Masadan qalxdılar • 5 maç sonra gəl"
                                pygame.time.delay(140)
                    else:
                        buton_ciz("BÜDCƏ YOX", 1040, y_konum + 20, 150, 46, KIRMIZI, focusable=False)

            else:
                listede_mi = p.get("transfer_listesinde", False)
                if listede_mi:
                    kalan_sure = p.get("teklif_suresi", 0)
                    if kalan_sure > 0:
                        etiket_ciz("LİSTƏDƏ", 785, y_konum + 14, (120, 90, 200))
                        screen.blit(font_oyuncu.render(f"Teklif gözlənilir • təxminən {kalan_sure} tur", True, ALTIN), (260, y_konum + 56))
                        if buton_ciz("SERBEST", 910, y_konum + 20, 120, 46, (100, 100, 100)):
                            oyuncuyu_kulube_tasi(p, "SERBEST")
                            p["deger"] = 0
                            oyuncu_transfer_degerini_belirle(p)
                            pygame.time.delay(110)
                            break
                        if buton_ciz("İPTAL ET", 1045, y_konum + 20, 145, 46, KIRMIZI):
                            p["transfer_listesinde"] = False
                            pygame.time.delay(110)
                    else:
                        teklif = p.get("aktif_teklif", deger)
                        talip = p.get("teklif_yapan", "Avrupa Kulübü")
                        etiket_ciz("TEKLİF VAR", 785, y_konum + 14, ALTIN, SIYAH)
                        screen.blit(font_oyuncu.render(f"{metni_kisalt(talip, 20)} kulübü {teklif}M$ təklif edir", True, ALTIN), (260, y_konum + 56))
                        if buton_ciz("REDDET", 900, y_konum + 20, 120, 46, KIRMIZI):
                            p["transfer_listesinde"] = False
                            pygame.time.delay(110)
                        if buton_ciz("KABUL", 1040, y_konum + 20, 150, 46, YESIL):
                            kariyer_verisi["kulup"]["butce"] += teklif
                            kariyer_verisi["sezon_gelir"] = kariyer_verisi.get("sezon_gelir", 0) + teklif
                            mesaj_ekle("Transfer Satışı", f"{p.get('isim', 'Oyuncu')}, {talip} kulübüne {teklif}M$ karşılığında satıldı.")
                            oyuncuyu_kulube_tasi(p, talip)
                            p["deger"] = deger
                            pygame.time.delay(110)
                            break
                else:
                    screen.blit(font_oyuncu.render("Oyuncu şu anda transfer listəsində deyil", True, (180, 200, 220)), (260, y_konum + 56))
                    if len(kariyer_verisi["kadro"]) > 11:
                        if buton_ciz("SERBEST", 900, y_konum + 20, 120, 46, (100, 100, 100)):
                            oyuncuyu_kulube_tasi(p, "SERBEST")
                            p["deger"] = 0
                            oyuncu_transfer_degerini_belirle(p)
                            pygame.time.delay(110)
                            break
                        if buton_ciz("LİSTEYE EKLE", 1040, y_konum + 20, 150, 46, MAVI):
                            p["transfer_listesinde"] = True
                            p["teklif_suresi"] = random.randint(1, 7)
                            p["aktif_teklif"] = max(1, round(deger + random.randint(-5, 5), 1))
                            rakip_listesi = ["Galatasaray", "Fenerbahçe", "Beşiktaş", "Real Madrid", "Bayern", "Barcelona", "Liverpool", "PSG", "Inter", "Milan", "Juventus", "Ajax", "Sporting", "Napoli"]
                            p["teklif_yapan"] = random.choice([k for k in rakip_listesi if k != kendi_kulup_adi])
                            pygame.time.delay(110)
                    else:
                        etiket_ciz("MIN 11 OYUNCU", 980, y_konum + 20, KIRMIZI)

        if transfer_index > 0:
            if buton_ciz("ÖNCƏKİ", 40, 685, 150, 28, MAVI):
                transfer_index = max(0, transfer_index - gorunur_sayi)
                pygame.time.delay(100)
        if transfer_index + gorunur_sayi < toplam:
            if buton_ciz("SONRAKI", 1090, 685, 150, 28, MAVI):
                transfer_index = min(max_index, transfer_index + gorunur_sayi)
                pygame.time.delay(100)

        _focus_publish(("transfer", transfer_sekme))
        for e in _focus_events():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        draw_focus_indicator(screen)
        pygame.display.flip()

def metni_satirlara_bol(metin, font, max_width):
    kelimeler = str(metin).split()
    if not kelimeler:
        return [""]

    satirlar = []
    aktif = kelimeler[0]
    for kelime in kelimeler[1:]:
        deneme = aktif + " " + kelime
        if font.size(deneme)[0] <= max_width:
            aktif = deneme
        else:
            satirlar.append(aktif)
            aktif = kelime
    satirlar.append(aktif)
    return satirlar


def cok_satirli_metin_ciz(yuzey, metin, font, renk, rect, satir_boslugu=4, ortala=False, dikey_ortala=True, max_satir=None):
    satirlar = metni_satirlara_bol(metin, font, max(40, rect.width - 20))
    satir_yuksekligi = font.get_height() + satir_boslugu
    if max_satir is None:
        max_satir = max(1, rect.height // max(1, satir_yuksekligi))

    cizilecek = satirlar[:max_satir]
    toplam_yukseklik = max(1, len(cizilecek)) * satir_yuksekligi - satir_boslugu
    if dikey_ortala:
        bas_y = rect.y + max(8, (rect.height - toplam_yukseklik) // 2)
    else:
        bas_y = rect.y + 8

    for i, satir in enumerate(cizilecek):
        txt = font.render(satir, True, renk)
        if ortala:
            x = rect.x + (rect.width - txt.get_width()) // 2
        else:
            x = rect.x + 10
        yuzey.blit(txt, (x, bas_y + i * satir_yuksekligi))


def memnunluk_renk(deger):
    if deger >= 70:
        return YESIL
    if deger >= 45:
        return ALTIN
    return KIRMIZI


def memnunluk_bar_ciz(baslik, deger, x, y, w, h):
    deger = max(0, min(100, int(deger)))
    pygame.draw.rect(screen, (24, 34, 52), (x, y, w, h), border_radius=12)
    pygame.draw.rect(screen, BEYAZ, (x, y, w, h), 2, border_radius=12)

    ic_marj = 4
    dolu_w = int((w - ic_marj * 2) * (deger / 100))
    pygame.draw.rect(screen, memnunluk_renk(deger), (x + ic_marj, y + ic_marj, dolu_w, h - ic_marj * 2), border_radius=10)

    txt_baslik = font_oyuncu.render(baslik, True, BEYAZ)
    txt_deger = font_oyuncu.render(f"%{deger}", True, SIYAH if deger >= 45 else BEYAZ)
    screen.blit(txt_baslik, (x + 10, y - 22))
    screen.blit(txt_deger, (x + w - txt_deger.get_width() - 10, y + (h - txt_deger.get_height()) // 2))


def basin_soru_sayisi_hesapla():
    taraftar = kariyer_verisi.get("taraftar_memnunluk", kariyer_verisi.get("taraftar", 50))
    if taraftar < 30:
        return 4
    if taraftar < 55:
        return 3
    if taraftar < 80:
        return 2
    return 1


def son_maca_uygun_sorular_uret():
    son_mac = kariyer_verisi.get("son_mac_bilgisi", {})
    bizim_skor = son_mac.get("bizim_skor", 0)
    rakip_skor = son_mac.get("rakip_skor", 0)
    rakip = son_mac.get("rakip", "rakip")
    takim = son_mac.get("bizim_takim", kariyer_verisi.get("kulup", {}).get("ad", "Takım"))
    taraftar = kariyer_verisi.get("taraftar_memnunluk", kariyer_verisi.get("taraftar", 50))

    sorular = []

    if son_mac.get("gec_gol_yedik"):
        sorular.append({
            "kategori": "mac_sonu",
            "soru": "80+ dakikalarda yediyiniz gol oyunun gedişatına nece tesir etdi?",
            "secenekler": [
                {"metin": "Son anlarda fokus itirdik, bunu düzeltmek benim sorumluluğumdur.", "etki": {"taraftar": 5, "takim": 2, "yonetim": 1}},
                {"metin": "Bu tamamilə uğursuz andı, komandanın ümumi oyunundan yenə də razıyam.", "etki": {"taraftar": -2, "takim": 3, "yonetim": 0}}
            ]
        })

    if son_mac.get("gec_gol_attik"):
        sorular.append({
            "kategori": "mac_sonu",
            "soru": "Son dəqiqələrdə vurduğunuz qol komandanın xarakterini göstərdimi?",
            "secenekler": [
                {"metin": "Bəli, bu komanda son saniyəyə qədər oyundan qopmur.", "etki": {"taraftar": 6, "takim": 4, "yonetim": 2}},
                {"metin": "Sevindirik, amma bunu hər matçda daha erkən göstərməliyik.", "etki": {"taraftar": 3, "takim": 2, "yonetim": 1}}
            ]
        })

    if son_mac.get("maglubiyet"):
        sorular.append({
            "kategori": "netice",
            "soru": f"{rakip} qarşısında alınan {bizim_skor}-{rakip_skor} məğlubiyyəti necə şərh edərsiniz?",
            "secenekler": [
                {"metin": "Azarkeşdən üzr istəyirik, bu nəticə bizim standartımıza uyğun deyil.", "etki": {"taraftar": 7, "takim": -1, "yonetim": 2}},
                {"metin": "Bəzən belə gecələr olur, dərhal toparlanıb cavab verəcəyik.", "etki": {"taraftar": 2, "takim": 2, "yonetim": 0}}
            ]
        })
    elif son_mac.get("beraberlik"):
        sorular.append({
            "kategori": "netice",
            "soru": f"{rakip} ilə heç-heçəni itirilmiş 2 xal kimi görürsünüz?",
            "secenekler": [
                {"metin": "Bəli, oyunun bəzi hissələrində qalib gələcək imkanları qaçırdıq.", "etki": {"taraftar": 4, "takim": 1, "yonetim": 0}},
                {"metin": "Bəzi anlarda risk etmədik, amma 1 xalın da dəyəri var.", "etki": {"taraftar": 0, "takim": 2, "yonetim": 1}}
            ]
        })
    else:
        sorular.append({
            "kategori": "netice",
            "soru": f"{rakip} üzərindəki {bizim_skor}-{rakip_skor} qələbədə əsas fərq nə oldu?",
            "secenekler": [
                {"metin": "Oyuna planlı başladıq və azarkeşə layiq reaksiya verdik.", "etki": {"taraftar": 5, "takim": 3, "yonetim": 2}},
                {"metin": "Meydanda intizam və birlik bizi qələbəyə apardı.", "etki": {"taraftar": 4, "takim": 4, "yonetim": 1}}
            ]
        })

    if son_mac.get("clean_sheet"):
        sorular.append({
            "kategori": "savunma",
            "soru": "Bu gün qol yeməməyiniz müdafiədə yeni balans tapdığınızı göstərir?",
            "secenekler": [
                {"metin": "Müdafiədə kollektiv olaraq çox doğru mövqe aldıq.", "etki": {"taraftar": 4, "takim": 3, "yonetim": 1}},
                {"metin": "Hələ ideal deyilik, amma doğru istiqamətdə gedirik.", "etki": {"taraftar": 2, "takim": 2, "yonetim": 1}}
            ]
        })

    if bizim_skor == 0:
        sorular.append({
            "kategori": "hucum",
            "soru": "Bu gün hücum xəttinizin susqun qalması sizi nə qədər narahat edir?",
            "secenekler": [
                {"metin": "Bitiricilikdə zəif idik, bunu məşqlərdə dərhal işləyəcəyik.", "etki": {"taraftar": 4, "takim": -1, "yonetim": 1}},
                {"metin": "Futbolda belə matçlar olur, panikaya ehtiyac yoxdur.", "etki": {"taraftar": -2, "takim": 2, "yonetim": 0}}
            ]
        })

    if son_mac.get("fark", 0) >= 2:
        sorular.append({
            "kategori": "ustunluk",
            "soru": "Fərqli qələbədən sonra komandanın özünəinamının artdığını düşünürsünüz?",
            "secenekler": [
                {"metin": "Bəli, amma ayaqlarımız yenə də yerdə qalmalıdır.", "etki": {"taraftar": 4, "takim": 3, "yonetim": 2}},
                {"metin": "Özünəinam yaxşıdır, əsas məsələ bunu davam etdirməkdir.", "etki": {"taraftar": 3, "takim": 2, "yonetim": 2}}
            ]
        })

    if taraftar < 45:
        sorular.append({
            "kategori": "taraftar",
            "soru": f"{takim} azarkeşinin narazılığı artıb. Onlara bu gecə nə demək istərdiniz?",
            "secenekler": [
                {"metin": "Onların narahatlığını anlayıram, cavabı meydanda verəcəyik.", "etki": {"taraftar": 8, "takim": 1, "yonetim": 1}},
                {"metin": "Tənqid futbolun bir hissəsidir, komanda təzyiqə hazırdır.", "etki": {"taraftar": -3, "takim": 2, "yonetim": 0}}
            ]
        })
    else:
        sorular.append({
            "kategori": "taraftar",
            "soru": "Azarkeş dəstəyi bu gün sizə nə verdi?",
            "secenekler": [
                {"metin": "Enerjini tribunadan aldıq, bu dəstək bizim üçün çox dəyərlidir.", "etki": {"taraftar": 5, "takim": 2, "yonetim": 1}},
                {"metin": "Azarkeş həmişə güc verir, bu birlik davam etməlidir.", "etki": {"taraftar": 4, "takim": 2, "yonetim": 1}}
            ]
        })

    sorular.append({
        "kategori": "yonetim",
        "soru": "Bugünkü oyundan sonra rəhbərliyə hansı mesajı verirsiniz?",
        "secenekler": [
            {"metin": "Bu layihəyə inanmağa davam etsinlər, komanda doğru yoldadır.", "etki": {"taraftar": 2, "takim": 2, "yonetim": 5}},
            {"metin": "Daha da yaxşısını istəyirəm, birlikdə çıtanı yüksəldəcəyik.", "etki": {"taraftar": 3, "takim": 3, "yonetim": 4}}
        ]
    })

    random.shuffle(sorular)
    return sorular


def basin_secenek_butonu(rect, metin, renk, hover, etiket):
    zemin = hover and (min(255, renk[0] + 25), min(255, renk[1] + 25), min(255, renk[2] + 25)) or renk
    pygame.draw.rect(screen, zemin, rect, border_radius=16)
    pygame.draw.rect(screen, BEYAZ, rect, 2, border_radius=16)
    etiket_txt = font_buton.render(etiket, True, ALTIN)
    screen.blit(etiket_txt, (rect.x + 14, rect.y + 8))
    metin_rect = pygame.Rect(rect.x + 18, rect.y + 35, rect.width - 36, rect.height - 45)
    cok_satirli_metin_ciz(screen, metin, font_oyuncu, BEYAZ, metin_rect, satir_boslugu=4, ortala=True, dikey_ortala=True, max_satir=4)


def basin_toplantisi_ekrani():
    global durum

    kariyer_verisi.setdefault("performans", 50)
    kariyer_verisi.setdefault("taraftar_memnunluk", kariyer_verisi.get("taraftar", 50))
    kariyer_verisi.setdefault("takim_memnunluk", 55)
    kariyer_verisi.setdefault("yonetim_memnunluk", 50)

    soru_havuzu = son_maca_uygun_sorular_uret()
    if not soru_havuzu:
        soru_havuzu = [
            {
                "kategori": "genel",
                "soru": "Bu matçdan sonra komandanız üçün əsas nəticə nə oldu?",
                "secenekler": [
                    {"metin": "Müsbət məqamları qoruyub səhvləri düzəldəcəyik.", "etki": {"taraftar": 3, "takim": 2, "yonetim": 1}},
                    {"metin": "Daha çox işləməliyik və bunu gizlətmirik.", "etki": {"taraftar": 4, "takim": 1, "yonetim": 2}}
                ]
            }
        ]

    toplam_soru = min(max(1, basin_soru_sayisi_hesapla()), min(4, len(soru_havuzu)))
    aktif_sorular = soru_havuzu[:toplam_soru]
    soru_index = 0
    etki_mesaji = ""
    cevap_verildi = False
    toplanti_bitti = False

    baslik_font = pygame.font.SysFont("Arial", 28, bold=True)
    soru_font = pygame.font.SysFont("Arial", 24, bold=True)

    while True:
        _focus_begin_frame(("basin", soru_index, cevap_verildi))
        if BASIN_FOTO:
            screen.blit(BASIN_FOTO, (0, 0))
        else:
            screen.fill(ARKA_PLAN)

        ust_panel = pygame.Surface((WIDTH, 112), pygame.SRCALPHA)
        ust_panel.fill((10, 18, 28, 185))
        screen.blit(ust_panel, (0, 0))

        bar_w = 360
        memnunluk_bar_ciz("TARAFTAR MEMNUNLUK SEVİYYESİ", kariyer_verisi.get("taraftar_memnunluk", 50), 40, 34, bar_w, 22)
        memnunluk_bar_ciz("TAKIM MEMNUNLUK SEVİYYESİ", kariyer_verisi.get("takim_memnunluk", 50), 460, 34, bar_w, 22)
        memnunluk_bar_ciz("YÖNETİM MEMNUNLUK SEVİYYESİ", kariyer_verisi.get("yonetim_memnunluk", 50), 880, 34, bar_w, 22)

        txt_baslik = baslik_font.render("MAÇ SONU BASIN TOPLANTISI", True, ALTIN)
        screen.blit(txt_baslik, (WIDTH // 2 - txt_baslik.get_width() // 2, 72))

        soru_no = font_oyuncu.render(f"SUAL {min(soru_index + 1, toplam_soru)} / {toplam_soru}", True, BEYAZ)
        screen.blit(soru_no, (WIDTH - soru_no.get_width() - 35, 10))

        soru_rect = pygame.Rect(WIDTH // 2 - 270, 142, 540, 122)
        soru_bg = pygame.Surface((soru_rect.width, soru_rect.height), pygame.SRCALPHA)
        soru_bg.fill((255, 255, 255, 215))
        screen.blit(soru_bg, soru_rect.topleft)
        pygame.draw.rect(screen, ALTIN, soru_rect, 3, border_radius=18)

        pygame.draw.polygon(screen, (255, 255, 255), [(610, 264), (670, 264), (640, 300)])
        pygame.draw.lines(screen, ALTIN, False, [(610, 264), (640, 300), (670, 264)], 3)

        aktif_soru = aktif_sorular[soru_index]
        soru_yazi_rect = pygame.Rect(soru_rect.x + 16, soru_rect.y + 12, soru_rect.width - 32, soru_rect.height - 24)
        cok_satirli_metin_ciz(screen, aktif_soru["soru"], soru_font, SIYAH, soru_yazi_rect, satir_boslugu=4, ortala=True, dikey_ortala=True, max_satir=4)

        sol_rect = pygame.Rect(110, 500, 430, 126)
        sag_rect = pygame.Rect(740, 500, 430, 126)
        mouse_pos = pygame.mouse.get_pos()

        if not cevap_verildi and not toplanti_bitti:
            basin_secenek_butonu(sol_rect, aktif_soru["secenekler"][0]["metin"], BUTON_RENGI, sol_rect.collidepoint(mouse_pos), "A")
            basin_secenek_butonu(sag_rect, aktif_soru["secenekler"][1]["metin"], BUTON_RENGI, sag_rect.collidepoint(mouse_pos), "B")
            _focus_event_button(sol_rect)
            _focus_event_button(sag_rect)
        else:
            sonuc_panel = pygame.Surface((760, 96), pygame.SRCALPHA)
            sonuc_panel.fill((12, 22, 36, 210))
            screen.blit(sonuc_panel, (260, 502))
            pygame.draw.rect(screen, ALTIN, (260, 502, 760, 96), 2, border_radius=16)
            cok_satirli_metin_ciz(screen, etki_mesaji, font_oyuncu, BEYAZ, pygame.Rect(276, 514, 728, 70), satir_boslugu=5, ortala=True, dikey_ortala=True, max_satir=3)

            buton_yazi = "NÖVBƏTİ SUAL" if (cevap_verildi and soru_index < toplam_soru - 1) else "TOPLANTINI BİTİR"
            devam_rect = pygame.Rect(WIDTH // 2 - 170, 640, 340, 56)
            pygame.draw.rect(screen, MAVI, devam_rect, border_radius=14)
            pygame.draw.rect(screen, BEYAZ, devam_rect, 2, border_radius=14)
            devam_txt = font_buton.render(buton_yazi, True, BEYAZ)
            screen.blit(devam_txt, devam_txt.get_rect(center=devam_rect.center))
            _focus_event_button(devam_rect)

        _focus_publish(("basin", soru_index, cevap_verildi))
        for event in _focus_events():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not cevap_verildi and not toplanti_bitti:
                    secilen = None
                    if sol_rect.collidepoint(event.pos):
                        secilen = aktif_soru["secenekler"][0]
                    elif sag_rect.collidepoint(event.pos):
                        secilen = aktif_soru["secenekler"][1]

                    if secilen:
                        etki = secilen.get("etki", {})
                        kariyer_verisi["taraftar_memnunluk"] = max(0, min(100, kariyer_verisi.get("taraftar_memnunluk", 50) + etki.get("taraftar", 0)))
                        kariyer_verisi["takim_memnunluk"] = max(0, min(100, kariyer_verisi.get("takim_memnunluk", 50) + etki.get("takim", 0)))
                        kariyer_verisi["yonetim_memnunluk"] = max(0, min(100, kariyer_verisi.get("yonetim_memnunluk", 50) + etki.get("yonetim", 0)))
                        kariyer_verisi["taraftar"] = kariyer_verisi["taraftar_memnunluk"]
                        kariyer_verisi["performans"] = max(0, min(100, kariyer_verisi.get("performans", 50) + etki.get("takim", 0)))
                        etki_mesaji = (
                            f"Cavab qeyd olundu. Taraftar {etki.get('taraftar', 0):+d} | "
                            f"Takım {etki.get('takim', 0):+d} | "
                            f"Yönetim {etki.get('yonetim', 0):+d}"
                        )
                        cevap_verildi = True
                        _focus_reset()

                else:
                    devam_rect = pygame.Rect(WIDTH // 2 - 170, 640, 340, 56)
                    if devam_rect.collidepoint(event.pos):
                        if soru_index < toplam_soru - 1:
                            soru_index += 1
                            cevap_verildi = False
                            _focus_reset()
                            etki_mesaji = ""
                        else:
                            toplanti_bitti = True
                            return "ana_menu"

        draw_focus_indicator(screen)
        pygame.display.flip()

# --- ANA DÖNGÜ ---
durum = "giris"
acilis_mesaji = ""
acilis_mesaj_renk = ALTIN
while True:
    if durum == "giris":
        _focus_begin_frame((durum,))
        screen.fill(ARKA_PLAN)
        screen.blit(font_skor.render("FM 2027", True, ALTIN), (WIDTH//2-200, 200))
        if acilis_mesaji:
            mesaj_yuzey = font_log.render(acilis_mesaji, True, acilis_mesaj_renk)
            screen.blit(mesaj_yuzey, (WIDTH//2 - mesaj_yuzey.get_width()//2, 320))
        if buton_ciz("OYUNA BASLA", WIDTH//2-150, 400, 300, 80, YESIL):
            acilis_mesaji = ""
            durum = "kayit"
        if kayit_var_mi():
            if buton_ciz("KAYDI YUKLE", WIDTH//2-150, 500, 300, 80, MAVI):
                basarili, mesaj = oyunu_yukle()
                acilis_mesaji = mesaj
                acilis_mesaj_renk = YESIL if basarili else KIRMIZI
                if basarili:
                    durum = "ana_menu"
        _focus_publish((durum,))
        for e in _focus_events():
            if e.type == pygame.QUIT: pygame.quit(); sys.exit()
        draw_focus_indicator(screen)
        pygame.display.flip()
    elif durum == "kayit": durum = kayit_ekrani()
    elif durum == "ana_menu": durum = ana_yonetim_paneli()
    elif durum == "kadro_ekrani": durum = kadro_ekrani()
    elif durum == "transfer_ekrani": durum = transfer_ekrani()
    elif durum == "mac_ekrani": durum = mac_ekrani()
        # Döngünün sonuna bu sətri əlavə et:
    elif durum == "sezon_bitti": durum = sezon_sonu_ekrani()
    elif durum == "gol_kralligi":
        durum = gol_kralligi_ekrani()
    elif durum == "taktik_ayarlar_ekrani":
    	durum = taktik_ayarlar_ekrani()
    elif durum == "basin_ekrani":
    	durum = basin_toplantisi_ekrani()
    elif durum == "ekip_ekrani":
    	durum = ekip_ekrani()
    elif durum == "mesajlar": durum = mesajlar_ekrani()
    elif durum == "istifa": durum = istifa_onay_ekrani()


# =============================================================================
# [YENI] MEVKI UYUMLULUGU + GORSEL UYARI SISTEMI - OZ KONTROL NOTLARI
# =============================================================================
# 1) NATURAL_POSITIONS yukaridaki kodlarla birebir aynidir:
#    KL:{KL} | CB:{CB} | LB:{LB,CB} | RB:{RB,CB} | MDO:{MDO,MO}
#    MO:{MO,MDO,MOO} | MOO:{MOO,MO,LW,RW} | LW:{LW,MOO,ST}
#    RW:{RW,MOO,ST} | ST:{ST,MOO,LW,RW}
#    -> Yeni mevki kodu URETILMEDI; DIZILIS_SLOT_MEVKILERI de yalnizca bu
#       10 kodu kullanir (saha uzerindeki slotun "hedef mevki"si).
# 2) draw_position_warning: badge_r = max(9, int(radius * 0.55))
#    yani rozet capi = radius * 1.10 -> her zaman oyuncu dairesinin
#    capindan (radius * 2) KUCUKTUR; alt sinir 9 oldugu icin kucuk
#    dairelerde (r=13) bile "!" okunur kalir.
# 3) Uyari YALNIZCA slot kodu oyuncunun dogal kumesinin disindaysa cizilir:
#    Osimhen "ST" -> CB slotunda UYARI, ST veya MOO slotunda uyari YOK.
# 4) Klavye gezinme sistemi (register_button, handle_keyboard_input,
#    _focus_*, draw_focus_indicator) HIC degistirilmedi; uyari rozeti
#    yalnizca pygame.draw / blit yapar, focus listesine dokunmaz.
# -----------------------------------------------------------------------------
# Uyari cizilen saha/11 gorunumleri:
#   A) mini_saha_ciz()            - Ana panel > Kadro sekmesi mini saha (r=13)
#   B) kadro_ekrani() / SAHA      - Kadro Merkezi saha gorunumu      (r=24)
#   C) mac_ici_kadro() / SAHA     - Mac ici kadro saha gorunumu      (r=25)
#   D) mac_ekrani() / oyuncu_ciz()- canli mac sahasi                 (r=20)
#   LİSTE sekmeleri, yedek/rezerv kartlari, transfer & detay ekranlari
#   BILEREK degistirilmedi (oyuncu zaten kendi dogal mevkisinde listelenir).
# =============================================================================
# -----------------------------------------------------------------------------
# 5) MEVKI RENK LEJANDI (mevki_lejandi_ciz)
#    Lejand sahadaki renklerle AYNI sabitlerden cizilir, ayrisamaz:
#      DOĞAL MEVKİ  : BEYAZ halka + MAVI govde  -> is_natural_position True
#      MEVKİ DIŞI   : UYARI_KIRMIZI (200,30,30) "!" rozeti, oran radius*0.55
#      SAKAT        : KIRMIZI (231,76,60) halka  -> sakat_gun > 0
#    Sayisal esik YOKTUR: uyumluluk ikili bir kumedir (NATURAL_POSITIONS),
#    bu yuzden lejantta da yuzde/bar gibi uydurma kademe gosterilmez.
#    Cagri yerleri: ana panel/Kadro, kadro_ekrani/SAHA, mac_ici_kadro/SAHA,
#    mac_ekrani/canli saha. LİSTE sekmelerinde renkli mevki isareti yok.
# =============================================================================
