"""The chunk lab: how small changed chunks could be stored.

    uv run strat-chunk-lab [FRAMES]

Plays the Python models (player.step, actions.act) for long sessions of
digging, tunnelling and placing, with the world store unlimited, then
encodes every changed chunk several ways against the tiles the generator
makes, and reports what each would hold in the world bank's 13K
(SLOT_COUNT chunks of 128 bytes today).

Encodings (bytes per chunk):

    raw         the chunk as stored now: 64 materials, 64 shapes
    bitmap      8 bytes saying which tiles differ from the generator's, then
                2 bytes for each that does
    short       as bitmap, but a tile dug out (open, with its own
                background) is 1 byte, and so is a tile of its generated
                material in a new shape (partly dug)
    maps        8 bytes saying which tiles differ, 8 saying which of those
                are dug out; then 1 byte for each partly dug, 2 for others

Any of them falls back to raw when that is smaller (a flag in the
directory, say). Sessions of random mining are followed by a quarry: a
room 24 tiles wide and 16 high dug out whole, the dense case.

Variable-length chunks can't sit in fixed slots, so each is also rounded up
to 16-byte granules, as a simple allocator would store them.
"""

from __future__ import annotations

import random
import sys
from collections import Counter

import numpy as np

from stratagem import actions, player, world
from stratagem.actions import Hands
from stratagem.camera import INPUT_ACTION, INPUT_DOWN, INPUT_LEFT, INPUT_PLACE, INPUT_RIGHT, INPUT_UP
from stratagem.tiles import AIR, SHAPE_BITS, SHAPE_FULL, SKY
from stratagem.world import CHUNK_SIZE, CHUNKS_ACROSS, HEIGHTS, World, background_bits, generate_tile

RAW_BYTES = 2 * CHUNK_SIZE * CHUNK_SIZE
STORE_BYTES = world.SLOT_COUNT * RAW_BYTES
BITMAP_BYTES = CHUNK_SIZE * CHUNK_SIZE // 8
GRANULE = 16

L, R, U, D, DIG, PLACE = INPUT_LEFT, INPUT_RIGHT, INPUT_UP, INPUT_DOWN, INPUT_ACTION, INPUT_PLACE
# What a miner does, a while at a time: (weight, inputs, frames).
MOVES = [
    (4, DIG | D, 120),              # a shaft
    (6, DIG | R, 160),              # tunnels
    (6, DIG | L, 160),
    (3, DIG | R | D, 120),          # diagonal tunnels
    (3, DIG | L | D, 120),
    (2, DIG | R | U, 100),
    (2, DIG | L | U, 100),
    (2, DIG | U, 60),
    (3, R, 60),                     # walking about, jumping
    (3, L, 60),
    (2, R | U, 40),
    (2, L | U, 40),
    (2, PLACE | D, 30),             # building
    (1, PLACE | R, 30),
    (1, PLACE | L, 30),
]


class UnlimitedWorld(World):
    """The world store with no limit on changed chunks."""

    def set_tile(self, x, y, tile):
        index = self.chunk_index(x, y)
        if index not in self.directory:
            x0, y0 = x - x % CHUNK_SIZE, y - y % CHUNK_SIZE
            self.slots.append([generate_tile(x0 + i, y0 + j) for j in range(CHUNK_SIZE) for i in range(CHUNK_SIZE)])
            self.directory[index] = len(self.slots)
        self.slots[self.directory[index] - 1][(y % CHUNK_SIZE) * CHUNK_SIZE + x % CHUNK_SIZE] = tile
        return True


def play(seed: int, frames: int) -> UnlimitedWorld:
    rng = random.Random(seed)
    w = UnlimitedWorld()
    start_px = 128 * player.TILE_WIDTH + 1
    start_py = HEIGHTS[128] * player.TILE_HEIGHT - player.PLAYER_HEIGHT
    hero = player.Player(x=start_px * player.SUBPIXELS, y=start_py * player.SUBPIXELS)
    hands = Hands(inventory=20)
    weights = [m[0] for m in MOVES]
    left = 0
    for _ in range(frames):
        if left == 0:
            _, inputs, length = rng.choices(MOVES, weights)[0]
            left = rng.randrange(length // 2, length + 1)
        left -= 1
        hero = player.step(hero, inputs, w.tile_at)
        hands, _, _ = actions.act(hands, hero, inputs, w)
    return w


def chunk_tiles(w: World, index: int) -> list[tuple[tuple[int, int], tuple[int, int], int, int]]:
    """Each tile of a stored chunk: (stored, generated, x, y)."""
    x0, y0 = index % CHUNKS_ACROSS * CHUNK_SIZE, index // CHUNKS_ACROSS * CHUNK_SIZE
    stored = w.slots[w.directory[index] - 1]
    return [(stored[j * CHUNK_SIZE + i], generate_tile(x0 + i, y0 + j), x0 + i, y0 + j)
            for j in range(CHUNK_SIZE) for i in range(CHUNK_SIZE)]


def dug_out(tile, x, y) -> bool:
    material, shape = tile
    return material in (AIR, SKY) and shape == SHAPE_FULL | background_bits(x, y)


def reshaped(tile, generated, x, y) -> bool:
    return tile[0] == generated[0] and tile[1] & ~SHAPE_BITS == background_bits(x, y)


def encodings(tiles) -> dict[str, int]:
    changed = [(t, g, x, y) for t, g, x, y in tiles if t != g]
    short = sum(1 if dug_out(t, x, y) or reshaped(t, g, x, y) else 2 for t, g, x, y in changed)
    dug = sum(dug_out(t, x, y) for t, g, x, y in changed)
    partly = sum(not dug_out(t, x, y) and reshaped(t, g, x, y) for t, g, x, y in changed)
    maps = 2 * BITMAP_BYTES + partly + 2 * (len(changed) - dug - partly)
    sizes = {"bitmap": BITMAP_BYTES + 2 * len(changed), "short": BITMAP_BYTES + short, "maps": maps}
    return {"raw": RAW_BYTES} | {name: min(size, RAW_BYTES) for name, size in sizes.items()}


def quarry() -> UnlimitedWorld:
    """A room dug out whole, below the surface at the start."""
    w = UnlimitedWorld()
    top = HEIGHTS[128] + 6
    for y in range(top, top + 16):
        for x in range(120, 144):
            w.set_tile(x, y, (AIR, SHAPE_FULL | background_bits(x, y)))
    return w


def granules(size: int) -> int:
    return -(-size // GRANULE) * GRANULE


def report(worlds: list[tuple[str, World]]) -> None:
    sizes: dict[str, list[int]] = {"raw": [], "bitmap": [], "short": [], "maps": []}
    changed_counts, kinds = [], Counter()
    for label, w in worlds:
        for index in w.directory:
            tiles = chunk_tiles(w, index)
            for name, size in encodings(tiles).items():
                sizes[name].append(size)
            changed = [(t, g, x, y) for t, g, x, y in tiles if t != g]
            changed_counts.append(len(changed))
            for t, g, x, y in changed:
                kinds["dug out" if dug_out(t, x, y) else "partly dug" if reshaped(t, g, x, y) else "other"] += 1
        print(f"{label}: {len(w.directory)} chunks changed")

    print(f"\n{len(changed_counts)} chunks; tiles changed per chunk: mean {np.mean(changed_counts):.1f}, "
          f"median {np.median(changed_counts):.0f}, max {max(changed_counts)}")
    total = sum(kinds.values())
    print("changed tiles: " + ", ".join(f"{k} {100 * v / total:.0f}%" for k, v in kinds.most_common()))
    print(f"\n{'encoding':8} {'mean':>6} {'median':>6} {'max':>4}  {'mean in granules':>16}  {'chunks in 13K':>13}")
    for name, values in sizes.items():
        rounded = [granules(v) for v in values]
        fit = STORE_BYTES / np.mean(rounded)
        print(f"{name:8} {np.mean(values):6.1f} {np.median(values):6.0f} {max(values):4}  "
              f"{np.mean(rounded):16.1f}  {fit:13.0f}")


def main() -> None:
    frames = int(sys.argv[1]) if len(sys.argv) > 1 else 20_000
    report([(f"mining, session {seed}, {frames} frames", play(1990 + seed, frames)) for seed in range(5)])
    print()
    report([("a quarry", quarry())])


if __name__ == "__main__":
    main()
