"""Pieces and their slots (asm/pieces.asm, host_compose in asm/host_main.asm),
in py65: the parasite gives each pair of piece and backdrop in the tile
cache a slot, with its visibility for the light, shows piece tiles as their
slots, and frees slots whose pairs have left the tile cache; the host
composes a slot as tiles.compose does. Run with -s to see what composing
costs."""

import collections

from py65.memory import ObservableMemory

from mos6502 import Machine6502
from stratagem import gen_tables
from stratagem.build import read_disc_file
from stratagem.tiles import (AIR, BACKGROUND_SKY, BACKDROPS, FIRST_PIECE, SHAPE_FULL, SKY, SLOT_COUNT, SLOT_MATERIAL,
                             TORCH, compose, slot_tile)

NO_SLOT = 0xFF
TUBE_R3_STATUS, TUBE_R3 = 0xFEE4, 0xFEE5
SLOT_GRAPHICS = 0x8100 + SLOT_MATERIAL * 0x200      # tube_layout.asm's HOST_MATERIAL_PAGES


def parasite(game_build):
    machine = Machine6502(cmos=True)
    for name in ("PGAME", "PWORLD", "PLIGHT"):
        machine.load(*read_disc_file(game_build.disc_filepath, name))
    labels = game_build.labels["PARASITE"]
    machine.call(labels["piece_init"])
    return machine, labels


def put_tile(machine, labels, index, tile):
    machine.mpu.memory[labels["tile_cache"] + index] = tile[0]
    machine.mpu.memory[labels["tile_cache_shapes"] + index] = tile[1]


def test_slots_are_given_shown_and_freed(game_build):
    machine, labels = parasite(game_build)
    memory = machine.mpu.memory
    cave_torch, sky_torch = (TORCH, SHAPE_FULL), (TORCH, SHAPE_FULL | BACKGROUND_SKY)
    put_tile(machine, labels, 5, cave_torch)
    put_tile(machine, labels, 700, sky_torch)

    slots = []
    for tile in (cave_torch, sky_torch):
        mpu = machine.call(labels["piece_slot"], a=tile[0], x=tile[1]).mpu
        assert mpu.p & 1, "a new slot"
        slot = mpu.x
        assert mpu.x != NO_SLOT
        mpu = machine.call(labels["piece_slot"], a=tile[0], x=tile[1]).mpu
        assert not mpu.p & 1 and mpu.x == slot, "the same slot, not new"
        mpu = machine.call(labels["piece_shown"], a=tile[0], x=tile[1]).mpu
        assert (mpu.a, mpu.x) == slot_tile(slot)
        slots.append(slot)
    assert slots[0] != slots[1]

    # Each slot's visibility is its pair's, for each parity.
    for pair, slot in enumerate(slots):
        for name, parity in (("slot_visibility_even", 0), ("slot_visibility_odd", 1)):
            base = labels[name] + slot * 8
            assert list(memory[base:base + 8]) == gen_tables._pair_visibility(parity)[pair * 8:pair * 8 + 8]

    # The sky's torch leaves the tile cache: a sweep frees its slot only.
    put_tile(machine, labels, 700, (AIR, SHAPE_FULL))
    machine.call(labels["slot_sweep"], max_steps=200_000)
    assert memory[labels["slot_pair"] + slots[0]] == 0
    assert memory[labels["slot_pair"] + slots[1]] == NO_SLOT
    assert memory[labels["pair_slot"] + 1] == NO_SLOT
    mpu = machine.call(labels["piece_shown"], a=TORCH, x=BACKGROUND_SKY).mpu
    assert (mpu.a, mpu.x) == (SKY, BACKGROUND_SKY), "no slot: shown as its backdrop"


def test_a_full_tile_cache_frees_slots_as_needed(game_build):
    """With every slot held by a pair no longer in the tile cache, a new pair
    sweeps and is given one."""
    machine, labels = parasite(game_build)
    memory = machine.mpu.memory
    # Slot 0 holds the sky's torch, which has left the cache; the rest are
    # held too (by the same pair, as far as the free search can tell).
    memory[labels["slot_pair"]:labels["slot_pair"] + SLOT_COUNT] = [1] * SLOT_COUNT
    memory[labels["pair_slot"] + 1] = 0
    put_tile(machine, labels, 9, (TORCH, SHAPE_FULL))
    mpu = machine.call(labels["piece_slot"], a=TORCH, x=SHAPE_FULL, max_steps=200_000).mpu
    assert mpu.p & 1 and mpu.x != NO_SLOT
    assert memory[labels["pair_slot"]] == mpu.x


def test_host_composes_slots(game_build):
    machine = Machine6502()
    machine.mpu.memory = ObservableMemory()
    memory = machine.mpu.memory
    machine.load(*read_disc_file(game_build.disc_filepath, "MAIN"))
    labels = game_build.labels["HOST"]
    sent = collections.deque()
    memory.subscribe_to_read([TUBE_R3_STATUS], lambda address: 0x80)
    memory.subscribe_to_read([TUBE_R3], lambda address: sent.popleft())
    cycles = []
    for slot, piece, backdrop in ((0, TORCH, AIR), (5, TORCH, SKY), (SLOT_COUNT - 1, TORCH, SKY)):
        sent.extend([slot, piece - FIRST_PIECE, BACKDROPS.index(backdrop)])
        mpu = machine.mpu
        machine.call(labels["host_compose"])
        assert not sent
        base = SLOT_GRAPHICS + slot * 64
        assert bytes(memory[base:base + 64]) == compose(piece, backdrop)
        assert memory[labels["host_slot_pair"] + slot] == (piece - FIRST_PIECE) * 2 + BACKDROPS.index(backdrop)
        sent.extend([slot, piece - FIRST_PIECE, BACKDROPS.index(backdrop)])
        before = mpu.processorCycles
        machine.call(labels["host_compose"])
        cycles.append(mpu.processorCycles - before)
    print(f"\ncomposing a slot on the host: {max(cycles)} cycles, with reading its 3 bytes")
