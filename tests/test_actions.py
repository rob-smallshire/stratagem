"""The 6502 digging and placing match the Python model, frame by frame, with
the player moving through a world that both change in step."""

import random

import pytest

from mos6502 import Machine6502
from stratagem import actions, player
from stratagem.actions import INPUT_ACTION, INPUT_PLACE, Hands
from stratagem.build import read_disc_file
from stratagem.camera import INPUT_DOWN, INPUT_LEFT, INPUT_RIGHT, INPUT_UP
from stratagem.tiles import PARTIAL_BASE
from stratagem.world import CHUNK_SIZE, World
from test_player import PlayerHarness, _random_start

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


INPUTS = [
    INPUT_ACTION, INPUT_ACTION | INPUT_DOWN, INPUT_ACTION | INPUT_UP, INPUT_ACTION | INPUT_RIGHT,
    INPUT_ACTION | INPUT_LEFT, INPUT_PLACE, INPUT_PLACE | INPUT_UP, INPUT_PLACE | INPUT_DOWN,
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
    for episode in range(60):
        state = _random_start(rng, world)
        inputs = 0
        cached_at = None
        for _ in range(150):
            if rng.random() < 0.08:
                inputs = rng.choice(INPUTS)
            here = (state.px // 8, state.py // 16)
            if cached_at is None or abs(here[0] - cached_at[0]) > 4 or abs(here[1] - cached_at[1]) > 4:
                harness.fill_cache(world, *here)
                cached_at = here
            harness.write(state, inputs)
            memory[labels["zp_inventory"]] = hands.inventory
            memory[labels["zp_cooldown"]] = hands.cooldown
            machine.call(labels["update_player"])
            machine.call(labels["player_action"])
            actual, _, _, _ = harness.read()
            expected = player.step(state, inputs, world.tile_at)
            assert actual == expected, f"from {state} with inputs {inputs}"
            hands, action, target = actions.act(hands, expected, inputs, world)
            assert (memory[labels["zp_inventory"]], memory[labels["zp_cooldown"]]) == (hands.inventory, hands.cooldown)
            assert memory[labels["zp_action"]] == action, f"at {expected} with inputs {inputs}"
            if target is not None:
                assert (memory[labels["zp_target_x"]], memory[labels["zp_target_y"]]) == target
                done[action] += 1
                partial_seen.add(world.tile_at(*target))
            state = expected
    assert done[actions.DIG] > 50 and done[actions.PLACE] > 20, done
    assert any(kind >= PARTIAL_BASE for kind in partial_seen), "no tile was ever partly dug"
    # The 6502 world agrees with the model everywhere it was changed.
    for index in world.directory:
        x0, y0 = index % 32 * CHUNK_SIZE, index // 32 * CHUNK_SIZE
        for y in range(y0, y0 + CHUNK_SIZE):
            for x in range(x0, x0 + CHUNK_SIZE):
                assert machine.call(labels["tile_at"], x=x, y=y).mpu.a == world.tile_at(x, y), (x, y)
