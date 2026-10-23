"""Items thrown out into the world: what a felled tree drops, a model of
asm/items.asm, exactly as the 6502 does it.

Each part of a tree's trunk that breaks, dug or fallen (DROPS), throws out
a piece of wood: an item, ITEM_WIDTH x ITEM_HEIGHT (pixels x lines),
sprayed from the tile it broke from, upwards and to one side by the next
of SPRAY_VX and SPRAY_VY (a count of items thrown picks them). An item
lives through three states, so that the miner sees how many there are,
and then they are gone:

- FLYING: under GRAVITY, at most ITEM_MAX_FALL a frame (a quarter-cell, so
  nothing is passed through), and at most a quarter-cell across. Moving
  across into a solid quarter-cell (at the item's middle line), it bounces
  back at half speed; moving down onto one (under its bottom's middle), it
  lands on it, and bounces up at half speed, losing half its speed across,
  or, if slower than BOUNCE_MIN, comes to rest; moving up into one (at its
  top's middle), it stops rising. Items pass through each other. One still
  flying after FLY_FRAMES frames (bouncing down a slope) is gathered.
- RESTING: it lies still for REST_FRAMES frames.
- GATHERING: it flies to the miner, through anything, faster each frame
  (to GATHER_MAX pixels and lines a frame, on each axis), towards the
  middle of his box; when it touches him, he has it: it goes into the
  inventory.

The 6502 looks at the tile cache: an item flying where the tile it would
look at isn't in the tile cache is gathered at once. At most ITEM_MAX are
out at once: more go straight into the inventory.

Each frame, after the miner moves and acts, every item moves, in the
list's order; an item gathered in is replaced in the list by the last,
which then moves in its turn.

The host draws the items in view as sprites: each at a view column and
line, if it lies wholly within the view, clear of the columns the camera
can scroll in (MAX_STEP_X at each side), so that nothing drawn over an
item's saved background is ever restored over.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from stratagem.camera import MAX_STEP_X
from stratagem.inventory import KIND_WOOD
from stratagem.player import GRAVITY, PLAYER_HEIGHT, PLAYER_WIDTH, TILE_HEIGHT, TILE_WIDTH, Player
from stratagem.screen import VIEW_COLUMNS, VIEW_ROWS
from stratagem.tiles import CANOPY_LEFT, QUARTER_LINES, QUARTER_PIXELS, QUARTERS, ROOT, TRUNK, TRUNK_KNOT, solid_quarter_cells

ITEM_MAX = 8
ITEM_WIDTH = 6              # pixels: three bytes of MODE 2
ITEM_HEIGHT = 5             # lines
ITEM_OFFSET_X = 1           # from its tile's left: in its middle
ITEM_MAX_FALL = QUARTER_LINES * 16      # sixteenths of a line a frame
SPRAY_VX = (-12, 8, -4, 14, -8, 4, 12, -14)     # sixteenths of a pixel a frame
SPRAY_VY = (-40, -52, -34, -46)                 # sixteenths of a line a frame
assert all(abs(vx) <= QUARTER_PIXELS * 16 for vx in SPRAY_VX)
BOUNCE_MIN = 32             # a landing slower than this comes to rest
FLY_FRAMES = 40             # flying, at most
REST_FRAMES = 25            # half a second
GATHER_MAX = 4              # pixels and lines a frame
FLYING, RESTING, GATHERING = 0, 1, 2
WOOD = KIND_WOOD             # the kinds of item are the inventory's (inventory.py)
DROPS = {ROOT: WOOD, TRUNK: WOOD, TRUNK_KNOT: WOOD}     # what each material drops
assert CANOPY_LEFT not in DROPS
VIEW_LINES = VIEW_ROWS * 8

TileAt = Callable[[int, int], tuple[int, int]]
InCache = Callable[[int, int], bool]


@dataclass(frozen=True)
class Item:
    x: int                  # sixteenths of a pixel
    y: int                  # sixteenths of a line
    vx: int = 0             # sixteenths a frame; gathering, its speed in pixels
    vy: int = 0
    state: int = FLYING
    timer: int = 0          # flying: frames flown; resting: frames left
    kind: int = WOOD

    @property
    def px(self) -> int:
        return self.x >> 4

    @property
    def py(self) -> int:
        return self.y >> 4


def thrown(tx: int, ty: int, count: int, kind: int = WOOD) -> Item:
    """The item thrown from tile (tx, ty), the count'th thrown (mod 256)."""
    return Item((tx * TILE_WIDTH + ITEM_OFFSET_X) << 4, ((ty + 1) * TILE_HEIGHT - ITEM_HEIGHT) << 4,
                SPRAY_VX[count % len(SPRAY_VX)], SPRAY_VY[count % len(SPRAY_VY)], FLYING, 0, kind)


def drop(items: list[Item], tx: int, ty: int, count: int, kind: int = WOOD) -> tuple[list[Item], int]:
    """Throw an item from tile (tx, ty); returns the items and how many went
    straight into the inventory instead (the list being full)."""
    if len(items) < ITEM_MAX:
        return items + [thrown(tx, ty, count, kind)], 0
    return items, 1


def solid_at(tile_at: TileAt, px: int, line: int) -> bool:
    """Whether the quarter-cell holding pixel px of line `line` is solid."""
    row, column = (line // QUARTER_LINES) % QUARTERS, (px // QUARTER_PIXELS) % QUARTERS
    return (row, column) in solid_quarter_cells(*tile_at(px // TILE_WIDTH, line // TILE_HEIGHT))


def _gathered(item: Item) -> Item:
    return replace(item, vx=0, vy=0, state=GATHERING, timer=0)


def fly(item: Item, tile_at: TileAt, in_cache: InCache) -> Item:
    """A flying item's frame."""
    if item.timer + 1 >= FLY_FRAMES:
        return _gathered(item)
    x, vx = item.x + item.vx, item.vx
    middle_line = item.py + ITEM_HEIGHT // 2
    if vx:
        edge = (x >> 4) + (ITEM_WIDTH - 1 if vx > 0 else 0)
        if not in_cache(edge // TILE_WIDTH, middle_line // TILE_HEIGHT):
            return _gathered(item)
        if solid_at(tile_at, edge, middle_line):
            x, vx = item.x, -(vx >> 1)
    vy = min(item.vy + GRAVITY, ITEM_MAX_FALL)
    y = item.y + vy
    middle = (x >> 4) + ITEM_WIDTH // 2
    if vy > 0:
        below = (y >> 4) + ITEM_HEIGHT
        if not in_cache(middle // TILE_WIDTH, below // TILE_HEIGHT):
            return _gathered(item)
        if solid_at(tile_at, middle, below):
            y = ((below & -QUARTER_LINES) - ITEM_HEIGHT) << 4
            if vy < BOUNCE_MIN:
                return Item(x, y, 0, 0, RESTING, REST_FRAMES, item.kind)
            vy, vx = -(vy >> 1), vx >> 1
    elif vy < 0:
        top = y >> 4
        if top < 0 or not in_cache(middle // TILE_WIDTH, top // TILE_HEIGHT):
            return _gathered(item)
        if solid_at(tile_at, middle, top):
            y, vy = item.y, 0
    return Item(x, y, vx, vy, FLYING, item.timer + 1, item.kind)


def _towards(position: int, target: int, speed: int) -> int:
    if position < target:
        return min(position + speed, target)
    return max(position - speed, target)


def gather(item: Item, player: Player) -> Item:
    """A gathering item's frame: towards the middle of the miner's box."""
    speed = min(item.vx + 1, GATHER_MAX)
    px = _towards(item.px, player.px + (PLAYER_WIDTH - ITEM_WIDTH) // 2, speed)
    py = _towards(item.py, player.py + (PLAYER_HEIGHT - ITEM_HEIGHT) // 2, speed)
    return replace(item, x=px << 4, y=py << 4, vx=speed)


def touches(item: Item, player: Player) -> bool:
    return (item.px < player.px + PLAYER_WIDTH and player.px < item.px + ITEM_WIDTH
            and item.py < player.py + PLAYER_HEIGHT and player.py < item.py + ITEM_HEIGHT)


def move(item: Item, player: Player, tile_at: TileAt, in_cache: InCache) -> Item:
    """An item's frame, by its state."""
    if item.state == FLYING:
        return fly(item, tile_at, in_cache)
    if item.state == RESTING:
        return replace(item, timer=item.timer - 1) if item.timer > 1 else _gathered(item)
    return gather(item, player)


def step(items: list[Item], player: Player, tile_at: TileAt, in_cache: InCache) -> tuple[list[Item], int]:
    """One frame: every item moves; those gathering that touch the miner are
    his. Returns the items left and how many he has gathered in."""
    items = list(items)
    gathered = 0
    i = 0
    while i < len(items):
        item = move(items[i], player, tile_at, in_cache)
        if item.state == GATHERING and touches(item, player):
            gathered += 1
            items[i] = items[-1]
            items.pop()
            continue
        items[i] = item
        i += 1
    return items, gathered


def shown(items: list[Item], camera_x: int, camera_y: int) -> list[tuple[int, int, int]]:
    """The items the host draws, in order: (view column, view line, kind)."""
    result = []
    for item in items:
        column = (item.px >> 1) - camera_x
        line = item.py - camera_y * 8
        if MAX_STEP_X <= column <= VIEW_COLUMNS - MAX_STEP_X - ITEM_WIDTH // 2 and 0 <= line <= VIEW_LINES - ITEM_HEIGHT:
            result.append((column, line, item.kind))
    return result
