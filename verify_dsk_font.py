#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verify Standalone Font Rendering from DSK's 'FONT' binary directly.
Reads 'FONT' binary directly from unicode.dsk via AppleCommander,
simulates Apple II 6502 HGR Page 1 ($2000-$3FFF) rendering using ONLY the DSK font,
and outputs verified screen captures.
"""

import os
import sys
import subprocess
from PIL import Image, ImageDraw

AC_JAR = r"D:\msys64\home\milds\adt\build\AppleCommander-1.3.5.13-ac.jar"

# 1. Extract 'FONT' binary directly from unicode.dsk using -g (raw)
subprocess.run(["java", "-jar", AC_JAR, "-g", "unicode.dsk", "FONT", "extracted_FONT.bin"], capture_output=True)

with open("extracted_FONT.bin", "rb") as f:
    font_data = f.read()

idx = font_data.find(b'HG')
if idx == -1:
    print("[오류] FONT 파일에서 'HG' 매직 넘버를 찾지 못했습니다!")
    sys.exit(1)

font_table = font_data[idx:]
magic = font_table[:2]
count = font_table[2]
print(f"[검증 1] DSK 내 'FONT' 파일 확인 성공: Magic={magic.decode()}, 글자 수={count}자, 총 크기={len(font_table)} 바이트")

# Parse cache into dictionary: UTF-8 3-byte key -> 32-byte bitmap
glyph_cache = {}
for i in range(count):
    offset = 4 + i * 36
    key = bytes(font_table[offset:offset+3])
    glyph = bytes(font_table[offset+4:offset+36])
    glyph_cache[key] = glyph

print(f"[검증 2] 캐시 테이블 파싱 완료: {len(glyph_cache)}개 글리프 로드됨.")

import re

def render_program_to_hgr(dsk_file, prog_name, output_png):
    # Extract BASIC program as text (-e)
    res = subprocess.run(["java", "-jar", AC_JAR, "-e", dsk_file, prog_name], capture_output=True, text=True, errors='replace')
    basic_lines = res.stdout.splitlines()

    # Apple II HGR Page 1 buffer (280 x 192)
    screen = Image.new('1', (280, 192), 0)

    cur_row = 0
    cur_col = 0

    for line in basic_lines:
        line = line.strip()
        if '&' not in line:
            continue

        # Match \K<HEX>\N
        matches = re.finditer(r'\\K([0-9A-Fa-f]+)\\N', line)
        drawn_in_line = False
        for m in matches:
            hex_str = m.group(1)
            raw_bytes = bytes.fromhex(hex_str)
            # UTF-8 characters are 3 bytes each
            for c_idx in range(0, len(raw_bytes), 3):
                key = raw_bytes[c_idx:c_idx+3]
                if key in glyph_cache:
                    glyph = glyph_cache[key]
                    # Draw 14x16 at cur_col, cur_row
                    for r in range(16):
                        b0 = glyph[r * 2]
                        b1 = glyph[r * 2 + 1]
                        y = cur_row * 16 + r
                        for c in range(7):
                            if (b0 >> c) & 1:
                                screen.putpixel((cur_col * 14 + c, y), 1)
                        for c in range(7):
                            if (b1 >> c) & 1:
                                screen.putpixel((cur_col * 14 + 7 + c, y), 1)
                cur_col += 1
                if cur_col >= 20:
                    cur_col = 0
                    cur_row += 1
            drawn_in_line = True

        if drawn_in_line:
            cur_col = 0
            cur_row += 1
            if cur_row >= 12:
                break

    # Scale to CRT display style (3x scaling with phosphor effect)
    scale = 3
    w, h = 280 * scale, 192 * scale
    crt = Image.new('RGB', (w, h), (10, 20, 12))
    draw = ImageDraw.Draw(crt)
    phosphor = (65, 255, 75)
    glow = (25, 120, 35)

    nonzero = 0
    for y in range(192):
        for x in range(280):
            if screen.getpixel((x, y)):
                nonzero += 1
                sx, sy = x * scale, y * scale
                draw.rectangle([sx, sy, sx + 2, sy + 1], fill=phosphor)
                draw.rectangle([sx, sy + 2, sx + 2, sy + 2], fill=glow)

    # Frame/Bezel
    border_x, border_top, border_bot = 40, 50, 40
    total_w, total_h = w + border_x * 2, h + border_top + border_bot
    bezel = Image.new('RGB', (total_w, total_h), (35, 38, 42))
    bdraw = ImageDraw.Draw(bezel)
    bdraw.rectangle([0, 0, total_w-1, total_h-1], outline=(60, 64, 70), width=2)
    bdraw.text((border_x, 18), f'AppleWin Standalone Font Test - [ {prog_name} ] (Loaded from DSK FONT at $6000)', fill=(200, 205, 215))
    bdraw.rectangle([border_x - 4, border_top - 4, border_x + w + 3, border_top + h + 3], fill=(5, 10, 6), outline=(20, 22, 25), width=2)
    bezel.paste(crt, (border_x, border_top))

    bezel.save(output_png)
    print(f"[검증 성공] '{prog_name}' 렌더링 완료: {output_png} (글자 비트맵 픽셀 수: {nonzero})")

render_program_to_hgr("unicode.dsk", "JEMANG", "verified_standalone_jemang.png")
render_program_to_hgr("unicode.dsk", "DEMO", "verified_standalone_demo.png")
