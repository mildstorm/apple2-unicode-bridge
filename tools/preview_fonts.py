#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apple II Font Comparison & Preview Tool (tools/preview_fonts.py)
Renders sample Korean, Hanja, and ASCII characters across all available fonts
using the Apple II 14x16 HGR monochrome rasterizer.
"""

import os
import sys
from PIL import Image, ImageDraw

# Add project root to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

from unicode_server import HangulRasterizer

FONTS_DIR = os.path.join(ROOT_DIR, "fonts")

TEST_FONTS = [
    ("Galmuri14 (14px, y-offset=1)", os.path.join(FONTS_DIR, "Galmuri14.ttf"), 14, 1, False, False),
    ("Neo둥근모 (16px, box-center)", os.path.join(FONTS_DIR, "neodgm.ttf"), 16, 0, True, False),
    ("삼국지3글꼴 (16px, box-center)", os.path.join(FONTS_DIR, "Sam3KRFont.ttf"), 16, 0, True, False),
    ("도스고딕 (16px, box-center)", os.path.join(FONTS_DIR, "DOSGothic.ttf"), 16, 0, True, False),
    ("도스명조 (16px, box-center)", os.path.join(FONTS_DIR, "DOSMyungjo.ttf"), 16, 0, True, False),
    ("Galmuri11 (11px, box-center)", os.path.join(FONTS_DIR, "Galmuri11.ttf"), 11, 0, True, False),
    ("Windows 굴림 (14px)", r"C:\Windows\Fonts\gulim.ttc", 14, 0, False, False),
    ("NotoSerif (14px, vector)", os.path.join(FONTS_DIR, "NotoSerifCJK16.ttf"), 14, 0, False, True),
]

SAMPLE_CHARS = ['한', '글', '산', '山', 'A']

def main():
    print("=" * 70)
    print(" Apple II 14x16 HGR Multilingual Font Preview")
    print("=" * 70)

    # 1. Terminal ASCII Preview for key characters
    for name, path, size, y_off, box_center, force_vec in TEST_FONTS:
        if not os.path.exists(path):
            continue
        print(f"\n--- [Font] {name} ---")
        try:
            r = HangulRasterizer(font_path=path, font_size=size, y_offset=y_off, box_center=box_center, force_vector=force_vec)
            for ch in ['한', '글']:
                g = r.rasterize(ch)
                print(f" Char '{ch}':")
                for row in range(16):
                    b0, b1 = g[row*2], g[row*2+1]
                    line = ''
                    for c in range(7): line += '##' if (b0 & (1<<c)) else '..'
                    for c in range(7): line += '##' if (b1 & (1<<c)) else '..'
                    print(f"  {row:2d}: {line}")
        except Exception as e:
            print(f"  Error: {e}")

    # 2. Generate side-by-side PNG image
    active_fonts = [(name, path, size, y_off, box_center, force_vec) for name, path, size, y_off, box_center, force_vec in TEST_FONTS if os.path.exists(path)]
    if not active_fonts:
        return

    # Image layout: columns = active_fonts, rows = SAMPLE_CHARS
    char_w, char_h = 14, 16
    scale = 3
    col_w = (char_w * scale) + 16
    row_h = (char_h * scale) + 20
    header_h = 30
    img_w = len(active_fonts) * col_w + 40
    img_h = len(SAMPLE_CHARS) * row_h + header_h + 30

    img = Image.new('RGB', (img_w, img_h), (24, 24, 27))
    draw = ImageDraw.Draw(img)

    draw.text((10, 8), "Apple II 14x16 HGR Font Comparison", fill=(240, 240, 240))

    for col_idx, (name, path, size, y_off, box_center, force_vec) in enumerate(active_fonts):
        try:
            r = HangulRasterizer(font_path=path, font_size=size, y_offset=y_off, box_center=box_center, force_vector=force_vec)
        except Exception:
            continue

        x_start = 40 + col_idx * col_w
        short_name = name.split()[0]
        draw.text((x_start, header_h - 10), short_name, fill=(120, 200, 255))

        for row_idx, ch in enumerate(SAMPLE_CHARS):
            y_start = header_h + 15 + row_idx * row_h
            if col_idx == 0:
                draw.text((10, y_start + 12), f"'{ch}'", fill=(200, 200, 200))

            if ord(ch) >= 128:
                glyph = r.rasterize(ch)
                for gy in range(16):
                    b0, b1 = glyph[gy*2], glyph[gy*2+1]
                    for gx in range(7):
                        if b0 & (1 << gx):
                            for py in range(scale):
                                for px in range(scale):
                                    img.putpixel((x_start + gx*scale + px, y_start + gy*scale + py), (80, 255, 120))
                    for gx in range(7):
                        if b1 & (1 << gx):
                            for py in range(scale):
                                for px in range(scale):
                                    img.putpixel((x_start + (gx+7)*scale + px, y_start + gy*scale + py), (80, 255, 120))
            else:
                glyph = r.rasterize_7x16(ch)
                for gy in range(16):
                    b0 = glyph[gy]
                    for gx in range(7):
                        if b0 & (1 << gx):
                            for py in range(scale):
                                for px in range(scale):
                                    img.putpixel((x_start + (gx+3)*scale + px, y_start + gy*scale + py), (80, 255, 120))

    out_png = os.path.join(ROOT_DIR, "docs", "images", "font_comparison.png")
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    img.save(out_png)
    print(f"\n[Preview Image Saved] -> {out_png}")
    print("=" * 70)

if __name__ == "__main__":
    main()
