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
    from unicode_server import HangulRasterizer
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from unicode_server import HangulRasterizer

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

def build_font_table(chars, rasterizer):
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
        
        glyph_bytes = rasterizer.rasterize(ch)
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

def process_dsk(dsk_path, specific_programs=None, custom_ac=None):
    if not os.path.exists(dsk_path):
        print(f"[오류] DSK 파일을 찾을 수 없습니다: {dsk_path}")
        return False

    print(f"\n[1/4] DSK 이미지 분석 중: {dsk_path}")
    files = list_dsk_files(dsk_path, custom_ac=custom_ac)
    basic_files = [name for ftype, name in files if ftype == 'A' and name not in ('HELLO', 'MASTER', 'COPYA', 'RENUMBER', 'CONVERT13', 'START13', 'SLOT#')]

    if specific_programs:
        target_programs = [p.strip().upper() for p in specific_programs]
    else:
        target_programs = basic_files

    print(f"  * 대상 BASIC 프로그램: {', '.join(target_programs)}")

    all_chars = set()
    for prog in target_programs:
        content = export_text_file(dsk_path, prog, custom_ac=custom_ac)
        chars = extract_used_characters(content)
        if chars:
            print(f"  - '{prog}': {len(chars)}글자 발견 -> {''.join(chars[:15])}{'...' if len(chars) > 15 else ''}")
            all_chars.update(chars)

    chars_list = sorted(list(all_chars))
    print(f"\n[2/4] 총 {len(chars_list)}개의 고유 한글/漢字 글리프 추출 완료:")
    print(f"  글자 목록: {''.join(chars_list)}")

    if not chars_list:
        print("[정보] 추출된 글자가 없습니다.")
        return False

    print(f"\n[3/4] PC TrueType 폰트로 14x16 비트맵 글리프 래스터라이징 중...")
    rasterizer = HangulRasterizer()
    font_bytes = build_font_table(chars_list, rasterizer)
    print(f"  * 생성된 FONT 바이너리 크기: {len(font_bytes)} 바이트 (메모리 로드 주소: $6000)")

    print(f"\n[4/4] DSK 이미지에 'FONT' 파일 주입 및 부팅 스크립트(HELLO) 패치 중...")
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
    parser.add_argument("--ac-jar", default=None, help="Explicit path to AppleCommander JAR file")
    args = parser.parse_args()

    progs = args.programs.split(",") if args.programs else None
    process_dsk(args.dsk, progs, custom_ac=args.ac_jar)
