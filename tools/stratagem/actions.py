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

Digging erodes the tile by quarters from the side nearest the player
(digging rightwards erodes it from the left, downwards from the top):
QUARTERS_PER_DIG of them, by how hard the material is (see
tiles.dig_shape). So soft ground goes
in one dig and stone in four, and you see it go. When nothing is left the
tile is empty (sky or cave, by its background), and one of the kind its
material yields goes into the inventory (inventory.py), and into the hand.
A tree's part breaks whole, at one dig,
leaving it empty, and a trunk's part drops a piece of wood (items.py) for
the miner to gather in; what it held falls (support.py). Only straight digs break parts: digging diagonally
passes through trees, as walking does. In aiming, a tree's part counts as
whole, so beside a tree the root, the lowest, goes first, and the tree
falls. Each dig starts a cooldown. Placing puts a whole block of the kind
in hand (inventory.py) in an empty tile (AIR or SKY); a torch is placed
the same way, or, with no such tile, in the miner's own tile (the one
holding the middle of the player's box), if that is empty, unless there
are TORCH_MAX in the world. If the world has no
room for a change, nothing happens.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from stratagem import inventory
from stratagem.camera import INPUT_ACTION, INPUT_DOWN, INPUT_LEFT, INPUT_PLACE, INPUT_RIGHT, INPUT_UP
from stratagem.player import PLAYER_HEIGHT, PLAYER_WIDTH, TILE_HEIGHT, TILE_WIDTH, Player
from stratagem.tiles import (AIR, DIGGABLE, FROM_BOTTOM, FROM_LEFT, FROM_RIGHT, FROM_TOP, GEM, GRASS, ORE,
                             QUARTER_LINES, QUARTER_PIXELS, QUARTERS, SHAPE_BITS, SHAPE_FULL, SKY, SOIL, STONE,
                             TORCH, TREE_PARTS, background, cut_to, dig_shape, solid_count, solid_quarter_cells)
from stratagem.world import RAMP_TOP_LEFT, RAMP_TOP_RIGHT, World, background_bits

QUARTERS_PER_DIG = {GRASS: 4, SOIL: 2, STONE: 1, ORE: 1, GEM: 1}
assert set(QUARTERS_PER_DIG) == set(DIGGABLE) == set(inventory.YIELDS)
DIG_FRAMES = 8
PLACE_FRAMES = 6
EMPTY = frozenset({AIR, SKY})
CHOPPABLE = frozenset(TREE_PARTS)       # broken whole by a dig, for wood

NONE, DIG, PLACE = 0, 1, 2


@dataclass(frozen=True)
class Hands:
    counts: tuple[int, ...] = inventory.STARTING    # of each kind (inventory.py)
    cooldown: int = 0
    hand: int = inventory.KIND_SOIL             # the kind placing puts down
    torches: int = 0                            # placed in the world (asm/torches.asm)


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
            left = _solid_left(most_left_of(column, row))
            if left > best_left:
                best, best_left = (column, row), left
    return best


def _solid_left(tile: tuple[int, int]) -> int:
    """Quarter-cells left in a tile, for aiming: a tree's part counts as whole."""
    return QUARTERS * QUARTERS if tile[0] in CHOPPABLE else solid_count(*tile)


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


Rect = tuple[int, int, int, int]       # left, right, top, bottom: pixels and lines, exclusive


def _in_path(tile_at, tx: int, ty: int, rects: list[Rect]) -> bool:
    """Whether any solid quarter-cell of a tile lies within any of rects."""
    material, shape = tile_at(tx, ty)
    for row, column in solid_quarter_cells(material, shape):
        x0, y0 = tx * TILE_WIDTH + column * QUARTER_PIXELS, ty * TILE_HEIGHT + row * QUARTER_LINES
        for left, right, top, bottom in rects:
            if x0 < right and x0 + QUARTER_PIXELS > left and y0 < bottom and y0 + QUARTER_LINES > top:
                return True
    return False


def diagonal(player: Player, dx: int, dy: int, tile_at) -> tuple[tuple[int, int] | None, int | None]:
    """Where digging diagonally works next: (a step to shape, its ramp), or
    (a tile to clear, None), or (None, None).

    The path of a one-tile diagonal step going down is in two parts: first
    across at the player's height, then a tile down (to a tile boundary).
    Going up, it is a tile up: anything rising ahead at the player's height
    is climbed, or if too high, is in that part too. It is worked column by column, nearest the player
    first, and in each column, part by part, so that a dig always opens
    space next to the space the player is in. In a column, the step, if it
    is there and not dug as far as a 45 degree ramp, is cut back to one: going down, the
    floor under the player's leading edge, once what is across above it is
    clear; going up, first, the tile ahead at the feet, which the player
    then walks up. Otherwise the first part of the path with diggable tiles
    with solid parts in it is dug: across, the one of them with the most left
    (the lowest, of equals), so that a wall as high as the player is cut back
    evenly; up or down, the nearest (going up, the lowest; down, the
    highest). Going up, the step is never cleared: it is
    the ramp to walk up. Going down, the floor under the player is never
    cleared in the part going down; but where it stands up into the path
    across (a slope rising ahead), it is dug.
    """
    px, py = player.px, player.py
    ground = py + PLAYER_HEIGHT                 # the line just below the feet
    across = dx * TILE_WIDTH
    left, right = min(px, px + across), max(px, px + across) + PLAYER_WIDTH
    under = range(px // TILE_WIDTH, (px + PLAYER_WIDTH - 1) // TILE_WIDTH + 1)
    if dy > 0:
        edge = (px + PLAYER_WIDTH - 1) // TILE_WIDTH if dx > 0 else px // TILE_WIDTH
        step = (edge, ground // TILE_HEIGHT)
        ramp = RAMP_TOP_RIGHT if dx > 0 else RAMP_TOP_LEFT
        keep = {(tx, ground // TILE_HEIGHT) for tx in under}
        below = (ground + TILE_HEIGHT) // TILE_HEIGHT * TILE_HEIGHT
        rects = [(left, right, py, ground), (px + across, px + across + PLAYER_WIDTH, py, below)]
    else:
        ahead = (px + PLAYER_WIDTH - 1) // TILE_WIDTH + 1 if dx > 0 else px // TILE_WIDTH - 1
        step = (ahead, ground // TILE_HEIGHT - 1)
        ramp = RAMP_TOP_LEFT if dx > 0 else RAMP_TOP_RIGHT
        keep = set()
        # Anything rising ahead at the player's height is climbed (or, if too
        # high, is in this part too), so the path is just a tile up.
        rects = [(left, right, py - TILE_HEIGHT, ground - TILE_HEIGHT)]
    columns = range(left // TILE_WIDTH, (right - 1) // TILE_WIDTH + 1)
    # The order of work in a column: going up, the ramp, then across, then
    # up; going down, across, then the ramp (under what was across), then down.
    order = ["ramp", 0] if dy < 0 else [0, "ramp", 1]
    for tx in columns if dx > 0 else reversed(columns):
        for part in order:
            if part == "ramp":
                if tx == step[0] and _in_world(*step):
                    material, shape = tile_at(*step)
                    if material in QUARTERS_PER_DIG and cut_to(shape & SHAPE_BITS, ramp) is not False:
                        return step, ramp
                continue
            rect = rects[part]
            best, best_left = None, 0
            rows = range((rect[3] - 1) // TILE_HEIGHT, rect[2] // TILE_HEIGHT - 1, -1)
            if dy > 0 and part == 1:
                rows = reversed(rows)       # Going down: the highest, nearest, first
            for ty in rows:
                if (part == 1 and (tx, ty) in keep) or (dy < 0 and (tx, ty) == step) or not _in_world(tx, ty):
                    continue
                material, shape = tile_at(tx, ty)
                if material in QUARTERS_PER_DIG and _in_path(tile_at, tx, ty, [rect]):
                    if dy < 0 or part == 1:
                        return (tx, ty), None   # Up or down: the nearest
                    left_here = solid_count(material, shape)
                    if left_here > best_left:
                        best, best_left = (tx, ty), left_here
            if best is not None:
                return best, None
    return None, None


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


def near_side(player: Player, target: tuple[int, int], dx: int) -> int:
    """The side of a tile nearest the player, digging diagonally: the top of
    a tile wholly below the feet, the bottom of one wholly above the head,
    otherwise the side towards the player."""
    if target[1] * TILE_HEIGHT >= player.py + PLAYER_HEIGHT:
        return FROM_TOP
    if (target[1] + 1) * TILE_HEIGHT <= player.py:
        return FROM_BOTTOM
    return FROM_LEFT if dx > 0 else FROM_RIGHT


def diggable(tile: tuple[int, int]) -> bool:
    """What a straight dig takes: terrain to erode, or a tree's part."""
    return tile[0] in QUARTERS_PER_DIG or tile[0] in CHOPPABLE


def act(hands: Hands, player: Player, inputs: int, world: World) -> tuple[Hands, int, tuple[int, int] | None]:
    """One frame's digging or placing. Returns the new hands, what was done
    and where, changing the world."""
    if hands.cooldown:
        return replace(hands, cooldown=hands.cooldown - 1), NONE, None

    in_world = _in_world
    if inputs & INPUT_ACTION:
        dx = (1 if inputs & INPUT_RIGHT else 0) - (1 if inputs & INPUT_LEFT else 0)
        dy = (1 if inputs & INPUT_DOWN else 0) - (1 if inputs & INPUT_UP else 0)
        if dx and dy:
            target, ramp = diagonal(player, dx, dy, world.tile_at)
            side = near_side(player, target, dx) if target else None
        else:
            target = aim(player, inputs, lambda x, y: in_world(x, y) and diggable(world.tile_at(x, y)),
                         most_left_of=world.tile_at)
            ramp, side = None, dig_direction(player, inputs)
        if target is not None:
            material, shape = world.tile_at(*target)
            behind = background_bits(*target)
            if ramp is not None:
                left = cut_to(shape & SHAPE_BITS, ramp)
                tile = (background(behind), SHAPE_FULL | behind) if left is None else (material, left | behind)
                if world.set_tile(*target, tile):
                    return _dug(hands, material, left), DIG, target
                return hands, NONE, None
            if material in CHOPPABLE:
                if world.set_tile(*target, (background(behind), SHAPE_FULL | behind)):
                    return replace(hands, cooldown=DIG_FRAMES), DIG, target
                return hands, NONE, None
            left = dig_shape(shape & SHAPE_BITS, QUARTERS_PER_DIG[material], side)
            tile = (background(behind), SHAPE_FULL | behind) if left is None else (material, left | behind)
            if world.set_tile(*target, tile):
                return _dug(hands, material, left), DIG, target
    elif inputs & INPUT_PLACE:
        hand = inventory.in_hand(hands.counts, hands.hand)
        if hand is None:
            return hands, NONE, None
        hands = replace(hands, hand=hand)
        torch = inventory.PLACES[hand] == TORCH
        if torch and hands.torches >= inventory.TORCH_MAX:
            return hands, NONE, None
        target = aim(player, inputs, lambda x, y: in_world(x, y) and world.tile_at(x, y)[0] in EMPTY
                     and not overlaps_player(player, x, y))
        if target is None and torch:            # the miner's own tile, if empty
            own = ((player.px + PLAYER_WIDTH // 2) // TILE_WIDTH, (player.py + PLAYER_HEIGHT // 2) // TILE_HEIGHT)
            target = own if world.tile_at(*own)[0] in EMPTY else None
        if target is not None and world.set_tile(*target, (inventory.PLACES[hand],
                                                           SHAPE_FULL | background_bits(*target))):
            return Hands(inventory.spend(hands.counts, hand), PLACE_FRAMES, hand, hands.torches + torch), PLACE, target
    return hands, NONE, None


def _dug(hands: Hands, material: int, left: int | None) -> Hands:
    """The hands after a dig of `material` that left `left` of it (None if
    nothing): a tile dug away entirely is carried, and is in hand."""
    if left is not None:
        return replace(hands, cooldown=DIG_FRAMES)
    kind = inventory.YIELDS[material]
    return Hands(inventory.gain(hands.counts, kind), DIG_FRAMES, kind, hands.torches)
