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

if getattr(sys, 'frozen', False):
    SCRIPT_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    EXE_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR = SCRIPT_DIR

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
    "NotoSerifCJK16.ttf"
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

# 2-Bul-Sik Korean Key Mapping
KEY_TO_CHO = {
    'r': 0, 'R': 1, 's': 2, 'e': 3, 'E': 4, 'f': 5, 'a': 6, 'q': 7,
    'Q': 8, 't': 9, 'T': 10, 'd': 11, 'w': 12, 'W': 13, 'c': 14,
    'z': 15, 'x': 16, 'v': 17, 'g': 18
}

KEY_TO_JUNG = {
    'k': 0, 'o': 1, 'i': 2, 'O': 3, 'j': 4, 'p': 5, 'u': 6, 'P': 7,
    'h': 8, 'y': 12, 'n': 13, 'b': 17, 'm': 18, 'l': 20
}

COMPOSITE_JUNG = {
    (8, 0): 9,   # ㅗ + ㅏ = ㅘ
    (8, 1): 10,  # ㅗ + ㅐ = ㅙ
    (8, 20): 11, # ㅗ + ㅣ = ㅚ
    (13, 4): 14, # ㅜ + ㅓ = ㅝ
    (13, 5): 15, # ㅜ + ㅔ = ㅞ
    (13, 20): 16,# ㅜ + ㅣ = ㅟ
    (18, 20): 19 # ㅡ + ㅣ = ㅢ
}

KEY_TO_JONG = {
    'r': 1, 'R': 2, 's': 4, 'e': 7, 'f': 8, 'a': 16, 'q': 17,
    't': 19, 'T': 20, 'd': 21, 'w': 22, 'c': 23, 'z': 24, 'x': 25,
    'v': 26, 'g': 27
}

COMPOSITE_JONG = {
    (1, 19): 3,   # ㄱ + ㅅ = ㄳ
    (4, 22): 5,   # ㄴ + ㅈ = ㄵ
    (4, 27): 6,   # ㄴ + ㅎ = ㄶ
    (8, 1): 9,    # ㄹ + ㄱ = ㄺ
    (8, 16): 10,  # ㄹ + ㅁ = ㄻ
    (8, 17): 11,  # ㄹ + ㅂ = ㄼ
    (8, 19): 12,  # ㄹ + ㅅ = ㄽ
    (8, 25): 13,  # ㄹ + ㅌ = ㄾ
    (8, 26): 14,  # ㄹ + ㅍ = ㄿ
    (8, 27): 15,  # ㄹ + ㅎ = ㅀ
    (17, 19): 18  # ㅂ + ㅅ = ㅄ
}

CHO_LIST = ['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ','ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']
JUNG_LIST = ['ㅏ','ㅐ','ㅑ','ㅒ','ㅓ','ㅔ','ㅕ','ㅖ','ㅗ','ㅘ','ㅙ','ㅚ','ㅛ','ㅜ','ㅝ','ㅞ','ㅟ','ㅠ','ㅡ','ㅢ','ㅣ']

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

def parse_font_segments(text):
    """
    Parses a string into segments of (font_identifier_or_None, text_segment).
    Recognizes tags like [F:neodgm], [FONT:1], \\F:myungjo\\, \\F2\\ etc.
    """
    segments = []
    last_idx = 0
    cur_font = None
    for m in FONT_TAG_PATTERN.finditer(text):
        seg = text[last_idx:m.start()]
        if seg:
            segments.append((cur_font, seg))
        cur_font = (m.group(1) or m.group(2)).strip()
        last_idx = m.end()
    seg = text[last_idx:]
    if seg:
        segments.append((cur_font, seg))
    return segments

_RASTERIZER_CACHE = {}

def get_font_rasterizer(font_identifier, fallback_rasterizer=None):
    """
    Resolves a font identifier (alias, index, filename, or path) to a HangulRasterizer.
    """
    if not font_identifier:
        return fallback_rasterizer

    key = str(font_identifier).strip().lower()
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
            raw_entries = [p.strip() for p in font_path.split(",") if p.strip()]
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
    """2-Bul-Sik Korean Input Automata"""
    def __init__(self):
        self.reset()

    def reset(self):
        self.step = 0 # 0: empty, 1: cho, 2: cho+jung, 3: cho+jung+jong
        self.cho = None
        self.jung = None
        self.jung_sub = None
        self.jong = None
        self.jong_sub = None

    def get_current_char(self):
        if self.step == 1:
            return CHO_LIST[self.cho]
        elif self.step == 2:
            return compose_syllable(self.cho, self.jung, 0)
        elif self.step == 3:
            return compose_syllable(self.cho, self.jung, self.jong)
        return ""

    def process_key(self, key):
        """
        Returns (committed_char, current_char)
        """
        committed = ""
        
        # Check if key is vowel
        if key in KEY_TO_JUNG:
            v = KEY_TO_JUNG[key]
            if self.step == 0:
                return (JUNG_LIST[v], "")
            elif self.step == 1:
                # cho + jung
                self.jung = v
                self.step = 2
                return ("", self.get_current_char())
            elif self.step == 2:
                # Check composite jung
                comb = (self.jung, v)
                if comb in COMPOSITE_JUNG:
                    self.jung_sub = v
                    self.jung = COMPOSITE_JUNG[comb]
                    return ("", self.get_current_char())
                else:
                    # Commit previous syllable, start new vowel
                    committed = self.get_current_char()
                    self.reset()
                    return (committed, JUNG_LIST[v])
            elif self.step == 3:
                # Syllable has jong consonant, but a vowel follows!
                # Move jong to next cho!
                if self.jong_sub is not None:
                    # Double jong: split
                    first_jong = None
                    for (j1, j2), val in COMPOSITE_JONG.items():
                        if val == self.jong:
                            first_jong = j1
                            break
                    prev_char = compose_syllable(self.cho, self.jung, first_jong)
                    next_cho = KEY_TO_CHO.get(self.jong_sub_key, 0)
                    self.reset()
                    self.cho = next_cho
                    self.jung = v
                    self.step = 2
                    return (prev_char, self.get_current_char())
                else:
                    # Single jong moves to next syllable cho
                    prev_char = compose_syllable(self.cho, self.jung, 0)
                    next_cho = KEY_TO_CHO.get(self.jong_key, 0)
                    self.reset()
                    self.cho = next_cho
                    self.jung = v
                    self.step = 2
                    return (prev_char, self.get_current_char())

        # Key is consonant
        elif key in KEY_TO_CHO or key in KEY_TO_JONG:
            c_cho = KEY_TO_CHO.get(key)
            c_jong = KEY_TO_JONG.get(key)

            if self.step == 0:
                if c_cho is not None:
                    self.cho = c_cho
                    self.step = 1
                    return ("", self.get_current_char())
            elif self.step == 1:
                # Check for double cho (ㄱ+ㄱ=ㄲ, ㄷ+ㄷ=ㄸ, ㅂ+ㅂ=ㅃ, ㅅ+ㅅ=ㅆ, ㅈ+ㅈ=ㅉ)
                DOUBLE_CHO = {0: 1, 3: 4, 7: 8, 9: 10, 12: 13}
                if c_cho == self.cho and self.cho in DOUBLE_CHO:
                    self.cho = DOUBLE_CHO[self.cho]
                    return ("", self.get_current_char())
                committed = self.get_current_char()
                self.reset()
                self.cho = c_cho
                self.step = 1
                return (committed, self.get_current_char())
            elif self.step == 2:
                # Add jong
                if c_jong is not None:
                    self.jong = c_jong
                    self.jong_key = key
                    self.step = 3
                    return ("", self.get_current_char())
                else:
                    committed = self.get_current_char()
                    self.reset()
                    self.cho = c_cho
                    self.step = 1
                    return (committed, self.get_current_char())
            elif self.step == 3:
                # Try composite jong
                comb = (self.jong, c_jong)
                if comb in COMPOSITE_JONG:
                    self.jong_sub = c_jong
                    self.jong_sub_key = key
                    self.jong = COMPOSITE_JONG[comb]
                    return ("", self.get_current_char())
                else:
                    committed = self.get_current_char()
                    self.reset()
                    self.cho = c_cho
                    self.step = 1
                    return (committed, self.get_current_char())
        
        # Other key
        committed = self.get_current_char()
        self.reset()
        return (committed + key, "")

    def backspace(self):
        """Handle backspace within composition"""
        if self.step == 3:
            if self.jong_sub is not None:
                # Revert composite jong
                for (j1, j2), val in COMPOSITE_JONG.items():
                    if val == self.jong:
                        self.jong = j1
                        self.jong_sub = None
                        break
            else:
                self.jong = None
                self.step = 2
            return self.get_current_char()
        elif self.step == 2:
            self.jung = None
            self.step = 1
            return self.get_current_char()
        elif self.step == 1:
            self.reset()
            return ""
        return None

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

class HangulTerminalServer:
    CMD_DRAW_14x16  = 0x81
    CMD_CLEAR       = 0x82
    CMD_EXIT        = 0x83
    CMD_SCROLL      = 0x84
    CMD_DRAW_7x16   = 0x85
    CMD_INPUT_BYTES = 0x86
    CMD_DONE        = 0x00

    CMD_DRAW_GLYPH  = 0x81

    MAX_COLS = 20
    MAX_ROWS = 12

    def __init__(self, host="127.0.0.1", port=1977, com_port=None, font_path=None, font_size=None, y_offset=None, box_center=None, force_vector=False, use_popup=False):
        self.host = host
        self.port = port
        self.com_port = com_port
        self.sock = None
        self.serial_io = None
        self.running = False
        self.use_popup = use_popup
        
        self.rasterizer = HangulRasterizer(font_path=font_path, font_size=font_size, y_offset=y_offset, box_center=box_center, force_vector=force_vector)
        self.default_rasterizer = self.rasterizer
        self.current_rasterizer = self.rasterizer
        self.automata = KoreanAutomata()
        
        self.cur_col = 0
        self.cur_row = 0
        self.hangul_mode = True # Default Korean 2-bul-sik mode
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

    def draw_glyph_at(self, col, row, glyph_bytes):
        packet = bytearray([self.CMD_DRAW_GLYPH, col, row]) + glyph_bytes
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
        self.draw_glyph_at(self.cur_col, self.cur_row, glyph)
        self.advance_cursor()

    def put_string(self, text):
        for ch in text:
            self.put_char(ch)

    def handle_apple2_key(self, b):
        ch = chr(b)
        
        # ESC -> Exit
        if b == 0x1B:
            print("\n[Term] Exit requested by Apple II.")
            self.running = False
            self.send_raw(bytes([self.CMD_EXIT]))
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

        # In Apple II, Caps Lock is ON by default, sending uppercase letters.
        # Normalize uppercase to lowercase unless Shift is held.
        norm_ch = ch
        if 'A' <= ch <= 'Z':
            try:
                import ctypes
                is_shift = (ctypes.windll.user32.GetAsyncKeyState(0x10) & 0x8000) != 0
            except Exception:
                is_shift = False
            if is_shift and ch in 'QWERTOP':
                norm_ch = ch
            else:
                norm_ch = ch.lower()

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

    def listen_apple2(self):
        """Thread that reads bytes from Apple II"""
        while self.running:
            try:
                b = self.recv_byte()
                if b is None:
                    time.sleep(0.01)
                    continue
                if b == 0xAA:
                    self.mode = "TERMINAL"
                    print("\n[Term] Terminal Client Handshake received from Apple II (READY!)")
                    self.clear_screen()
                    self.put_string("한글 시스템 준비완료\n")
                    self.put_string("Apple II + Gulim 14\n")
                    self.put_string("--------------------\n")
                    self.put_string("안녕하세요 漢字\n")
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
                        self.send_raw(bytes([0x00]))
                        continue

                    # Dedicated command: & "/font <name>" or & "/f <name>"
                    stripped_cmd = text.strip()
                    if stripped_cmd.lower().startswith(("/font ", "/f ")):
                        parts = stripped_cmd.split(maxsplit=1)
                        if len(parts) > 1:
                            target_f = parts[1].strip()
                            new_r = get_font_rasterizer(target_f, self.default_rasterizer)
                            if new_r:
                                self.current_rasterizer = new_r
                                print(f"[System] Active font switched to: {target_f}")
                        self.send_raw(bytes([0x00]))
                        continue

                    if self.cur_col == 0 and self.cur_row == 0:
                        self.clear_screen()

                    segments = parse_font_segments(text)
                    for font_tag, seg_text in segments:
                        active_r = get_font_rasterizer(font_tag, self.current_rasterizer) if font_tag else self.current_rasterizer
                        for ch in seg_text:
                            if ch == '\n' or ch == '\r':
                                self.newline()
                                continue
                            glyph = active_r.rasterize(ch)
                            self.draw_glyph_at(self.cur_col, self.cur_row, glyph)
                            self.advance_cursor()
                    self.newline()
                    self.send_raw(bytes([0x00])) # Send CMD_DONE
                    continue

                if b == 0x0B:
                    # Ctrl+K requested by Apple II
                    print("\n" + "=" * 50)
                    print("[Apple II -> PC] Ctrl+K 특수키 감지!")
                    if self.use_popup:
                        print("한글 / 漢字 입력 팝업창을 엽니다...")
                        line = prompt_korean_dialog()
                    else:
                        print("이 콘솔창에 한글 또는 한자를 직접 입력(붙여넣기)한 후 Enter를 누르세요:")
                        print("(입력을 취소하려면 내용 없이 Enter만 누르세요)")
                        try:
                            line = input("한글/漢字 입력 > ")
                        except (EOFError, KeyboardInterrupt):
                            line = ""

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
        if self.use_popup:
            print("  * AppleWin에서 BASIC 작성 중 Ctrl+K 를 누르면")
            print("    화면에 한글 입력 팝업창이 바로 뜹니다.")
        else:
            print("  * AppleWin에서 BASIC 작성 중 Ctrl+K 를 누르면")
            print("    이 콘솔창에서 바로 한글/한자를 직접 입력(붙여넣기)할 수 있습니다.")
        print("  * 입력 후 Enter를 치면 Apple II로 전달됩니다.")
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
    parser.add_argument("--popup", action="store_true", help="Use GUI popup window for Korean/Hanja input instead of console prompt")
    args = parser.parse_args()

    server = HangulTerminalServer(
        host=args.host,
        port=args.port,
        com_port=args.com,
        font_path=args.font,
        font_size=args.size,
        y_offset=args.y_offset,
        box_center=args.box_center,
        force_vector=args.force_vector,
        use_popup=args.popup
    )
    server.start()
