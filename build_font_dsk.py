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

def font_tag_hash(name):
    """The byte the driver keys a font tag's glyphs with (unicode_driver.s
    PARSE_TAG_FONT): over the name after the colon, h = rol8(h ^ (c | $20)),
    from 0. A name that hashes to 0 shares the untagged glyphs."""
    h = 0
    for c in name.encode("latin-1", errors="replace"):
        x = h ^ (c | 0x20)
        h = ((x << 1) | (x >> 7)) & 0xFF
    return h


def extract_glyph_uses(text, default_font=None):
    """
    What the $6000 cache must hold for a program: {(char, tag hash): font}.

    The driver draws a character from the entry whose 4th key byte is the hash
    of the statement's last [F:name] tag (reset by each &), else from the
    untagged one (hash 0). So a character used in two fonts gets one entry for
    each tag it appears under. The font is the one the server would use there
    (a [F:...] or \\F...\\ tag, else the /font default); None means the default
    rasterizer. Tags the driver does not read (\\F...\\) leave the hash as it is.
    """
    expanded = []
    i = 0
    while i < len(text):
        if text[i:i+2].upper() == r'\K':
            end = text.upper().find(r'\N', i + 2)
            if end != -1:
                try:
                    expanded.append(bytes.fromhex(text[i+2:end]).decode('utf-8', errors='ignore'))
                    i = end + 2
                    continue
                except ValueError:
                    pass
        expanded.append(text[i])
        i += 1

    uses = {}
    current_default = default_font
    for line in "".join(expanded).splitlines():
        trimmed = line.strip()
        low = trimmed.lower()
        if '&' in trimmed and ('/font ' in low or '/f ' in low):
            m = re.search(r'/(?:font|f)\s+([A-Za-z0-9_.\-]+)', trimmed, re.IGNORECASE)
            if m:
                current_default = m.group(1).strip()
        if '&' in trimmed and ('/font-add ' in low or '/alias ' in low):
            m = re.search(r'/(?:font-add|alias)\s+([A-Za-z0-9_.\-]+)\s+([A-Za-z0-9_.\-]+)', trimmed, re.IGNORECASE)
            if m:
                font_add(m.group(1).strip(), m.group(2).strip())
        if '&' in trimmed and ('/font-del ' in low or '/font-remove ' in low or '/unalias ' in low):
            m = re.search(r'/(?:font-del|font-remove|unalias)\s+([A-Za-z0-9_.\-]+)', trimmed, re.IGNORECASE)
            if m:
                font_del(m.group(1).strip())
        if '&' in trimmed and '/font-clear' in low:
            font_clear()

        tag, font = 0, None
        j = 0
        while j < len(line):
            ch = line[j]
            if ch == '&':
                tag, font = 0, None
            elif ch == '[' and line[j+1:j+2].lower() in ('f', 'c', 'm'):
                end = line.find(']', j)
                if end != -1:
                    inner = line[j+1:end]
                    if inner[:1].lower() == 'f':
                        name = inner.split(':', 1)[1] if ':' in inner else ''
                        tag, font = font_tag_hash(name), (name.strip() or None)
                    j = end + 1
                    continue
            elif ch == '\\' and line[j+1:j+2].upper() in ('F', 'C', 'M'):
                end = line.find('\\', j + 2)
                if end != -1:
                    if line[j+1].upper() == 'F':
                        font = line[j+2:end].lstrip(':').strip() or None
                    j = end + 1
                    continue
            elif ord(ch) > 127:
                want = font or current_default
                key = (ch, tag)
                if key in uses and uses[key] != want:
                    print(f"[경고] '{ch}' 이(가) 같은 글꼴 태그 아래 두 글꼴({uses[key]}, {want})로 쓰여 뒤의 것을 씁니다.")
                uses[key] = want
            j += 1
    return uses


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

def build_font_table(chars, rasterizer, char_font_map=None, uses=None):
    """
    Builds the Apple II $6000 cache table format:
    Offset 0: 'H' ($48)
    Offset 1: 'G' ($47)
    Offset 2: Count N (1 byte, max 255)
    Offset 3: $00 (Reserved)
    Offset 4..: N * 36 bytes:
        [Byte 0..3]: UTF-8 encoding of the character, $00 past its end. For a
                     character of up to 3 bytes, byte 3 may instead be the
                     font_tag_hash of the [F:name] it is drawn under
        [Byte 4..35]: 32 bytes 14x16 bitmap glyph

    uses ({(char, tag hash): font}, from extract_glyph_uses) gives one entry
    per character and font tag, tagged entries first: the driver takes the
    first entry that matches the character and either its 4th byte or the
    current tag. Without it, one entry per character of chars.
    """
    if uses is not None:
        entries = sorted(uses.items(), key=lambda kv: (kv[0][1] == 0, kv[0][0], kv[0][1]))
        entries = [(ch, tag, font) for (ch, tag), font in entries]
    else:
        entries = [(ch, 0, (char_font_map or {}).get(ch)) for ch in chars]
    if len(entries) > 255:
        print(f"[경고] 글리프 수({len(entries)})가 255개를 초과하여 255개로 제한합니다.")
        entries = entries[:255]

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
    buf.append(len(entries))
    buf.append(0x00)

    for ch, tag, font in entries:
        utf8_bytes = ch.encode('utf-8')
        # The UTF-8 bytes, 0 past the end (4 for a character outside the BMP);
        # a shorter one carries its font tag's hash in the 4th byte
        key = bytearray(4)
        for i in range(min(4, len(utf8_bytes))):
            key[i] = utf8_bytes[i]
        if len(utf8_bytes) < 4:
            key[3] = tag

        target_r = None
        if font:
            target_r = get_font_rasterizer(font, rasterizer)
        elif ch in char_rasterizer_map:
            target_r, _ = char_rasterizer_map[ch]
        else:
            target_r = rasterizer

        glyph_bytes = target_r.rasterize(ch)

        if len(glyph_bytes) != 32:
            glyph_bytes = glyph_bytes.ljust(32, b'\x00')[:32]

        buf.extend(key)
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

    all_uses = {}
    for prog in target_programs:
        content = export_text_file(dsk_path, prog, custom_ac=custom_ac)
        prog_uses = extract_glyph_uses(content, default_font=font_path)
        if prog_uses:
            chars_found = sorted({ch for ch, _ in prog_uses})
            print(f"  - '{prog}': {len(chars_found)}글자 발견 -> {''.join(chars_found[:15])}{'...' if len(chars_found) > 15 else ''}")
            for key, font in prog_uses.items():
                if key in all_uses and all_uses[key] != font:
                    print(f"[경고] '{key[0]}' 이(가) 같은 글꼴 태그 아래 두 글꼴({all_uses[key]}, {font})로 쓰여 '{prog}'의 것을 씁니다.")
                all_uses[key] = font

    chars_list = sorted({ch for ch, _ in all_uses})
    print(f"\n[2/4] 총 {len(chars_list)}개의 고유 한글/漢字 글자, 글꼴 태그별 글리프 {len(all_uses)}개 추출 완료:")
    print(f"  글자 목록: {''.join(chars_list)}")

    if not chars_list:
        print("[정보] 추출된 글자가 없습니다.")
        return False

    print(f"\n[3/4] PC TrueType 폰트로 14x16 비트맵 글리프 래스터라이징 중...")
    rasterizer = HangulRasterizer(font_path=font_path, font_size=size, y_offset=y_offset, box_center=box_center, force_vector=force_vector)
    font_bytes = build_font_table(chars_list, rasterizer, uses=all_uses)
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
