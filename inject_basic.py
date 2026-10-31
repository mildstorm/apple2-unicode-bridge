#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apple II Applesoft BASIC Injector
Allows users to type or edit BASIC lines on PC (supporting Korean / Multilingual UTF-8)
and injects them directly into hangul.dsk as an Applesoft BASIC file.
"""

import os
import sys
import shutil
from ac_tool import put_file

TOKENS = {
    'END': 0x80, 'FOR': 0x81, 'NEXT': 0x82, 'DATA': 0x83, 'INPUT': 0x84,
    'DEL': 0x85, 'DIM': 0x86, 'READ': 0x87, 'GR': 0x88, 'TEXT': 0x89,
    'PR#': 0x8A, 'IN#': 0x8B, 'CALL': 0x8C, 'PLOT': 0x8D, 'HLIN': 0x8E,
    'VLIN': 0x8F, 'HGR2': 0x90, 'HGR': 0x91, 'HCOLOR=': 0x92, 'HPLOT': 0x93,
    'DRAW': 0x94, 'XDRAW': 0x95, 'HTAB': 0x96, 'HOME': 0x97, 'ROT=': 0x98,
    'SCALE=': 0x99, 'SHLOAD': 0x9A, 'TRACE': 0x9B, 'NOTRACE': 0x9C, 'NORMAL': 0x9D,
    'INVERSE': 0x9E, 'FLASH': 0x9F, 'COLOR=': 0xA0, 'POP': 0xA1, 'VTAB': 0xA2,
    'HIMEM:': 0xA3, 'LOMEM:': 0xA4, 'ONERR': 0xA5, 'RESUME': 0xA6, 'RECALL': 0xA7,
    'STORE': 0xA8, 'SPEED=': 0xA9, 'LET': 0xAA, 'GOTO': 0xAB, 'RUN': 0xAC,
    'IF': 0xAD, 'RESTORE': 0xAE, '&': 0xAF, 'GOSUB': 0xB0, 'RETURN': 0xB1,
    'REM': 0xB2, 'STOP': 0xB3, 'ON': 0xB4, 'WAIT': 0xB5, 'LOAD': 0xB6,
    'SAVE': 0xB7, 'DEF': 0xB8, 'POKE': 0xB9, 'PRINT': 0xBA, 'CONT': 0xBB,
    'LIST': 0xBC, 'CLEAR': 0xBD, 'GET': 0xBE, 'NEW': 0xBF, 'TAB(': 0xC0,
    'TO': 0xC1, 'FN': 0xC2, 'SPC(': 0xC3, 'THEN': 0xC4, 'AT': 0xC5,
    'NOT': 0xC6, 'STEP': 0xC7, '+': 0xC8, '-': 0xC9, '*': 0xCA,
    '/': 0xCB, '^': 0xCC, 'AND': 0xCD, 'OR': 0xCE, '>': 0xCF,
    '=': 0xD0, '<': 0xD1, 'SGN': 0xD2, 'INT': 0xD3, 'ABS': 0xD4,
    'USR': 0xD5, 'FRE': 0xD6, 'SCRN(': 0xD7, 'PDL': 0xD8, 'POS': 0xD9,
    'SQR': 0xDA, 'RND': 0xDB, 'LOG': 0xDC, 'EXP': 0xDD, 'COS': 0xDE,
    'SIN': 0xDF, 'TAN': 0xE0, 'ATN': 0xE1, 'PEEK': 0xE2, 'LEN': 0xE3,
    'STR$': 0xE4, 'VAL': 0xE5, 'ASC': 0xE6, 'CHR$': 0xE7, 'FRE': 0xE8,
    'LEFT$': 0xE9, 'RIGHT$': 0xEA, 'MID$': 0xEB
}

SORTED_TOKENS = sorted(TOKENS.items(), key=lambda x: len(x[0]), reverse=True)

def tokenize_line(line_text):
    buf = bytearray()
    i = 0
    in_quote = False
    in_rem = False

    while i < len(line_text):
        ch = line_text[i]
        if ch == '"':
            in_quote = not in_quote
            buf.append(ord('"'))
            i += 1
            continue

        if in_quote or in_rem:
            buf.extend(ch.encode('utf-8'))
            i += 1
            continue

        matched = False
        remaining = line_text[i:].upper()
        for tok_name, tok_val in SORTED_TOKENS:
            if remaining.startswith(tok_name):
                buf.append(tok_val)
                i += len(tok_name)
                matched = True
                if tok_name == 'REM':
                    in_rem = True
                break

        if not matched:
            buf.append(ord(ch))
            i += 1

    buf.append(0x00)
    return buf

def build_applesoft_program(lines, start_addr=0x0801):
    prog = bytearray()
    curr_addr = start_addr

    for line_num, line_text in sorted(lines, key=lambda x: x[0]):
        tokenized = tokenize_line(line_text)
        next_addr = curr_addr + 2 + 2 + len(tokenized)
        prog.extend([next_addr & 0xFF, (next_addr >> 8) & 0xFF])
        prog.extend([line_num & 0xFF, (line_num >> 8) & 0xFF])
        prog.extend(tokenized)
        curr_addr = next_addr

    prog.extend([0x00, 0x00])
    return prog

def inject_to_dsk(dsk_path, file_name, lines, custom_ac=None):
    prog_bytes = build_applesoft_program(lines)
    put_file(dsk_path, file_name, "A", 0x0801, prog_bytes, custom_ac=custom_ac)

    # Sync to bin if exists
    bin_dsk = os.path.join("bin", os.path.basename(dsk_path))
    if os.path.exists("bin"):
        shutil.copyfile(dsk_path, bin_dsk)
    print(f"\n[성공] '{file_name}' 프로그램이 '{dsk_path}'에 저장되었습니다!")
    print(f"Apple II에서 'LOAD {file_name}' 후 'LIST' 또는 'RUN' 하시면 됩니다.\n")

    # Auto-update standalone font in DSK
    try:
        from build_font_dsk import process_dsk
        print("[폰트 자동 갱신] 프로그램에 사용된 글리프를 DSK 'FONT' 파일에 동기화합니다...")
        process_dsk(dsk_path, custom_ac=custom_ac)
    except Exception as e:
        print(f"[폰트 동기화 건너뜀] {e}")

def interactive_mode():
    print("=" * 60)
    print(" Apple II Applesoft BASIC 한글 프로그램 생성기")
    print(" PC에서 한글 BASIC 코드를 자유롭게 입력하면 디스크에 즉시 주입합니다.")
    print(" (입력을 마치려면 빈 줄에서 Enter를 누르세요)")
    print("=" * 60)
    
    file_name = input("생성할 BASIC 프로그램 이름 (기본값: TEST) > ").strip().upper()
    if not file_name:
        file_name = "TEST"

    lines = []
    print("\nBASIC 코드를 한 줄씩 입력하세요 (예: 10 PRINT \"안녕하세요\"):")
    while True:
        try:
            line = input("> ").strip()
            if not line:
                break
            parts = line.split(" ", 1)
            if parts[0].isdigit():
                num = int(parts[0])
                rest = parts[1] if len(parts) > 1 else ""
                lines.append((num, rest))
            else:
                print("※ 라인 번호(예: 10, 20...)로 시작해야 합니다.")
        except (EOFError, KeyboardInterrupt):
            break

    if lines:
        dsk_path = "unicode.dsk" if os.path.exists("unicode.dsk") else "hangul.dsk"
        inject_to_dsk(dsk_path, file_name, lines)

if __name__ == '__main__':
    interactive_mode()
