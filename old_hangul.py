"""Old Hangul (훈민정음, 아래아 ...) as one 14x16 cell per syllable.

Old Hangul has no precomposed codepoints: a syllable is a run of conjoining
jamo (choseong U+1100/U+A960, jungseong U+1160/U+D7B0, jongseong U+11A8/
U+D7CB), sometimes a modern syllable followed by a jongseong, and maybe a
bangjeom (U+302E/U+302F). Drawn one codepoint at a time the jamo come out
spelled apart. As picoFreeRTOS does (mcufont/decoder/fonts/_compose_font.py),
each run is shaped with HarfBuzz using Noto Serif CJK's ljmo/vjmo/tjmo
features, which pick the jamo forms and positions, and the result is one
glyph.

split() replaces each such run with a private-use token (U+F0000 on), so code
that walks a string a character at a time keeps the syllable together;
render() draws a token's run into the bridge's 14x16 cell.
"""
import os

import freetype
import uharfbuzz as hb

CELL_W, CELL_H = 14, 16
TOKEN_BASE = 0xF0000


def is_l(c):
    return 0x1100 <= c <= 0x115F or 0xA960 <= c <= 0xA97F


def is_v(c):
    return 0x1160 <= c <= 0x11A7 or 0xD7B0 <= c <= 0xD7C6


def is_t(c):
    return 0x11A8 <= c <= 0x11FF or 0xD7CB <= c <= 0xD7FB


def is_syllable(c):
    return 0xAC00 <= c <= 0xD7A3


def is_tone(c):
    return c in (0x302E, 0x302F)


class Composer:
    def __init__(self, font_path, size=None, baseline=13):
        self.font_path = font_path
        self.baseline = baseline
        blob = hb.Blob.from_file_path(font_path)
        self.hb_face = hb.Face(blob)
        self.hb_font = hb.Font(self.hb_face)
        self.upem = self.hb_face.upem
        self.hb_font.scale = (self.upem, self.upem)
        self.ft = freetype.Face(font_path)
        self.size = size or CELL_W
        self.ft.set_pixel_sizes(0, self.size)
        self.runs = {}    # run -> token
        self.tokens = {}  # token -> run
        self.cache = {}

    # ---- text -------------------------------------------------------------

    def split(self, text):
        """text with each old Hangul syllable replaced by one token. In a
        string that has any, the modern syllables become tokens too, so the
        whole line is drawn in one typeface."""
        runs = self._runs(text)
        old = [self._hangul(run) and (len(run) > 1 or not is_syllable(ord(run[0]))) for run in runs]
        whole = any(old)
        out = []
        for run, is_old in zip(runs, old):
            if is_old or (whole and self._hangul(run)):
                out.append(self.token(run))
            else:
                out.append(run)
        return "".join(out)

    @staticmethod
    def _hangul(run):
        c = ord(run[0])
        return is_l(c) or is_v(c) or is_t(c) or is_syllable(c)

    def _runs(self, text):
        out = []
        i, n = 0, len(text)
        while i < n:
            c = ord(text[i])
            if not (is_l(c) or is_v(c) or is_t(c) or is_syllable(c)):
                out.append(text[i])
                i += 1
                continue
            j = i + 1
            prev = c
            while j < n:
                d = ord(text[j])
                if is_l(d) and is_l(prev):
                    pass
                elif is_v(d) and (is_l(prev) or is_v(prev)):
                    pass
                elif is_t(d) and (is_v(prev) or is_t(prev) or is_syllable(prev)):
                    pass
                elif is_tone(d):
                    pass
                else:
                    break
                prev = d
                j += 1
            out.append(text[i:j])
            i = j
        return out

    def token(self, run):
        tok = self.runs.get(run)
        if tok is None:
            tok = chr(TOKEN_BASE + len(self.runs))
            self.runs[run] = tok
            self.tokens[tok] = run
        return tok

    def owns(self, ch):
        return ch in self.tokens

    # ---- pixels ----------------------------------------------------------

    def _px(self, units):
        return int(round(units * self.size / self.upem))

    def grid(self, run):
        """The run's 14x16 bitmap as rows of 0/1."""
        buf = hb.Buffer()
        buf.add_str(run)
        buf.guess_segment_properties()
        buf.script = "Hang"  # as picoFreeRTOS: keeps syllable + bangjeom together
        buf.language = "ko"
        hb.shape(self.hb_font, buf, {"ljmo": True, "vjmo": True, "tjmo": True,
                                     "ccmp": True, "calt": True})
        ink = []  # (x, y) on a canvas with the baseline at y = 0
        pen = 0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            self.ft.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_MONOCHROME)
            g = self.ft.glyph
            bmp = g.bitmap
            ox = self._px(pen + pos.x_offset) + g.bitmap_left
            oy = -g.bitmap_top - self._px(pos.y_offset)
            for r in range(bmp.rows):
                for col in range(bmp.width):
                    if (bmp.buffer[r * bmp.pitch + (col >> 3)] >> (7 - (col & 7))) & 1:
                        ink.append((ox + col, oy + r))
            pen += pos.x_advance
        cell = [[0] * CELL_W for _ in range(CELL_H)]
        if not ink:
            return cell
        # The syllable is centred in the cell; a bangjeom that falls left of
        # the syllable's box still fits, as the box is narrower than 14.
        x0 = min(x for x, _ in ink)
        x1 = max(x for x, _ in ink)
        shift_x = (CELL_W - (x1 - x0 + 1)) // 2 - x0
        y0 = min(y for _, y in ink)
        y1 = max(y for _, y in ink)
        shift_y = self.baseline
        if y0 + shift_y < 0:
            shift_y = -y0
        if y1 + shift_y >= CELL_H:
            shift_y = CELL_H - 1 - y1
        for x, y in ink:
            x += shift_x
            y += shift_y
            if 0 <= x < CELL_W and 0 <= y < CELL_H:
                cell[y][x] = 1
        return cell

    def render(self, tok):
        """The bridge's 32-byte cell: two 7-dot bytes a row, bit 0 leftmost."""
        if tok in self.cache:
            return self.cache[tok]
        cell = self.grid(self.tokens[tok])
        out = bytearray(32)
        for r in range(CELL_H):
            for c in range(CELL_W):
                if cell[r][c]:
                    out[r * 2 + c // 7] |= 1 << (c % 7)
        self.cache[tok] = bytes(out)
        return self.cache[tok]


def default_font(bridge_dir):
    for p in (os.path.join(bridge_dir, "NotoSerifCJK16.ttf"),
              os.path.join(bridge_dir, "fonts", "NotoSerifCJK16.ttf")):
        if os.path.isfile(p):
            return p
    return None
