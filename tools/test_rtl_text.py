#!/usr/bin/env python3
"""Checks rtl_text: Arabic contextual forms and right-to-left display order.

    python tools/test_rtl_text.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rtl_text import reorder, shape_arabic, shape_for_display  # noqa: E402

CASES = [
    # (function, input, expected)
    # salaam: seen initial, lam-alef final ligature, meem isolated
    (shape_arabic, "سلام", "ﺳﻼﻡ"),
    (shape_for_display, "سلام", "ﻡﻼﺳ"),
    # beh alone / two behs / three behs: isolated, initial+final, initial+medial+final
    (shape_arabic, "ب", "ﺏ"),
    (shape_arabic, "بب", "ﺑﺐ"),
    (shape_arabic, "ببب", "ﺑﺒﺐ"),
    # alef does not join the letter after it: beh alef beh
    (shape_arabic, "باب", "ﺑﺎﺏ"),
    # Hebrew is only reversed; Latin around it stays
    (shape_for_display, "abc שלום def", "abc םולש def"),
    # Two right-to-left words with the space between them, as one run
    (reorder, "אב גד", "דג בא"),
    # A number inside a right-to-left run stays left to right
    (reorder, "אב 123 גד", "דג 123 בא"),
    # Nothing right to left: unchanged
    (shape_for_display, "한글 abc 😀", "한글 abc 😀"),
]


def main():
    failed = 0
    for fn, text, want in CASES:
        got = fn(text)
        ok = got == want
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {fn.__name__}({text!r}) -> {got!r}"
              + ("" if ok else f" (want {want!r})"))
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
