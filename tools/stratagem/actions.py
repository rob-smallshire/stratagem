"""A model of digging and placing in asm/actions.asm, exactly as the 6502
does it.

Each frame, after the player moves: if the cooldown is running, it counts
down and nothing happens. Otherwise ACTION (L) digs and PLACE (SPACE)
places, at a tile chosen by aiming: DOWN (M) aims at the tile holding the
line just below the feet, UP (K) the line just above the head; otherwise
the aim is the column holding the pixel just ahead, in the direction faced,
where digging takes the lowest diggable tile and placing the lowest empty
one, from the feet up to the head. (A partly dug tile may hold some of the
player, in its dug part; it can still be dug. A tile is only placed where
it would not overlap the player.)

Digging removes quarters of the tile, from the side the player digs from
(digging rightwards removes it from the left, downwards from the top), or
from the side it is already dug from: QUARTERS_PER_DIG of them, by how hard
the material is. So soft ground goes in one dig and stone in four, and you
see it go. When the last quarter goes the tile is AIR, and a block goes
into the inventory (up to INVENTORY_MAX). Each dig starts a cooldown.
Placing puts SOIL in an empty tile (AIR or SKY), using a block. If the
world has no room for a change, nothing happens.
"""

from __future__ import annotations

from dataclasses import dataclass

from stratagem.camera import INPUT_DOWN, INPUT_UP
from stratagem.player import PLAYER_HEIGHT, PLAYER_WIDTH, TILE_HEIGHT, TILE_WIDTH, Player
from stratagem.tiles import (AIR, DIGGABLE, FROM_BOTTOM, FROM_LEFT, FROM_RIGHT, FROM_TOP, GEM, GRASS,
                             ORE, QUARTERS, SKY, SOIL, STONE, kind_info, partial_kind)
from stratagem.world import World

INPUT_ACTION = 16
INPUT_PLACE = 32

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


def _ahead(player: Player, wanted) -> tuple[int, int] | None:
    """The lowest tile in the column ahead, from the feet up to the head,
    that `wanted` accepts."""
    px, py = player.px, player.py
    column = (px + PLAYER_WIDTH) // TILE_WIDTH if player.facing > 0 else (px - 1) // TILE_WIDTH
    for row in range((py + PLAYER_HEIGHT - 1) // TILE_HEIGHT, py // TILE_HEIGHT - 1, -1):
        if wanted(column, row):
            return column, row
    return None


def aim(player: Player, inputs: int, wanted) -> tuple[int, int] | None:
    px, py = player.px, player.py
    middle = (px + PLAYER_WIDTH // 2) // TILE_WIDTH
    if inputs & INPUT_DOWN:
        target = middle, (py + PLAYER_HEIGHT) // TILE_HEIGHT
    elif inputs & INPUT_UP:
        target = middle, (py - 1) // TILE_HEIGHT
    else:
        return _ahead(player, wanted)
    return target if wanted(*target) else None


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


def diggable(kind: int) -> bool:
    return kind_info(kind)[0] in QUARTERS_PER_DIG


def act(hands: Hands, player: Player, inputs: int, world: World) -> tuple[Hands, int, tuple[int, int] | None]:
    """One frame's digging or placing. Returns the new hands, what was done
    and where, changing the world."""
    if hands.cooldown:
        return Hands(hands.inventory, hands.cooldown - 1), NONE, None

    def in_world(x: int, y: int) -> bool:
        return 0 <= x < 256 and 0 <= y < 256

    if inputs & INPUT_ACTION:
        target = aim(player, inputs, lambda x, y: in_world(x, y) and diggable(world.tile_at(x, y)))
        if target is not None:
            material, direction, removed = kind_info(world.tile_at(*target))
            if not removed:
                direction = dig_direction(player, inputs)
            removed += QUARTERS_PER_DIG[material]
            kind = AIR if removed >= QUARTERS else partial_kind(material, direction, removed)
            if world.set_tile(*target, kind):
                inventory = min(hands.inventory + 1, INVENTORY_MAX) if kind == AIR else hands.inventory
                return Hands(inventory, DIG_FRAMES), DIG, target
    elif inputs & INPUT_PLACE and hands.inventory:
        target = aim(player, inputs, lambda x, y: in_world(x, y) and world.tile_at(x, y) in EMPTY
                     and not overlaps_player(player, x, y))
        if target is not None and world.set_tile(*target, PLACED_TILE):
            return Hands(hands.inventory - 1, PLACE_FRAMES), PLACE, target
    return hands, NONE, None
