#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADTPro Audio / Cassette Protocol Encoder & Audio Player for Apple II Unicode Bridge.
Derived from ADTPro (Apple Disk Transfer ProDOS) Audio Transport & BytesToWav specifications.
Copyright (C) 2007-2014 David Schmidt / ADTPro Project.

Modulation:
  - Sample rate: 44,100 Hz, 8-bit or 16-bit PCM Audio
  - Leader tone: 770 Hz
  - Sync bit:    2000-2200 Hz
  - Data '0':    2000 Hz (half cycle ~250 us)
  - Data '1':    1000 Hz (half cycle ~500 us)
  - Checksum:    Running XOR of all transmitted data bytes
  - Trailer:     200 Hz tone + silence
"""

import os
import sys
import wave
import struct

SAMPLE_FREQ = 44100

def encode_bytes_to_audio_pcm(data_bytes: bytes, leader_cycles: int = 300, gain: int = 100) -> bytes:
    """
    Encodes raw data bytes into 8-bit unsigned PCM audio waveform
    compatible with ADTPro BytesToWav and Apple II Cassette In ($C060).
    """
    samples = bytearray()
    remainder = 0.0

    def one_period(freq, in_rem):
        num_bytes = int(SAMPLE_FREQ / (2 * freq))
        rem = in_rem + ((SAMPLE_FREQ / (2.0 * freq)) - num_bytes) / 20.0
        # Positive half-cycle
        val_pos = min(255, max(0, 128 + gain))
        samples.extend([val_pos] * num_bytes)
        if rem > 1.0:
            samples.append(val_pos)
        # Negative half-cycle
        val_neg = min(255, max(0, 128 - gain))
        samples.extend([val_neg] * num_bytes)
        if rem > 1.0:
            samples.append(val_neg)
            rem -= 1.0
        return rem

    # 1. Leader tone: 770 Hz
    for _ in range(leader_cycles):
        remainder = one_period(770, 0.0)

    # 2. Sync bit: 2200 Hz
    remainder = one_period(2200, 0.0)

    # 3. Data bytes
    checksum = 0xFF
    for b in data_bytes:
        checksum ^= b
        curr = b
        for _ in range(8):
            if (curr & 0x80) != 0:
                remainder = one_period(1000, remainder) # '1' = 1000 Hz
            else:
                remainder = one_period(2000, remainder) # '0' = 2000 Hz
            curr = (curr << 1) & 0xFF

    # 4. Checksum byte
    curr = checksum
    for _ in range(8):
        if (curr & 0x80) != 0:
            remainder = one_period(1000, remainder)
        else:
            remainder = one_period(2000, remainder)
        curr = (curr << 1) & 0xFF

    # 5. Trailer: 200 Hz period
    one_period(200, 0.0)

    # 6. Trailing silence (approx. 0.35s)
    samples.extend([128] * 15000)

    return bytes(samples)

def write_audio_wav_file(filename: str, pcm_bytes: bytes, sample_freq: int = SAMPLE_FREQ):
    """Writes 8-bit mono PCM audio data as a standard Windows RIFF WAV file."""
    with wave.open(filename, "wb") as wav_out:
        wav_out.setnchannels(1)      # Mono
        wav_out.setsampwidth(1)      # 8-bit unsigned
        wav_out.setframerate(sample_freq)
        wav_out.writeframes(pcm_bytes)

def play_audio_wav(wav_path: str):
    """Plays WAV audio via Windows audio subsystem (or winsound)."""
    try:
        import winsound
        winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_SYNC)
        return True
    except Exception as e:
        print(f"[ADTPro-Audio] PlaySound note: {e}")
        return False

def stream_font_data_as_audio(font_bytes: bytes, output_wav: str = "font_audio.wav", play: bool = False):
    """Encodes full font cache table into an audio WAV stream for Apple II Cassette In."""
    print(f"[ADTPro-Audio] Encoding {len(font_bytes)} bytes into ADTPro audio format...")
    pcm = encode_bytes_to_audio_pcm(font_bytes, leader_cycles=300, gain=100)
    duration_sec = len(pcm) / SAMPLE_FREQ
    print(f"[ADTPro-Audio] Generated {len(pcm)} samples ({duration_sec:.2f} seconds of audio)")
    write_audio_wav_file(output_wav, pcm)
    print(f"[ADTPro-Audio] Saved WAV audio to: {output_wav}")
    if play:
        print(f"[ADTPro-Audio] Playing audio through PC speaker/headphone jack to Apple II Cassette In...")
        play_audio_wav(output_wav)
    return output_wav
