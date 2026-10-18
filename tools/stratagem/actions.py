"""A model of digging and placing in asm/actions.asm, exactly as the 6502
does it.

Each frame, after the player moves: if the cooldown is running, it counts
down and nothing happens. Otherwise ACTION (L) digs and PLACE (SPACE)
places, at a tile chosen by aiming: DOWN (M) aims below the feet, UP (K)
above the head; otherwise the aim is the column ahead, in the direction
faced, where digging takes the lowest diggable tile and placing the lowest
empty one, from the feet up to the head. The aimed tile never overlaps the
player.

Digging turns the tile to AIR, adds a block to the inventory (up to
INVENTORY_MAX) and starts a cooldown that depends on how hard the tile is.
Placing puts SOIL in an empty tile (AIR or SKY), using a block. If the
world has no room for the change, nothing happens.
"""

from __future__ import annotations

from dataclasses import dataclass

from stratagem.camera import INPUT_DOWN, INPUT_UP
from stratagem.player import PLAYER_HEIGHT, PLAYER_WIDTH, TILE_HEIGHT, TILE_WIDTH, Player
from stratagem.tiles import AIR, GEM, GRASS, ORE, SKY, SOIL, STONE
from stratagem.world import World

INPUT_ACTION = 16
INPUT_PLACE = 32

DIG_FRAMES = {GRASS: 6, SOIL: 6, STONE: 12, ORE: 12, GEM: 12}   # diggable tiles
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
    column = (px + PLAYER_WIDTH - 1) // TILE_WIDTH + 1 if player.facing > 0 else px // TILE_WIDTH - 1
    for row in range((py + PLAYER_HEIGHT - 1) // TILE_HEIGHT, py // TILE_HEIGHT - 1, -1):
        if wanted(column, row):
            return column, row
    return None


def aim(player: Player, inputs: int, wanted) -> tuple[int, int] | None:
    px, py = player.px, player.py
    middle = (px + PLAYER_WIDTH // 2) // TILE_WIDTH
    if inputs & INPUT_DOWN:
        target = middle, (py + PLAYER_HEIGHT - 1) // TILE_HEIGHT + 1
    elif inputs & INPUT_UP:
        target = middle, py // TILE_HEIGHT - 1
    else:
        return _ahead(player, wanted)
    return target if wanted(*target) else None


def act(hands: Hands, player: Player, inputs: int, world: World) -> tuple[Hands, int, tuple[int, int] | None]:
    """One frame's digging or placing. Returns the new hands, what was done
    and where, changing the world."""
    if hands.cooldown:
        return Hands(hands.inventory, hands.cooldown - 1), NONE, None

    def in_world(x: int, y: int) -> bool:
        return 0 <= x < 256 and 0 <= y < 256

    if inputs & INPUT_ACTION:
        target = aim(player, inputs, lambda x, y: in_world(x, y) and world.tile_at(x, y) in DIG_FRAMES)
        if target is not None:
            frames = DIG_FRAMES[world.tile_at(*target)]
            if world.set_tile(*target, AIR):
                return Hands(min(hands.inventory + 1, INVENTORY_MAX), frames), DIG, target
    elif inputs & INPUT_PLACE and hands.inventory:
        target = aim(player, inputs, lambda x, y: in_world(x, y) and world.tile_at(x, y) in EMPTY)
        if target is not None and world.set_tile(*target, PLACED_TILE):
            return Hands(hands.inventory - 1, PLACE_FRAMES), PLACE, target
    return hands, NONE, None
