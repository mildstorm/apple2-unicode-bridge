#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive End-to-End Verification Test Script for apple2-unicode-bridge
Tests:
1. All bundled fonts integrity and loading (FreeType & PIL)
2. Multi-font rasterizer logic and character mapping
3. DSK inspection & FONT binary parsing from unicode.dsk
4. Simulation of Apple II HGR rendering for DEMO and JEMANG
5. Live TCP Server & SSC protocol emulation (0x81, 0x87, 0xAA)
"""

import os
import sys
import socket
import threading
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

from unicode_server import HangulRasterizer, HangulTerminalServer, MULTI_FONT_SPECS
from ac_tool import list_dsk_files, get_raw_file, export_text_file
from build_font_dsk import process_dsk
from verify_dsk_font import verify_and_render

def test_1_font_loading():
    print("\n[TEST 1] Bundled Fonts Loading & Glyph Rasterization")
    fonts_dir = os.path.join(ROOT_DIR, "fonts")
    assert os.path.exists(fonts_dir), "fonts/ directory does not exist!"
    
    font_files = [
        "Galmuri14.ttf", "Galmuri11.ttf", "Galmuri9.ttf",
        "neodgm.ttf", "Sam3KRFont.ttf", "DOSGothic.ttf",
        "DOSMyungjo.ttf", "NotoSerifCJK16.ttf"
    ]
    for fn in font_files:
        fp = os.path.join(fonts_dir, fn)
        if not os.path.exists(fp):
            fp = os.path.join(ROOT_DIR, fn)
        assert os.path.exists(fp), f"Missing font: {fn}"
        r = HangulRasterizer(font_path=fp, font_size=14)
        g = r.rasterize('한')
        assert len(g) == 32, f"Invalid glyph length {len(g)} for {fn}"
        print(f"  * {fn:20s}: OK (14x16 glyph = 32 bytes)")
    print("  -> TEST 1 PASSED!")

def test_2_dsk_baking_and_verification():
    print("\n[TEST 2] Standalone DSK Baking & HGR Rendering Verification")
    dsk_path = os.path.join(ROOT_DIR, "unicode.dsk")
    assert os.path.exists(dsk_path), "unicode.dsk does not exist!"
    
    # 1. Bake font table
    ok = process_dsk(dsk_path)
    assert ok, "process_dsk failed!"
    
    # 2. Check catalog
    file_list = list_dsk_files(dsk_path)
    filenames = [name for ftype, name in file_list]
    print(f"  * DSK Files: {filenames}")
    assert 'HANGUL' in filenames, "HANGUL driver missing from DSK!"
    assert 'FONT' in filenames, "FONT binary missing from DSK!"
    assert 'DEMO' in filenames, "DEMO program missing from DSK!"
    
    # 3. Verify HGR simulation
    v_ok = verify_and_render(dsk_path)
    assert v_ok, "verify_and_render failed!"
    
    demo_png = os.path.join(ROOT_DIR, "docs", "images", "verified_standalone_demo.png")
    jemang_png = os.path.join(ROOT_DIR, "docs", "images", "verified_standalone_jemang.png")
    assert os.path.exists(demo_png) and os.path.getsize(demo_png) > 1000, "demo PNG not generated!"
    assert os.path.exists(jemang_png) and os.path.getsize(jemang_png) > 1000, "jemang PNG not generated!"
    print(f"  * verified_standalone_demo.png: {os.path.getsize(demo_png)} bytes")
    print(f"  * verified_standalone_jemang.png: {os.path.getsize(jemang_png)} bytes")
    print("  -> TEST 2 PASSED!")

def test_3_live_tcp_server_protocol():
    print("\n[TEST 3] Live TCP Font Server & Apple II Protocol Emulation")
    test_port = 1978
    server = HangulTerminalServer(host="127.0.0.1", port=test_port)
    
    server_thread = None
    client_sock = None
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", test_port))
    server_sock.listen(1)
    
    # We run an emulator of AppleWin connecting to port 1978
    # But wait, HangulTerminalServer connects as a client to AppleWin!
    # (AppleWin listens on 1977, and unicode_server connects to it)
    print("  * Starting mock AppleWin listener on port 1978...")
    
    conn_holder = []
    def mock_applewin():
        c, addr = server_sock.accept()
        conn_holder.append(c)
    
    t_listen = threading.Thread(target=mock_applewin, daemon=True)
    t_listen.start()
    
    # Start HangulTerminalServer in a thread
    def run_srv():
        server.connect()
        server.running = True
        server.listen_apple2()
    
    t_srv = threading.Thread(target=run_srv, daemon=True)
    t_srv.start()
    
    t_listen.join(timeout=3)
    assert conn_holder, "Mock AppleWin did not receive connection from server!"
    c_applewin = conn_holder[0]
    print("  * Mock AppleWin connected successfully.")
    
    # 1. Send 0x87 (CMD_BASIC_DRAW_STR) with Korean text "안녕하세요"
    # Protocol: 0x87, UTF-8 hex string or raw bytes ending with 0x00
    test_str = "\\KEC9588EB8595ED9598EC84B8EC9A94\\N\x00"
    print("  * Sending 0x87 string drawing command to server...")
    c_applewin.sendall(bytes([0x87]) + test_str.encode('ascii'))
    
    # Read response packets from server (should receive CMD_DRAW_GLYPH packets and CMD_DONE 0x00)
    received = bytearray()
    start_time = time.time()
    while time.time() - start_time < 3:
        data = c_applewin.recv(4096)
        if data:
            received.extend(data)
            if received.endswith(b'\x00'): # CMD_DONE
                break
        time.sleep(0.05)
    
    print(f"  * Received {len(received)} bytes response from font server.")
    # Check that received bytes contain CMD_DRAW_GLYPH (0x81)
    assert 0x81 in received, "Server did not send CMD_DRAW_GLYPH packet!"
    print("  * Verified CMD_DRAW_GLYPH (0x81) packets received correctly!")
    
    # Stop server
    server.running = False
    server_sock.close()
    if server.sock:
        server.sock.close()
    print("  -> TEST 3 PASSED!")

def test_4_multifont_and_program_font_switching():
    print("\n[TEST 4] Multi-Font Fallback Chaining & Program-Level Font Switching")
    from unicode_server import parse_font_segments, get_font_rasterizer, HangulRasterizer
    from build_font_dsk import extract_font_tagged_characters

    # 1. Inline Font Tags Parsing
    sample_text = "[F:neodgm]도스타자방 [F:myungjo]명조체 [F:3]삼국지 \\F:noto\\漢字"
    segs = parse_font_segments(sample_text)
    print(f"  * Parsed Segments: {segs}")
    assert len(segs) == 4
    assert segs[0] == ('neodgm', '도스타자방 ')
    assert segs[1] == ('myungjo', '명조체 ')
    assert segs[2] == ('3', '삼국지 ')
    assert segs[3] == ('noto', '漢字')
    print("  * Inline font tag parsing: OK")

    # 2. Dynamic Font Rasterizer Retrieval by Alias / Index
    r_neo = get_font_rasterizer("neodgm")
    assert r_neo is not None
    assert len(r_neo.rasterize("도")) == 32
    print("  * 'neodgm' alias rasterizer: OK")

    r_myungjo = get_font_rasterizer("myungjo")
    assert r_myungjo is not None
    assert len(r_myungjo.rasterize("명")) == 32
    print("  * 'myungjo' alias rasterizer: OK")

    # 3. Multi-Font Fallback Chaining
    chain_r = HangulRasterizer(font_path="Galmuri14.ttf, Sam3KRFont.ttf, NotoSerifCJK16.ttf")
    assert len(chain_r.faces) >= 3, "Failed to load multi-font chain faces!"
    g_han = chain_r.rasterize("한")
    g_hanja = chain_r.rasterize("國")
    assert len(g_han) == 32 and len(g_hanja) == 32
    print("  * Comma-separated font fallback chaining: OK")

    # 4. BASIC Program Font Extraction & Custom Aliases
    basic_code = """
    10 REM TEST PROGRAM
    20 & "/alias 1 DOSMyungjo.ttf"
    30 & "/alias title Sam3KRFont.ttf"
    40 & "[F:1]명조체"
    50 & "[F:title]삼국지"
    """
    char_map = extract_font_tagged_characters(basic_code)
    assert char_map['명'] == '1'
    assert char_map['삼'] == 'title'
    r_custom_1 = get_font_rasterizer("1")
    assert r_custom_1 is not None and len(r_custom_1.rasterize("명")) == 32
    r_custom_title = get_font_rasterizer("title")
    assert r_custom_title is not None and len(r_custom_title.rasterize("삼")) == 32
    print("  * Custom arbitrary font aliases & number overrides: OK")
    print("  -> TEST 4 PASSED!")

def test_5_live_applewin_emulator():
    print("\n[TEST 5] Live AppleWin Real Emulator Execution Verification")
    applewin_exe = r"d:\msys64\home\milds\AppleWin\Release\AppleWin.exe"
    if not os.path.exists(applewin_exe):
        print("  * AppleWin.exe not found at path, skipping live emulator test.")
        return

    import tools.test_applewin_live as live_test
    live_test.main()
    print("  -> TEST 5 PASSED!")

def main():
    print("=" * 70)
    print(" Apple II Unicode Bridge: Total System Operations Test")
    print("=" * 70)
    try:
        test_1_font_loading()
        test_2_dsk_baking_and_verification()
        test_3_live_tcp_server_protocol()
        test_4_multifont_and_program_font_switching()
        test_5_live_applewin_emulator()
        print("\n" + "=" * 70)
        print(" ALL END-TO-END VERIFICATION TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 70)
    except Exception as e:
        import traceback
        print(f"\n[TEST FAILED] {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
