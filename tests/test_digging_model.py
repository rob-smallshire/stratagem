"""Digging, in the Python models: every dig opens space next to the space the
player is in, never a cavity beyond solid ground.

(The 6502 matches these models exactly: see test_actions.py.)
"""

from collections import deque

import pytest

from stratagem import actions, player
from stratagem.actions import Hands
from stratagem.camera import INPUT_ACTION, INPUT_DOWN, INPUT_LEFT, INPUT_RIGHT, INPUT_UP
from stratagem.player import PLAYER_HEIGHT, PLAYER_WIDTH, TILE_HEIGHT, TILE_WIDTH, Player
from stratagem.tiles import QUARTER_LINES, QUARTER_PIXELS, QUARTERS, SOIL, STONE, solid_quarter_cells
from stratagem.world import HEIGHTS, World

DIRECTIONS = {
    "down-left": INPUT_LEFT | INPUT_DOWN,
    "down-right": INPUT_RIGHT | INPUT_DOWN,
    "up-left": INPUT_LEFT | INPUT_UP,
    "up-right": INPUT_RIGHT | INPUT_UP,
    "left": INPUT_LEFT,
    "right": INPUT_RIGHT,
    "down": INPUT_DOWN,
}

Cell = tuple[int, int]      # a quarter-cell: (column, row) in the world


def tile_cells(tile: tuple[int, int], tx: int, ty: int) -> set[Cell]:
    """A tile's solid quarter-cells, in world quarter-cell coordinates."""
    return {(tx * QUARTERS + c, ty * QUARTERS + r) for r, c in solid_quarter_cells(*tile)}


def solid_cells(world: World, tx: int, ty: int) -> set[Cell]:
    if not (0 <= tx < 256 and 0 <= ty < 256):
        return {(tx * QUARTERS + c, ty * QUARTERS + r) for r in range(QUARTERS) for c in range(QUARTERS)}
    return tile_cells(world.tile_at(tx, ty), tx, ty)


def open_near_player(world: World, hero: Player) -> set[Cell]:
    """The open quarter-cells connected to the player's box, within a tile of
    it on every side."""
    c0, c1 = (hero.px - TILE_WIDTH) // QUARTER_PIXELS, (hero.px + PLAYER_WIDTH + TILE_WIDTH - 1) // QUARTER_PIXELS
    r0, r1 = (hero.py - TILE_HEIGHT) // QUARTER_LINES, (hero.py + PLAYER_HEIGHT + TILE_HEIGHT - 1) // QUARTER_LINES
    solid = set()
    for ty in range(r0 // QUARTERS, r1 // QUARTERS + 1):
        for tx in range(c0 // QUARTERS, c1 // QUARTERS + 1):
            solid |= solid_cells(world, tx, ty)
    seen = {(c, r)
            for c in range(hero.px // QUARTER_PIXELS, (hero.px + PLAYER_WIDTH - 1) // QUARTER_PIXELS + 1)
            for r in range(hero.py // QUARTER_LINES, (hero.py + PLAYER_HEIGHT - 1) // QUARTER_LINES + 1)
            if (c, r) not in solid}
    queue = deque(seen)
    while queue:
        c, r = queue.popleft()
        for n in ((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)):
            if c0 <= n[0] <= c1 and r0 <= n[1] <= r1 and n not in solid and n not in seen:
                seen.add(n)
                queue.append(n)
    return seen


def touches(cells: set[Cell], region: set[Cell]) -> bool:
    return any((c + dc, r + dr) in region for c, r in cells for dc, dr in ((-1, 0), (1, 0), (0, -1), (0, 1)))


def starts():
    """Standing places across the world, on the surface (slopes included) and
    in a pocket dug underground: (description, world, player)."""
    for x in range(12, 244, 7):
        yield f"surface at {x}", World(), Player(x=(x * TILE_WIDTH + 1) * 16,
                                                 y=(HEIGHTS[x] * TILE_HEIGHT - PLAYER_HEIGHT) * 16)
        world = World()
        floor = HEIGHTS[x] + 21
        for dy in range(-3, 0):
            for dx in range(-1, 2):
                world.set_tile(x + dx, floor + dy, (0, 0))
        yield f"underground at {x}", world, Player(x=(x * TILE_WIDTH + 1) * 16,
                                                   y=(floor * TILE_HEIGHT - PLAYER_HEIGHT) * 16)


@pytest.mark.parametrize("direction", DIRECTIONS.keys())
def test_every_dig_opens_space_next_to_the_player(direction):
    keys = DIRECTIONS[direction] | INPUT_ACTION
    digs = 0
    for where, world, hero in starts():
        for _ in range(30):
            hero = player.step(hero, 0, world.tile_at)
        hands = Hands()
        for frame in range(400):
            hero = player.step(hero, keys, world.tile_at)
            region = open_near_player(world, hero)
            near = {(tx, ty): world.tile_at(tx, ty)
                    for tx in range(hero.px // TILE_WIDTH - 2, hero.px // TILE_WIDTH + 3)
                    for ty in range(hero.py // TILE_HEIGHT - 2, hero.py // TILE_HEIGHT + 4)
                    if 0 <= tx < 256 and 0 <= ty < 256}
            hands, action, target = actions.act(hands, hero, keys, world)
            if action != actions.DIG:
                continue
            digs += 1
            emptied = tile_cells(near[target], *target) - solid_cells(world, *target)
            if not emptied:
                continue    # shaping a ramp can leave no quarter-cell less solid... not so: see below
            assert touches(emptied, region), (
                f"{where}, frame {frame}: digging {direction} at {target} opened a cavity away from the "
                f"player at ({hero.px}, {hero.py}): quarter-cells {sorted(emptied)}")
    assert digs > 200, digs


class SolidWorld:
    """A world of one material, whole everywhere, with changes: for measuring
    tunnels without caves in the way."""

    def __init__(self, material: int) -> None:
        self.material, self.changes = material, {}

    def tile_at(self, x: int, y: int) -> tuple[int, int]:
        return self.changes.get((x, y), (self.material, 0))

    def set_tile(self, x: int, y: int, tile: tuple[int, int]) -> bool:
        self.changes[(x, y)] = tile
        return True


def tunnel(world, direction: str, x: int, floor: int, frames: int) -> tuple[int, int, int]:
    """Dig from a pocket with its floor at row `floor`, holding a diagonal
    direction: (pixels across, lines down (or up), biggest vertical move)."""
    keys = DIRECTIONS[direction] | INPUT_ACTION
    for dy in range(-3, 0):
        for dx in range(-1, 2):
            world.set_tile(x + dx, floor + dy, (0, 0))
    hero = Player(x=(x * TILE_WIDTH + 1) * 16, y=(floor * TILE_HEIGHT - PLAYER_HEIGHT) * 16)
    for _ in range(30):
        hero = player.step(hero, 0, world.tile_at)
    hands = Hands()
    x0, y0, biggest = hero.px, hero.py, 0
    for _ in range(frames):
        before = hero
        hero = player.step(hero, keys, world.tile_at)
        hands, _, _ = actions.act(hands, hero, keys, world)
        biggest = max(biggest, abs(hero.py - before.py))
    across = (hero.px - x0) * (1 if "right" in direction else -1)
    vertical = (hero.py - y0) * (1 if "down" in direction else -1)
    return across, vertical, biggest


@pytest.mark.parametrize("direction", ["down-left", "down-right", "up-left", "up-right"])
@pytest.mark.parametrize("material", [SOIL, STONE])
def test_digging_diagonally_tunnels_at_45_degrees(direction, material):
    """In solid ground, holding a diagonal direction and dig tunnels along a
    45 degree slope, a tile down (or up) for each tile across, smoothly."""
    across, vertical, biggest = tunnel(SolidWorld(material), direction, 128, 128, 1200)
    assert across >= 8 * TILE_WIDTH, f"only {across} pixels across"
    assert abs(vertical - 2 * across) <= 2 * TILE_HEIGHT, f"not at 45 degrees: {across} pixels across, {vertical} lines"
    assert biggest <= QUARTER_LINES, f"a vertical move of {biggest} lines"


@pytest.mark.parametrize("direction", ["down-left", "down-right", "up-left", "up-right"])
@pytest.mark.parametrize("x", [60, 128, 190])
def test_digging_diagonally_makes_progress_through_real_ground(direction, x):
    """Through the generated world, caves and all, diagonal tunnelling keeps
    going the right way."""
    across, vertical, _ = tunnel(World(), direction, x, HEIGHTS[x] + 31, 1200)
    assert across >= 4 * TILE_WIDTH and vertical >= 2 * TILE_HEIGHT, f"moved {across} pixels across, {vertical} lines"
