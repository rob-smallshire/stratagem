"""The 6502 world generator matches its Python model, tile for tile."""

import pytest

from conftest import FakeHost, parasite_machine
from stratagem.world import WORLD_SIZE, tile_at


@pytest.fixture(scope="module")
def world_machine(game_build):
    return parasite_machine(game_build)[0]


@pytest.mark.slow
def test_tile_at_matches_model_everywhere(world_machine, game_build):
    tile_at_address = game_build.labels["PARASITE"]["tile_at"]
    shape_address = game_build.labels["PARASITE"]["zp_world_shape"]
    mismatches = []
    for y in range(WORLD_SIZE):
        for x in range(WORLD_SIZE):
            mpu = world_machine.call(tile_at_address, x=x, y=y).mpu
            actual = ((mpu.a, mpu.memory[shape_address]), mpu.x, mpu.y)
            if actual != (tile_at(x, y), x, y):
                mismatches.append(((x, y), actual, tile_at(x, y)))
    assert mismatches[:10] == []


def test_changes_match_model_until_the_world_is_full(world_machine, game_build):
    import random
    from stratagem.tiles import MATERIAL_COUNT, SHAPE_COUNT
    from stratagem.world import CHUNK_SIZE, SLOT_COUNT, World

    labels = game_build.labels["PARASITE"]
    world = World()
    world_machine.call(labels["world_reset"])
    rng = random.Random(7)
    chunks = [(rng.randrange(32), rng.randrange(32)) for _ in range(SLOT_COUNT + 120)]
    memory = world_machine.mpu.memory
    host = FakeHost(world_machine, labels)
    refused = 0
    for step in range(3000):
        cx, cy = rng.choice(chunks[: 20 + step // 8])
        x, y = cx * CHUNK_SIZE + rng.randrange(CHUNK_SIZE), cy * CHUNK_SIZE + rng.randrange(CHUNK_SIZE)
        tile = (rng.randrange(MATERIAL_COUNT), rng.randrange(SHAPE_COUNT) | rng.choice([0, 0x40]))
        world_machine.mpu.memory[labels["zp_world_new_shape"]] = tile[1]
        mpu = world_machine.call(labels["set_tile"], a=tile[0], x=x, y=y).mpu
        accepted = world.set_tile(x, y, tile)
        assert (mpu.p & 1 == 0) == accepted, f"set_tile({x}, {y}) carry disagrees"
        assert (mpu.x, mpu.y) == (x, y)
        refused += not accepted
        host.take_queue()
    assert refused > 0, "the world never filled up"
    # The host's store holds every changed chunk, as the model does, and the
    # parasite reads them back, fetching those it doesn't hold.
    assert len(host.store) == len(world.slots) == SLOT_COUNT
    for slot, tiles in enumerate(world.slots, start=1):
        assert host.store[slot] == [m for m, _ in tiles] + [s for _, s in tiles], f"slot {slot}"
    for cx, cy in chunks[:60]:
        for x, y in ((cx * CHUNK_SIZE, cy * CHUNK_SIZE), (cx * CHUNK_SIZE + 7, cy * CHUNK_SIZE + 5)):
            mpu = world_machine.call(labels["tile_at"], x=x, y=y).mpu
            assert (mpu.a, memory[labels["zp_world_shape"]]) == world.tile_at(x, y), (x, y)
    assert host.fetched > 0, "no chunk was fetched"
    assert world_machine.mpu.memory[labels["world_slots_used"]] == SLOT_COUNT
    tile_at_address = labels["tile_at"]
    for cx, cy in set(chunks):
        for j in range(CHUNK_SIZE):
            for i in range(CHUNK_SIZE):
                x, y = cx * CHUNK_SIZE + i, cy * CHUNK_SIZE + j
                mpu = world_machine.call(tile_at_address, x=x, y=y).mpu
                assert (mpu.a, mpu.memory[labels["zp_world_shape"]]) == world.tile_at(x, y), (x, y)
