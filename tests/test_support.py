"""Support on the parasite (asm/support.asm): what isn't held falls, as
support.py says, a few pieces a frame. The game runs in py65 with the
host's part played by FakeHost."""

import numpy as np

from stratagem import support
from stratagem.piece_lab import Cell
from stratagem.tiles import BACKGROUND_SKY, MATERIAL_NAMES, PASSABLE, PIECES, SKY
from stratagem.world import HEIGHTS, TRUNKS, generate_tile
from test_daylight import ParasiteGame

TILE_CACHE_SIZE = 32
STRENGTH_BITS = 7


def cells_of(tile_at, x0, x1, y0, y1):
    """The tiles of a region as support.py's cells."""
    cells = []
    for y in range(y0, y1):
        row = []
        for x in range(x0, x1):
            material, _ = tile_at(x, y)
            if material in PIECES:
                row.append(Cell(piece=MATERIAL_NAMES[material]))
            else:
                row.append(Cell(terrain=None if material in PASSABLE else material))
        cells.append(row)
    return cells


def settle(game, frames: int = 60) -> int:
    """Play idle frames until nothing is left to check; returns how many."""
    for n in range(frames):
        game.frame(0)
        game.host.check_cache()
        if game.byte("support_head") == game.byte("support_tail"):
            return n + 1
    raise AssertionError("support never settled")


def test_a_felled_tree_falls_as_the_model_says():
    from conftest import parasite_machine  # noqa: F401 (the fixtures' module)
    from stratagem.build import build
    game = ParasiteGame(build())
    labels, memory = game.labels, game.memory
    trunk = 127
    assert trunk in TRUNKS
    assert game.byte("cached_left") < trunk - 1 and trunk + 1 < game.byte("cached_right")
    ground = HEIGHTS[trunk]
    x0, x1, y0, y1 = trunk - 4, trunk + 5, ground - TRUNKS[trunk] - 6, ground + 2
    before = cells_of(generate_tile, x0, x1, y0, y1)
    cut = (trunk, ground - 2)               # the trunk's first tile above the root

    memory[labels["zp_world_new_shape"]] = BACKGROUND_SKY
    game.call("call_set_tile", a=SKY, x=cut[0], y=cut[1])
    index = (cut[1] % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + cut[0] % TILE_CACHE_SIZE
    memory[labels["tile_cache"] + index] = SKY      # as a dig changes the tile cache too
    memory[labels["tile_cache_shapes"] + index] = BACKGROUND_SKY
    frames = settle(game)

    expected = [[Cell(terrain=c.terrain, piece=c.piece) for c in row] for row in before]
    expected[cut[1] - y0][cut[0] - x0] = Cell()
    support.collapse(expected, support.GAME_SPAN, (cut[0] - x0, cut[1] - y0), 10 ** 6)
    actual = cells_of(game.tile_at, x0, x1, y0, y1)
    assert [[c.piece for c in row] for row in actual] == [[c.piece for c in row] for row in expected]
    fell = sum(1 for a, b in zip(sum(before, []), sum(actual, [])) if a.piece and not b.piece)
    assert fell == 1 + TRUNKS[trunk] - 1 + 6, "the trunk above the cut and the canopy"

    strength = support.strengths(expected, support.GAME_SPAN)
    for y in range(y0, y1):
        for x in range(x0, x1):
            material, shape = game.tile_at(x, y)
            if material in PIECES:
                assert shape & STRENGTH_BITS == strength[y - y0, x - x0], (x, y)

    for y in range(game.byte("cached_top"), game.byte("cached_bottom") + 1):
        for x in range(game.byte("cached_left"), game.byte("cached_right") + 1):
            index = (y % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + x % TILE_CACHE_SIZE
            held = memory[labels["tile_cache"] + index], memory[labels["tile_cache_shapes"] + index]
            assert held == game.tile_at(x, y), (x, y)
    assert game.byte("support_lost") == 0
    print(f"\n{fell} pieces fell over {frames} frames")


def test_generated_trees_hold_their_strengths():
    """Each generated tree part's strength is the model's."""
    for trunk, height in TRUNKS.items():
        x0, x1 = trunk - 1, trunk + 2
        y0, y1 = HEIGHTS[trunk] - height - 4, max(HEIGHTS[x0:x1]) + 2
        cells = cells_of(generate_tile, x0, x1, y0, y1)
        strength = support.strengths(cells, support.GAME_SPAN)
        for y in range(y0, y1):
            for x in range(x0, x1):
                material, shape = generate_tile(x, y)
                if material in PIECES:
                    assert shape & STRENGTH_BITS == strength[y - y0, x - x0], (trunk, x, y)


def test_digging_at_a_tree_fells_it():
    """From the start, face the tree beside the miner and dig: its root
    breaks for wood, and the rest of it falls."""
    from stratagem.build import build
    from stratagem.camera import INPUT_ACTION, INPUT_LEFT
    game = ParasiteGame(build())
    labels, memory = game.labels, game.memory
    trunk = 127
    for _ in range(12):
        game.frame(INPUT_LEFT | INPUT_ACTION)
        game.host.check_cache()
    assert game.byte("wood") >= 1, "no wood"
    settle(game)
    ground = HEIGHTS[trunk]
    left = [(x, y) for x in range(trunk - 1, trunk + 2) for y in range(ground - 10, ground)
            if game.tile_at(x, y)[0] in PIECES]
    assert left == [], "part of the tree is still standing"
    for y in range(game.byte("cached_top"), game.byte("cached_bottom") + 1):
        for x in range(game.byte("cached_left"), game.byte("cached_right") + 1):
            index = (y % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + x % TILE_CACHE_SIZE
            held = memory[labels["tile_cache"] + index], memory[labels["tile_cache_shapes"] + index]
            assert held == game.tile_at(x, y), (x, y)
    assert game.byte("support_lost") == 0
