# -*- coding: utf-8 -*-
"""Генерация PNG-иконок для PWA без сторонних библиотек.

Рисует тёмный скруглённый квадрат, кольцевую шкалу на 70% и цифры «70»
в стиле семисегментного индикатора. Запуск: python tools/make_icons.py
"""
import math
import os
import struct
import zlib

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons")

BG_TOP = (26, 31, 46)
BG_BOTTOM = (16, 19, 28)
TRACK = (42, 48, 64)
ACCENT = (108, 140, 255)
GOOD = (61, 220, 151)
DIGIT = (238, 241, 247)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(int(round(lerp(c1[i], c2[i], t))) for i in range(3))


def dist_segment(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def rounded_rect_contains(x, y, x0, y0, x1, y1, r):
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return math.hypot(x - cx, y - cy) <= r


def digit_segments(x0, y0, w, h, t):
    """Координаты сегментов a,b,c,d,e,f,g для одной цифры."""
    half = t / 2
    mid = y0 + h / 2
    return {
        "a": (x0 + half, y0, x0 + w - half, y0),
        "b": (x0 + w, y0 + half, x0 + w, mid - half),
        "c": (x0 + w, mid + half, x0 + w, y0 + h - half),
        "d": (x0 + half, y0 + h, x0 + w - half, y0 + h),
        "e": (x0, mid + half, x0, y0 + h - half),
        "f": (x0, y0 + half, x0, mid - half),
        "g": (x0 + half, mid, x0 + w - half, mid),
    }


def build_layout(size):
    s = float(size)
    cx = cy = s / 2
    radius = 0.335 * s
    thickness = 0.105 * s
    w = 0.170 * s
    h = 0.340 * s
    gap = 0.062 * s
    t = 0.046 * s
    total = 2 * w + gap
    left_x = cx - total / 2
    right_x = left_x + w + gap
    top_y = cy - h / 2
    d1 = digit_segments(left_x, top_y, w, h, t)
    d2 = digit_segments(right_x, top_y, w, h, t)
    return {
        "size": s, "cx": cx, "cy": cy,
        "radius": radius, "thickness": thickness, "digit_t": t,
        "digits": [("a", "b", "c"), ("a", "b", "c", "d", "e", "f")],
        "segments": [d1, d2],
    }


def pixel_color(x, y, L):
    s = L["size"]
    cx, cy = L["cx"], L["cy"]
    if not rounded_rect_contains(x, y, 0, 0, s, s, 0.22 * s):
        return (0, 0, 0, 0)

    # Фон: вертикальный градиент.
    col = mix(BG_TOP, BG_BOTTOM, y / s)

    dx, dy = x - cx, y - cy
    dist = math.hypot(dx, dy)
    R = L["radius"]
    T = L["thickness"]
    arc = 0.70 * 2 * math.pi

    # Угол от «12 часов» по часовой стрелке.
    theta = math.atan2(dx, -dy)
    if theta < 0:
        theta += 2 * math.pi

    start_pt = (cx, cy - R)
    end_pt = (cx + R * math.sin(arc), cy - R * math.cos(arc))
    cap_start = math.hypot(x - start_pt[0], y - start_pt[1]) <= T / 2
    cap_end = math.hypot(x - end_pt[0], y - end_pt[1]) <= T / 2

    if abs(dist - R) <= T / 2 or cap_start or cap_end:
        in_arc = theta <= arc
        if in_arc or cap_start or cap_end:
            t = min(1.0, theta / arc)
            col = mix(ACCENT, GOOD, t)
        else:
            col = TRACK

    # Цифры «70».
    for idx, segments in enumerate(L["segments"]):
        for name in L["digits"][idx]:
            ax, ay, bx, by = segments[name]
            if dist_segment(x, y, ax, ay, bx, by) <= L["digit_t"] / 2:
                col = DIGIT

    return (col[0], col[1], col[2], 255)


def render(size, ss=3):
    L = build_layout(size)
    rows = []
    step = 1.0 / ss
    for py in range(size):
        row = bytearray()
        for px in range(size):
            r = g = b = a = 0
            for sy in range(ss):
                for sx in range(ss):
                    c = pixel_color(px + (sx + 0.5) * step, py + (sy + 0.5) * step, L)
                    r += c[0] * c[3]
                    g += c[1] * c[3]
                    b += c[2] * c[3]
                    a += c[3]
            n = ss * ss
            if a == 0:
                row += b"\x00\x00\x00\x00"
            else:
                row += bytes((r // a, g // a, b // a, a // n))
        rows.append(bytes(row))
    return rows


def write_png(path, size, rows):
    raw = b"".join(b"\x00" + row for row in rows)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for size, name in ((512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png")):
        rows = render(size)
        write_png(os.path.join(OUT_DIR, name), size, rows)
        print("ok", name)


if __name__ == "__main__":
    main()
