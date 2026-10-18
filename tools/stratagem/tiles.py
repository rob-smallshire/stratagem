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

# A tile in the world is a *kind*: one of the materials above, whole (kinds
# 0 to len(TILE_NAMES) - 1, the same numbers), or a diggable material partly
# dug away, from one side, by quarters. The dug part is empty (like AIR); the
# rest is a solid rectangle.
DIGGABLE = [GRASS, SOIL, STONE, ORE, GEM]
FROM_LEFT, FROM_RIGHT, FROM_TOP, FROM_BOTTOM = range(4)
DIRECTIONS = 4
QUARTERS = 4
PARTIAL_BASE = len(TILE_NAMES)
KIND_COUNT = PARTIAL_BASE + len(DIGGABLE) * DIRECTIONS * (QUARTERS - 1)

TILE_PIXEL_WIDTH = 8
TILE_LINE_HEIGHT = 16


def partial_kind(material: int, direction: int, removed: int) -> int:
    """The kind of `material` with `removed` quarters (1-3) dug away from
    side `direction`."""
    assert 1 <= removed < QUARTERS
    return PARTIAL_BASE + (DIGGABLE.index(material) * DIRECTIONS + direction) * (QUARTERS - 1) + removed - 1


def kind_info(kind: int) -> tuple[int, int, int]:
    """(material, direction, quarters removed) of a kind; whole kinds have
    direction 0 and nothing removed."""
    if kind < PARTIAL_BASE:
        return kind, 0, 0
    index = kind - PARTIAL_BASE
    removed = index % (QUARTERS - 1) + 1
    index //= QUARTERS - 1
    return DIGGABLE[index // DIRECTIONS], index % DIRECTIONS, removed


def kind_rect(kind: int) -> tuple[int, int, int, int] | None:
    """The solid part of a kind, (left, right, top, bottom) in pixels and
    lines within the tile, right and bottom exclusive; None if passable."""
    material, direction, removed = kind_info(kind)
    if material in PASSABLE:
        return None
    left, right, top, bottom = 0, TILE_PIXEL_WIDTH, 0, TILE_LINE_HEIGHT
    if direction == FROM_LEFT:
        left = removed * TILE_PIXEL_WIDTH // QUARTERS
    elif direction == FROM_RIGHT:
        right = TILE_PIXEL_WIDTH - removed * TILE_PIXEL_WIDTH // QUARTERS
    elif direction == FROM_TOP:
        top = removed * TILE_LINE_HEIGHT // QUARTERS
    else:
        bottom = TILE_LINE_HEIGHT - removed * TILE_LINE_HEIGHT // QUARTERS
    return left, right, top, bottom


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


def kind_pixels(kind: int) -> list[list[int]]:
    """A kind's pixels: its material, with the dug part empty."""
    material = kind_info(kind)[0]
    if kind < PARTIAL_BASE:
        return TILE_PIXELS[material]
    left, right, top, bottom = kind_rect(kind)
    return [
        [TILE_PIXELS[material][y][x] if left <= x < right and top <= y < bottom else TILE_PIXELS[AIR][y][x]
         for x in range(TILE_WIDTH_PIXELS)]
        for y in range(TILE_HEIGHT_LINES)
    ]


def tile_graphics() -> list[bytes]:
    """Every kind's 64 bytes, in kind order."""
    return [
        encode_tile([[TILE_COLOUR_BASE + colour for colour in row] for row in kind_pixels(kind)])
        for kind in range(KIND_COUNT)
    ]
