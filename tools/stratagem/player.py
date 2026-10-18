"""A model of the player's movement in asm/player.asm, exactly as the 6502
does it.

The player is a PLAYER_WIDTH x PLAYER_HEIGHT box (pixels x lines) whose top
left is at (x, y). Positions are in sixteenths of a pixel (x) and of a line
(y), in 16 bits; velocities are signed sixteenths per frame, in 8 bits.

Each frame: walking eases the horizontal velocity towards WALK_SPEED in the
direction held (faster on the ground than in the air). UP jumps from the
ground (holding it jumps again on landing); in the air, a fresh press of UP
jumps again if the player has the double jump ability and hasn't used it
since landing. Gravity accelerates the fall, up to MAX_FALL.

Then the player moves horizontally and vertically, each separately. A tile
is solid in some of its quarter-cells (2 pixels by 4 lines), by its shape,
so a move that would overlap solid quarter-cells stops flush against the
nearest of them. Walking into a ledge at most a tile high climbs it, if
there is room above, so a slope is climbed a quarter-cell step at a time;
and a player who was standing doesn't fall off a step down shallower than
SNAP_DOWN lines (a quarter-cell step), but follows the ground down it. Every move is less than a
tile, so the player can never pass through one; and as the player was clear
before the move, anything it would overlap lies wholly beyond its old
position.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from stratagem.camera import INPUT_LEFT, INPUT_RIGHT, INPUT_UP
from stratagem.tiles import QUARTER_LINES, QUARTER_PIXELS, solid_quarter_cells

PLAYER_WIDTH = 6        # pixels
PLAYER_HEIGHT = 24      # lines
TILE_WIDTH = 8
TILE_HEIGHT = 16
SUBPIXELS = 16

WALK_SPEED = 16         # sixteenths of a pixel a frame
GROUND_ACCELERATION = 2
AIR_ACCELERATION = 1
JUMP_SPEED = 72         # sixteenths of a line a frame, upwards
AIR_JUMP_SPEED = 64
GRAVITY = 4
MAX_FALL = 96
SNAP_DOWN = 5           # lines probed below: follows steps down of up to 4

ABILITY_DOUBLE_JUMP = 1
STARTING_ABILITIES = ABILITY_DOUBLE_JUMP    # until abilities can be earned

TileAt = Callable[[int, int], tuple[int, int]]
Rect = tuple[int, int, int, int]            # left, right, top, bottom; exclusive


@dataclass(frozen=True)
class Player:
    x: int              # sixteenths of a pixel
    y: int              # sixteenths of a line
    vx: int = 0
    vy: int = 0
    on_ground: bool = False
    facing: int = 1     # 1 right, -1 left
    jump_held: bool = False     # UP was held last frame
    air_jumps: int = 0          # jumps left before landing

    @property
    def px(self) -> int:
        return self.x >> 4

    @property
    def py(self) -> int:
        return self.y >> 4


def hits(tile_at: TileAt, px: int, py: int) -> list[Rect]:
    """The solid quarter-cells, as rectangles in world pixels and lines, that
    a player box at (px, py) would overlap."""
    found = []
    for ty in range(py // TILE_HEIGHT, (py + PLAYER_HEIGHT - 1) // TILE_HEIGHT + 1):
        for tx in range(px // TILE_WIDTH, (px + PLAYER_WIDTH - 1) // TILE_WIDTH + 1):
            for row, column in solid_quarter_cells(*tile_at(tx, ty)):
                left = tx * TILE_WIDTH + column * QUARTER_PIXELS
                top = ty * TILE_HEIGHT + row * QUARTER_LINES
                right, bottom = left + QUARTER_PIXELS, top + QUARTER_LINES
                if px < right and px + PLAYER_WIDTH > left and py < bottom and py + PLAYER_HEIGHT > top:
                    found.append((left, right, top, bottom))
    return found


def box_free(tile_at: TileAt, px: int, py: int) -> bool:
    return not hits(tile_at, px, py)


def _toward(value: int, target: int, step: int) -> int:
    if value < target:
        return min(value + step, target)
    if value > target:
        return max(value - step, target)
    return value


def step(player: Player, inputs: int, tile_at: TileAt, abilities: int = STARTING_ABILITIES) -> Player:
    direction = (1 if inputs & INPUT_RIGHT else 0) - (1 if inputs & INPUT_LEFT else 0)
    acceleration = GROUND_ACCELERATION if player.on_ground else AIR_ACCELERATION
    vx = _toward(player.vx, direction * WALK_SPEED, acceleration)
    facing = direction or player.facing
    vy = player.vy
    air_jumps = player.air_jumps
    up = bool(inputs & INPUT_UP)
    if up and player.on_ground:
        vy = -JUMP_SPEED
    elif up and not player.jump_held and air_jumps:
        vy = -AIR_JUMP_SPEED
        air_jumps -= 1
    vy = min(vy + GRAVITY, MAX_FALL)
    x, y = player.x, player.y

    # Horizontally.
    if vx:
        new_x = x + vx
        new_px, py = new_x >> 4, y >> 4
        found = hits(tile_at, new_px, py)
        if not found:
            x = new_x
        else:
            lift = py + PLAYER_HEIGHT - min(rect[2] for rect in found)
            if player.on_ground and lift <= TILE_HEIGHT and lift <= py and box_free(tile_at, new_px, py - lift):
                x, y = new_x, (py - lift) << 4      # Climb the ledge
            else:
                if vx > 0:
                    x = (min(rect[0] for rect in found) - PLAYER_WIDTH) << 4
                else:
                    x = max(rect[1] for rect in found) << 4
                vx = 0

    # Vertically.
    on_ground = False
    new_y = y + vy
    if new_y < 0:
        new_y, vy = 0, 0
    px, new_py = x >> 4, new_y >> 4
    found = hits(tile_at, px, new_py)
    if not found and player.on_ground and vy > 0:
        # Follow the ground down a small step, rather than fall off it.
        found = hits(tile_at, px, (y >> 4) + SNAP_DOWN)
    if not found:
        y = new_y
    elif vy > 0:
        y = (min(rect[2] for rect in found) - PLAYER_HEIGHT) << 4
        vy, on_ground = 0, True
    else:
        y = max(rect[3] for rect in found) << 4
        vy = 0
    if on_ground:
        air_jumps = 1 if abilities & ABILITY_DOUBLE_JUMP else 0
    return replace(player, x=x, y=y, vx=vx, vy=vy, on_ground=on_ground, facing=facing,
                   jump_held=up, air_jumps=air_jumps)


def focus(player: Player) -> tuple[int, int]:
    """The camera focus for the player: a little left of and above its centre."""
    return player.px + 2, player.py + 8
