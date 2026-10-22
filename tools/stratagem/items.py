"""Items lying in the world: what a felled tree drops, a model of
asm/items.asm, exactly as the 6502 does it.

Each part of a tree's trunk that breaks, dug or fallen (actions.CHOPPABLE
less the canopy), drops a piece of wood: an item, ITEM_WIDTH x ITEM_HEIGHT
(pixels x lines), at the bottom of the tile it broke from. Items fall,
under GRAVITY, until the quarter-cell under the middle of an item's bottom
is solid, and lie there; one whose ground is dug away falls again. An item
falls at most ITEM_MAX_FALL a frame, a quarter-cell, so it can't pass
through one. Only items over the tile cache move (the 6502 looks at the
tile cache); others wait. The miner picks up an item by touching it (their
boxes overlap): it goes into the inventory. At most ITEM_MAX lie in the
world: more go straight into the inventory.

Each frame, after the miner moves and acts, every item falls and then is
picked up if touched; an item picked up is replaced in the list by the
last, which is then dealt with in its turn.

The host draws the items in view as sprites: each at a view column and
line, if it lies wholly within the view, clear of the columns the camera
can scroll in (MAX_STEP_X at each side), so that nothing drawn over an
item's saved background is ever restored over.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from stratagem.camera import MAX_STEP_X
from stratagem.player import GRAVITY, PLAYER_HEIGHT, PLAYER_WIDTH, TILE_HEIGHT, TILE_WIDTH, Player
from stratagem.screen import VIEW_COLUMNS, VIEW_ROWS
from stratagem.tiles import CANOPY_LEFT, QUARTER_LINES, QUARTER_PIXELS, QUARTERS, ROOT, TRUNK, TRUNK_KNOT, solid_quarter_cells

ITEM_MAX = 8
ITEM_WIDTH = 6              # pixels: three bytes of MODE 2
ITEM_HEIGHT = 6             # lines
ITEM_MAX_FALL = QUARTER_LINES * 16      # sixteenths of a line a frame
ITEM_OFFSET_X = 2           # from its tile's left, so that it is byte aligned
WOOD = 0                    # the kinds of item
DROPS = {ROOT: WOOD, TRUNK: WOOD, TRUNK_KNOT: WOOD}     # what each material drops
assert CANOPY_LEFT not in DROPS
VIEW_LINES = VIEW_ROWS * 8

TileAt = Callable[[int, int], tuple[int, int]]


@dataclass(frozen=True)
class Item:
    x: int                  # pixels
    y: int                  # sixteenths of a line
    vy: int = 0             # sixteenths of a line a frame, downwards
    kind: int = WOOD

    @property
    def py(self) -> int:
        return self.y >> 4


def dropped(tx: int, ty: int, kind: int = WOOD) -> Item:
    """The item dropped from tile (tx, ty): at the bottom of the tile."""
    return Item(tx * TILE_WIDTH + ITEM_OFFSET_X, ((ty + 1) * TILE_HEIGHT - ITEM_HEIGHT) << 4, 0, kind)


def drop(items: list[Item], tx: int, ty: int, kind: int = WOOD) -> tuple[list[Item], int]:
    """Drop an item from tile (tx, ty); returns the items and how many went
    straight into the inventory instead (the list being full)."""
    if len(items) < ITEM_MAX:
        return items + [dropped(tx, ty, kind)], 0
    return items, 1


def solid_at(tile_at: TileAt, px: int, line: int) -> bool:
    """Whether the quarter-cell holding pixel px of line `line` is solid."""
    row, column = (line // QUARTER_LINES) % QUARTERS, (px // QUARTER_PIXELS) % QUARTERS
    return (row, column) in solid_quarter_cells(*tile_at(px // TILE_WIDTH, line // TILE_HEIGHT))


def fall(item: Item, tile_at: TileAt, in_cache: Callable[[int, int], bool]) -> Item:
    """One frame's fall, if the tile under the item's middle is in the tile
    cache."""
    vy = min(item.vy + GRAVITY, ITEM_MAX_FALL)
    y = item.y + vy
    middle, below = item.x + ITEM_WIDTH // 2, (y >> 4) + ITEM_HEIGHT
    if not in_cache(middle // TILE_WIDTH, below // TILE_HEIGHT):
        return item
    if solid_at(tile_at, middle, below):
        return replace(item, y=((below & -QUARTER_LINES) - ITEM_HEIGHT) << 4, vy=0)
    return replace(item, y=y, vy=vy)


def touches(item: Item, player: Player) -> bool:
    return (item.x < player.px + PLAYER_WIDTH and player.px < item.x + ITEM_WIDTH
            and item.py < player.py + PLAYER_HEIGHT and player.py < item.py + ITEM_HEIGHT)


def step(items: list[Item], player: Player, tile_at: TileAt,
         in_cache: Callable[[int, int], bool]) -> tuple[list[Item], int]:
    """One frame: every item falls, and is picked up if the player touches
    it. Returns the items left and how many were picked up."""
    items = list(items)
    picked = 0
    i = 0
    while i < len(items):
        item = fall(items[i], tile_at, in_cache)
        if touches(item, player):
            picked += 1
            items[i] = items[-1]
            items.pop()
            continue
        items[i] = item
        i += 1
    return items, picked


def shown(items: list[Item], camera_x: int, camera_y: int) -> list[tuple[int, int, int]]:
    """The items the host draws, in order: (view column, view line, kind)."""
    result = []
    for item in items:
        column = (item.x >> 1) - camera_x
        line = item.py - camera_y * 8
        if MAX_STEP_X <= column <= VIEW_COLUMNS - MAX_STEP_X - ITEM_WIDTH // 2 and 0 <= line <= VIEW_LINES - ITEM_HEIGHT:
            result.append((column, line, item.kind))
    return result
