"""The 6502 world generator matches its Python model, tile for tile."""

import pytest

from conftest import parasite_machine
from stratagem.world import WORLD_SIZE, tile_at

STORE_QUEUE, STORE_CHUNK = 32, 0xFF     # asm/world.asm, asm/tube_layout.asm
SLOT_BYTES = 128


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
    chunks = [(rng.randrange(32), rng.randrange(32)) for _ in range(SLOT_COUNT + 40)]
    memory = world_machine.mpu.memory
    slots = labels["world_slots"]
    host = {}           # the host's copy of the store: slot -> bytes

    def take_changes():
        """Apply the queued changes, as the host does from a packet."""
        head, tail = memory[labels["store_head"]], memory[labels["store_tail"]]
        while head != tail:
            slot, offset = memory[labels["store_queue_slot"] + head], memory[labels["store_queue_offset"] + head]
            if offset == STORE_CHUNK:
                host[slot] = memory[slots + (slot - 1) * SLOT_BYTES:slots + slot * SLOT_BYTES]
            else:
                host[slot][offset] = memory[labels["store_queue_material"] + head]
                host[slot][offset + CHUNK_SIZE ** 2] = memory[labels["store_queue_shape"] + head]
            head = (head + 1) % STORE_QUEUE
        memory[labels["store_head"]] = head

    refused = 0
    for step in range(1500):
        cx, cy = rng.choice(chunks[: 20 + step // 5])
        x, y = cx * CHUNK_SIZE + rng.randrange(CHUNK_SIZE), cy * CHUNK_SIZE + rng.randrange(CHUNK_SIZE)
        tile = (rng.randrange(MATERIAL_COUNT), rng.randrange(SHAPE_COUNT) | rng.choice([0, 0x40]))
        world_machine.mpu.memory[labels["zp_world_new_shape"]] = tile[1]
        mpu = world_machine.call(labels["set_tile"], a=tile[0], x=x, y=y).mpu
        accepted = world.set_tile(x, y, tile)
        assert (mpu.p & 1 == 0) == accepted, f"set_tile({x}, {y}) carry disagrees"
        assert (mpu.x, mpu.y) == (x, y)
        refused += not accepted
        take_changes()
    assert refused > 0, "the world never filled up"
    used = memory[labels["world_slots_used"]]
    assert sorted(host) == list(range(1, used + 1))
    for slot, data in host.items():
        assert data == memory[slots + (slot - 1) * SLOT_BYTES:slots + slot * SLOT_BYTES], f"slot {slot}"
    assert world_machine.mpu.memory[labels["world_slots_used"]] == SLOT_COUNT
    tile_at_address = labels["tile_at"]
    for cx, cy in set(chunks):
        for j in range(CHUNK_SIZE):
            for i in range(CHUNK_SIZE):
                x, y = cx * CHUNK_SIZE + i, cy * CHUNK_SIZE + j
                mpu = world_machine.call(tile_at_address, x=x, y=y).mpu
                assert (mpu.a, mpu.memory[labels["zp_world_shape"]]) == world.tile_at(x, y), (x, y)
