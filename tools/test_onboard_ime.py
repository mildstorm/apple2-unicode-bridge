#!/usr/bin/env python3
"""Runs the driver's onboard 2-Bul-Sik automaton (unicode_driver.s, the
Ctrl+K line composed on the Apple II) in a 6502 emulator (py65) on the
cases of test_dubeol_ime.py, so it composes as the server's KoreanAutomata.

    python tools/test_onboard_ime.py       (needs xa and py65: pip install py65)

Each case is typed key by key into OB_KEY, then Return; the \\K..\\N hex it
types into the input buffer is decoded and compared.
"""
import os
import subprocess
import sys
import tempfile

from py65.devices.mpu6502 import MPU

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from test_dubeol_ime import CAPS_CASES, CASES  # noqa: E402

sys.path.insert(0, ROOT)
from unicode_server import decode_apple2_multilingual  # noqa: E402


def assemble():
    tmp = tempfile.mkdtemp()
    binary, labels = os.path.join(tmp, "d.bin"), os.path.join(tmp, "d.lab")
    subprocess.run(["xa", "-o", binary, "-l", labels, os.path.join(ROOT, "unicode_driver.s")],
                   check=True, cwd=ROOT)
    sym = {}
    for line in open(labels):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2 and parts[1].startswith("0x"):
            sym[parts[0]] = int(parts[1], 16)
    return open(binary, "rb").read(), sym


def run(keys, code, sym):
    cpu = MPU()
    mem = cpu.memory
    mem[0x4000:0x4000 + len(code)] = list(code)
    tramp = 0x0300

    def call(addr, a=0):
        mem[tramp:tramp + 4] = [0x20, addr & 0xFF, addr >> 8, 0x00]   # JSR addr; BRK
        cpu.pc, cpu.a, cpu.sp = tramp, a, 0xFF
        for _ in range(200000):
            if mem[cpu.pc] == 0x00 and cpu.pc == tramp + 3:
                return
            cpu.step()
        raise RuntimeError("did not return")

    for name in ("OB_NU", "OB_LANG", "CAND_ON", "BUF_HEAD"):
        mem[sym[name]] = 0
    mem[sym["OB_CAPS"]] = 1          # as OB_IME starts the line: Caps Lock on
    call(sym["OB_RESET"])
    for k in keys:
        call(sym["OB_KEY"], 0x08 if k == "\b" else ord(k))
    call(sym["OB_KEY"], 0x0D)
    mem[sym["OB_WRITE"]] = 1
    call(sym["OB_ENCODE"])
    n = mem[sym["BUF_HEAD"]]
    raw = bytes(mem[sym["BUF_START"]:sym["BUF_START"] + n])
    return decode_apple2_multilingual(raw)


def main():
    code, sym = assemble()
    failed = total = 0
    # On the Apple II the case of a letter is all there is, so the onboard
    # line always guesses Caps Lock: lower-case cases behave as with Shift.
    for keys, want in CASES + CAPS_CASES:
        got = run(keys, code, sym)
        ok = got == want
        failed += not ok
        total += 1
        print(f"{'ok  ' if ok else 'FAIL'} {keys!r:20} -> {got!r} (want {want!r})")
    print(f"\n{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
