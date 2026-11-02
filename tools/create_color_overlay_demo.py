#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create and inject COLORDEMO program into unicode.dsk to showcase:
1. Apple II HGR Colors (Green, Violet, White, Orange, Blue)
2. Overlay Draw Mode vs Replace Draw Mode over an existing HGR background
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

from inject_basic import build_applesoft_program
from ac_tool import put_file
from build_font_dsk import process_dsk
from unicode_server import encode_apple2_multilingual

def enc(text):
    return encode_apple2_multilingual(text).decode('ascii')

def make_colordemo_program():
    lines = [
        (10, 'REM *** HGR COLOR & OVERLAY DEMO ***'),
        (20, 'HGR : HCOLOR=3'),
        (30, 'FOR I = 0 TO 191 STEP 16: HPLOT 0,I TO 279,I: NEXT I'),
        (40, 'FOR I = 0 TO 279 STEP 28: HPLOT I,0 TO I,191: NEXT I'),
        (50, '& "/pos 0 0"'),
        (60, '& "/overlay"'),
        (70, f'& "[C:green]{enc("녹색 오버레이 글씨")}"'),
        (80, f'& "[C:violet]{enc("보라색 유니코드 글꼴")}"'),
        (90, f'& "[C:orange]{enc("오렌지색 배경 위 글자")}"'),
        (100, f'& "[C:blue]{enc("푸른색 그래픽 오버레이")}"'),
        (110, f'& "[C:white]{enc("선명한 백색 텍스트")}"'),
        (120, '& "/replace"'),
        (130, f'& "[C:white]{enc("리플레이스는 배경 지움")}"'),
        (140, '& "/xor"'),
        (150, f'& "[C:white]{enc("반전 엑스오어 모드")}"'),
        (160, 'END'),
    ]
    return lines

def main():
    dsk_path = os.path.join(ROOT_DIR, "unicode.dsk")
    lines = make_colordemo_program()
    print("Injecting COLORDEMO lines:")
    for num, txt in lines:
        print(f"  {num} {txt}")

    prog_bytes = build_applesoft_program(lines)
    put_file(dsk_path, "COLORDEMO", "A", 0x0801, prog_bytes)
    print(f"COLORDEMO successfully injected into {dsk_path}!")

    # Also update HANGUL driver from UNICODE.BIN
    driver_bin = os.path.join(ROOT_DIR, "UNICODE.BIN")
    if os.path.exists(driver_bin):
        put_file(dsk_path, "HANGUL", "B", 0x4000, open(driver_bin, "rb").read())
        print(f"Updated HANGUL driver on {dsk_path} from {driver_bin}")

    # Re-bake DSK font cache
    print("Re-baking DSK font cache...")
    ok = process_dsk(dsk_path)
    if ok:
        print("DSK font cache updated successfully with COLORDEMO glyphs!")
    else:
        print("Failed to re-bake DSK!")

if __name__ == "__main__":
    main()
