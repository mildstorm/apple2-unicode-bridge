#!/usr/bin/env python3
"""The font cache as an Apple II cassette recording, for & "/TAPE".

The driver reads it with the monitor's READ routine ($FEFD), so it is in the
standard Apple II cassette format (Apple II Reference Manual, the cassette
interface; the monitor's WRITE writes the same): for each record a leader
tone of 770 Hz, a sync bit (a 2500 Hz half cycle, then a 2000 Hz one), the
bytes most significant bit first (a 0 is one cycle of 2000 Hz, a 1 one of
1000 Hz), then a checksum byte ($FF exclusive-ored with every byte).

READ waits 3.5 seconds after the tone starts before it looks for the sync
bit, so each leader lasts 5 seconds. There are two records: 3 bytes (the
length of the cache and its checksum, which the driver checks the cache
against, since READ only prints ERR), then the cache, which READ puts at
$6000.

The recording is kept as half cycles in microseconds, and goes out as
  - a WAV file, played from the PC's line or headphone output into the
    cassette input of a real Apple II,
  - or the half cycles themselves, to an emulator that takes them, such as
    the STM32F769I-DISCO //e on TCP 6503 (two bytes each, little endian).
"""
import socket
import struct
import wave

LEADER_US = 650          # 770 Hz
SYNC_US = (200, 250)     # 2500 Hz, then 2000 Hz
ZERO_US = 250            # 2000 Hz
ONE_US = 500             # 1000 Hz
LEADER_SECONDS = 5.0
SAMPLE_RATE = 44100


def record_half_cycles(data, leader_seconds=LEADER_SECONDS):
    """One cassette record: leader, sync bit, data bytes, checksum."""
    halves = [LEADER_US] * int(leader_seconds * 1e6 / LEADER_US)
    halves += list(SYNC_US)
    body = bytes(data)
    for b in body + bytes([cache_checksum(body)]):
        for bit in range(7, -1, -1):
            us = ONE_US if (b >> bit) & 1 else ZERO_US
            halves += [us, us]
    halves += [LEADER_US] * 4    # a short tail, so the last cycle ends
    return halves


def cache_checksum(cache):
    checksum = 0xFF
    for b in cache:
        checksum ^= b
    return checksum


def font_cache_half_cycles(cache):
    """The two records & "/TAPE" reads: length and checksum, then the cache."""
    cache = bytes(cache)
    if not 1 <= len(cache) <= 9215:
        raise ValueError(f"a font cache of {len(cache)} bytes does not fit (1-9215)")
    header = struct.pack("<HB", len(cache), cache_checksum(cache))
    return record_half_cycles(header) + record_half_cycles(cache)


def write_wav(halves, path, rate=SAMPLE_RATE, level=100):
    """The half cycles as an 8-bit square wave."""
    samples = bytearray()
    high = True
    t = 0.0
    done = 0
    for us in halves:
        t += us * rate / 1e6
        n = int(round(t)) - done
        samples += bytes([128 + level if high else 128 - level]) * n
        done += n
        high = not high
    samples += bytes([128]) * (rate // 2)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(rate)
        w.writeframes(bytes(samples))
    return len(samples) / rate


def send_half_cycles(halves, host, port=6503, source=None):
    """To an emulator's cassette input over TCP (two bytes each, little
    endian); the emulator plays them at its own speed."""
    data = b"".join(struct.pack("<H", us) for us in halves)
    with socket.create_connection((host, port), timeout=10,
                                  source_address=(source, 0) if source else None) as s:
        s.sendall(data)


def seconds(halves):
    return sum(halves) / 1e6


def play_wav(path):
    """Plays a WAV file through the PC's sound output (Windows)."""
    import winsound
    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_SYNC)


def stream_font_data_as_audio(cache, output_wav="font_audio.wav", play=False):
    """Writes the font cache as a cassette recording (and plays it)."""
    halves = font_cache_half_cycles(cache)
    write_wav(halves, output_wav)
    print(f"[Cassette] {len(cache)} bytes, {seconds(halves):.1f} s: {output_wav}")
    print('[Cassette] On the Apple II run & "/TAPE", then play the file into the cassette input')
    if play:
        play_wav(output_wav)
    return output_wav
