# -*- coding: utf-8 -*-
"""СМЕНА (The Watch) - v3. Python + Kivy. Версия 0.1 Beta.
Графика, музыка и звук генерируются кодом, внешних файлов не нужно."""
import os, json, math, random, wave, array, threading

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.text import Label as CoreLabel
from kivy.core.audio import SoundLoader
from kivy.graphics import Color, Rectangle, Quad, Line
from kivy.graphics.texture import Texture



W, H = 480, 270          # виртуальное разрешение (пиксель-арт)
VERSION = "v0.1 Beta"
ARROW = "→"              # если вместо стрелки квадрат - замени на "->"

# ---------------------------------------------------------------- ДАННЫЕ
FIRST = ["Иван", "Пётр", "Олаф", "Ян", "Карл", "Мартин", "Антон", "Юхан",
         "Эрик", "Лев", "Артур", "Георг"]
LAST = ["Орлов", "Берг", "Лунд", "Кроль", "Видман", "Соболь", "Рейн", "Ульман",
        "Хавик", "Тарн", "Мельд", "Остин", "Фогель", "Саар", "Коваль"]
PORTS = ["Рига", "Нарва", "Таллин", "Ревель", "Выборг", "Гданьск", "Мемель",
         "Лиепая", "Хельсинки", "Турку", "Стокгольм", "Висбю", "Росток",
         "Пярну", "Ханко"]
CARGO_GROUPS = [["Треска", "Сельдь", "Салака", "Лосось"],
                ["Уголь", "Кокс", "Торф"],
                ["Пшеница", "Рожь", "Овёс", "Ячмень"],
                ["Брёвна", "Доски", "Смола"],
                ["Железо", "Соль", "Лён", "Янтарь"]]
CARGOS = [c for g in CARGO_GROUPS for c in g]

HULL_RGB = {"чёрный": (0.10, 0.10, 0.12), "тёмно-серый": (0.25, 0.26, 0.30),
            "серый": (0.50, 0.52, 0.56), "светло-серый": (0.72, 0.74, 0.78),
            "коричневый": (0.40, 0.24, 0.12), "рыжий": (0.70, 0.38, 0.12),
            "зелёный": (0.12, 0.35, 0.20), "тёмно-зелёный": (0.07, 0.22, 0.13)}
HULL_PAIRS = [("чёрный", "тёмно-серый"), ("серый", "светло-серый"),
              ("коричневый", "рыжий"), ("зелёный", "тёмно-зелёный")]
FLAG_RGB = {"красный": (0.85, 0.15, 0.15), "оранжевый": (0.95, 0.50, 0.12),
            "синий": (0.15, 0.25, 0.85), "голубой": (0.40, 0.75, 0.95),
            "зелёный": (0.15, 0.65, 0.25), "салатовый": (0.60, 0.90, 0.30),
            "жёлтый": (0.95, 0.85, 0.20), "золотой": (0.80, 0.62, 0.10)}
FLAG_PAIRS = [("красный", "оранжевый"), ("синий", "голубой"),
              ("зелёный", "салатовый"), ("жёлтый", "золотой")]


def pair_map(pairs):
    m = {}
    for a, b in pairs:
        m[a] = b
        m[b] = a
    return m


HULL_NEAR, FLAG_NEAR = pair_map(HULL_PAIRS), pair_map(FLAG_PAIRS)
FIELDS = ["captain", "cargo", "route", "masts", "hull", "flag", "number"]
LABEL = {"captain": "Капитан", "cargo": "Груз", "route": "Маршрут",
         "masts": "Мачты", "hull": "Корпус", "flag": "Флаг", "number": "Борт"}

# день: (судов, веса уровней тонкости [явное, заметное, тонкое, очень тонкое])
DAYS = {1: (10, (90, 10, 0, 0)), 2: (12, (50, 40, 10, 0)),
        3: (15, (25, 45, 25, 5)), 4: (18, (10, 40, 35, 15)),
        5: (20, (5, 25, 45, 25))}
VOICES = [150, 190, 230, 280, 340, 120]


# ---------------------------------------------------------------- ИСКАЖЕНИЯ
def mutate_vowel(word):
    vow = "аеёиоуыэюя"
    idx = [i for i, ch in enumerate(word) if i > 0 and ch in vow]
    if not idx:
        return None
    i = random.choice(idx)
    new = random.choice([v for v in "аеиоу" if v != word[i]])
    return word[:i] + new + word[i + 1:]


def swap_letters(word):
    idx = [i for i in range(1, len(word) - 1) if word[i] != word[i + 1]]
    if not idx:
        return None
    i = random.choice(idx)
    return word[:i] + word[i + 1] + word[i] + word[i + 2:]


def other_port(*exclude):
    return random.choice([p for p in PORTS if p not in exclude])


def mutate(field, val, level):
    """Возвращает искажённое значение (всегда != val)."""
    if field == "captain":
        first, last = val.split()
        if level == 1:
            return random.choice([f for f in FIRST if f != first]) + " " + \
                random.choice([l for l in LAST if l != last])
        if level == 2:
            if random.random() < 0.5:
                return random.choice([f for f in FIRST if f != first]) + " " + last
            return first + " " + random.choice([l for l in LAST if l != last])
        new = (mutate_vowel(last) if level == 3 else swap_letters(last)) \
            or mutate_vowel(last) or swap_letters(last)
        return first + " " + new
    if field == "cargo":
        gi = [i for i, g in enumerate(CARGO_GROUPS) if val in g][0]
        if level == 1:
            g = random.choice([x for i, x in enumerate(CARGO_GROUPS) if i != gi])
            return random.choice(g)
        return random.choice([c for c in CARGO_GROUPS[gi] if c != val])
    if field == "route":
        a, b = val
        if level == 1:
            na = other_port(a, b)
            return (na, other_port(a, b, na))
        if level == 2:
            if random.random() < 0.5:
                return (other_port(a, b), b)
            return (a, other_port(a, b))
        if level == 3:
            if random.random() < 0.5 and mutate_vowel(a):
                return (mutate_vowel(a), b)
            return (a, mutate_vowel(b) or other_port(a, b))
        return (b, a)
    if field == "masts":
        if level == 1:
            c = [m for m in range(1, 5) if abs(m - val) >= 2]
        else:
            c = [m for m in range(1, 5) if abs(m - val) == 1]
        return random.choice(c)
    if field in ("hull", "flag"):
        near = HULL_NEAR if field == "hull" else FLAG_NEAR
        table = HULL_RGB if field == "hull" else FLAG_RGB
        if level == 1:
            return random.choice([k for k in table if k != val and k != near[val]])
        return near[val]
    if field == "number":
        d1, d2 = divmod(val, 10)
        if level == 1:
            return random.choice([x for x in range(12, 99)
                                  if x // 10 != d1 and x % 10 != d2 and x % 11])
        if level == 2:
            return random.choice([x for x in range(1, 10) if x != d1]) * 10 + \
                random.choice([x for x in range(10) if x != d2])
        if level == 4 and d2 != 0 and d1 != d2:
            return d2 * 10 + d1
        if random.random() < 0.5:
            return random.choice([x for x in range(1, 10) if x != d1]) * 10 + d2
        return d1 * 10 + random.choice([x for x in range(10) if x != d2])
    return val


def fmt(field, val):
    if field == "route":
        return "%s %s %s" % (val[0], ARROW, val[1])
    if field == "number":
        return "№%d" % val
    return str(val)


def masts_word(n):
    return "%d %s" % (n, "мачта" if n == 1 else "мачты" if n < 5 else "мачт")


def make_day(day, hist):
    n, w = DAYS.get(day, (min(30, 22 + day - 6), (0, 10, 45, 45)))
    k = round(n * min(0.55, 0.45 + 0.02 * (day - 1)))
    flags = [True] * k + [False] * (n - k)
    random.shuffle(flags)
    names, nums, ships = set(), set(), []
    for fake in flags:
        while True:
            cap = "%s %s" % (random.choice(FIRST), random.choice(LAST))
            if cap not in names:
                names.add(cap)
                break
        while True:
            num = random.randint(12, 98)
            if num % 11 and num not in nums:
                nums.add(num)
                break
        o, d = random.sample(PORTS, 2)
        truth = dict(captain=cap, cargo=random.choice(CARGOS), route=(o, d),
                     masts=random.randint(1, 3), hull=random.choice(list(HULL_RGB)),
                     flag=random.choice(list(FLAG_RGB)), number=num)
        shown, diffs = dict(truth), []
        if fake:
            nf = 2 if (day >= 6 and random.random() < 0.5) else 1
            ban = {f for f in FIELDS
                   if len(hist) >= 2 and f in hist[-1] and f in hist[-2]}
            fields = random.sample([f for f in FIELDS if f not in ban], nf)
            hist.append(set(fields))
            for f in fields:
                lvl = random.choices([1, 2, 3, 4], weights=w)[0]
                shown[f] = mutate(f, truth[f], lvl)
                diffs.append((f, truth[f], shown[f]))
        tpl = random.choice(["Говорит %s. Груз: %s. Маршрут: %s %s %s.",
                             "Маяк, это %s. Везу: %s. Идём %s %s %s.",
                             "%s на связи. Груз — %s. Рейс %s %s %s."])
        msg = tpl % (shown["captain"], shown["cargo"].lower(),
                     shown["route"][0], ARROW, shown["route"][1])
        ships.append(dict(truth=truth, shown=shown, fake=fake, diffs=diffs,
                          msg=msg, voice=random.randrange(len(VOICES))))
    return ships


def wrap(text, n):
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > n:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines




# ---------------------------------------------------------------- ПИКСЕЛЬ-АРТ ДВИЖОК
BAY = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
WX, WY, WW, WH, HOR = 76, 22, 328, 124, 70      # окно: позиция, размер, горизонт
WLN = 118                                        # линия воды (абсолютная y)


def C(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def lc(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rgb255(c):
    return tuple(int(v * 255) for v in c)


class PX:
    def __init__(s, w, h, bg=(0, 0, 0, 0)):
        s.w, s.h = w, h
        s.b = bytearray(bytes(bg) * (w * h))
        s.tw = []

    def px(s, x, y, c, a=1.0):
        x, y = int(x), int(y)
        if 0 <= x < s.w and 0 <= y < s.h:
            i = (y * s.w + x) * 4
            b = s.b
            if a >= 0.999:
                b[i:i + 4] = bytes((c[0], c[1], c[2], 255))
            else:
                da = b[i + 3] / 255.0
                oa = a + da * (1 - a)
                if oa <= 0:
                    return
                for k in range(3):
                    b[i + k] = int((c[k] * a + b[i + k] * da * (1 - a)) / oa)
                b[i + 3] = int(oa * 255)

    def rect(s, x, y, w, h, c, a=1.0):
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(s.w, int(x + w)), min(s.h, int(y + h))
        if x1 <= x0 or y1 <= y0:
            return
        if a >= 0.999:
            row = bytes((c[0], c[1], c[2], 255)) * (x1 - x0)
            for yy in range(y0, y1):
                i = (yy * s.w + x0) * 4
                s.b[i:i + len(row)] = row
        else:
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    s.px(xx, yy, c, a)

    def clear(s, x, y, w, h):
        row = bytes(4) * w
        for yy in range(y, y + h):
            i = (yy * s.w + x) * 4
            s.b[i:i + len(row)] = row

    def line(s, x0, y0, x1, y1, c, a=1.0):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            s.px(x0, y0, c, a)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def ell(s, cx, cy, rx, ry, c, a=1.0):
        for y in range(int(cy - ry), int(cy + ry) + 1):
            dy = (y + 0.5 - cy) / ry
            if abs(dy) > 1:
                continue
            dx = rx * math.sqrt(1 - dy * dy)
            s.rect(round(cx - dx), y, round(cx + dx) - round(cx - dx), 1, c, a)

    def poly(s, pts, c, a=1.0):
        n = len(pts)
        ys = [p[1] for p in pts]
        for y in range(int(min(ys)), int(max(ys)) + 1):
            yc, xs = y + 0.5, []
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= yc < y1) or (y1 <= yc < y0):
                    xs.append(x0 + (yc - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for j in range(0, len(xs) - 1, 2):
                s.rect(round(xs[j]), y, round(xs[j + 1]) - round(xs[j]), 1, c, a)

    def vgrad(s, x, y, w, h, c0, c1, n=8):
        for yy in range(h):
            t = yy / max(1, h - 1)
            tb = t * (n - 1)
            lo = int(tb)
            fr = tb - lo
            a = bytes(lc(c0, c1, lo / (n - 1)) + (255,))
            b = bytes(lc(c0, c1, min(n - 1, lo + 1) / (n - 1)) + (255,))
            ch = b"".join(b if fr > (BAY[(y + yy) & 3][i] + 0.5) / 16 else a
                          for i in range(4))
            row = (ch * (w // 4 + 1))[:w * 4]
            i0 = ((y + yy) * s.w + x) * 4
            s.b[i0:i0 + w * 4] = row

    def glow(s, cx, cy, r, c, amax):
        for y in range(int(cy - r), int(cy + r) + 1):
            for x in range(int(cx - r), int(cx + r) + 1):
                d = math.hypot(x - cx, y - cy) / r
                if d < 1:
                    s.px(x, y, c, amax * (1 - d) ** 2)

    def speckle(s, x, y, w, h, n, c, a, rnd):
        for _ in range(n):
            s.px(x + rnd.randrange(w), y + rnd.randrange(h), c, a)


DIGITS = {"0": "111101101101111", "1": "010110010010111", "2": "111001111100111",
          "3": "111001111001111", "4": "101101111001001", "5": "111100111001111",
          "6": "111100111101111", "7": "111001001001001", "8": "111101111101111",
          "9": "111101111001111"}


def digits(p, text, x, y, sc, c):
    for ch in text:
        g = DIGITS[ch]
        for i, v in enumerate(g):
            if v == "1":
                p.rect(x + (i % 3) * sc, y + (i // 3) * sc, sc, sc, c)
        x += 4 * sc


def cloud(p, cx, cy, wd, rnd, rim=True):
    for _ in range(wd // 6):
        ex, ey = cx + rnd.randint(-wd // 2, wd // 2), cy + rnd.randint(-2, 2)
        rx, ry = rnd.randint(9, 18), rnd.randint(3, 6)
        p.ell(ex, ey, rx, ry, C("#141b3d"), 0.85)
        p.ell(ex, ey - 1, rx - 3, ry - 1, C("#222d5a"), 0.5)
        if rim:
            p.ell(ex + 3, ey - ry + 1, rx - 5, 1, C("#7589c2"), 0.45)


def night_sky(p, x, y, w, hor, rnd, nstars, moon):
    p.vgrad(x, y, w, hor, C("#04061a"), C("#3b5082"), 10)
    tw = []
    for _ in range(nstars):
        sx, sy = rnd.randrange(w), int(hor * rnd.random() ** 1.5 * 0.92)
        col = rnd.choice([(150, 160, 195), (205, 210, 235), (255, 250, 225)])
        p.px(x + sx, y + sy, col)
        if rnd.random() < 0.14:
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p.px(x + sx + ox, y + sy + oy, col, 0.5)
            tw.append((x + sx, y + sy))
    mx, my = x + moon[0], y + moon[1]
    for r, a in ((46, 0.035), (32, 0.05), (21, 0.08)):
        p.ell(mx, my, r, r, C("#9fb8ff"), a)
    p.ell(mx, my, 10, 10, C("#f0f1de"))
    p.ell(mx + 3, my + 2, 7, 7, C("#d3d6c1"), 0.5)
    for cx, cy, r in ((-3, -3, 2), (2, 3, 1.5), (-4, 3, 1.2), (4, -4, 1)):
        p.ell(mx + cx, my + cy, r, r, C("#b9bca8"), 0.8)
    return tw


def sea(p, x, y, w, h, mx, rnd):
    p.vgrad(x, y, w, h, C("#2c4272"), C("#040916"), 10)
    p.rect(x, y - 1, w, 1, C("#6b82b4"), 0.7)
    for yy in range(1, h):
        t = yy / h
        for _ in range(3):
            cx = mx + rnd.uniform(-1, 1) * (3 + t * 30)
            p.rect(cx, y + yy, rnd.randint(2, int(4 + t * 16)), 1, C("#c9d8ff"),
                   0.18 + 0.4 * (1 - t) * rnd.random())
        if rnd.random() < 0.5:
            p.rect(x + rnd.randrange(w), y + yy, rnd.randint(6, 20), 1, C("#486aa8"), 0.2)


def hills(p, x, hor, pts, c, lights, rnd):
    P = [(x + a, hor - b) for a, b in pts]
    p.poly(P + [(P[-1][0], hor), (P[0][0], hor)], c)
    for lx, ly in lights:
        p.px(x + lx, hor - ly, C("#ffd070"))
        p.px(x + lx, hor - ly, C("#ffd070"))


def build_scene():
    rnd = random.Random(7)
    p = PX(WW, WH)
    p.tw = night_sky(p, 0, 0, WW, HOR, rnd, 85, (262, 26))
    cloud(p, 250, 40, 70, rnd)
    cloud(p, 70, 22, 60, rnd, False)
    cloud(p, 150, 58, 90, rnd, False)
    cloud(p, 310, 62, 50, rnd, True)
    hills(p, 0, HOR, [(190, 0), (205, 4), (228, 8), (250, 5), (275, 10), (300, 6),
                      (328, 9)], C("#080d20"), [(214, 3), (232, 4), (260, 3), (286, 5)], rnd)
    hills(p, 0, HOR, [(0, 5), (18, 8), (40, 5), (60, 2), (75, 0)], C("#0a1024"), [(30, 3)], rnd)
    sea(p, 0, HOR, WW, WH - HOR, 262, rnd)
    return p


# ---------------------------------------------------------------- КОРАБЛЬ
def build_ship(d):
    p = PX(170, 120)
    hull = rgb255(HULL_RGB[d["hull"]])
    flag = rgb255(FLAG_RGB[d["flag"]])
    m = d["masts"]
    xs = {1: [104], 2: [82, 126], 3: [68, 102, 136], 4: [62, 86, 110, 134]}[m]
    wood, dwood = C("#6a4a2c"), C("#3b2a1b")
    # отражение рисуется в конце; сначала корпус
    hp = [(8, 74), (158, 65), (151, 88), (133, 97), (30, 97), (14, 90)]
    p.poly(hp, hull)
    p.poly([(11, 84), (155, 77), (151, 88), (133, 97), (30, 97), (14, 90)], (0, 0, 0), 0.28)
    p.poly([(8, 74), (158, 65), (157, 68), (9, 77)], shade(hull, 1.45))
    for off in (9, 16):
        for x in range(12, 150):
            p.px(x, int(74 - (x - 8) * 9 / 150 + off), shade(hull, 0.72))
    p.line(10, 77, 156, 69, shade(hull, 0.6))
    for x in range(70, 156, 13):                       # леер и стойки
        yt = int(74 - (x - 8) * 9 / 150)
        p.rect(x, yt - 5, 1, 5, dwood)
    p.line(70, int(74 - 62 * 9 / 150) - 5, 156, int(74 - 148 * 9 / 150) - 5, dwood)
    for x in (30, 60, 90, 118, 140):                   # заклёпки
        p.px(x, int(74 - (x - 8) * 9 / 150) + 21, shade(hull, 1.3), 0.7)
    # рубка
    p.rect(16, 52, 44, 24, wood)
    p.rect(16, 52, 44, 2, shade(wood, 1.4))
    p.rect(13, 47, 50, 6, dwood)
    p.rect(13, 47, 50, 1, C("#8a6a46"))
    p.rect(46, 36, 6, 11, C("#2a2a30"))
    p.rect(45, 35, 8, 2, C("#18181c"))
    for wx in (21, 39):
        p.glow(wx + 4, 63, 10, C("#ffb84a"), 0.35)
        p.rect(wx, 59, 9, 9, C("#2a1a10"))
        p.rect(wx + 1, 60, 7, 7, C("#ffd47a"))
        p.rect(wx + 1, 60, 7, 2, C("#fff0b0"))
        p.rect(wx + 4, 60, 1, 7, C("#2a1a10"))
        p.rect(wx + 1, 63, 7, 1, C("#2a1a10"))
    p.rect(26, 68, 8, 8, C("#4b331f"))
    # мачты, паруса
    tops = [14 + (i % 2) * 7 for i in range(m)]
    ws = {1: 40, 2: 32, 3: 26, 4: 20}[m]
    cream = C("#e2d8b8")
    for x, top in zip(xs, tops):
        p.rect(x - 1, top, 3, 76 - top, wood)
        p.rect(x - 1, top, 1, 76 - top, shade(wood, 1.35))
        for (y0, y1) in ((top + 4, top + 26), (top + 29, 70)):
            hw = ws // 2
            p.poly([(x - hw, y0), (x + hw, y0), (x + hw + 2, (y0 + y1) // 2),
                    (x + hw, y1), (x - hw, y1), (x - hw - 2, (y0 + y1) // 2)], cream)
            p.rect(x - hw // 2, y0 + 1, hw, y1 - y0 - 3, (255, 250, 230), 0.22)
            p.rect(x - hw - 1, y0, 3, y1 - y0, (60, 50, 70), 0.25)
            p.rect(x + hw - 1, y0, 3, y1 - y0, (60, 50, 70), 0.3)
            for sx in range(-hw + 7, hw - 3, 7):
                p.line(x + sx, y0 + 1, x + sx, y1 - 1, (110, 95, 80), 0.35)
            p.rect(x - hw, y1 - 2, hw * 2, 2, (110, 95, 85), 0.55)
            p.rect(x - hw - 2, y0 - 1, hw * 2 + 4, 2, dwood)
            p.rect(x + hw - 8, y0 + 7, 6, 5, (190, 160, 120), 0.9)
        p.px(x, top - 1, C("#e8c97a"))
    # такелаж
    for x, top in zip(xs, tops):
        p.line(x, top + 2, 158, 65, (20, 16, 14), 0.45)
        p.line(x, top + 2, 10, 74, (20, 16, 14), 0.35)
    # флаг на последней мачте
    fx, ft = xs[-1] + 2, tops[-1] - 2
    for col in range(16):
        off = int(2 * math.sin(col * 0.55))
        for row in range(9 - col // 6):
            k = 1.18 if row < 2 else (0.82 if row > 5 else 1.0)
            p.px(fx + col, ft + row + off, shade(flag, k))
    # огни
    p.glow(158, 66, 8, C("#ff6a3a"), 0.5)
    p.rect(157, 64, 3, 3, C("#ff8a5a"))
    p.glow(11, 72, 7, C("#ffe9a0"), 0.5)
    p.rect(10, 71, 3, 3, C("#fff3c4"))
    # номер на борту
    lum = 0.3 * hull[0] + 0.6 * hull[1] + 0.1 * hull[2]
    col = (245, 245, 235) if lum < 120 else (25, 22, 20)
    digits(p, str(d["number"]), 112, 73, 2, col)
    # ватерлиния и отражение
    p.rect(26, 96, 110, 1, (210, 225, 255), 0.55)
    for y in range(97, 119):
        t = y - 96
        sy = 96 - t
        off = int(2 * math.sin(t * 0.9))
        for x in range(8, 160):
            i = (sy * p.w + x) * 4
            if p.b[i + 3]:
                p.px(x + off, y, (p.b[i], p.b[i + 1], p.b[i + 2]), 0.30 * (1 - t / 24.0))
    return p


# ---------------------------------------------------------------- КОМНАТА (маяк изнутри)
def build_room():
    rnd = random.Random(3)
    p = PX(W, H)
    # камень
    p.rect(0, 0, W, H, C("#1a1614"))
    bh, bw = 11, 26
    for r in range(H // bh + 1):
        yy, off = r * bh, (r % 2) * 13
        for bx in range(-bw + off, W, bw):
            v = rnd.uniform(0.86, 1.12) * (1 - 0.45 * abs(bx + 13 - 240) / 240.0)
            c = (int(92 * v), int(80 * v), int(72 * v))
            p.rect(bx + 1, yy + 1, bw - 1, bh - 1, c)
            p.rect(bx + 1, yy + 1, bw - 1, 1, shade(c, 1.25), 0.8)
            p.rect(bx + 1, yy + bh - 1, bw - 1, 1, shade(c, 0.7), 0.8)
            p.speckle(bx + 1, yy + 1, bw - 1, bh - 1, 5, shade(c, rnd.choice([0.7, 1.3])), 0.7, rnd)
    # потолочная балка
    p.rect(0, 0, W, 12, C("#2a1c12"))
    p.rect(0, 11, W, 1, C("#0e0805"))
    p.rect(0, 0, W, 1, C("#4a3220"))
    for x in range(0, W, 3):
        if rnd.random() < 0.35:
            p.rect(x, rnd.randint(2, 9), rnd.randint(4, 14), 1, C("#1c120a"), 0.7)
    # откосы окна (глубина стены)
    p.poly([(60, 8), (76, 22), (76, 146), (60, 158)], C("#8b7a68"))
    p.poly([(60, 8), (420, 8), (404, 22), (76, 22)], C("#4b4036"))
    p.poly([(420, 8), (404, 22), (404, 146), (420, 158)], C("#5a4d40"))
    p.poly([(60, 158), (76, 146), (404, 146), (420, 158)], C("#a39380"))
    p.line(60, 158, 76, 146, C("#d8c8b0"))
    p.line(76, 146, 404, 146, C("#cdbda4"))
    p.line(404, 146, 420, 158, C("#9a8a76"))
    p.rect(60, 157, 360, 1, C("#3a2f25"))
    for x in range(70, 410, 9):
        p.px(x + rnd.randint(0, 6), rnd.randint(148, 156), C("#8a7a66"), 0.7)
    # окно: вырез, рама, переплёты, блик
    p.clear(WX, WY, WW, WH)
    wd, hi = C("#2c1d12"), C("#5a3f28")
    p.rect(WX, WY, WW, 5, wd)
    p.rect(WX, WY + WH - 5, WW, 5, wd)
    p.rect(WX, WY, 5, WH, wd)
    p.rect(WX + WW - 5, WY, 5, WH, wd)
    p.rect(WX, WY, WW, 1, hi)
    p.rect(WX, WY, 1, WH, hi)
    for mx in (WX + 78, WX + 246):
        p.rect(mx, WY, 4, WH, wd)
        p.rect(mx, WY, 1, WH, hi)
        p.rect(mx + 3, WY, 1, WH, C("#150d07"))
    for (x0, w_) in ((WX + 20, 14), (WX + 150, 8), (WX + 260, 24)):
        p.poly([(x0, WY + 5), (x0 + w_, WY + 5), (x0 + w_ - 40, WY + WH - 5),
                (x0 - 40, WY + WH - 5)], (255, 255, 255), 0.035)
    for _ in range(26):                                # капли и пятна на стекле
        p.px(WX + rnd.randrange(WW), WY + rnd.randrange(WH), (200, 220, 255), 0.18)
    # левая стена: карта и полка с книгами
    p.rect(8, 22, 44, 36, C("#2a1c12"))
    p.rect(10, 24, 40, 32, C("#cdb888"))
    p.speckle(10, 24, 40, 32, 60, C("#a89468"), 0.5, rnd)
    p.line(14, 46, 24, 36, C("#6a5a3c"))
    p.line(24, 36, 34, 44, C("#6a5a3c"))
    p.line(34, 44, 44, 30, C("#6a5a3c"))
    p.ell(40, 48, 5, 3, C("#8fa07a"), 0.8)
    p.px(44, 30, C("#b03a2a"))
    p.rect(4, 88, 54, 4, C("#2a1c12"))
    p.rect(4, 88, 54, 1, C("#5a3f28"))
    x = 7
    for bc in ("#7a2a2a", "#2a4a6a", "#5a5a2a", "#4a2a5a", "#2a5a4a", "#8a5a2a", "#3a3a4a"):
        bw_, bh_ = rnd.randint(5, 8), rnd.randint(14, 24)
        p.rect(x, 88 - bh_, bw_, bh_, C(bc))
        p.rect(x, 88 - bh_, 1, bh_, shade(C(bc), 1.4))
        p.rect(x + 1, 88 - bh_ + 3, bw_ - 2, 1, C("#d9c27a"), 0.7)
        x += bw_ + 1
    p.ell(14, 122, 5, 5, C("#8a6a3a"))                 # бухта каната
    p.ell(14, 122, 2, 2, C("#1a1410"))
    for k in range(4):
        p.ell(14, 122, 5 - k, 5 - k, shade(C("#8a6a3a"), 0.85 + 0.1 * (k % 2)), 0.5)
    # правая стена: часы и антенна
    cx, cy = 450, 42
    p.ell(cx, cy, 17, 17, C("#2a1c12"))
    p.ell(cx, cy, 15, 15, C("#e6dcc0"))
    for k in range(12):
        a = k * math.pi / 6
        p.px(cx + 12.5 * math.sin(a), cy - 12.5 * math.cos(a), C("#2a1c12"))
    p.line(cx, cy, cx + 8, cy - 5, C("#1a1410"))
    p.line(cx, cy, cx - 2, cy - 10, C("#1a1410"))
    p.px(cx, cy, C("#b03a2a"))
    # СТОЛ
    p.rect(0, 158, W, H - 158, C("#4a2c16"))
    for r, y in enumerate(range(158, H, 22)):
        c = shade(C("#4a2c16"), rnd.uniform(0.85, 1.15))
        p.rect(0, y, W, 22, c)
        p.rect(0, y, W, 1, C("#241206"))
        for _ in range(26):
            p.rect(rnd.randrange(W), y + rnd.randint(2, 20), rnd.randint(10, 60), 1,
                   shade(c, rnd.choice([0.8, 1.2])), 0.55)
        for _ in range(2):
            kx = rnd.randrange(30, W - 30)
            p.ell(kx, y + 11, 4, 2, shade(c, 0.7), 0.6)
    p.rect(0, 158, W, 2, C("#8a5a30"))
    p.rect(0, 160, W, 1, C("#2a1608"))
    # ПАПКА (обложка + бумага)
    p.rect(2, 162, 254, 106, (0, 0, 0), 0.35)
    p.rect(4, 160, 250, 108, C("#6a4a26"))
    p.rect(4, 160, 250, 2, C("#8a6a3e"))
    p.rect(4, 266, 250, 2, C("#3a2812"))
    p.rect(8, 164, 242, 100, C("#d9cfb0"))
    p.speckle(8, 164, 242, 100, 160, C("#b8ac8a"), 0.5, rnd)
    p.rect(8, 164, 242, 1, C("#f0e8d0"))
    p.rect(8, 177, 242, 1, C("#9a8a68"))
    p.rect(8, 259, 242, 1, C("#9a8a68"))
    for k in range(1, 5):
        p.rect(12, int(177 + k * 16.4), 234, 1, C("#b8aa86"), 0.8)
    p.rect(64, 165, 1, 98, C("#b5463a"), 0.0)
    # РАДИО
    p.rect(256, 162, 224, 68, (0, 0, 0), 0.35)
    p.rect(258, 160, 218, 66, C("#35241a"))
    p.rect(258, 160, 218, 2, C("#6a4a34"))
    p.rect(258, 224, 218, 2, C("#1a100a"))
    p.rect(258, 160, 2, 66, C("#52382a"))
    p.rect(264, 166, 148, 54, C("#120d0a"))
    p.rect(266, 168, 144, 50, C("#0b1a12"))
    for yy in range(168, 218, 2):
        p.rect(266, yy, 144, 1, (0, 0, 0), 0.25)
    p.rect(266, 168, 144, 1, C("#1d3a2a"))
    p.rect(416, 166, 54, 44, C("#120d0a"))
    for gy in range(169, 208, 4):
        for gx in range(419, 468, 4):
            p.rect(gx, gy, 2, 2, C("#05030a"))
            p.rect(gx, gy, 1, 1, C("#4a3a30"), 0.6)
    for kx in (430, 456):
        p.ell(kx, 216, 5, 5, C("#12090a"))
        p.ell(kx, 216, 4, 4, C("#8a6a3a"))
        p.line(kx, 216, kx + 2, 212, C("#2a1c10"))
    p.line(468, 160, 456, 96, C("#8a8a92"))
    p.line(469, 160, 457, 96, C("#4a4a52"))
    p.ell(456, 95, 2, 2, C("#c8c8d0"))
    # фонарь на подоконнике (слева) и кружка (справа)
    p.rect(94, 143, 14, 4, C("#3a2a14"))
    p.rect(93, 142, 16, 2, C("#b8903a"))
    p.rect(95, 128, 12, 14, C("#5a3a1a"))
    p.rect(96, 129, 10, 12, C("#ffd070"))
    p.rect(98, 132, 6, 8, C("#fff2b0"))
    p.rect(100, 133, 2, 6, C("#ffffff"), 0.8)
    for xx in (95, 101, 106):
        p.rect(xx, 128, 1, 14, C("#3a2a14"))
    p.rect(93, 125, 16, 3, C("#3a2a14"))
    p.rect(96, 122, 10, 3, C("#2a1c0c"))
    p.line(97, 122, 101, 116, C("#2a1c0c"))
    p.line(105, 122, 101, 116, C("#2a1c0c"))
    p.rect(376, 134, 12, 12, C("#c9c2b0"))
    p.rect(376, 134, 12, 2, C("#3a2410"))
    p.rect(377, 136, 2, 9, C("#fffbe8"), 0.5)
    p.rect(388, 137, 3, 6, C("#c9c2b0"))
    p.rect(389, 139, 1, 2, C("#6a6a5a"))
    p.rect(376, 145, 12, 1, C("#8a8272"))
    return p


# ---------------------------------------------------------------- ЗАСТАВКА (маяк снаружи)
def build_title():
    rnd = random.Random(11)
    p = PX(W, H)
    hor = 196
    tw = night_sky(p, 0, 0, W, hor, rnd, 160, (84, 52))
    cloud(p, 120, 40, 110, rnd)
    cloud(p, 300, 74, 90, rnd, False)
    cloud(p, 40, 110, 80, rnd, False)
    hills(p, 0, hor, [(0, 6), (40, 10), (90, 6), (140, 3), (170, 0)], C("#080d20"),
          [(60, 4), (100, 3)], rnd)
    sea(p, 0, hor, W, H - hor, 84, rnd)
    lx = 380
    # башня: конус с красно-белыми полосами
    top_y, bot_y, top_w, bot_w = 112, 256, 30, 54
    def half(y):
        return (top_w + (bot_w - top_w) * (y - top_y) / float(bot_y - top_y)) / 2.0
    for i, y in enumerate(range(top_y, bot_y, 18)):
        y2 = min(bot_y, y + 18)
        col = C("#b3342f") if i % 2 == 0 else C("#d9d4c7")
        p.poly([(lx - half(y), y), (lx + half(y), y), (lx + half(y2), y2), (lx - half(y2), y2)], col)
    for y in range(top_y, bot_y):                      # объём: тень справа, блик слева
        h_ = half(y)
        p.rect(lx + h_ * 0.35, y, h_ * 0.65, 1, (5, 8, 25), 0.5)
        p.rect(lx - h_, y, 2, 1, (180, 200, 255), 0.35)
    for wy in (148, 196):
        p.rect(lx - 3, wy, 6, 10, C("#10141f"))
        p.rect(lx - 2, wy + 1, 4, 8, C("#ffd070"), 0.9)
    p.rect(lx - 8, 240, 16, 16, C("#2a1c12"))
    # галерея и фонарная
    p.rect(lx - 26, 108, 52, 5, C("#1a1a22"))
    p.rect(lx - 26, 108, 52, 1, C("#505068"))
    for x in range(lx - 24, lx + 26, 6):
        p.rect(x, 96, 1, 12, C("#1a1a22"))
    p.rect(lx - 26, 96, 52, 1, C("#1a1a22"))
    p.glow(lx, 82, 40, C("#ffd98a"), 0.28)
    p.glow(lx, 82, 22, C("#fff0b0"), 0.35)
    p.rect(lx - 13, 66, 26, 30, C("#ffe9a8"))
    p.rect(lx - 9, 70, 18, 22, C("#fffbe0"))
    for x in (lx - 13, lx - 4, lx + 5, lx + 12):
        p.rect(x, 66, 2, 30, C("#2a2430"))
    p.rect(lx - 15, 63, 30, 4, C("#2a2430"))
    p.poly([(lx - 15, 63), (lx + 15, 63), (lx, 46)], C("#8a2a28"))
    p.poly([(lx - 15, 63), (lx, 46), (lx - 2, 46)], C("#c94a40"))
    p.rect(lx - 1, 38, 2, 8, C("#2a2430"))
    # скалы и пена
    p.poly([(lx - 70, 270), (lx - 50, 246), (lx - 28, 240), (lx - 8, 252), (lx + 20, 242),
            (lx + 46, 248), (lx + 70, 270)], C("#0d0f18"))
    p.poly([(lx - 50, 246), (lx - 28, 240), (lx - 24, 246), (lx - 46, 252)], C("#2a3042"))
    p.poly([(lx + 20, 242), (lx + 46, 248), (lx + 40, 252), (lx + 16, 248)], C("#2a3042"))
    for x in range(lx - 74, lx + 74, 5):
        p.rect(x, 262 + rnd.randint(-3, 3), rnd.randint(3, 8), 1, (210, 225, 255), 0.5)
    p.tw = tw
    return p


# ---------------------------------------------------------------- ПОКУПКИ: КОТ И ГЕРАНЬ
def build_cat():
    p = PX(48, 28)
    o, d, w = C("#d08a45"), C("#8e5426"), C("#f4e8d2")
    p.ell(22, 24, 18, 3, (0, 0, 0), 0.3)
    p.ell(20, 17, 17, 9, o)
    p.ell(20, 12, 14, 3, shade(o, 1.25), 0.6)
    for x in (9, 15, 21, 27):
        p.poly([(x, 9), (x + 2, 9), (x + 3, 17), (x + 1, 17)], d, 0.9)
    p.ell(38, 17, 8, 7, o)
    p.poly([(31, 13), (32, 5), (38, 11)], o)
    p.poly([(39, 11), (45, 5), (46, 14)], o)
    p.poly([(33, 11), (33, 8), (36, 11)], (236, 150, 150), 0.9)
    p.poly([(41, 10), (44, 8), (44, 12)], (236, 150, 150), 0.9)
    p.rect(34, 16, 3, 1, C("#2a1a10"))
    p.rect(40, 16, 3, 1, C("#2a1a10"))
    p.rect(37, 19, 2, 1, (236, 120, 130))
    p.ell(38, 21, 5, 3, w)
    p.ell(26, 23, 6, 3, w)
    for k in range(16):                              # хвост, свернувшийся вокруг
        a = k / 15.0
        p.ell(3 + 5 * math.sin(a * 2.2), 22 - 8 * a + 3 * a * a, 2.2, 2.2, o if k % 4 else d)
    return p


def leaf(p, x0, y0, x1, y1, wd, c):
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L * wd, dx / L * wd
    mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    p.poly([(x0, y0), (mx + nx, my + ny), (x1, y1), (mx - nx, my - ny)], c)
    p.line(x0, y0, x1, y1, shade(c, 1.35))


def build_plant():
    p = PX(36, 46)
    for (x1, y1, wd, k) in ((4, 14, 4, 0.9), (10, 6, 4, 1.1), (18, 2, 4, 1.0),
                            (27, 7, 4, 0.9), (32, 15, 4, 1.1), (18, 12, 3, 0.8)):
        leaf(p, 18, 32, x1, y1, wd, shade(C("#3f8a3a"), k))
    for (fx, fy) in ((10, 6), (27, 7), (18, 3)):
        for ox, oy in ((0, 0), (2, 1), (-2, 1), (1, -1), (-1, -1)):
            p.px(fx + ox, fy + oy, C("#d8344a"))
        p.px(fx, fy, C("#ffb0b8"))
    p.poly([(8, 33), (28, 33), (25, 45), (11, 45)], C("#b5562f"))
    p.rect(6, 31, 24, 4, C("#cf6a3c"))
    p.rect(6, 31, 24, 1, C("#e88a5a"))
    p.rect(11, 40, 14, 1, C("#8a3e20"), 0.7)
    return p


# ---------------------------------------------------------------- ЗВУК
SR = 22050


def save_wav(path, data, sr=SR):
    a = array.array("h", (int(max(-1.0, min(1.0, v)) * 30000) for v in data))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(a.tobytes())


def tone(freq, dur, noisy=False, vib=0.0, vol=0.5):
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        f = freq * (1 + vib * math.sin(t * 60))
        ph = (t * f) % 1
        v = (0.5 if ph < 0.5 else -0.5) * 0.6 + math.sin(2 * math.pi * f * t) * 0.4
        if noisy:
            v = v * 0.6 + random.uniform(-0.5, 0.5)
        out.append(v * min(1, i / 120) * (1 - i / n) * vol)
    return out


def sweep(f0, f1, dur, vol=0.5, decay=3.0, noise=0.0):
    n = int(SR * dur)
    out, ph = [], 0.0
    for i in range(n):
        t = i / float(n)
        ph += 2 * math.pi * (f0 + (f1 - f0) * t) / SR
        v = math.sin(ph) + 0.3 * math.sin(2 * ph)
        if noise:
            v = v * (1 - noise) + random.uniform(-1, 1) * noise
        out.append(v * vol * math.exp(-decay * t) * min(1.0, i / 80.0))
    return out


def bell(freqs, dur, vol=0.3, decay=4.0):
    n = int(SR * dur)
    return [sum(math.sin(2 * math.pi * f * i / SR) for f in freqs) / len(freqs) * vol *
            math.exp(-decay * i / float(n)) for i in range(n)]


def rumble(dur=2.4):
    n = int(SR * dur)
    y, out = 0.0, []
    for i in range(n):
        y += 0.03 * (random.uniform(-1, 1) - y)
        t = i / float(n)
        out.append(y * 7 * math.exp(-1.6 * t) * min(1.0, i / 2000.0))
    return out


def burst(dur, vol):
    n = int(SR * dur)
    return [random.uniform(-1, 1) * vol * (1 - i / float(n)) ** 2 for i in range(n)]


def sea_data(sr=11025, dur=8.0):
    n = int(sr * dur)
    y, out = 0.0, []
    for i in range(n):
        y += 0.06 * (random.uniform(-1, 1) - y)
        env = 0.35 + 0.65 * math.sin(math.pi * i / n) ** 2
        out.append(y * env * 2.5)
    return out


def build_music(path):
    """Спокойная петля 16 с: арпеджио, пэд, бас, редкая мелодия, лёгкое эхо."""
    sr, bar = 11025, 4.0
    n = int(sr * bar * 4)
    buf = [0.0] * n
    N = lambda m: 440.0 * 2 ** ((m - 69) / 12.0)

    def pluck(f, start, dur, amp, tau):
        w, s0 = 2 * math.pi * f / sr, int(start * sr)
        for k in range(int(dur * sr)):
            t = k / float(sr)
            buf[(s0 + k) % n] += amp * math.exp(-t / tau) * min(1.0, t / 0.015) * \
                (math.sin(w * k) + 0.25 * math.sin(2 * w * k))

    def pad(f, start, dur, amp):
        w, s0 = 2 * math.pi * f / sr, int(start * sr)
        for k in range(int(dur * sr)):
            t = k / float(sr)
            env = min(1.0, t / 1.2) * min(1.0, (dur - t) / 1.2)
            buf[(s0 + k) % n] += amp * env * math.sin(w * k)

    chords = [(45, [52, 57, 60, 64]), (41, [48, 53, 57, 60]),
              (48, [55, 60, 64, 67]), (43, [50, 55, 59, 62])]
    rnd = random.Random(5)
    scale = [69, 72, 74, 76, 79]
    pattern = [0, 1, 2, 3, 2, 1, 2, 3]
    for b, (root, tones) in enumerate(chords):
        t0 = b * bar
        pad(N(root + 12), t0, bar + 0.8, 0.06)
        pad(N(tones[1]), t0, bar + 0.8, 0.05)
        pad(N(tones[2]), t0, bar + 0.8, 0.04)
        pluck(N(root), t0, 3.5, 0.16, 1.6)
        for k, idx in enumerate(pattern):
            pluck(N(tones[idx] + 12), t0 + k * 0.5, 1.8, 0.10, 0.5)
        if b % 2 == 1:
            pluck(N(rnd.choice(scale) + 12), t0, 2.5, 0.09, 0.9)
            pluck(N(rnd.choice(scale) + 12), t0 + 2.0, 2.5, 0.08, 0.9)
    d1, d2 = int(0.43 * sr), int(0.77 * sr)
    for i in range(n):
        buf[i] += 0.28 * buf[(i - d1) % n] + 0.18 * buf[(i - d2) % n]
    y = 0.0
    for i in range(n):
        y += 0.55 * (buf[i] - y)
        buf[i] = y
    peak = max(1e-6, max(abs(v) for v in buf))
    save_wav(path, [v / peak * 0.6 for v in buf], sr)


class Sfx:
    def __init__(self, folder, cfg):
        self.cfg, self.snd, self.sea, self.music = cfg, {}, None, None
        self.mready, self.mtried = False, False
        try:
            os.makedirs(folder, exist_ok=True)

            def mk(name, data, sr=SR):
                p = os.path.join(folder, name + ".wav")
                save_wav(p, data, sr)
                self.snd[name] = SoundLoader.load(p)

            for v, f in enumerate(VOICES):
                for k, m in enumerate((1.0, 1.26)):
                    for nz in (0, 1):
                        mk("v%d_%d_%d" % (v, k, nz), tone(f * m, 0.07, bool(nz), 0.04))
            mk("click", tone(900, 0.04))
            mk("good", tone(660, 0.1) + tone(880, 0.14))
            mk("bad", tone(110, 0.35, True))
            mk("scratch", [random.uniform(-1, 1) * 0.25 * (1 - i / 1200.0) for i in range(1200)])
            mk("coin", tone(1200, 0.06) + tone(1700, 0.12))
            mk("meow", sweep(620, 380, 0.45, 0.5, 2.5))
            mk("squawk", sweep(900, 600, 0.22, 0.4, 2.0, 0.35))
            mk("chime", bell([880, 1320, 1760], 1.3))
            mk("star", sweep(500, 1900, 0.6, 0.25, 2.0))
            mk("splash", burst(0.3, 0.5))
            mk("crackle", [random.uniform(-1, 1) * (0.4 if random.random() < 0.3 else 0.03)
                           for _ in range(int(SR * 0.5))])
            mk("thunder", rumble())
            mk("sea", sea_data(), 11025)
            self.sea = self.snd.get("sea")
            if self.sea:
                self.sea.loop = True
                self.sea.play()
        except Exception as e:
            print("Звук отключён:", e)
        self.mpath = os.path.join(folder, "music1.wav")
        if os.path.exists(self.mpath):
            self.mready = True
        else:
            threading.Thread(target=self._mk_music, daemon=True).start()
        self.apply()

    def _mk_music(self):
        try:
            build_music(self.mpath + ".tmp")
            os.replace(self.mpath + ".tmp", self.mpath)
            self.mready = True
        except Exception as e:
            print("Музыка не создана:", e)

    def poll(self):
        if self.mready and not self.mtried:
            self.mtried = True
            try:
                self.music = SoundLoader.load(self.mpath)
                if self.music:
                    self.music.loop = True
                    self.apply()
                    self.music.play()
            except Exception:
                pass

    def apply(self):
        try:
            if self.sea:
                self.sea.volume = 0.3 * self.cfg["sfx"]
            if self.music:
                self.music.volume = 0.7 * self.cfg["music"]
        except Exception:
            pass

    def play(self, name, vol=1.0):
        s = self.snd.get(name)
        if s:
            try:
                voice = name[0] == "v" and name[1:2].isdigit()
                s.volume = vol * (self.cfg["voice"] if voice else self.cfg["sfx"])
                s.stop()
                s.play()
            except Exception:
                pass


# ---------------------------------------------------------------- ИГРА
def make_tex(px, smooth=False):
    t = Texture.create(size=(px.w, px.h), colorfmt="rgba")
    t.blit_buffer(bytes(px.b), colorfmt="rgba", bufferfmt="ubyte")
    t.flip_vertical()
    t.mag_filter = t.min_filter = "linear" if smooth else "nearest"
    return t


def radial(w, h, power, edge=0.0):
    p = PX(w, h)
    for y in range(h):
        for x in range(w):
            d = math.hypot((x + 0.5 - w / 2.0) / (w / 2.0), (y + 0.5 - h / 2.0) / (h / 2.0))
            a = (max(0.0, 1 - d) ** power) if edge == 0 else \
                min(1.0, max(0.0, (d - edge) / (1.0 - edge * 0.6))) ** power
            i = (y * w + x) * 4
            p.b[i:i + 4] = bytes((255, 255, 255, int(255 * min(1.0, a))))
    return p


def inside(vx, vy, x, y, w, h):
    return x <= vx <= x + w and y <= vy <= y + h


ENT_Y0, ENT_H = 177, 16.4
INK = (0.13, 0.09, 0.06)
TS = [0.94, 1.0, 1.08]
DEFAULT_CFG = dict(music=0.6, sfx=0.8, voice=0.7, speed=0.35, text=1, shake=True)
RANKS = [(0, "Новичок"), (3, "Смотритель"), (7, "Опытный смотритель"),
         (15, "Старший смотритель"), (30, "Хранитель маяка")]
SHOP = [("tea", "Ромашковый чай", "Стресс −10%", 15),
        ("valer", "Настойка", "Стресс −25%", 35),
        ("lupa", "Лупа", "Подсветит запись в папке", 10),
        ("charm", "Талисман", "Прощает одну ошибку", 40),
        ("plant", "Герань", "Живой цветок на окне", 25),
        ("cat", "Кот Маяк", "Спит на окне и мурлычет", 60)]
WEATHER = {"clear": "ясно", "rain": "дождь", "fog": "туман", "storm": "гроза"}
QUIPS = {
    "lantern": ["Фитиль потрескивает.", "Керосина хватит до утра.", "Огонёк кивает тебе."],
    "mug": ["Чай остыл. Как всегда.", "Пахнет мятой.", "Пар вьётся над кружкой."],
    "clock": ["Тик-так. Смена длинная.", "Без пяти полночь. Опять.", "Часы спешат на минуту."],
    "map": ["Карта побережья. Кто-то обвёл Нарву.", "На карте пятно от чая."],
    "shelf": ["Лоция, лоция и снова лоция.", "Одна книга без названия.", "Пыль. Много пыли."],
    "wall": ["Холодный камень.", "Стены помнят штормы."],
}


def rank_of(d):
    r = RANKS[0][1]
    for n, name in RANKS:
        if d >= n:
            r = name
    return r


class Game(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.dir = App.get_running_app().user_data_dir
        self.save_path = os.path.join(self.dir, "save.json")
        self.d = self.load_save()
        self.cfg = self.d["cfg"]
        self.sfx = None
        self.cache = {}
        self.t = self.st_t = 0.0
        self.state, self.menu, self.menu_prev, self.drag = "loading", None, None, None
        self.ship = self.ship_tex = None
        self.ship_x, self.ship_sc, self.ship_wl, self.ship_a = -100.0, 1.0, WLN, 1.0
        self.beam_x = W / 2.0
        self.dust = [[random.random(), random.uniform(-1, 1)] for _ in range(18)]
        self.glints, self.birds, self.shots, self.ripples = [], [], [], []
        self.fish, self.hearts = [], []
        self.toast = ("", 0.0)
        self.weather, self.flash, self.bolt, self.thunder_t = "clear", 0.0, [], 0.0
        self.ghost_t, self.static_t, self.jig, self.lamp_flash = 0.0, 0.0, 0.0, 0.0
        self.taps = dict(clock=0, shelf=0, star=0)
        self.stress, self.page, self.hint = 0, 0, -1
        self.day, self.i, self.errors, self.day_errors, self.day_coins = 1, 0, [], 0, 0
        self.hist, self.ships, self.reg, self.struck = [], [], [], {}
        self.typed, self.blip_n, self.lines, self.leave = 0.0, 0, [], 1
        self.win, self.rankup = False, ""
        self.stroke, self.stroke_k, self.stroke_uid = None, 0, None
        self.s, self.ox, self.oy, self.bx, self.by = 1, 0, 0, 0, 0
        Clock.schedule_interval(self.update, 1 / 30.0)
        Clock.schedule_once(self.load_assets, 0.4)

    def load_assets(self, dt):
        sc = build_scene()
        self.tex_scene, self.twinkle = make_tex(sc), sc.tw
        self.tex_room = make_tex(build_room())
        self.tex_title = make_tex(build_title())
        self.tex_glow = make_tex(radial(64, 64, 2.0), True)
        self.tex_vig = make_tex(radial(64, 36, 1.6, 0.5), True)
        self.tex_ghost = make_tex(build_ship(dict(hull="тёмно-серый", flag="синий",
                                                  masts=3, number=13)))
        self.tex_cat = make_tex(build_cat())
        self.tex_plant = make_tex(build_plant())
        self.sfx = Sfx(os.path.join(self.dir, "snd"), self.cfg)
        self.state = "title"

    # ---- сохранение
    def load_save(self):
        d = dict(best=0, coins=0, lupa=0, charm=0, cat=False, plant=False, cfg=dict(DEFAULT_CFG))
        try:
            with open(self.save_path) as f:
                j = json.load(f)
            for k in ("best", "coins", "lupa", "charm"):
                d[k] = int(j.get(k, 0))
            for k in ("cat", "plant"):
                d[k] = bool(j.get(k, False))
            d["cfg"].update({k: v for k, v in j.get("cfg", {}).items() if k in DEFAULT_CFG})
        except Exception:
            pass
        return d

    def save(self):
        try:
            with open(self.save_path, "w") as f:
                json.dump(self.d, f)
        except Exception:
            pass

    def snd(self, name, vol=1.0):
        if self.sfx:
            self.sfx.play(name, vol)

    def say(self, text, secs=2.6):
        self.toast = (text, self.t + secs)

    # ---- ход игры
    def start_game(self):
        self.day, self.stress, self.errors, self.hist = 1, 0, [], []
        self.start_day()

    def start_day(self):
        self.ships = make_day(self.day, self.hist)
        self.reg = sorted(self.ships, key=lambda s: s["truth"]["captain"])
        for k, sh in enumerate(self.reg):
            sh["ri"] = k
        self.struck, self.page, self.hint = {}, 0, -1
        self.i, self.day_errors, self.day_coins, self.rankup = -1, 0, 0, ""
        self.weather = "clear" if self.day == 1 else \
            random.choices(["clear", "rain", "fog", "storm"], [40, 25, 20, 15])[0]
        self.ship_tex = None
        self.state, self.st_t = "intro", 0.0

    def next_ship(self):
        self.i += 1
        self.hint = -1
        if self.i >= len(self.ships):
            self.finish_day()
            return
        self.ship = self.ships[self.i]
        self.ship_tex = make_tex(build_ship(self.ship["shown"]))
        self.lines = wrap(self.ship["msg"], int(31 / TS[self.cfg["text"]]))
        self.ship_x, self.ship_sc, self.ship_wl, self.ship_a = -100.0, 1.0, WLN, 1.0
        self.typed, self.blip_n = 0.0, 0
        self.state, self.st_t = "arrive", 0.0

    def finish_day(self):
        self.d["best"] = max(self.d["best"], self.day)
        if self.day_errors == 0:
            self.d["coins"] += 10
            self.day_coins += 10
        if self.day in (3, 7, 15, 30):
            self.rankup = rank_of(self.day)
            self.d["coins"] += 20
            self.day_coins += 20
        self.save()
        self.win = self.day >= 30
        self.ship_tex = None
        self.state, self.st_t = "dayend", 0.0

    def decide(self, admit):
        sh = self.ship
        if admit and sh["fake"]:
            d, ok = 12, False
        elif not admit and not sh["fake"]:
            d, ok = 6, False
        else:
            d, ok = 0, True
        if ok:
            self.d["coins"] += 2
            self.day_coins += 2
        else:
            self.day_errors += 1
            self.errors.append(dict(
                day=self.day, n=self.i + 1,
                kind="впустил подставного" if admit else "отказал настоящему",
                diffs=sh["diffs"]))
            if self.d["charm"] > 0:
                self.d["charm"] -= 1
            else:
                self.stress = min(100, self.stress + d)
        self.save()
        self.snd("click")
        self.leave = 1 if admit else -1
        self.state, self.st_t = "leave", 0.0

    def buy(self, key):
        it = [s for s in SHOP if s[0] == key][0]
        if key in ("cat", "plant") and self.d[key]:
            self.say("Уже куплено")
            return
        if self.d["coins"] < it[3]:
            self.say("Не хватает монет")
            self.snd("bad", 0.4)
            return
        self.d["coins"] -= it[3]
        if key == "tea":
            self.stress = max(0, self.stress - 10)
        elif key == "valer":
            self.stress = max(0, self.stress - 25)
        elif key in ("lupa", "charm"):
            self.d[key] += 1
        else:
            self.d[key] = True
        self.save()
        self.snd("coin")
        self.say("Куплено: " + it[1])

    # ---- обновление
    def update(self, dt):
        self.t += dt
        if self.sfx:
            self.sfx.poll()
        self.ambient(dt)
        if self.state != "loading" and not self.menu:
            self.st_t += dt
            self.step(dt)
        self.draw()

    def step(self, dt):
        st = self.state
        if st in ("arrive", "radio", "decide"):
            target = self.ship_x
        else:
            target = W / 2 + 70 * math.sin(self.t * 0.35)
        self.beam_x += (target - self.beam_x) * min(1.0, dt * 3)
        for p in self.dust:
            p[0] = (p[0] + dt * 0.03) % 1.0
        if st == "intro":
            if self.st_t > 3.4:
                self.next_ship()
        elif st == "arrive":
            p = min(1.0, self.st_t / 2.4)
            self.ship_x = -100 + (W / 2 + 100) * (1 - (1 - p) ** 3)
            if p >= 1.0:
                self.state, self.st_t = "radio", 0.0
        elif st == "radio":
            self.typed += dt * (12 + 38 * self.cfg["speed"])
            n = int(self.typed)
            msg = self.ship["msg"]
            while self.blip_n < min(n, len(msg)):
                self.blip_n += 1
                if self.blip_n % 2 == 0 and msg[self.blip_n - 1] != " ":
                    noisy = int(random.random() < self.stress / 120.0)
                    self.snd("v%d_%d_%d" % (self.ship["voice"], random.randint(0, 1), noisy), 0.5)
            if n >= len(msg):
                self.state = "decide"
        elif st == "leave":
            p = min(1.0, self.st_t / 1.5)
            if self.leave > 0:
                self.ship_x = W / 2 + p * p * 300
            else:
                self.ship_sc = 1 - 0.65 * p
                self.ship_x = W / 2 - 30 * p
                self.ship_wl = WLN - 26 * p
                self.ship_a = 1 - p ** 1.5
            if self.st_t >= 1.6:
                self.ship_tex = None
                if self.stress >= 100:
                    self.save()
                    self.state, self.st_t = "gameover", 0.0
                else:
                    self.state, self.st_t = "strike", 0.0
        elif st == "pause" and self.st_t > 0.6:
            self.next_ship()
        if self.stress > 60 and random.random() < (self.stress - 60) / 200.0:
            self.glints.append([WX + random.randint(8, WW - 8), WY + random.randint(8, 100), 0.3])

    def ambient(self, dt):
        """Живой фон: птицы, падающие звёзды, рыбы, круги на воде, погода."""
        t, st = self.t, self.state
        playing = st not in ("title", "loading", "shop", "dayend", "gameover")
        if playing and random.random() < dt / 14.0 and len(self.birds) < 2:
            self.birds.append([WX - 8, WY + random.randint(14, 62), random.uniform(26, 48),
                               random.random() * 6])
        for b in self.birds:
            b[0] += b[2] * dt
        self.birds = [b for b in self.birds if b[0] < WX + WW + 12]
        if st not in ("loading",) and random.random() < dt / 22.0:
            self.spawn_star(random.randint(WX + 30, WX + WW - 30), WY + random.randint(8, 40))
        for s in self.shots:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[4] -= dt
        self.shots = [s for s in self.shots if s[4] > 0]
        if playing and random.random() < dt / 26.0 and not self.fish:
            self.fish.append([random.randint(WX + 30, WX + WW - 30), 0.0])
        for f in self.fish:
            f[1] += dt
            if f[1] > 0.7 and len(f) == 2:
                f.append(1)
                self.ripples.append([f[0], WY + 112, 2.0, 1.0])
                self.snd("splash", 0.25)
        self.fish = [f for f in self.fish if f[1] < 0.8]
        for r in self.ripples:
            r[2] += dt * 22
            r[3] -= dt * 0.9
        self.ripples = [r for r in self.ripples if r[3] > 0]
        for h in self.hearts:
            h[1] -= dt * 14
            h[2] -= dt * 0.7
        self.hearts = [h for h in self.hearts if h[2] > 0]
        self.flash = max(0.0, self.flash - dt * 2.2)
        self.static_t = max(0.0, self.static_t - dt)
        self.jig = max(0.0, self.jig - dt)
        self.lamp_flash = max(0.0, self.lamp_flash - dt)
        if self.ghost_t > 0:
            self.ghost_t -= dt
        if self.thunder_t > 0:
            self.thunder_t -= dt
            if self.thunder_t <= 0:
                self.snd("thunder", 0.8)
        if playing and self.weather == "storm" and random.random() < dt / 9.0:
            self.flash = 0.9
            self.thunder_t = random.uniform(0.3, 1.2)
            x, y, pts = random.randint(WX + 40, WX + WW - 40), WY, []
            while y < WY + HOR:
                pts.append((x, y))
                x += random.randint(-9, 9)
                y += random.randint(6, 14)
            self.bolt = pts

    def spawn_star(self, x, y):
        self.shots.append([x, y, random.uniform(60, 90), random.uniform(25, 40), 0.9])

    # ---- ввод
    def vpos(self, touch):
        return (touch.x - self.bx) / self.s, H - (touch.y - self.by) / self.s

    def on_touch_down(self, touch):
        vx, vy = self.vpos(touch)
        st = self.state
        if st == "loading":
            return True
        if self.menu:
            return self.menu_touch(vx, vy)
        if st == "title":
            self.title_touch(vx, vy)
        elif st == "intro":
            if self.st_t > 0.6:
                self.next_ship()
        elif st == "dayend":
            if self.st_t > 0.5:
                if self.win:
                    self.state = "title"
                else:
                    self.state, self.st_t = "shop", 0.0
        elif st == "shop":
            self.shop_touch(vx, vy)
        elif st == "gameover":
            if self.st_t > 1.0:
                self.state = "title"
        else:
            self.play_touch(touch, vx, vy)
        return True

    def title_touch(self, vx, vy):
        if inside(vx, vy, 100, 136, 140, 32):
            self.snd("click")
            self.start_game()
        elif inside(vx, vy, 100, 176, 140, 32):
            self.snd("click")
            self.menu, self.menu_prev = "settings", None
        elif inside(vx, vy, 100, 216, 140, 32):
            App.get_running_app().stop()
        elif math.hypot(vx - 84, vy - 52) < 16:
            self.spawn_star(60, 30)
            self.snd("star", 0.5)
        elif math.hypot(vx - 380, vy - 82) < 26:
            self.lamp_flash = 1.2
            self.snd("chime", 0.6)
            self.say("Маяк подмигнул тебе.")
        elif inside(vx, vy, 40, 24, 260, 64):
            self.jig = 0.8
            self.snd("click", 0.5)
        elif vy > 200 and vx < 300:
            self.ripples.append([vx, vy, 2.0, 1.0])
            self.snd("splash", 0.25)

    def play_touch(self, touch, vx, vy):
        st = self.state
        if inside(vx, vy, 434, 0, 46, 14):
            self.menu, self.menu_prev, self.stroke = "pause", None, None
            self.snd("click", 0.5)
            return
        if inside(vx, vy, 4, 258, 252, 10):
            pages = max(1, (len(self.reg) + 4) // 5)
            self.page = (self.page + (1 if vx > 130 else -1)) % pages
            self.snd("click", 0.5)
            return
        if st == "strike":
            for k, sh in enumerate(self.reg[self.page * 5:self.page * 5 + 5]):
                x, y, w, h = self.entry_rect(k)
                if inside(vx, vy, x, y - 2, w, h + 2) and sh["ri"] not in self.struck:
                    self.stroke, self.stroke_k, self.stroke_uid = [(vx, vy)], k, touch.uid
                    return
        if st in ("radio", "decide") and self.d["lupa"] > 0 and inside(vx, vy, 416, 206, 54, 16):
            self.d["lupa"] -= 1
            self.hint = self.ship["ri"]
            self.page = self.hint // 5
            self.save()
            self.snd("chime", 0.5)
            return
        if st == "radio" and inside(vx, vy, 264, 166, 148, 54):
            self.typed = float(len(self.ship["msg"]))
            return
        if st == "decide":
            if inside(vx, vy, 260, 232, 104, 30):
                self.decide(True)
                return
            if inside(vx, vy, 372, 232, 104, 30):
                self.decide(False)
                return
        self.tap_world(vx, vy)

    def tap_world(self, vx, vy):
        """Пасхалки: всё в комнате реагирует на касание."""
        for b in self.birds:
            if abs(vx - b[0]) < 12 and abs(vy - b[1]) < 10:
                b[2] = 160
                self.snd("squawk", 0.6)
                self.say("Кыш!")
                return
        if self.d["cat"] and inside(vx, vy, 318, 118, 52, 32):
            self.snd("meow", 0.8)
            self.hearts += [[vx + random.randint(-12, 12), vy - 8, 1.0] for _ in range(3)]
            self.say(random.choice(["Мурр.", "Кот делает вид, что спит.", "Маяк мурлычет."]))
        elif self.d["plant"] and inside(vx, vy, 116, 102, 40, 48):
            self.snd("click", 0.4)
            self.say(random.choice(["Герани нравится лунный свет.", "Листик качнулся."]))
        elif inside(vx, vy, 86, 114, 30, 40):
            self.lamp_flash = 1.0
            self.snd("chime", 0.4)
            self.say(random.choice(QUIPS["lantern"]))
        elif inside(vx, vy, 370, 126, 28, 24):
            self.say(random.choice(QUIPS["mug"]))
            self.snd("click", 0.3)
        elif math.hypot(vx - 450, vy - 42) < 20:
            self.taps["clock"] += 1
            self.snd("chime", 0.5)
            if self.taps["clock"] % 7 == 0:
                self.ghost_t = 16.0
                self.say("Часы встали. На горизонте чей-то корабль…", 4.0)
            else:
                self.say(random.choice(QUIPS["clock"]))
        elif inside(vx, vy, 4, 18, 52, 44):
            self.say(random.choice(QUIPS["map"]))
            self.snd("click", 0.3)
        elif inside(vx, vy, 2, 60, 60, 34):
            self.taps["shelf"] += 1
            if self.taps["shelf"] % 5 == 0:
                self.say("Из дневника: «Подставных выдаёт мелочь. Всегда мелочь.»", 4.5)
                self.snd("chime", 0.5)
            else:
                self.say(random.choice(QUIPS["shelf"]))
                self.snd("click", 0.3)
        elif inside(vx, vy, 438, 90, 40, 72) or inside(vx, vy, 264, 166, 148, 54):
            self.static_t = 0.6
            self.snd("crackle", 0.6)
        elif inside(vx, vy, WX, WY, WW, HOR):
            self.spawn_star(vx, vy)
            self.snd("star", 0.4)
            self.taps["star"] += 1
            if self.taps["star"] % 3 == 0:
                self.say("Загадай желание.")
        elif inside(vx, vy, WX, WY + HOR, WW, WH - HOR):
            self.ripples.append([vx, vy, 2.0, 1.0])
            self.snd("splash", 0.3)
            if random.random() < 0.2:
                self.say("Плеск!")
        elif inside(vx, vy, 60, 0, 360, 22):
            self.say(random.choice(QUIPS["wall"]), 1.6)

    def menu_touch(self, vx, vy):
        if self.menu == "pause":
            if inside(vx, vy, 170, 96, 140, 34):
                self.menu = None
            elif inside(vx, vy, 170, 140, 140, 34):
                self.menu, self.menu_prev = "settings", "pause"
            elif inside(vx, vy, 170, 184, 140, 34):
                self.menu = None
                self.stroke, self.ship_tex = None, None
                self.state = "title"
            self.snd("click", 0.5)
        else:
            for key, y in (("music", 46), ("sfx", 78), ("voice", 110), ("speed", 142)):
                if inside(vx, vy, 200, y - 6, 200, 26):
                    self.drag = key
                    self.set_slider(vx)
                    return True
            for k in range(3):
                if inside(vx, vy, 210 + k * 62, 172, 58, 22):
                    self.cfg["text"] = k
                    self.snd("click", 0.5)
            if inside(vx, vy, 210, 204, 80, 22):
                self.cfg["shake"] = not self.cfg["shake"]
                self.snd("click", 0.5)
            if inside(vx, vy, 170, 230, 140, 24):
                self.menu = self.menu_prev
                self.save()
                self.snd("click", 0.5)
        return True

    def set_slider(self, vx):
        v = min(1.0, max(0.0, (vx - 210) / 180.0))
        self.cfg[self.drag] = v
        if self.sfx:
            self.sfx.apply()

    def shop_touch(self, vx, vy):
        if inside(vx, vy, 150, 234, 180, 30):
            self.day += 1
            self.snd("click")
            self.start_day()
            return
        for k, it in enumerate(SHOP):
            x, y = 16 + (k % 2) * 232, 40 + (k // 2) * 64
            if inside(vx, vy, x, y, 216, 58):
                self.buy(it[0])

    def on_touch_move(self, touch):
        vx, vy = self.vpos(touch)
        if self.drag:
            self.set_slider(vx)
        elif self.stroke is not None and touch.uid == self.stroke_uid:
            self.stroke.append((vx, vy))
            if len(self.stroke) % 4 == 0:
                self.snd("scratch", 0.35)
        return True

    def on_touch_up(self, touch):
        if self.drag:
            self.drag = None
            self.save()
        elif self.stroke is not None and touch.uid == self.stroke_uid:
            pts, k = self.stroke, self.stroke_k
            self.stroke = None
            ex, ey, ew, eh = self.entry_rect(k)
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            if max(xs) - min(xs) >= ew * 0.55 and abs(sum(ys) / len(ys) - (ey + eh / 2)) < 10:
                ri = self.reg[self.page * 5 + k]["ri"]
                self.struck[ri] = [(x, min(max(y, ey + 3), ey + eh - 2)) for x, y in pts]
                self.snd("good", 0.4)
                self.state, self.st_t = "pause", 0.0
        return True

    def entry_rect(self, k):
        return (10, ENT_Y0 + k * ENT_H, 238, ENT_H)

    # ---- примитивы рисования
    def R(self, x, y, w, h, c, a=1.0):
        s = self.s
        x0, x1 = round(self.ox + x * s), round(self.ox + (x + w) * s)
        yt, yb = round(self.oy + (H - y) * s), round(self.oy + (H - y - h) * s)
        Color(c[0], c[1], c[2], a)
        Rectangle(pos=(x0, yb), size=(max(1, x1 - x0), max(1, yt - yb)))

    def IMG(self, tex, x, y, w, h, a=1.0, col=(1, 1, 1)):
        s = self.s
        x0, x1 = round(self.ox + x * s), round(self.ox + (x + w) * s)
        yt, yb = round(self.oy + (H - y) * s), round(self.oy + (H - y - h) * s)
        Color(col[0], col[1], col[2], a)
        Rectangle(texture=tex, pos=(x0, yb), size=(x1 - x0, yt - yb))

    def Q(self, pts, c, a):
        flat = []
        for x, y in pts:
            flat += [self.ox + x * self.s, self.oy + (H - y) * self.s]
        Color(c[0], c[1], c[2], a)
        Quad(points=flat)

    def LINE(self, pts, c, a, wd):
        flat = []
        for x, y in pts:
            flat += [self.ox + x * self.s, self.oy + (H - y) * self.s]
        if len(flat) >= 4:
            Color(c[0], c[1], c[2], a)
            Line(points=flat, width=max(1.0, wd * self.s))

    def tex_of(self, text, size):
        px = max(6, int(size * self.s))
        key = (text, px)
        tex = self.cache.get(key)
        if tex is None:
            if len(self.cache) > 900:
                self.cache.clear()
            lab = CoreLabel(text=text, font_size=px)
            lab.refresh()
            tex = self.cache[key] = lab.texture
        return tex

    def T(self, text, x, y, size, c, a=1.0, anchor="l"):
        tex = self.tex_of(text, size)
        tw, th = tex.size
        px_x = self.ox + x * self.s
        if anchor == "c":
            px_x -= tw / 2
        elif anchor == "r":
            px_x -= tw
        Color(c[0], c[1], c[2], a)
        Rectangle(texture=tex, pos=(round(px_x), round(self.oy + (H - y) * self.s - th)),
                  size=(tw, th))

    def btn(self, x, y, w, h, label, base, on=True, fs=9.5):
        c = base if on else tuple(v * 0.45 for v in base)
        up = lambda f: tuple(min(1.0, v * f) for v in c)
        self.R(x + 2, y + 3, w, h, (0, 0, 0), 0.45)
        self.R(x, y, w, h, up(0.5))
        self.R(x + 1, y + 1, w - 2, h - 2, c)
        self.R(x + 1, y + 1, w - 2, 2, up(1.45))
        self.R(x + 1, y + h - 3, w - 2, 2, up(0.65))
        self.T(label, x + w / 2.0, y + h / 2.0 - fs * 0.6, fs, (1, 1, 1) if on else (0.6, 0.6, 0.6), 1, "c")

    def panel(self, x, y, w, h):
        self.R(x + 3, y + 4, w, h, (0, 0, 0), 0.5)
        self.R(x, y, w, h, (0.1, 0.06, 0.03))
        self.R(x + 2, y + 2, w - 4, h - 4, (0.36, 0.23, 0.12))
        self.R(x + 4, y + 4, w - 8, h - 8, (0.2, 0.13, 0.07))
        self.R(x + 4, y + 4, w - 8, 1, (0.5, 0.35, 0.2))

    def coin(self, x, y):
        self.R(x + 1, y, 5, 7, (0.95, 0.75, 0.15))
        self.R(x, y + 1, 7, 5, (0.95, 0.75, 0.15))
        self.R(x + 2, y + 1, 2, 4, (1, 0.93, 0.5))

    def heart(self, x, y, a):
        for r, row in enumerate(("0110110", "1111111", "0111110", "0011100", "0001000")):
            for cc, ch in enumerate(row):
                if ch == "1":
                    self.R(x + cc, y + r, 1, 1, (1, 0.35, 0.45), a)

    # ---- кадр
    def draw(self):
        w, h = self.size
        self.s = min(w / float(W), h / float(H))
        self.bx = self.x + (w - W * self.s) / 2
        self.by = self.y + (h - H * self.s) / 2
        amp = 0.0
        if self.cfg["shake"] and self.state in ("arrive", "radio", "decide", "leave", "strike", "pause"):
            amp = max(0, self.stress - 50) / 50.0 * 0.7
        self.ox = self.bx + random.uniform(-amp, amp) * self.s
        self.oy = self.by + random.uniform(-amp, amp) * self.s
        self.canvas.clear()
        with self.canvas:
            Color(0.02, 0.03, 0.06, 1)
            Rectangle(pos=self.pos, size=self.size)
            st = self.state
            if st == "loading":
                self.T("Загрузка…", W / 2.0, H / 2.0 - 8, 14, (0.9, 0.85, 0.7), 1, "c")
            elif st == "title":
                self.draw_title()
            elif st == "shop":
                self.draw_shop()
            else:
                self.draw_window()
                self.IMG(self.tex_room, 0, 0, W, H)
                self.draw_room()
                if st == "intro":
                    self.draw_intro()
                elif st == "dayend":
                    self.draw_dayend()
                elif st == "gameover":
                    self.draw_gameover()
            self.draw_toast()
            if self.menu == "pause":
                self.draw_pause()
            elif self.menu == "settings":
                self.draw_settings()

    def draw_toast(self):
        text, until = self.toast
        if text and self.t < until:
            tex = self.tex_of(text, 8.5)
            w = tex.size[0] / self.s + 16
            y = 26 if self.state == "shop" else (252 if self.state == "title" else 30)
            self.R(W / 2.0 - w / 2, y - 3, w, 17, (0.05, 0.04, 0.03), 0.82)
            self.R(W / 2.0 - w / 2, y - 3, w, 1, (0.9, 0.75, 0.4), 0.7)
            self.T(text, W / 2.0, y, 8.5, (1, 0.95, 0.8), 1, "c")

    def draw_title(self):
        t = self.t
        self.IMG(self.tex_title, 0, 0, W, H)
        for x, y in self.twinkle:
            self.R(x, y, 1, 1, (1, 1, 1), 0.2 + 0.5 * (0.5 + 0.5 * math.sin(t * 2 + x)))
        a = 26 * math.sin(t * 0.5)
        lx, ly = 380, 82
        boost = 1 + 2.5 * self.lamp_flash
        for wd, al in ((52, 0.05), (32, 0.07), (14, 0.09)):
            self.Q([(lx, ly - 2), (lx, ly + 2), (0, 90 + a + wd), (0, 90 + a - wd)],
                   (1, 0.93, 0.68), min(0.6, al * boost))
        if self.lamp_flash > 0:
            self.IMG(self.tex_glow, lx - 70, ly - 70, 140, 140, min(1.0, self.lamp_flash), (1, 0.9, 0.6))
        for s in self.shots:
            self.LINE([(s[0], s[1]), (s[0] - s[2] * 0.12, s[1] - s[3] * 0.12)], (1, 1, 1), min(1, s[4] * 1.5), 1.4)
        for r in self.ripples:
            self.ring(r)
        jx = 3 * math.sin(t * 40) * self.jig
        self.T("СМЕНА", 170 + jx, 30, 46, (1, 0.9, 0.62), 1, "c")
        self.T("The Watch", 170, 86, 13, (0.8, 0.82, 0.9), 1, "c")
        self.R(208, 88, 40, 13, (0.75, 0.25, 0.15))
        self.R(208, 88, 40, 1, (1, 0.6, 0.4))
        self.T("BETA", 228, 88.5, 8.5, (1, 1, 1), 1, "c")
        self.T(VERSION, W - 8, H - 14, 8, (0.8, 0.82, 0.9), 0.8, "r")
        self.T("Звание: " + rank_of(self.d["best"]), 170, 108, 9, (1, 0.85, 0.5), 1, "c")
        self.T("Рекорд: %d дн." % self.d["best"], 170, 121, 8, (0.8, 0.82, 0.9), 0.9, "c")
        self.coin(116, 125)
        self.T("%d" % self.d["coins"], 126, 122, 8, (1, 0.9, 0.5), 0.9)
        self.btn(100, 136, 140, 32, "ИГРАТЬ", (0.18, 0.5, 0.24))
        self.btn(100, 176, 140, 32, "НАСТРОЙКИ", (0.4, 0.32, 0.18))
        self.btn(100, 216, 140, 32, "ВЫХОД", (0.32, 0.32, 0.4))
        self.IMG(self.tex_vig, 0, 0, W, H, 0.7, (0, 0, 0))

    def ring(self, r):
        pts = [(r[0] + r[2] * math.cos(a / 8.0 * math.pi), r[1] + r[2] * 0.35 * math.sin(a / 8.0 * math.pi))
               for a in range(17)]
        self.LINE(pts, (0.8, 0.9, 1), max(0.0, r[3]) * 0.6, 1)

    def draw_window(self):
        t = self.t
        self.IMG(self.tex_scene, WX, WY, WW, WH)
        for k, (x, y) in enumerate(self.twinkle):
            self.R(WX + x, WY + y, 1, 1, (1, 1, 1), 0.15 + 0.5 * (0.5 + 0.5 * math.sin(t * 1.7 + k * 2)))
        if int(t / 1.1) % 2 == 0:
            self.R(WX + 236, WY + HOR - 6, 1, 1, (1, 0.3, 0.2), 0.9)
        for s in self.shots:
            self.LINE([(s[0], s[1]), (s[0] - s[2] * 0.12, s[1] - s[3] * 0.12)], (1, 1, 1), min(1, s[4] * 1.5), 1.3)
        for b in self.birds:
            f = 1 if math.sin(t * 11 + b[3]) > 0 else 0
            c = (0.02, 0.03, 0.07)
            self.R(b[0] - 4, b[1] + f, 3, 1, c, 0.9)
            self.R(b[0] - 1, b[1] + 1, 3, 1, c, 0.9)
            self.R(b[0] + 2, b[1] + f, 3, 1, c, 0.9)
        if self.ghost_t > 0:
            p = 1 - self.ghost_t / 16.0
            gx = WX + WW + 60 - p * (WW + 120)
            self.IMG(self.tex_ghost, gx - 36, WY + HOR + 6 - 40, 72, 51, 0.28 + 0.12 * math.sin(t * 3), (0.6, 0.85, 1))
        for f in self.fish:
            q = f[1] / 0.7
            if q < 1:
                self.R(f[0] - 2, WY + 112 - 13 * math.sin(math.pi * q), 5, 2, (0.8, 0.9, 1), 0.9)
        for r in self.ripples:
            self.ring(r)
        for r in range(11):
            y = WY + HOR + 4 + r * 5
            for k in range(7):
                x = (k * 62 + t * (6 + r) + r * 17) % (WW + 40) - 20
                self.R(WX + x, y + math.sin(t * 1.3 + k + r), 8 + r * 2, 1, (0.62, 0.75, 0.98), 0.10 + 0.012 * r)
        bx0, by0 = W / 2.0, WY + 4
        tx, ty = self.beam_x, WLN - 10
        for wd, al in ((52, 0.045), (34, 0.06), (16, 0.07)):
            self.Q([(bx0 - 6, by0), (bx0 + 6, by0), (tx + wd, ty), (tx - wd, ty)],
                   (1, 0.93, 0.68), al * (1 + 0.25 * math.sin(t * 2)))
        for v, u in self.dust:
            x = bx0 + (tx - bx0) * v + u * (6 + 40 * v)
            self.R(x, by0 + (ty - by0) * v, 1, 1, (1, 0.96, 0.75), 0.55)
        if self.ship_tex is not None:
            sc = self.ship_sc
            wl = self.ship_wl + 1.2 * math.sin(t * 1.6)
            self.IMG(self.ship_tex, self.ship_x - 85 * sc, wl - 96 * sc, 170 * sc, 120 * sc, self.ship_a)
            for k in range(9):
                x = self.ship_x - 70 * sc + ((k * 17 + t * 9) % 150) * sc
                self.R(x, wl + 1, 7 * sc, 1, (0.85, 0.92, 1), 0.35 * self.ship_a)
        wt = self.weather
        if wt == "fog":
            for k in range(4):
                x = (t * (4 + k) + k * 110) % (WW + 240) - 120
                self.IMG(self.tex_glow, WX + x - 130, WY + 50 + k * 16, 260, 46, 0.16, (0.75, 0.8, 0.9))
        if wt in ("rain", "storm"):
            for k in range(70):
                y = (k * 29 + t * 230) % (WH + 20) - 10
                x = (k * 53) % WW + y * 0.12
                self.R(WX + x % WW, WY + y, 1, 5, (0.7, 0.8, 1), 0.28)
            for k in range(16):
                gx, gy = (k * 83) % (WW - 10) + 5, (k * 41 + t * (3 + k % 3)) % WH
                self.R(WX + gx, WY + gy, 1, 2, (0.8, 0.9, 1), 0.35)
        if self.flash > 0:
            self.R(WX, WY, WW, WH, (0.85, 0.9, 1), self.flash * 0.45)
            if self.flash > 0.4 and len(self.bolt) > 1:
                self.LINE(self.bolt, (1, 1, 1), 0.95, 1.6)
        for x, y, l in self.glints:
            self.R(x, y, 3, 1, (1, 1, 1), min(1.0, l * 3))
            self.R(x + 1, y - 1, 1, 3, (1, 1, 1), min(1.0, l * 3) * 0.7)

    def draw_room(self):
        t, st = self.t, self.state
        fl = 1 + 0.12 * math.sin(t * 7) + 0.08 * math.sin(t * 13.3)
        if self.d["plant"]:
            sway = math.sin(t * 1.2)
            self.IMG(self.tex_plant, 118 + sway * 0.6, 104, 36, 46)
        if self.d["cat"]:
            br = 1 + 0.035 * math.sin(t * 1.8)
            self.IMG(self.tex_cat, 320, 148 - 28 * br, 48, 28 * br)
            if int(t * 0.5) % 3 == 0:
                self.T("z", 366, 112 - (t * 5) % 10, 7, (0.9, 0.95, 1), 0.7)
        self.IMG(self.tex_glow, 98 - 80, 134 - 80, 160, 160, 0.20 * fl + 0.25 * self.lamp_flash, (1, 0.72, 0.35))
        self.IMG(self.tex_glow, 250 - 220, 205 - 110, 440, 220, 0.07, (1, 0.7, 0.4))
        self.IMG(self.tex_glow, 240 - 190, 120 - 90, 380, 180, 0.06, (0.5, 0.62, 1))
        for k in range(5):
            ph = (t * 0.5 + k * 0.2) % 1.0
            self.R(382 + 3 * math.sin(ph * 6 + k), 132 - ph * 18, 2, 2, (1, 1, 1), 0.28 * (1 - ph))
        # потолочная панель: ночь, монеты, предметы, кнопка меню
        self.T("Ночь %d  ·  судно %d / %d" % (self.day, min(self.i + 1, len(self.ships)),
                                           len(self.ships)), 12, 1.5, 8, (0.9, 0.82, 0.65))
        self.coin(206, 2)
        self.T("%d" % self.d["coins"], 216, 1.5, 8, (1, 0.9, 0.5))
        extra = []
        if self.d["lupa"]:
            extra.append("лупа %d" % self.d["lupa"])
        if self.d["charm"]:
            extra.append("талисман %d" % self.d["charm"])
        if extra:
            self.T(" · ".join(extra), 262, 1.5, 7.5, (0.75, 0.85, 1))
        for k in range(3):
            self.R(458, 3 + k * 3, 14, 2, (0.9, 0.82, 0.65))
        self.draw_folder()
        self.draw_radio()
        on = st == "decide"
        self.btn(260, 232, 104, 30, "ВПУСТИТЬ", (0.18, 0.5, 0.24), on)
        self.btn(372, 232, 104, 30, "ОТКАЗАТЬ", (0.6, 0.18, 0.16), on)
        if self.d["lupa"] > 0:
            self.btn(416, 206, 54, 16, "ЛУПА x%d" % self.d["lupa"], (0.45, 0.36, 0.12),
                     st in ("radio", "decide"), 7.5)
        for h in self.hearts:
            self.heart(h[0], h[1], min(1.0, h[2]))
        if self.stress >= 50:
            self.IMG(self.tex_vig, 0, 0, W, H, (self.stress - 50) / 50.0 * 0.55, (0.7, 0, 0))
        self.IMG(self.tex_vig, 0, 0, W, H, 0.85, (0, 0, 0))
        if self.stroke is not None:
            self.LINE(self.stroke, (0.8, 0.1, 0.1), 0.95, 1.7)
            self.pencil(*self.stroke[-1])

    def draw_folder(self):
        ts = TS[self.cfg["text"]]
        pages = max(1, (len(self.reg) + 4) // 5)
        self.page = min(self.page, pages - 1)
        self.T("ЖУРНАЛ РЕЙСОВ", 14, 166, 7, INK)
        self.T("за смену: %d" % len(self.reg), 244, 166, 7, INK, 1, "r")
        wob = max(0, self.stress - 60) / 40.0
        for k, sh in enumerate(self.reg[self.page * 5:self.page * 5 + 5]):
            t = sh["truth"]
            y = ENT_Y0 + 1 + k * ENT_H + wob * math.sin(self.t * 3 + k)
            dim = 0.55 if sh["ri"] in self.struck else 1.0
            if sh["ri"] == self.hint:
                self.R(10, ENT_Y0 + k * ENT_H, 238, ENT_H - 1, (1, 0.85, 0.2), 0.35 + 0.15 * math.sin(self.t * 6))
            self.T("%s · %s · борт №%d" % (t["captain"], t["cargo"], t["number"]),
                   14, y, 7.2 * ts, INK, dim)
            self.T("%s %s %s · %s · %s корпус · %s флаг" % (
                t["route"][0], ARROW, t["route"][1], masts_word(t["masts"]),
                t["hull"], t["flag"]), 14, y + 8, 5.8 * ts, (0.32, 0.22, 0.16), dim)
        for ri, pts in self.struck.items():
            if self.page * 5 <= ri < self.page * 5 + 5:
                self.LINE(pts, (0.78, 0.1, 0.1), 0.9, 1.6)
        for r in range(4):
            self.R(18 + r, 260 + r, 1, 8 - 2 * r, INK)
            self.R(238 - r, 260 + r, 1, 8 - 2 * r, INK)
        self.T("%d / %d" % (self.page + 1, pages), 129, 260, 6.5, INK, 1, "c")

    def draw_radio(self):
        st, ts = self.state, TS[self.cfg["text"]]
        self.T("РАДИО", 270, 168, 5.5, (0.35, 0.65, 0.45))
        talking = st == "radio"
        self.R(402, 169, 5, 5, (1, 0.2, 0.15) if talking else (0.3, 0.08, 0.08))
        g = (0.55, 1.0, 0.65)
        if st == "arrive" or self.static_t > 0:
            for _ in range(8):
                self.R(270 + random.randint(0, 130), 180 + random.randint(0, 34),
                       random.randint(4, 18), 1, g, 0.3)
        if st in ("radio", "decide", "leave") and self.static_t <= 0:
            rem = int(self.typed) if st == "radio" else 999
            for li, line in enumerate(self.lines):
                part = line[:max(0, rem)]
                if part:
                    self.T(part, 270, 177 + li * 10, 7.2 * ts, g)
                rem -= len(line) + 1
        elif st == "strike":
            if int(self.t * 2) % 2 == 0 or self.stroke is not None:
                self.T("ВЫЧЕРКНИ РЕЙС", 270, 182, 8, (1, 0.8, 0.4))
            self.T("проведи пальцем по записи", 270, 196, 6.3, g, 0.9)
            self.T("в папке слева", 270, 205, 6.3, g, 0.9)

    def pencil(self, x, y):
        dx, dy = 0.55, -0.83
        nx, ny = -dy, dx

        def pt(l, w):
            return (x + dx * l + nx * w, y + dy * l + ny * w)

        self.Q([pt(0, 0), pt(0, 0.1), pt(9, 2.6), pt(9, -2.6)], (0.85, 0.7, 0.45), 1)
        self.Q([pt(0, 0), pt(0, 0.1), pt(2.8, 0.9), pt(2.8, -0.9)], (0.15, 0.12, 0.12), 1)
        self.Q([pt(9, -2.6), pt(9, 2.6), pt(36, 2.6), pt(36, -2.6)], (0.75, 0.12, 0.12), 1)
        self.Q([pt(9, -2.6), pt(9, -1.4), pt(36, -1.4), pt(36, -2.6)], (0.95, 0.4, 0.35), 1)
        self.Q([pt(36, -2.6), pt(36, 2.6), pt(40, 2.6), pt(40, -2.6)], (0.7, 0.7, 0.72), 1)
        self.Q([pt(40, -2.6), pt(40, 2.6), pt(44, 2.6), pt(44, -2.6)], (0.9, 0.55, 0.6), 1)

    # ---- экраны поверх сцены
    def draw_intro(self):
        a = min(1.0, self.st_t * 2) * (1 if self.st_t < 3.0 else max(0.0, 3.4 - self.st_t) * 2.5)
        self.R(0, 0, W, H, (0, 0, 0), 0.62 * a)
        self.T("НОЧЬ %d" % self.day, W / 2.0, 58, 30, (1, 0.9, 0.55), a, "c")
        self.T("Погода: " + WEATHER[self.weather], W / 2.0, 98, 12, (0.85, 0.9, 1), a, "c")
        self.T("Звание: " + rank_of(self.d["best"]), W / 2.0, 118, 10, (1, 0.85, 0.5), a, "c")
        if self.day == 1:
            for k, line in enumerate(("Сверяй радио и корабль с папкой.",
                                      "Подставных выдаёт мелочь.",
                                      "Ошибка копит стресс, и он не проходит сам.",
                                      "После решения проведи пальцем по записи, чтобы вычеркнуть рейс.")):
                self.T(line, W / 2.0, 150 + k * 16, 9, (0.9, 0.9, 0.9), a, "c")
        else:
            self.T("Коснись, чтобы начать", W / 2.0, 210, 8, (0.7, 0.7, 0.7), a * 0.8, "c")

    def draw_dayend(self):
        self.R(0, 0, W, H, (0, 0, 0), 0.82)
        if self.win:
            self.T("ТЫ ВЫДЕРЖАЛ 30 СМЕН", W / 2.0, 36, 24, (1, 0.9, 0.5), 1, "c")
            self.T("Маяк в безопасности.", W / 2.0, 70, 12, (1, 1, 1), 1, "c")
        else:
            self.T("СМЕНА %d ЗАКРЫТА" % self.day, W / 2.0, 36, 24, (1, 0.9, 0.5), 1, "c")
        if self.rankup:
            self.T("Новое звание: " + self.rankup + "  (+20 монет)", W / 2.0, 76, 11, (0.6, 0.9, 1), 1, "c")
        if self.day_errors == 0:
            self.T("Идеальная смена!  (+10 монет)", W / 2.0, 104, 14, (0.5, 1, 0.5), 1, "c")
        else:
            self.T("Ошибок за смену: %d" % self.day_errors, W / 2.0, 104, 14, (1, 0.6, 0.5), 1, "c")
        k = self.stress / 100.0
        self.R(140, 146, 200, 14, (0.1, 0.08, 0.06))
        self.R(141, 147, 198 * k, 12, (0.3 + 0.6 * k, 0.8 - 0.6 * k, 0.2))
        self.T("Стресс: %d%%" % self.stress, W / 2.0, 166, 10, (1, 1, 1), 1, "c")
        self.coin(188, 192)
        self.T("+%d за смену, всего %d" % (self.day_coins, self.d["coins"]), 200, 189, 10, (1, 0.9, 0.5))
        self.T("Коснись экрана", W / 2.0, 240, 9, (0.7, 0.7, 0.7), 1, "c")

    def draw_shop(self):
        self.R(0, 0, W, H, (0.12, 0.08, 0.05))
        for y in range(0, H, 22):
            self.R(0, y, W, 1, (0.08, 0.05, 0.03))
        self.T("ЛАВКА СМОТРИТЕЛЯ", 16, 10, 15, (1, 0.9, 0.6))
        self.coin(W - 70, 12)
        self.T("%d" % self.d["coins"], W - 58, 9, 12, (1, 0.9, 0.5))
        k = self.stress / 100.0
        self.T("стресс", 262, 12, 8, (0.85, 0.85, 0.85))
        self.R(300, 12, 70, 8, (0.05, 0.04, 0.03))
        self.R(301, 13, 68 * k, 6, (0.3 + 0.6 * k, 0.8 - 0.6 * k, 0.2))
        for n, it in enumerate(SHOP):
            key, name, desc, price = it
            x, y = 16 + (n % 2) * 232, 40 + (n // 2) * 64
            owned = self.d.get(key) if key in ("cat", "plant") else None
            self.panel(x, y, 216, 58)
            self.T(name, x + 10, y + 8, 11, (1, 0.92, 0.7))
            self.T(desc, x + 10, y + 26, 7.5, (0.85, 0.8, 0.7))
            if owned:
                self.T("куплено", x + 10, y + 40, 8, (0.5, 1, 0.5))
            else:
                if key in ("lupa", "charm"):
                    self.T("есть: %d" % self.d[key], x + 10, y + 40, 7.5, (0.7, 0.85, 1))
                can = self.d["coins"] >= price
                self.coin(x + 166, y + 40)
                self.T("%d" % price, x + 176, y + 37, 10, (1, 0.9, 0.5) if can else (0.7, 0.4, 0.4))
        self.btn(150, 234, 180, 30, "К СЛЕДУЮЩЕЙ СМЕНЕ", (0.18, 0.5, 0.24), True, 9)

    def draw_gameover(self):
        self.R(0, 0, W, H, (0, 0, 0), 0.85)
        self.T("СМЕНА ПРОВАЛЕНА", W / 2.0, 14, 22, (1, 0.35, 0.3), 1, "c")
        self.T("Ты продержался дней: %d    Рекорд: %d" % (self.day - 1, self.d["best"]),
               W / 2.0, 46, 10, (1, 1, 1), 1, "c")
        self.T("Журнал ошибок:", 20, 72, 9, (1, 0.9, 0.5))
        y = 88
        for e in self.errors[-5:]:
            self.T("День %d, судно %d: %s" % (e["day"], e["n"], e["kind"]), 20, y, 8, (1, 0.7, 0.6))
            if e["diffs"]:
                txt = "; ".join("%s: в папке %s, пришло %s" % (
                    LABEL[f], fmt(f, a), fmt(f, b)) for f, a, b in e["diffs"])
            else:
                txt = "Рейс был настоящим"
            self.T(txt, 28, y + 10, 7.2, (0.85, 0.85, 0.85))
            y += 31
        if self.st_t > 1.0:
            self.T("Коснись экрана", W / 2.0, 254, 8, (0.7, 0.7, 0.7), 1, "c")

    def draw_pause(self):
        self.R(0, 0, W, H, (0, 0, 0), 0.6)
        self.panel(150, 44, 180, 188)
        self.T("ПАУЗА", W / 2.0, 58, 18, (1, 0.9, 0.6), 1, "c")
        self.btn(170, 96, 140, 34, "ПРОДОЛЖИТЬ", (0.18, 0.5, 0.24))
        self.btn(170, 140, 140, 34, "НАСТРОЙКИ", (0.4, 0.32, 0.18))
        self.btn(170, 184, 140, 34, "В МЕНЮ", (0.5, 0.2, 0.18))

    def draw_settings(self):
        self.R(0, 0, W, H, (0, 0, 0), 0.65)
        self.panel(60, 10, 360, 252)
        self.T("НАСТРОЙКИ", W / 2.0, 20, 14, (1, 0.9, 0.6), 1, "c")
        self.T(VERSION, 410, 20, 7, (0.7, 0.7, 0.75), 0.8, "r")
        rows = (("Музыка", "music", 46), ("Звуки", "sfx", 78), ("Голос радио", "voice", 110),
                ("Скорость печати", "speed", 142))
        for label, key, y in rows:
            self.T(label, 76, y + 2, 9, (1, 0.95, 0.8))
            v = self.cfg[key]
            self.R(210, y + 8, 180, 4, (0.08, 0.05, 0.03))
            self.R(210, y + 8, 180 * v, 4, (0.9, 0.7, 0.3))
            self.R(210 + 180 * v - 3, y + 2, 6, 16, (0.95, 0.88, 0.6))
        self.T("Размер текста", 76, 176, 9, (1, 0.95, 0.8))
        for k, name in enumerate(("мелкий", "обычный", "крупный")):
            on = self.cfg["text"] == k
            self.btn(210 + k * 62, 172, 58, 22, name, (0.45, 0.35, 0.15) if on else (0.22, 0.16, 0.1), True, 7.5)
        self.T("Тряска экрана", 76, 208, 9, (1, 0.95, 0.8))
        self.btn(210, 204, 80, 22, "ВКЛ" if self.cfg["shake"] else "ВЫКЛ",
                 (0.18, 0.5, 0.24) if self.cfg["shake"] else (0.5, 0.2, 0.18), True, 8.5)
        self.btn(170, 230, 140, 24, "НАЗАД", (0.32, 0.32, 0.4), True, 9)


class WatchApp(App):
    def build(self):
        Window.clearcolor = (0.02, 0.03, 0.06, 1)
        return Game()


if __name__ == "__main__":
    WatchApp().run()
