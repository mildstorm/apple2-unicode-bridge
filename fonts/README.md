# Apple II Retro & Unicode Fonts Collection

This directory contains curated retro pixel/bitmap and vector fonts suitable for the Apple II 14x16 High-Resolution (HGR) display.

All fonts bundled in this directory are 100% free and open-source (SIL Open Font License 1.1 or MIT License).

---

## Font Catalog & Specifications

| Font File | Type | Target Grid | Characteristics & Best Usage | License | Author / Source |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`Galmuri14.ttf`** | Pixel TTF | 14×14 | **Recommended default for Apple II HGR.** Crisp Korean glyphs with ideal 1-line top & bottom margins in 14×16 cells (`--y-offset 1`). | SIL OFL 1.1 | [quiple/galmuri](https://github.com/quiple/galmuri) |
| **`Galmuri11.ttf`** | Pixel TTF | 11×11 | Compact pixel font, ideal for dense layouts or 80-column style Apple II displays. | SIL OFL 1.1 | [quiple/galmuri](https://github.com/quiple/galmuri) |
| **`Galmuri9.ttf`** | Pixel TTF | 9×9 | Ultra-compact micro pixel font for status bars and HUDs. | SIL OFL 1.1 | [quiple/galmuri](https://github.com/quiple/galmuri) |
| **`neodgm.ttf`** | Pixel TTF | 16×16 | **Neo둥근모.** The legendary 1990s Korean MS-DOS aesthetic (Hanme Taja, Iyagi). Full 16-row height with thick, bold retro strokes. | SIL OFL 1.1 | [neodgm/neodgm](https://github.com/neodgm/neodgm) |
| **`Sam3KRFont.ttf`** | Pixel TTF | 16×16 | **삼국지3 한글 글꼴.** Faithful reproduction of the classic Koei Romance of the Three Kingdoms III Hangul bitmap font. | MIT License | Damheo Lee ([hurss/fonts](https://github.com/hurss/fonts)) |
| **`DOSGothic.ttf`** | Pixel TTF | 16×16 | **도스고딕.** Classic Korean MS-DOS Gothic monospace pixel font. | MIT License | Damheo Lee ([hurss/fonts](https://github.com/hurss/fonts)) |
| **`DOSMyungjo.ttf`** | Pixel TTF | 16×16 | **도스명조.** Classic Korean MS-DOS serif (myeongjo) pixel font. | MIT License | Damheo Lee ([hurss/fonts](https://github.com/hurss/fonts)) |
| **`NotoSerifCJK16.ttf`** | Vector TTF | Scalable | Full CJK Unicode vector font covering Hangul, Hanja, Japanese Kana, Cyrillic, Greek, and Latin diacritics. | SIL OFL 1.1 | Google / Adobe (Noto Project) |

---

## Operating System Fonts (Not bundled, auto-discovered)

* **Windows 굴림/돋움 (`gulim.ttc` / `dotum.ttc`)**:
  * Located at `C:\Windows\Fonts\gulim.ttc`.
  * Contains hand-crafted 14×14 embedded 1-bit monochrome bitmaps for Hangul (2,350 syllables) and Hanja (4,888 ideographs).
  * Automatically prioritized when running on Windows.

---

## License Details

* **SIL Open Font License 1.1 (OFL)**:
  * Applies to: `Galmuri14.ttf`, `Galmuri11.ttf`, `Galmuri9.ttf`, `neodgm.ttf`, `NotoSerifCJK16.ttf`
  * Rights: Free for personal and commercial use, modification, bundling, and distribution.
* **MIT License**:
  * Applies to: `Sam3KRFont.ttf`, `DOSGothic.ttf`, `DOSMyungjo.ttf` (Damheo Lee / leedheo@gmail.com)
  * Rights: Free for personal and commercial use, modification, and redistribution with copyright notice preserved.
