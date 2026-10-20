"""Daylight on the parasite (asm/daylight.asm) matches the model: whenever
its relighting is done and the queue sent, every tile in the tile cache has
the brighter of lighting.shaft_sun and the glow, from the world as the
parasite holds it, and each column's sky depth is right. The game runs in
py65 (a 65C02), the host played by a hook. Run with -s to see what the
parasite's frames cost."""

import numpy as np

from mos6502 import Machine6502
from stratagem import lighting
from stratagem.build import read_disc_file
from stratagem.camera import INPUT_ACTION, INPUT_DOWN, INPUT_LEFT, INPUT_RIGHT, INPUT_UP
from stratagem.world import CHUNK_SIZE, CHUNKS_ACROSS, generate_tile

TILE_CACHE_SIZE = 32
SUN_DEPTH = 0xBD00              # asm/parasite.asm
SLOT_BYTES = 2 * CHUNK_SIZE * CHUNK_SIZE
OSWRCH = 0xFFEE
MAILBOX_INPUT, MAILBOX_FRAME = 0x8E, 0x8F

KEYS = {"Z": INPUT_LEFT, "X": INPUT_RIGHT, "K": INPUT_UP, "M": INPUT_DOWN, "L": INPUT_ACTION}
# Down a shaft from the surface, along a tunnel, and back up the shaft.
SCRIPT = [(200, "ML"), (60, "XL"), (40, "ZL"), (30, ""), (60, "Z"), (60, "ZK"), (40, "X")]


class ParasiteGame:
    def __init__(self, game_build):
        self.machine = Machine6502(cmos=True)
        for name in ("PGAME", "PWORLD", "PLIGHT"):
            self.machine.load(*read_disc_file(game_build.tube_disc_filepath, name))
        self.labels = game_build.labels["PARASITE"]
        self.mpu = self.machine.mpu
        self.memory = self.mpu.memory
        self.memory[OSWRCH] = 0x60      # RTS: the host reads nothing
        self.mpu.pc = self.labels["pgame_start"]
        self.run_to(self.labels["para_loop"])

    def run_to(self, address: int, max_steps: int = 5_000_000) -> None:
        for _ in range(max_steps):
            if self.mpu.pc == address:
                return
            self.mpu.step()
        raise TimeoutError(f"&{address:04X} not reached")

    def frame(self, inputs: int) -> int:
        """Play a frame; returns its cycles, from taking the input to sending
        the packet."""
        labels = self.labels
        self.memory[MAILBOX_INPUT] = inputs
        self.memory[MAILBOX_FRAME] = self.memory[labels["para_sent"]]
        self.mpu.step()
        self.run_to(labels["para_input"])
        before = self.mpu.processorCycles
        self.run_to(labels["para_send"])
        cycles = self.mpu.processorCycles - before
        self.run_to(labels["para_loop"])
        return cycles

    def byte(self, name: str) -> int:
        return self.memory[self.labels[name]]

    def tile_at(self, x: int, y: int):
        """The world as the parasite holds it."""
        index = (y // CHUNK_SIZE) * CHUNKS_ACROSS + x // CHUNK_SIZE
        slot = self.memory[self.labels["world_directory"] + index]
        if not slot:
            return generate_tile(x, y)
        base = self.labels["world_slots"] + (slot - 1) * SLOT_BYTES
        offset = (y % CHUNK_SIZE) * CHUNK_SIZE + x % CHUNK_SIZE
        return self.memory[base + offset], self.memory[base + SLOT_BYTES // 2 + offset]

    def cache_light(self, x: int, y: int) -> int:
        index = (y % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + x % TILE_CACHE_SIZE
        return self.memory[self.labels["tile_cache_light"] + index]


def check_daylight(game: ParasiteGame) -> int:
    """Compare the cache's tiles with the model; returns how many are lit by
    sunlight beyond the glow."""
    left, right = game.byte("cached_left"), game.byte("cached_right")
    top, bottom = game.byte("cached_top"), game.byte("cached_bottom")

    def clear_at(x, y):
        return lighting.transparent(game.tile_at(x, y))

    depth = [0] * 256
    for x in range(max(0, left - lighting.SHAFT_REACH), min(255, right + lighting.SHAFT_REACH) + 1):
        depth[x] = lighting.sky_depth(clear_at, x)
        assert game.memory[SUN_DEPTH + x] == depth[x], f"column {x}'s sky depth"
    beyond = 0
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            sun = lighting.shaft_sun(depth, clear_at(x, y), x, y, clear_above=y > 0 and clear_at(x, y - 1))
            day = max(sun, lighting.glow(x, y))
            assert game.cache_light(x, y) == day * lighting.LIGHT_SCALE, f"tile ({x}, {y}): light"
            beyond += sun > lighting.glow(x, y)
    return beyond


def test_daylight_matches_the_model(game_build):
    game = ParasiteGame(game_build)
    cycles, checks, lit = [], 0, 0
    for count, keys in SCRIPT:
        for _ in range(count):
            cycles.append(game.frame(sum(KEYS[k] for k in keys)))
            idle = not game.byte("sun_busy") and game.byte("torch_queue_head") == game.byte("torch_queue_tail")
            if idle:
                lit = max(lit, check_daylight(game))
                checks += 1
    assert checks > 30
    assert lit > 0, "no sunlight beyond the glow: the shaft isn't lit"
    print(f"\nthe parasite's frames: mean {np.mean(cycles):.0f} cycles, max {max(cycles)}")
