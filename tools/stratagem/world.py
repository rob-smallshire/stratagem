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


def generate_tile(x: int, y: int) -> int:
    """The tile the generator puts at (x, y): the world before any changes."""
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


tile_at = generate_tile   # the world as generated, before any changes


CHUNK_SIZE = 8                              # tiles square
CHUNKS_ACROSS = WORLD_SIZE // CHUNK_SIZE    # 32
SLOT_COUNT = 208                            # changed chunks the world bank holds


class World:
    """The world with the player's changes, modelling the world bank: a
    directory of chunks, and SLOT_COUNT slots that hold changed chunks. The
    first change to a chunk copies its generated tiles into the next free
    slot; when none is free, the change is refused."""

    def __init__(self) -> None:
        self.directory: dict[int, int] = {}     # chunk index -> slot (1-based)
        self.slots: list[bytearray] = []

    @staticmethod
    def chunk_index(x: int, y: int) -> int:
        return (y // CHUNK_SIZE) * CHUNKS_ACROSS + x // CHUNK_SIZE

    def tile_at(self, x: int, y: int) -> int:
        slot = self.directory.get(self.chunk_index(x, y))
        if slot is None:
            return generate_tile(x, y)
        return self.slots[slot - 1][(y % CHUNK_SIZE) * CHUNK_SIZE + x % CHUNK_SIZE]

    def set_tile(self, x: int, y: int, tile: int) -> bool:
        index = self.chunk_index(x, y)
        slot = self.directory.get(index)
        if slot is None:
            if len(self.slots) == SLOT_COUNT:
                return False
            x0, y0 = x - x % CHUNK_SIZE, y - y % CHUNK_SIZE
            self.slots.append(bytearray(
                generate_tile(x0 + i, y0 + j) for j in range(CHUNK_SIZE) for i in range(CHUNK_SIZE)
            ))
            slot = self.directory[index] = len(self.slots)
        self.slots[slot - 1][(y % CHUNK_SIZE) * CHUNK_SIZE + x % CHUNK_SIZE] = tile
        return True
