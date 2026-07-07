# -*- coding: utf-8 -*-
"""Probe a (compressed) SWF: decompress, walk tags, dump DefineFont2/3 headers.
Dev-side only (Python 3). Read-only; helps identify the embedded MoEBattle font."""
import sys, zlib, struct

TAG_NAMES = {48: "DefineFont2", 75: "DefineFont3", 73: "DefineFontAlignZones",
             62: "DefineFontInfo2", 13: "DefineFontInfo", 88: "DefineFontName",
             43: "FrameLabel", 0: "End", 9: "SetBackgroundColor", 69: "FileAttributes",
             77: "Metadata", 65: "ScriptLimits", 76: "SymbolClass"}


class Bits(object):
    def __init__(self, data, pos=0):
        self.d = data; self.byte = pos; self.bit = 0
    def align(self):
        if self.bit: self.byte += 1; self.bit = 0
    def u8(self):
        self.align(); v = self.d[self.byte]; self.byte += 1; return v
    def u16(self):
        self.align(); v = struct.unpack_from("<H", self.d, self.byte)[0]; self.byte += 2; return v
    def ub(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | ((self.d[self.byte] >> (7 - self.bit)) & 1)
            self.bit += 1
            if self.bit == 8: self.bit = 0; self.byte += 1
        return v


def load_swf_body(path):
    raw = open(path, "rb").read()
    sig = raw[:3]
    if sig == b"CWS":
        body = zlib.decompress(raw[8:])
    elif sig == b"FWS":
        body = raw[8:]
    else:
        raise SystemExit("unsupported signature %r (need CWS/FWS)" % sig)
    return raw[3], body  # version, body(after 8-byte header)


def skip_rect(b):
    nb = b.ub(5)
    for _ in range(4): b.ub(nb)
    b.align()


def walk(body):
    b = Bits(body, 0)
    skip_rect(b)          # FrameSize
    b.u16(); b.u16()      # frame rate, frame count
    tags = []
    while b.byte < len(body):
        b.align()
        code_len = b.u16()
        code = code_len >> 6
        length = code_len & 0x3F
        if length == 0x3F:
            length = struct.unpack_from("<I", b.d, b.byte)[0]; b.byte += 4
        start = b.byte
        tags.append((code, start, length))
        b.byte = start + length
        if code == 0: break
    return tags


def dump_font(body, start, length, code):
    b = Bits(body, start)
    fid = b.u16()
    flags = b.u8()
    has_layout = (flags >> 7) & 1
    wide_off = (flags >> 3) & 1
    wide_codes = (flags >> 2) & 1
    italic = (flags >> 1) & 1
    bold = flags & 1
    lang = b.u8()
    namelen = b.u8()
    name = bytes(body[b.byte:b.byte + namelen]).decode("latin-1"); b.byte += namelen
    nglyphs = b.u16()
    print("  [%s] id=%d name=%r glyphs=%d bold=%d italic=%d wideOff=%d wideCodes=%d hasLayout=%d lang=%d"
          % (TAG_NAMES.get(code, code), fid, name, nglyphs, bold, italic, wide_off, wide_codes, has_layout, lang))


def main():
    path = sys.argv[1]
    ver, body = load_swf_body(path)
    print("SWF v%d  body=%d bytes" % (ver, len(body)))
    tags = walk(body)
    from collections import Counter
    c = Counter(t[0] for t in tags)
    print("tag histogram:", {TAG_NAMES.get(k, k): v for k, v in sorted(c.items())})
    for code, start, length in tags:
        if code in (48, 75):
            dump_font(body, start, length, code)


if __name__ == "__main__":
    main()
