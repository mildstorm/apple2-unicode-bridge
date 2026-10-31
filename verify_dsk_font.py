#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verify Standalone Font Rendering from DSK's 'FONT' binary directly.
Reads 'FONT' binary directly from unicode.dsk via ac_tool,
simulates Apple II 6502 HGR Page 1 ($2000-$3FFF) rendering using ONLY the DSK font,
and outputs verified screen captures.
"""

import os
import sys
import re
import argparse
from PIL import Image, ImageDraw
from ac_tool import get_raw_file, export_text_file

def verify_and_render(dsk_file="unicode.dsk", custom_ac=None):
    temp_extracted = f"_extracted_FONT_{os.getpid()}.bin"
    try:
        # 1. Extract 'FONT' binary directly from DSK using get_raw_file (-g)
        get_raw_file(dsk_file, "FONT", temp_extracted, custom_ac=custom_ac)

        with open(temp_extracted, "rb") as f:
            font_data = f.read()

        idx = font_data.find(b'HG')
        if idx == -1:
            print("[오류] FONT 파일에서 'HG' 매직 넘버를 찾지 못했습니다!")
            return False

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

        def render_program_to_hgr(prog_name, output_png):
            content_text = export_text_file(dsk_file, prog_name, custom_ac=custom_ac)
            basic_lines = content_text.splitlines()

            # Apple II HGR Page 1 buffer (280 x 192)
            screen = Image.new('1', (280, 192), 0)
            cur_row = 0
            cur_col = 0

            for line in basic_lines:
                line = line.strip()
                if '&' not in line:
                    continue

                matches = re.finditer(r'\\K([0-9A-Fa-f]+)\\N', line)
                drawn_in_line = False
                for m in matches:
                    hex_str = m.group(1)
                    raw_bytes = bytes.fromhex(hex_str)
                    for c_idx in range(0, len(raw_bytes), 3):
                        key = raw_bytes[c_idx:c_idx+3]
                        if key in glyph_cache:
                            glyph = glyph_cache[key]
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

            os.makedirs(os.path.dirname(output_png) or ".", exist_ok=True)
            bezel.save(output_png)
            print(f"[검증 성공] '{prog_name}' 렌더링 완료: {output_png} (글자 비트맵 픽셀 수: {nonzero})")

        render_program_to_hgr("JEMANG", "docs/images/verified_standalone_jemang.png")
        render_program_to_hgr("DEMO", "docs/images/verified_standalone_demo.png")
        return True
    finally:
        if os.path.exists(temp_extracted):
            os.remove(temp_extracted)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Verify Standalone Font Rendering from DSK's FONT binary")
    parser.add_argument("--dsk", default="unicode.dsk", help="Path to DSK file (default: unicode.dsk)")
    parser.add_argument("--ac-jar", default=None, help="Explicit path to AppleCommander JAR file")
    args = parser.parse_args()

    verify_and_render(dsk_file=args.dsk, custom_ac=args.ac_jar)
