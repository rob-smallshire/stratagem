"""The 6502 player movement matches the Python model, frame by frame."""

import random

import pytest

from mos6502 import Machine6502
from stratagem import player, sprites
from stratagem.build import read_disc_file
from stratagem.camera import INPUT_LEFT, INPUT_RIGHT, INPUT_UP
from stratagem.player import Player
from stratagem.tiles import AIR, SOIL, STONE
from stratagem.world import HEIGHTS, World

TILE_CACHE_SIZE = 32       # asm/layout.asm


@pytest.fixture(scope="module")
def main_machine(game_build):
    load_address, data = read_disc_file(game_build.disc_filepath, "MAIN")
    machine = Machine6502()
    machine.load(load_address, data)
    return machine


def _signed(byte: int) -> int:
    return byte - 256 if byte & 0x80 else byte


class PlayerHarness:
    def __init__(self, machine: Machine6502, labels: dict[str, int]):
        self.machine, self.labels = machine, labels
        self.memory = machine.mpu.memory

    def fill_cache(self, world: World, centre_tx: int, centre_ty: int) -> None:
        """Fill the 32 x 32 tile cache ring with the world around a tile."""
        base = self.labels["tile_cache"]
        for ty in range(centre_ty - 15, centre_ty + 17):
            for tx in range(centre_tx - 15, centre_tx + 17):
                tile = world.tile_at(tx, ty) if 0 <= tx < 256 and 0 <= ty < 256 else STONE
                self.memory[base + (ty % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + tx % TILE_CACHE_SIZE] = tile

    def write(self, state: Player, inputs: int) -> None:
        m, l = self.memory, self.labels
        m[l["zp_input"]] = inputs
        m[l["zp_player_x"]], m[l["zp_player_x"] + 1] = state.x & 0xFF, state.x >> 8
        m[l["zp_player_y"]], m[l["zp_player_y"] + 1] = state.y & 0xFF, state.y >> 8
        m[l["zp_player_vx"]] = state.vx & 0xFF
        m[l["zp_player_vy"]] = state.vy & 0xFF
        m[l["zp_player_on_ground"]] = 0xFF if state.on_ground else 0
        m[l["zp_player_facing"]] = state.facing & 0xFF

    def read(self) -> tuple[Player, tuple[int, int], int, int]:
        m, l = self.memory, self.labels

        def word(name):
            return m[l[name]] | m[l[name] + 1] << 8

        state = Player(
            x=word("zp_player_x"), y=word("zp_player_y"),
            vx=_signed(m[l["zp_player_vx"]]), vy=_signed(m[l["zp_player_vy"]]),
            on_ground=m[l["zp_player_on_ground"]] != 0, facing=_signed(m[l["zp_player_facing"]]),
        )
        return state, (word("zp_focus_x"), word("zp_focus_y")), m[l["zp_player_frame"]], _signed(m[l["zp_direction"]])

    def step(self, state: Player, inputs: int):
        self.write(state, inputs)
        self.machine.call(self.labels["update_player"])
        return self.read()


def _random_start(rng: random.Random, world: World) -> Player:
    while True:
        tx = rng.randrange(4, 252)
        if rng.random() < 0.6:
            py = HEIGHTS[tx] * player.TILE_HEIGHT - player.PLAYER_HEIGHT - rng.randrange(40)
        else:
            py = rng.randrange(HEIGHTS[tx] * player.TILE_HEIGHT, 250 * player.TILE_HEIGHT)
        px = tx * player.TILE_WIDTH + rng.randrange(player.TILE_WIDTH)
        if py >= 0 and player.box_free(world.tile_at, px, py):
            return Player(x=px * 16 + rng.randrange(16), y=py * 16, facing=rng.choice([-1, 1]))


def test_player_matches_model(main_machine, game_build):
    harness = PlayerHarness(main_machine, game_build.labels["STRATAGEM"])
    rng = random.Random(1989)
    world = World()
    frames = 0
    for episode in range(120):
        state = _random_start(rng, world)
        inputs = 0
        cached_at = None
        for _ in range(150):
            if rng.random() < 0.1:
                inputs = rng.choice([0, INPUT_LEFT, INPUT_RIGHT, INPUT_UP, INPUT_LEFT | INPUT_UP,
                                     INPUT_RIGHT | INPUT_UP, INPUT_LEFT | INPUT_RIGHT])
            if rng.random() < 0.05:
                # Dig or build next to the player, to vary the terrain.
                tx = state.px // 8 + rng.choice([-2, -1, 1, 2])
                ty = state.py // 16 + rng.randrange(-1, 3)
                if 0 < tx < 255 and 0 <= ty < 255:
                    world.set_tile(tx, ty, rng.choice([AIR, AIR, SOIL]))
                    if player.box_free(world.tile_at, state.px, state.py) is False:
                        world.set_tile(tx, ty, AIR)
                    cached_at = None
            here = (state.px // 8, state.py // 16)
            if cached_at is None or abs(here[0] - cached_at[0]) > 4 or abs(here[1] - cached_at[1]) > 4:
                harness.fill_cache(world, *here)
                cached_at = here
            actual, focus, frame, direction = harness.step(state, inputs)
            expected = player.step(state, inputs, world.tile_at)
            assert actual == expected, f"from {state} with inputs {inputs}"
            assert focus == player.focus(expected)
            assert frame == sprites.frame_for(expected)
            assert direction == (1 if inputs & INPUT_RIGHT else 0) - (1 if inputs & INPUT_LEFT else 0)
            state = expected
            frames += 1
    assert frames == 18_000
