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
| **`build_font_dsk.py`** | Automated font subsetter: extracts used glyphs, bakes `FONT` binary ($6000) into DSK for standalone execution. |
| **`inject_basic.py`** | PC-to-Apple II BASIC injector tool with automatic font synchronization. |
| **`verify_dsk_font.py`** | Verification utility confirming glyph rendering directly from DSK `FONT` binary. |
| **`unicode_driver.s`** | 6502 assembly source code for the Apple II resident driver ($4000). |
| **`unicode.dsk`** | Ready-to-boot DOS 3.3 disk image containing `UNICODE.BIN`, standalone `FONT`, and demo programs. |
| **`UNICODE.BIN`** | Assembled 6502 binary driver ($4000). |
| **`NotoSerifCJK16.ttf`** | Default bundled 16px TrueType font covering extensive CJK & Unicode glyphs. |
| **`README_HANGUL.md`** | Detailed Korean documentation (한글 사용 설명서). |

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

## 🌐 Customizing Fonts for Any Language

The PC server supports any TrueType (`.ttf`), OpenType (`.otf`), or TrueType Collection (`.ttc`) font. You can specify fonts for your preferred writing system (e.g., Cyrillic, Greek, Japanese, Arabic, Hebrew, or custom retro pixel fonts):

```bash
python unicode_server.py --font /path/to/your-font.ttf
```

Common system fonts you can use:
- **Korean / CJK**: `NotoSerifCJK16.ttf`, `gulim.ttc`, `malgun.ttf`
- **Japanese**: `msgothic.ttc`, `meiryo.ttc`
- **Simplified / Traditional Chinese**: `simsun.ttc`, `msjh.ttc`
- **Cyrillic / Greek / Latin**: `consola.ttf`, `arial.ttf`, `DejaVuSansMono.ttf`

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
- **Bundled Fonts**: `NotoSerifCJK16.ttf` is licensed under the [SIL Open Font License 1.1](https://scripts.sil.org/OFL).
