"""A model of the placeholder world generator in asm/world.asm.

The world is 256 x 256 tiles, y increasing downwards. tile_at(x, y) is
computed from two generated tables, exactly as the 6502 does it:

- HEIGHTS[x], the surface row for each column, a smooth random curve;
- PERM, a permutation of 0-255 used as a hash.
"""

from __future__ import annotations

import math
import random

from stratagem.tiles import AIR, BEDROCK, GEM, GRASS, ORE, SKY, SOIL, STONE, WATER

WORLD_SIZE = 256
SEED = 1988

SOIL_DEPTH = 4          # soil rows below the grass, plus 0-3 from the hash
CAVE_THRESHOLD = 40     # cave where the coarse hash is below this
WATER_DEPTH = 200       # caves at or below this row hold water
ORE_THRESHOLD = 12      # ore where the fine hash is below this
GEM_THRESHOLD = 15      # gem where it is below this (and not ore)


def _make_tables(seed: int) -> tuple[list[int], list[int]]:
    rng = random.Random(seed)
    phases = [rng.uniform(0, 2 * math.pi) for _ in range(3)]
    heights = []
    for x in range(WORLD_SIZE):
        h = 48 + 10 * math.sin(2 * math.pi * x / 256 * 3 + phases[0])
        h += 5 * math.sin(2 * math.pi * x / 256 * 7 + phases[1])
        h += 2 * math.sin(2 * math.pi * x / 256 * 19 + phases[2])
        heights.append(int(round(h)))
    perm = list(range(256))
    rng.shuffle(perm)
    return heights, perm


HEIGHTS, PERM = _make_tables(SEED)


def tile_at(x: int, y: int) -> int:
    if x == 0 or x == WORLD_SIZE - 1 or y == WORLD_SIZE - 1:
        return BEDROCK
    h = HEIGHTS[x]
    if y < h:
        return SKY
    if y == h:
        return GRASS
    fine = PERM[PERM[x] ^ y]
    if y - h <= SOIL_DEPTH + (fine & 3):
        return SOIL
    coarse = PERM[(x >> 2) ^ PERM[y >> 1]]
    if coarse < CAVE_THRESHOLD:
        return WATER if y >= WATER_DEPTH else AIR
    if fine < ORE_THRESHOLD:
        return ORE
    if fine < GEM_THRESHOLD:
        return GEM
    return STONE


def view_tiles(view_x: int, view_y: int, size: int = 16) -> list[list[int]]:
    """The tiles of a size x size view whose top-left tile is (view_x, view_y)."""
    return [[tile_at(view_x + i, view_y + j) for i in range(size)] for j in range(size)]
