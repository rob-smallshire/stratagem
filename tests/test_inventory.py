"""The parasite's inventory (asm/inventory.asm) counts as inventory.py
does: up to COUNT_MAX of each kind."""

from conftest import parasite_machine
from stratagem import inventory
from stratagem.camera import INPUT_ACTION, INPUT_DOWN, INPUT_LEFT, INPUT_PLACE, INPUT_RIGHT
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


def test_the_miner_starts_with_torches_and_places_them(game_build):
    """The game starts with inventory.STARTING; SPACE, with the torches in
    hand, places one, spending it: here behind the miner, turned round in
    a tunnel dug down and along."""
    from test_daylight import ParasiteGame
    game = ParasiteGame(game_build)
    game.frame(0)
    address = game.labels["inventory"]
    assert tuple(game.memory[address + k] for k in range(KIND_COUNT)) == inventory.STARTING
    for count, inputs in [(150, INPUT_DOWN | INPUT_ACTION), (60, INPUT_RIGHT | INPUT_ACTION), (2, INPUT_LEFT)]:
        for _ in range(count):
            game.frame(inputs)
    game.memory[game.labels["hand"]] = KIND_TORCH
    for frame in range(3):
        game.frame(INPUT_PLACE)
    assert game.byte("torch_count") == 1
    assert game.memory[address + KIND_TORCH] == inventory.STARTING_TORCHES - 1
