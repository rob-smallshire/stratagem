"""Tiles: materials and shapes, and their placeholder graphics.

A tile is two bytes: a material and a shape. Each tile is 8 x 16 pixels in
colours 0-7 of the tile colour group, which is logical colours 8-15
(TILE_COLOUR_BASE); sprites use logical colours 0-7. The palette maps both
groups to physical colours, so either can be recoloured on its own. The
materials are drawn by code for now; they will come from an image later.

Shapes. A tile is a 4 x 4 grid of quarter-cells, each 2 pixels by 4 lines;
a shape says which are solid, as a 16-bit mask (bit row * 4 + column).
SHAPE_FULL (0) is all solid. The others are made by *erosion* from one side:
four depths, in quarters, one for each strip of the tile running away from
that side, with everything nearer the side than its depth removed. Flat
erosion (the same depth everywhere) is a partly dug tile; ramps make slopes,
sloped walls and sloped ceilings. Each shape keeps the side and depths it
was made from, so that digging it can erode further from the same side.

The shape byte holds the shape number (SHAPE_BITS) and BACKGROUND_SKY,
set if what shows through the tile's empty parts is sky rather than a dark
cave: tiles at or above the surface line of their column. A piece's shape
byte holds its strength (support.py) for a shape, and PIECE_FRONT, set if
it stands in front of the miner and items.

In front and behind. Every pixel on the screen says whether a sprite may
be drawn over it: tiles are drawn in the tile colour group, but the pixels
of pieces in front in the sprite colour group (the same colours), and a
sprite leaves its pixels out over any pixel in the sprite colour group
(sprites.drawn_byte): over a piece in front, or over another sprite drawn
first.

Drawing. A tile is eight character cells, two rows of four; each cell is
two quarter-cells, one above the other, so in any shape a cell is one of
four variants of its material's cell: full, top half, bottom half or empty,
the empty parts showing the background.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from stratagem.screen import TILE_HEIGHT_LINES, TILE_WIDTH_PIXELS, encode_tile

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

TILE_COLOUR_BASE = 8

AIR, GRASS, SOIL, STONE, ORE, GEM, BEDROCK, WATER, SKY, TORCH = range(10)
# Trees' parts, pieces the generator places (world.py)
(ROOT, TRUNK, TRUNK_KNOT, CANOPY_LEFT, CANOPY_OVER_TRUNK, CANOPY_RIGHT,
 CANOPY_TOP_LEFT, CANOPY_TOP, CANOPY_TOP_RIGHT) = range(10, 19)
BENCH = 19                  # the workbench, placed by the player (crafting.py)
MATERIAL_NAMES = ["air", "grass", "soil", "stone", "ore", "gem", "bedrock", "water", "sky", "torch",
                  "root", "trunk", "trunk, knot", "canopy left", "canopy over trunk", "canopy right",
                  "canopy top left", "canopy top", "canopy top right", "bench"]
MATERIAL_COUNT = len(MATERIAL_NAMES)
DRAWN_COUNT = SKY + 1       # materials the renderer draws, with pages of graphics;
                            # pieces are drawn through slots (below)
TREE_PARTS = list(range(ROOT, CANOPY_TOP_RIGHT + 1))

# Materials a body can pass through, whatever their shape; the rest are
# solid in their shape's solid quarter-cells.
PASSABLE = frozenset({AIR, WATER, SKY, TORCH, *TREE_PARTS, BENCH})
# Materials that can be dug, and so take shapes other than SHAPE_FULL.
DIGGABLE = [GRASS, SOIL, STONE, ORE, GEM]

TILE_PIXEL_WIDTH = TILE_WIDTH_PIXELS        # 8
TILE_LINE_HEIGHT = TILE_HEIGHT_LINES        # 16
QUARTERS = 4
QUARTER_PIXELS = TILE_PIXEL_WIDTH // QUARTERS   # 2
QUARTER_LINES = TILE_LINE_HEIGHT // QUARTERS    # 4

FROM_LEFT, FROM_RIGHT, FROM_TOP, FROM_BOTTOM = range(4)
SIDE_NAMES = ["left", "right", "top", "bottom"]

SHAPE_FULL = 0
FULL_MASK = 0xFFFF
MAX_SHAPES = 64
SHAPE_BITS = 0x3F
BACKGROUND_SKY = 0x40
PIECE_FRONT = 0x80          # a piece's: in front of sprites

# Depth profiles, each also shifted deeper by 1-3 quarters: flat, 45 degree
# ramps and half-height (22.5 degree) ramps.
PROFILES = [(0, 0, 0, 0), (0, 1, 2, 3), (3, 2, 1, 0), (0, 0, 1, 1), (1, 1, 0, 0)]


def _quarter_cell(side: int, strip: int, depth: int) -> tuple[int, int]:
    """(row, column) of the quarter-cell `depth` quarters in from `side`,
    along strip `strip`."""
    if side == FROM_LEFT:
        return strip, depth
    if side == FROM_RIGHT:
        return strip, QUARTERS - 1 - depth
    if side == FROM_TOP:
        return depth, strip
    return QUARTERS - 1 - depth, strip


def eroded_mask(side: int, depths: tuple[int, ...]) -> int:
    mask = 0
    for strip, depth in enumerate(depths):
        for d in range(depth, QUARTERS):
            row, column = _quarter_cell(side, strip, d)
            mask |= 1 << (row * QUARTERS + column)
    return mask


@dataclass(frozen=True)
class Shape:
    mask: int
    side: int                       # the side it was eroded from
    depths: tuple[int, int, int, int]


def _make_shapes() -> list[Shape]:
    shapes = [Shape(FULL_MASK, FROM_TOP, (0, 0, 0, 0))]
    seen = {FULL_MASK, 0}
    for profile in PROFILES:
        for shift in range(QUARTERS):
            depths = tuple(min(QUARTERS, depth + shift) for depth in profile)
            for side in (FROM_TOP, FROM_LEFT, FROM_RIGHT, FROM_BOTTOM):
                mask = eroded_mask(side, depths)
                if mask not in seen:
                    seen.add(mask)
                    shapes.append(Shape(mask, side, depths))
    assert len(shapes) <= MAX_SHAPES
    return shapes


SHAPES = _make_shapes()
SHAPE_COUNT = len(SHAPES)
SHAPE_BY_MASK = {shape.mask: number for number, shape in enumerate(SHAPES)}


def shape_of(side: int, depths: tuple[int, ...]) -> int | None:
    """The shape eroded to `depths` from `side`, or None if nothing is left."""
    mask = eroded_mask(side, tuple(min(QUARTERS, depth) for depth in depths))
    return None if mask == 0 else SHAPE_BY_MASK[mask]


def erode(mask: int, side: int, quarters: int) -> int:
    """A mask eroded from `side`: along each strip running in from that side,
    the first `quarters` solid quarter-cells removed."""
    for strip in range(QUARTERS):
        left = quarters
        for depth in range(QUARTERS):
            row, column = _quarter_cell(side, strip, depth)
            bit = 1 << (row * QUARTERS + column)
            if mask & bit and left:
                mask &= ~bit
                left -= 1
    return mask


@cache
def dig_shape(shape: int, quarters: int, side: int) -> int | None:
    """The shape left after digging `quarters` from `side` of a tile of
    `shape`, or None if nothing is left. Eroding a shape from a side it
    wasn't made from can leave a pattern that isn't a shape; then it is the
    largest shape within that pattern (the first, of equals), so a dig never
    leaves solid what it should have removed: the near side always goes."""
    return best_within(erode(SHAPES[shape].mask, side, quarters))


@cache
def best_within(mask: int) -> int | None:
    """The largest shape within a pattern of quarter-cells (the first, of
    equals), or None if there is none."""
    best, best_count = None, 0
    for number, candidate in enumerate(SHAPES):
        if candidate.mask & ~mask == 0:
            count = bin(candidate.mask).count("1")
            if count > best_count:
                best, best_count = number, count
    return best


@cache
def cut_to(shape: int, target: int) -> int | None | bool:
    """A tile of `shape` cut back to within `target`: the largest shape within
    both, or None if that leaves nothing; False if it is within target
    already, so there is nothing to cut."""
    mask = SHAPES[shape].mask
    if mask & ~SHAPES[target].mask == 0:
        return False
    return best_within(mask & SHAPES[target].mask)


def solid_count(material: int, shape: int) -> int:
    """How many quarter-cells of a tile are solid."""
    return len(solid_quarter_cells(material, shape))


def solid_quarter_cells(material: int, shape: int) -> list[tuple[int, int]]:
    """The solid quarter-cells, (row, column), of a tile."""
    if material in PASSABLE:
        return []
    mask = SHAPES[shape & SHAPE_BITS].mask
    return [(row, column) for row in range(QUARTERS) for column in range(QUARTERS)
            if mask >> (row * QUARTERS + column) & 1]


# Cell variants, and the offset of each in a material's page of graphics.
VARIANT_FULL, VARIANT_TOP, VARIANT_BOTTOM, VARIANT_EMPTY = range(4)
VARIANT_BYTES = 64


def cell_variant(shape: int, half: int, column: int) -> int:
    """Which variant cell (half, column) of a tile of `shape` is."""
    mask = SHAPES[shape & SHAPE_BITS].mask
    top = mask >> ((2 * half) * QUARTERS + column) & 1
    bottom = mask >> ((2 * half + 1) * QUARTERS + column) & 1
    return [[VARIANT_EMPTY, VARIANT_BOTTOM], [VARIANT_TOP, VARIANT_FULL]][top][bottom]


def cell_offset(shape: int, half: int, column: int) -> int:
    """The offset, within a material's page for its background, of cell
    (half, column) of a tile of `shape`, or of a slot's pseudo-shape."""
    variant = SLOT_SHAPE_VARIANTS.get(shape & SHAPE_BITS)
    if variant is None:
        variant = cell_variant(shape, half, column)
    return variant * VARIANT_BYTES + half * 32 + column * 8


def background(shape: int) -> int:
    return SKY if shape & BACKGROUND_SKY else AIR


def _speckle(x: int, y: int, salt: int) -> int:
    """A small deterministic hash of a pixel position, 0-255."""
    h = (x * 73 + y * 151 + salt * 37) & 0xFF
    h ^= h >> 3
    h = (h * 29 + 11) & 0xFF
    return h


def _pixels(colour_at) -> list[list[int]]:
    return [[colour_at(x, y) for x in range(TILE_WIDTH_PIXELS)] for y in range(TILE_HEIGHT_LINES)]


def _soil(x: int, y: int) -> int:
    return YELLOW if _speckle(x, y, 1) < 40 else RED


def _stone(x: int, y: int) -> int:
    return WHITE if (x + 2 * y) % 5 == 0 or _speckle(x, y, 2) < 24 else BLACK


# A torch, dropped by the player into an empty tile: a flame on a stick,
# against the dark (see asm/torches.asm).
TORCH_ART = """
..Y.
.YY.
YRY.
YRRY
.YY.
.WR.
..R.
..R.
..R.
..R.
"""
_TORCH_COLOURS = {".": BLACK, "R": RED, "Y": YELLOW, "W": WHITE}
_TORCH_ROWS = TORCH_ART.split()
TORCH_LEFT, TORCH_TOP = 2, 4


def _torch(x: int, y: int) -> int:
    row, column = y - TORCH_TOP, x - TORCH_LEFT
    if 0 <= row < len(_TORCH_ROWS) and 0 <= column < len(_TORCH_ROWS[row]):
        return _TORCH_COLOURS[_TORCH_ROWS[row][column]]
    return BLACK


MATERIAL_PIXELS = {
    AIR: _pixels(lambda x, y: BLACK),
    GRASS: _pixels(lambda x, y: GREEN if y < 3 or (y < 5 and _speckle(x, y, 3) < 128) else _soil(x, y)),
    SOIL: _pixels(_soil),
    STONE: _pixels(_stone),
    ORE: _pixels(lambda x, y: YELLOW if 2 <= x <= 5 and 5 <= y <= 10 and _speckle(x, y, 4) < 170 else _stone(x, y)),
    GEM: _pixels(lambda x, y: (MAGENTA if (x + y) % 2 else CYAN) if abs(x - 3.5) + abs(y - 7.5) / 2 < 3 else _stone(x, y)),
    BEDROCK: _pixels(lambda x, y: BLACK if y % 8 == 7 or (x == (0 if y // 8 % 2 else 4)) else MAGENTA),
    WATER: _pixels(lambda x, y: CYAN if y == (x // 2) % 2 else BLUE),
    SKY: _pixels(lambda x, y: BLUE),
}


def _variant_pixels(material: int, variant: int, behind: int) -> list[list[int]]:
    """A whole tile of one variant of the material's cells: within each
    cell, lines 0-3 and 4-7 are the material's or the background's."""
    keep_top = variant in (VARIANT_FULL, VARIANT_TOP)
    keep_bottom = variant in (VARIANT_FULL, VARIANT_BOTTOM)
    return [
        [MATERIAL_PIXELS[material][y][x] if (keep_top if y % 8 < 4 else keep_bottom) else MATERIAL_PIXELS[behind][y][x]
         for x in range(TILE_WIDTH_PIXELS)]
        for y in range(TILE_HEIGHT_LINES)
    ]


def material_pages(material: int) -> bytes:
    """A material's 512 bytes of graphics: a page for each background (cave,
    then sky), each holding its four variants, 64 bytes each."""
    return b"".join(
        encode_tile([[TILE_COLOUR_BASE + colour for colour in row] for row in _variant_pixels(material, variant, behind)])
        for behind in (AIR, SKY)
        for variant in range(4)
    )


# Pieces (docs/tile-set.md): materials drawn whole over a backdrop, the
# background that shows through their clear pixels. The torch is the first.
# A piece's graphics are its pixels and a mask of the clear ones; the host
# keeps them in its program RAM, and composes each pair of piece and
# backdrop that is in the tile cache once, into a slot in the render region,
# which the renderer draws as an ordinary material (below).
PIECES = [TORCH, *TREE_PARTS, BENCH]
FIRST_PIECE = TORCH
PIECE_COUNT = len(PIECES)
assert PIECES == list(range(FIRST_PIECE, FIRST_PIECE + PIECE_COUNT))
BACKDROPS = [AIR, SKY]                  # by the shape byte's background bit


def piece_pixels(material: int) -> list[list[int | None]]:
    """A piece's pixels, None where clear."""
    if material == TORCH:
        return [[_torch(x, y) if _torch_covers(x, y) else None for x in range(TILE_WIDTH_PIXELS)]
                for y in range(TILE_HEIGHT_LINES)]
    from stratagem import piece_art
    picture = {ROOT: piece_art.ROOT, TRUNK: piece_art.TRUNK, TRUNK_KNOT: piece_art.TRUNK_KNOT,
               CANOPY_LEFT: piece_art.CANOPY[1][0], CANOPY_OVER_TRUNK: piece_art.CANOPY[1][1],
               CANOPY_RIGHT: piece_art.CANOPY[1][2], CANOPY_TOP_LEFT: piece_art.CANOPY[0][0],
               CANOPY_TOP: piece_art.CANOPY[0][1], CANOPY_TOP_RIGHT: piece_art.CANOPY[0][2],
               BENCH: piece_art.BENCH}[material]
    return [[None if c == piece_art.CLEAR else int(c) for c in row] for row in picture]


def _torch_covers(x: int, y: int) -> bool:
    row, column = y - TORCH_TOP, x - TORCH_LEFT
    return 0 <= row < len(_TORCH_ROWS) and 0 <= column < len(_TORCH_ROWS[row]) and _TORCH_ROWS[row][column] != "."


def composed_pixels(material: int, backdrop: int) -> list[list[int]]:
    """A piece drawn over a backdrop's pixels."""
    return [[MATERIAL_PIXELS[backdrop][y][x] if colour is None else colour for x, colour in enumerate(row)]
            for y, row in enumerate(piece_pixels(material))]


def piece_graphics(material: int) -> bytes:
    """A piece's 128 bytes: its 64 bytes of screen data (clear pixels 0),
    then 64 of mask (clear pixels' bits set)."""
    pixels = piece_pixels(material)
    data = encode_tile([[0 if c is None else TILE_COLOUR_BASE + c for c in row] for row in pixels])
    mask = encode_tile([[15 if c is None else 0 for c in row] for row in pixels])
    return data + mask


def backdrop_graphics(backdrop: int) -> bytes:
    return encode_tile([[TILE_COLOUR_BASE + colour for colour in row] for row in MATERIAL_PIXELS[backdrop]])


FRONT_COLOURS = 0x3F        # a screen byte's bits but those of the tile colour group


def compose(material: int, backdrop: int, front: bool = False) -> bytes:
    """What the host composes into a slot: (backdrop AND mask) OR data, the
    data in the sprite colour group (data AND FRONT_COLOURS) if in front."""
    graphics, back = piece_graphics(material), backdrop_graphics(backdrop)
    keep = FRONT_COLOURS if front else 0xFF
    return bytes(back[i] & graphics[64 + i] | graphics[i] & keep for i in range(64))


# A pair is the piece index * 2 + 1 for the sky, + FRONT_PAIR in front.
FRONT_PAIR = 32
assert PIECE_COUNT * 2 <= FRONT_PAIR


def pair_of(tile: tuple[int, int]) -> int:
    """The pair (piece, backdrop, in front or not) a piece tile needs."""
    material, shape = tile
    return ((material - FIRST_PIECE) * 2 + (1 if shape & BACKGROUND_SKY else 0)
            + (FRONT_PAIR if shape & PIECE_FRONT else 0))


# Slots: SLOT_COUNT composed pairs, 64 bytes each, in SLOT_GROUPS materials
# from SLOT_MATERIAL, each of whose two pages (cave, sky) holds four as its
# four variants: so slot s is variant s AND 3 of page (s >> 2) AND 1 of
# material SLOT_MATERIAL + s >> 3, drawn whole with a pseudo-shape whose
# cells are all that variant (shape numbers above the real shapes), and its
# graphics are at material_pages + SLOT_MATERIAL * 512 + s * 64.
SLOT_MATERIAL = 24
SLOT_GROUPS = 7
SLOT_COUNT = 8 * SLOT_GROUPS
SLOT_SHAPES = [SHAPE_FULL, MAX_SHAPES - 3, MAX_SHAPES - 2, MAX_SHAPES - 1]    # variants 0-3
SLOT_SHAPE_VARIANTS = {MAX_SHAPES - 3: VARIANT_TOP, MAX_SHAPES - 2: VARIANT_BOTTOM, MAX_SHAPES - 1: VARIANT_EMPTY}
assert SHAPE_COUNT <= MAX_SHAPES - 3
assert VARIANT_FULL == 0 and (VARIANT_TOP, VARIANT_BOTTOM, VARIANT_EMPTY) == (1, 2, 3)


def slot_tile(slot: int) -> tuple[int, int]:
    """The tile the host is sent for a piece in `slot`."""
    return SLOT_MATERIAL + (slot >> 3), SLOT_SHAPES[slot & 3] | (BACKGROUND_SKY if slot & 4 else 0)


def slot_of(tile: tuple[int, int]) -> int | None:
    """The slot a host tile shows, or None if it is not a slot."""
    material, shape = tile
    if not SLOT_MATERIAL <= material < SLOT_MATERIAL + SLOT_GROUPS:
        return None
    return (material - SLOT_MATERIAL) * 8 + (4 if shape & BACKGROUND_SKY else 0) + SLOT_SHAPES.index(shape & SHAPE_BITS)


def tile_pixels(material: int, shape: int) -> list[list[int]]:
    """A tile's pixels (in the tile colour group, without the base)."""
    if material in PIECES:
        return composed_pixels(material, background(shape))
    if material in PASSABLE:
        return MATERIAL_PIXELS[material]
    cells = set(solid_quarter_cells(material, shape))
    behind = background(shape)
    return [
        [MATERIAL_PIXELS[material][y][x] if (y // QUARTER_LINES, x // QUARTER_PIXELS) in cells
         else MATERIAL_PIXELS[behind][y][x]
         for x in range(TILE_WIDTH_PIXELS)]
        for y in range(TILE_HEIGHT_LINES)
    ]


@cache
def tile_bytes(tile: tuple[int, int]) -> bytes:
    """A tile's 64 bytes of screen data, its eight cells in order."""
    material, shape = tile
    if material in PIECES:
        return compose(material, background(shape), bool(shape & PIECE_FRONT))
    return encode_tile([[TILE_COLOUR_BASE + colour for colour in row] for row in tile_pixels(material, shape)])
