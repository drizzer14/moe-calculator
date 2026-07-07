"""Generate the in-battle overlay's halftone checker tile (`checker.png`).

WG's efficiency-panel backdrop is a fine halftone dither. Gameface can't tile a
gradient (background-size renders ONE gradient = a smooth blob), so we tile a tiny
RASTER checker instead (rasters DO tile). The tile MUST be natively fine: at
`background-size: auto` the PNG paints at its own pixel size, so a 2px-cell tile
gives ~2px cells in-game -- WG's dither. Shrinking a coarse tile with rem/px
`background-size` was a dead end (goes sub-pixel on the 0.42x browser tuner, and
risks aliasing even with image-rendering:pixelated).

Run with either Python (2.7 or 3) + Pillow:
    python tools/dev/gen_checker.py            # default 2px cells -> 4x4 tile
    python tools/dev/gen_checker.py --cell 3   # iterate cell size if 2px reads wrong

Also prints the base64 data-URI to paste into gen_overlay_tuner.ps1's CHECKER_URI.
"""
import argparse
import base64
import io
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(
    HERE, "..", "..", "src", "res", "gui", "gameface", "mods",
    "14th_ua", "MoECalculator", "checker.png"))


def build(cell):
    """A 2x2-cell seamless tile: black cell / transparent cell, `cell` px each."""
    size = cell * 2
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = im.load()
    for y in range(size):
        for x in range(size):
            if (x // cell + y // cell) % 2 == 0:
                px[x, y] = (0, 0, 0, 255)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", type=int, default=2, help="cell size in px (default 2)")
    args = ap.parse_args()

    im = build(args.cell)
    im.save(OUT)

    buf = io.BytesIO()
    im.save(buf, format="PNG")
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    print("wrote %s (%dx%d, %dpx cells)" % (OUT, im.size[0], im.size[1], args.cell))
    print("CHECKER_URI base64 for gen_overlay_tuner.ps1:")
    print(uri)


if __name__ == "__main__":
    main()
