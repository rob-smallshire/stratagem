"""A model of digging and placing in asm/actions.asm, exactly as the 6502
does it.

Each frame, after the player moves: if the cooldown is running, it counts
down and nothing happens. Otherwise ACTION (L) digs and PLACE (SPACE)
places, at a tile chosen by aiming: DOWN (M) aims at the tile holding the
line just below the feet, UP (K) the line just above the head; otherwise
the aim is the column holding the pixel just ahead, in the direction faced,
where digging takes the diggable tile with the most left (the lowest, of
equals), so that a wall as high as the player is cut back evenly, and
placing takes the lowest empty one, from the feet up to the head. (A partly dug tile may hold some of the
player, in its dug part; it can still be dug. A tile is only placed where
it would not overlap the player.)

Digging diagonally, with LEFT or RIGHT and DOWN or UP held, makes a sloping
tunnel, a column at a time: in the column beyond the player, first the
step the ground should slope through is shaped into a 45 degree ramp, then
the tiles above it are cleared, lowest first, up to the head (going up, a
tile higher), so that, still walking, the player moves down (or up) the
ramp into the space (see diagonal).

Digging erodes the tile by quarters, from the side the player digs from
(digging rightwards erodes it from the left, downwards from the top), or if
it is already shaped, from the side its shape was eroded from:
QUARTERS_PER_DIG of them, by how hard the material is. So soft ground goes
in one dig and stone in four, and you see it go. When nothing is left the
tile is empty (sky or cave, by its background), and a block goes into the
inventory (up to INVENTORY_MAX). Each dig starts a cooldown. Placing puts
whole SOIL in an empty tile (AIR or SKY), using a block. If the world has
no room for a change, nothing happens.
"""

from __future__ import annotations

from dataclasses import dataclass

from stratagem.camera import INPUT_ACTION, INPUT_DOWN, INPUT_LEFT, INPUT_PLACE, INPUT_RIGHT, INPUT_UP
from stratagem.player import PLAYER_HEIGHT, PLAYER_WIDTH, TILE_HEIGHT, TILE_WIDTH, Player
from stratagem.tiles import (AIR, DIGGABLE, FROM_BOTTOM, FROM_LEFT, FROM_RIGHT, FROM_TOP, GEM, GRASS, ORE,
                             QUARTER_LINES, QUARTER_PIXELS, SHAPE_BITS, SHAPE_FULL, SKY, SOIL, STONE, background,
                             dig_shape, solid_count, solid_quarter_cells)
from stratagem.world import RAMP_TOP_LEFT, RAMP_TOP_RIGHT, World, background_bits

QUARTERS_PER_DIG = {GRASS: 4, SOIL: 2, STONE: 1, ORE: 1, GEM: 1}
assert set(QUARTERS_PER_DIG) == set(DIGGABLE)
DIG_FRAMES = 8
PLACE_FRAMES = 6
EMPTY = frozenset({AIR, SKY})
PLACED_TILE = SOIL
INVENTORY_MAX = 99

NONE, DIG, PLACE = 0, 1, 2


@dataclass(frozen=True)
class Hands:
    inventory: int = 0
    cooldown: int = 0


def _ahead(player: Player, wanted, most_left_of=None) -> tuple[int, int] | None:
    """In the column ahead, from the feet up to the head, the tile `wanted`
    accepts: with the most solid left, by tile_at most_left_of, if given (the
    lowest, of equals), otherwise the lowest."""
    px, py = player.px, player.py
    column = (px + PLAYER_WIDTH) // TILE_WIDTH if player.facing > 0 else (px - 1) // TILE_WIDTH
    best, best_left = None, -1
    for row in range((py + PLAYER_HEIGHT - 1) // TILE_HEIGHT, py // TILE_HEIGHT - 1, -1):
        if wanted(column, row):
            if most_left_of is None:
                return column, row
            left = solid_count(*most_left_of(column, row))
            if left > best_left:
                best, best_left = (column, row), left
    return best


def aim(player: Player, inputs: int, wanted, most_left_of=None) -> tuple[int, int] | None:
    px, py = player.px, player.py
    middle = (px + PLAYER_WIDTH // 2) // TILE_WIDTH
    if inputs & INPUT_DOWN:
        target = middle, (py + PLAYER_HEIGHT) // TILE_HEIGHT
    elif inputs & INPUT_UP:
        target = middle, (py - 1) // TILE_HEIGHT
    else:
        return _ahead(player, wanted, most_left_of)
    return target if wanted(*target) else None


def _first_obstruction(tile_at, left: int, right: int, top: int, bottom: int, dx: int,
                       keep_row: int = -1, keep_columns: range = range(0)) -> tuple[int, int] | None:
    """The diggable tile with solid parts within a rectangle (in pixels and
    lines, right and bottom exclusive) with the most solid left; of equals,
    the first met scanning the lowest row first, and in a row, the nearest
    column to the player first (columns in the direction dx). Tiles in
    keep_row and keep_columns are skipped."""
    columns = range(left // TILE_WIDTH, (right - 1) // TILE_WIDTH + 1)
    best, best_left = None, -1
    for ty in range((bottom - 1) // TILE_HEIGHT, top // TILE_HEIGHT - 1, -1):
        for tx in columns if dx > 0 else reversed(columns):
            if (ty == keep_row and tx in keep_columns) or not _in_world(tx, ty):
                continue
            material, shape = tile_at(tx, ty)
            if material not in QUARTERS_PER_DIG:
                continue
            for row, column in solid_quarter_cells(material, shape):
                x0, y0 = tx * TILE_WIDTH + column * QUARTER_PIXELS, ty * TILE_HEIGHT + row * QUARTER_LINES
                if x0 < right and x0 + QUARTER_PIXELS > left and y0 < bottom and y0 + QUARTER_LINES > top:
                    left_here = solid_count(material, shape)
                    if left_here > best_left:
                        best, best_left = (tx, ty), left_here
                    break
    return best


def diagonal(player: Player, dx: int, dy: int, tile_at) -> tuple[tuple[int, int] | None, int | None]:
    """Where digging diagonally works next: (a step to shape, its ramp), or
    (a tile to clear, None), or (None, None).

    Going down, the path is a tile across at the player's height, then a
    tile down; going up, a tile up, then across. Whatever is solid in that
    path is cleared, lowest first; but first the step is shaped into a 45
    degree ramp, if it is whole: going down, the floor under the player's
    leading edge (which is never cleared), going up, the tile ahead at the
    feet, which the player then walks up.
    """
    px, py = player.px, player.py
    ground = py + PLAYER_HEIGHT                 # the line just below the feet
    across = dx * TILE_WIDTH
    left, right = min(px, px + across), max(px, px + across) + PLAYER_WIDTH
    if dy > 0:
        edge = (px + PLAYER_WIDTH - 1) // TILE_WIDTH if dx > 0 else px // TILE_WIDTH
        step = (edge, ground // TILE_HEIGHT)
        ramp = RAMP_TOP_RIGHT if dx > 0 else RAMP_TOP_LEFT
    else:
        ahead = (px + PLAYER_WIDTH - 1) // TILE_WIDTH + 1 if dx > 0 else px // TILE_WIDTH - 1
        step = (ahead, ground // TILE_HEIGHT - 1)
        ramp = RAMP_TOP_LEFT if dx > 0 else RAMP_TOP_RIGHT
    if _in_world(*step):
        material, shape = tile_at(*step)
        if material in QUARTERS_PER_DIG and shape & SHAPE_BITS == SHAPE_FULL:
            return step, ramp
    if dy > 0:
        # Across, then down; but never the floor under the player.
        floor_row = ground // TILE_HEIGHT
        under = range(px // TILE_WIDTH, (px + PLAYER_WIDTH - 1) // TILE_WIDTH + 1)
        target = (_first_obstruction(tile_at, left, right, py, ground, dx, floor_row, under)
                  or _first_obstruction(tile_at, px + across, px + across + PLAYER_WIDTH,
                                        py, ground + TILE_HEIGHT, dx, floor_row, under))
    else:
        # Up, then across.
        target = _first_obstruction(tile_at, left, right, py - TILE_HEIGHT, ground - TILE_HEIGHT, dx)
    return target, None


def _in_world(x: int, y: int) -> bool:
    return 0 <= x < 256 and 0 <= y < 256


def overlaps_player(player: Player, x: int, y: int) -> bool:
    px, py = player.px, player.py
    return (px < (x + 1) * TILE_WIDTH and px + PLAYER_WIDTH > x * TILE_WIDTH
            and py < (y + 1) * TILE_HEIGHT and py + PLAYER_HEIGHT > y * TILE_HEIGHT)


def dig_direction(player: Player, inputs: int) -> int:
    """The side of the tile a dig removes first: the side the player is on."""
    if inputs & INPUT_DOWN:
        return FROM_TOP
    if inputs & INPUT_UP:
        return FROM_BOTTOM
    return FROM_LEFT if player.facing > 0 else FROM_RIGHT


def diggable(tile: tuple[int, int]) -> bool:
    return tile[0] in QUARTERS_PER_DIG


def act(hands: Hands, player: Player, inputs: int, world: World) -> tuple[Hands, int, tuple[int, int] | None]:
    """One frame's digging or placing. Returns the new hands, what was done
    and where, changing the world."""
    if hands.cooldown:
        return Hands(hands.inventory, hands.cooldown - 1), NONE, None

    in_world = _in_world
    if inputs & INPUT_ACTION:
        dx = (1 if inputs & INPUT_RIGHT else 0) - (1 if inputs & INPUT_LEFT else 0)
        dy = (1 if inputs & INPUT_DOWN else 0) - (1 if inputs & INPUT_UP else 0)
        if dx and dy:
            target, ramp = diagonal(player, dx, dy, world.tile_at)
            side = FROM_LEFT if dx > 0 else FROM_RIGHT
        else:
            target = aim(player, inputs, lambda x, y: in_world(x, y) and diggable(world.tile_at(x, y)),
                         most_left_of=world.tile_at)
            ramp, side = None, dig_direction(player, inputs)
        if target is not None:
            material, shape = world.tile_at(*target)
            behind = background_bits(*target)
            if ramp is not None:
                if world.set_tile(*target, (material, ramp | behind)):
                    return Hands(hands.inventory, DIG_FRAMES), DIG, target
                return hands, NONE, None
            left = dig_shape(shape & SHAPE_BITS, QUARTERS_PER_DIG[material], side)
            tile = (background(behind), SHAPE_FULL | behind) if left is None else (material, left | behind)
            if world.set_tile(*target, tile):
                inventory = min(hands.inventory + 1, INVENTORY_MAX) if left is None else hands.inventory
                return Hands(inventory, DIG_FRAMES), DIG, target
    elif inputs & INPUT_PLACE and hands.inventory:
        target = aim(player, inputs, lambda x, y: in_world(x, y) and world.tile_at(x, y)[0] in EMPTY
                     and not overlaps_player(player, x, y))
        if target is not None and world.set_tile(*target, (PLACED_TILE, SHAPE_FULL | background_bits(*target))):
            return Hands(hands.inventory - 1, PLACE_FRAMES), PLACE, target
    return hands, NONE, None
