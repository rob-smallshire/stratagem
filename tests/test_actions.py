"""The 6502 digging and placing match the Python model, frame by frame, with
the player moving through a world that both change in step."""

import collections
import random

import pytest

from conftest import FakeHost, parasite_machine, pickaxe_hands
from stratagem import actions, inventory, player
from stratagem.actions import Hands
from stratagem.camera import INPUT_ACTION, INPUT_PLACE
from stratagem.camera import INPUT_DOWN, INPUT_LEFT, INPUT_RIGHT, INPUT_UP
from stratagem.tiles import AIR, SHAPE_BITS, SHAPE_FULL, TORCH
from stratagem.world import CHUNK_SIZE, HEIGHTS, RAMP_TOP_LEFT, RAMP_TOP_RIGHT, World
from test_player import TILE_CACHE_SIZE, PlayerHarness, _random_start


@pytest.fixture
def machine(game_build):
    """The parasite's game, with an empty world, and the host's store."""
    machine, labels = parasite_machine(game_build)
    machine.host = FakeHost(machine, labels)
    machine.call(labels["world_reset"])
    return machine


def write_hands(machine, labels, hands: Hands) -> None:
    """The model's hands into the 6502's: the tool hand as the belt's first
    slot, chosen (tool_update)."""
    memory = machine.mpu.memory
    for kind, count in enumerate(hands.counts):
        memory[labels["inventory"] + kind] = count
    memory[labels["hand"]] = hands.hand
    memory[labels["cooldown"]] = hands.cooldown
    memory[labels["torch_count"]] = hands.torches
    memory[labels["belt"]] = hands.tool
    memory[labels["belt_slot"]] = 0
    memory[labels["belt_wear"]] = hands.wear
    memory[labels["zp_place_wait"]] = 0xFF if hands.wait else 0
    machine.call(labels["tool_update"])


def read_hands(memory, labels) -> Hands:
    counts = tuple(memory[labels["inventory"] + kind] for kind in range(inventory.KIND_COUNT))
    tool = memory[labels["belt"] + memory[labels["belt_slot"]]]
    wear = memory[labels["belt_wear"] + memory[labels["belt_slot"]]]
    return Hands(counts, memory[labels["cooldown"]], memory[labels["hand"]], memory[labels["torch_count"]], tool, wear,
                 bool(memory[labels["zp_place_wait"]]))


def random_hands(rng: random.Random, kinds=sorted(inventory.PLACES)) -> Hands:
    """Hands with counts often empty or full, the hand on one of `kinds`
    (those placed, by default), and often empty, so that placing moves it."""
    counts = [rng.choice([0, 0, 1, 2, rng.randrange(100), 98, 99]) for _ in range(inventory.KIND_COUNT)]
    hand = rng.choice(kinds)
    if rng.random() < 0.5:
        counts[hand] = 0
    if rng.random() < 0.05:                     # nothing to place at all
        for kind in inventory.PLACES:
            counts[kind] = 0
    tool, wear = random_tool(rng, counts)
    return Hands(tuple(counts), 0, hand, rng.choice([0, 0, inventory.TORCH_MAX - 1, inventory.TORCH_MAX]), tool, wear,
                 rng.random() < 0.2)


def random_tool(rng: random.Random, counts: list[int]) -> tuple[int, int]:
    """A tool hand, often a pickaxe, and its wear, often about to break."""
    tool = rng.choice([actions.NO_TOOL, *inventory.TOOLS, *inventory.TOOLS])
    if tool == actions.NO_TOOL:
        return tool, 0
    return tool, rng.choice([0, rng.randrange(actions.DURABILITY[tool]), actions.DURABILITY[tool] - 1])


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


@pytest.mark.slow
def test_actions_match_model(machine, game_build):
    labels = game_build.labels["PARASITE"]
    harness = PlayerHarness(machine, labels)
    memory = machine.mpu.memory
    rng = random.Random(1990)
    world = World()
    hands = pickaxe_hands()
    done = {actions.DIG: 0, actions.PLACE: 0}
    broken = 0
    partial_seen = set()
    ramps = 0
    for episode in range(100):
        state = _random_start(rng, world)
        hands = random_hands(rng)
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
            write_hands(machine, labels, hands)
            memory[labels["item_count"]] = 0        # wood dropped is items.py's business
            machine.call(labels["update_player"])
            machine.call(labels["player_action"])
            machine.host.take_queue()
            actual, _, _, _ = harness.read()
            expected = player.step(state, inputs, world.tile_at)
            assert actual == expected, f"from {state} with inputs {inputs}"
            before = hands
            hands, action, target = actions.act(hands, expected, inputs, world)
            broken += before.tool != actions.NO_TOOL and hands.tool == actions.NO_TOOL
            assert read_hands(memory, labels) == hands
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
    assert broken >= 3, f"tools broke {broken} times"
    # The 6502 world agrees with the model everywhere it was changed.
    for index in world.directory:
        x0, y0 = index % 32 * CHUNK_SIZE, index // 32 * CHUNK_SIZE
        for y in range(y0, y0 + CHUNK_SIZE):
            for x in range(x0, x0 + CHUNK_SIZE):
                mpu = machine.call(labels["tile_at"], x=x, y=y).mpu
                assert (mpu.a, memory[labels["zp_world_shape"]]) == world.tile_at(x, y), (x, y)


def test_placing_takes_the_hand_or_the_first_kind_held(machine, game_build):
    """Placing puts down the kind in hand; with none of it left, the first
    kind held that places something, which the hand moves to; with nothing
    to place, or a hand that places nothing (wood), nothing; a torch,
    unless there are TORCH_MAX in the world, in the miner's own tile if
    there's no other. The 6502 does
    as the model, from random places and hands."""
    labels = game_build.labels["PARASITE"]
    harness = PlayerHarness(machine, labels)
    memory = machine.mpu.memory
    rng = random.Random(1066)
    world = World()
    seen = collections.Counter()
    torches = collections.Counter()
    waited = overlapping = 0
    for trial in range(1600):
        state = _random_start(rng, world)
        inputs = INPUT_PLACE | rng.choice([0, INPUT_UP, INPUT_DOWN])
        hands = random_hands(rng, [*range(inventory.KIND_COUNT), *[inventory.KIND_TORCH] * 4])    # torches often
        harness.fill_cache(world, state.px // 8, state.py // 16)
        harness.write(state, inputs)
        write_hands(machine, labels, hands)
        machine.call(labels["player_action"])
        machine.host.take_queue()
        before = hands
        hands, action, target = actions.act(hands, state, inputs, world)
        assert memory[labels["action"]] == action, f"trial {trial}: {state}"
        assert read_hands(memory, labels) == hands, f"trial {trial}: {state}"
        if target is not None:
            assert_tile_matches(machine, labels, world, target)
        seen["moved" if hands.hand != before.hand else "places nothing" if before.hand not in inventory.PLACES
             else "nothing held" if not any(before.counts[k] for k in inventory.PLACES) else "kept"] += 1
        waited += before.wait and action == actions.NONE
        overlapping += action == actions.PLACE and actions.overlaps_player(state, *target)
        if inventory.PLACES.get(hands.hand) == TORCH:
            own = ((state.px + player.PLAYER_WIDTH // 2) // player.TILE_WIDTH,
                   (state.py + player.PLAYER_HEIGHT // 2) // player.TILE_HEIGHT)
            torches["own tile" if action == actions.PLACE and target == own
                    else "placed" if action == actions.PLACE
                    else "full" if before.torches == inventory.TORCH_MAX else "not placed"] += 1
    assert min(seen.values()) >= 5 and len(seen) == 4, seen
    assert min(torches.values()) >= 5 and len(torches) == 4, torches
    assert waited >= 5 and overlapping >= 5, (waited, overlapping)


@pytest.mark.parametrize("keys", [pytest.param(INPUT_LEFT | INPUT_DOWN, marks=pytest.mark.slow),
                                  INPUT_RIGHT | INPUT_DOWN,
                                  pytest.param(INPUT_LEFT | INPUT_UP, marks=pytest.mark.slow),
                                  pytest.param(INPUT_RIGHT | INPUT_UP, marks=pytest.mark.slow)],
                         ids=["down-left", "down-right", "up-left", "up-right"])
def test_long_diagonal_tunnels_match_model(machine, game_build, keys):
    """Holding a diagonal dig for a long time, from places on the surface
    (slopes included) and underground, the 6502 tunnels exactly as the model
    does, frame by frame."""
    labels = game_build.labels["PARASITE"]
    harness = PlayerHarness(machine, labels)
    memory = machine.mpu.memory
    keys |= INPUT_ACTION
    world = World()
    hands = pickaxe_hands()
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
                write_hands(machine, labels, hands)
                memory[labels["item_count"]] = 0
                machine.call(labels["update_player"])
                machine.call(labels["player_action"])
                machine.host.take_queue()
                actual, _, _, _ = harness.read()
                expected = player.step(state, keys, world.tile_at)
                assert actual == expected, f"from {state}"
                hands, action, target = actions.act(hands, expected, keys, world)
                assert memory[labels["action"]] == action
                assert read_hands(memory, labels) == hands
                if target is not None:
                    assert (memory[labels["target_x"]], memory[labels["target_y"]]) == target
                    assert_tile_matches(machine, labels, world, target)
                    digs += 1
                state = expected
    assert digs > 100


@pytest.mark.slow
@pytest.mark.parametrize("keys", [INPUT_LEFT | INPUT_DOWN, INPUT_RIGHT | INPUT_DOWN,
                                  INPUT_LEFT | INPUT_UP, INPUT_RIGHT | INPUT_UP],
                         ids=["down-left", "down-right", "up-left", "up-right"])
def test_diagonal_digs_in_random_ground_match_model(machine, game_build, keys):
    """A single diagonal dig, from thousands of random places in random
    ground (every material and shape near the player), chooses and leaves
    exactly what the model does: every case of the choice, not only those a
    tunnel meets."""
    from stratagem.tiles import MATERIAL_COUNT, PASSABLE, SHAPE_COUNT, BACKGROUND_SKY
    labels = game_build.labels["PARASITE"]
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
                machine.host.take_queue()
        px, py = tx0 * 8 + rng.randrange(8), ty0 * 16 + rng.randrange(16)
        # Clear whatever the player would overlap.
        for tx in range(px // 8, (px + 5) // 8 + 1):
            for ty in range(py // 16, (py + 23) // 16 + 1):
                if player.hits(world.tile_at, px, py):
                    world.set_tile(tx, ty, (AIR, SHAPE_FULL))
                    memory[labels["zp_world_new_shape"]] = SHAPE_FULL
                    machine.call(labels["set_tile"], a=AIR, x=tx, y=ty)
                    machine.host.take_queue()
        if player.hits(world.tile_at, px, py):
            continue
        state = player.Player(x=px * 16 + rng.randrange(16), y=py * 16, on_ground=rng.random() < 0.7,
                              facing=1 if keys & INPUT_RIGHT else -1)
        harness.fill_cache(world, tx0, ty0)
        harness.write(state, keys)
        hands = random_hands(random.Random(trial))     # leaving rng's trials as they were
        write_hands(machine, labels, hands)
        machine.call(labels["player_action"])
        machine.host.take_queue()
        dx = 1 if keys & INPUT_RIGHT else -1
        target, ramp = actions.diagonal(state, dx, 1 if keys & INPUT_DOWN else -1, world.tile_at)
        if target and ramp is None:
            sides[actions.near_side(state, target, dx)] += 1
        hands, action, target = actions.act(hands, state, keys, world)
        assert memory[labels["action"]] == action, f"trial {trial}: {state}"
        assert read_hands(memory, labels) == hands
        if target is not None:
            assert (memory[labels["target_x"]], memory[labels["target_y"]]) == target, f"trial {trial}: {state}"
            assert_tile_matches(machine, labels, world, target)
    assert len(sides) >= 2, sides
