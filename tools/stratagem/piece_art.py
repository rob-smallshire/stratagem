"""Piece art shared by the game's tables (tiles.py) and the labs: pictures
of pieces as rows of characters, and the trees' (docs/tile-set.md).

A piece is a whole tile, 8 pixels by 16 lines, of colours 0-7, with CLEAR
where the backdrop shows.
"""

from __future__ import annotations

import numpy as np

from stratagem.screen import TILE_HEIGHT_LINES as TILE_LINE_HEIGHT, TILE_WIDTH_PIXELS as TILE_PIXEL_WIDTH

W, H = TILE_PIXEL_WIDTH, TILE_LINE_HEIGHT
COLOURS = {"K": 0, "R": 1, "G": 2, "Y": 3, "B": 4, "M": 5, "C": 6, "W": 7}
CLEAR = -1


def _hash(x: int, y: int, salt: int = 0) -> int:
    h = (x * 73 + y * 151 + salt * 97) & 0xFF
    h ^= h >> 3
    return (h * 29 + 11) & 0xFF


def art(text: str, width: int = W, height: int = H) -> np.ndarray:
    """Rows of characters: '.' clear, K black, R G Y B M C W colours."""
    rows = [line for line in text.split("\n") if line.strip()]
    rows += ["." * width] * (height - len(rows))
    assert len(rows) == height and all(len(r) == width for r in rows), text
    return np.array([[CLEAR if c == "." else COLOURS[c] for c in row] for row in rows])


def split(big: np.ndarray, columns: int, rows: int) -> list[list[np.ndarray]]:
    """A picture of columns x rows tiles, as [row][column] tiles."""
    return [[big[j * H:(j + 1) * H, i * W:(i + 1) * W] for i in range(columns)] for j in range(rows)]


# Trees: a canopy three tiles wide and two high (dithered leaves, as in
# Stryker's Run, so that backdrop shows through), over a trunk.

def _canopy() -> np.ndarray:
    width, height = 3 * W, 2 * H
    out = np.full((height, width), CLEAR)
    cx, cy = (width - 1) / 2, height * 0.55
    for y in range(height):
        for x in range(width):
            # Pixels are twice as wide as tall: measure in lines.
            dx, dy = (x - cx) * 2 / (width * 1.0), (y - cy) / (height * 0.58)
            lump = (_hash(x // 2, y // 3, 5) - 128) / 900
            if dx * dx + dy * dy > 1 + lump:
                continue
            depth = y / height
            noise = _hash(x, y, 7)
            if noise < 50 + 120 * depth * depth:
                out[y, x] = COLOURS["K"]
            elif noise > 235 - 40 * (1 - depth) and depth < 0.5:
                out[y, x] = COLOURS["Y"]
            else:
                out[y, x] = COLOURS["G"]
    # The trunk's top, among the lowest leaves.
    for y in range(height - 5, height):
        for x in range(W + 2, W + 6):
            if out[y, x] == CLEAR or _hash(x, y, 9) < 120:
                out[y, x] = COLOURS["K"] if _hash(x, y, 3) < 70 else COLOURS["R"]
    return out


TRUNK = art("""
..RRKR..
..RKRR..
..RRRK..
..KRRR..
..RRKR..
..RRRR..
..RKRR..
..RRRK..
..RRKR..
..KRRR..
..RRRR..
..RKRR..
..RRKR..
..RRRK..
..RKRR..
..RRRR..
""")
TRUNK_KNOT = art("""
..RRKR..
..RKRR..
..RRRK..
..KRRRRK
..RRKRRR
..RRRR.K
..RKRR..
..RRRK..
..RRKR..
..KRRR..
KRRRRR..
RRKKRR..
.K.RRK..
..RRRK..
..RKRR..
..RRRR..
""")
ROOT = art("""
..RRKR..
..RKRR..
..RRRK..
..KRRR..
..RRKR..
..RRRR..
..RKRR..
..RRRK..
..RRKR..
..KRRR..
..RRRR..
.RRKRRR.
.RKRRKRR
RRK.RRKR
RK..KRRR
K....KRK
""")


CANOPY = split(_canopy(), 3, 2)     # [row][column]: top left ... right
