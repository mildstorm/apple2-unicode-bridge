#!/usr/bin/env python3
"""Sends a font cache to an Apple II through its cassette input, for
& "/TAPE" (no serial card or disk needed).

    python tools/audio_font_streamer.py --dsk unicode.dsk --wav font.wav [--play]
    python tools/audio_font_streamer.py --dsk unicode.dsk --board 169.254.246.139
    python tools/audio_font_streamer.py --text "안녕하세요 漢字" --wav font.wav

The cache is the FONT file of a disk image (as build_font_dsk.py makes it),
or one made from --text. On the Apple II run & "/TAPE" first, then play the
WAV file into the cassette input (real hardware), or use --board for the
STM32F769I-DISCO //e, which takes the cassette signal on TCP 6503. The load
takes about 10 seconds of leader plus 6 ms a byte.
"""
import argparse
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

from cassette_audio import font_cache_half_cycles, play_wav, seconds, send_half_cycles, write_wav  # noqa: E402


def cache_from_disk(dsk):
    data = subprocess.run(["java", "-jar", os.path.join(SCRIPT_DIR, "AppleCommander.jar"),
                           "-g", dsk, "FONT"], capture_output=True).stdout
    start = data.find(b"HG")
    if start < 0:
        sys.exit(f"{dsk} has no FONT file with an HG cache")
    count = data[start + 2]
    return data[start:start + 4 + count * 36]


def cache_from_text(text, font):
    from build_font_dsk import build_font_table
    from unicode_server import HangulRasterizer
    chars = sorted({c for c in text if ord(c) > 127})
    return build_font_table(chars, HangulRasterizer(font_path=font))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--dsk", default=os.path.join(ROOT_DIR, "unicode.dsk"),
                     help="disk image with the FONT cache (default: unicode.dsk)")
    src.add_argument("--text", help="make the cache from the characters of this text instead")
    ap.add_argument("--font", default=None, help="font for --text (default: the server's)")
    ap.add_argument("--wav", help="write the recording as a WAV file")
    ap.add_argument("--play", action="store_true", help="play the WAV file through the PC's sound output")
    ap.add_argument("--board", help="send it to an emulator's cassette input over TCP (host)")
    ap.add_argument("--port", type=int, default=6503)
    ap.add_argument("--src", default=None, help="local address to send from (the PC's link-local one)")
    args = ap.parse_args()

    cache = cache_from_text(args.text, args.font) if args.text else cache_from_disk(args.dsk)
    halves = font_cache_half_cycles(cache)
    print(f"[Cassette] font cache {len(cache)} bytes ({cache[2]} glyphs), {seconds(halves):.1f} s")
    if not args.wav and not args.board:
        args.wav = os.path.join(ROOT_DIR, "font_audio.wav")
    if args.wav:
        write_wav(halves, args.wav)
        print(f"[Cassette] WAV: {args.wav}")
        if args.play:
            print('[Cassette] Playing; run & "/TAPE" on the Apple II first')
            play_wav(args.wav)
    if args.board:
        print(f"[Cassette] Sending to {args.board}:{args.port}; run & \"/TAPE\" on the Apple II first")
        send_half_cycles(halves, args.board, args.port, args.src)
        print("[Cassette] Sent; the emulator plays it at its own speed")


if __name__ == "__main__":
    main()
