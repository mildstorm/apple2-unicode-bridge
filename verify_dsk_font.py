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
from build_font_dsk import font_tag_hash

def verify_and_render(dsk_file="unicode.dsk", custom_ac=None, out_dir="docs/images"):
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

        # Parse cache into dictionary: 4-byte key -> 32-byte bitmap. The key is
        # the UTF-8 bytes, 0 past the end; for a character of up to 3 bytes the
        # 4th byte may be the font tag's hash (build_font_dsk.font_tag_hash).
        # The driver takes the first match, so keep the first of each key.
        glyph_cache = {}
        for i in range(count):
            offset = 4 + i * 36
            key = bytes(font_table[offset:offset+4])
            glyph = bytes(font_table[offset+4:offset+36])
            glyph_cache.setdefault(key, glyph)

        def utf8_len(lead):
            return 1 if lead < 0x80 else 2 if lead < 0xE0 else 3 if lead < 0xF0 else 4

        def font_tag_before(line, pos):
            # the last [F:name] of the & statement up to pos, as the driver reads it
            stmt = line[line.rfind('&', 0, pos) + 1:pos]
            tag = 0
            for m_tag in re.finditer(r'\[[Ff][^\]:]*(?::([^\]]*))?\]', stmt):
                tag = font_tag_hash(m_tag.group(1) or "")
            return tag

        def lookup(seq, tag):
            # as the driver's DRAW_CACHED_GLYPH: the character in the current
            # tag's font, else its untagged entry
            key = bytes(seq) + bytes(4 - len(seq))
            if len(seq) < 4 and tag and key[:3] + bytes([tag]) in glyph_cache:
                return glyph_cache[key[:3] + bytes([tag])]
            return glyph_cache.get(key)

        print(f"[검증 2] 캐시 테이블 파싱 완료: {len(glyph_cache)}개 글리프 로드됨.")

        # Apple II color masks
        COLOR_MASKS = {
            0: (0x00, 0x00), 1: (0x2A, 0x55), 2: (0x55, 0x2A), 3: (0x7F, 0x7F),
            4: (0x80, 0x80), 5: (0xAA, 0xD5), 6: (0xD5, 0xAA), 7: (0xFF, 0xFF),
        }
        COLOR_RGB = {
            0: (10, 20, 12),      # Black
            1: (65, 255, 75),     # Green
            2: (180, 100, 255),   # Violet
            3: (255, 255, 255),   # White
            4: (10, 20, 12),      # Black
            5: (255, 140, 50),    # Orange
            6: (80, 170, 255),    # Blue
            7: (255, 255, 255),   # White
        }

        def render_program_to_hgr(prog_name, output_png):
            content_text = export_text_file(dsk_file, prog_name, custom_ac=custom_ac)
            basic_lines = content_text.splitlines()

            # Apple II HGR Page 1 buffer (280 x 192), using RGB color buffer
            color_screen = Image.new('RGB', (280, 192), (10, 20, 12))
            draw_buffer = ImageDraw.Draw(color_screen)
            cur_row = 0
            cur_col = 0
            cur_color = 3
            draw_mode = 0 # 0=replace, 1=overlay, 2=xor

            for line in basic_lines:
                line = line.strip()
                upper_line = line.upper()

                if "HPLOT" in upper_line:
                    if "FOR I = 0 TO 191 STEP 16" in upper_line:
                        for i in range(0, 192, 16):
                            draw_buffer.line([(0, i), (279, i)], fill=(90, 100, 110))
                    elif "FOR I = 0 TO 279 STEP 28" in upper_line:
                        for i in range(0, 280, 28):
                            draw_buffer.line([(i, 0), (i, 191)], fill=(90, 100, 110))
                    else:
                        m_hp = re.search(r'HPLOT\s+(\d+)\s*,\s*(\d+)\s+TO\s+(\d+)\s*,\s*(\d+)', upper_line)
                        if m_hp:
                            x1, y1, x2, y2 = map(int, m_hp.groups())
                            draw_buffer.line([(x1, y1), (x2, y2)], fill=(90, 100, 110))

                if '&' not in line:
                    continue

                # Parse inline commands
                lower_line = line.lower()
                if '/overlay' in lower_line or '[m:overlay]' in lower_line:
                    draw_mode = 1
                elif '/replace' in lower_line or '[m:replace]' in lower_line:
                    draw_mode = 0
                elif '/xor' in lower_line or '[m:xor]' in lower_line:
                    draw_mode = 2

                m_pos = re.search(r'/pos\s+(\d+)\s+(\d+)', lower_line)
                if m_pos:
                    cur_col, cur_row = int(m_pos.group(1)), int(m_pos.group(2))

                # Detect /color or [c:...]
                m_col = re.search(r'\[c:([a-z0-9]+)\]', lower_line) or re.search(r'/color\s+([a-z0-9]+)', lower_line)
                if m_col:
                    c_tag = m_col.group(1)
                    if c_tag in ('green', '1', 'g'): cur_color = 1
                    elif c_tag in ('violet', 'purple', '2', 'v', 'p'): cur_color = 2
                    elif c_tag in ('white', '3', 'w', '7'): cur_color = 3
                    elif c_tag in ('orange', 'red', '5', 'o', 'r'): cur_color = 5
                    elif c_tag in ('blue', 'cyan', '6', 'b', 'c'): cur_color = 6
                    elif c_tag in ('black', '0', '4'): cur_color = 0

                matches = list(re.finditer(r'\\K([0-9A-Fa-f]+)\\N', line))
                drawn_in_line = False
                last_m_end = 0

                for m in matches:
                    # Check for spaces before this match
                    between = line[last_m_end:m.start()]
                    if last_m_end > 0 and ' ' in between:
                        cur_col += between.count(' ')
                    last_m_end = m.end()

                    hex_str = m.group(1)
                    raw_bytes = bytes.fromhex(hex_str)
                    tag = font_tag_before(line, m.start())
                    c_idx = 0
                    while c_idx < len(raw_bytes):
                        if raw_bytes[c_idx] == 0x20:
                            cur_col += 1
                            c_idx += 1
                            continue
                        n = utf8_len(raw_bytes[c_idx])
                        glyph = lookup(raw_bytes[c_idx:c_idx+n], tag)
                        c_idx += n
                        if glyph is not None:
                            # If replace mode, clear 14x16 box
                            if draw_mode == 0:
                                draw_buffer.rectangle([cur_col * 14, cur_row * 16, cur_col * 14 + 13, cur_row * 16 + 15], fill=(10, 20, 12))
                            
                            c_rgb = COLOR_RGB.get(cur_color, (255, 255, 255))
                            if cur_color in (3, 7): # White: 100% full-resolution, every dot preserved
                                for r in range(16):
                                    b0 = glyph[r * 2] & 0x7F
                                    b1 = glyph[r * 2 + 1] & 0x7F
                                    y = cur_row * 16 + r
                                    for c in range(7):
                                        if (b0 >> c) & 1:
                                            target_x = cur_col * 14 + c
                                            if draw_mode == 2:
                                                px = color_screen.getpixel((target_x, y))
                                                color_screen.putpixel((target_x, y), (255 - px[0], 255 - px[1], 255 - px[2]))
                                            else:
                                                color_screen.putpixel((target_x, y), c_rgb)
                                    for c in range(7):
                                        if (b1 >> c) & 1:
                                            target_x = cur_col * 14 + 7 + c
                                            if draw_mode == 2:
                                                px = color_screen.getpixel((target_x, y))
                                                color_screen.putpixel((target_x, y), (255 - px[0], 255 - px[1], 255 - px[2]))
                                            else:
                                                color_screen.putpixel((target_x, y), c_rgb)
                            else: # Colors (Green, Violet, Orange, Blue) with stroke expansion
                                color_mask = 0x2AAA if cur_color in (1, 5) else 0x1555
                                for r in range(16):
                                    b0 = glyph[r * 2] & 0x7F
                                    b1 = glyph[r * 2 + 1] & 0x7F
                                    val = b0 | (b1 << 7)
                                    if val:
                                        matching = val & color_mask
                                        wrong = val & ~color_mask
                                        shifted = (wrong << 1) & color_mask
                                        c_val = (matching | shifted) & 0x3FFF
                                        y = cur_row * 16 + r
                                        for c in range(14):
                                            if (c_val >> c) & 1:
                                                target_x = cur_col * 14 + c
                                                if draw_mode == 2:
                                                    px = color_screen.getpixel((target_x, y))
                                                    color_screen.putpixel((target_x, y), (255 - px[0], 255 - px[1], 255 - px[2]))
                                                else:
                                                    color_screen.putpixel((target_x, y), c_rgb)
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

            nonzero = 0
            for y in range(192):
                for x in range(280):
                    px = color_screen.getpixel((x, y))
                    if px != (10, 20, 12):
                        nonzero += 1
                        sx, sy = x * scale, y * scale
                        draw.rectangle([sx, sy, sx + 2, sy + 1], fill=px)
                        glow_px = (max(0, px[0]//3), max(0, px[1]//3), max(0, px[2]//3))
                        draw.rectangle([sx, sy + 2, sx + 2, sy + 2], fill=glow_px)

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
            return color_screen

        # The 280x192 screens by program, for tests to look at
        screens = {}
        for prog in ("JEMANG", "DEMO", "COLORDEMO"):
            screens[prog] = render_program_to_hgr(
                prog, os.path.join(out_dir, f"verified_standalone_{prog.lower()}.png"))
        return screens
    finally:
        if os.path.exists(temp_extracted):
            os.remove(temp_extracted)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Verify Standalone Font Rendering from DSK's FONT binary")
    parser.add_argument("--dsk", default="unicode.dsk", help="Path to DSK file (default: unicode.dsk)")
    parser.add_argument("--ac-jar", default=None, help="Explicit path to AppleCommander JAR file")
    parser.add_argument("--out-dir", default="docs/images", help="Where to write the PNGs (default: docs/images)")
    args = parser.parse_args()

    verify_and_render(dsk_file=args.dsk, custom_ac=args.ac_jar, out_dir=args.out_dir)
