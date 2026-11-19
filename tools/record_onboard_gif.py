#!/usr/bin/env python3
"""Records the onboard Ctrl+K line as animated GIFs for the README: AppleWin
booted from unicode.hdv, no serial card and no PC server, the screen captured
after every key with a caption saying what was pressed.

    python tools/record_onboard_gif.py          (needs AppleWin, Pillow)

Writes docs/images/onboard_hangul.gif (2-Bul-Sik composing 안녕하세요, a
jamo at a time, then RUN) and docs/images/onboard_hanja.gif (한 국 turned
into 韓國 with Ctrl+J, then RUN). AppleWin's settings are put back afterwards
(it keeps the slot 7 card given on its command line).
"""
import os
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from test_applewin_live import APPLEWIN_EXE, capture_hwnd, find_applewin_hwnd  # noqa: E402
from test_ime_live import post_char, type_text  # noqa: E402

REG_KEY = r"HKCU\Software\AppleWin"
OUT_DIR = os.path.join(ROOT_DIR, "docs", "images")
CAPTION_FONT = r"C:\Windows\Fonts\malgun.ttf"
SCALE = 0.5            # the 1120x768 screen to 560x384
CAPTION_H = 34

CTRL_K, CTRL_J, RETURN = 0x0B, 0x0A, 0x0D


class Recorder:
    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.frames = []
        self.font = ImageFont.truetype(CAPTION_FONT, 17)

    def shot(self, caption, ms=700):
        img = capture_hwnd(self.hwnd).convert("RGB")
        w, h = img.size
        # The Apple II screen, without the title bar, frame and button bar
        screen = img.crop((10, 33, w - 56, h - 9))
        screen = screen.resize((int(screen.width * SCALE), int(screen.height * SCALE)),
                               Image.NEAREST)
        frame = Image.new("RGB", (screen.width, screen.height + CAPTION_H), (24, 24, 24))
        frame.paste(screen, (0, 0))
        draw = ImageDraw.Draw(frame)
        draw.text((10, screen.height + 6), caption, font=self.font, fill=(235, 235, 235))
        self.frames.append((frame, ms))

    def key(self, code, caption, ms=700, wait=0.35):
        post_char(self.hwnd, code)
        time.sleep(wait)
        self.shot(caption, ms)

    def save(self, name):
        path = os.path.join(OUT_DIR, name)
        imgs = [f.convert("P", palette=Image.ADAPTIVE, colors=32) for f, _ in self.frames]
        imgs[0].save(path, save_all=True, append_images=imgs[1:],
                     duration=[ms for _, ms in self.frames], loop=0, optimize=True)
        print(f"  * {path} ({len(imgs)} frames, {os.path.getsize(path) // 1024} KB)")
        self.frames = []


def letters(rec, keys, captions):
    for k, cap in zip(keys, captions):
        rec.key(ord(k), cap)


def record(hwnd):
    rec = Recorder(hwnd)
    # --- Hangul: 안녕하세요, a jamo at a time ---
    type_text(hwnd, "NEW\r")
    type_text(hwnd, "HOME\r")
    type_text(hwnd, '10 & "')
    time.sleep(0.5)
    rec.shot('BASIC 줄 10 & "  (서버·시리얼 카드 없음, HDD 부팅)', 1400)
    rec.key(CTRL_K, "Ctrl+K: 화면 아래에 입력 줄 [한]", 1400, wait=0.8)
    letters(rec, "dkssud", ["d → ㅇ", "k → 아", "s → 안", "s → 안ㄴ", "u → 안녀",
                            "d → 안녕"])
    letters(rec, "gktpdy", ["g → 안녕ㅎ", "k → 안녕하", "t → 안녕핫",
                            "p → 안녕하세  (ㅅ이 다음 글자로)", "d → 안녕하셍",
                            "y → 안녕하세요  (ㅇ이 다음 글자로)"])
    rec.key(0x08, "← (백스페이스): 자모 하나 지움 → 안녕하세ㅇ", 1100)
    rec.key(ord("y"), "y → 안녕하세요", 900)
    rec.key(RETURN, "Return: BASIC 줄에 16진수 문자열로 들어감", 1600, wait=0.8)
    type_text(hwnd, '"\r')
    type_text(hwnd, "RUN\r")
    time.sleep(2.5)
    rec.shot("RUN: 하드디스크의 UFONT로 그림 (서버 없음)", 3000)
    rec.save("onboard_hangul.gif")

    # --- Hanja: 한국 → 韓國 ---
    type_text(hwnd, "NEW\r")
    type_text(hwnd, '& "/CLEAR"\r')     # the first recording off the HGR screen
    type_text(hwnd, "TEXT\r")
    type_text(hwnd, "HOME\r")
    type_text(hwnd, '10 & "')
    time.sleep(0.5)
    rec.shot('BASIC 줄 10 & "', 1200)
    rec.key(CTRL_K, "Ctrl+K: 입력 줄 [한]", 1200, wait=0.8)
    letters(rec, "gks", ["g → ㅎ", "k → 하", "s → 한"])
    rec.key(CTRL_J, "Ctrl+J (↓): '한'의 한자 후보 (1-9, Space 다음 쪽)", 2200, wait=0.8)
    rec.key(ord("8"), "8 → 韓", 1200)
    letters(rec, "rnr", ["r → 韓ㄱ", "n → 韓구", "r → 韓국"])
    rec.key(CTRL_J, "Ctrl+J: '국'의 한자 후보", 2200, wait=0.8)
    rec.key(ord("1"), "1 → 韓國", 1400)
    rec.key(RETURN, "Return: BASIC 줄에 들어감", 1600, wait=0.8)
    type_text(hwnd, '"\r')
    type_text(hwnd, "RUN\r")
    time.sleep(2.5)
    rec.shot("RUN: 韓國 (서버 없음)", 3000)
    rec.save("onboard_hanja.gif")


def main():
    image = os.path.join(ROOT_DIR, "unicode.hdv")
    subprocess.run(["powershell", "-Command",
                    "Stop-Process -Name AppleWin -Force -ErrorAction SilentlyContinue"],
                   capture_output=True)
    time.sleep(0.5)
    saved = os.path.join(tempfile.gettempdir(), "applewin_settings_gif.reg")
    subprocess.run(["reg", "export", REG_KEY, saved, "/y"], capture_output=True, check=True)
    aw = subprocess.Popen([APPLEWIN_EXE, "-s7", "hdc", "-h1", image],
                          cwd=os.path.dirname(APPLEWIN_EXE))
    try:
        time.sleep(8.0)
        hwnds = find_applewin_hwnd()
        assert hwnds, "AppleWin window not found"
        record(hwnds[0][0])
    finally:
        aw.terminate()
        aw.wait(10)
        time.sleep(1.0)
        subprocess.run(["reg", "delete", REG_KEY, "/f"], capture_output=True)
        subprocess.run(["reg", "import", saved], capture_output=True, check=True)
        print("  * AppleWin settings restored")


if __name__ == "__main__":
    main()
