"""Crafting (crafting.py): the grid, the recipes and the book, as the model
says, and on the parasite (asm/crafting.asm, py65) exactly as the model."""

import random

from conftest import parasite_machine
from stratagem import crafting
from stratagem.crafting import EMPTY, EMPTY_GRID, GRID_CELLS, RECIPES, STATION_HAND
from stratagem.inventory import COUNT_MAX, KIND_BENCH, KIND_COUNT, KIND_ORE, KIND_PLANKS, KIND_TORCH, KIND_WOOD

W, O, P, _ = KIND_WOOD, KIND_ORE, KIND_PLANKS, EMPTY


def counts_of(**kinds) -> tuple[int, ...]:
    names = {"wood": KIND_WOOD, "ore": KIND_ORE, "planks": KIND_PLANKS, "torch": KIND_TORCH, "bench": KIND_BENCH}
    return tuple(next((n for name, n in kinds.items() if names[name] == kind), 0) for kind in range(KIND_COUNT))


def grid_of(*cells: int) -> tuple[int, ...]:
    return tuple(cells) + (EMPTY,) * (GRID_CELLS - len(cells))


def test_shapes_match_anywhere_in_the_grid_but_not_mirrored():
    for cell in (0, 1, 3, 4):
        grid = list(EMPTY_GRID)
        grid[cell] = W
        assert crafting.match(tuple(grid), STATION_HAND) == 0        # planks, from wood anywhere
    assert crafting.match(grid_of(_, O, _, _, W), STATION_HAND) == 1   # a torch, in the right column
    assert crafting.match(grid_of(W, _, _, O), STATION_HAND) is None     # upside down
    assert crafting.match(grid_of(P, P, _, P, P), STATION_HAND) == 2     # a workbench
    assert crafting.match(grid_of(P, P, _, P), STATION_HAND) is None
    assert crafting.match(grid_of(W, W), STATION_HAND) is None
    assert crafting.match(EMPTY_GRID, STATION_HAND) is None


def test_a_cells_key_puts_takes_back_and_swaps():
    counts = counts_of(wood=2, ore=1)
    counts, grid = crafting.put(counts, EMPTY_GRID, 0, W)
    assert counts == counts_of(wood=1, ore=1) and grid == grid_of(W)
    counts, grid = crafting.put(counts, grid, 0, W)                 # the same kind: taken back
    assert counts == counts_of(wood=2, ore=1) and grid == EMPTY_GRID
    counts, grid = crafting.put(counts, grid, 0, W)
    counts, grid = crafting.put(counts, grid, 0, O)                 # another: swapped
    assert counts == counts_of(wood=2) and grid == grid_of(O)
    counts, grid = crafting.put(counts, grid, 1, O)                 # none left: nothing
    assert counts == counts_of(wood=2) and grid == grid_of(O)
    counts, grid = crafting.clear(counts, grid)
    assert counts == counts_of(wood=2, ore=1) and grid == EMPTY_GRID


def test_making_lays_the_shape_out_again_as_far_as_the_counts_go():
    counts, grid = crafting.lay_out(counts_of(wood=2, ore=1), RECIPES[1].rows)
    assert grid == grid_of(O, _, _, W) and counts == counts_of(wood=1)
    counts, grid, book = crafting.make(counts, grid, 0, STATION_HAND)
    assert counts == counts_of(torch=2) and grid == grid_of(_, _, _, W) and book == 0b10
    counts, grid, book = crafting.make(counts, grid, book, STATION_HAND)     # the wood left: planks
    assert counts == counts_of(torch=2, planks=4) and grid == EMPTY_GRID and book == 0b11
    assert crafting.make(counts, grid, book, STATION_HAND) == (counts, grid, book)     # nothing laid out
    counts, grid, book = crafting.make(counts_of(planks=COUNT_MAX - 1), grid_of(W), 0, STATION_HAND)
    assert counts == counts_of(planks=COUNT_MAX) and grid == EMPTY_GRID      # the rest lost


def test_copy_steps_through_the_book():
    counts = counts_of(wood=3, ore=1, planks=1)
    assert crafting.copy(counts, EMPTY_GRID, 0, len(RECIPES) - 1, STATION_HAND) == \
        (counts, EMPTY_GRID, len(RECIPES) - 1)                       # nothing in the book
    book = 0b101
    counts, grid, copied = crafting.copy(counts, grid_of(O), book, len(RECIPES) - 1, STATION_HAND)
    assert copied == 0 and grid == grid_of(W) and counts == counts_of(wood=2, ore=2, planks=1)
    counts, grid, copied = crafting.copy(counts, grid, book, copied, STATION_HAND)
    assert copied == 2 and grid == grid_of(P) and counts == counts_of(wood=3, ore=2)   # what's missing, left empty
    counts, grid, copied = crafting.copy(counts, grid, book, copied, STATION_HAND)
    assert copied == 0


def random_grid(rng: random.Random) -> tuple[int, ...]:
    """A grid, often one of the recipes', perhaps moved, perhaps spoilt."""
    if rng.random() < 0.6:
        rows = rng.choice(RECIPES).rows
        top, left = rng.randrange(crafting.GRID_MAX - len(rows) + 1), rng.randrange(crafting.GRID_MAX - len(rows[0]) + 1)
        grid = list(EMPTY_GRID)
        for r, row in enumerate(rows):
            for c, kind in enumerate(row):
                grid[(top + r) * crafting.GRID_MAX + left + c] = kind
        if rng.random() < 0.3:
            grid[rng.randrange(GRID_CELLS)] = rng.choice([EMPTY, rng.randrange(KIND_COUNT)])
        return tuple(grid)
    return tuple(rng.choice([EMPTY, EMPTY, W, O, P, rng.randrange(KIND_COUNT)]) for _ in range(GRID_CELLS))


def test_parasite_crafting_matches_model(game_build):
    machine, labels = parasite_machine(game_build)
    memory = machine.mpu.memory
    rng = random.Random(1987)
    inventory, grid_address = labels["inventory"], labels["craft_grid"]
    seen = {"matched": 0, "made": 0, "copied": 0, "put": 0}
    for trial in range(1500):
        counts = tuple(rng.choice([0, 0, 1, 2, rng.randrange(100), 98, 99]) for _ in range(KIND_COUNT))
        grid = random_grid(rng)
        book = rng.randrange(1 << len(RECIPES))
        copied = rng.randrange(len(RECIPES))
        memory[inventory:inventory + KIND_COUNT] = counts
        memory[grid_address:grid_address + GRID_CELLS] = grid
        memory[labels["craft_book"]] = book
        memory[labels["craft_copied"]] = copied
        memory[labels["pack_station"]] = STATION_HAND
        what = rng.choice(["match", "put", "clear", "make", "copy"])
        if what == "match":
            machine.call(labels["craft_match"])
            index = crafting.match(grid, STATION_HAND)
            assert (not machine.mpu.p & 2) == (index is not None), f"trial {trial}"
            if index is not None:
                assert machine.mpu.x == index, f"trial {trial}"
                seen["matched"] += 1
            continue
        if what == "put":
            cell = rng.randrange(GRID_CELLS)
            hand = rng.randrange(KIND_COUNT)
            memory[labels["hand"]] = hand
            machine.call(labels["craft_put"], x=cell)
            counts, grid = crafting.put(counts, grid, cell, hand)
            seen["put"] += 1
        elif what == "clear":
            machine.call(labels["craft_clear"])
            counts, grid = crafting.clear(counts, grid)
        elif what == "make":
            machine.call(labels["craft_make"])
            before = counts
            counts, grid, book = crafting.make(counts, grid, book, STATION_HAND)
            seen["made"] += counts != before
        else:
            machine.call(labels["craft_copy"])
            counts, grid, copied = crafting.copy(counts, grid, book, copied, STATION_HAND)
            seen["copied"] += 1
        assert tuple(memory[inventory:inventory + KIND_COUNT]) == counts, f"trial {trial}: {what}"
        assert tuple(memory[grid_address:grid_address + GRID_CELLS]) == grid, f"trial {trial}: {what}"
        assert memory[labels["craft_book"]] == book, f"trial {trial}: {what}"
        assert memory[labels["craft_copied"]] == copied, f"trial {trial}: {what}"
    assert min(seen.values()) >= 50, seen
