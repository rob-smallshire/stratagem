"""The parasite's smooth miner's light (asm/smooth_light.asm) matches the
model: after every pass each block holds lighting.smooth_miner_light's level,
and exactly the cells whose change shows are queued. Run with -s to see what
a pass costs the 65C02."""

import random

import numpy as np
import pytest

from mos6502 import Machine6502
from stratagem import lighting
from stratagem.build import read_disc_file
from stratagem.glide_lab import walk
from stratagem.lighting_lab import mine_scene, open_up
from stratagem.tiles import tile_pixels

PLANE_COLUMNS, PLANE_ROWS, MAP_SIZE = 64, 64, 32        # asm/smooth_light.asm: blocks, cell rows, tiles
QUEUE_COLUMNS = 128         # the queue holds u MOD 128
CHECK_RADIUS = 7        # tiles around the miner whose cells are checked


class Parasite:
    def __init__(self, game_build, world):
        self.machine = Machine6502(cmos=True)
        self.machine.load(*read_disc_file(game_build.disc_filepath, "SMOOTH"))
        self.labels = game_build.labels["SMOOTH"]
        self.memory = self.machine.mpu.memory
        self.world = world
        self.kinds = {}

    def kind(self, tile) -> int:
        if tile not in self.kinds:
            kind = len(self.kinds)
            assert kind < 256
            self.kinds[tile] = kind
            self.memory[self.labels["sl_kind_clear"] + kind] = 0xFF if lighting.transparent(tile) else 0
            for cell, bits in enumerate(lighting.cell_visibility(tile_pixels(*tile))):
                self.memory[self.labels["sl_kind_visibility"] + cell * 256 + kind] = bits
        return self.kinds[tile]

    def fill_map(self, cx: int, cy: int) -> None:
        """The map around the miner's tile, as the parasite's world would hold it."""
        for ty in range(cy - MAP_SIZE // 2, cy + MAP_SIZE // 2):
            for tx in range(cx - MAP_SIZE // 2, cx + MAP_SIZE // 2):
                index = (ty % MAP_SIZE) * MAP_SIZE + tx % MAP_SIZE
                self.memory[self.labels["sl_map"] + index] = self.kind(self.world.tile_at(tx, ty))

    def update(self, px: int, py: int) -> int:
        """A pass with the miner at (px, py); returns its cycles."""
        for name, value in (("sl_px", px), ("sl_py", py)):
            self.memory[self.labels[name]] = value & 0xFF
            self.memory[self.labels[name] + 1] = value >> 8
        self.fill_map(*lighting.miner_tile(px, py))
        before = self.machine.mpu.processorCycles
        self.machine.call(self.labels["sl_update"], max_steps=1_000_000)
        return self.machine.mpu.processorCycles - before

    def level(self, u: int, v: int) -> int:
        return self.memory[self.labels["sl_plane"] + (v % PLANE_ROWS) * PLANE_COLUMNS + (u // 2) % PLANE_COLUMNS]

    def take_queue(self) -> list[tuple[int, int, int]]:
        count = self.memory[self.labels["sl_queue_count"]]
        queue = [tuple(self.memory[self.labels[name] + i] for name in ("sl_queue_u", "sl_queue_v", "sl_queue_level"))
                 for i in range(count)]
        self.memory[self.labels["sl_queue_count"]] = 0
        return queue


def check_moves(parasite: Parasite, moves: list[tuple[int, int]]) -> list[int]:
    world = parasite.world
    shown = {}          # cell -> level, as last drawn

    def clear_at(x, y):
        return lighting.transparent(world.tile_at(x, y))

    cycles = []
    for n, (px, py) in enumerate(moves):
        cycles.append(parasite.update(px, py))
        light = lighting.smooth_miner_light(clear_at, px, py, soft=True)
        cx, cy = lighting.miner_tile(px, py)
        cells = [(u, v) for v in range((cy - CHECK_RADIUS) * 2, (cy + CHECK_RADIUS + 1) * 2)
                 for u in range((cx - CHECK_RADIUS) * 4, (cx + CHECK_RADIUS + 1) * 4)]
        wrong = [(u, v) for u, v in cells if parasite.level(u, v) != light.get((u, v), 0)]
        assert wrong[:8] == [], f"move {n}: {len(wrong)} cells lit wrongly"
        expected = set()
        for u, v in cells:
            before, after = shown.get((u, v), 0), light.get((u, v), 0)
            visibility = lighting.cell_visibility(tile_pixels(*world.tile_at(u // 4, v // 2)))[(v % 2) * 4 + u % 4]
            if lighting.shows(visibility, before, after, u % 2):
                expected.add((u % QUEUE_COLUMNS, v & 0xFF, after))
            shown[(u, v)] = after
        queue = parasite.take_queue()
        assert len(queue) == len(set(queue)), f"move {n}: a cell queued twice"
        assert set(queue) == expected, f"move {n}"
    return cycles


def report(name: str, cycles: list[int]) -> None:
    moving = cycles[1:]         # the first pass lights the pool from nothing
    print(f"\n  {name}: 65C02 cycles a pass: mean {np.mean(moving):.0f}, max {max(moving)}; "
          f"first {cycles[0]} (a 3 MHz frame is 60,000)")


def test_smooth_light_while_walking(game_build):
    scene = mine_scene()
    parasite = Parasite(game_build, scene.world)
    moves = [(hero.px, hero.py) for hero in walk(scene)]
    report("walking", check_moves(parasite, moves))


@pytest.mark.parametrize("seed", range(3))
def test_smooth_light_in_random_ground(game_build, seed):
    rng = random.Random(seed)
    scene = mine_scene()
    world = scene.world
    x0, y0 = 120 + seed * 40, 70
    for ty in range(y0 - 12, y0 + 12):          # caves and walls at random
        for tx in range(x0 - 16, x0 + 16):
            if rng.random() < 0.5:
                open_up(world, tx, ty)
    parasite = Parasite(game_build, world)
    px, py = x0 * 8, y0 * 16
    moves = []
    for _ in range(60):             # walking, jumping and falling speeds
        px += rng.randint(-2, 2)
        py += rng.randint(-6, 6)
        moves.append((px, py))
    report(f"random ground {seed}", check_moves(parasite, moves))
