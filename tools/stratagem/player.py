"""A model of the player's movement in asm/player.asm, exactly as the 6502
does it.

The player is a PLAYER_WIDTH x PLAYER_HEIGHT box (pixels x lines) whose top
left is at (x, y). Positions are in sixteenths of a pixel (x) and of a line
(y), in 16 bits; velocities are signed sixteenths per frame, in 8 bits.

Each frame: walking eases the horizontal velocity towards WALK_SPEED in the
direction held (faster on the ground than in the air); UP jumps if the
player is on the ground; gravity accelerates the fall, up to MAX_FALL. Then
the player moves horizontally and vertically, each separately, and stops
flush against any solid tile in the way. Walking into a step one tile high
climbs it, if there is room above. Falls are slower than a tile a frame,
so the player can never pass through a tile.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from stratagem.camera import INPUT_LEFT, INPUT_RIGHT, INPUT_UP
from stratagem.tiles import PASSABLE

PLAYER_WIDTH = 6        # pixels
PLAYER_HEIGHT = 24      # lines
TILE_WIDTH = 8
TILE_HEIGHT = 16
SUBPIXELS = 16

WALK_SPEED = 16         # sixteenths of a pixel a frame
GROUND_ACCELERATION = 2
AIR_ACCELERATION = 1
JUMP_SPEED = 72         # sixteenths of a line a frame, upwards
GRAVITY = 4
MAX_FALL = 96

TileAt = Callable[[int, int], int]


@dataclass(frozen=True)
class Player:
    x: int              # sixteenths of a pixel
    y: int              # sixteenths of a line
    vx: int = 0
    vy: int = 0
    on_ground: bool = False
    facing: int = 1     # 1 right, -1 left

    @property
    def px(self) -> int:
        return self.x >> 4

    @property
    def py(self) -> int:
        return self.y >> 4


def box_free(tile_at: TileAt, px: int, py: int) -> bool:
    """Whether a player box at (px, py) overlaps only passable tiles."""
    for ty in range(py // TILE_HEIGHT, (py + PLAYER_HEIGHT - 1) // TILE_HEIGHT + 1):
        for tx in range(px // TILE_WIDTH, (px + PLAYER_WIDTH - 1) // TILE_WIDTH + 1):
            if tile_at(tx, ty) not in PASSABLE:
                return False
    return True


def _toward(value: int, target: int, step: int) -> int:
    if value < target:
        return min(value + step, target)
    if value > target:
        return max(value - step, target)
    return value


def step(player: Player, inputs: int, tile_at: TileAt) -> Player:
    direction = (1 if inputs & INPUT_RIGHT else 0) - (1 if inputs & INPUT_LEFT else 0)
    acceleration = GROUND_ACCELERATION if player.on_ground else AIR_ACCELERATION
    vx = _toward(player.vx, direction * WALK_SPEED, acceleration)
    facing = direction or player.facing
    vy = player.vy
    if inputs & INPUT_UP and player.on_ground:
        vy = -JUMP_SPEED
    vy = min(vy + GRAVITY, MAX_FALL)
    x, y = player.x, player.y

    # Horizontally.
    if vx:
        new_x = x + vx
        new_px, py = new_x >> 4, y >> 4
        if box_free(tile_at, new_px, py):
            x = new_x
        elif player.on_ground and py >= TILE_HEIGHT and box_free(tile_at, new_px, py - TILE_HEIGHT):
            x, y = new_x, (py - TILE_HEIGHT) << 4       # Climb a step
        else:
            if vx > 0:
                edge = (new_px + PLAYER_WIDTH - 1) // TILE_WIDTH
                x = (edge * TILE_WIDTH - PLAYER_WIDTH) << 4
            else:
                edge = new_px // TILE_WIDTH
                x = ((edge + 1) * TILE_WIDTH) << 4
            vx = 0

    # Vertically.
    on_ground = False
    new_y = y + vy
    if new_y < 0:
        new_y, vy = 0, 0
    px, new_py = x >> 4, new_y >> 4
    if box_free(tile_at, px, new_py):
        y = new_y
    elif vy > 0:
        edge = (new_py + PLAYER_HEIGHT - 1) // TILE_HEIGHT
        y = (edge * TILE_HEIGHT - PLAYER_HEIGHT) << 4
        vy, on_ground = 0, True
    else:
        edge = new_py // TILE_HEIGHT
        y = ((edge + 1) * TILE_HEIGHT) << 4
        vy = 0
    return replace(player, x=x, y=y, vx=vx, vy=vy, on_ground=on_ground, facing=facing)


def focus(player: Player) -> tuple[int, int]:
    """The camera focus for the player: a little left of and above its centre."""
    return player.px + 2, player.py + 8
