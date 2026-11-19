#!/usr/bin/env python3
"""Minimal ProDOS volume reader / writer and Applesoft tokenizer.

Enough to build a bootable ProDOS hard-disk image (.hdv / .po, ProDOS block
order) of any size up to 65535 blocks (32 MB): files in the volume directory
only, seedling / sapling / tree storage, and sparse files (index entries of
0 for blocks that are all zeros, which ProDOS reads back as zeros).
"""
import datetime
import struct

BLOCK = 512

# ProDOS file types
TYPE_BIN = 0x06
TYPE_BAS = 0xFC
TYPE_SYS = 0xFF


def prodos_datetime(when=None):
    when = when or datetime.datetime.now()
    date = ((when.year % 100) << 9) | (when.month << 5) | when.day
    return struct.pack("<HBB", date, when.minute, when.hour)


# --- Reading ---

def read_volume(path):
    """Returns ([(name, type, aux, data)], block0_1) from a ProDOS-order image."""
    img = open(path, "rb").read()

    def block(n):
        return img[n * BLOCK:(n + 1) * BLOCK]

    def index_ptrs(blk):
        b = block(blk)
        return [b[i] | (b[256 + i] << 8) for i in range(256)]

    def read_blocks(ptrs, count):
        out = bytearray()
        for p in ptrs[:count]:
            out += block(p) if p else bytes(BLOCK)
        return out

    files = []
    blk = 2
    first = True
    while blk:
        b = block(blk)
        nxt = struct.unpack_from("<H", b, 2)[0]
        for i in range(13):
            off = 4 + i * 39
            if first and i == 0:
                continue                      # volume header
            st_len = b[off]
            storage, name_len = st_len >> 4, st_len & 0x0F
            if storage == 0:
                continue
            name = b[off + 1:off + 1 + name_len].decode("ascii")
            ftype = b[off + 16]
            key = struct.unpack_from("<H", b, off + 17)[0]
            eof = b[off + 21] | (b[off + 22] << 8) | (b[off + 23] << 16)
            aux = struct.unpack_from("<H", b, off + 31)[0]
            nblocks = (eof + BLOCK - 1) // BLOCK
            if storage == 1:
                data = block(key)
            elif storage == 2:
                data = read_blocks(index_ptrs(key), nblocks)
            elif storage == 3:
                data = bytearray()
                for ip in index_ptrs(key):
                    if len(data) >= eof:
                        break
                    data += read_blocks(index_ptrs(ip), 256) if ip else bytes(256 * BLOCK)
            else:
                continue                      # subdirectories etc. are not needed
            files.append((name, ftype, aux, bytes(data[:eof])))
        blk = nxt
        first = False
    return files, img[:2 * BLOCK]


# --- Writing ---

class Volume:
    DIR_BLOCKS = 4                            # volume directory: blocks 2-5

    def __init__(self, total_blocks, name, boot_blocks=bytes(2 * BLOCK)):
        assert 280 <= total_blocks <= 65535
        self.total = total_blocks
        self.name = name.upper()
        self.img = bytearray(total_blocks * BLOCK)
        self.img[:2 * BLOCK] = boot_blocks[:2 * BLOCK]
        self.used = set(range(2 + self.DIR_BLOCKS))
        self.bitmap_start = 2 + self.DIR_BLOCKS
        self.bitmap_blocks = (total_blocks + 4095) // 4096
        self.used.update(range(self.bitmap_start, self.bitmap_start + self.bitmap_blocks))
        self.next_free = self.bitmap_start + self.bitmap_blocks
        self.entries = []

    def _alloc(self):
        while self.next_free in self.used:
            self.next_free += 1
        if self.next_free >= self.total:
            raise RuntimeError("volume full")
        self.used.add(self.next_free)
        return self.next_free

    def _put(self, blk, data):
        self.img[blk * BLOCK:blk * BLOCK + len(data)] = data

    def _index_block(self, ptrs):
        b = bytearray(BLOCK)
        for i, p in enumerate(ptrs):
            b[i], b[256 + i] = p & 0xFF, p >> 8
        return b

    def add_file(self, name, ftype, aux, data, eof=None, sparse=True):
        """Adds a file. eof may be larger than data (the rest reads as zeros);
        with sparse, data blocks of all zeros are not allocated."""
        eof = len(data) if eof is None else eof
        nblocks = max(1, (eof + BLOCK - 1) // BLOCK)
        used = 0

        def data_ptr(i):
            nonlocal used
            chunk = bytes(data[i * BLOCK:(i + 1) * BLOCK])
            if sparse and i > 0 and not any(chunk):
                return 0                     # ProDOS needs the first block
            blk = self._alloc()
            self._put(blk, chunk)
            used += 1
            return blk

        if nblocks == 1:
            storage, key = 1, data_ptr(0)
        elif nblocks <= 256:
            storage = 2
            ptrs = [data_ptr(i) for i in range(nblocks)]
            key = self._alloc()
            used += 1
            self._put(key, self._index_block(ptrs))
        else:
            storage = 3
            master = []
            for start in range(0, nblocks, 256):
                ptrs = [data_ptr(i) for i in range(start, min(start + 256, nblocks))]
                if sparse and not any(ptrs):
                    master.append(0)
                    continue
                ib = self._alloc()
                used += 1
                self._put(ib, self._index_block(ptrs))
                master.append(ib)
            key = self._alloc()
            used += 1
            self._put(key, self._index_block(master))
        self.entries.append((name.upper(), storage, ftype, key, used, eof, aux))

    def _entry(self, name, storage, ftype, key, used, eof, aux):
        e = bytearray(39)
        e[0] = (storage << 4) | len(name)
        e[1:1 + len(name)] = name.encode("ascii")
        e[16] = ftype
        struct.pack_into("<HH", e, 17, key, used)
        e[21:24] = eof.to_bytes(3, "little")
        e[24:28] = prodos_datetime()
        e[30] = 0xE3                          # access: destroy, rename, write, read
        struct.pack_into("<H", e, 31, aux)
        e[33:37] = prodos_datetime()
        struct.pack_into("<H", e, 37, 2)      # header pointer: volume directory
        return e

    def save(self, path):
        per_block = 13
        if len(self.entries) > per_block * self.DIR_BLOCKS - 1:
            raise RuntimeError("too many files for the volume directory")
        slots = [None] + self.entries         # slot 0 is the volume header
        for d in range(self.DIR_BLOCKS):
            blk = 2 + d
            b = bytearray(BLOCK)
            struct.pack_into("<HH", b, 0, blk - 1 if d else 0,
                             blk + 1 if d < self.DIR_BLOCKS - 1 else 0)
            for i in range(per_block):
                n = d * per_block + i
                if n == 0:
                    h = bytearray(39)
                    h[0] = 0xF0 | len(self.name)
                    h[1:1 + len(self.name)] = self.name.encode("ascii")
                    h[24:28] = prodos_datetime()
                    h[30] = 0xC3
                    h[31], h[32] = 0x27, 0x0D
                    struct.pack_into("<HHH", h, 33, len(self.entries),
                                     self.bitmap_start, self.total)
                    b[4:43] = h
                elif n < len(slots):
                    b[4 + i * 39:4 + (i + 1) * 39] = self._entry(*slots[n])
            self._put(blk, b)
        # Volume bitmap: 1 = free
        bitmap = bytearray(self.bitmap_blocks * BLOCK)
        for blk in range(self.total):
            if blk not in self.used:
                bitmap[blk >> 3] |= 0x80 >> (blk & 7)
        self._put(self.bitmap_start, bitmap)
        with open(path, "wb") as f:
            f.write(self.img)


# --- Applesoft tokenizer ---

TOKENS = (
    "END FOR NEXT DATA INPUT DEL DIM READ GR TEXT PR# IN# CALL PLOT HLIN VLIN "
    "HGR2 HGR HCOLOR= HPLOT DRAW XDRAW HTAB HOME ROT= SCALE= SHLOAD TRACE NOTRACE "
    "NORMAL INVERSE FLASH COLOR= POP VTAB HIMEM: LOMEM: ONERR RESUME RECALL STORE "
    "SPEED= LET GOTO RUN IF RESTORE & GOSUB RETURN REM STOP ON WAIT LOAD SAVE DEF "
    "POKE PRINT CONT LIST CLEAR GET NEW TAB( TO FN SPC( THEN AT NOT STEP + - * / ^ "
    "AND OR > = < SGN INT ABS USR FRE SCRN( PDL POS SQR RND LOG EXP COS SIN TAN ATN "
    "PEEK LEN STR$ VAL ASC CHR$ LEFT$ RIGHT$ MID$").split()
assert len(TOKENS) == 107
TOK_REM, TOK_DATA = 0x80 + TOKENS.index("REM"), 0x80 + TOKENS.index("DATA")


def _tokenize_line(text):
    out = bytearray()
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = text.find('"', i + 1)
            j = n if j < 0 else j + 1
            out += text[i:j].encode("latin-1")
            i = j
            continue
        if c == ' ':
            i += 1
            continue
        if c == '?':
            out.append(0x80 + TOKENS.index("PRINT"))
            i += 1
            continue
        # Keyword match ignoring spaces, in table order, as Applesoft does
        tok = None
        for t, word in enumerate(TOKENS):
            k, j = 0, i
            while k < len(word) and j < n:
                if text[j] == ' ':
                    j += 1
                    continue
                if text[j].upper() != word[k]:
                    break
                k, j = k + 1, j + 1
            if k == len(word):
                if word == "AT" and text[j:j + 1].upper() == "N":
                    continue                  # ATN
                tok, i = t, j
                break
        if tok is not None:
            out.append(0x80 + tok)
            if 0x80 + tok == TOK_REM:
                out += text[i:].encode("latin-1")
                break
            if 0x80 + tok == TOK_DATA:
                j = text.find(':', i)
                j = n if j < 0 else j
                out += text[i:j].encode("latin-1")
                i = j
            continue
        out.append(ord(c.upper()))
        i += 1
    return bytes(out)


def tokenize(program, base=0x0801):
    """Tokenizes Applesoft source lines ('10 PRINT "HI"') into a program image
    loaded at base, as a BAS file holds it."""
    out = bytearray()
    for line in program.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        num, _, rest = line.partition(' ')
        body = _tokenize_line(rest)
        link = base + len(out) + 4 + len(body) + 1
        out += struct.pack("<HH", link, int(num)) + body + b"\0"
    return bytes(out + b"\0\0")
