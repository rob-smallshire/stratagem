"""The 6502 player movement matches the Python model, frame by frame."""

import random

import pytest

from mos6502 import Machine6502
from stratagem import player, sprites
from stratagem.build import read_disc_file
from stratagem.camera import INPUT_LEFT, INPUT_RIGHT, INPUT_UP
from stratagem.player import Player
from stratagem.tiles import AIR, BACKGROUND_SKY, DIGGABLE, SHAPE_COUNT, SHAPE_FULL, SOIL, STONE
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
        materials, shapes = self.labels["tile_cache"], self.labels["tile_cache_shapes"]
        for ty in range(centre_ty - 15, centre_ty + 17):
            for tx in range(centre_tx - 15, centre_tx + 17):
                material, shape = world.tile_at(tx, ty) if 0 <= tx < 256 and 0 <= ty < 256 else (STONE, SHAPE_FULL)
                index = (ty % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + tx % TILE_CACHE_SIZE
                self.memory[materials + index] = material
                self.memory[shapes + index] = shape

    def write(self, state: Player, inputs: int, abilities: int = player.STARTING_ABILITIES) -> None:
        m, l = self.memory, self.labels
        m[l["zp_input"]] = inputs
        m[l["zp_abilities"]] = abilities
        m[l["zp_player_jump_held"]] = 0xFF if state.jump_held else 0
        m[l["zp_player_air_jumps"]] = state.air_jumps
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
            jump_held=m[l["zp_player_jump_held"]] != 0, air_jumps=m[l["zp_player_air_jumps"]],
        )
        return state, (word("zp_focus_x"), word("zp_focus_y")), m[l["zp_player_frame"]], _signed(m[l["zp_direction"]])

    def step(self, state: Player, inputs: int, abilities: int = player.STARTING_ABILITIES):
        self.write(state, inputs, abilities)
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
            return Player(x=px * 16 + rng.randrange(16), y=py * 16, facing=rng.choice([-1, 1]),
                          air_jumps=rng.randrange(2), jump_held=rng.random() < 0.5)


def _random_tile(rng: random.Random) -> tuple[int, int]:
    """Mostly air or soil; often a shaped diggable tile."""
    choice = rng.random()
    if choice < 0.4:
        return AIR, SHAPE_FULL
    if choice < 0.6:
        return SOIL, SHAPE_FULL
    return rng.choice(DIGGABLE), rng.randrange(1, SHAPE_COUNT) | rng.choice([0, BACKGROUND_SKY])


def test_player_matches_model(main_machine, game_build):
    harness = PlayerHarness(main_machine, game_build.labels["STRATAGEM"])
    rng = random.Random(1989)
    world = World()
    frames = 0
    seen = {"climbed a ledge": 0, "jumped in the air": 0, "stopped on a shaped tile": 0, "followed the ground down": 0}
    for episode in range(120):
        state = _random_start(rng, world)
        abilities = rng.choice([0, player.ABILITY_DOUBLE_JUMP])
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
                    world.set_tile(tx, ty, _random_tile(rng))
                    if player.box_free(world.tile_at, state.px, state.py) is False:
                        world.set_tile(tx, ty, (AIR, SHAPE_FULL))
                    cached_at = None
            here = (state.px // 8, state.py // 16)
            if cached_at is None or abs(here[0] - cached_at[0]) > 4 or abs(here[1] - cached_at[1]) > 4:
                harness.fill_cache(world, *here)
                cached_at = here
            actual, focus, frame, direction = harness.step(state, inputs, abilities)
            expected = player.step(state, inputs, world.tile_at, abilities)
            assert actual == expected, f"from {state} with inputs {inputs}"
            assert focus == player.focus(expected)
            assert frame == sprites.frame_for(expected)
            assert direction == (1 if inputs & INPUT_RIGHT else 0) - (1 if inputs & INPUT_LEFT else 0)
            if expected.y < state.y and state.on_ground and expected.vy >= 0 and expected.vx:
                seen["climbed a ledge"] += 1
            if not state.on_ground and expected.air_jumps < state.air_jumps:
                seen["jumped in the air"] += 1
            if expected.on_ground and (expected.py + player.PLAYER_HEIGHT) % player.TILE_HEIGHT:
                seen["stopped on a shaped tile"] += 1
            if state.on_ground and expected.on_ground and expected.py > state.py:
                seen["followed the ground down"] += 1
            state = expected
            frames += 1
    assert frames == 18_000
    assert all(count > 5 for count in seen.values()), seen
