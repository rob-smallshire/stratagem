"""Support: how pieces are held up (docs/tile-set.md, Support), a model.

Every kind of piece says how it is held:

    BELOW   by what is under it: tree trunks, wooden ladders, walls...
    ABOVE   by what is over it: ropes, rope ladders, vines
    SPAN    by what is under it, or by a neighbour beside it, one step
            further from the ground: blocks, roofs, platforms, canopy
    ANY     by any neighbour that holds things: torches

and what it holds in turn: ALL (anything, on any side: ground, blocks,
trunks), FAMILY (only its own family, the way that family is held: a rope
holds a rope below it, a ladder a ladder above it), UP (only its own family,
above it: the leaves at a canopy's edge, so that trees don't hold up each
other's leaves), or NOTHING.

Each piece has a strength. Terrain is an anchor, at full strength (the
span); a piece held from below or above takes its holder's strength; one
held from the side takes its holder's less one. A piece whose strength is 0
isn't held, and falls. So a roof reaches `span` tiles from a wall and no
further; and strength only comes from the ground, so nothing holds itself
up.

The world here is a grid of piece_lab.Cell: terrain (a solid material), a
piece (by name), or neither.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from stratagem.tiles import PASSABLE

BELOW, ABOVE, SPAN, ANY = "below", "above", "span", "any"
GAME_SPAN = 5               # the game's span (decided by the feature lab)
ALL, FAMILY, UP, NOTHING = "all", "family", "up", "nothing"


@dataclass(frozen=True)
class Kind:
    held: str           # BELOW, ABOVE, SPAN or ANY
    bears: str          # ALL, FAMILY or NOTHING
    family: str = ""    # pieces of a family hold each other (FAMILY)


def _kinds() -> dict[str, Kind]:
    kinds = {
        "trunk": Kind(BELOW, ALL, "tree"),
        "trunk, knot": Kind(BELOW, ALL, "tree"),
        "root": Kind(BELOW, ALL, "tree"),
        "vine": Kind(ABOVE, FAMILY, "vine"),
        "vine end": Kind(ABOVE, FAMILY, "vine"),
        "rope": Kind(ABOVE, FAMILY, "rope"),
        "rope end": Kind(ABOVE, FAMILY, "rope"),
        "ladder": Kind(BELOW, FAMILY, "ladder"),
        "planks": Kind(SPAN, ALL, "block"),
        "bricks": Kind(SPAN, ALL, "block"),
        "platform": Kind(SPAN, ALL, "block"),
        "window": Kind(SPAN, ALL, "block"),
        "torch": Kind(ANY, NOTHING),
        "grass tuft": Kind(BELOW, NOTHING),
        "mushroom": Kind(BELOW, NOTHING),
        "chest": Kind(BELOW, NOTHING),
        "door bottom": Kind(BELOW, FAMILY, "door"),
        "door top": Kind(BELOW, FAMILY, "door"),
        "door open bottom": Kind(BELOW, FAMILY, "door"),
        "door open top": Kind(BELOW, FAMILY, "door"),
    }
    for side in ("left", "right"):
        kinds[f"bench {side}"] = Kind(BELOW, NOTHING)
        kinds[f"anvil {side}"] = Kind(BELOW, NOTHING)
    for name in ("top left", "top right", "left", "right"):
        kinds[f"furnace {name}"] = Kind(BELOW, FAMILY, "furnace")
    kinds["canopy over trunk"] = Kind(SPAN, FAMILY, "canopy")   # holds the leaves beside and above it
    for name in ("top left", "top", "top right", "left", "right"):
        kinds[f"canopy {name}"] = Kind(SPAN, UP, "canopy")
    return kinds


KINDS = _kinds()

# (dx, dy) of the holder, for each way of being held; ANY is every side
BELOW_HOLDER, ABOVE_HOLDER, SIDES = (0, 1), (0, -1), ((-1, 0), (1, 0))


def is_anchor(cell) -> bool:
    """Terrain that holds anything: a solid material, not air or water."""
    return cell.terrain is not None and cell.terrain not in PASSABLE


def holds(holder, held: Kind, side: tuple[int, int]) -> bool:
    """Whether the cell `holder`, on `side` of a piece of kind `held`, can
    hold it there."""
    if is_anchor(holder):
        return True
    if holder.piece is None or holder.terrain is not None:
        return False
    kind = KINDS[holder.piece]
    if kind.bears == ALL:
        return True
    if kind.bears == FAMILY and kind.family == held.family:
        way = {BELOW: (BELOW_HOLDER,), ABOVE: (ABOVE_HOLDER,), SPAN: (BELOW_HOLDER,) + SIDES}.get(held.held, ())
        return side in way
    if kind.bears == UP and kind.family == held.family:
        return side == BELOW_HOLDER
    return False


def strengths(cells, span: int) -> np.ndarray:
    """Each cell's strength: span for terrain that holds, and for each piece
    the most it can get from its holders (0 if it isn't held); 0 elsewhere.
    Worked out to a fixed point from nothing, so strength only ever comes
    from the ground."""
    height, width = len(cells), len(cells[0])
    strength = np.zeros((height, width), dtype=int)
    pieces = []
    for y in range(height):
        for x in range(width):
            if is_anchor(cells[y][x]):
                strength[y, x] = span
            elif cells[y][x].piece is not None:
                pieces.append((x, y, KINDS[cells[y][x].piece]))

    def given(x, y, kind, dx, dy, step):
        hx, hy = x + dx, y + dy
        if not (0 <= hx < width and 0 <= hy < height) or not holds(cells[hy][hx], kind, (dx, dy)):
            return 0
        return max(0, strength[hy, hx] - step)

    changed = True
    while changed:
        changed = False
        for x, y, kind in pieces:
            if kind.held == BELOW:
                best = given(x, y, kind, *BELOW_HOLDER, 0)
            elif kind.held == ABOVE:
                best = given(x, y, kind, *ABOVE_HOLDER, 0)
            elif kind.held == SPAN:
                best = max([given(x, y, kind, *BELOW_HOLDER, 0)] + [given(x, y, kind, dx, dy, 1) for dx, dy in SIDES])
            else:
                best = max(given(x, y, kind, dx, dy, 0) for dx, dy in (BELOW_HOLDER, ABOVE_HOLDER) + SIDES)
            if best > strength[y, x]:
                strength[y, x] = best
                changed = True
    return strength


def unheld(cells, span: int) -> list[tuple[int, int]]:
    """The pieces that aren't held."""
    strength = strengths(cells, span)
    return [(x, y) for y, row in enumerate(cells) for x, cell in enumerate(row)
            if cell.piece is not None and cell.terrain is None and strength[y, x] == 0]


def collapse(cells, span: int, origin: tuple[int, int], per_frame: int) -> list[list[tuple[int, int]]]:
    """Let what isn't held fall, at most per_frame pieces a frame, nearest
    origin first (as a queue would, from the change). Changes cells; returns
    the pieces that fell in each frame."""
    frames = []
    while True:
        falling = sorted(unheld(cells, span), key=lambda p: (abs(p[0] - origin[0]) + abs(p[1] - origin[1]), p))
        if not falling:
            return frames
        frame = falling[:per_frame]
        for x, y in frame:
            cells[y][x].piece = None
        frames.append(frame)
