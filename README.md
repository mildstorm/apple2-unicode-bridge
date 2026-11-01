# Apple II Unicode Bridge (`apple2-unicode-bridge`)

[![Platform](https://img.shields.io/badge/Platform-Apple%20II%20%7C%20AppleWin-blue.svg)](https://github.com/mildstorm/apple2-unicode-bridge)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Encoding](https://img.shields.io/badge/Encoding-UTF--8%20%2F%20Unicode-orange.svg)](#)
[![Display](https://img.shields.io/badge/Display-HGR%20280x192-purple.svg)](#)

> **Universal TrueType / Unicode Multilingual Font Bridge & I/O Engine for Apple II**  
> Stream high-resolution global typography (Hangul, Hanja, Kanji, Chinese, Cyrillic, Greek, Latin diacritics, and symbols) to Apple II High-Resolution Graphics (HGR 280×192) via Super Serial Card (SSC) without any ROM or hardware modifications.

[English](README.md) | [한국어 문서](README_HANGUL.md)

---

## 🌟 Overview

The original Apple II hardware is constrained by its 1970s character generator ROM, which only natively displays standard 7-bit US-ASCII uppercase/lowercase glyphs on a 40-column text screen. Supporting non-Latin writing systems historically required dedicated regional clone hardware (e.g., Korean TriGem/Sekyoung, Japanese J-Plus, Cyrillic Pravets-8D) or expensive custom character-generator expansion cards.

**`apple2-unicode-bridge`** solves this fundamentally by transforming the Apple II into a **universal multilingual platform** through modern PC font co-processing:

1. **Zero Hardware/ROM Modifications**: Uses the standard **Super Serial Card (SSC)** in Slot 2 (TCP socket for emulators, RS-232/USB-serial for real hardware).
2. **Global Unicode Coverage**: Dynamically rasterizes any Unicode script—Korean Hangul (all 11,172 syllables), CJK Hanja/Kanji/Chinese characters, Cyrillic, Greek, Arabic, accented Latin, and custom symbols—using TrueType / OpenType fonts via FreeType.
3. **Applesoft BASIC `&` (Ampersand) Integration**: Easily embed and execute multilingual strings directly in standard Applesoft BASIC programs using syntax like `10 & "\KHello World / 한글 / 漢字 / Привет / こんにちは\N"`.
4. **Hex-Safe Encoding Pipeline**: Prevents BASIC token collisions ($80–$EA) and `?SYNTAX ERROR` issues caused by Apple II 8-bit parsing conventions and Caps Lock states.
5. **Interactive Full-Screen Terminal**: Provides a real-time 280×192 graphic console with interactive keyboard input, IME support, and automatic word wrapping.

---

## 🏗️ Architecture

```
+-------------------------------------------------------------+
|                       PC / Host System                      |
|                                                             |
|   +----------------------+       +----------------------+   |
|   |  FreeType / Pillow   | ----> |  unicode_server.py   |   |
|   |  TrueType Font (TTF) |       |  (TCP / COM Port)    |   |
|   +----------------------+       +----------------------+   |
+----------------------------------------------|--------------+
                                               |  Serial / TCP (Slot 2 SSC)
                                               v  9600-115200 Baud
+-------------------------------------------------------------+
|               Apple II (AppleWin or Real Hardware)          |
|                                                             |
|   +-------------------+         +-----------------------+   |
|   | 6551 ACIA (Slot 2)| ------> | UNICODE.BIN Driver    |   |
|   +-------------------+         | (Resident at $4000)   |   |
|                                 +-----------------------+   |
|                                             |               |
|                                             v               |
|                           +-------------------------------+ |
|                           | HGR Page 1 ($2000-$3FFF)      | |
|                           | 280 x 192 Multilingual Screen | |
|                           +-------------------------------+ |
+-------------------------------------------------------------+
```

### Font Metrics & Layout on HGR Screen
- **Full-width characters (CJK, etc.)**: 14×16 pixels (20 columns × 12 rows).
- **Half-width characters (ASCII, Latin, etc.)**: 7×16 pixels (40 columns × 12 rows).
- Pixel-perfect rasterization ensures clean readability on composite color and monochrome monitors alike without artifact distortion.

---

## 📺 Live Demonstration: 祭亡妹歌 (Je-mang-mae-ga) with Mixed Hanja & Hangul

Below is an authentic Apple II High-Resolution (HGR 280×192) display of the famous 8th-century Korean Hyangga poem *Je-mang-mae-ga* (Master Wolmyeong), demonstrating **mixed Classical Chinese Hanja (漢字) and Korean Hangul (한글)** rendered dynamically without modifying any Apple II ROM:

![Apple II Unicode Bridge: Je-mang-mae-ga Demo](docs/images/jemangmaega_demo.png)

### The Applesoft BASIC Program

You can write this directly in Applesoft BASIC using standard line numbers and the `&` ampersand extension:

```basic
10 REM ====================================================
20 REM  祭亡妹歌 (제망매가) - 月明師 (월명사)
30 REM  Multilingual Hanja & Hangul Demo on Apple II HGR
40 REM ====================================================
50 & "\K[ 祭亡妹歌 (제망매가) ]\N"
60 & "\K  - 月明師 (월명사) -\N"
70 & "\K生死路隱 此矣有阿米\N"
80 & "\K생사 길은 이에 있으매\N"
90 & "\K吾隱去內如辭叱都\N"
100 & "\K나는 간다는 말도\N"
110 & "\K毛如云遣去奴隱尼\N"
120 & "\K못 다 이르고 갔는가\N"
130 & "\K於內秋察早隱風未\N"
140 & "\K어느 가을 이른 바람에\N"
150 & "\K阿也 彌陀刹良逢乎吾\N"
160 & "\K아아 彌陀刹에서 만날나\N"
```

### How to Input Hanja & Multilingual Text in AppleWin:
1. Type `50 & "` in AppleWin.
2. Press **`Ctrl+K`**.
3. A host input window appears on your PC. Type or paste `[ 祭亡妹歌 (제망매가) ]` and press `Enter`.
4. The bridge automatically injects the hex-safe stream `\K[ 祭亡妹歌 (제망매가) ]\N` into the BASIC prompt.
5. Close the quotes with `"` and press `Enter`.
6. Type `RUN` — the Apple II immediately switches to HGR High-Resolution graphics and draws the rendered typography!

---

## 🚀 Key Features

### 1. Applesoft BASIC Extension (`&`)
You can print multilingual Unicode text right from Applesoft BASIC:

```basic
10 & "\KWelcome to Apple II Unicode Bridge!\N"
20 & "\K한글과 漢字 및 다국어 폰트 출력\N"
30 & "\KHello, こんにちは, Привет, Bonjour!\N"
```
When executed (`RUN`), the driver switches to HGR graphics mode and renders high-density typographic glyphs with accurate letter spacing and vertical alignment.

### 2. Interactive `Ctrl+K` Input Bridge
Writing non-ASCII scripts on an Apple II keyboard is challenging. With this bridge:
- While typing a BASIC program in AppleWin or terminal, press **`Ctrl+K`**.
- The PC server opens an instant input prompt / popup window.
- Type or paste your desired Unicode text (in your OS's native IME) and hit `Enter`.
- The text is hex-encoded and injected into the Apple II input buffer automatically.

### 3. Hex-Safe Stream Protocol (`\K ... \N`)
Standard Apple II line input (`GETLN`) and Applesoft keyword parsing (`PARSE`) treat byte values `$80`–`$FF` as internal BASIC tokens or control codes. Raw UTF-8 byte streams cause immediate syntax errors.
- **`apple2-unicode-bridge`** encapsulates Unicode streams inside a robust hex/escape framing protocol (`\K<HEX>\N`).
- It remains completely unaffected by the Apple II `Caps Lock` state, quote delimiters, or carriage return filters.

### 4. Interactive Terminal Mode
Entering `&` at the Applesoft prompt `]` drops directly into a full-screen interactive graphics terminal:
- Supports 2-Bul-Sik Korean IME, Latin characters, and hotkeys.
- Instant toggle between localized input and English with `Ctrl+K` or `` ` `` (backtick).
- `ESC` returns safely back to Applesoft BASIC.

### 5. Standalone Execution via Font Subsetting (No PC Server Required!)
While the live font server streams unlimited Unicode glyphs dynamically, you can also bake the exact subset of fonts used by your BASIC programs directly into the `.dsk` disk image:
- **Zero PC dependency**: Once baked, the Apple II boots and runs multilingual graphics programs entirely standalone from floppy disk.
- **Microscopic footprint**: Extracting all 77 unique Hanja and Hangul characters for the *Je-mang-mae-ga* and `DEMO` suites consumes **only 2.7 KB** of disk space (as binary `FONT` loaded at `$6000`).
- **One-click baking tool**: Run `python build_font_dsk.py --dsk unicode.dsk` to scan all BASIC programs, rasterize their characters, inject the `FONT` binary, and patch `HELLO` automatically.

---

## 📦 Repository Structure

| File | Description |
| :--- | :--- |
| **`unicode_server.py`** | Universal Unicode font co-processor & streaming serial/TCP server (Python 3). |
| **`unicode_server.exe`** | Standalone pre-compiled Windows executable (bundled with default CJK font). |
| **`ac_tool.py`** | AppleCommander management wrapper & standalone DSK inspection CLI. |
| **`build_font_dsk.py`** | Automated font subsetter: extracts used glyphs, bakes `FONT` binary ($6000) into DSK for standalone execution. |
| **`inject_basic.py`** | PC-to-Apple II BASIC injector tool with automatic font synchronization. |
| **`verify_dsk_font.py`** | Verification utility confirming glyph rendering directly from DSK `FONT` binary. |
| **`unicode_driver.s`** | 6502 assembly source code for the Apple II resident driver ($4000). |
| **`unicode.dsk`** | Ready-to-boot DOS 3.3 disk image containing `UNICODE.BIN`, standalone `FONT`, and demo programs. |
| **`UNICODE.BIN`** | Assembled 6502 binary driver ($4000). |
| **`NotoSerifCJK16.ttf`** | Default bundled 16px TrueType font covering extensive CJK & Unicode glyphs. |
| **`README_HANGUL.md`** | Detailed Korean documentation (한글 사용 설명서). |

---

## ⚙️ Environment Setup & Prerequisites

All scripts in this repository are designed to work out-of-the-box on Windows, macOS, and Linux without containing any user-specific hardcoded paths.

### 1. Requirements
- **Python 3.8+**:
  ```bash
  pip install pillow freetype-py
  ```
- **Java Runtime (JRE / JDK 8+)**: Required for running AppleCommander disk operations. Verify with `java -version`.

### 2. AppleCommander Configuration (3 Easy Options)
AppleCommander (`AppleCommander.jar`) handles reading and writing DOS 3.3 `.dsk` disk images. Choose any of the following options:

- **Option A (Zero-config, Default)**:  
  A pre-packaged copy of `AppleCommander.jar` is included directly in the [`tools/`](tools/) directory. All scripts detect it automatically without any setup needed.
- **Option B (System Environment Variable)**:  
  Point to an existing AppleCommander JAR on your machine:
  - **Windows (PowerShell)**:
    ```powershell
    [System.Environment]::SetEnvironmentVariable('APPLECOMMANDER_JAR', 'C:\path\to\AppleCommander.jar', 'User')
    ```
  - **Linux / macOS (`~/.bashrc` or `~/.zshrc`)**:
    ```bash
    export APPLECOMMANDER_JAR="/usr/local/bin/AppleCommander.jar"
    ```
- **Option C (CLI Parameter)**:  
  Pass the path directly when invoking scripts:
  ```bash
  python build_font_dsk.py --dsk unicode.dsk --ac-jar "/path/to/AppleCommander.jar"
  ```

### 3. Diagnose Environment (`ac_tool.py check`)
Run the built-in diagnostic tool anytime to check Java and AppleCommander readiness:

```bash
python ac_tool.py check
```

---

## 🛠️ Quick Start Guide

### Step 1: Start the PC Font Server

Ensure Python 3 with `Pillow` and `freetype-py` is installed (or run the standalone `hangul_server.exe`):

```bash
# Using Python
python unicode_server.py

# Or run the standalone executable:
./unicode_server.exe
```

*By default, the server listens on `127.0.0.1:1977` for emulator connections, or you can pass `--port COMx` for physical USB serial connections.*

### Step 2: Launch AppleWin or Real Hardware

#### Using AppleWin:
1. Open **AppleWin**.
2. Configure **Slot 2** as **Super Serial Card (SSC)** connecting to `TCP 127.0.0.1:1977`.
3. Insert `unicode.dsk` into Drive 1 and boot (`F2`).

#### Using Real Apple II Hardware:
1. Connect your PC to the Apple II Super Serial Card (Slot 2) using an RS-232 to USB adapter cable.
2. Run `python unicode_server.py --serial COM3 --baud 9600`.
3. Boot `unicode.dsk` on your Apple II.

### Step 3: Run the Demonstration

At the Applesoft `]` prompt, type:
```basic
RUN DEMO
```
Watch the Apple II high-resolution screen seamlessly display high-density Korean, Hanja, and multilingual typographic scripts!

---

## 💾 Standalone Font Subsetter & Offline DSK Baking

If you want to run multilingual Apple II programs **completely standalone from floppy disk** without having the PC serial font server running, you can extract the exact font subset used by your BASIC programs and bake them into the DSK image as a binary `FONT` file (loaded at `$6000`).

### 1. Principles of Font Subsetting on Retro Systems
- **Overcoming 140 KB Floppy Capacity**: Storing the full Unicode Hangul syllabus (11,172 characters ≈ 357 KB) or tens of thousands of Hanja characters exceeds the entire capacity of a 140 KB DOS 3.3 floppy disk.
- **Extracting Only Used Glyphs**: By scanning your BASIC source and extracting only the unique characters actually referenced (for instance, the 77 unique Hanja and Hangul characters across *Je-mang-mae-ga* and `DEMO`), the entire font table is compressed down to **only 2.7 KB** (occupying just 12 disk sectors).
- **Fast Local Rendering in RAM**: On boot, the `HELLO` startup script executes `BLOAD FONT`, placing the font table at `$6000`. The 6502 driver immediately detects the cache and draws glyphs directly from local RAM with zero communication latency.

### 2. Building & Injecting the Font Table
Run `build_font_dsk.py` to scan BASIC programs and automatically package the font binary into the disk:

```bash
# Scan all BASIC programs in unicode.dsk and inject FONT binary
python build_font_dsk.py --dsk unicode.dsk

# Or target specific BASIC programs (e.g. DEMO, JEMANG)
python build_font_dsk.py --dsk unicode.dsk --programs DEMO,JEMANG
```

- **What `build_font_dsk.py` does**:
  1. Scans the selected BASIC programs (`DEMO`, `JEMANG`, etc.) and extracts all unique Unicode characters.
  2. Renders high-quality 14×16 bitmap glyphs using host TrueType fonts via FreeType.
  3. Uses `AppleCommander` to inject the `FONT` binary into the DSK image at `$6000` and automatically patches `HELLO` with `BLOAD FONT`.
  4. Now you can boot `unicode.dsk` in AppleWin or on real hardware and run `RUN DEMO` or `RUN JEMANG` with zero PC connection!

### 3. Automatic Synchronization via `inject_basic.py`
When authoring or modifying BASIC code on your PC, using `inject_basic.py` automatically synchronizes newly introduced characters into the DSK's `FONT` table in a single step:

```bash
python inject_basic.py
```

### 4. Binary Rendering Integrity Verification (`verify_dsk_font.py`)
To mathematically verify that the baked `FONT` binary inside the DSK renders correctly without any glyph corruption:

```bash
python verify_dsk_font.py
```
- Extracts the raw binary `FONT` from the DSK image and renders pixel-perfect Apple II HGR (280×192) screen captures ([`verified_standalone_jemang.png`](docs/images/verified_standalone_jemang.png) and [`verified_standalone_demo.png`](docs/images/verified_standalone_demo.png)).

---

## 🔤 Font Engine: Retro Pixel Fonts & Scalable Vectors

`apple2-unicode-bridge` accommodates both **Vector Outlines** and **Pixel/Bitmap Fonts** within the low-resolution 14×16 Apple II HGR grid:

* **Pixel / Bitmap TTF Fonts (Recommended for Authentic Retro Aesthetic)**:  
  Fonts such as **Galmuri14** and **Neo둥근모** are designed on integer pixel grids. When rendered in 1-bit monochrome, they produce razor-sharp, hand-tuned retro glyphs without stroke collisions or dropped lines.
* **Vector Outline TTF Fonts (Universal Multilingual Coverage)**:  
  Fonts like **Noto Serif CJK** or system fonts provide complete worldwide Unicode coverage (thousands of characters across CJK, Cyrillic, Greek, Arabic, Latin).
* **Embedded Bitmap Strikes (`EBDT` / `sbit`)**:  
  Fonts like Windows **굴림 (`gulim.ttc`)** contain built-in 14×14 1-bit monochrome bitmaps for Hangul and Hanja, which FreeType uses automatically.

### Bundled Font Library (`fonts/`)

| Font File | Type | Target Grid | Characteristics | License |
| :--- | :--- | :--- | :--- | :--- |
| **`Galmuri14.ttf`** | Pixel TTF | 14×14 | **Recommended default for HGR.** Crisp Korean glyphs with ideal 1-line top & bottom margins in 14×16 cells (`--y-offset 1`). | SIL OFL 1.1 |
| **`Galmuri11.ttf`** | Pixel TTF | 11×11 | Compact pixel font, ideal for dense layouts or 80-column style Apple II displays. | SIL OFL 1.1 |
| **`Galmuri9.ttf`** | Pixel TTF | 9×9 | Ultra-compact micro pixel font for status bars and HUDs. | SIL OFL 1.1 |
| **`neodgm.ttf`** | Pixel TTF | 16×16 | **Neo둥근모.** The legendary 1990s Korean MS-DOS aesthetic (Hanme Taja, Iyagi). Full 16-row height with thick, bold retro strokes. | SIL OFL 1.1 |
| **`Sam3KRFont.ttf`** | Pixel TTF | 16×16 | **삼국지3 한글 글꼴.** Faithful reproduction of the classic Koei Romance of the Three Kingdoms III Hangul bitmap font. | MIT License |
| **`DOSGothic.ttf`** | Pixel TTF | 16×16 | **도스고딕.** Classic Korean MS-DOS Gothic monospace pixel font. | MIT License |
| **`DOSMyungjo.ttf`** | Pixel TTF | 16×16 | **도스명조.** Classic Korean MS-DOS serif (myeongjo) pixel font. | MIT License |
| **`NotoSerifCJK16.ttf`** | Vector TTF | Scalable | Full CJK Unicode vector font covering Hangul, Hanja, Japanese Kana, Cyrillic, Greek, and Latin diacritics. | SIL OFL 1.1 |

### Font Customization, Auto-Detection & Manual Overrides

Both `unicode_server.py` and `build_font_dsk.py` feature **smart auto-detection** alongside full manual override flags:

#### 1. Zero-Configuration Mode (Automatic Detection)
When you omit `--size`, `--y-offset`, or `--box-center`, the engine automatically detects the font's native pixel grid and applies optimal padding:
```bash
# Auto-detects 14px with 1-line top margin (ideal for 14x14 in 14x16 cell)
python unicode_server.py --font Galmuri14.ttf

# Auto-detects 16px native height and centers vertically
python unicode_server.py --font neodgm.ttf

# Auto-detects 11px / 9px native size and centers vertically
python unicode_server.py --font Galmuri11.ttf
```

#### 2. Manual Override Examples
You can explicitly override any parameter whenever desired:
```bash
# Force custom size (e.g., scale Neo둥근모 down to 14px, or scale NotoSerif to 16px)
python unicode_server.py --font neodgm.ttf --size 14
python unicode_server.py --font NotoSerifCJK16.ttf --size 16

# Custom vertical shift (e.g., push glyph down by 2 pixels)
python unicode_server.py --font Galmuri14.ttf --y-offset 2

# Force box-centering or force pure vector outline rasterization
python unicode_server.py --font Galmuri14.ttf --box-center
python unicode_server.py --font NotoSerifCJK16.ttf --force-vector
```

### Multi-Font & Multi-Size Showcase: `RUN DEMO`

When running `DEMO` on the Apple II (`RUN DEMO`), the system demonstrates its ability to display **multiple distinct fonts and sizes on the same screen, line by line**:

| Line (Row) | Font Name | Pixel Size | Type | Rendered Text Preview |
| :---: | :--- | :---: | :---: | :--- |
| **Row 1** | **`Galmuri14`** | 14 px | 픽셀 | `[GALMURI14] 안녕하세요애플투` |
| **Row 2** | **`Neo둥근모`** | 16 px | 도스 픽셀 | `[NEODGM 16] 도스타자방이야기` |
| **Row 3** | **`삼국지3글꼴`** | 16 px | 고전 한자/한글 | `[SAM3K  16] 三國志英雄崛起` |
| **Row 4** | **`도스명조`** | 16 px | 세리프 픽셀 | `[MYUNGJO16] 붓글씨고전바탕` |
| **Row 5** | **`Galmuri11`** | 11 px | 소형 픽셀 | `[GALMURI11] 조밀한작은폰트` |
| **Row 6** | **`Galmuri9`** | 9 px | 마이크로 픽셀 | `[GALMURI 9] 초소형모니터화면` |
| **Row 7** | **`NotoSerifCJK`** | 14 px | 벡터 외곽선 | `[NOTOSERIF] 漢字萬國훈민정음` |
| **Row 8** | *System* | 7×16 | ASCII | `1977 - 2026 RETRO COMPUTING` |

![Multi-Font Standalone Demo](docs/images/verified_standalone_demo.png)

### Previewing & Comparing Fonts (`tools/preview_fonts.py`)

Run the font preview utility to render and compare all fonts side-by-side in both ASCII terminal format and as an exported high-resolution graphic comparison:

```bash
python tools/preview_fonts.py
# Saves side-by-side comparison to docs/images/font_comparison.png
```

---

## 🤝 Contributing

Contributions to `apple2-unicode-bridge` are warmly welcomed! Areas of active exploration:
- Additional 6502 drivers for ProDOS and 80-column Double High-Resolution (DHGR 560×192) modes.
- Support for bidirectional text (Arabic, Hebrew) shaping engines on the host side.
- Pre-configured disk images for other retro machines with 6502/serial setups.

Please feel free to open an issue or submit a Pull Request!

---

## 📄 License

- **Source Code & Documentation**: Licensed under the [MIT License](LICENSE). Copyright (c) 2026 mildstorm.
- **Bundled Fonts**:
  - `Galmuri` series (`Galmuri14.ttf`, `Galmuri11.ttf`, `Galmuri9.ttf`): [SIL Open Font License 1.1](fonts/README.md) by quiple.
  - `Neo둥근모` (`neodgm.ttf`): [SIL Open Font License 1.1](fonts/README.md) by Dalgona.
  - `Sam3KRFont.ttf`, `DOSGothic.ttf`, `DOSMyungjo.ttf`: [MIT License](fonts/README.md) by Damheo Lee.
  - `NotoSerifCJK16.ttf`: [SIL Open Font License 1.1](https://scripts.sil.org/OFL) by Google / Adobe.
