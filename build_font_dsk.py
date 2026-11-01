#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apple II Standalone Font Subsetter and DSK Injector (build_font_dsk.py)

Extracts Korean and Hanja characters used in Apple II BASIC programs,
rasterizes them into 14x16 bitmap glyphs using PC TrueType fonts (Gulim/NotoSerif),
builds a compact binary font table (loaded at $6000),
and injects it directly into the DOS 3.3 DSK image as 'FONT' (Binary).

Enables 100% STANDALONE execution on Apple II / AppleWin without requiring
a running PC Super Serial font server!
"""

import os
import sys
import re
import shutil
import argparse

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from ac_tool import list_dsk_files, export_text_file, put_file, find_applecommander

try:
    from unicode_server import (
        HangulRasterizer, get_font_rasterizer, parse_font_segments,
        register_font_mapping, CUSTOM_FONT_ALIASES, font_add, font_del, font_clear
    )
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from unicode_server import (
        HangulRasterizer, get_font_rasterizer, parse_font_segments,
        register_font_mapping, CUSTOM_FONT_ALIASES, font_add, font_del, font_clear
    )

def extract_used_characters(text):
    """
    Finds all unique Korean and Hanja characters in the text,
    including \\K...\\N hex encoded strings and direct UTF-8 characters.
    """
    chars = set()
    # 1. Parse \K<HEX>\N
    matches = re.findall(r'\\[Kk]([0-9A-Fa-f]+)\\[Nn]', text)
    for m in matches:
        try:
            raw_bytes = bytes.fromhex(m)
            decoded = raw_bytes.decode('utf-8', errors='ignore')
            for ch in decoded:
                if ord(ch) > 127:
                    chars.add(ch)
        except Exception:
            pass

    # 2. Direct UTF-8 multilingual characters in quotes or comments
    for ch in text:
        if ord(ch) > 127:
            chars.add(ch)

    return sorted(list(chars))

def extract_font_tagged_characters(text, default_font=None):
    """
    Finds all unique Korean and Hanja characters in the text,
    including \\K...\\N hex encoded strings and direct UTF-8 characters,
    while tracking which font was specified via inline tags ([F:...], \\F...\\)
    or & "/font ..." commands.
    """
    expanded = []
    i = 0
    while i < len(text):
        if text[i:i+2].upper() == r'\K':
            end = text.upper().find(r'\N', i + 2)
            if end != -1:
                hex_data = text[i+2:end]
                try:
                    expanded.append(bytes.fromhex(hex_data).decode('utf-8', errors='ignore'))
                    i = end + 2
                    continue
                except Exception:
                    pass
        expanded.append(text[i])
        i += 1
    expanded_text = "".join(expanded)

    char_font_map = {}
    current_default = default_font

    for line in expanded_text.splitlines():
        trimmed = line.strip()
        if '&' in trimmed and ('/font ' in trimmed.lower() or '/f ' in trimmed.lower()):
            m = re.search(r'/(?:font|f)\s+([A-Za-z0-9_.\-]+)', trimmed, re.IGNORECASE)
            if m:
                current_default = m.group(1).strip()

        if '&' in trimmed and ('/font-add ' in trimmed.lower() or '/alias ' in trimmed.lower()):
            m = re.search(r'/(?:font-add|alias)\s+([A-Za-z0-9_.\-]+)\s+([A-Za-z0-9_.\-]+)', trimmed, re.IGNORECASE)
            if m:
                font_add(m.group(1).strip(), m.group(2).strip())

        if '&' in trimmed and ('/font-del ' in trimmed.lower() or '/font-remove ' in trimmed.lower() or '/unalias ' in trimmed.lower()):
            m = re.search(r'/(?:font-del|font-remove|unalias)\s+([A-Za-z0-9_.\-]+)', trimmed, re.IGNORECASE)
            if m:
                font_del(m.group(1).strip())

        if '&' in trimmed and '/font-clear' in trimmed.lower():
            font_clear()

        segments = parse_font_segments(line)
        for font_ident, seg in segments:
            chosen_font = font_ident or current_default
            for ch in seg:
                if ord(ch) > 127:
                    char_font_map[ch] = chosen_font

    return char_font_map

MULTI_FONT_SPECS = [
    {
        'chars': "안녕하세요애플투",
        'font': "Galmuri14.ttf",
        'size': 14,
        'y_offset': 1,
        'box_center': False,
        'force_vector': False,
        'label': "Galmuri14 (14px)"
    },
    {
        'chars': "도스타자방이야기",
        'font': "neodgm.ttf",
        'size': 16,
        'y_offset': 0,
        'box_center': True,
        'force_vector': False,
        'label': "Neo둥근모 (16px)"
    },
    {
        'chars': "三國志英雄崛起",
        'font': "Sam3KRFont.ttf",
        'size': 16,
        'y_offset': 0,
        'box_center': True,
        'force_vector': False,
        'label': "삼국지3 (16px)"
    },
    {
        'chars': "붓글씨고전바탕",
        'font': "DOSMyungjo.ttf",
        'size': 16,
        'y_offset': 0,
        'box_center': True,
        'force_vector': False,
        'label': "도스명조 (16px)"
    },
    {
        'chars': "조밀한작은폰트",
        'font': "Galmuri11.ttf",
        'size': 11,
        'y_offset': 0,
        'box_center': True,
        'force_vector': False,
        'label': "Galmuri11 (11px)"
    },
    {
        'chars': "초소형모니터화면",
        'font': "Galmuri9.ttf",
        'size': 9,
        'y_offset': 0,
        'box_center': True,
        'force_vector': False,
        'label': "Galmuri9 (9px)"
    },
    {
        'chars': "漢字萬國훈민정음",
        'font': "NotoSerifCJK16.ttf",
        'size': 14,
        'y_offset': 0,
        'box_center': False,
        'force_vector': True,
        'label': "NotoSerifCJK (14px Vector)"
    },
]

def build_font_table(chars, rasterizer, char_font_map=None):
    """
    Builds the Apple II $6000 cache table format:
    Offset 0: 'H' ($48)
    Offset 1: 'G' ($47)
    Offset 2: Count N (1 byte, max 255)
    Offset 3: $00 (Reserved)
    Offset 4..: N * 36 bytes:
        [Byte 0..2]: UTF-8 3-byte encoding of character
        [Byte 3]:    $00 (Padding)
        [Byte 4..35]: 32 bytes 14x16 bitmap glyph
    """
    if len(chars) > 255:
        print(f"[경고] 사용된 글자 수({len(chars)})가 255자를 초과하여 255자로 제한합니다.")
        chars = chars[:255]

    char_rasterizer_map = {}
    fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    
    for spec in MULTI_FONT_SPECS:
        fpath = os.path.join(fonts_dir, spec['font'])
        if not os.path.exists(fpath):
            fpath = spec['font']
        try:
            r = HangulRasterizer(
                font_path=fpath,
                font_size=spec['size'],
                y_offset=spec['y_offset'],
                box_center=spec['box_center'],
                force_vector=spec['force_vector']
            )
            for c in spec['chars']:
                char_rasterizer_map[c] = (r, spec['label'])
        except Exception as e:
            pass

    buf = bytearray()
    buf.append(ord('H'))
    buf.append(ord('G'))
    buf.append(len(chars))
    buf.append(0x00)

    for ch in chars:
        utf8_bytes = ch.encode('utf-8')
        # Ensure 3 bytes
        key = bytearray(3)
        for i in range(min(3, len(utf8_bytes))):
            key[i] = utf8_bytes[i]
        
        target_r = None
        if char_font_map and ch in char_font_map and char_font_map[ch]:
            target_r = get_font_rasterizer(char_font_map[ch], rasterizer)
        elif ch in char_rasterizer_map:
            target_r, _ = char_rasterizer_map[ch]
        else:
            target_r = rasterizer

        glyph_bytes = target_r.rasterize(ch)

        if len(glyph_bytes) != 32:
            glyph_bytes = glyph_bytes.ljust(32, b'\x00')[:32]

        buf.extend(key)
        buf.append(0x00) # Padding
        buf.extend(glyph_bytes)

    return bytes(buf)

def patch_hello_program(dsk_path, custom_ac=None):
    """
    Updates the HELLO program in DSK to load FONT at $6000 upon booting.
    """
    from inject_basic import build_applesoft_program

    hello_lines = [
        (10, 'D$ = CHR$(4)'),
        (20, 'PRINT D$;"BLOAD HANGUL"'),
        (25, 'PRINT D$;"BLOAD FONT"'),
        (30, 'CALL 16384'),
        (40, 'TEXT : HOME'),
        (50, 'PRINT "========================================"'),
        (60, 'PRINT " APPLE II MULTILINGUAL SYSTEM READY!"'),
        (65, 'PRINT " [STANDALONE FONT LOADED AT $6000]"'),
        (70, 'PRINT " TYPE BASIC CODE OR CTRL+K FOR KOREAN"'),
        (80, 'PRINT "========================================"'),
        (90, 'NEW')
    ]

    prog_bytes = build_applesoft_program(hello_lines)
    put_file(dsk_path, "HELLO", "A", 0x0801, prog_bytes, custom_ac=custom_ac)

def process_dsk(dsk_path, specific_programs=None, custom_ac=None, font_path=None, size=None, y_offset=None, box_center=None, force_vector=False):
    if not os.path.exists(dsk_path):
        print(f"[오류] DSK 파일을 찾을 수 없습니다: {dsk_path}")
        return False

    if font_path:
        register_font_mapping(font_path)

    print(f"\n[1/4] DSK 이미지 분석 중: {dsk_path}")
    files = list_dsk_files(dsk_path, custom_ac=custom_ac)
    basic_files = [name for ftype, name in files if ftype == 'A' and name not in ('HELLO', 'MASTER', 'COPYA', 'RENUMBER', 'CONVERT13', 'START13', 'SLOT#')]

    if specific_programs:
        target_programs = [p.strip().upper() for p in specific_programs]
    else:
        target_programs = basic_files

    print(f"  * 대상 BASIC 프로그램: {', '.join(target_programs)}")

    all_chars_map = {}
    for prog in target_programs:
        content = export_text_file(dsk_path, prog, custom_ac=custom_ac)
        prog_char_map = extract_font_tagged_characters(content, default_font=font_path)
        if prog_char_map:
            chars_found = list(prog_char_map.keys())
            print(f"  - '{prog}': {len(chars_found)}글자 발견 -> {''.join(chars_found[:15])}{'...' if len(chars_found) > 15 else ''}")
            all_chars_map.update(prog_char_map)

    chars_list = sorted(list(all_chars_map.keys()))
    print(f"\n[2/4] 총 {len(chars_list)}개의 고유 한글/漢字 글리프 추출 완료:")
    print(f"  글자 목록: {''.join(chars_list)}")

    if not chars_list:
        print("[정보] 추출된 글자가 없습니다.")
        return False

    print(f"\n[3/4] PC TrueType 폰트로 14x16 비트맵 글리프 래스터라이징 중...")
    rasterizer = HangulRasterizer(font_path=font_path, font_size=size, y_offset=y_offset, box_center=box_center, force_vector=force_vector)
    font_bytes = build_font_table(chars_list, rasterizer, char_font_map=all_chars_map)
    print(f"  * 생성된 FONT 바이너리 크기: {len(font_bytes)} 바이트 (메모리 로드 주소: $6000)")

    print(f"\n[4/4] DSK 이미지에 'FONT' 파일 주입 및 부팅 스크립트(HELLO) 패치 중...")
    # Ensure HANGUL driver is the latest standalone-capable UNICODE.BIN ($4000)
    unicode_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "UNICODE.BIN")
    if os.path.exists(unicode_bin):
        with open(unicode_bin, "rb") as f:
            ub_data = f.read()
        put_file(dsk_path, "HANGUL", "B", 0x4000, ub_data, custom_ac=custom_ac)

    put_file(dsk_path, "FONT", "B", 0x6000, font_bytes, custom_ac=custom_ac)
    patch_hello_program(dsk_path, custom_ac=custom_ac)

    # Sync to bin if exists
    bin_dsk = os.path.join("bin", os.path.basename(dsk_path))
    if os.path.exists("bin"):
        shutil.copyfile(dsk_path, bin_dsk)

    print("\n" + "=" * 60)
    print(" [완료] 독립 실행형 폰트 주입이 성공적으로 완료되었습니다!")
    print(f"  * DSK 파일: {dsk_path}")
    print(f"  * 포함된 폰트 수: {len(chars_list)}자 ({len(font_bytes)} 바이트)")
    print("  * 이제 PC 폰트 서버(Super Serial 연결) 없이도,")
    print("    Apple II에서 부팅 후 바로 'RUN DEMO' 또는 'RUN JEMANG'을 실행하면")
    print("    화면에 고품질 한글/한자가 완벽하게 출력됩니다.")
    print("=" * 60 + "\n")
    return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Apple II Standalone Font Subsetter and DSK Injector")
    parser.add_argument("--dsk", default="unicode.dsk", help="Path to Apple II DSK image (default: unicode.dsk)")
    parser.add_argument("--programs", default=None, help="Comma-separated list of BASIC programs to extract fonts from (default: all)")
    parser.add_argument("--font", default=None, help="Path to TTF/TTC font file (default: Galmuri / Gulim / NotoSerif)")
    parser.add_argument("--size", type=int, default=None, help="Font size (default: auto-detected from font native size)")
    parser.add_argument("--y-offset", type=int, default=None, help="Vertical offset adjustment in pixels (default: auto)")
    parser.add_argument("--box-center", action="store_true", default=None, help="Center glyph vertically in 16-row box (default: auto for 16px/11px/9px)")
    parser.add_argument("--force-vector", action="store_true", help="Force vector outline rasterization (ignore embedded bitmaps)")
    parser.add_argument("--ac-jar", default=None, help="Explicit path to AppleCommander JAR file")
    args = parser.parse_args()

    progs = args.programs.split(",") if args.programs else None
    process_dsk(
        args.dsk,
        progs,
        custom_ac=args.ac_jar,
        font_path=args.font,
        size=args.size,
        y_offset=args.y_offset,
        box_center=args.box_center,
        force_vector=args.force_vector
    )
