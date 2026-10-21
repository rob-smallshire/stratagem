"""A model of the placeholder world generator in asm/world.asm.

The world is 256 x 256 tiles, y increasing downwards; a tile is (material,
shape). The material at (x, y) is computed from two generated tables,
exactly as the 6502 does it:

- HEIGHTS[x], the surface row for each column, a smooth random curve;
- PERM, a permutation of 0-255 used as a hash.

The shape smooths the terrain: a surface tile with a lower neighbouring
column on one side (only) slopes down towards it, and an underground tile
with open space above or below it and to one side (only) has that corner
rounded off by a ramp.
"""

from __future__ import annotations

import math
import random

from stratagem.tiles import (AIR, BACKGROUND_SKY, BEDROCK, DIGGABLE, FROM_BOTTOM, FROM_TOP, GEM, GRASS, ORE,
                             PASSABLE, SHAPE_FULL, SKY, SOIL, STONE, WATER, shape_of)

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


Tile = tuple[int, int]      # (material, shape)

# Ramps falling to the left and to the right, cut from the top (slopes and
# floors) or the bottom (sloped ceilings).
RAMP_TOP_LEFT = shape_of(FROM_TOP, (3, 2, 1, 0))
RAMP_TOP_RIGHT = shape_of(FROM_TOP, (0, 1, 2, 3))
RAMP_BOTTOM_LEFT = shape_of(FROM_BOTTOM, (3, 2, 1, 0))
RAMP_BOTTOM_RIGHT = shape_of(FROM_BOTTOM, (0, 1, 2, 3))


def generate_material(x: int, y: int) -> int:
    """The material the generator puts at (x, y)."""
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


def _open(x: int, y: int) -> bool:
    return generate_material(x, y) in PASSABLE


def background_bits(x: int, y: int) -> int:
    """BACKGROUND_SKY for tiles at or above the surface line of their column."""
    return BACKGROUND_SKY if y <= HEIGHTS[x] else 0


def generate_tile(x: int, y: int) -> Tile:
    """The tile the generator puts at (x, y): the world before any changes."""
    material, shape = _generate_shaped(x, y)
    return material, shape | background_bits(x, y)


def _generate_shaped(x: int, y: int) -> Tile:
    material = generate_material(x, y)
    if material not in DIGGABLE:
        return material, SHAPE_FULL
    if y == HEIGHTS[x]:
        left_lower = HEIGHTS[x - 1] > y
        right_lower = HEIGHTS[x + 1] > y
        if left_lower and not right_lower:
            return material, RAMP_TOP_LEFT
        if right_lower and not left_lower:
            return material, RAMP_TOP_RIGHT
        return material, SHAPE_FULL
    left_open, right_open = _open(x - 1, y), _open(x + 1, y)
    if left_open == right_open:
        return material, SHAPE_FULL
    if _open(x, y - 1):
        return material, RAMP_TOP_LEFT if left_open else RAMP_TOP_RIGHT
    if _open(x, y + 1):
        return material, RAMP_BOTTOM_LEFT if left_open else RAMP_BOTTOM_RIGHT
    return material, SHAPE_FULL


tile_at = generate_tile   # the world as generated, before any changes


CHUNK_SIZE = 8                              # tiles square
CHUNKS_ACROSS = WORLD_SIZE // CHUNK_SIZE    # 32
SLOT_COUNT = 255                            # changed chunks the host's store holds


class World:
    """The world with the player's changes, modelling the store of changed
    chunks: a directory of chunks, and SLOT_COUNT slots that hold them. The
    first change to a chunk copies its generated tiles into the next free
    slot; when none is free, the change is refused."""

    def __init__(self) -> None:
        self.directory: dict[int, int] = {}     # chunk index -> slot (1-based)
        self.slots: list[list[Tile]] = []

    @staticmethod
    def chunk_index(x: int, y: int) -> int:
        return (y // CHUNK_SIZE) * CHUNKS_ACROSS + x // CHUNK_SIZE

    def tile_at(self, x: int, y: int) -> Tile:
        slot = self.directory.get(self.chunk_index(x, y))
        if slot is None:
            return generate_tile(x, y)
        return self.slots[slot - 1][(y % CHUNK_SIZE) * CHUNK_SIZE + x % CHUNK_SIZE]

    def set_tile(self, x: int, y: int, tile: Tile) -> bool:
        index = self.chunk_index(x, y)
        slot = self.directory.get(index)
        if slot is None:
            if len(self.slots) == SLOT_COUNT:
                return False
            x0, y0 = x - x % CHUNK_SIZE, y - y % CHUNK_SIZE
            self.slots.append([
                generate_tile(x0 + i, y0 + j) for j in range(CHUNK_SIZE) for i in range(CHUNK_SIZE)
            ])
            slot = self.directory[index] = len(self.slots)
        self.slots[slot - 1][(y % CHUNK_SIZE) * CHUNK_SIZE + x % CHUNK_SIZE] = tile
        return True
