# -*- coding: utf-8 -*-
"""Extract an embedded DefineFont3 from a (zlib) SWF and rebuild it as a real TTF.

Dev-side only (Python 3, needs fontTools). Used to pull the game's actual
MoEBattle / MoEBattle (the Flash efficiency-panel font) out of
gui/flash/fontlib.swf so we can preview it in the overlay tuner.

SWF DefineFont3 glyph shapes are SWF SHAPE records (moveto / straight / quadratic
edges) in a 20480-units-per-em grid, y-DOWN. TrueType glyf is quadratic too, y-UP,
so the geometry maps 1:1 after a y-flip + scale. The one real subtlety is FILL: SWF
uses fill-style sides, TrueType uses non-zero winding -> we re-orient contours by
nesting depth parity (even depth CCW, odd CW) so counters ('0','8','%') stay hollow.

  usage: python swf_font_to_ttf.py <in.swf> <FontName> <out.ttf>
"""
import sys, zlib, struct
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

DEFINEFONT3 = 75
DEFINEFONT2 = 48
EM_FONT3 = 20480.0   # DefineFont3 grid (20x DefineFont2's 1024)
EM_FONT2 = 1024.0
UPM = 2048           # target TrueType units-per-em (<=16384)


class Bits(object):
    def __init__(self, data, pos=0):
        self.d = data; self.byte = pos; self.bit = 0
    def align(self):
        if self.bit: self.byte += 1; self.bit = 0
    def u8(self):
        self.align(); v = self.d[self.byte]; self.byte += 1; return v
    def u16(self):
        self.align(); v = struct.unpack_from("<H", self.d, self.byte)[0]; self.byte += 2; return v
    def s16(self):
        self.align(); v = struct.unpack_from("<h", self.d, self.byte)[0]; self.byte += 2; return v
    def ub(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | ((self.d[self.byte] >> (7 - self.bit)) & 1)
            self.bit += 1
            if self.bit == 8: self.bit = 0; self.byte += 1
        return v
    def sb(self, n):
        if n == 0: return 0
        v = self.ub(n)
        if v & (1 << (n - 1)): v -= (1 << n)
        return v


def load_body(path):
    raw = open(path, "rb").read()
    if raw[:3] == b"CWS": return zlib.decompress(raw[8:])
    if raw[:3] == b"FWS": return raw[8:]
    raise SystemExit("unsupported signature %r" % raw[:3])


def skip_rect(b):
    nb = b.ub(5)
    for _ in range(4): b.ub(nb)
    b.align()


def walk(body):
    b = Bits(body, 0)
    skip_rect(b); b.u16(); b.u16()   # FrameSize, rate, count
    tags = []
    while b.byte < len(body):
        b.align()
        cl = b.u16(); code = cl >> 6; length = cl & 0x3F
        if length == 0x3F:
            length = struct.unpack_from("<I", b.d, b.byte)[0]; b.byte += 4
        tags.append((code, b.byte, length)); b.byte += length
        if code == 0: break
    return tags


def parse_shape(b, num_fill_bits, num_line_bits):
    """Read one glyph SHAPE -> list of contours; each contour a list of (x,y,on)."""
    contours = []
    cur = None
    x = y = 0
    fb, lb = num_fill_bits, num_line_bits
    while True:
        type_flag = b.ub(1)
        if type_flag == 0:
            new_styles = b.ub(1); line_style = b.ub(1)
            fs1 = b.ub(1); fs0 = b.ub(1); move = b.ub(1)
            if not (new_styles or line_style or fs1 or fs0 or move):
                break                                   # EndShapeRecord
            if move:
                mb = b.ub(5); x = b.sb(mb); y = b.sb(mb)
                if cur: contours.append(cur)
                cur = [(x, y, True)]                     # moveto -> on-curve start
            if fs0: b.ub(fb)
            if fs1: b.ub(fb)
            if line_style: b.ub(lb)
            if new_styles:                               # not expected in fonts
                nfb = b.ub(4); nlb = b.ub(4); fb, lb = nfb, nlb
        else:
            straight = b.ub(1)
            if straight:
                nb = b.ub(4) + 2; general = b.ub(1)
                if general:
                    dx = b.sb(nb); dy = b.sb(nb)
                else:
                    if b.ub(1): dx = 0; dy = b.sb(nb)
                    else: dx = b.sb(nb); dy = 0
                x += dx; y += dy
                if cur is None: cur = [(x, y, True)]
                else: cur.append((x, y, True))
            else:
                nb = b.ub(4) + 2
                cdx = b.sb(nb); cdy = b.sb(nb); adx = b.sb(nb); ady = b.sb(nb)
                cx = x + cdx; cy = y + cdy; x = cx + adx; y = cy + ady
                if cur is None: cur = [(0, 0, True)]
                cur.append((cx, cy, False))              # quadratic control (off-curve)
                cur.append((x, y, True))                 # anchor (on-curve)
    if cur: contours.append(cur)
    return contours


def parse_font(body, start, code_tag):
    b = Bits(body, start)
    b.u16()                                              # FontID
    flags = b.u8()
    has_layout = (flags >> 7) & 1
    wide_off = (flags >> 3) & 1
    wide_codes = (flags >> 2) & 1
    b.u8()                                               # LanguageCode
    namelen = b.u8(); name = bytes(body[b.byte:b.byte + namelen]); b.byte += namelen
    n = b.u16()
    off_start = b.byte                                   # offsets are relative to here
    def rdoff(): return (struct.unpack_from("<I", b.d, b.byte)[0], b.byte.__iadd__ if False else None)
    offsets = []
    if wide_off:
        for _ in range(n): offsets.append(struct.unpack_from("<I", b.d, b.byte)[0]); b.byte += 4
        b.byte += 4                                      # CodeTableOffset (u32)
    else:
        for _ in range(n): offsets.append(b.u16())
        b.u16()                                          # CodeTableOffset (u16)
    glyphs = []
    for i in range(n):
        b.byte = off_start + offsets[i]; b.bit = 0
        nfb = b.ub(4); nlb = b.ub(4)
        glyphs.append(parse_shape(b, nfb, nlb))
    # code table follows the last glyph shape (byte-aligned)
    b.align()
    codes = []
    for _ in range(n):
        codes.append(b.u16() if wide_codes else b.u8())
    asc = desc = 0; advances = [0] * n
    if has_layout:
        asc = b.s16(); desc = b.s16(); b.s16()           # ascent, descent, leading
        advances = [b.s16() for _ in range(n)]
        # bounds table + kerning ignored (not needed for a preview font)
    return {"name": name.rstrip(b"\x00").decode("latin-1"), "glyphs": glyphs,
            "codes": codes, "advances": advances, "ascent": asc, "descent": desc}


# ---- winding: re-orient contours so non-zero fill keeps counters hollow ----
def signed_area(pts):
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i][0], pts[i][1]
        x2, y2 = pts[(i + 1) % len(pts)][0], pts[(i + 1) % len(pts)][1]
        a += x1 * y2 - x2 * y1
    return a * 0.5


def point_in_poly(px, py, poly):
    inside = False; n = len(poly); j = n - 1
    for i in range(n):
        xi, yi = poly[i][0], poly[i][1]; xj, yj = poly[j][0], poly[j][1]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def orient(contours):
    """Reverse contours as needed: even nesting depth -> CCW(+area), odd -> CW."""
    for idx, c in enumerate(contours):
        rep = c[0]
        depth = 0
        for k, other in enumerate(contours):
            if k == idx: continue
            if point_in_poly(rep[0], rep[1], other): depth += 1
        want_ccw = (depth % 2 == 0)
        is_ccw = signed_area(c) > 0
        if is_ccw != want_ccw:
            c.reverse()
    return contours


def emit(pen, pts):
    k = next((i for i, p in enumerate(pts) if p[2]), 0)   # rotate to an on-curve start
    pts = pts[k:] + pts[:k]
    pen.moveTo((pts[0][0], pts[0][1]))
    offs = []
    for p in pts[1:]:
        if p[2]:
            if offs:
                pen.qCurveTo(*([(o[0], o[1]) for o in offs] + [(p[0], p[1])])); offs = []
            else:
                pen.lineTo((p[0], p[1]))
        else:
            offs.append(p)
    if offs:
        pen.qCurveTo(*([(o[0], o[1]) for o in offs] + [(pts[0][0], pts[0][1])]))
    pen.closePath()


def build_ttf(font, out_path, em_units):
    scale = UPM / em_units
    order = [".notdef"]; names = []
    cmap = {}
    for i, code in enumerate(font["codes"]):
        nm = ("uni%04X" % code) if code else ("gid%d" % i)
        while nm in order or nm in names: nm += "_"
        names.append(nm); order.append(nm)
        if code and code not in cmap: cmap[code] = nm
    fb = FontBuilder(unitsPerEm=UPM, isTTF=True)
    fb.setupGlyphOrder(order)
    glyf = {}; hmtx = {}
    pen = TTGlyphPen(None); glyf[".notdef"] = pen.glyph(); hmtx[".notdef"] = (round(font["advances"][0] * scale) if font["advances"] else 600, 0)
    for i, nm in enumerate(names):
        contours = font["glyphs"][i]
        tc = []
        xmin = 1e9
        for c in contours:
            pc = [(round(x * scale), round(-y * scale), on) for (x, y, on) in c]
            if pc:
                xmin = min(xmin, min(p[0] for p in pc))
            tc.append(pc)
        orient(tc)
        pen = TTGlyphPen(None)
        for c in tc:
            if len(c) >= 2: emit(pen, c)
        glyf[nm] = pen.glyph()
        adv = round(font["advances"][i] * scale) if i < len(font["advances"]) else 0
        lsb = int(xmin) if xmin < 1e9 else 0
        hmtx[nm] = (max(adv, 0), lsb)
    fb.setupGlyf(glyf)
    fb.setupHorizontalMetrics(hmtx)
    fb.setupCharacterMap(cmap)
    asc = round(font["ascent"] * scale) or int(UPM * 0.8)
    desc = round(font["descent"] * scale) or int(-UPM * 0.2)
    fb.setupHorizontalHeader(ascent=asc, descent=-abs(desc))
    fam = font["name"]
    fb.setupNameTable({"familyName": fam, "styleName": "Regular",
                       "fullName": fam, "psName": fam.replace(" ", "")})
    fb.setupOS2(sTypoAscender=asc, sTypoDescender=-abs(desc), usWinAscent=asc, usWinDescent=abs(desc))
    fb.setupPost()
    fb.save(out_path)
    print("wrote %s  (%d glyphs, %d cmapped, em=%g->upm=%d)" % (out_path, len(names), len(cmap), em_units, UPM))


def main():
    swf, want, out = sys.argv[1], sys.argv[2], sys.argv[3]
    body = load_body(swf)
    for code, start, length in walk(body):
        if code in (DEFINEFONT2, DEFINEFONT3):
            f = parse_font(body, start, code)
            if f["name"] == want:
                em = EM_FONT3 if code == DEFINEFONT3 else EM_FONT2
                build_ttf(f, out, em)
                return
    raise SystemExit("font %r not found" % want)


if __name__ == "__main__":
    main()
