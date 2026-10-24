"""Daylight on the parasite (asm/daylight.asm) matches the model: whenever
its relighting is done and the queue sent, every tile in the tile cache has
the brighter of lighting.shaft_sun and the glow, from the world as the
parasite holds it, and each column's sky depth is right. The game runs in
py65 (a 65C02), the host played by a hook. Run with -s to see what the
parasite's frames cost."""

import numpy as np

from conftest import FakeHost
from mos6502 import Machine6502
from stratagem import lighting
from stratagem.build import read_disc_file
from stratagem.camera import INPUT_ACTION, INPUT_DOWN, INPUT_LEFT, INPUT_RIGHT, INPUT_UP
from stratagem.world import HEIGHTS

TILE_CACHE_SIZE = 32
SUN_DEPTH = 0xBD00              # asm/parasite.asm
MAILBOX_KEYS, MAILBOX_INPUT, MAILBOX_FRAME = 0x8D, 0x8E, 0x8F
PACKET_REDRAW, PACKET_PACK, PACKET_PACK_DRAW, PACKET_PACK_MOVED, PACKET_PACK_CHANGED = 0x80, 0x40, 0x20, 0x10, 0x08    # tube_layout.asm

KEYS = {"Z": INPUT_LEFT, "X": INPUT_RIGHT, "K": INPUT_UP, "M": INPUT_DOWN, "L": INPUT_ACTION}
# Down a shaft from the surface, along a tunnel, and back up the shaft.
SCRIPT = [(200, "ML"), (60, "XL"), (40, "ZL"), (30, ""), (60, "Z"), (60, "ZK"), (40, "X")]


class ParasiteGame:
    """The parasite's game in py65, the host playing only its part in the
    store of changed chunks (FakeHost), taken from each packet."""

    def __init__(self, game_build):
        self.machine = Machine6502(cmos=True)
        for name in ("PGAME", "PWORLD", "PLIGHT"):
            self.machine.load(*read_disc_file(game_build.disc_filepath, name))
        self.labels = game_build.labels["PARASITE"]
        self.mpu = self.machine.mpu
        self.memory = self.mpu.memory
        self.host = FakeHost(self.machine, self.labels)
        self.machine.hooks[self.labels["para_send"]] = self.take_packet
        self.mpu.pc = self.labels["pgame_start"]
        self.run_to(self.labels["para_loop"])

    def take_packet(self, mpu=None) -> None:
        """The host's part in the store, from a game's packet (not the
        pack's, which carries none)."""
        if not self.packet()[0] & PACKET_PACK:
            self.host.take_packet(mpu)

    def packet(self) -> list[int]:
        """The packet being sent (at para_send), from its start."""
        at = self.memory[self.labels["para_packet"]] | self.memory[self.labels["para_packet"] + 1] << 8
        return list(self.memory[at:at + 64])

    def run_to(self, address: int, max_steps: int = 5_000_000) -> None:
        for _ in range(max_steps):
            if self.mpu.pc == address:
                return
            self.machine.step()
        raise TimeoutError(f"&{address:04X} not reached")

    def frame(self, inputs: int) -> int:
        """Play a frame; returns its cycles, from taking the input to sending
        the packet."""
        labels = self.labels
        self.memory[MAILBOX_INPUT] = inputs
        self.memory[MAILBOX_FRAME] = self.memory[labels["para_sent"]]
        self.machine.step()
        self.run_to(labels["para_input"])
        before = self.mpu.processorCycles
        self.run_to(labels["para_send"])
        cycles = self.mpu.processorCycles - before
        self.run_to(labels["para_loop"])
        return cycles

    def call(self, name: str, a: int = 0, x: int = 0, y: int = 0) -> None:
        """Call a routine between frames, leaving the game as it was."""
        mpu = self.mpu
        saved = mpu.pc, mpu.sp, mpu.a, mpu.x, mpu.y, mpu.p, list(self.memory[0x100:0x200])
        self.machine.call(self.labels[name], a=a, x=x, y=y)
        mpu.pc, mpu.sp, mpu.a, mpu.x, mpu.y, mpu.p, stack = saved
        self.memory[0x100:0x200] = stack

    def byte(self, name: str) -> int:
        return self.memory[self.labels[name]]

    def tile_at(self, x: int, y: int):
        """The world as the parasite and the host hold it."""
        return self.host.tile_at(x, y)

    def cache_light(self, x: int, y: int) -> int:
        index = (y % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + x % TILE_CACHE_SIZE
        return self.memory[self.labels["tile_cache_light"] + index]


def check_daylight(game: ParasiteGame) -> tuple[int, int]:
    """Compare the cache's tiles with the model; returns how many are lit by
    sunlight beyond the glow, and how many of those are tapered (dimmed
    with depth below the surface)."""
    left, right = game.byte("cached_left"), game.byte("cached_right")
    top, bottom = game.byte("cached_top"), game.byte("cached_bottom")

    def clear_at(x, y):
        return lighting.transparent(game.tile_at(x, y))

    depth = [0] * 256
    for x in range(max(0, left - lighting.SHAFT_REACH), min(255, right + lighting.SHAFT_REACH) + 1):
        depth[x] = lighting.sky_depth(clear_at, x)
        assert game.memory[SUN_DEPTH + x] == depth[x], f"column {x}'s sky depth"
    beyond = tapered = 0
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            sun = lighting.shaft_sun(depth, clear_at(x, y), x, y, clear_above=y > 0 and clear_at(x, y - 1))
            day = max(sun, lighting.glow(x, y))
            assert game.cache_light(x, y) == day * lighting.LIGHT_SCALE, f"tile ({x}, {y}): light"
            beyond += sun > lighting.glow(x, y)
            tapered += sun > lighting.glow(x, y) and y - HEIGHTS[x] >= lighting.SHAFT_TAPER
    return beyond, tapered


def test_daylight_matches_the_model(game_build):
    game = ParasiteGame(game_build)
    cycles, checks, lit, tapered = [], 0, 0, 0
    for count, keys in SCRIPT:
        for _ in range(count):
            cycles.append(game.frame(sum(KEYS[k] for k in keys)))
            game.host.check_cache()
            idle = not game.byte("sun_busy") and game.byte("torch_queue_head") == game.byte("torch_queue_tail")
            if idle:
                beyond, deep = check_daylight(game)
                lit, tapered = max(lit, beyond), max(tapered, deep)
                checks += 1
    assert checks > 30
    assert lit > 0, "no sunlight beyond the glow: the shaft isn't lit"
    assert tapered > 0, "no sunlight deep enough down the shaft to be tapered"
    print(f"\nthe parasite's frames: mean {np.mean(cycles):.0f} cycles, max {max(cycles)}")
