"""Features: pieces the generator places (docs/tile-set.md), by name, for
the labs. The generator itself is world.py; the first features are its
trees (world.TRUNKS, world.COVER, world.tree_part).
"""

from __future__ import annotations

from stratagem.tiles import MATERIAL_NAMES, PIECES
from stratagem.world import COVER, TREE_SPACING, TRUNK_MAX, TRUNKS, generate_tile

__all__ = ["COVER", "TREE_SPACING", "TRUNK_MAX", "TRUNKS", "feature_at", "tile_at"]


def feature_at(x: int, y: int) -> str | None:
    """The name of the piece the generator puts at (x, y), if any."""
    material, _ = generate_tile(x, y)
    return MATERIAL_NAMES[material] if material in PIECES else None


def tile_at(x: int, y: int) -> tuple[int | None, str | None]:
    """The generated world as (terrain material or None, piece name or
    None): sky is neither."""
    from stratagem.tiles import SKY
    material, _ = generate_tile(x, y)
    if material in PIECES:
        return None, MATERIAL_NAMES[material]
    return (None if material == SKY else material), None
