"""Light: a level per tile, and drawing tiles at a level.

A model for exploring lighting (see docs/lighting-tactics.md), not yet
something the 6502 does. Light is a level per tile, 0 (dark) to FULL (15).

Sources. Daylight falls straight down each column until it meets an opaque
tile (`sky_light`); torches and the player emit a level at their tile.

Spreading. `spread` carries light from lit transparent tiles to their
neighbours, losing a cost per step, through transparent tiles only, highest
level first (a bucket queue, so each tile is settled once). The alternative,
`stamp`, applies a precomputed radial kernel and so lights through walls.

Walls. Either light soaks into opaque tiles at a higher cost (`wall_step`
in `spread`), so walls are shaded a few tiles deep, or it doesn't enter them
at all and `light_surfaces` gives each opaque tile the brightest light
beside it, so only the faces of walls are lit.

Drawing. A tile at level L keeps a pixel where the 4 x 4 Bayer threshold at
its world position is below the pixel coverage for L, and is black
elsewhere (`coverage`). The pattern is fixed to the world, as scrolling
moves the screen by whole character cells.

The renderer. The tile cache holds a light plane, each tile's level times
LIGHT_SCALE, which is the offset of the level's masks in the mask page
(`light_masks`): for each level, the eight lines of a cell in an even world
cell column, then in an odd one (a cell is two pixels wide, so the Bayer
pattern's columns alternate between cells). Each line of a tile cell is
drawn ANDed with its mask. A mask always keeps bits 7 and 6, colour bit 3 of
both pixels, so a dark pixel is tile colour 8 (black), still marked as
terrain.

For now the light plane holds `fixed_light`, a stand-in for daylight.
"""

from __future__ import annotations

import math

import numpy as np

from stratagem.tiles import PASSABLE, SHAPE_BITS, SHAPE_FULL, WATER
from stratagem.world import HEIGHTS

FULL = 15
LIGHT_SCALE = 16        # light plane value per level: 16 mask bytes per level
FIXED_FLOOR = 0         # fixed_light never goes below this

BAYER = np.array([
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
])

ORTHOGONAL = [(-1, 0), (1, 0), (0, -1), (0, 1)]
DIAGONAL = [(-1, -1), (1, -1), (-1, 1), (1, 1)]


def coverage(level: int) -> int:
    """How many of the 16 Bayer thresholds a pixel at `level` passes: 0 for
    dark, 16 for full light."""
    return 16 if level >= FULL else max(level, 0)


def transparent(tile: tuple[int, int]) -> bool:
    """Light passes through open tiles and any tile partly dug away."""
    material, shape = tile
    return material in PASSABLE or shape & SHAPE_BITS != SHAPE_FULL


def extra_cost(tile: tuple[int, int]) -> int:
    """What light loses entering a tile, beyond the step cost."""
    return 2 if tile[0] == WATER else 0


def sky_light(clear: np.ndarray, level: int = FULL) -> np.ndarray:
    """Direct daylight: each column lit from the top down to its first opaque
    tile. `clear` is the transparency of a region whose row 0 is the top of
    the world."""
    light = np.zeros(clear.shape, dtype=int)
    for x in range(clear.shape[1]):
        for y in range(clear.shape[0]):
            if not clear[y, x]:
                break
            light[y, x] = level
    return light


def spread(light: np.ndarray, clear: np.ndarray, step: int | None, diagonal_step: int | None = None,
           wall_step: int | None = None, extra: np.ndarray | None = None) -> np.ndarray:
    """Light spread from every lit tile: through transparent tiles, losing
    `step` per orthogonal move (none if None) and `diagonal_step` per
    diagonal one (none if None); and, if `wall_step` is given, into opaque
    tiles orthogonally: the face of a wall as bright as the space beside it,
    losing `wall_step` per tile further in, but never out again (a thin wall doesn't light the cave behind it). A diagonal move
    needs one of the two tiles beside it to be transparent, so light doesn't
    leak through a crack between corners."""
    light = light.copy()
    height, width = light.shape
    moves = [(dx, dy, step) for dx, dy in ORTHOGONAL]
    if diagonal_step is not None:
        moves += [(dx, dy, diagonal_step) for dx, dy in DIAGONAL]
    buckets: list[list[tuple[int, int]]] = [[] for _ in range(FULL + 1)]
    for y, x in zip(*np.nonzero(light > 0)):
        buckets[light[y, x]].append((x, y))
    for level in range(FULL, 0, -1):
        for x, y in buckets[level]:
            if light[y, x] != level:
                continue
            for dx, dy, cost in moves:
                nx, ny = x + dx, y + dy
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                if clear[ny, nx]:
                    if cost is None or not clear[y, x]:
                        continue
                    if dx and dy and not (clear[y, nx] or clear[ny, x]):
                        continue
                elif wall_step is None or (dx and dy):
                    continue
                else:
                    cost = 0 if clear[y, x] else wall_step
                reached = level - cost - (extra[ny, nx] if extra is not None else 0)
                if reached > light[ny, nx]:
                    light[ny, nx] = reached
                    buckets[reached].append((nx, ny))
    return light


def light_surfaces(light: np.ndarray, clear: np.ndarray, loss: int = 0) -> np.ndarray:
    """Each opaque tile lit as brightly as the brightest transparent tile
    beside it (diagonals included, for corners), less `loss`."""
    lit = light.copy()
    height, width = light.shape
    for y, x in zip(*np.nonzero(~clear)):
        best = lit[y, x]
        for dx, dy in ORTHOGONAL + DIAGONAL:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and clear[ny, nx]:
                best = max(best, light[ny, nx] - loss)
        lit[y, x] = best
    return lit


def radial_kernel(level: int, falloff: float) -> np.ndarray:
    """A square kernel of max(0, level - falloff * distance), in tiles."""
    radius = math.ceil(level / falloff)
    size = 2 * radius + 1
    kernel = np.zeros((size, size), dtype=int)
    for j in range(size):
        for i in range(size):
            kernel[j, i] = max(0, round(level - falloff * math.hypot(i - radius, j - radius)))
    return kernel


def stamp(light: np.ndarray, kernel: np.ndarray, x: int, y: int) -> np.ndarray:
    """`light` with `kernel` centred on (x, y), by maximum: walls or not."""
    light = light.copy()
    radius = kernel.shape[0] // 2
    height, width = light.shape
    for j in range(kernel.shape[0]):
        for i in range(kernel.shape[1]):
            tx, ty = x + i - radius, y + j - radius
            if 0 <= tx < width and 0 <= ty < height:
                light[ty, tx] = max(light[ty, tx], kernel[j, i])
    return light


def lit_pixels(pixels: np.ndarray, levels: np.ndarray, origin_x: int = 0, origin_y: int = 0) -> np.ndarray:
    """Colour indices with the dither applied: `levels` gives the light of
    each pixel; pixel (0, 0) is at world pixel (origin_x, origin_y)."""
    height, width = pixels.shape
    ys = (np.arange(height) + origin_y) % 4
    xs = (np.arange(width) + origin_x) % 4
    thresholds = BAYER[ys[:, None], xs[None, :]]
    cover = np.where(levels >= FULL, 16, np.maximum(levels, 0))
    return np.where(thresholds < cover, pixels, 0)


def mask_byte(level: int, parity: int, line: int) -> int:
    """The AND mask for a line of a cell in a world cell column of `parity`
    (0 even, 1 odd) at `level`: the cell's two pixels are at world pixel x
    mod 4 = 2 * parity and 2 * parity + 1."""
    thresholds = BAYER[line % 4]
    byte = 0xC0
    if thresholds[2 * parity] < coverage(level):
        byte |= 0xAA
    if thresholds[2 * parity + 1] < coverage(level):
        byte |= 0x55
    return byte


def light_masks() -> bytes:
    """The mask page: at level * LIGHT_SCALE + parity * 8 + line."""
    return bytes(mask_byte(level, parity, line)
                 for level in range(FULL + 1) for parity in range(2) for line in range(8))


def cell_masks(light_at):
    """The mask for line `line` of world cell (u, v), given each tile's
    level by light_at(x, y): for screen.render_view."""
    def mask_at(u: int, v: int, line: int) -> int:
        return mask_byte(light_at(u // 4, v // 2), u % 2, line)
    return mask_at


def fixed_light(x: int, y: int) -> int:
    """A stand-in for daylight: full down to the surface, then a level less
    each tile deeper, down to FIXED_FLOOR: darkness."""
    depth = y - HEIGHTS[x]
    return FULL if depth <= 0 else max(FIXED_FLOOR, FULL - depth)


# The miner's light: a pool around the miner's tile, computed in one pass
# over a window, each tile from its neighbours one step nearer the miner
# (MINER_ORDER is nearest first, by Manhattan distance). Into an open tile,
# light loses OPEN_STEP orthogonally, or OPEN_DIAGONAL_STEP diagonally past
# an open corner; a wall's face is as bright as the open tile beside it, and
# light loses WALL_STEP a tile further into the wall. Light leaves only open
# tiles (and the miner's own). Unlike `spread`, light never turns back
# towards the miner, which a pool this small doesn't need.

MINER_LEVEL = 12
MINER_RADIUS = 4            # the window is 2 * MINER_RADIUS + 1 tiles square
OPEN_STEP = 3
OPEN_DIAGONAL_STEP = 4
WALL_STEP = 4
NO_TILE = 0xFF


def _sign(n: int) -> int:
    return (n > 0) - (n < 0)


MINER_ORDER = sorted(
    ((dx, dy) for dy in range(-MINER_RADIUS, MINER_RADIUS + 1) for dx in range(-MINER_RADIUS, MINER_RADIUS + 1)),
    key=lambda d: (abs(d[0]) + abs(d[1]), d[1], d[0]))
MINER_INDEX = {offset: k for k, offset in enumerate(MINER_ORDER)}


def miner_predecessors(k: int) -> tuple[int, int, int]:
    """Window entry k's neighbours one step nearer the miner: across, down
    (or up) and diagonal, each an index into MINER_ORDER or NO_TILE."""
    dx, dy = MINER_ORDER[k]
    sx, sy = _sign(dx), _sign(dy)
    across = MINER_INDEX[(dx - sx, dy)] if sx else NO_TILE
    vertical = MINER_INDEX[(dx, dy - sy)] if sy else NO_TILE
    diagonal = MINER_INDEX[(dx - sx, dy - sy)] if sx and sy else NO_TILE
    return across, vertical, diagonal


def miner_tile(px: int, py: int) -> tuple[int, int]:
    """The tile at the middle of the player's box, at (px, py)."""
    from stratagem.player import PLAYER_HEIGHT, PLAYER_WIDTH
    return (px + PLAYER_WIDTH // 2) // 8, (py + PLAYER_HEIGHT // 2) // 16


def miner_light(clear_at, cx: int, cy: int, inside=lambda x, y: True) -> dict[tuple[int, int], int]:
    """The pool of light around the miner's tile (cx, cy): tile -> level.
    clear_at(x, y) says whether a tile lets light through; tiles where
    inside(x, y) is false (outside the tile cache) are dark and stop light."""
    pool, clear = [], []
    for k, (dx, dy) in enumerate(MINER_ORDER):
        x, y = cx + dx, cy + dy
        if not inside(x, y):
            pool.append(0)
            clear.append(False)
            continue
        if k == 0:
            pool.append(MINER_LEVEL)
            clear.append(True)
            continue
        is_clear = clear_at(x, y)
        across, vertical, diagonal = miner_predecessors(k)
        best = 0
        for p in (across, vertical):
            if p == NO_TILE:
                continue
            if clear[p]:
                best = max(best, pool[p] - (OPEN_STEP if is_clear else 0))
            elif not is_clear:
                best = max(best, pool[p] - WALL_STEP)
        if is_clear and diagonal != NO_TILE and clear[diagonal] and \
                any(p != NO_TILE and clear[p] for p in (across, vertical)):
            best = max(best, pool[diagonal] - OPEN_DIAGONAL_STEP)
        pool.append(best)
        clear.append(is_clear)
    return {(cx + dx, cy + dy): level for (dx, dy), level in zip(MINER_ORDER, pool)}


def lit_level(x: int, y: int, pool: dict[tuple[int, int], int]) -> int:
    """A tile's light: the brighter of daylight and the miner's light."""
    return max(fixed_light(x, y), pool.get((x, y), 0))


# The smooth miner's light: a level per character cell (2 pixels by 8
# lines), from the miner's exact position rather than its tile. In the open
# a cell's level falls off with its distance from the middle of the miner's
# box, OPEN_STEP a tile's width (a tile looks square), so the pool glides
# with the miner. Walls and corners still shape it: each tile's pool level
# from `miner_light` falls short of what open ground would give by the extra
# cost of the path light took, and the tile's cells lose that excess (never
# less than nothing: a wall's face is lit as the open ground would be at its
# distance). A tile the pool doesn't reach stays dark.

CELL_PIXELS = 2
CELL_LINES = 8
TILE_CELLS_ACROSS = 4
TILE_CELLS_DOWN = 2


def miner_centre(px: int, py: int) -> tuple[float, float]:
    """The middle of the player's box at (px, py), in pixels and lines."""
    from stratagem.player import PLAYER_HEIGHT, PLAYER_WIDTH
    return px + PLAYER_WIDTH / 2, py + PLAYER_HEIGHT / 2


def radial_level(dx_pixels: float, dy_lines: float) -> float:
    """The open-ground level at an offset from the miner's centre."""
    return MINER_LEVEL - OPEN_STEP * math.hypot(dx_pixels / 8, dy_lines / 16)


def smooth_miner_light(clear_at, px: int, py: int, inside=lambda x, y: True) -> dict[tuple[int, int], int]:
    """The miner's light at (px, py): world cell (u, v) -> level."""
    cx, cy = miner_tile(px, py)
    pool = miner_light(clear_at, cx, cy, inside)
    open_pool = miner_light(lambda x, y: True, cx, cy, inside)
    mx, my = miner_centre(px, py)
    cells = {}
    for (x, y), level in pool.items():
        excess = max(0, open_pool[(x, y)] - level)
        for v in range(y * TILE_CELLS_DOWN, (y + 1) * TILE_CELLS_DOWN):
            for u in range(x * TILE_CELLS_ACROSS, (x + 1) * TILE_CELLS_ACROSS):
                if level == 0:
                    cells[(u, v)] = 0
                    continue
                r = radial_level(u * CELL_PIXELS + CELL_PIXELS / 2 - mx, v * CELL_LINES + CELL_LINES / 2 - my)
                cells[(u, v)] = max(0, rounded(r) - excess)
    return cells


def rounded(level: float) -> int:
    """A level rounded to the nearest whole level, and no less than 0."""
    return max(0, math.floor(level + 0.5))


# Which cells a change of light shows in. A cell's two pixels sit in two of
# the Bayer pattern's four columns (its parity), which hold 8 of the 16
# thresholds; a cell drawn at a level keeps the pixels whose threshold is
# below the level's coverage, so a level's mask class is how many of those 8
# are below it. A change of light shows only if a pixel that isn't black has
# a threshold between the two classes: `cell_visibility` gives each cell of
# a tile a bit per threshold (in order) that falls on a pixel of colour.

def parity_thresholds(parity: int) -> list[int]:
    return sorted(int(t) for t in BAYER[:, 2 * parity:2 * parity + 2].ravel())


def mask_class(level: int, parity: int) -> int:
    return sum(t < coverage(level) for t in parity_thresholds(parity))


def cell_visibility(pixels) -> list[int]:
    """For a tile's pixels (16 lines of 8), a byte per cell (row * 4 +
    column): bit i set if the cell has a coloured pixel at its parity's i-th
    threshold."""
    bits = []
    for row in range(TILE_CELLS_DOWN):
        for column in range(TILE_CELLS_ACROSS):
            parity = column % 2
            order = parity_thresholds(parity)
            byte = 0
            for line in range(CELL_LINES):
                for x in range(CELL_PIXELS):
                    if pixels[row * CELL_LINES + line][column * CELL_PIXELS + x] & 7:
                        byte |= 1 << order.index(int(BAYER[line % 4][2 * parity + x]))
            bits.append(byte)
    return bits


def shows(visibility: int, before: int, after: int, parity: int) -> bool:
    """Whether a cell with `visibility` looks different at level `after`."""
    low, high = sorted((mask_class(before, parity), mask_class(after, parity)))
    return visibility & ((1 << high) - (1 << low)) != 0
