"""The parasite's inventory (asm/inventory.asm) counts as inventory.py
does: up to COUNT_MAX of each kind."""

from conftest import parasite_machine
from stratagem import inventory
from stratagem.inventory import COUNT_MAX, KIND_COUNT


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
