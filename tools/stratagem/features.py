"""Features: pieces the generator places, a model (docs/tile-set.md).

A feature is a small template of pieces anchored to the ground. The first
are trees on the surface: a root on the grass, a trunk of 1 to 4 tiles and a
canopy three tiles wide and two high, as the piece lab draws them.

Where trees stand is decided once for the whole world, a column at a time,
as the surface heights are: a column may hold a trunk if the hash says so,
it is far enough from the last trunk that canopies don't overlap, and the
ground beside it is low enough for the canopy to clear it. From that comes
COVER, a table of a byte a column (on the 6502): the tree that covers the
column, if any, as its trunk's offset (-1, 0, +1) and height. So whether a
tile is part of a tree takes one look-up and a subtraction from the surface
height: no search of the columns around.
"""

from __future__ import annotations

from stratagem.world import HEIGHTS, PERM, WORLD_SIZE, generate_material
from stratagem.tiles import GRASS, SKY

TREE_CHANCE = 90            # a trunk where the hash is below this, of 256
TREE_SALT = 0x5A
TREE_SPACING = 3            # columns between trunks, at least
TRUNK_MIN, TRUNK_MAX = 1, 4  # trunk tiles, between the root and the canopy
CANOPY_ROWS = 2


def _trunks() -> dict[int, int]:
    """Trunk column -> trunk height, left to right."""
    trunks = {}
    last = -TREE_SPACING
    for x in range(2, WORLD_SIZE - 2):
        fine = PERM[x ^ TREE_SALT]
        if fine >= TREE_CHANCE or x - last < TREE_SPACING:
            continue
        ground = HEIGHTS[x]
        if generate_material(x, ground) != GRASS:
            continue
        height = TRUNK_MIN + (PERM[fine] & 3) % (TRUNK_MAX - TRUNK_MIN + 1)
        canopy_bottom = ground - 2 - height
        # The canopy must clear the ground beside the trunk.
        if any(HEIGHTS[x + dx] <= canopy_bottom for dx in (-1, 1)):
            continue
        trunks[x] = height
        last = x
    return trunks


TRUNKS = _trunks()


def _cover() -> list[tuple[int, int] | None]:
    cover: list[tuple[int, int] | None] = [None] * WORLD_SIZE
    for x, height in TRUNKS.items():
        for dx in (-1, 0, 1):
            assert cover[x + dx] is None, "canopies overlap"
            cover[x + dx] = (x, height)
    return cover


COVER = _cover()            # each column's tree: (trunk column, trunk height), or None


def feature_at(x: int, y: int) -> str | None:
    """The piece the generator puts at (x, y), if any."""
    tree = COVER[x]
    if tree is None:
        return None
    trunk, height = tree
    up = HEIGHTS[trunk] - y         # rows above the trunk's grass
    if x == trunk:
        if up == 1:
            return "root"
        if 2 <= up <= 1 + height:
            return "trunk, knot" if (PERM[y ^ x] & 3) == 0 else "trunk"
    side = {-1: " left", 0: "", 1: " right"}[x - trunk]
    if up == 2 + height:
        return "canopy over trunk" if x == trunk else "canopy" + side
    if up == 3 + height:
        return "canopy top" + side
    return None


def tile_at(x: int, y: int) -> tuple[int | None, str | None]:
    """The generated world with its features: (terrain material or None,
    piece or None). A feature only takes the place of sky."""
    material = generate_material(x, y)
    piece = feature_at(x, y)
    if piece is not None and material == SKY:
        return None, piece
    return (None if material == SKY else material), None
