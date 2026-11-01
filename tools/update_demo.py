#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper script to update DEMO program in unicode.dsk with multi-font, multi-size lines.
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

from inject_basic import build_applesoft_program
from ac_tool import put_file

DEMO_LINES_DATA = [
    (10, 'REM MULTI-FONT & MULTI-SIZE DEMO'),
    (20, '[GALMURI14] ', '안녕하세요애플투'),
    (30, '[NEODGM 16] ', '도스타자방이야기'),
    (40, '[SAM3K  16] ', '三國志英雄崛起'),
    (50, '[MYUNGJO16] ', '붓글씨고전바탕'),
    (60, '[GALMURI11] ', '조밀한작은폰트'),
    (70, '[GALMURI 9] ', '초소형모니터화면'),
    (80, '[NOTOSERIF] ', '漢字萬國훈민정음'),
    (90, '& "1977 - 2026 RETRO COMPUTING"'),
    (100, 'END'),
]

def make_demo_program():
    lines = []
    for item in DEMO_LINES_DATA:
        line_num = item[0]
        if len(item) == 2:
            lines.append((line_num, item[1]))
        elif len(item) == 3:
            tag = item[1]
            kor = item[2]
            hex_str = ''.join(f'{b:02X}' for b in kor.encode('utf-8'))
            basic_line = f'& "{tag}\\K{hex_str}\\N"'
            lines.append((line_num, basic_line))
    return lines

def main():
    dsk_path = os.path.join(ROOT_DIR, "unicode.dsk")
    lines = make_demo_program()
    print("New DEMO lines:")
    for num, txt in lines:
        print(f"  {num} {txt}")

    prog_bytes = build_applesoft_program(lines)
    print(f"\nInjecting new DEMO ({len(prog_bytes)} bytes) into {dsk_path}...")
    put_file(dsk_path, "DEMO", "A", 0x0801, prog_bytes)
    print("DEMO successfully updated in unicode.dsk!")

if __name__ == "__main__":
    main()
