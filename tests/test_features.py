"""Support and features (tools/stratagem/support.py, features.py): the
rules of the model, which the 6502 will be checked against."""

import pytest

from stratagem import features, support
from stratagem.feature_lab import GROUND, copy, flat, put, remove, structures, surface_cells
from stratagem.tiles import GRASS
from stratagem.world import HEIGHTS, generate_material


def roof(width: int):
    """Walls four high, and a roof `width` between them."""
    cells = flat(width + 4)
    for y in range(GROUND - 4, GROUND):
        put(cells, 1, y, "planks")
        put(cells, width + 2, y, "planks")
    for x in range(1, width + 3):
        put(cells, x, GROUND - 5, "bricks")
    return cells


@pytest.mark.parametrize("span", [3, 5])
@pytest.mark.parametrize("width", [4, 6, 8, 10])
def test_a_roof_reaches_the_span_from_each_wall(span, width):
    falling = {x for x, y in support.unheld(roof(width), span)}
    # Tile x (from 2) is x - 1 from the left wall and width + 2 - x from the right.
    expected = {x for x in range(2, width + 2) if min(x - 1, width + 2 - x) >= span}
    assert falling == expected


def test_ropes_hang_ladders_stand_torches_cling():
    cells = flat(10)
    put(cells, 2, GROUND - 4, "planks")         # a plank held only from the side
    for y in range(GROUND - 3, GROUND):
        put(cells, 4, y, "rope")                # a rope with nothing above
        put(cells, 6, y, "ladder")              # a ladder on the ground
    put(cells, 8, GROUND - 2, "torch")          # a torch with nothing beside it
    put(cells, 1, GROUND - 1, "torch")          # ... and one on the ground
    assert set(support.unheld(cells, 3)) == ({(2, GROUND - 4), (8, GROUND - 2)}
                                             | {(4, y) for y in range(GROUND - 3, GROUND)})


def test_nothing_holds_itself_up():
    cells = flat(8)
    for x in range(2, 6):
        put(cells, x, GROUND - 4, "planks")
    put(cells, 3, GROUND - 5, "planks")
    assert len(support.unheld(cells, 5)) == 5


def test_a_felled_tree_takes_its_leaves_but_not_its_neighbours():
    name, cells, at = next(s for s in structures() if s[0].startswith("trees"))
    before = support.unheld(cells, 3)
    remove(cells, at)
    support.collapse(cells, 3, at, 2)
    trunk = at[0]
    left = {(x, y) for y, row in enumerate(cells) for x, c in enumerate(row) if c.piece}
    assert not any(trunk - 1 <= x <= trunk + 1 and y < at[1] for x, y in left), "the felled tree's leaves stayed"
    for neighbour in (trunk - 3, trunk + 5):
        assert (neighbour, GROUND - 5) in left, "a neighbour's leaves fell"
    assert before, "the leaf beyond the canopy's edge was held"


def test_collapse_leaves_only_what_is_held():
    for name, cells, at in structures():
        for span in (3, 5):
            work = copy(cells)
            remove(work, at)
            frames = support.collapse(work, span, at, 2)
            assert all(len(frame) <= 2 for frame in frames)
            assert support.unheld(work, span) == [], name


def test_trees_stand_on_grass_and_dont_overlap():
    assert len(features.TRUNKS) > 20
    trunks = sorted(features.TRUNKS)
    assert all(b - a >= features.TREE_SPACING for a, b in zip(trunks, trunks[1:]))
    for x in trunks:
        assert generate_material(x, HEIGHTS[x]) == GRASS
        assert features.feature_at(x, HEIGHTS[x] - 1) == "root"


def test_generated_trees_are_held():
    for trunk, height in features.TRUNKS.items():
        x0, x1 = trunk - 1, trunk + 2        # its own columns: a neighbour's canopy may touch it
        y0, y1 = HEIGHTS[trunk] - height - 5, max(HEIGHTS[x0:x1]) + 2
        cells = surface_cells(x0, x1, y0, y1)
        pieces = [(x, y) for y, row in enumerate(cells) for x, c in enumerate(row) if c.piece]
        assert len(pieces) == 6 + 1 + height
        assert support.unheld(cells, 3) == [], f"the tree at column {trunk}"
