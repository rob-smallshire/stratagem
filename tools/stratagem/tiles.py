"""Placeholder tile set.

Each tile is 8 x 16 pixels in colours 0-7 of the tile colour group, which
is logical colours 8-15 (TILE_COLOUR_BASE); sprites use logical colours
0-7. The palette maps both groups to physical colours, so either can be
recoloured on its own. The tiles are drawn by code for now; they will come
from an image later.
"""

from __future__ import annotations

from stratagem.screen import TILE_HEIGHT_LINES, TILE_WIDTH_PIXELS, encode_tile

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

TILE_COLOUR_BASE = 8

AIR, GRASS, SOIL, STONE, ORE, GEM, BEDROCK, WATER, SKY = range(9)
TILE_NAMES = ["air", "grass", "soil", "stone", "ore", "gem", "bedrock", "water", "sky"]

# Tiles a body can pass through; the rest are solid.
PASSABLE = frozenset({AIR, WATER, SKY})


def _speckle(x: int, y: int, salt: int) -> int:
    """A small deterministic hash of a pixel position, 0-255."""
    h = (x * 73 + y * 151 + salt * 37) & 0xFF
    h ^= h >> 3
    h = (h * 29 + 11) & 0xFF
    return h


def _pixels(colour_at) -> list[list[int]]:
    return [[colour_at(x, y) for x in range(TILE_WIDTH_PIXELS)] for y in range(TILE_HEIGHT_LINES)]


def _soil(x: int, y: int) -> int:
    return YELLOW if _speckle(x, y, 1) < 40 else RED


def _stone(x: int, y: int) -> int:
    return WHITE if (x + 2 * y) % 5 == 0 or _speckle(x, y, 2) < 24 else BLACK


TILE_PIXELS = {
    AIR: _pixels(lambda x, y: BLACK),
    GRASS: _pixels(lambda x, y: GREEN if y < 3 or (y < 5 and _speckle(x, y, 3) < 128) else _soil(x, y)),
    SOIL: _pixels(_soil),
    STONE: _pixels(_stone),
    ORE: _pixels(lambda x, y: YELLOW if 2 <= x <= 5 and 5 <= y <= 10 and _speckle(x, y, 4) < 170 else _stone(x, y)),
    GEM: _pixels(lambda x, y: (MAGENTA if (x + y) % 2 else CYAN) if abs(x - 3.5) + abs(y - 7.5) / 2 < 3 else _stone(x, y)),
    BEDROCK: _pixels(lambda x, y: BLACK if y % 8 == 7 or (x == (0 if y // 8 % 2 else 4)) else MAGENTA),
    WATER: _pixels(lambda x, y: CYAN if y == (x // 2) % 2 else BLUE),
    SKY: _pixels(lambda x, y: BLUE),
}


def tile_graphics() -> list[bytes]:
    """Every tile's 64 bytes, in tile number order."""
    return [
        encode_tile([[TILE_COLOUR_BASE + colour for colour in row] for row in TILE_PIXELS[tile]])
        for tile in range(len(TILE_NAMES))
    ]
