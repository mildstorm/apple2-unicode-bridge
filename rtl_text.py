#!/usr/bin/env python3
"""Arabic and Hebrew for the Apple II screen, which draws a character to a
14x16 cell from left to right.

shape_for_display(text) returns the text as it is to be drawn:
  - each Arabic letter in its contextual form (isolated, initial, medial or
    final) from the Arabic Presentation Forms, lam-alef as one ligature, so a
    font that has those forms shows the joined shapes;
  - runs of right-to-left text (Arabic, Hebrew) reversed into display order,
    with the numbers inside them kept left to right.

The forms come from Unicode's own data (the <isolated>, <initial>,
<medial> and <final> decompositions of the presentation forms), so there is
no table to keep. This is the simple form of the Unicode bidirectional
algorithm: a line is left to right, and each run of right-to-left words is
turned around. The text stored in the BASIC program keeps its logical order.
"""
import unicodedata

_FORMS = {}       # base letter -> {"isolated": cp, "initial": ..., ...}
_LIGATURES = {}   # (first, second) -> {"isolated": cp, "final": cp}


def _load():
    for cp in list(range(0xFB50, 0xFE00)) + list(range(0xFE70, 0xFF00)):
        d = unicodedata.decomposition(chr(cp))
        if not d.startswith("<"):
            continue
        tag, _, rest = d.partition(" ")
        tag = tag.strip("<>")
        if tag not in ("isolated", "initial", "medial", "final"):
            continue
        parts = [int(p, 16) for p in rest.split()]
        if len(parts) == 1:
            _FORMS.setdefault(parts[0], {}).setdefault(tag, cp)
        elif len(parts) == 2 and parts[0] == 0x0644:     # lam-alef
            _LIGATURES.setdefault((parts[0], parts[1]), {}).setdefault(tag, cp)


_load()


def _transparent(ch):
    return unicodedata.category(ch) in ("Mn", "Me", "Cf")


def _joins_back(ch):
    """The letter takes a joint from the letter before it (has a final form)."""
    f = _FORMS.get(ord(ch), {})
    return "final" in f or "medial" in f


def _joins_forward(ch):
    """The letter gives a joint to the letter after it (dual-joining)."""
    f = _FORMS.get(ord(ch), {})
    return "initial" in f or "medial" in f


def shape_arabic(text):
    """Contextual forms of the Arabic letters in text (logical order)."""
    chars = list(text)
    out = []
    i = 0

    def neighbour(j, step):
        while 0 <= j < len(chars) and _transparent(chars[j]):
            j += step
        return chars[j] if 0 <= j < len(chars) else None

    while i < len(chars):
        ch = chars[i]
        cp = ord(ch)
        if cp not in _FORMS:
            out.append(ch)
            i += 1
            continue
        prev = neighbour(i - 1, -1)
        joined_before = prev is not None and _joins_forward(prev) and _joins_back(ch)
        nxt_i = i + 1
        while nxt_i < len(chars) and _transparent(chars[nxt_i]):
            nxt_i += 1
        nxt = chars[nxt_i] if nxt_i < len(chars) else None
        # Lam followed by alef: one ligature, joined to what comes before
        if cp == 0x0644 and nxt is not None and (cp, ord(nxt)) in _LIGATURES:
            lig = _LIGATURES[(cp, ord(nxt))]
            form = "final" if joined_before and "final" in lig else "isolated"
            out.append(chr(lig.get(form, lig.get("isolated"))))
            out.extend(chars[i + 1:nxt_i])          # marks between them
            i = nxt_i + 1
            continue
        joined_after = nxt is not None and _joins_forward(ch) and _joins_back(nxt)
        form = ("medial" if joined_before and joined_after else
                "final" if joined_before else
                "initial" if joined_after else "isolated")
        forms = _FORMS[cp]
        out.append(chr(forms.get(form) or forms.get("isolated") or cp))
        i += 1
    return "".join(out)


def _direction(ch):
    bidi = unicodedata.bidirectional(ch)
    if bidi in ("R", "AL"):
        return "R"
    if bidi == "L":
        return "L"
    return "N"     # numbers, spaces, punctuation


def reorder(text):
    """Each run of right-to-left text (with the spaces and numbers between
    its words) reversed, numbers inside it kept left to right."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        if _direction(text[i]) != "R":
            out.append(text[i])
            i += 1
            continue
        # The run goes on through neutrals while more right-to-left follows
        j = i
        last_r = i
        while j < n and _direction(text[j]) != "L":
            if _direction(text[j]) == "R":
                last_r = j
            j += 1
        run = text[i:last_r + 1]
        # Reverse, then put each number back in its own order
        rev = run[::-1]
        fixed = []
        k = 0
        while k < len(rev):
            if unicodedata.bidirectional(rev[k]) in ("EN", "AN"):
                m = k
                while m < len(rev) and unicodedata.bidirectional(rev[m]) in ("EN", "AN", "CS"):
                    m += 1
                fixed.append(rev[k:m][::-1])
                k = m
            else:
                fixed.append(rev[k])
                k += 1
        out.append("".join(fixed))
        i = last_r + 1
    return "".join(out)


def has_rtl(text):
    return any(_direction(c) == "R" for c in text)


def shape_for_display(text):
    """The text in display order with Arabic contextual forms."""
    if not has_rtl(text):
        return text
    return reorder(shape_arabic(text))
