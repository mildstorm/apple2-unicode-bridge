#!/usr/bin/env python3
"""Builds a bootable ProDOS hard-disk image with the Unicode font on it, so a
real Apple II (or AppleWin) draws & strings without the PC server.

    python build_hdd.py --prodos ProDOS_2_4_3.po                      (unicode.hdv)
    python build_hdd.py --prodos ProDOS_2_4_3.po --size 800K --out build/unicode_800k.po

The image (ProDOS block order, .hdv / .po) holds:
  PRODOS, BASIC.SYSTEM  copied from the ProDOS 2.4.x disk given with --prodos,
                        with its boot blocks
  STARTUP               loads the driver and says whether the font was found
  UNICODE               the driver (UNICODE.BIN, $4000)
  UFONT                 the 14x16 glyph of each code point at code point * 32,
                        a sparse 2 MB file: only blocks with glyphs take disk
  HDDEMO, JEMANG        demo programs

32M (65535 blocks) holds Hangul, Hanja (CJK Unified Ideographs and Extension A), kana,
Latin, Greek, Cyrillic and symbols. 800K leaves the Hanja out: spread over
20,992 code points they need about 1,300 blocks of the 1,600.

Copy the image to the hard disk of the Apple II: a CFFA3000 or Floppy Emu
takes the file as it is (CF / USB / SD card); for a CFFA or MicroDrive
partition or a SCSI disk, write it with CiderPress or ADTPro.
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)

from prodos_image import TYPE_BAS, TYPE_BIN, TYPE_SYS, Volume, read_volume, tokenize  # noqa: E402

GLYPH = 32
FONT_EOF = 0x10000 * GLYPH          # every BMP code point

RANGES = [
    (0x0020, 0x007E, "ASCII"),
    (0x00A0, 0x024F, "Latin-1, Latin Extended"),
    (0x0370, 0x03FF, "Greek"),
    (0x0400, 0x04FF, "Cyrillic"),
    # Old Hangul is written in these; without the server (which composes a
    # syllable to a cell) they are drawn one jamo to a cell, not left blank
    (0x1100, 0x11FF, "Hangul jamo (old Hangul)"),
    (0xA960, 0xA97F, "Hangul jamo extended-A"),
    (0xD7B0, 0xD7FF, "Hangul jamo extended-B"),
    (0x2000, 0x206F, "punctuation"),
    (0x2100, 0x218F, "letterlike, number forms"),
    (0x2190, 0x22FF, "arrows, math"),
    (0x2460, 0x24FF, "enclosed alphanumerics"),
    (0x2500, 0x26FF, "box drawing, shapes, symbols"),
    (0x3000, 0x30FF, "CJK punctuation, kana"),
    (0x3130, 0x318F, "Hangul compatibility jamo"),
    (0x3200, 0x32FF, "enclosed CJK"),
    (0x3400, 0x4DBF, "CJK Extension A (rare Hanja)"),
    (0x4E00, 0x9FFF, "CJK Unified Ideographs (Hanja)"),
    (0xAC00, 0xD7A3, "Hangul syllables"),
    (0xF900, 0xFAFF, "CJK compatibility ideographs"),
    (0xFF00, 0xFFEF, "fullwidth forms"),
]
HANJA_RANGES = {0x3400, 0x4E00, 0xF900}

STARTUP = """
10 D$ = CHR$ (4)
20 PRINT D$;"BLOAD UNICODE"
30 CALL 16384
40 TEXT : HOME
50 PRINT "========================================"
60 PRINT " APPLE II UNICODE - PRODOS HARD DISK"
70 IF PEEK (16387) THEN PRINT " FONT: UFONT (NO SERVER NEEDED)"
80 IF NOT PEEK (16387) THEN PRINT " UFONT NOT FOUND: & USES THE SERVER"
85 IF PEEK (16387) THEN PRINT " CTRL+K HANGUL, CTRL+J HANJA (ONBOARD)"
90 PRINT " RUN HDDEMO   (POKE 16453,1: SSC INPUT)"
100 PRINT "========================================"
110 NEW
"""

DEMO_LINES = [
    "/clear",
    "UNICODE FROM DISK",
    "한글 가나다라 훈민정음",
    "漢字 天地玄黃 宇宙洪荒",
    "ひらがな カタカナ",
    "Привет, мир!",
    "Καλημέρα κόσμε",
    "Café Ñandú Øre ß",
    "→ ★ ♥ ① ㉠ ㈜ ½",
]


def encode_line(text):
    """Hex-safe \\K...\\N for everything that is not plain upper-case ASCII
    (Applesoft keeps the string as typed, but hex keeps it safe to retype)."""
    from unicode_server import encode_apple2_multilingual
    return encode_apple2_multilingual(text).decode("ascii")


def demo_program():
    lines = []
    for n, text in enumerate(DEMO_LINES, 1):
        lines.append(f'{n * 10} & "{encode_line(text)}"')
    lines.append(f"{len(DEMO_LINES) * 10 + 10} END")
    return "\n".join(lines)


# Hanja for the onboard Ctrl+K line, where no glyphs are (U+D800-DFFF): for
# syllable s (code point - U+AC00) 4 bytes at HANJA_INDEX + s*4 (where its
# list starts, in code points, 2 bytes; how many; 0), the lists of 16-bit
# code points from HANJA_DATA.
HANJA_INDEX = 0xD800 * GLYPH          # $1B0000
HANJA_DATA = HANJA_INDEX + 0xB000     # $1BB000
HANJA_END = 0xE000 * GLYPH


def add_hanja(font):
    table = {}
    with open(os.path.join(ROOT, "hanja_table.txt"), encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#") and "\t" in line:
                reading, cands = line.rstrip("\n").split("\t", 1)
                table[reading] = [c for c in cands if ord(c) <= 0xFFFF][:255]
    data = bytearray()
    for s in range(11172):
        cands = table.get(chr(0xAC00 + s), [])
        if not cands:
            continue
        start = len(data) // 2
        font[HANJA_INDEX + s * 4:HANJA_INDEX + s * 4 + 4] = bytes(
            [start & 0xFF, start >> 8, len(cands), 0])
        for c in cands:
            data += ord(c).to_bytes(2, "little")
    assert HANJA_DATA + len(data) <= HANJA_END, "Hanja lists do not fit"
    font[HANJA_DATA:HANJA_DATA + len(data)] = data
    return len(data) // 2


def build_font(font, ranges):
    from unicode_server import HangulRasterizer
    r = HangulRasterizer(font_path=font)
    data = bytearray(FONT_EOF)
    count = 0
    for lo, hi, label in ranges:
        n = 0
        for cp in range(lo, hi + 1):
            if 0xD800 <= cp <= 0xDFFF or not any(f.get_char_index(cp) for f in r.faces):
                continue
            g = r.rasterize(chr(cp))
            if any(g):
                data[cp * GLYPH:(cp + 1) * GLYPH] = g
                n += 1
        count += n
        print(f"  {label:34} U+{lo:04X}-U+{hi:04X}: {n} glyphs")
    return data, count


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--prodos", default=os.environ.get("PRODOS_IMAGE"),
                    help="ProDOS 2.4.x disk image (.po) to take PRODOS, BASIC.SYSTEM and the boot blocks from (or set PRODOS_IMAGE)")
    ap.add_argument("--out", default=os.path.join(ROOT, "unicode.hdv"),
                    help="the image (default: unicode.hdv in the repository, the one it ships)")
    ap.add_argument("--size", default="32M", choices=["32M", "800K"],
                    help="32M: 65535 blocks with Hanja; 800K: 1600 blocks without (default 32M)")
    ap.add_argument("--font", default="Galmuri14.ttf, NotoSerifCJK16.ttf",
                    help="Font chain for the glyphs, first font first (default: Galmuri14, then NotoSerifCJK16)")
    ap.add_argument("--volume", default="UNICODE")
    args = ap.parse_args()
    if not args.prodos or not os.path.exists(args.prodos):
        sys.exit("Give a ProDOS 2.4.x disk image with --prodos (ProDOS_2_4_3.po, e.g. from prodos8.com or the AppleWin folder)")

    files, boot = read_volume(args.prodos)
    system = {name: (ftype, aux, data) for name, ftype, aux, data in files}
    for need in ("PRODOS", "BASIC.SYSTEM"):
        if need not in system:
            sys.exit(f"{args.prodos} has no {need}")

    blocks = 65535 if args.size == "32M" else 1600
    ranges = [r for r in RANGES if args.size == "32M" or r[0] not in HANJA_RANGES]
    print(f"[1/3] Rasterising glyphs with {args.font}")
    font, count = build_font(args.font, ranges)
    print(f"  Hanja for Ctrl+J: {add_hanja(font)} candidates")

    print("[2/3] Writing the volume")
    vol = Volume(blocks, args.volume, boot)
    for name in ("PRODOS", "BASIC.SYSTEM"):
        ftype, aux, data = system[name]
        vol.add_file(name, ftype, aux, data, sparse=False)
    vol.add_file("STARTUP", TYPE_BAS, 0x0801, tokenize(STARTUP), sparse=False)
    vol.add_file("UNICODE", TYPE_BIN, 0x4000, open(os.path.join(ROOT, "UNICODE.BIN"), "rb").read(), sparse=False)
    vol.add_file("HDDEMO", TYPE_BAS, 0x0801, tokenize(demo_program()), sparse=False)
    jemang = subprocess.run(["java", "-jar", os.path.join(ROOT, "tools", "AppleCommander.jar"),
                             "-g", os.path.join(ROOT, "unicode.dsk"), "JEMANG"], capture_output=True).stdout
    if jemang:
        vol.add_file("JEMANG", TYPE_BAS, 0x0801, jemang, sparse=False)
    vol.add_file("UFONT", TYPE_BIN, 0x0000, font, eof=FONT_EOF, sparse=True)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    vol.save(args.out)
    used = len(vol.used)
    print(f"[3/3] {args.out}: {blocks} blocks, {used} used ({used * 512 // 1024} KB), "
          f"UFONT {count} glyphs")


if __name__ == "__main__":
    main()
