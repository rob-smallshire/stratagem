"""The 6502 digging and placing match the Python model, frame by frame, with
the player moving through a world that both change in step."""

import collections
import random

import pytest

from mos6502 import Machine6502
from stratagem import actions, player
from stratagem.actions import Hands
from stratagem.camera import INPUT_ACTION, INPUT_PLACE
from stratagem.build import read_disc_file
from stratagem.camera import INPUT_DOWN, INPUT_LEFT, INPUT_RIGHT, INPUT_UP
from stratagem.tiles import AIR, SHAPE_BITS, SHAPE_FULL
from stratagem.world import CHUNK_SIZE, HEIGHTS, RAMP_TOP_LEFT, RAMP_TOP_RIGHT, World
from test_player import TILE_CACHE_SIZE, PlayerHarness, _random_start

RTS = 0x60


@pytest.fixture
def machine(game_build):
    """STRAT, MAIN and WORLD in one flat memory. The renderer shares the
    world bank's addresses, so it is left out and redrawing does nothing."""
    machine = Machine6502()
    for name in ("STRAT", "MAIN", "WORLD"):
        machine.load(*read_disc_file(game_build.disc_filepath, name))
    labels = game_build.labels["STRATAGEM"]
    machine.mpu.memory[labels["call_render_row"]] = RTS
    machine.call(labels["world_reset"])
    return machine


def assert_tile_matches(machine, labels, world, target) -> None:
    """The tile a dig or place left, in the 6502's world and the tile cache,
    is the model's."""
    x, y = target
    mpu = machine.call(labels["tile_at"], x=x, y=y).mpu
    assert (mpu.a, mpu.memory[labels["zp_world_shape"]]) == world.tile_at(x, y), f"the tile at {target}"
    index = (y % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + x % TILE_CACHE_SIZE
    cached = (mpu.memory[labels["tile_cache"] + index], mpu.memory[labels["tile_cache_shapes"] + index])
    assert cached == world.tile_at(x, y), f"the cached tile at {target}"


INPUTS = [
    INPUT_ACTION, INPUT_ACTION | INPUT_DOWN, INPUT_ACTION | INPUT_UP, INPUT_ACTION | INPUT_RIGHT,
    INPUT_ACTION | INPUT_LEFT,
    INPUT_ACTION | INPUT_LEFT | INPUT_DOWN, INPUT_ACTION | INPUT_RIGHT | INPUT_DOWN,
    INPUT_ACTION | INPUT_LEFT | INPUT_UP, INPUT_ACTION | INPUT_RIGHT | INPUT_UP,
    INPUT_ACTION | INPUT_LEFT | INPUT_DOWN, INPUT_ACTION | INPUT_RIGHT | INPUT_UP, INPUT_PLACE, INPUT_PLACE | INPUT_UP, INPUT_PLACE | INPUT_DOWN,
    INPUT_PLACE | INPUT_LEFT, INPUT_RIGHT, INPUT_LEFT, INPUT_UP, INPUT_RIGHT | INPUT_UP, 0,
]


def test_actions_match_model(machine, game_build):
    labels = game_build.labels["STRATAGEM"]
    harness = PlayerHarness(machine, labels)
    memory = machine.mpu.memory
    rng = random.Random(1990)
    world = World()
    hands = Hands()
    done = {actions.DIG: 0, actions.PLACE: 0}
    partial_seen = set()
    ramps = 0
    for episode in range(60):
        state = _random_start(rng, world)
        inputs = 0
        cached_at = None
        for _ in range(150):
            if rng.random() < 0.04:
                inputs = rng.choice(INPUTS)
            here = (state.px // 8, state.py // 16)
            if cached_at is None or abs(here[0] - cached_at[0]) > 4 or abs(here[1] - cached_at[1]) > 4:
                harness.fill_cache(world, *here)
                cached_at = here
            harness.write(state, inputs)
            memory[labels["inventory"]] = hands.inventory
            memory[labels["cooldown"]] = hands.cooldown
            machine.call(labels["update_player"])
            machine.call(labels["player_action"])
            actual, _, _, _ = harness.read()
            expected = player.step(state, inputs, world.tile_at)
            assert actual == expected, f"from {state} with inputs {inputs}"
            hands, action, target = actions.act(hands, expected, inputs, world)
            assert (memory[labels["inventory"]], memory[labels["cooldown"]]) == (hands.inventory, hands.cooldown)
            assert memory[labels["action"]] == action, f"at {expected} with inputs {inputs}"
            if target is not None:
                assert (memory[labels["target_x"]], memory[labels["target_y"]]) == target
                assert_tile_matches(machine, labels, world, target)
                done[action] += 1
                partial_seen.add(world.tile_at(*target))
                if world.tile_at(*target)[1] & SHAPE_BITS in (RAMP_TOP_LEFT, RAMP_TOP_RIGHT):
                    ramps += 1
            state = expected
    assert done[actions.DIG] > 50 and done[actions.PLACE] > 20, done
    assert any(shape & SHAPE_BITS != SHAPE_FULL for _, shape in partial_seen), "no tile was ever partly dug"
    assert ramps > 10, "diagonal digging hardly ever shaped a ramp"
    # The 6502 world agrees with the model everywhere it was changed.
    for index in world.directory:
        x0, y0 = index % 32 * CHUNK_SIZE, index // 32 * CHUNK_SIZE
        for y in range(y0, y0 + CHUNK_SIZE):
            for x in range(x0, x0 + CHUNK_SIZE):
                mpu = machine.call(labels["tile_at"], x=x, y=y).mpu
                assert (mpu.a, memory[labels["zp_world_shape"]]) == world.tile_at(x, y), (x, y)


@pytest.mark.parametrize("keys", [INPUT_LEFT | INPUT_DOWN, INPUT_RIGHT | INPUT_DOWN,
                                  INPUT_LEFT | INPUT_UP, INPUT_RIGHT | INPUT_UP],
                         ids=["down-left", "down-right", "up-left", "up-right"])
def test_long_diagonal_tunnels_match_model(machine, game_build, keys):
    """Holding a diagonal dig for a long time, from places on the surface
    (slopes included) and underground, the 6502 tunnels exactly as the model
    does, frame by frame."""
    labels = game_build.labels["STRATAGEM"]
    harness = PlayerHarness(machine, labels)
    memory = machine.mpu.memory
    keys |= INPUT_ACTION
    world = World()
    hands = Hands()
    digs = 0
    for x in (40, 75, 128, 170, 210):
        for depth in (0, 20):
            floor = HEIGHTS[x] + depth
            if depth:
                for dy in range(-3, 0):
                    for dx in range(-1, 2):
                        world.set_tile(x + dx, floor + dy, (0, 0))
            state = player.Player(x=(x * 8 + 1) * 16, y=(floor * 16 - 24) * 16)
            cached_at = None
            for _ in range(400):
                here = (state.px // 8, state.py // 16)
                if cached_at is None or abs(here[0] - cached_at[0]) > 4 or abs(here[1] - cached_at[1]) > 4:
                    harness.fill_cache(world, *here)
                    cached_at = here
                harness.write(state, keys)
                memory[labels["inventory"]] = hands.inventory
                memory[labels["cooldown"]] = hands.cooldown
                machine.call(labels["update_player"])
                machine.call(labels["player_action"])
                actual, _, _, _ = harness.read()
                expected = player.step(state, keys, world.tile_at)
                assert actual == expected, f"from {state}"
                hands, action, target = actions.act(hands, expected, keys, world)
                assert memory[labels["action"]] == action
                if target is not None:
                    assert (memory[labels["target_x"]], memory[labels["target_y"]]) == target
                    assert_tile_matches(machine, labels, world, target)
                    digs += 1
                state = expected
    assert digs > 100


@pytest.mark.parametrize("keys", [INPUT_LEFT | INPUT_DOWN, INPUT_RIGHT | INPUT_DOWN,
                                  INPUT_LEFT | INPUT_UP, INPUT_RIGHT | INPUT_UP],
                         ids=["down-left", "down-right", "up-left", "up-right"])
def test_diagonal_digs_in_random_ground_match_model(machine, game_build, keys):
    """A single diagonal dig, from thousands of random places in random
    ground (every material and shape near the player), chooses and leaves
    exactly what the model does: every case of the choice, not only those a
    tunnel meets."""
    from stratagem.tiles import MATERIAL_COUNT, PASSABLE, SHAPE_COUNT, BACKGROUND_SKY
    labels = game_build.labels["STRATAGEM"]
    harness = PlayerHarness(machine, labels)
    memory = machine.mpu.memory
    keys |= INPUT_ACTION
    rng = random.Random(keys)
    sides = collections.Counter()
    for trial in range(500):
        world = World()
        machine.call(labels["world_reset"])
        tx0, ty0 = rng.randrange(20, 236), rng.randrange(60, 230)
        for tx in range(tx0 - 3, tx0 + 4):
            for ty in range(ty0 - 3, ty0 + 4):
                material = rng.randrange(MATERIAL_COUNT)
                shape = 0 if material in PASSABLE else rng.choice([0, 0, rng.randrange(SHAPE_COUNT)])
                tile = (material, shape | rng.choice([0, BACKGROUND_SKY]))
                world.set_tile(tx, ty, tile)
                memory[labels["zp_world_new_shape"]] = tile[1]
                machine.call(labels["set_tile"], a=tile[0], x=tx, y=ty)
        px, py = tx0 * 8 + rng.randrange(8), ty0 * 16 + rng.randrange(16)
        # Clear whatever the player would overlap.
        for tx in range(px // 8, (px + 5) // 8 + 1):
            for ty in range(py // 16, (py + 23) // 16 + 1):
                if player.hits(world.tile_at, px, py):
                    world.set_tile(tx, ty, (AIR, SHAPE_FULL))
                    memory[labels["zp_world_new_shape"]] = SHAPE_FULL
                    machine.call(labels["set_tile"], a=AIR, x=tx, y=ty)
        if player.hits(world.tile_at, px, py):
            continue
        state = player.Player(x=px * 16 + rng.randrange(16), y=py * 16, on_ground=rng.random() < 0.7,
                              facing=1 if keys & INPUT_RIGHT else -1)
        harness.fill_cache(world, tx0, ty0)
        harness.write(state, keys)
        hands = Hands(inventory=rng.randrange(5))
        memory[labels["inventory"]] = hands.inventory
        memory[labels["cooldown"]] = 0
        machine.call(labels["player_action"])
        dx = 1 if keys & INPUT_RIGHT else -1
        target, ramp = actions.diagonal(state, dx, 1 if keys & INPUT_DOWN else -1, world.tile_at)
        if target and ramp is None:
            sides[actions.near_side(state, target, dx)] += 1
        hands, action, target = actions.act(hands, state, keys, world)
        assert memory[labels["action"]] == action, f"trial {trial}: {state}"
        assert memory[labels["inventory"]] == hands.inventory
        if target is not None:
            assert (memory[labels["target_x"]], memory[labels["target_y"]]) == target, f"trial {trial}: {state}"
            assert_tile_matches(machine, labels, world, target)
    assert len(sides) >= 2, sides
