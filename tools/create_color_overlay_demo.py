#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create and inject COLORDEMO program into unicode.dsk.

Design: Colored ribbon bars (Blue/Green/Orange/Violet/Black) with Korean text
cut out of them in black: each ribbon's text is drawn in /xor mode in the
ribbon's own colour, which clears the ribbon's coloured dots under the glyph.
(White text ORed onto a ribbon loses about half its dots: a colour area has
every other dot lit already.) Each ribbon uses a different font to demonstrate
multi-font support on the Apple II HGR screen.

HCOLOR mapping (Apple II HGR):
  0 = Black   1 = Green   2 = Violet   3 = White
  4 = Black   5 = Orange  6 = Blue     7 = White

Usage:
  python tools/create_color_overlay_demo.py
Then in AppleWin with unicode.dsk booted:
  RUN COLORDEMO
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
    """Build ribbon-bar color demo with multiple fonts."""
    lines = [
        (10,  'REM *** GORGEOUS APPLE II MULTI-COLOR DEMO ***'),
        # Blue ribbon — row 0  (HGR y 0..17)
        (20,  'HGR : HCOLOR=6: FOR Y=0 TO 17: HPLOT 0,Y TO 279,Y: NEXT Y'),
        # Every line fits the 20 cells of a row as the server lays it out (a
        # cell for every character, ASCII too), and none ends on row 11, whose
        # newline would scroll the screen.
        (30,  f'& "/pos 1 0" : & "/xor" : & "[F:sam3k][C:blue]{enc("★ 애플 II 멀티폰트 데모 ★")}"'),
        # Green ribbon — row 2  (HGR y 32..49)
        (40,  'HCOLOR=1: FOR Y=32 TO 49: HPLOT 0,Y TO 279,Y: NEXT Y'),
        (50,  f'& "/pos 1 2" : & "/xor" : & "[F:neodgm][C:green]{enc("녹색 리본: 둥근모 레트로 타자체")}"'),
        # Orange ribbon — row 4  (HGR y 64..81)
        (60,  'HCOLOR=5: FOR Y=64 TO 81: HPLOT 0,Y TO 279,Y: NEXT Y'),
        (70,  f'& "/pos 1 4" : & "/xor" : & "[F:dosmyungjo][C:orange]{enc("주황 리본: 품격있는 도스명조체")}"'),
        # Violet ribbon — row 6  (HGR y 96..113)
        (80,  'HCOLOR=2: FOR Y=96 TO 113: HPLOT 0,Y TO 279,Y: NEXT Y'),
        (90,  f'& "/pos 1 6" : & "/xor" : & "[F:galmuri14][C:violet]{enc("보라 리본: 선명한 갈무리 본문체")}"'),
        # Black rows — /replace (no background fill needed)
        (100, f'& "/pos 1 8"  : & "/replace" : & "[F:galmuri11][C:white]{enc("블랙 바탕: 갈무리11 폰트")}"'),
        # Row 9, not 10: HGR leaves the bottom four text lines (rows 10-11)
        # showing as text.
        (110, f'& "/pos 1 9"  : & "/replace" : & "[F:galmuri9][C:white]{enc("HUD: 초소형 갈무리9 폰트")}"'),
        (120, 'END'),
    ]
    return lines

def main():
    dsk_path = os.path.join(ROOT_DIR, "unicode.dsk")
    lines = make_colordemo_program()
    print("Injecting COLORDEMO lines:")
    for num, txt in lines:
        print(f"  {num} {txt[:80]}")

    prog_bytes = build_applesoft_program(lines)
    put_file(dsk_path, "COLORDEMO", "A", 0x0801, prog_bytes)
    print(f"COLORDEMO successfully injected into {dsk_path}!")

    # Also refresh HANGUL driver from UNICODE.BIN if present
    driver_bin = os.path.join(ROOT_DIR, "UNICODE.BIN")
    if os.path.exists(driver_bin):
        put_file(dsk_path, "HANGUL", "B", 0x4000, open(driver_bin, "rb").read())
        print(f"Updated HANGUL driver on {dsk_path} from {driver_bin}")

    # Re-bake DSK font cache
    print("Re-baking DSK font cache...")
    ok = process_dsk(dsk_path)
    if ok:
        print("DSK font cache updated successfully!")
    else:
        print("Failed to re-bake DSK!")

if __name__ == "__main__":
    main()
