#!/usr/bin/env python3
"""Checks the 2-Bul-Sik automaton against what the Windows Korean IME types.

Run from the repository root:  python tools/test_dubeol_ime.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unicode_server import KoreanAutomata  # noqa: E402

BACKSPACE = '\b'


def type_keys(keys):
    """Types keys ('\\b' is Backspace); returns committed text + composing char."""
    ime = KoreanAutomata()
    text = []
    for k in keys:
        if k == BACKSPACE:
            if ime.backspace() is None and text:
                text.pop()
            continue
        committed, _ = ime.process_key(k)
        text.extend(committed)
    return ''.join(text) + ime.get_current_char()


CASES = [
    ("rkskek", "가나다"),
    ("dkssudgktpdy", "안녕하세요"),
    ("qnfrhrl", "불고기"),
    ("ekfrk", "달가"),          # final ㄺ splits before a vowel
    ("rkqtdl", "값이"),
    ("dlTek", "있다"),          # Shift+T is ㅆ, also as a final
    ("Ekfrl", "딸기"),
    ("dkEk", "아따"),           # ㄸ never ends a syllable
    ("Rk", "까"),
    ("rr", "ㄱㄱ"),             # repeating a key does not make ㄲ
    ("hk", "ㅘ"),               # vowels alone still combine
    ("rhk", "과"),
    ("dhksk", "와나"),
    ("rt", "ㄳ"),               # consonants alone combine as in Windows
    ("rtk", "ㄱ사"),
    ("dho", "왜"),
    ("dmlwk", "의자"),
    ("Dkssud", "안녕"),         # Shift on a key with no tense form is ignored
    ("dkO", "아ㅒ"),
    ("rkO", "가ㅒ"),
    ("rhk\b", "고"),            # Backspace takes back one jamo
    ("ekfr\b", "달"),
    ("ekfr\b\b", "다"),
    ("ekfr\b\b\b", "ㄷ"),
    ("ekfr\b\b\b\b", ""),
    ("rk rk\b\b", "가 "),      # then deletes committed text
    ("rk1", "가1"),
]


def main():
    failed = 0
    for keys, want in CASES:
        got = type_keys(keys)
        ok = got == want
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {keys!r:18} -> {got!r} (want {want!r})")
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
