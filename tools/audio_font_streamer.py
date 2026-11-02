#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Font Streamer for Apple II Unicode Bridge.
Converts Apple II font cache data into ADTPro-compatible audio cassette waveforms
and streams it directly through the PC audio output (3.5mm headphone/line-out)
to the Apple II Cassette In ($C060) port.
"""

import os
import sys
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

from adtpro_audio import stream_font_data_as_audio
from ac_tool import get_raw_file

def main():
    parser = argparse.ArgumentParser(description="Stream Apple II Font Cache via ADTPro Audio Cassette Protocol")
    parser.add_argument("--dsk", default="unicode.dsk", help="DSK image containing 'FONT' file (default: unicode.dsk)")
    parser.add_argument("--wav", default="font_audio.wav", help="Output WAV filename (default: font_audio.wav)")
    parser.add_argument("--play", action="store_true", help="Play audio immediately through PC speaker/headphone out")
    args = parser.parse_args()

    dsk_path = os.path.abspath(args.dsk) if os.path.isabs(args.dsk) else os.path.join(ROOT_DIR, args.dsk)
    if not os.path.exists(dsk_path):
        print(f"[오류] DSK 파일을 찾을 수 없습니다: {dsk_path}")
        sys.exit(1)

    temp_font = f"_temp_font_{os.getpid()}.bin"
    try:
        print(f"[*] '{dsk_path}'에서 'FONT' 바이너리 추출 중...")
        get_raw_file(dsk_path, "FONT", temp_font)
        with open(temp_font, "rb") as f:
            font_data = f.read()

        idx = font_data.find(b"HG")
        if idx == -1:
            print("[오류] FONT 파일에서 'HG' 매직 헤더를 찾을 수 없습니다!")
            sys.exit(1)

        font_payload = font_data[idx:]
        count = font_payload[2]
        print(f"[*] 유효한 폰트 캐시 확인: {count}개 글리프, 총 {len(font_payload)} 바이트")

        wav_file = os.path.abspath(args.wav) if os.path.isabs(args.wav) else os.path.join(ROOT_DIR, args.wav)
        stream_font_data_as_audio(font_payload, output_wav=wav_file, play=args.play)
        print(f"\n[성공] ADTPro 오디오 폰트 스트림 생성 완료!")
        print(f"  - WAV 파일: {wav_file}")
        print(f"  - 재생 안내: PC 3.5mm 이어폰/라인아웃 단자를 애플 II 후면 Cassette IN 단자에 연결하고,")
        print(f"               애플 II에서 & \"/audio\"를 실행한 후 본 WAV 파일을 재생하면 폰트 데이터가 수신됩니다.")
    finally:
        if os.path.exists(temp_font):
            os.remove(temp_font)

if __name__ == "__main__":
    main()
