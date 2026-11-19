#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apple II Unicode Bridge Server (apple2-unicode-bridge)
Communicates with Apple II running UNICODE.BIN / HANGUL.BIN via Super Serial Card (SSC) over TCP or COM port.
Dynamically rasterizes Unicode characters (CJK, Hanja, Hangul, Cyrillic, Greek, Latin diacritics, symbols)
using TrueType/OpenType fonts and streams 14x16 (and 7x16) bitmaps to Apple II HGR Page 1 ($2000-$3FFF).
"""

import sys
import os
import re
import socket
import threading
import time
import argparse

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(errors='replace')
    except Exception:
        pass
try:
    import freetype
    HAVE_FREETYPE = True
except ImportError:
    HAVE_FREETYPE = False

from PIL import Image, ImageDraw, ImageFont

import apple_ime

if getattr(sys, 'frozen', False):
    SCRIPT_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    EXE_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR = SCRIPT_DIR

# Old Hangul (훈민정음: 아래아, 옛 자모, 방점) is written with conjoining jamo,
# which drawn one codepoint to a cell come out spelled apart. old_hangul.py
# shapes each syllable with HarfBuzz into one 14x16 cell (needs uharfbuzz and
# NotoSerifCJK16.ttf); without it old Hangul is drawn jamo by jamo as before.
OLD_HANGUL = None
try:
    import old_hangul
    _old_hangul_font = old_hangul.default_font(SCRIPT_DIR) or old_hangul.default_font(EXE_DIR)
    if _old_hangul_font:
        OLD_HANGUL = old_hangul.Composer(_old_hangul_font)
    else:
        print("[Old Hangul] NotoSerifCJK16.ttf not found: old Hangul is drawn jamo by jamo")
except ImportError as e:
    print(f"[Old Hangul] {e}: old Hangul is drawn jamo by jamo (pip install uharfbuzz)")


import rtl_text


def compose_old_hangul(text):
    """text as the cells to draw, left to right: each old Hangul syllable as
    one unit for rasterize(), Arabic in its joined forms and right-to-left
    runs (Arabic, Hebrew) in display order (rtl_text)."""
    text = rtl_text.shape_for_display(text)
    return OLD_HANGUL.split(text) if OLD_HANGUL is not None else text

# Default Font Candidates: prioritize Galmuri / Gulim (굴림/돋움) which has pixel-perfect 14x14 bitmaps for Korean & Hanja
FONT_CANDIDATES = [
    # Local project fonts (Galmuri pixel font or NotoSerif)
    os.path.join(EXE_DIR, "Galmuri14.ttf"),
    os.path.join(SCRIPT_DIR, "Galmuri14.ttf"),
    os.path.join(SCRIPT_DIR, "fonts", "Galmuri14.ttf"),
    "Galmuri14.ttf",
    # Windows system fonts
    r"C:\Windows\Fonts\gulim.ttc",
    r"C:\Windows\Fonts\gulimche.ttc",
    r"C:\Windows\Fonts\dotum.ttc",
    r"C:\Windows\Fonts\batang.ttc",
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\msjh.ttc",       # Microsoft JhengHei (Full CJK Ideographs)
    r"C:\Windows\Fonts\simsun.ttc",     # SimSun (Full CJK Ideographs)
    r"C:\Windows\Fonts\mingliub.ttc",
    # macOS / Linux system fonts
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    # Local fallback fonts
    os.path.join(EXE_DIR, "NotoSerifCJK16.ttf"),
    os.path.join(SCRIPT_DIR, "NotoSerifCJK16.ttf"),
    os.path.join(SCRIPT_DIR, "fonts", "NotoSerifCJK16.ttf"),
    "NotoSerifCJK16.ttf",
    # Last, for what none of the above has: emoji and symbols (monochrome
    # outlines), then Arabic (with its presentation forms), Hebrew and Thai
    r"C:\Windows\Fonts\seguisym.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
    "/System/Library/Fonts/Apple Symbols.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# Hanja Variant Mapping: map common CJK variant ideographs (신자체/간체/이체자) to standard Korean Hanja
HANJA_VARIANTS = {
    0x96A0: 0x96B1,  # 隠 -> 隱 (숨길 은)
    0x9641: 0x9640,  # 陁 -> 陀 (비탈질/아미타 타)
    0x56FD: 0x570B,  # 国 -> 國 (나라 국)
    0x9F84: 0x9F8D,  # 竜 -> 龍 (용 룡)
    0x9244: 0x9435,  # 鉄 -> 鐵 (쇠 철)
    0x5B66: 0x5B78,  # 学 -> 學 (배울 학)
    0x4F1A: 0x6703,  # 会 -> 會 (모일 회)
    0x4E07: 0x842C,  # 万 -> 萬 (일만 만)
    0x5E83: 0x5EE3,  # 広 -> 廣 (넓을 광)
    0x7D4C: 0x7D93,  # 経 -> 經 (지날 경)
    0x6761: 0x689D,  # 条 -> 條 (가지 조)
    0x6E08: 0x6FDF,  # 済 -> 濟 (건널 제)
    0x4F53: 0x9AD4,  # 体 -> 體 (몸 체)
    0x65F6: 0x6642,  # 时 -> 時 (때 시)
    0x5B9E: 0x5BE6,  # 実 -> 實 (열매 실)
}

# 2-Bul-Sik (KS X 5002) key layout. Shift gives the five tense consonants
# and ㅒ ㅖ; on every other key Shift types the same jamo, as in Windows.
DUBEOL_KEYS = {
    'q': 'ㅂ', 'w': 'ㅈ', 'e': 'ㄷ', 'r': 'ㄱ', 't': 'ㅅ',
    'y': 'ㅛ', 'u': 'ㅕ', 'i': 'ㅑ', 'o': 'ㅐ', 'p': 'ㅔ',
    'a': 'ㅁ', 's': 'ㄴ', 'd': 'ㅇ', 'f': 'ㄹ', 'g': 'ㅎ',
    'h': 'ㅗ', 'j': 'ㅓ', 'k': 'ㅏ', 'l': 'ㅣ',
    'z': 'ㅋ', 'x': 'ㅌ', 'c': 'ㅊ', 'v': 'ㅍ', 'b': 'ㅠ', 'n': 'ㅜ', 'm': 'ㅡ',
    'Q': 'ㅃ', 'W': 'ㅉ', 'E': 'ㄸ', 'R': 'ㄲ', 'T': 'ㅆ', 'O': 'ㅒ', 'P': 'ㅖ',
}

CHO_LIST = ['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ','ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']
JUNG_LIST = ['ㅏ','ㅐ','ㅑ','ㅒ','ㅓ','ㅔ','ㅕ','ㅖ','ㅗ','ㅘ','ㅙ','ㅚ','ㅛ','ㅜ','ㅝ','ㅞ','ㅟ','ㅠ','ㅡ','ㅢ','ㅣ']
JONG_LIST = ['', 'ㄱ','ㄲ','ㄳ','ㄴ','ㄵ','ㄶ','ㄷ','ㄹ','ㄺ','ㄻ','ㄼ','ㄽ','ㄾ','ㄿ','ㅀ',
             'ㅁ','ㅂ','ㅄ','ㅅ','ㅆ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']

VOWEL_PAIRS = {
    ('ㅗ', 'ㅏ'): 'ㅘ', ('ㅗ', 'ㅐ'): 'ㅙ', ('ㅗ', 'ㅣ'): 'ㅚ',
    ('ㅜ', 'ㅓ'): 'ㅝ', ('ㅜ', 'ㅔ'): 'ㅞ', ('ㅜ', 'ㅣ'): 'ㅟ',
    ('ㅡ', 'ㅣ'): 'ㅢ',
}

CONSONANT_PAIRS = {
    ('ㄱ', 'ㅅ'): 'ㄳ', ('ㄴ', 'ㅈ'): 'ㄵ', ('ㄴ', 'ㅎ'): 'ㄶ',
    ('ㄹ', 'ㄱ'): 'ㄺ', ('ㄹ', 'ㅁ'): 'ㄻ', ('ㄹ', 'ㅂ'): 'ㄼ', ('ㄹ', 'ㅅ'): 'ㄽ',
    ('ㄹ', 'ㅌ'): 'ㄾ', ('ㄹ', 'ㅍ'): 'ㄿ', ('ㄹ', 'ㅎ'): 'ㅀ', ('ㅂ', 'ㅅ'): 'ㅄ',
}

def compose_syllable(cho, jung, jong=0):
    return chr(0xAC00 + (cho * 21 + jung) * 28 + jong)

MULTI_FONT_SPECS = [
    ("안녕하세요애플투", "Galmuri14.ttf", 14, 1, False, False),
    ("도스타자방이야기", "neodgm.ttf", 16, 0, True, False),
    ("三國志英雄崛起", "Sam3KRFont.ttf", 16, 0, True, False),
    ("붓글씨고전바탕", "DOSMyungjo.ttf", 16, 0, True, False),
    ("조밀한작은폰트", "Galmuri11.ttf", 11, 0, True, False),
    ("초소형모니터화면", "Galmuri9.ttf", 9, 0, True, False),
    ("漢字萬國훈민정음", "NotoSerifCJK16.ttf", 14, 0, False, True),
]

BUNDLED_FONT_INFO = {
    'galmuri14': {'file': 'Galmuri14.ttf', 'size': 14, 'y_offset': 1, 'box_center': False, 'force_vector': False, 'aliases': ['galmuri14', 'galmuri', '1']},
    'neodgm': {'file': 'neodgm.ttf', 'size': 16, 'y_offset': 0, 'box_center': True, 'force_vector': False, 'aliases': ['neodgm', '둥근모', 'dunggeunmo', '2']},
    'sam3k': {'file': 'Sam3KRFont.ttf', 'size': 16, 'y_offset': 0, 'box_center': True, 'force_vector': False, 'aliases': ['sam3k', 'sam3kr', '삼국지', 'samgukji', '3']},
    'dosmyungjo': {'file': 'DOSMyungjo.ttf', 'size': 16, 'y_offset': 0, 'box_center': True, 'force_vector': False, 'aliases': ['dosmyungjo', 'myungjo', '명조', '4']},
    'dosgothic': {'file': 'DOSGothic.ttf', 'size': 16, 'y_offset': 0, 'box_center': True, 'force_vector': False, 'aliases': ['dosgothic', 'gothic', '고딕', '5']},
    'galmuri11': {'file': 'Galmuri11.ttf', 'size': 11, 'y_offset': 0, 'box_center': True, 'force_vector': False, 'aliases': ['galmuri11', '6']},
    'galmuri9': {'file': 'Galmuri9.ttf', 'size': 9, 'y_offset': 0, 'box_center': True, 'force_vector': False, 'aliases': ['galmuri9', '7']},
    'notoserif': {'file': 'NotoSerifCJK16.ttf', 'size': 14, 'y_offset': 0, 'box_center': False, 'force_vector': True, 'aliases': ['notoserif', 'noto', 'cjk', '8']},
}

FONT_TAG_PATTERN = re.compile(r'\[(?:F|FONT):([^\]]+)\]|\\(?:F|f):?([^\\/]+)\\')
STYLE_TAG_PATTERN = re.compile(
    r'\[(F|FONT|C|COLOR|M|MODE):([^\]]+)\]|\\(F|f|C|c|M|m):?([^\\/]+)\\',
    re.IGNORECASE
)

# Apple II HGR Color Masks (HCOLOR 0..7)
# Each entry is (mask_even_byte0, mask_odd_byte1)
HGR_COLOR_MASKS = {
    0: (0x00, 0x00), # Black 1
    1: (0x2A, 0x55), # Green
    2: (0x55, 0x2A), # Violet / Purple
    3: (0x7F, 0x7F), # White 1
    4: (0x80, 0x80), # Black 2
    5: (0xAA, 0xD5), # Orange / Red
    6: (0xD5, 0xAA), # Blue / Cyan
    7: (0xFF, 0xFF), # White 2
}

HGR_COLOR_ALIASES = {
    '0': 0, 'black': 0, 'blk': 0, 'black1': 0, '검정': 0,
    '1': 1, 'green': 1, 'grn': 1, 'g': 1, '초록': 1, '녹색': 1,
    '2': 2, 'violet': 2, 'purple': 2, 'magenta': 2, 'vio': 2, 'pur': 2, 'v': 2, 'p': 2, '보라': 2, '자주': 2,
    '3': 3, 'white': 3, 'wht': 3, 'w': 3, 'white1': 3, '흰색': 3, '백색': 3,
    '4': 4, 'black2': 4,
    '5': 5, 'orange': 5, 'red': 5, 'org': 5, 'o': 5, 'r': 5, '주황': 5, '빨강': 5, '적색': 5,
    '6': 6, 'blue': 6, 'cyan': 6, 'blu': 6, 'b': 6, 'c': 6, '파랑': 6, '청색': 6, '하늘': 6,
    '7': 7, 'white2': 7,
}

DRAW_MODE_ALIASES = {
    '0': 0, 'replace': 0, 'rep': 0, 'r': 0, 'normal': 0, '덮어쓰기': 0,
    '1': 1, 'overlay': 1, 'over': 1, 'or': 1, 'o': 1, 'transparent': 1, '오버레이': 1, '겹치기': 1,
    '2': 2, 'xor': 2, 'invert': 2, 'x': 2, '반전': 2,
}

def parse_hgr_color(color_spec, default=3):
    """Resolves color index (0..7) or name ('green', 'orange', 'blue', etc.) to HCOLOR 0..7."""
    if color_spec is None:
        return default
    if isinstance(color_spec, int):
        return color_spec & 7
    key = str(color_spec).strip().lower()
    if key in HGR_COLOR_ALIASES:
        return HGR_COLOR_ALIASES[key]
    if key.isdigit():
        return int(key) & 7
    return default

def parse_draw_mode(mode_spec, default=0):
    """Resolves draw mode ('replace'/0, 'overlay'/1, 'xor'/2) to integer 0, 1, or 2."""
    if mode_spec is None:
        return default
    if isinstance(mode_spec, int):
        return mode_spec if mode_spec in (0, 1, 2) else default
    key = str(mode_spec).strip().lower()
    if key in DRAW_MODE_ALIASES:
        return DRAW_MODE_ALIASES[key]
    return default

def apply_color_to_glyph(glyph_32: bytes, color_idx: int) -> bytes:
    """Applies Apple II HGR color bit-mask, high-bit palette, and stroke expansion to a 32-byte (14x16) glyph."""
    c = parse_hgr_color(color_idx, default=3)
    if c in (3, 7): # White (100% full-resolution, all dots preserved)
        return glyph_32
    if c in (0, 4): # Black
        return bytes(32)

    hb = 0x80 if c in (5, 6) else 0x00
    color_phase_mask = 0x2AAA if c in (1, 5) else 0x1555

    out = bytearray(32)
    for r in range(16):
        b0 = glyph_32[r * 2] & 0x7F
        b1 = glyph_32[r * 2 + 1] & 0x7F
        val = b0 | (b1 << 7)
        if val:
            matching = val & color_phase_mask
            wrong = val & ~color_phase_mask
            shifted = (wrong << 1) & color_phase_mask
            colored_val = (matching | shifted) & 0x3FFF
            out[r * 2]     = (colored_val & 0x7F) | hb
            out[r * 2 + 1] = ((colored_val >> 7) & 0x7F) | hb
        else:
            out[r * 2]     = hb
            out[r * 2 + 1] = hb
    return bytes(out)

# A coloured hi-res dot is every other dot: two dots side by side are white.
# So a 14-dot cell holds only 7 coloured dots across, and squeezing the 14-dot
# white glyph into them (apply_color_to_glyph) merges and breaks strokes.
# Coloured text is drawn instead from a glyph rasterised for 7 columns, a
# vector font at 8x15 pixels with grey levels, each column one coloured dot.
COLOR_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgun.ttf",          # Malgun Gothic: Hangul, Latin, Cyrillic
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    r"C:\Windows\Fonts\gulim.ttc",
    r"C:\Windows\Fonts\msjh.ttc",            # Hanja the fonts above lack
    r"C:\Windows\Fonts\simsun.ttc",
    os.path.join(SCRIPT_DIR, "NotoSerifCJK16.ttf"),
]


class ColorRasterizer:
    """Glyphs 7 columns wide (one per coloured dot) by 16 rows."""

    COLS = 7
    WIDTH_PX, HEIGHT_PX = 8, 15
    BASELINE = 13
    INK = 96  # grey level counted as ink

    def __init__(self, font_paths=None):
        self.faces = []
        self.cache = {}
        if not HAVE_FREETYPE:
            return
        paths = []
        for p in list(font_paths or []) + COLOR_FONT_CANDIDATES:
            for cand in (p, os.path.join(SCRIPT_DIR, "fonts", p), os.path.join(SCRIPT_DIR, p)):
                if os.path.exists(cand):
                    cand = os.path.abspath(cand)
                    if cand not in paths:
                        paths.append(cand)
                    break
        for p in paths:
            try:
                f = freetype.Face(p)
                f.set_pixel_sizes(self.WIDTH_PX, self.HEIGHT_PX)
                self.faces.append(f)
            except Exception:
                pass
        if self.faces:
            print(f"[Color-Font] {os.path.basename(paths[0])} (+{len(self.faces) - 1} fallback)")

    def rasterize(self, ch):
        """16 rows of 7-bit column masks (bit 0 leftmost), or None when no
        colour font has the character (the caller then folds the white glyph)."""
        if ch in self.cache:
            return self.cache[ch]
        rows = None
        if ch == ' ':
            rows = [0] * 16
        elif len(ch) == 1:
            face = next((f for f in self.faces if f.get_char_index(ord(ch)) != 0), None)
            if face is not None:
                face.load_char(ch, freetype.FT_LOAD_RENDER)
                bmp = face.glyph.bitmap
                start_x = max(0, (self.COLS - bmp.width) // 2)
                start_y = self.BASELINE - face.glyph.bitmap_top
                rows = [0] * 16
                for r in range(bmp.rows):
                    y = start_y + r
                    if not 0 <= y < 16:
                        continue
                    for c in range(bmp.width):
                        x = start_x + c
                        if 0 <= x < self.COLS and bmp.buffer[r * bmp.pitch + c] >= self.INK:
                            rows[y] |= 1 << x
        self.cache[ch] = rows
        return rows


def color_glyph_from_columns(rows, color_idx: int) -> bytes:
    """A 7-column glyph as a 14x16 cell of coloured dots: column c lights the
    dot of the colour's phase in its pair (green/orange odd, violet/blue
    even), and every byte carries the palette bit."""
    c = parse_hgr_color(color_idx, default=3)
    hb = 0x80 if c in (5, 6) else 0x00
    phase = 1 if c in (1, 5) else 0
    out = bytearray(32)
    for r in range(16):
        val = 0
        for col in range(7):
            if (rows[r] >> col) & 1:
                val |= 1 << (col * 2 + phase)
        out[r * 2] = (val & 0x7F) | hb
        out[r * 2 + 1] = ((val >> 7) & 0x7F) | hb
    return bytes(out)


def parse_styled_segments(text, default_font=None, default_color=None, default_mode=None):
    """
    Parses a string into segments of (font_id, color_id, mode_id, text_segment).
    Recognizes inline tags:
      - Font:  [F:neodgm], [FONT:1], \\F:myungjo\\, \\F1\\
      - Color: [C:green], [COLOR:5], \\C:blue\\, \\C1\\
      - Mode:  [M:overlay], [MODE:replace], [M:xor], \\M:overlay\\, \\M1\\
    """
    segments = []
    last_idx = 0
    cur_font = default_font
    cur_color = default_color
    cur_mode = default_mode

    for m in STYLE_TAG_PATTERN.finditer(text):
        seg = text[last_idx:m.start()]
        if seg:
            segments.append((cur_font, cur_color, cur_mode, seg))
        tag_type = (m.group(1) or m.group(3)).strip().upper()
        tag_val = (m.group(2) or m.group(4)).strip()
        if tag_type.startswith('F'):
            cur_font = tag_val
        elif tag_type.startswith('C'):
            cur_color = parse_hgr_color(tag_val, default=cur_color if cur_color is not None else 3)
        elif tag_type.startswith('M'):
            cur_mode = parse_draw_mode(tag_val, default=cur_mode if cur_mode is not None else 0)
        last_idx = m.end()

    seg = text[last_idx:]
    if seg:
        segments.append((cur_font, cur_color, cur_mode, seg))
    return segments

def parse_font_segments(text):
    """
    Parses a string into segments of (font_identifier_or_None, text_segment).
    Recognizes tags like [F:neodgm], [FONT:1], \\F:myungjo\\, \\F2\\ etc.
    Strips any inline color/mode tags ([C:...], [M:...]) from text_segment so they are not rendered as literal text.
    """
    styled = parse_styled_segments(text)
    if not styled:
        return []
    merged = []
    for f_id, _c_id, _m_id, seg in styled:
        if merged and merged[-1][0] == f_id:
            merged[-1] = (f_id, merged[-1][1] + seg)
        else:
            merged.append((f_id, seg))
    return merged

_RASTERIZER_CACHE = {}
CUSTOM_FONT_ALIASES = {}

def font_add(alias: str, font_path_or_name: str):
    """Register or modify a font slot/alias."""
    key = str(alias).strip().lower()
    val = str(font_path_or_name).strip()
    CUSTOM_FONT_ALIASES[key] = val
    if key in _RASTERIZER_CACHE:
        del _RASTERIZER_CACHE[key]
    print(f"[FontManager] Registered/Updated font slot: '{key}' -> '{val}'")

def font_del(alias: str):
    """Remove/unregister a font slot/alias."""
    key = str(alias).strip().lower()
    if key in CUSTOM_FONT_ALIASES:
        del CUSTOM_FONT_ALIASES[key]
        if key in _RASTERIZER_CACHE:
            del _RASTERIZER_CACHE[key]
        print(f"[FontManager] Removed font slot: '{key}'")

def font_clear():
    """Clear all custom registered font slots/aliases."""
    CUSTOM_FONT_ALIASES.clear()
    _RASTERIZER_CACHE.clear()
    print("[FontManager] Cleared all custom font slots")

def register_font_mapping(font_arg):
    """
    Registers custom font mappings and aliases.
    Accepts:
      - Plain list: "neodgm.ttf, Sam3KRFont.ttf" (maps 1->neodgm, 2->Sam3KRFont)
      - Key=Value list: "1=DOSMyungjo.ttf, title=Sam3KRFont.ttf, body=Galmuri14.ttf"
    """
    if not font_arg:
        return
    entries = [p.strip() for p in font_arg.split(",") if p.strip()]
    plain_idx = 1
    for item in entries:
        if "=" in item:
            alias, target = item.split("=", 1)
            font_add(alias, target)
        else:
            font_add(str(plain_idx), item)
            stem = os.path.splitext(os.path.basename(item))[0].lower()
            font_add(stem, item)
            plain_idx += 1

def get_font_rasterizer(font_identifier, fallback_rasterizer=None):
    """
    Resolves a font identifier (alias, index, filename, or path) to a HangulRasterizer.
    """
    if not font_identifier:
        return fallback_rasterizer

    key = str(font_identifier).strip().lower()

    # 0. Check custom user aliases first
    if key in CUSTOM_FONT_ALIASES:
        target = CUSTOM_FONT_ALIASES[key]
        if target.lower() != key:
            return get_font_rasterizer(target, fallback_rasterizer)

    if key in _RASTERIZER_CACHE:
        return _RASTERIZER_CACHE[key]

    fonts_dir = os.path.join(SCRIPT_DIR, "fonts")
    if not os.path.exists(fonts_dir):
        fonts_dir = os.path.join(os.path.dirname(SCRIPT_DIR), "fonts")

    # 1. Match aliases in BUNDLED_FONT_INFO
    target_spec = None
    for spec in BUNDLED_FONT_INFO.values():
        all_aliases = [a.lower() for a in spec['aliases']] + [
            spec['file'].lower(),
            os.path.splitext(spec['file'].lower())[0]
        ]
        if key in all_aliases:
            target_spec = spec
            break

    if target_spec:
        fpath = os.path.join(fonts_dir, target_spec['file'])
        if not os.path.exists(fpath):
            fpath = os.path.join(SCRIPT_DIR, target_spec['file'])
        try:
            r = HangulRasterizer(
                font_path=fpath,
                font_size=target_spec['size'],
                y_offset=target_spec['y_offset'],
                box_center=target_spec['box_center'],
                force_vector=target_spec['force_vector']
            )
            _RASTERIZER_CACHE[key] = r
            return r
        except Exception as e:
            print(f"[Warning] Failed to instantiate rasterizer for {key}: {e}")

    # 2. Match direct file or path
    candidate_paths = [
        font_identifier,
        os.path.join(fonts_dir, font_identifier),
        os.path.join(SCRIPT_DIR, font_identifier),
        os.path.join(fonts_dir, font_identifier + ".ttf"),
        os.path.join(SCRIPT_DIR, font_identifier + ".ttf"),
    ]
    for cp in candidate_paths:
        if os.path.exists(cp):
            try:
                auto_sz, auto_y, auto_c = auto_detect_font_config(cp)
                r = HangulRasterizer(
                    font_path=cp,
                    font_size=auto_sz,
                    y_offset=auto_y,
                    box_center=auto_c,
                    force_vector=False
                )
                _RASTERIZER_CACHE[key] = r
                return r
            except Exception as e:
                print(f"[Warning] Failed to load font from {cp}: {e}")

    return fallback_rasterizer

def auto_detect_font_config(font_path):
    """Automatically detects native pixel size and vertical alignment for bitmap fonts."""
    if not font_path:
        return 14, 1, False # Default Galmuri14
    base = os.path.basename(font_path).lower()
    if 'galmuri14' in base:
        return 14, 1, False # 14px with 1-line top padding
    elif 'galmuri11' in base:
        return 11, 0, True  # 11px box-centered
    elif 'galmuri9' in base:
        return 9, 0, True   # 9px box-centered
    elif 'galmuri7' in base:
        return 7, 0, True   # 7px box-centered
    elif any(k in base for k in ['neodgm', 'sam3k', 'dosgothic', 'dosmyungjo', 'dosiyagi', 'dossaemmul']):
        return 16, 0, True  # 16px DOS fonts box-centered
    elif 'gulim' in base or 'dotum' in base:
        return 14, 0, False # 14px Windows embedded bitmap
    elif 'tahoma' in base:
        return 18, 0, False # Arabic and Hebrew: at 14px they come out at half the height of Hangul
    return 14, 0, False

class HangulRasterizer:
    def __init__(self, font_path=None, font_size=None, y_offset=None, box_center=None, force_vector=False):
        auto_sz, auto_y, auto_center = auto_detect_font_config(font_path)
        self.font_size = font_size if font_size is not None else auto_sz
        self.y_offset = y_offset if y_offset is not None else auto_y
        self.box_center = box_center if box_center is not None else auto_center
        self.force_vector = force_vector
        self.faces = []
        self.pil_fonts = []
        self.cache = {}
        self.cache_7x16 = {}
        self.multi_font_map = {}

        if font_path is None:
            # Setup multi-font demo mapping when no explicit font is forced
            fonts_dir = os.path.join(SCRIPT_DIR, "fonts")
            for chars, f_file, sz, y_off, box_c, force_vec in MULTI_FONT_SPECS:
                fp = os.path.join(fonts_dir, f_file)
                if os.path.exists(fp):
                    try:
                        sub_r = HangulRasterizer(font_path=fp, font_size=sz, y_offset=y_off, box_center=box_c, force_vector=force_vec)
                        for c in chars:
                            self.multi_font_map[c] = sub_r
                    except Exception:
                        pass

        font_paths = []
        if font_path:
            register_font_mapping(font_path)
            raw_entries = [p.split("=", 1)[1].strip() if "=" in p else p.strip() for p in font_path.split(",") if p.strip()]
            for item in raw_entries:
                candidate_p = [
                    item,
                    os.path.join(SCRIPT_DIR, "fonts", item),
                    os.path.join(EXE_DIR, "fonts", item),
                    os.path.join(SCRIPT_DIR, item),
                    os.path.join(EXE_DIR, item)
                ]
                found = False
                for cp in candidate_p:
                    if os.path.exists(cp):
                        abs_p = os.path.abspath(cp)
                        if abs_p not in font_paths:
                            font_paths.append(abs_p)
                        found = True
                        break
                if not found:
                    print(f"[Warning] Specified font '{item}' not found, skipping.")
        for p in FONT_CANDIDATES:
            if os.path.exists(p):
                abs_p = os.path.abspath(p)
                if abs_p not in font_paths:
                    font_paths.append(abs_p)

        if not font_paths:
            raise FileNotFoundError("Could not find a valid TrueType font.")

        if HAVE_FREETYPE:
            for p in font_paths:
                try:
                    f = freetype.Face(p)
                    auto_sz, _, _ = auto_detect_font_config(p)
                    eff_sz = self.font_size if font_size is not None else auto_sz
                    f.set_pixel_sizes(0, eff_sz)
                    self.faces.append(f)
                    print(f"[Font-FreeType] Loaded: {p}")
                except Exception:
                    pass
        else:
            # Pillow (PIL) mode
            for p in font_paths:
                try:
                    f = ImageFont.truetype(p, self.font_size)
                    self.pil_fonts.append(f)
                    print(f"[Font-Pillow] Loaded: {p}")
                except Exception:
                    pass

    def get_blank_glyph(self):
        return bytes(32)

    def get_cursor_glyph(self):
        data = bytearray(32)
        data[14 * 2] = 0x7F
        data[14 * 2 + 1] = 0x7F
        data[15 * 2] = 0x7F
        data[15 * 2 + 1] = 0x7F
        return bytes(data)

    def rasterize(self, ch):
        if OLD_HANGUL is not None and OLD_HANGUL.owns(ch):
            return OLD_HANGUL.render(ch)
        if ch in self.cache:
            return self.cache[ch]

        if ch in self.multi_font_map:
            glyph = self.multi_font_map[ch].rasterize(ch)
            self.cache[ch] = glyph
            return glyph

        if ch == ' ':
            glyph = self.get_blank_glyph()
            self.cache[ch] = glyph
            return glyph

        grid = [[0]*14 for _ in range(16)]

        if HAVE_FREETYPE and self.faces:
            code = ord(ch)
            target_face = None
            render_char = ch

            # 1. Try exact char in faces
            for f in self.faces:
                if f.get_char_index(code) != 0:
                    target_face = f
                    break

            # 2. Check Hanja variant mapping (prefer clean bitmap in primary font if available)
            if code in HANJA_VARIANTS:
                alt_code = HANJA_VARIANTS[code]
                if self.faces[0].get_char_index(alt_code) != 0:
                    target_face = self.faces[0]
                    render_char = chr(alt_code)
                elif target_face is None:
                    for f in self.faces:
                        if f.get_char_index(alt_code) != 0:
                            target_face = f
                            render_char = chr(alt_code)
                            break

            if target_face is None:
                target_face = self.faces[0]

            load_flags = freetype.FT_LOAD_RENDER | freetype.FT_LOAD_MONOCHROME
            if self.force_vector:
                load_flags |= freetype.FT_LOAD_NO_BITMAP

            target_face.load_char(render_char, load_flags)
            bitmap = target_face.glyph.bitmap
            top = target_face.glyph.bitmap_top
            
            if self.box_center:
                start_y = max(0, (16 - bitmap.rows) // 2) + self.y_offset
            else:
                baseline_y = 13
                start_y = baseline_y - top + self.y_offset
            start_x = max(0, (14 - bitmap.width) // 2)
            
            if bitmap.pixel_mode == freetype.FT_PIXEL_MODE_MONO:
                for r in range(bitmap.rows):
                    y = start_y + r
                    if 0 <= y < 16:
                        for c in range(bitmap.width):
                            x = start_x + c
                            if 0 <= x < 14:
                                byte_val = bitmap.buffer[r * bitmap.pitch + (c // 8)]
                                bit_val = (byte_val >> (7 - (c % 8))) & 1
                                if bit_val:
                                    grid[y][x] = 1
            else:
                for r in range(bitmap.rows):
                    y = start_y + r
                    if 0 <= y < 16:
                        for c in range(bitmap.width):
                            x = start_x + c
                            if 0 <= x < 14:
                                if bitmap.buffer[r * bitmap.pitch + c] >= 64:
                                    grid[y][x] = 1
        else:
            # Pillow (PIL) backend
            render_char = ch
            if ord(ch) in HANJA_VARIANTS:
                render_char = chr(HANJA_VARIANTS[ord(ch)])
            target_font = self.pil_fonts[0]
            im = Image.new('1', (14, 16), 0)
            draw = ImageDraw.Draw(im)
            bbox = target_font.getbbox(render_char)
            if bbox:
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                x_off = max(0, (14 - w) // 2) - bbox[0]
                if self.box_center:
                    y_off = max(0, (16 - h) // 2) - bbox[1] + self.y_offset
                else:
                    y_off = max(0, (16 - h) // 2) - bbox[1] + self.y_offset
                draw.text((x_off, y_off), render_char, font=target_font, fill=1)
            
            for r in range(16):
                for c in range(14):
                    if im.getpixel((c, r)):
                        grid[r][c] = 1

        hgr_grid = grid

        # Pack into 32 bytes Apple II HGR format
        raw_bytes = bytearray(32)
        for r in range(16):
            b0 = 0
            for c in range(7):
                if hgr_grid[r][c]:
                    b0 |= (1 << c)
            b1 = 0
            for c in range(7):
                if hgr_grid[r][c + 7]:
                    b1 |= (1 << c)
            raw_bytes[r * 2] = b0
            raw_bytes[r * 2 + 1] = b1
            
        glyph = bytes(raw_bytes)
        self.cache[ch] = glyph
        return glyph

    def rasterize_7x16(self, ch):
        if ch in self.cache_7x16:
            return self.cache_7x16[ch]
        
        if ch == ' ':
            g = bytes(16)
            self.cache_7x16[ch] = g
            return g

        grid = [[0]*7 for _ in range(16)]

        if HAVE_FREETYPE and self.faces:
            code = ord(ch)
            target_face = self.faces[0]
            load_flags = freetype.FT_LOAD_RENDER | freetype.FT_LOAD_MONOCHROME
            if self.force_vector:
                load_flags |= freetype.FT_LOAD_NO_BITMAP
            target_face.load_char(ch, load_flags)
            bitmap = target_face.glyph.bitmap
            top = target_face.glyph.bitmap_top
            
            if self.box_center:
                start_y = max(0, (16 - bitmap.rows) // 2) + self.y_offset
            else:
                baseline_y = 13
                start_y = baseline_y - top + self.y_offset
            start_x = max(0, (7 - bitmap.width) // 2)
            
            if bitmap.pixel_mode == freetype.FT_PIXEL_MODE_MONO:
                for r in range(bitmap.rows):
                    y = start_y + r
                    if 0 <= y < 16:
                        for c in range(bitmap.width):
                            x = start_x + c
                            if 0 <= x < 7:
                                byte_val = bitmap.buffer[r * bitmap.pitch + (c // 8)]
                                bit_val = (byte_val >> (7 - (c % 8))) & 1
                                if bit_val:
                                    grid[y][x] = 1
            else:
                for r in range(bitmap.rows):
                    y = start_y + r
                    if 0 <= y < 16:
                        for c in range(bitmap.width):
                            x = start_x + c
                            if 0 <= x < 7:
                                if bitmap.buffer[r * bitmap.pitch + c] >= 64:
                                    grid[y][x] = 1
        else:
            target_font = self.pil_fonts[0]
            im = Image.new('1', (7, 16), 0)
            draw = ImageDraw.Draw(im)
            bbox = target_font.getbbox(ch)
            if bbox:
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                x_off = max(0, (7 - w) // 2) - bbox[0]
                y_off = max(0, (16 - h) // 2) - bbox[1]
                draw.text((x_off, y_off), ch, font=target_font, fill=1)
            
            for r in range(16):
                for c in range(7):
                    if im.getpixel((c, r)):
                        grid[r][c] = 1

        hgr_grid = grid

        raw = bytearray(16)
        for r in range(16):
            b0 = 0
            for c in range(7):
                if hgr_grid[r][c]:
                    b0 |= (1 << c)
            raw[r] = b0
            
        g = bytes(raw)
        self.cache_7x16[ch] = g
        return g

class KoreanAutomata:
    """2-Bul-Sik Korean input automaton that composes the way the Windows
    Korean IME does.

    The syllable being composed is kept as the jamo typed for it, in three
    slots: leading consonants, vowels and final consonants. Each slot holds
    one jamo or a pair that combines (ㅗ+ㅏ=ㅘ, ㄹ+ㄱ=ㄺ). Backspace takes back
    the last jamo typed, so ㅘ goes back to ㅗ and 닭 to 달.

    guess_caps: for keys from an Apple II whose Shift the PC cannot see.
    Caps Lock sends every letter in upper case, and only the case tells
    Shift+R (ㄲ) from R (ㄱ). A //e starts with Caps Lock on, so it is taken
    to be on: letters count as unshifted (EO is 대). A lower-case letter
    shows it is off: from then on case counts, and the syllable being
    composed is read again from its keys as typed (Shift+R then k: ㄱ, then
    까). An upper-case letter that Shift does nothing for in 2-Bul-Sik (any
    but Q W E R T O P) shows it is on again.
    """
    SHIFTED = "QWERTOP"

    def __init__(self, guess_caps=False):
        self.guess_caps = guess_caps
        self.caps_on = True           # as a //e starts
        self.keys = []    # the keys of the syllable being composed, as typed
        self.reset()

    def reset(self):
        self.lead = []    # 1 consonant, or 2 that pair (ㄳ typed alone)
        self.vowel = []   # 1 vowel, or 2 that pair
        self.tail = []    # 1 final consonant, or 2 that pair
        self.order = []   # slot of each jamo in typing order, for backspace

    @staticmethod
    def _pair(parts, pairs):
        return parts[0] if len(parts) == 1 else pairs[tuple(parts)]

    def get_current_char(self):
        if not self.lead and not self.vowel:
            return ""
        if not self.vowel:
            return self._pair(self.lead, CONSONANT_PAIRS)
        v = self._pair(self.vowel, VOWEL_PAIRS)
        if not self.lead:
            return v
        jong = JONG_LIST.index(self._pair(self.tail, CONSONANT_PAIRS)) if self.tail else 0
        return compose_syllable(CHO_LIST.index(self.lead[0]), JUNG_LIST.index(v), jong)

    def _add(self, slot, jamo):
        getattr(self, slot).append(jamo)
        self.order.append(slot)

    def _restart(self, slot, jamo):
        committed = self.get_current_char()
        self.reset()
        self._add(slot, jamo)
        return committed

    def feed(self, jamo):
        """Adds one compatibility jamo; returns the text committed by it."""
        if jamo in JUNG_LIST:
            if self.tail:
                # The last final consonant leads the new syllable: 닭+ㅏ = 달가
                moved = self.tail.pop()
                self.order.pop()
                committed = self.get_current_char()
                self.reset()
                self._add('lead', moved)
                self._add('vowel', jamo)
                return committed
            if self.vowel:
                if len(self.vowel) == 1 and (self.vowel[0], jamo) in VOWEL_PAIRS:
                    self._add('vowel', jamo)
                    return ""
                return self._restart('vowel', jamo)
            if len(self.lead) == 2:
                # ㄳ+ㅏ = ㄱ사
                first, second = self.lead
                self.reset()
                self._add('lead', second)
                self._add('vowel', jamo)
                return first
            self._add('vowel', jamo)
            return ""

        # Consonant
        if not self.vowel:
            if not self.lead:
                self._add('lead', jamo)
                return ""
            if len(self.lead) == 1 and (self.lead[0], jamo) in CONSONANT_PAIRS:
                self._add('lead', jamo)
                return ""
            return self._restart('lead', jamo)
        if not self.lead:
            return self._restart('lead', jamo)  # after a lone vowel
        if not self.tail:
            if jamo in JONG_LIST:
                self._add('tail', jamo)
                return ""
            return self._restart('lead', jamo)  # ㄸ ㅃ ㅉ never end a syllable
        if len(self.tail) == 1 and (self.tail[0], jamo) in CONSONANT_PAIRS:
            self._add('tail', jamo)
            return ""
        return self._restart('lead', jamo)

    # Engine interface shared with apple_ime.py (used by the Ctrl+K line)
    def takes(self, ch):
        return ch.isascii() and ch.isalpha()

    def key(self, ch):
        return self.process_key(ch)[0]

    def current(self):
        return self.get_current_char()

    def flush(self):
        """Commits whatever is being composed and returns it."""
        committed = self.get_current_char()
        self.reset()
        self.keys = []
        return committed

    def _feed_key(self, typed):
        """Feeds a key as typed, read as unshifted while Caps Lock is guessed on."""
        key = typed.lower() if self.guess_caps and self.caps_on else typed
        committed = self.feed(DUBEOL_KEYS.get(key) or DUBEOL_KEYS[key.lower()])
        # Every key gives one jamo, so the syllable being composed is made of
        # the last len(order) keys
        self.keys = (self.keys + [typed])[len(self.keys) + 1 - len(self.order):]
        return committed

    def _read_again(self):
        """The syllable being composed, from its keys as typed, with the Caps
        Lock guess just changed."""
        again = list(self.keys)
        self.reset()
        self.keys = []
        return "".join(self._feed_key(k) for k in again)

    def process_key(self, key):
        """Feeds one keyboard letter. Returns (committed_text, composing_char)."""
        if key not in DUBEOL_KEYS and key.lower() not in DUBEOL_KEYS:
            return (self.flush() + key, "")
        committed = ""
        if self.guess_caps and key.isascii() and key.isalpha():
            if key.islower() and self.caps_on:
                self.caps_on = False            # Caps Lock is off after all
                committed += self._read_again()
            elif key.isupper() and key not in self.SHIFTED and not self.caps_on:
                self.caps_on = True             # Caps Lock is on
                committed += self._read_again()
        committed += self._feed_key(key)
        return (committed, self.get_current_char())

    def backspace(self):
        """Takes back the last jamo typed. Returns the new composing char
        ("" when nothing is left), or None when nothing was being composed."""
        if not self.order:
            return None
        getattr(self, self.order.pop()).pop()
        self.keys = self.keys[:-1]
        return self.get_current_char()

def encode_apple2_multilingual(line):
    out = bytearray()
    i = 0
    while i < len(line):
        if ord(line[i]) <= 127:
            out.append(ord(line[i]))
            i += 1
        else:
            start = i
            while i < len(line) and ord(line[i]) > 127:
                i += 1
            chunk = line[start:i]
            hx = chunk.encode('utf-8').hex().upper().encode('ascii')
            out.extend(b'\\K' + hx + b'\\N')
    return bytes(out)

def decode_apple2_multilingual(raw):
    try:
        s = raw.decode('utf-8')
        if any(ord(c) > 127 for c in s):
            return s
    except UnicodeDecodeError:
        pass

    out = []
    i = 0
    while i < len(raw):
        if i + 1 < len(raw) and bytes(raw[i:i+2]) in (b'\\K', b'\\k'):
            end = raw.find(b'\\N', i + 2)
            if end == -1:
                end = raw.find(b'\\n', i + 2)
            if end != -1:
                hex_data = raw[i+2:end]
                try:
                    decoded_chunk = bytes.fromhex(hex_data.decode('ascii')).decode('utf-8')
                    out.append(decoded_chunk)
                    i = end + 2
                    continue
                except Exception:
                    pass
        out.append(chr(raw[i]))
        i += 1
    return ''.join(out)

    return ''.join(out)

def prompt_korean_dialog():
    """
    Pops up a dedicated, guaranteed TOP-MOST GUI dialog for Korean/Hanja text input.
    Directly brings itself to foreground above AppleWin and focuses the input box.
    """
    result = [""]
    try:
        import tkinter as tk
        from tkinter import ttk

        root = tk.Tk()
        root.title("Apple II 한글 / 漢字 입력")
        root.attributes("-topmost", True)
        root.resizable(False, False)

        # Dialog dimensions and centering on screen
        dlg_w, dlg_h = 440, 160
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = max(0, (sw - dlg_w) // 2)
        y = max(0, (sh - dlg_h) // 2)
        root.geometry(f"{dlg_w}x{dlg_h}+{x}+{y}")

        # Frame and widgets
        frame = ttk.Frame(root, padding="16 14 16 14")
        frame.pack(fill=tk.BOTH, expand=True)

        lbl = ttk.Label(
            frame,
            text="Apple II로 전송할 한글 또는 漢字를 입력하세요:\n(Enter: 입력 완료, Esc: 취소)",
            font=("Malgun Gothic", 10)
        )
        lbl.pack(anchor=tk.W, pady=(0, 8))

        entry_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=entry_var, font=("Malgun Gothic", 12))
        entry.pack(fill=tk.X, pady=(0, 12))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)

        def on_ok(event=None):
            result[0] = entry_var.get()
            root.destroy()

        def on_cancel(event=None):
            result[0] = ""
            root.destroy()

        btn_ok = ttk.Button(btn_frame, text="입력 완료 (Enter)", command=on_ok)
        btn_ok.pack(side=tk.RIGHT, padx=(5, 0))

        btn_cancel = ttk.Button(btn_frame, text="취소 (Esc)", command=on_cancel)
        btn_cancel.pack(side=tk.RIGHT)

        root.bind("<Return>", on_ok)
        root.bind("<Escape>", on_cancel)

        # Force window to top and set focus immediately
        root.lift()
        root.focus_force()
        entry.focus_set()

        try:
            import ctypes
            hwnd = root.winfo_id()
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

        root.mainloop()
        return result[0]
    except Exception as e:
        print(f"[Dialog Exception] {e}")
        return ""

IME_LANGS = {
    # name: (mode cell, engine factory)
    'ko':   ('한', KoreanAutomata),
    'hira': ('あ', apple_ime.KanaEngine),
    'kata': ('ア', lambda: apple_ime.KanaEngine(katakana=True)),
    'ru':   ('Я', apple_ime.russian_engine),
    'el':   ('Ω', apple_ime.greek_engine),
}


def _is_hangul_syllable(text):
    return len(text) == 1 and 0xAC00 <= ord(text) <= 0xD7A3


class AppleIme:
    """Ctrl+K input line typed on the Apple II keyboard.

    The driver sends each key as typed. The line is drawn on HGR row 9, the
    last row shown in mixed mode, while the BASIC line stays in the four text
    lines below; Hanja candidates use row 8 above it. As in Windows, what is
    being composed is shown inverse and commits once the next key cannot
    join it.

    Col 0 shows the mode: 한 (2-Bul-Sik), あ / ア (romaji to hiragana /
    katakana), Я (Russian ЙЦУКЕН), Ω (Greek) or A (as typed).
      Ctrl+K   language <-> A, as the 한/영 key
      Ctrl+L   next language
      Ctrl+J   (down arrow) Hanja for the syllable being composed or the one
               before the cursor: 1-9 picks, Space / arrows page, Esc closes
      Ctrl+P   PC input box (Windows IME, paste); its text is added
      Return   types the line into BASIC as hex-safe \\K...\\N
      Esc      cancels
    """
    ROW = 9
    CAND_ROW = 8
    COLS = 20
    PER_PAGE = 9
    MAX_PAYLOAD = 200       # bytes the driver's 256-byte input buffer takes
    BLANK = (' ', 'plain')  # the driver blanks both rows when it shows them

    def __init__(self, server):
        self.server = server
        self.engines = {}
        self.units = []     # committed characters (an old Hangul syllable is one)
        self.view = 0       # index of the first unit shown
        self.cand = None    # open Hanja list: {'list', 'page', 'composing'}
        self.drawn = {}     # (row, col) -> cell last drawn there
        self.saved_mode = server._last_sent_mode
        server.send_raw(bytes([server.CMD_SET_MODE, 0]))
        server._last_sent_mode = 0
        self.render()

    @property
    def lang(self):
        s = self.server
        return s.ime_langs[s.ime_lang % len(s.ime_langs)]

    @property
    def engine(self):
        """The engine of the current language, or None in A mode."""
        if self.server.ime_latin:
            return None
        if self.lang not in self.engines:
            eng = IME_LANGS[self.lang][1]()
            if isinstance(eng, KoreanAutomata):
                eng.guess_caps = not self.server._pc_shift_visible()
            self.engines[self.lang] = eng
        return self.engines[self.lang]

    def text(self):
        eng = self.engine
        return ''.join(self.units) + (eng.current() if eng else '')

    def fits(self, more):
        return len(encode_apple2_multilingual(self.text() + more)) <= self.MAX_PAYLOAD

    def commit(self):
        if self.engine:
            self.units.extend(self.engine.flush())

    def key(self, b):
        """Handles one key from the Apple II. Returns True once input has ended."""
        s = self.server
        b &= 0x7F
        if os.environ.get("APPLE_IME_DEBUG"):
            print(f"[IME key] ${b:02X}")
        if self.cand is not None:
            if self.candidate_key(b):
                self.render()
                return False
            self.cand = None    # any other key closes the list and goes on as usual
        if b == 0x1B:
            return self.finish("")
        if b == 0x0D:
            return self.finish(self.text())
        if b in (0x08, 0x7F):
            eng = self.engine
            if (eng is None or eng.backspace() is None) and self.units:
                self.units.pop()
        elif b == 0x0B:
            self.commit()
            s.ime_latin = not s.ime_latin
        elif b == 0x0C:
            self.commit()
            if s.ime_latin:
                s.ime_latin = False
            else:
                s.ime_lang = (s.ime_lang + 1) % len(s.ime_langs)
        elif b == 0x0A:
            self.open_hanja()
        elif b == 0x10:
            self.commit()
            for unit in compose_old_hangul(s.ask_pc_text()):
                if not self.fits(unit):
                    break
                self.units.append(unit)
        elif 0x20 <= b <= 0x7E:
            ch = chr(b)
            eng = self.engine
            if eng is not None and eng.takes(ch):
                if self.fits('가가'):
                    self.units.extend(eng.key(s.hangul_key_case(ch)))
            elif self.fits(ch):
                self.commit()
                self.units.append(ch)
        else:
            return False
        self.render()
        return False

    def open_hanja(self):
        if self.server.ime_latin or self.lang != 'ko':
            return
        cur = self.engine.current()
        if _is_hangul_syllable(cur):
            syllable, composing = cur, True
        elif self.units and _is_hangul_syllable(self.units[-1]):
            syllable, composing = self.units[-1], False
        else:
            return
        cands = apple_ime.hanja_candidates(syllable)
        if cands:
            self.cand = {'list': cands, 'page': 0, 'composing': composing}

    def candidate_key(self, b):
        """Keys while the Hanja list is open. True when the key was used."""
        c = self.cand
        pages = (len(c['list']) + self.PER_PAGE - 1) // self.PER_PAGE
        first = c['page'] * self.PER_PAGE
        if ord('1') <= b <= ord('9'):
            i = first + b - ord('1')
            if i < len(c['list']):
                self.pick(c['list'][i])
            return True
        if b == 0x0D:
            self.pick(c['list'][first])
            return True
        if b in (0x20, 0x15, 0x0A):     # Space, right / down arrow
            c['page'] = (c['page'] + 1) % pages
            return True
        if b in (0x08, 0x0B):           # left / up arrow
            c['page'] = (c['page'] - 1) % pages
            return True
        if b == 0x1B:
            self.cand = None
            return True
        return False

    def pick(self, hanja):
        if self.cand['composing']:
            self.engine.reset()
            self.units.append(hanja)
        else:
            self.units[-1] = hanja
        self.cand = None

    def finish(self, text):
        s = self.server
        payload = encode_apple2_multilingual(text) if text else b''
        s.send_raw(bytes([s.CMD_INPUT_BYTES, len(payload)]) + payload)
        s._last_sent_mode = self.saved_mode
        try:
            if text:
                print(f"[Ctrl+K 입력] '{text}' ({len(payload)} 바이트) -> Apple II BASIC 줄에 입력")
            else:
                print("[Ctrl+K 취소] 입력 없이 BASIC 줄로 복귀")
        except Exception:
            pass
        return True

    def render(self):
        eng = self.engine
        cur = eng.current() if eng else ''
        content = [(u, 'plain') for u in self.units]
        content += [(c, 'inverse') for c in cur] or [(' ', 'cursor')]
        room = self.COLS - 2    # after the mode cell and the divider
        if len(content) - self.view > room or len(content) <= self.view:
            # Page by half a line, so the whole row is redrawn only now and then
            self.view = max(0, len(content) - room // 2)
        mode = 'A' if self.server.ime_latin else IME_LANGS[self.lang][0]
        # The divider keeps the mode (한, あ, A ...) from reading as typed text
        line = [(mode, 'inverse'), ('│', 'plain')] + content[self.view:self.view + room]

        cands = []
        if self.cand is not None:
            c = self.cand
            first = c['page'] * self.PER_PAGE
            for n, h in enumerate(c['list'][first:first + self.PER_PAGE], 1):
                cands += [(str(n), 'inverse'), (h, 'plain')]
            cands += [self.BLANK] * (self.COLS - 2 - len(cands))
            cands += [('<' if c['page'] > 0 else ' ', 'plain'),
                      ('>' if first + self.PER_PAGE < len(c['list']) else ' ', 'plain')]

        for row, cells in ((self.CAND_ROW, cands), (self.ROW, line)):
            cells = cells + [self.BLANK] * (self.COLS - len(cells))
            for col, cell in enumerate(cells):
                if self.drawn.get((row, col), self.BLANK) != cell:
                    self.draw(row, col, cell)
                    self.drawn[(row, col)] = cell

    def draw(self, row, col, cell):
        ch, style = cell
        glyph = bytearray(self.server.rasterizer.rasterize(ch) if ch != ' ' else bytes(32))
        if style == 'inverse':
            glyph = bytearray(x ^ 0x7F for x in glyph)
        elif style == 'cursor':
            for i in range(28, 32):     # underline on rows 14-15
                glyph[i] |= 0x7F
        self.server.send_raw(bytes([self.server.CMD_DRAW_GLYPH, col, row]) + bytes(glyph))


class HangulTerminalServer:
    CMD_DRAW_14x16  = 0x81
    CMD_CLEAR       = 0x82
    CMD_EXIT        = 0x83
    CMD_SCROLL      = 0x84
    CMD_DRAW_7x16   = 0x85
    CMD_INPUT_BYTES = 0x86
    CMD_SET_MODE    = 0x88
    CMD_DONE        = 0x00

    CMD_DRAW_GLYPH  = 0x81

    MAX_COLS = 20
    MAX_ROWS = 12

    def __init__(self, host="127.0.0.1", port=1977, com_port=None, font_path=None, font_size=None, y_offset=None, box_center=None, force_vector=False, use_popup=False, color=3, draw_mode="replace", color_font=None, pc_input=False, ime_langs=("ko", "hira", "kata", "ru", "el")):
        self.host = host
        self.port = port
        self.com_port = com_port
        self.sock = None
        self.serial_io = None
        self.running = False
        self.use_popup = use_popup
        # Ctrl+K in BASIC: False types 2-Bul-Sik on the Apple II keyboard
        # (AppleIme); True opens the PC input box straight away, as before.
        self.pc_input = pc_input
        self.ime = None
        
        self.rasterizer = HangulRasterizer(font_path=font_path, font_size=font_size, y_offset=y_offset, box_center=box_center, force_vector=force_vector)
        self.default_rasterizer = self.rasterizer
        self.current_rasterizer = self.rasterizer
        self.automata = KoreanAutomata()
        self.color_rasterizer = ColorRasterizer(
            [p.strip() for p in color_font.split(",") if p.strip()] if color_font else None)

        self.cur_col = 0
        self.cur_row = 0
        self.current_color = parse_hgr_color(color, default=3)
        self.current_mode = parse_draw_mode(draw_mode, default=0)
        self._last_sent_mode = 0
        self.has_drawn = False
        self.hangul_mode = True # Default Korean 2-bul-sik mode
        # Mode of the Ctrl+K line, kept between uses: a language from
        # ime_langs (IME_LANGS keys), or A (as typed) when ime_latin
        self.ime_langs = list(ime_langs)
        self.ime_lang = 0
        self.ime_latin = False
        self.mode = "INIT"      # "TERMINAL" or "BASIC"
        self.utf8_mode = False
        self.utf8_buf = bytearray()

    def connect(self):
        if self.com_port:
            import serial
            print(f"[Serial] Connecting to {self.com_port} at 9600 baud...")
            self.serial_io = serial.Serial(self.com_port, 9600, timeout=1)
            print("[Serial] Connected.")
        else:
            print(f"[TCP] Connecting to AppleWin SSC at {self.host}:{self.port}...")
            while True:
                try:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.connect((self.host, self.port))
                    print(f"[TCP] Successfully connected to AppleWin on {self.host}:{self.port}!")
                    break
                except ConnectionRefusedError:
                    print(f"[TCP] AppleWin port {self.port} not ready. Retrying in 1s... (Make sure AppleWin is running with Slot 2 = TCP)")
                    time.sleep(1)

    def send_raw(self, data: bytes):
        if self.sock:
            self.sock.sendall(data)
        elif self.serial_io:
            self.serial_io.write(data)

    def recv_byte(self):
        if self.sock:
            data = self.sock.recv(1)
            return data[0] if data else None
        elif self.serial_io:
            data = self.serial_io.read(1)
            return data[0] if data else None

    def set_apple2_draw_mode(self, mode_val: int):
        mode_val = parse_draw_mode(mode_val, default=0)
        self.current_mode = mode_val
        # Always sent: the Apple II may have been reset since the last one (its
        # driver then starts in replace mode) without the server knowing.
        self.send_raw(bytes([self.CMD_SET_MODE, mode_val]))
        self._last_sent_mode = mode_val

    def draw_glyph_at(self, col, row, glyph_bytes, color=None, mode=None, ch=None):
        eff_mode = self.current_mode if mode is None else parse_draw_mode(mode, default=self.current_mode)
        if eff_mode != self._last_sent_mode:
            self.send_raw(bytes([self.CMD_SET_MODE, eff_mode]))
            self._last_sent_mode = eff_mode
        eff_color = self.current_color if color is None else parse_hgr_color(color, default=self.current_color)
        columns = None
        if ch is not None and eff_color not in (0, 3, 4, 7):
            columns = self.color_rasterizer.rasterize(ch)
        if columns is not None:
            colored_glyph = color_glyph_from_columns(columns, eff_color)
        else:
            colored_glyph = apply_color_to_glyph(glyph_bytes, eff_color)
        packet = bytearray([self.CMD_DRAW_GLYPH, col, row]) + colored_glyph
        self.send_raw(packet)

    def clear_screen(self):
        self.send_raw(bytes([self.CMD_CLEAR]))
        self.cur_col = 0
        self.cur_row = 0
        self.automata.reset()

    def advance_cursor(self):
        self.cur_col += 1
        if self.cur_col >= self.MAX_COLS:
            self.newline()

    def scroll_up(self):
        self.send_raw(bytes([self.CMD_SCROLL]))
        time.sleep(0.02)

    def newline(self):
        self.cur_col = 0
        if self.cur_row < self.MAX_ROWS - 1:
            self.cur_row += 1
        else:
            self.scroll_up()

    def put_char(self, ch):
        if ch == '\n' or ch == '\r':
            self.newline()
            return
        
        glyph = self.rasterizer.rasterize(ch)
        self.draw_glyph_at(self.cur_col, self.cur_row, glyph, ch=ch)
        self.advance_cursor()

    def put_string(self, text):
        for ch in compose_old_hangul(text):
            self.put_char(ch)

    def hangul_key_case(self, ch):
        """Decides whether an upper-case letter from the Apple II was typed with
        Shift (ㄲ ㄸ ㅃ ㅆ ㅉ ㅒ ㅖ) or only under Caps Lock.

        AppleWin on this PC: the PC's own Shift key says which. Caps Lock is on
        by default in AppleWin, so the letter's case alone would read every
        R as ㄲ. Elsewhere (real hardware, an emulator on another machine)
        the byte's case is all there is: the letter goes as it came, and
        KoreanAutomata.guess_caps tells Caps Lock from Shift.
        """
        if not ('A' <= ch <= 'Z') or not self._pc_shift_visible():
            return ch
        try:
            import ctypes
            shift = (ctypes.windll.user32.GetAsyncKeyState(0x10) & 0x8000) != 0
        except Exception:
            return ch
        return ch if shift else ch.lower()

    def _pc_shift_visible(self):
        return (os.name == 'nt' and self.sock is not None
                and self.host in ('127.0.0.1', 'localhost', '::1'))

    def handle_apple2_key(self, b):
        ch = chr(b)
        
        # ESC: the driver has left terminal mode; back to BASIC, server keeps running
        if b == 0x1B:
            print("\n[Term] Terminal mode closed on the Apple II, back to BASIC.")
            self.automata.reset()
            self.mode = "BASIC"
            return

        # Backspace (0x08 or 0x7F)
        if b == 0x08 or b == 0x7F:
            sub = self.automata.backspace()
            if sub is not None:
                if sub == "":
                    blank = self.rasterizer.get_blank_glyph()
                    self.draw_glyph_at(self.cur_col, self.cur_row, blank)
                else:
                    glyph = self.rasterizer.rasterize(sub)
                    self.draw_glyph_at(self.cur_col, self.cur_row, glyph)
            else:
                if self.cur_col > 0:
                    self.cur_col -= 1
                    blank = self.rasterizer.get_blank_glyph()
                    self.draw_glyph_at(self.cur_col, self.cur_row, blank)
            return

        # Return (0x0D)
        if b == 0x0D:
            comm = self.automata.get_current_char()
            if comm:
                glyph = self.rasterizer.rasterize(comm)
                self.draw_glyph_at(self.cur_col, self.cur_row, glyph)
            self.automata.reset()
            self.newline()
            return

        # Space (0x20)
        if b == 0x20:
            comm = self.automata.get_current_char()
            if comm:
                glyph = self.rasterizer.rasterize(comm)
                self.draw_glyph_at(self.cur_col, self.cur_row, glyph)
                self.advance_cursor()
            self.automata.reset()
            self.put_char(' ')
            return

        # Mode toggle (Ctrl+K = 0x0B or backquote '`')
        if b == 0x0B or ch == '`':
            self.hangul_mode = not self.hangul_mode
            mode_str = "한글 (2-Bul-Sik)" if self.hangul_mode else "English (ASCII)"
            print(f"\n[Mode Changed] -> {mode_str}")
            return

        norm_ch = self.hangul_key_case(ch)
        self.automata.guess_caps = not self._pc_shift_visible()

        # If in Hangul Mode and key is valid Hangul letter (a-z / A-Z)
        if self.hangul_mode and ((norm_ch >= 'a' and norm_ch <= 'z') or (norm_ch >= 'A' and norm_ch <= 'Z')):
            committed, current = self.automata.process_key(norm_ch)
            if committed:
                for c in committed:
                    glyph = self.rasterizer.rasterize(c)
                    self.draw_glyph_at(self.cur_col, self.cur_row, glyph)
                    self.advance_cursor()
            if current:
                glyph = self.rasterizer.rasterize(current)
                self.draw_glyph_at(self.cur_col, self.cur_row, glyph)
        else:
            comm = self.automata.get_current_char()
            if comm:
                glyph = self.rasterizer.rasterize(comm)
                self.draw_glyph_at(self.cur_col, self.cur_row, glyph)
                self.advance_cursor()
                self.automata.reset()
            self.put_char(ch)

    def handle_basic_cout(self, b):
        # Carriage Return (0x8D or 0x0D)
        if b == 0x8D or b == 0x0D:
            self.cur_col = 0
            if self.cur_row < self.MAX_ROWS - 1:
                self.cur_row += 1
                self.send_raw(bytes([self.CMD_DONE]))
            else:
                self.send_raw(bytes([self.CMD_SCROLL, self.CMD_DONE]))
            return

        # Backspace (0x88 or 0x08)
        if b == 0x88 or b == 0x08:
            if self.cur_col > 0:
                self.cur_col -= 1
                blank = bytes(16)
                self.send_raw(bytes([self.CMD_DRAW_7x16, self.cur_col, self.cur_row]) + blank + bytes([self.CMD_DONE]))
            else:
                self.send_raw(bytes([self.CMD_DONE]))
            return

        # FormFeed / Clear (0x8C or 0x0C)
        if b == 0x8C or b == 0x0C:
            self.cur_col = 0
            self.cur_row = 0
            self.send_raw(bytes([self.CMD_CLEAR, self.CMD_DONE]))
            return

        # Shift-Out: Begin UTF-8 Multilingual
        if b == 0x0E:
            self.utf8_mode = True
            self.utf8_buf.clear()
            self.send_raw(bytes([self.CMD_DONE]))
            return

        # Shift-In: End UTF-8 Multilingual
        if b == 0x0F:
            self.utf8_mode = False
            self.utf8_buf.clear()
            self.send_raw(bytes([self.CMD_DONE]))
            return

        if self.utf8_mode:
            self.utf8_buf.append(b)
            try:
                s = self.utf8_buf.decode('utf-8')
                self.utf8_buf.clear()
                glyph = self.current_rasterizer.rasterize(s) # 32 bytes 14x16
                if self.cur_col > 38:
                    self.cur_col = 0
                    if self.cur_row < self.MAX_ROWS - 1:
                        self.cur_row += 1
                    else:
                        self.send_raw(bytes([self.CMD_SCROLL]))
                pkt = bytes([self.CMD_DRAW_14x16, self.cur_col, self.cur_row]) + glyph + bytes([self.CMD_DONE])
                self.send_raw(pkt)
                self.cur_col += 2
                if self.cur_col >= 40:
                    self.cur_col = 0
                    if self.cur_row < self.MAX_ROWS - 1:
                        self.cur_row += 1
                    else:
                        self.send_raw(bytes([self.CMD_SCROLL]))
            except UnicodeDecodeError:
                # Waiting for more bytes of multi-byte UTF-8 sequence
                self.send_raw(bytes([self.CMD_DONE]))
            return

        # Standard ASCII
        ascii_code = b & 0x7F
        if 0x20 <= ascii_code <= 0x7E:
            ch = chr(ascii_code)
            glyph = self.rasterizer.rasterize_7x16(ch) # 16 bytes 7x16
            if self.cur_col > 39:
                self.cur_col = 0
                if self.cur_row < self.MAX_ROWS - 1:
                    self.cur_row += 1
                else:
                    self.send_raw(bytes([self.CMD_SCROLL]))
            pkt = bytes([self.CMD_DRAW_7x16, self.cur_col, self.cur_row]) + glyph + bytes([self.CMD_DONE])
            self.send_raw(pkt)
            self.cur_col += 1
            if self.cur_col >= 40:
                self.cur_col = 0
                if self.cur_row < self.MAX_ROWS - 1:
                    self.cur_row += 1
                else:
                    self.send_raw(bytes([self.CMD_SCROLL]))
        else:
            self.send_raw(bytes([self.CMD_DONE]))

    def ask_pc_text(self):
        """Asks for a line on the PC (popup or this console), typed with the
        Windows IME or pasted. Returns "" when cancelled."""
        if self.use_popup:
            print("한글 / 漢字 입력 팝업창을 엽니다...")
            return prompt_korean_dialog()
        print("이 콘솔창에 한글 또는 한자를 직접 입력(붙여넣기)한 후 Enter를 누르세요:")
        print("(입력을 취소하려면 내용 없이 Enter만 누르세요)")
        try:
            return input("한글/漢字 입력 > ")
        except (EOFError, KeyboardInterrupt):
            return ""

    def listen_apple2(self):
        """Thread that reads bytes from Apple II"""
        while self.running:
            try:
                b = self.recv_byte()
                if b is None:
                    time.sleep(0.01)
                    continue
                if self.ime is not None:
                    # Ctrl+K line: the driver sends nothing but keys until it ends
                    if self.ime.key(b):
                        self.ime = None
                    continue
                if b == 0xAA:
                    self.mode = "TERMINAL"
                    print("\n[Term] Terminal Client Handshake received from Apple II (READY!)")
                    self.clear_screen()
                    self.put_string("한글 터미널 준비완료\n")
                    self.put_string("Ctrl+K 한/영 ESC 끝\n")
                    self.put_string("--------------------\n")
                    continue
                if b == 0xAB:
                    self.mode = "BASIC"
                    self.send_raw(bytes([0x80])) # Send ACK
                    self.cur_col = 0
                    self.cur_row = 0
                    self.utf8_mode = False
                    self.utf8_buf.clear()
                    print("\n" + "=" * 50)
                    print("[System] Apple II Applesoft BASIC Multilingual Driver Active!")
                    print("  * On Apple II: Type BASIC code (e.g. 10 PRINT \"...\")")
                    print("  * Press Ctrl+K on Apple II anytime to input Korean/Hanja via PC")
                    print("  * Or type below in PC console to inject directly into BASIC")
                    print("=" * 50 + "\n")
                    continue

                if b == 0x87:
                    # CMD_PRINT_STRING: 10 & "문자열" executed from BASIC!
                    raw_bytes = bytearray()
                    while True:
                        ch_b = self.recv_byte()
                        if ch_b is None or ch_b == 0x00:
                            break
                        raw_bytes.append(ch_b)
                    
                    text = decode_apple2_multilingual(raw_bytes)
                    try:
                        print(f"\n[Apple II BASIC & 한글/漢字 출력] \"{text}\"")
                    except Exception:
                        pass

                    if text.strip() == "/clear":
                        self.clear_screen()
                        self.has_drawn = True
                        self.send_raw(bytes([0x00]))
                        continue

                    stripped_cmd = text.strip()
                    lower_cmd = stripped_cmd.lower()

                    # Dedicated command: & "/color <name_or_0-7>" or & "/c <name_or_0-7>"
                    if lower_cmd.startswith(("/color ", "/c ")):
                        parts = stripped_cmd.split(maxsplit=1)
                        if len(parts) > 1:
                            self.current_color = parse_hgr_color(parts[1].strip(), default=self.current_color)
                            print(f"[System] Active HGR color switched to: {self.current_color} ({parts[1].strip()})")
                        self.send_raw(bytes([0x00]))
                        continue

                    # Dedicated command: & "/mode <replace|overlay|xor>" or & "/overlay" or & "/replace" or & "/xor"
                    if lower_cmd.startswith("/mode "):
                        parts = stripped_cmd.split(maxsplit=1)
                        if len(parts) > 1:
                            m_val = parse_draw_mode(parts[1].strip(), default=self.current_mode)
                            self.set_apple2_draw_mode(m_val)
                            print(f"[System] Draw mode switched to: {m_val} ({parts[1].strip()})")
                        self.send_raw(bytes([0x00]))
                        continue

                    if lower_cmd in ("/overlay", "/over"):
                        self.set_apple2_draw_mode(1)
                        print("[System] Draw mode switched to: OVERLAY (1)")
                        self.send_raw(bytes([0x00]))
                        continue

                    if lower_cmd in ("/replace", "/rep"):
                        self.set_apple2_draw_mode(0)
                        print("[System] Draw mode switched to: REPLACE (0)")
                        self.send_raw(bytes([0x00]))
                        continue

                    if lower_cmd in ("/xor", "/invert"):
                        self.set_apple2_draw_mode(2)
                        print("[System] Draw mode switched to: XOR (2)")
                        self.send_raw(bytes([0x00]))
                        continue

                    # Dedicated command: & "/pos <col> <row>"
                    if lower_cmd.startswith("/pos "):
                        parts = stripped_cmd.split()
                        if len(parts) >= 3:
                            try:
                                self.cur_col = max(0, min(self.MAX_COLS - 1, int(parts[1])))
                                self.cur_row = max(0, min(self.MAX_ROWS - 1, int(parts[2])))
                                print(f"[System] Cursor positioned to col={self.cur_col}, row={self.cur_row}")
                            except ValueError:
                                pass
                        self.send_raw(bytes([0x00]))
                        continue

                    # Dedicated command: & "/font <name>" or & "/f <name>"
                    if lower_cmd.startswith(("/font ", "/f ")):
                        parts = stripped_cmd.split(maxsplit=1)
                        if len(parts) > 1:
                            target_f = parts[1].strip()
                            new_r = get_font_rasterizer(target_f, self.default_rasterizer)
                            if new_r:
                                self.current_rasterizer = new_r
                                print(f"[System] Active font switched to: {target_f}")
                        self.send_raw(bytes([0x00]))
                        continue

                    # Dedicated command: & "/font-add <slot> <font>" or & "/alias <slot> <font>"
                    if lower_cmd.startswith(("/font-add ", "/alias ")):
                        parts = stripped_cmd.split()
                        if len(parts) >= 3:
                            font_add(parts[1].strip(), parts[2].strip())
                        self.send_raw(bytes([0x00]))
                        continue

                    # Dedicated command: & "/font-del <slot>" or & "/font-remove <slot>" or & "/unalias <slot>"
                    if lower_cmd.startswith(("/font-del ", "/font-remove ", "/unalias ")):
                        parts = stripped_cmd.split()
                        if len(parts) >= 2:
                            font_del(parts[1].strip())
                        self.send_raw(bytes([0x00]))
                        continue

                    # Dedicated command: & "/font-clear"
                    if lower_cmd == "/font-clear":
                        font_clear()
                        self.send_raw(bytes([0x00]))
                        continue

                    if not self.has_drawn:
                        self.has_drawn = True
                        if self.current_mode == 0 and self.cur_col == 0 and self.cur_row == 0:
                            self.clear_screen()

                    segments = parse_styled_segments(
                        text,
                        default_font=None,
                        default_color=self.current_color,
                        default_mode=self.current_mode
                    )
                    for font_tag, color_val, mode_val, seg_text in segments:
                        active_r = get_font_rasterizer(font_tag, self.current_rasterizer) if font_tag else self.current_rasterizer
                        if color_val is not None:
                            self.current_color = color_val
                        if mode_val is not None:
                            self.set_apple2_draw_mode(mode_val)
                        for ch in compose_old_hangul(seg_text):
                            if ch == '\n' or ch == '\r':
                                self.newline()
                                continue
                            if ch == ' ' and self.current_mode != 0:
                                # In overlay / xor mode, space only advances cursor without touching background
                                self.advance_cursor()
                                continue
                            glyph = active_r.rasterize(ch)
                            self.draw_glyph_at(self.cur_col, self.cur_row, glyph, color=self.current_color, mode=self.current_mode, ch=ch)
                            self.advance_cursor()
                    self.newline()
                    self.send_raw(bytes([0x00])) # Send CMD_DONE
                    continue

                if b == 0x0B and self.mode != "TERMINAL":
                    # Ctrl+K requested by Apple II
                    print("\n" + "=" * 50)
                    print("[Apple II -> PC] Ctrl+K 특수키 감지!")
                    if not self.pc_input:
                        print("Apple II 키보드로 입력 (Ctrl+K 한/영, Ctrl+L 언어, Ctrl+J 한자, Return 입력, Esc 취소, Ctrl+P PC 입력창)")
                        print("=" * 50 + "\n")
                        self.ime = AppleIme(self)
                        continue
                    line = self.ask_pc_text()

                    if line:
                        payload = encode_apple2_multilingual(line)
                        if len(payload) > 200:
                            payload = payload[:200]
                        self.send_raw(bytes([self.CMD_INPUT_BYTES, len(payload)]) + payload)
                        try:
                            print(f"[전송 완료] '{line}' ({len(payload)} 바이트 인코딩 전송) -> Apple II로 전달됨")
                        except Exception:
                            pass
                    else:
                        self.send_raw(bytes([self.CMD_INPUT_BYTES, 0]))
                        print("[취소/원복] 입력 없이 Enter -> Apple II 키보드 모드로 즉시 복귀")
                    print("=" * 50 + "\n")
                    continue

                if self.mode == "BASIC":
                    self.handle_basic_cout(b)
                elif self.mode == "TERMINAL":
                    self.handle_apple2_key(b)
                else:
                    # Non-terminal mode: do not echo graphics packets back to Apple II!
                    pass
            except Exception as e:
                if self.running:
                    print(f"[Error in Rx] {e}")
                break

    def run_console_loop(self):
        """Allows user to type Korean/English directly on PC console to send to Apple II"""
        print("\n" + "=" * 50)
        print("Apple II Hangul Server Active (Listening for connection...)")
        print("Commands on PC console:")
        print("  /clear     - Clear Apple II screen")
        print("  /exit      - Exit server")
        print("=" * 50 + "\n")

        while self.running:
            try:
                line = input("PC Input > ")
                if not line:
                    continue
                if line.strip() == "/clear":
                    self.clear_screen()
                elif line.strip() == "/exit":
                    self.running = False
                    self.send_raw(bytes([self.CMD_EXIT]))
                    break
                elif line.startswith("/send "):
                    raw_text = line[6:] + "\r"
                    for b in raw_text.encode('latin1', 'ignore'):
                        self.send_raw(bytes([b]))
                        time.sleep(0.005)
                    print(f"[PC -> Apple II Raw] {line[6:]}")
                else:
                    if self.mode == "TERMINAL":
                        self.put_string(line + "\n")
                    else:
                        # Send directly to Apple II text / BASIC buffer
                        raw_text = line + "\r"
                        for b in raw_text.encode('latin1', 'ignore'):
                            self.send_raw(bytes([b]))
                            time.sleep(0.005)
                        print(f"[PC -> Apple II BASIC] {line}")
            except (EOFError, KeyboardInterrupt):
                self.running = False
                break

    def start(self):
        self.connect()
        self.running = True
        
        print("\n" + "=" * 50)
        print("Apple II Hangul Server Active (Port 1977 Connected)")
        if not self.pc_input:
            print("  * AppleWin에서 BASIC 작성 중 Ctrl+K 를 누르면")
            print("    Apple II 키보드로 2벌식 한글·가나·러시아어·그리스어를 입력합니다 (화면 아래 입력 줄).")
            print("    Ctrl+K 한/영, Ctrl+L 언어 바꾸기, Ctrl+J(↓) 한자, Return 입력, Esc 취소, Ctrl+P PC 입력창")
        elif self.use_popup:
            print("  * AppleWin에서 BASIC 작성 중 Ctrl+K 를 누르면")
            print("    화면에 한글 입력 팝업창이 바로 뜹니다.")
        else:
            print("  * AppleWin에서 BASIC 작성 중 Ctrl+K 를 누르면")
            print("    이 콘솔창에서 바로 한글/한자를 직접 입력(붙여넣기)할 수 있습니다.")
        print("  * 입력 후 Enter(Return)를 치면 Apple II로 전달됩니다.")
        print("  * 종료하려면 Ctrl+C 를 누르세요.")
        print("=" * 50 + "\n")

        try:
            self.listen_apple2()
        except KeyboardInterrupt:
            self.running = False
            print("\n[Term] Server stopped by user.")
        
        if self.sock:
            self.sock.close()
        if self.serial_io:
            self.serial_io.close()
        print("[Term] Server closed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apple II Hangul Terminal Server")
    parser.add_argument("--host", default="127.0.0.1", help="TCP Host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=1977, help="TCP Port (default: 1977)")
    parser.add_argument("--com", default=None, help="COM port (e.g. COM1) instead of TCP")
    parser.add_argument("--font", default=None, help="Path to TTF/TTC font file (default: Galmuri / Gulim / NotoSerif)")
    parser.add_argument("--size", type=int, default=None, help="Font size (default: auto-detected from font native size)")
    parser.add_argument("--y-offset", type=int, default=None, help="Vertical offset adjustment in pixels (default: auto)")
    parser.add_argument("--box-center", action="store_true", default=None, help="Center glyph vertically in 16-row box (default: auto for 16px/11px/9px)")
    parser.add_argument("--force-vector", action="store_true", help="Force vector outline rasterization (ignore embedded bitmaps)")
    parser.add_argument("--color", default="white", help="Default Apple II HGR color: 0..7 or black, green, violet, white, orange, blue (default: white)")
    parser.add_argument("--color-font", default=None, help="Vector font(s) for coloured text, drawn 7 columns wide (default: Malgun Gothic, then system CJK fonts)")
    parser.add_argument("--mode", default="replace", help="Default drawing mode: replace, overlay, or xor (default: replace)")
    parser.add_argument("--popup", action="store_true", help="Use GUI popup window for Korean/Hanja input instead of console prompt")
    parser.add_argument("--pc-input", action="store_true", help="Ctrl+K opens the PC input (console or --popup) straight away, instead of 2-Bul-Sik typing on the Apple II keyboard")
    parser.add_argument("--ime-langs", default="ko,hira,kata,ru,el", help="Languages Ctrl+L cycles through on the Ctrl+K line, first is the default: ko (2-Bul-Sik), hira, kata (romaji to kana), ru (ЙЦУКЕН), el (Greek)")
    parser.add_argument("--audio-wav", default=None, help="Write a demo font cache as a cassette recording (WAV) for & \"/TAPE\" (see tools/audio_font_streamer.py)")
    parser.add_argument("--play-audio", action="store_true", help="Play that recording through the PC's sound output into the Apple II cassette input")
    args = parser.parse_args()

    if args.audio_wav or args.play_audio:
        from cassette_audio import stream_font_data_as_audio
        wav_file = args.audio_wav or "font_audio.wav"
        # Build font cache table using bundled/specified fonts
        from build_font_dsk import build_font_table
        rasterizer = HangulRasterizer(font_path=args.font, font_size=args.size, y_offset=args.y_offset, box_center=args.box_center, force_vector=args.force_vector)
        demo_chars = "안녕하세요애플투도스타자방이야기三國志英雄崛起붓글씨고전바탕조밀한작은폰트초소형모니터화면漢字萬國훈민정음"
        font_data = build_font_table(demo_chars, rasterizer)
        stream_font_data_as_audio(font_data, output_wav=wav_file, play=args.play_audio)
        sys.exit(0)

    server = HangulTerminalServer(
        host=args.host,
        port=args.port,
        com_port=args.com,
        font_path=args.font,
        font_size=args.size,
        y_offset=args.y_offset,
        box_center=args.box_center,
        force_vector=args.force_vector,
        use_popup=args.popup,
        color=args.color,
        draw_mode=args.mode,
        color_font=args.color_font,
        pc_input=args.pc_input,
        ime_langs=[l for l in (p.strip() for p in args.ime_langs.split(",")) if l in IME_LANGS] or ["ko"]
    )
    server.start()
