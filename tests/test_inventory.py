"""The parasite's inventory (asm/inventory.asm) counts as inventory.py
does: up to COUNT_MAX of each kind."""

from conftest import parasite_machine
from stratagem import inventory
from stratagem.camera import INPUT_TORCH
from stratagem.inventory import COUNT_MAX, KIND_COUNT, KIND_TORCH


def test_counts_go_up_to_the_cap(game_build):
    machine, labels = parasite_machine(game_build)
    memory = machine.mpu.memory
    address = labels["inventory"]
    for kind in range(KIND_COUNT):
        others = [memory[address + k] for k in range(KIND_COUNT) if k != kind]
        for count in range(COUNT_MAX + 1):
            counts = tuple(count if k == kind else 0 for k in range(KIND_COUNT))
            memory[address + kind] = count
            machine.call(labels["inventory_gain"], a=kind)
            assert memory[address + kind] == inventory.gain(counts, kind)[kind]
        assert [memory[address + k] for k in range(KIND_COUNT) if k != kind] == others


def test_the_miner_starts_with_torches_and_t_spends_them(game_build):
    """The game starts with inventory.STARTING; T drops a torch for each one
    carried, and none once they are gone."""
    from test_daylight import ParasiteGame
    game = ParasiteGame(game_build)
    game.frame(0)
    address = game.labels["inventory"]
    assert tuple(game.memory[address + k] for k in range(KIND_COUNT)) == inventory.STARTING
    game.memory[address + KIND_TORCH] = 0
    game.call("torch_drop")         # none carried: nothing, though the tile is empty
    assert game.byte("torch_count") == 0
    game.memory[address + KIND_TORCH] = 2
    for frame in range(40):         # T pressed every other frame, the miner standing
        game.frame(INPUT_TORCH if frame % 2 == 0 else 0)
    assert game.byte("torch_count") == 1        # only one tile to drop it in
    assert game.memory[address + KIND_TORCH] == 1
