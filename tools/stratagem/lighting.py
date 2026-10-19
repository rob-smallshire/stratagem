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
FIXED_FLOOR = 3         # fixed_light never goes below this

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
    each tile deeper, down to FIXED_FLOOR, so that underground stays
    playable."""
    depth = y - HEIGHTS[x]
    return FULL if depth <= 0 else max(FIXED_FLOOR, FULL - depth)
