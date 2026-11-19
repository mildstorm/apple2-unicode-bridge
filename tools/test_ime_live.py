#!/usr/bin/env python3
"""Live AppleWin check of the Ctrl+K 2-Bul-Sik input line.

1. Boots unicode.dsk in AppleWin (Slot 2 SSC = TCP 1977) and starts
   unicode_server.py against it.
2. Types  10 & "  then Ctrl+K and 2-Bul-Sik keys on the Apple II keyboard,
   and captures the input line on the mixed HGR screen while it composes.
3. Ends with Return, closes the quote, LISTs and RUNs the line.

Screenshots go to ime_*.png in the temp directory. Run from the repository root:
    python tools/test_ime_live.py
"""
import os
import subprocess
import sys
import tempfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from test_applewin_live import (APPLEWIN_EXE, DSK_PATH, WM_CHAR, WM_KEYDOWN,  # noqa: E402
                                WM_KEYUP, capture_hwnd, find_applewin_hwnd, user32)

OUT_DIR = tempfile.gettempdir()


def post_char(hwnd, code):
    # Backspace goes as Ctrl+H ($08), the code the Apple II left arrow sends
    vk = {0x0D: 0x0D, 0x1B: 0x1B}.get(code, 0)
    if vk:
        user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
    user32.PostMessageW(hwnd, WM_CHAR, code, 0)
    if vk:
        user32.PostMessageW(hwnd, WM_KEYUP, vk, 0)
    # The Apple II keyboard latch holds one key: give the driver time to
    # read it before the next one overwrites it
    time.sleep(0.12)


def type_text(hwnd, text):
    for ch in text:
        post_char(hwnd, ord(ch))


def shot(hwnd, name):
    path = os.path.join(OUT_DIR, f"ime_{name}.png")
    capture_hwnd(hwnd).save(path)
    print(f"  * {path}")
    return path


def main():
    subprocess.run(["powershell", "-Command",
                    "Stop-Process -Name AppleWin -Force -ErrorAction SilentlyContinue"],
                   capture_output=True)
    time.sleep(0.5)
    aw = subprocess.Popen([APPLEWIN_EXE, "-d1", DSK_PATH], cwd=os.path.dirname(APPLEWIN_EXE))
    log_path = os.path.join(tempfile.gettempdir(), "ime_live_server.log")
    print(f"  * server log: {log_path}")
    log = open(log_path, "w", encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    srv = subprocess.Popen([sys.executable, os.path.join(ROOT_DIR, "unicode_server.py")],
                           stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                           cwd=ROOT_DIR, env=env)
    try:
        time.sleep(6.0)
        hwnds = find_applewin_hwnd()
        assert hwnds, "AppleWin window not found"
        hwnd = hwnds[0][0]

        type_text(hwnd, "POKE 24576,0\r")
        time.sleep(0.5)
        type_text(hwnd, '10 & "')
        post_char(hwnd, 0x0B)                    # Ctrl+K
        time.sleep(1.0)
        type_text(hwnd, "dkssudgktpdy dovmf2 rhk")  # 안녕하세요 애플2 과
        time.sleep(1.0)
        shot(hwnd, "composing")                   # 과 still composing, inverse
        post_char(hwnd, 0x08)                    # Backspace: 과 -> 고
        time.sleep(0.6)
        shot(hwnd, "backspace")
        post_char(hwnd, 0x0B)                    # 한 -> A
        time.sleep(0.6)
        type_text(hwnd, " ok")
        time.sleep(0.8)
        shot(hwnd, "english")
        post_char(hwnd, 0x0D)                    # Return: into the BASIC line
        time.sleep(1.0)
        shot(hwnd, "injected")
        type_text(hwnd, '"\r')
        time.sleep(0.5)
        type_text(hwnd, "LIST\r")
        time.sleep(1.0)
        shot(hwnd, "list")
        type_text(hwnd, "RUN\r")
        time.sleep(3.0)
        shot(hwnd, "run")

        # A line longer than the 19 cells pages along; ESC then cancels it
        type_text(hwnd, '20 & "')
        post_char(hwnd, 0x0B)
        time.sleep(1.0)
        post_char(hwnd, 0x0B)                    # back to 한 (the mode is kept)
        time.sleep(0.4)
        type_text(hwnd, "rkskekfkakqktkdkwkckzkxkvkgk" * 1)  # 가나다라마바사아자차카타파하
        type_text(hwnd, "rkskekfkakqktkdk")                   # 가나다라마바사아
        time.sleep(1.5)
        shot(hwnd, "paging")
        post_char(hwnd, 0x1B)
        time.sleep(1.0)
        type_text(hwnd, 'X"\r')
        time.sleep(0.5)
        type_text(hwnd, "LIST 20\r")
        time.sleep(1.0)
        shot(hwnd, "cancel")

        # Hanja candidates, then kana, Russian and Greek on one line
        type_text(hwnd, '30 & "')
        post_char(hwnd, 0x0B)
        time.sleep(1.0)
        type_text(hwnd, "gks")
        post_char(hwnd, 0x0A)                    # Ctrl+J: Hanja for 한
        time.sleep(1.5)
        shot(hwnd, "hanja")
        post_char(hwnd, 0x1B)                    # Esc closes the list only
        time.sleep(0.8)
        post_char(hwnd, 0x0A)
        time.sleep(0.8)
        post_char(hwnd, 0x1B)                    # a second Esc, still only the list
        time.sleep(0.8)
        post_char(hwnd, 0x0A)
        time.sleep(0.8)
        type_text(hwnd, "1 ")                    # 限
        post_char(hwnd, 0x0C)                    # あ
        type_text(hwnd, "nihon ")
        post_char(hwnd, 0x0C)                    # ア
        post_char(hwnd, 0x0C)                    # Я
        type_text(hwnd, "ghbdtn ")
        post_char(hwnd, 0x0C)                    # Ω
        type_text(hwnd, "kalhm;era")
        time.sleep(1.5)
        shot(hwnd, "multi")
        post_char(hwnd, 0x0D)
        time.sleep(1.0)
        type_text(hwnd, '"\r')
        time.sleep(0.5)
        type_text(hwnd, "RUN\r")
        time.sleep(4.0)
        shot(hwnd, "multi_run")
        print("[done] check the screenshots and the server log")
    finally:
        srv.terminate()
        aw.terminate()
        log.close()


if __name__ == "__main__":
    main()
