#!/usr/bin/env python3
"""Checks the Ctrl+K line's kana, Russian and Greek engines, Hanja
conversion and mode keys, with a stand-in for the server.

Run from the repository root:  python tools/test_ime_engines.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import apple_ime  # noqa: E402
import unicode_server as us  # noqa: E402


def run_engine(engine, keys):
    out = []
    for k in keys:
        if k == '\b':
            if engine.backspace() is None and out:
                out.pop()
        else:
            out.extend(engine.key(k))
    return ''.join(out) + engine.current()


class FakeServer:
    """What AppleIme needs from HangulTerminalServer; records what it sends."""
    CMD_SET_MODE = 0x88
    CMD_DRAW_GLYPH = 0x81
    CMD_INPUT_BYTES = 0x86

    def __init__(self):
        self.out = bytearray()
        self._last_sent_mode = 0
        self.ime_langs = ["ko", "hira", "kata", "ru", "el"]
        self.ime_lang = 0
        self.ime_latin = False
        self.rasterizer = type("R", (), {"rasterize": staticmethod(lambda ch: bytes(32))})()

    def send_raw(self, data):
        self.out += data

    def hangul_key_case(self, ch):
        return ch

    def ask_pc_text(self):
        return ""


CTRL = {'K': 0x0B, 'L': 0x0C, 'J': 0x0A, 'P': 0x10}


def run_line(keys):
    """Types keys on a Ctrl+K line ({K} {L} {J} for Ctrl keys, \\b, \\x1b);
    returns the text it ends with on Return."""
    srv = FakeServer()
    ime = us.AppleIme(srv)
    i = 0
    while i < len(keys):
        if keys[i] == '{':
            b = CTRL[keys[i + 1]]
            i += 3
        else:
            b = ord(keys[i])
            i += 1
        assert not ime.key(b), f"line ended early at {keys[:i]!r}"
    srv.out.clear()
    assert ime.key(0x0D)
    return us.decode_apple2_multilingual(bytes(srv.out[2:]))


ENGINE_CASES = [
    ("hira", apple_ime.KanaEngine, "konnnichiha", "こんにちは"),
    ("hira", apple_ime.KanaEngine, "kanji", "かんじ"),
    ("hira", apple_ime.KanaEngine, "kitte", "きって"),
    ("hira", apple_ime.KanaEngine, "matcha", "まっちゃ"),
    ("hira", apple_ime.KanaEngine, "kyouto", "きょうと"),
    ("hira", apple_ime.KanaEngine, "shinbun", "しんぶn"),   # last n waits
    ("hira", apple_ime.KanaEngine, "tokyo-.", "ときょー。"),
    ("hira", apple_ime.KanaEngine, "ky\b\ba", "あ"),
    ("kata", lambda: apple_ime.KanaEngine(katakana=True), "ko-hi-", "コーヒー"),
    ("kata", lambda: apple_ime.KanaEngine(katakana=True), "viorin", "ヴィオリn"),
    ("ru", apple_ime.russian_engine, "Ghbdtn", "Привет"),
    ("ru", apple_ime.russian_engine, "vbh/", "мир."),
    ("ru", apple_ime.russian_engine, "`krf", "ёлка"),
    ("el", apple_ime.greek_engine, "Kalhm;era", "Καλημέρα"),
    ("el", apple_ime.greek_engine, "kosmow", "κοσμος"),
    ("el", apple_ime.greek_engine, ";", "΄"),
    ("el", apple_ime.greek_engine, ":i", "ϊ"),
]

LINE_CASES = [
    ("rkd", "강"),
    ("gks{J}1", "限"),                  # composing 한 -> first candidate
    ("gks{J} 2", None),                 # page 2, second candidate (checked below)
    ("gksrnr{J}1", "한國"),            # syllable before the cursor
    ("gks{J}\x1b", "한"),               # Esc closes the list only
    ("gks{J}k", "하나"),                # another key closes it and goes on
    ("gks{K}a1", "한a1"),               # Ctrl+K: A mode
    ("{L}sushi", "すし"),
    ("{L}{L}sushi", "スシ"),
    ("{L}{L}{L}Ghbdtn", "Привет"),
    ("{L}{L}{L}{L}Kalhm;era", "Καλημέρα"),
    ("{L}{L}{L}{L}{L}rk", "가"),        # the cycle comes back to 한
    ("{L}kan{L}{L}{L}{L}rk", "かん가"),  # switching commits the pending n
    ("dkssud{J}{J}3", "안" + apple_ime.hanja_candidates("녕")[2]),  # one page: {J} wraps
    ("Eha{J}", "똠"),                  # no Hanja read 똠: the key does nothing
]


def main():
    failed = 0
    for lang, factory, keys, want in ENGINE_CASES:
        got = run_engine(factory(), keys)
        ok = got == want
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {lang:4} {keys!r:16} -> {got!r} (want {want!r})")

    page2 = apple_ime.hanja_candidates("한")[9 + 1]
    for keys, want in LINE_CASES:
        want = page2 if want is None else want
        got = run_line(keys)
        ok = got == want
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} line {keys!r:28} -> {got!r} (want {want!r})")

    total = len(ENGINE_CASES) + len(LINE_CASES)
    print(f"\n{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
