"""Items lying in the world: what a felled tree drops, a model of
asm/items.asm, exactly as the 6502 does it.

Each part of a tree's trunk that breaks, dug or fallen (actions.CHOPPABLE
less the canopy), drops a piece of wood: an item, ITEM_WIDTH x ITEM_HEIGHT
(pixels x lines), at the bottom of the tile it broke from.

Items fall, under GRAVITY, at most ITEM_MAX_FALL a frame (a quarter-cell,
so nothing is passed through), until something holds one of an item's
bottom corners: a solid quarter-cell under it, or the top of another item.
Items pile up, as sand does: an item lies still only if both its corners
are held, at the same height, and not both by the same item (the ground
holds both, or two items between them). Otherwise it comes to that height
and slides SLIDE pixels towards the side not held (off a single item it
lies squarely on, the way it overhangs it, or by its place in the list),
and falls again: so logs dropped on one spot pile up into a cone, and slide
down slopes. A slide into solid ground or another item is not made; the
item lies still.
Only items over the tile cache move (the 6502 looks at the tile cache);
others wait. The miner picks up an item by touching it (their boxes
overlap): it goes into the inventory. At most ITEM_MAX lie in the world:
more go straight into the inventory.

Each frame, after the miner moves and acts, every item falls, in the
list's order (each against the others as they are by then), and then is
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
ITEM_HEIGHT = 5             # lines
ITEM_MAX_FALL = QUARTER_LINES * 16      # sixteenths of a line a frame
ITEM_OFFSET_X = 2           # from its tile's left, so that it is byte aligned
SLIDE = 2                   # pixels a frame, sideways: a byte of MODE 2
TERRAIN = -1                # what holds a corner: the ground, or an item's index
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


def _held(items: list[Item], i: int, px: int, old_below: int, below: int,
          tile_at: TileAt) -> tuple[int, int] | None:
    """What holds item i's corner over pixel px, moving its bottom from line
    old_below to line below: (the line its bottom comes to, TERRAIN or the
    holding item's index), the highest; or None. The ground wins a tie, and
    of items the first."""
    held = None
    if solid_at(tile_at, px, below):
        held = below & -QUARTER_LINES, TERRAIN
    for j, other in enumerate(items):
        if j != i and other.x <= px < other.x + ITEM_WIDTH and old_below <= other.py <= below:
            if held is None or other.py < held[0]:
                held = other.py, j
    return held


def _blocked(items: list[Item], i: int, tile_at: TileAt, px: int, top: int) -> bool:
    """Whether item i, with its top at line `top`, would overlap solid ground
    or another item in pixel column px."""
    if any(solid_at(tile_at, px, line) for line in (top, top + QUARTER_LINES, top + ITEM_HEIGHT - 1)):
        return True
    return any(j != i and other.x <= px < other.x + ITEM_WIDTH and top - ITEM_HEIGHT < other.py < top + ITEM_HEIGHT
               for j, other in enumerate(items))


def fall(items: list[Item], i: int, tile_at: TileAt, in_cache: Callable[[int, int], bool]) -> Item:
    """Item i's frame: it falls, comes to rest or slides; or it waits, if
    the tiles around it aren't all in the tile cache."""
    item = items[i]
    vy = min(item.vy + GRAVITY, ITEM_MAX_FALL)
    y = item.y + vy
    old_below, below = item.py + ITEM_HEIGHT, (y >> 4) + ITEM_HEIGHT
    left, right = item.x, item.x + ITEM_WIDTH - 1
    if not (in_cache((left - SLIDE) // TILE_WIDTH, (item.py - QUARTER_LINES) // TILE_HEIGHT)
            and in_cache((right + SLIDE) // TILE_WIDTH, below // TILE_HEIGHT)):
        return item
    held_left = _held(items, i, left, old_below, below, tile_at)
    held_right = _held(items, i, right, old_below, below, tile_at)
    if held_left is None and held_right is None:
        return replace(item, y=y, vy=vy)
    line = min(held[0] for held in (held_left, held_right) if held is not None)
    top = line - ITEM_HEIGHT
    lying = replace(item, y=top << 4, vy=0)
    left_holds = held_left is not None and held_left[0] == line
    right_holds = held_right is not None and held_right[0] == line
    if left_holds and right_holds:
        under = held_left[1]
        if under == TERRAIN or held_right[1] != under:
            return lying                                    # held at both corners
        # Squarely on a single item: off it, the way it overhangs it.
        other = items[under].x
        step = SLIDE if item.x > other or (item.x == other and i & 1) else -SLIDE
    else:
        step = SLIDE if left_holds else -SLIDE
    edge = right + step if step > 0 else left + step
    if _blocked(items, i, tile_at, edge, top):
        return lying
    return replace(lying, x=item.x + step)


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
        item = fall(items, i, tile_at, in_cache)
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
