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


# Daylight down shafts (docs/lighting-tactics.md section 6). Sunlight falls
# down each column to its first opaque tile, however deep (the column's sky
# depth); then, a row at a time from the top, it spreads through open tiles,
# down (losing SUN_DOWN_STEP a tile) and sideways (SUN_SIDE_STEP), never up.
# A wall is lit at its faces (as bright as the open tile beside it, above or
# below), and soaks sideways and downwards, losing SUN_WALL_STEP a tile, never
# upwards: so each row is final once the row below it is open-lit, and a pass
# from the top is exact. Daylight is the brighter of sunlight and the glow:
# fixed_light, GLOW_LOSS levels darker, which lets shallow caves be made out.
# This is the look we chose (in the daylight lab); the game uses the cheaper
# `shaft_sun` below.
#
# `sun_rows` works a rectangle of a region, taking what lies just outside the
# rectangle from the plane as it stands, and anything outside the region as
# opaque and unlit.

SUN_DOWN_STEP = 2
SUN_SIDE_STEP = 2
SUN_WALL_STEP = 4
GLOW_LOSS = 4


def sky_depths(clear: np.ndarray) -> np.ndarray:
    """Each column's first opaque row (the region's height if none)."""
    height = clear.shape[0]
    opaque = ~clear
    return np.where(opaque.any(axis=0), opaque.argmax(axis=0), height)


def sky_depth(clear_at, x: int, start: int = 0) -> int:
    """Column x's first opaque row, looking down from row `start`."""
    y = start
    while y < 255 and clear_at(x, y):
        y += 1
    return y


def sun_rows(plane: np.ndarray, clear: np.ndarray, depth, left: int, right: int, top: int, bottom: int,
             sun: int = FULL, down_step: int = SUN_DOWN_STEP, side_step: int = SUN_SIDE_STEP,
             wall_step: int = SUN_WALL_STEP) -> None:
    """Work out the sunlight of `plane` (a region: `clear` its tiles,
    `depth[x]` each column's sky depth, relative to the region's top) in
    columns left-right and rows top-bottom, inclusive."""
    height, width = clear.shape

    def open_row(y):
        for x in range(left, right + 1):
            if not clear[y, x]:
                continue
            if y < depth[x]:
                plane[y, x] = sun
            elif y > 0 and clear[y - 1, x]:
                plane[y, x] = max(0, plane[y - 1, x] - down_step)
            else:
                plane[y, x] = 0
        _passes(y, lambda x: clear[y, x], side_step)

    def wall_row(y):
        for x in range(left, right + 1):
            if clear[y, x]:
                continue
            best = 0
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < width and 0 <= ny < height and clear[ny, nx]:
                    best = max(best, plane[ny, nx])
            if y > 0 and not clear[y - 1, x]:
                best = max(best, plane[y - 1, x] - wall_step)
            plane[y, x] = best
        _passes(y, lambda x: not clear[y, x], wall_step)

    def _passes(y, kind, step):
        """Spread along row y between tiles of a kind, both ways, from the
        tiles just outside the rectangle too."""
        for x in range(max(left, 1), right + 1):
            if kind(x) and kind(x - 1):
                plane[y, x] = max(plane[y, x], plane[y, x - 1] - step)
        for x in range(min(right, width - 2), left - 1, -1):
            if kind(x) and kind(x + 1):
                plane[y, x] = max(plane[y, x], plane[y, x + 1] - step)

    for y in range(top, bottom + 1):
        open_row(y)
        if y > top:
            wall_row(y - 1)
    wall_row(bottom)


def sunlight(clear: np.ndarray, depth=None, **steps) -> np.ndarray:
    """Sunlight per tile of a region; by default its row 0 is the top of the
    world, and the sky depths are its own."""
    plane = np.zeros(clear.shape, dtype=int)
    sun_rows(plane, clear, sky_depths(clear) if depth is None else depth, 0, clear.shape[1] - 1, 0,
             clear.shape[0] - 1, **steps)
    return plane


def glow(x: int, y: int) -> int:
    """The glow: fixed_light, GLOW_LOSS levels darker."""
    return max(0, fixed_light(x, y) - GLOW_LOSS)


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


# The smooth miner's light: a level per block of two character cells (4
# pixels by 8 lines: square on the screen, and as wide as the Bayer pattern),
# from the miner's exact position rather than its tile. In the open a block's
# level falls off with the distance of its centre from the middle of the
# miner's box, OPEN_STEP a tile's width (a tile looks square), so the pool
# glides with the miner. Walls and corners still shape it: each tile's pool
# level from `miner_light` falls short of what open ground would give by the
# extra cost of the path light took, and the tile's blocks lose that excess
# (never less than nothing: a wall's face is lit as the open ground would be
# at its distance). A tile the pool doesn't reach stays dark.
#
# With soft shadows, a block instead loses the excess interpolated between
# the centres of the four tiles around it (rounded to a whole level), a tile
# the pool doesn't reach counting as MINER_LEVEL, so shadows fade over a tile
# as the pool does.

CELL_PIXELS = 2
CELL_LINES = 8
TILE_CELLS_ACROSS = 4
TILE_CELLS_DOWN = 2
BLOCK_CELLS = 2
BLOCK_PIXELS = BLOCK_CELLS * CELL_PIXELS
TILE_PIXELS = 8
TILE_LINES = 16


def miner_centre(px: int, py: int) -> tuple[float, float]:
    """The middle of the player's box at (px, py), in pixels and lines."""
    from stratagem.player import PLAYER_HEIGHT, PLAYER_WIDTH
    return px + PLAYER_WIDTH / 2, py + PLAYER_HEIGHT / 2


def radial_level(dx_pixels: float, dy_lines: float) -> float:
    """The open-ground level at an offset from the miner's centre."""
    return MINER_LEVEL - OPEN_STEP * math.hypot(dx_pixels / TILE_PIXELS, dy_lines / TILE_LINES)


def tile_excess(clear_at, px: int, py: int, inside=lambda x, y: True) -> dict[tuple[int, int], int | None]:
    """Each tile of the pool's window: the excess cost of the path light took
    to it, or None where the pool doesn't reach."""
    cx, cy = miner_tile(px, py)
    pool = miner_light(clear_at, cx, cy, inside)
    open_pool = miner_light(lambda x, y: True, cx, cy, inside)
    return {tile: None if level == 0 else max(0, open_pool[tile] - level) for tile, level in pool.items()}


def smooth_miner_light(clear_at, px: int, py: int, inside=lambda x, y: True,
                       soft: bool = False) -> dict[tuple[int, int], int]:
    """The miner's light at (px, py): world cell (u, v) -> level (both cells
    of a block alike)."""
    excess = tile_excess(clear_at, px, py, inside)
    mx, my = miner_centre(px, py)

    def dark_as(tile):
        e = excess.get(tile)
        return MINER_LEVEL if e is None else e

    cells = {}
    for (x, y), e in excess.items():
        for v in range(y * TILE_CELLS_DOWN, (y + 1) * TILE_CELLS_DOWN):
            for u in range(x * TILE_CELLS_ACROSS, (x + 1) * TILE_CELLS_ACROSS, BLOCK_CELLS):
                bx, by = u * CELL_PIXELS + BLOCK_PIXELS / 2, v * CELL_LINES + CELL_LINES / 2
                r = radial_level(bx - mx, by - my)
                if soft:
                    # The block is a quarter of a tile from its tile's centre
                    # each way, towards one neighbour across and one down.
                    sx = -1 if u % TILE_CELLS_ACROSS < BLOCK_CELLS else 1
                    sy = -1 if v % TILE_CELLS_DOWN == 0 else 1
                    blend = soft_blend(dark_as((x, y)), dark_as((x + sx, y)), dark_as((x, y + sy)),
                                       dark_as((x + sx, y + sy)))
                    level = max(0, rounded(r) - blend)
                else:
                    level = 0 if e is None else max(0, rounded(r) - e)
                cells[(u, v)] = cells[(u + 1, v)] = level
    return cells


def soft_blend(own: int, across: int, down: int, diagonal: int) -> int:
    """The excess at a block a quarter of a tile from its tile's centre each
    way: half its tile's, half that at the tile's nearest corner (the four
    tiles' average), each rounded to a whole level. So 5:1:1:1, near enough
    the 9:3:3:1 of interpolating, and cheaper: the four blocks around a corner
    share its average."""
    corner = (own + across + down + diagonal + 2) // 4
    return (own + corner + 1) // 2


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


# Daylight by columns: cheaper than `sunlight`, needing only each column's sky
# depth. An open tile is lit fully above its own column's sky depth, else
# from the nearest column within SHAFT_REACH that is open to the sky at its
# row, losing SHAFT_SIDE_STEP a column. A wall is lit fully at its column's
# sky depth, losing SUN_WALL_STEP a tile below it, from a column open to the
# sky beside it, losing SUN_WALL_STEP a column beyond the first, and, as a
# floor, as brightly as the open tile above it. Light ignores what lies
# between, so it can seep a little way through rock.

SHAFT_SIDE_STEP = 3
SHAFT_REACH = FULL // SHAFT_SIDE_STEP - 1
SHAFT_WALL_REACH = FULL // SUN_WALL_STEP + 1


def shaft_sun(depth, clear: bool, x: int, y: int, side_step: int = SHAFT_SIDE_STEP,
              clear_above: bool = False, reach: int = SHAFT_REACH, taper: int | None = None,
              surface=None) -> int:
    """Sunlight at tile (x, y), from `depth[x]`, each column's sky depth
    (a sequence over the whole world), from columns at most `reach` away.
    With `taper`, sunlight in a column loses a level for each `taper` tiles
    below its surface (`surface[x]`, its original surface row), so that it
    dims slowly down a shaft."""
    def open_to_sky(column):
        return 0 <= column < len(depth) and y < depth[column]

    def sun(column, row):
        if taper is None:
            return FULL
        return max(0, FULL - max(0, row - surface[column]) // taper)

    if clear:
        for d in range(0, min(FULL // side_step, reach + 1)):
            for column in (x - d, x + d):
                if open_to_sky(column):
                    return max(0, sun(column, y) - side_step * d)
        return 0
    best = max(0, sun(x, depth[x] - 1) - SUN_WALL_STEP * (y - depth[x])) if y >= depth[x] else 0
    for d in range(1, min(SHAFT_WALL_REACH, reach) + 1):
        for column in (x - d, x + d):
            if open_to_sky(column):
                best = max(best, sun(column, y) - SUN_WALL_STEP * (d - 1))
        if open_to_sky(x - d) or open_to_sky(x + d):
            break
    if clear_above:
        best = max(best, shaft_sun(depth, True, x, y - 1, side_step, reach=reach, taper=taper, surface=surface))
    return best


def shaft_sunlight(clear: np.ndarray, side_step: int = SHAFT_SIDE_STEP, reach: int = SHAFT_REACH,
                   taper: int | None = None, surface=None) -> np.ndarray:
    """shaft_sun for each tile of a region whose row 0 is the top of the
    world (and `surface`, if given, its columns' surface rows)."""
    depth = sky_depths(clear)
    return np.array([[shaft_sun(depth, clear[y, x], x, y, side_step, y > 0 and clear[y - 1, x], reach, taper, surface)
                      for x in range(clear.shape[1])] for y in range(clear.shape[0])])
