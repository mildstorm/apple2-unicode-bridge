#!/usr/bin/env python3
"""Input engines for the Ctrl+K line besides 2-Bul-Sik Hangul (which is
KoreanAutomata in unicode_server.py), and the Hanja dictionary.

Every engine has the same small interface:
    takes(ch)   -> True if the engine handles this key in its mode
    key(ch)     -> text committed by the key ("" while it is still composing)
    current()   -> text being composed, shown inverse ("" when none)
    backspace() -> None when nothing was being composed, else current()
    flush()     -> commits and returns what was being composed
"""
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Japanese kana from romaji (as the Windows Microsoft IME types it) ---

_KANA_ROWS = {
    '': 'あいうえお', 'k': 'かきくけこ', 's': 'さしすせそ', 't': 'たちつてと',
    'n': 'なにぬねの', 'h': 'はひふへほ', 'm': 'まみむめも', 'y': 'や い ゆ いぇ よ',
    'r': 'らりるれろ', 'w': 'わ うぃ う うぇ を', 'g': 'がぎぐげご', 'z': 'ざじずぜぞ',
    'd': 'だぢづでど', 'b': 'ばびぶべぼ', 'p': 'ぱぴぷぺぽ', 'x': 'ぁぃぅぇぉ',
    'l': 'ぁぃぅぇぉ', 'f': 'ふぁ ふぃ ふ ふぇ ふぉ', 'v': 'ゔぁ ゔぃ ゔ ゔぇ ゔぉ',
    'j': 'じゃ じ じゅ じぇ じょ', 'sh': 'しゃ し しゅ しぇ しょ', 'ch': 'ちゃ ち ちゅ ちぇ ちょ',
    'ts': 'つぁ つぃ つ つぇ つぉ', 'q': 'くぁ くぃ く くぇ くぉ',
    'ky': 'きゃ きぃ きゅ きぇ きょ', 'sy': 'しゃ しぃ しゅ しぇ しょ',
    'ty': 'ちゃ ちぃ ちゅ ちぇ ちょ', 'cy': 'ちゃ ちぃ ちゅ ちぇ ちょ',
    'ny': 'にゃ にぃ にゅ にぇ にょ', 'hy': 'ひゃ ひぃ ひゅ ひぇ ひょ',
    'my': 'みゃ みぃ みゅ みぇ みょ', 'ry': 'りゃ りぃ りゅ りぇ りょ',
    'gy': 'ぎゃ ぎぃ ぎゅ ぎぇ ぎょ', 'zy': 'じゃ じぃ じゅ じぇ じょ',
    'jy': 'じゃ じぃ じゅ じぇ じょ', 'dy': 'ぢゃ ぢぃ ぢゅ ぢぇ ぢょ',
    'by': 'びゃ びぃ びゅ びぇ びょ', 'py': 'ぴゃ ぴぃ ぴゅ ぴぇ ぴょ',
    'th': 'てゃ てぃ てゅ てぇ てょ', 'dh': 'でゃ でぃ でゅ でぇ でょ',
    'xy': 'ゃ ぃ ゅ ぇ ょ', 'ly': 'ゃ ぃ ゅ ぇ ょ',
}


def _build_romaji():
    table = {}
    for cons, kana in _KANA_ROWS.items():
        parts = kana.split() if ' ' in kana else list(kana)
        for vowel, k in zip('aiueo', parts):
            table[cons + vowel] = k
    table.update({
        'nn': 'ん', "n'": 'ん', 'xn': 'ん', 'xtu': 'っ', 'ltu': 'っ', 'xtsu': 'っ',
        'xwa': 'ゎ', 'lwa': 'ゎ', 'xka': 'ゕ', 'xke': 'ゖ',
        'shi': 'し', 'chi': 'ち', 'tsu': 'つ', 'fu': 'ふ', 'ji': 'じ',
        'wi': 'うぃ', 'we': 'うぇ', 'wo': 'を', 'yi': 'い', 'ye': 'いぇ', 'wu': 'う',
        '-': 'ー', ',': '、', '.': '。', '[': '「', ']': '」', '/': '・',
    })
    return table


ROMAJI = _build_romaji()
_ROMAJI_PREFIXES = {k[:i] for k in ROMAJI for i in range(1, len(k))}


def to_katakana(text):
    return ''.join(chr(ord(c) + 0x60) if 0x3041 <= ord(c) <= 0x3096 else c for c in text)


class KanaEngine:
    """Romaji -> hiragana (or katakana). The romaji typed so far is shown
    inverse until it makes a kana: ka -> か, kka -> っか, kya -> きゃ,
    nn / n' / n before a consonant -> ん."""

    def __init__(self, katakana=False):
        self.katakana = katakana
        self.buf = ''

    def takes(self, ch):
        return ch.isascii() and (ch.isalpha() or ch in "-,.[]/'")

    def _out(self, text):
        return to_katakana(text) if self.katakana else text

    def key(self, ch):
        if ch == "'" and self.buf != 'n':
            return self.flush() + "'"
        self.buf += ch.lower()
        out = ''
        while self.buf:
            b = self.buf
            if b in ROMAJI:
                out += ROMAJI[b]
                self.buf = ''
            elif b in _ROMAJI_PREFIXES:
                break
            elif len(b) >= 2 and ((b[0] == b[1] and b[0].isalpha() and b[0] not in 'aiueon')
                                  or b[:2] == 'tc'):
                out += 'っ'        # doubled consonant: kka -> っか, tcha -> っちゃ
                self.buf = b[1:]
            elif b[0] == 'n':
                out += 'ん'        # n before a consonant: kanji -> かんじ
                self.buf = b[1:]
            else:
                out += b[0]        # not romaji: kept as typed
                self.buf = b[1:]
        return self._out(out)

    def current(self):
        return self.buf

    def backspace(self):
        if not self.buf:
            return None
        self.buf = self.buf[:-1]
        return self.buf

    def flush(self):
        out = 'ん' if self.buf == 'n' else self.buf
        self.buf = ''
        return self._out(out)


# --- Keyboard layouts: Russian (ЙЦУКЕН) and Greek, as in Windows ---

class LayoutEngine:
    """A key maps to a letter; Greek has dead keys for accents (; then a
    vowel gives ά, : then ι gives ϊ), shown inverse while pending."""

    def __init__(self, keymap, dead=None):
        self.keymap = keymap
        self.dead = dead or {}      # dead key -> (standalone mark, {letter: accented})
        self.pending = ''

    def takes(self, ch):
        return ch in self.keymap or ch in self.dead

    def key(self, ch):
        if self.pending:
            mark, combos = self.dead[self.pending]
            self.pending = ''
            letter = self.keymap.get(ch, ch)
            if letter in combos:
                return combos[letter]
            if ch in self.dead:
                self.pending = ch
                return mark
            return mark + letter
        if ch in self.dead:
            self.pending = ch
            return ''
        return self.keymap.get(ch, ch)

    def current(self):
        return self.dead[self.pending][0] if self.pending else ''

    def backspace(self):
        if not self.pending:
            return None
        self.pending = ''
        return ''

    def flush(self):
        out = self.current()
        self.pending = ''
        return out


def _with_shift(lower, extra):
    keymap = dict(lower)
    keymap.update({k.upper(): v.upper() for k, v in lower.items() if k.isalpha()})
    keymap.update(extra)
    return keymap


RUSSIAN_KEYS = _with_shift(
    dict(zip("qwertyuiop[]asdfghjkl;'zxcvbnm,.`",
             "йцукенгшщзхъфывапролджэячсмитьбюё")),
    {'{': 'Х', '}': 'Ъ', ':': 'Ж', '"': 'Э', '<': 'Б', '>': 'Ю', '~': 'Ё',
     '/': '.', '?': ','})

GREEK_KEYS = _with_shift(
    dict(zip("ertyuiopasdfghjklzxcvbnm",
             "ερτυθιοπασδφγηξκλζχψωβνμ")),
    {'q': ';', 'Q': ':', 'w': 'ς', 'W': 'Σ'})

GREEK_DEAD = {
    ';': ('΄', {'α': 'ά', 'ε': 'έ', 'η': 'ή', 'ι': 'ί', 'ο': 'ό', 'υ': 'ύ', 'ω': 'ώ',
                'Α': 'Ά', 'Ε': 'Έ', 'Η': 'Ή', 'Ι': 'Ί', 'Ο': 'Ό', 'Υ': 'Ύ', 'Ω': 'Ώ'}),
    ':': ('¨', {'ι': 'ϊ', 'υ': 'ϋ', 'Ι': 'Ϊ', 'Υ': 'Ϋ'}),
}


def russian_engine():
    return LayoutEngine(RUSSIAN_KEYS)


def greek_engine():
    return LayoutEngine(GREEK_KEYS, GREEK_DEAD)


# --- Hanja dictionary (hanja_table.txt, built by tools/build_hanja_table.py) ---

_HANJA = None


def hanja_candidates(syllable):
    """Hanja read as this Hangul syllable, most common first ("" if none)."""
    global _HANJA
    if _HANJA is None:
        _HANJA = {}
        path = os.path.join(SCRIPT_DIR, "hanja_table.txt")
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if not line.startswith('#') and '\t' in line:
                        reading, cands = line.rstrip('\n').split('\t', 1)
                        _HANJA[reading] = cands
        except OSError:
            print(f"[Hanja] {path} not found: Hanja conversion is off")
    return _HANJA.get(syllable, "")
