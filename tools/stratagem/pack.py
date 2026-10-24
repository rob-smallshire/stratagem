"""A model of the pack screen (asm/pack.asm and asm/crafting.asm on the
parasite, render_pack in asm/render.asm on the host), exactly as the 6502
does it.

PACK (P) opens the pack, and the game pauses: nothing moves, and each
frame's packet is a short one, the pack's. It shows the kinds held (a count
above 0), in kind order, eight across: each as its icon, a tile's 8 x 16
pixels, with its count below, and the hand marked by arrowheads either
side of its count; if the hand isn't among them, it moves to the first.
A kind once shown stays shown while the pack is open, even at 0, so the
kinds don't move about as counts run out; a kind gained (by making it)
joins them, in kind order. Z and X move the hand back and forth across
the kinds shown, in order, from the end of one row to the start of the
next, and K and M up and down a row, a key press each step, as the miner
moves in play; and only the arrowheads are redrawn (redrawing the panel
would show it half drawn, for a frame).

Below the kinds is the crafting grid (crafting.py), the hand's 2 x 2, and
what it makes. The hand is the brush: a cell's key (R T / F G) puts a kind
in its cell or takes it out; DELETE empties the grid; L makes what it
lays out, again every MAKE_REPEAT frames while held, after MAKE_DELAY; COPY
lays out the next recipe in the book. A change redraws the counts, the grid
and the result (the panel whole if a kind joins those shown). PACK again
closes the pack, emptying the grid back into the counts, and the view is
redrawn whole, as after a jump of the camera, on a frame with no other
input.

The panel is drawn over the view, PANEL_TOP rows down, PANEL_COLUMNS cells
wide and centred: a blank row, then for each row of kinds two rows of
icons, a row of counts and a blank row; then for each row of the grid, two
rows of icons and a blank row. A slot is SLOT_CELLS cells across: a blank
cell, an arrowhead's cell, the icon's four (the count's two digits below
it), an arrowhead's cell and a blank cell. The grid's cells are
GRID_PITCH cells apart, an empty cell drawn as a socket, and the result is
drawn as a slot, after them, with an arrowhead pointing at its count, in
the grid's first row of icons.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from stratagem import crafting
from stratagem.camera import INPUT_DOWN, INPUT_LEFT, INPUT_RIGHT, INPUT_UP
from stratagem.crafting import EMPTY, EMPTY_GRID, GRID_CELLS, GRID_MAX, GRID_SIZES, RECIPES, STATION_HAND
from stratagem.inventory import (KIND_BENCH, KIND_COUNT, KIND_GEM, KIND_ORE, KIND_PLANKS, KIND_SOIL, KIND_STONE,
                                 KIND_TORCH, KIND_WOOD, cycle)
from stratagem.screen import CELL_BYTES, VIEW_COLUMNS, cell_address, encode_tile, mode2_byte
from stratagem.tiles import (AIR, BENCH, BLACK, GEM, ORE, RED, SHAPE_FULL, SOIL, STONE, TILE_COLOUR_BASE, TORCH, TRUNK, WHITE,
                             YELLOW, tile_bytes)

INPUT_PACK = 128                    # P: open or close the pack
KEY_CYCLE = 1                       # TAB, in the second byte of input in play: cycle the hand
KEY_CELL = 0x0F                     # in the pack, the second byte: the cell's key held (1 on), or 0
KEY_CLEAR = 0x10                    # DELETE
KEY_MAKE = 0x20                     # L: make
KEY_BOOK = 0x40                     # COPY: the recipe book
KEY_NEXT = 0x80                     # TAB: the hand to the next kind shown
CELL_KEYS = "RTYFGHVBN"             # by cell
MAKE_DELAY = 20                     # frames L is held before it repeats...
MAKE_REPEAT = 8                     # ... and then between makes

PACK_COLUMNS = 8                    # kinds across
SLOT_CELLS = 8
PANEL_COLUMNS = PACK_COLUMNS * SLOT_CELLS
PANEL_LEFT = (VIEW_COLUMNS - PANEL_COLUMNS) // 2
PANEL_TOP = 1
ROWS_PER_SLOT_ROW = 4
assert PANEL_LEFT >= 0
GRID_PITCH = 5                      # cells across from one grid cell to the next
ROWS_PER_GRID_ROW = 3


def grid_left(size: int) -> int:
    """The grid's first column: the grid and its result, centred."""
    return PANEL_LEFT + (PANEL_COLUMNS - (GRID_PITCH * size + SLOT_CELLS - 2)) // 2

PANEL_COLOUR = 0                    # black, in the sprite colour group
DIGIT_COLOUR = 7                    # white
MARK_COLOUR = 3                     # yellow
SOCKET_COLOUR = 4                   # blue


@dataclass(frozen=True)
class Pack:
    open: bool = False
    held: int = 0                   # the input last frame, for key presses
    draw: bool = False              # the panel needs drawing this frame
    moved: bool = False             # the hand moved: redraw the arrowheads
    changed: bool = False           # the counts or the grid changed: redraw them
    closed: bool = False            # it closed this frame: redraw the view
    kinds: tuple[int, ...] = ()     # the kinds shown, since it opened
    held_keys: int = 0              # the second byte of input last frame
    grid: tuple[int, ...] = EMPTY_GRID
    book: int = 0                   # the recipes made, a bit each (crafting.py)
    copied: int = len(RECIPES) - 1  # the recipe COPY laid out last
    repeat: int = 0                 # frames until L, held, makes again
    station: int = STATION_HAND


def shown(counts: tuple[int, ...], kinds: tuple[int, ...] = ()) -> list[int]:
    """The kinds the pack shows, in order: those held and those shown
    already."""
    return [kind for kind in range(KIND_COUNT) if counts[kind] or kind in kinds]


def hand_shown(kinds: tuple[int, ...] | list[int], hand: int) -> int:
    """The hand, if it is among the kinds shown, otherwise the first of
    them; the hand if none are shown."""
    return hand if hand in kinds or not kinds else kinds[0]


def step(pack: Pack, counts: tuple[int, ...], hand: int, inputs: int, keys: int = 0, station: int = STATION_HAND
         ) -> tuple[Pack, tuple[int, ...], int]:
    """One frame's input to the pack, before the game's: `inputs` and the
    second byte, `keys`, and the station the miner is at, if the pack opens
    (crafting.station_near). Returns the pack, the counts and the hand; the
    game runs this frame only if the pack isn't open. In play, TAB
    (KEY_CYCLE) cycles the hand (inventory.cycle)."""
    pressed = inputs & ~pack.held
    pressed_keys = keys & ~pack.held_keys
    cell = keys & KEY_CELL if keys & KEY_CELL != pack.held_keys & KEY_CELL else 0     # a cell's key, newly
    pack = replace(pack, held=inputs, held_keys=keys, draw=False, moved=False, changed=False, closed=False)
    if not pack.open:
        if pressed & INPUT_PACK:
            kinds = tuple(shown(counts))
            return (replace(pack, open=True, draw=True, kinds=kinds, station=station), counts,
                    hand_shown(kinds, hand))
        if pressed_keys & KEY_CYCLE:
            return pack, counts, cycle(counts, hand)
        return pack, counts, hand
    if pressed & INPUT_PACK:
        counts, grid = crafting.clear(counts, pack.grid)
        return replace(pack, open=False, closed=True, grid=grid), counts, hand
    kinds = pack.kinds
    index = kinds.index(hand) if kinds else 0
    moved = index
    if pressed & INPUT_LEFT and moved > 0:
        moved -= 1
    if pressed & INPUT_RIGHT and moved < len(kinds) - 1:
        moved += 1
    if pressed & INPUT_UP and moved >= PACK_COLUMNS:
        moved -= PACK_COLUMNS
    if pressed & INPUT_DOWN and moved + PACK_COLUMNS < len(kinds):
        moved += PACK_COLUMNS
    if pressed_keys & KEY_NEXT and kinds:
        moved = (moved + 1) % len(kinds)
    hand = kinds[moved] if kinds else hand
    pack = replace(pack, moved=moved != index)
    before = counts, pack.grid
    grid, book, copied, repeat = pack.grid, pack.book, pack.copied, pack.repeat
    if cell and crafting.in_grid(cell - 1, pack.station):
        counts, grid = crafting.put(counts, grid, cell - 1, hand)
    if pressed_keys & KEY_CLEAR:
        counts, grid = crafting.clear(counts, grid)
    if keys & KEY_MAKE:
        if pressed_keys & KEY_MAKE:
            repeat = MAKE_DELAY
        else:
            repeat = (repeat - 1) & 0xFF
        if repeat == 0 or pressed_keys & KEY_MAKE:
            counts, grid, book = crafting.make(counts, grid, book, pack.station)
            repeat = repeat or MAKE_REPEAT
    if pressed_keys & KEY_BOOK:
        counts, grid, copied = crafting.copy(counts, grid, book, copied, pack.station)
    now = tuple(shown(counts, kinds))
    hand = hand_shown(now, hand)
    pack = replace(pack, grid=grid, book=book, copied=copied, repeat=repeat, kinds=now,
                   changed=(counts, grid) != before, draw=now != kinds)
    return pack, counts, hand


# The icons: each kind's picture, a tile's 64 bytes (screen.encode_tile):
# a material's whole tile, which the render region's material pages hold
# already (ICON_MATERIALS), a piece's over the cave, or a picture of its own.
ICON_MATERIALS = {KIND_SOIL: SOIL, KIND_STONE: STONE, KIND_ORE: ORE, KIND_GEM: GEM}
ICON_PIECES = {KIND_WOOD: TRUNK, KIND_TORCH: TORCH, KIND_BENCH: BENCH}
ICON_ART = {
    KIND_PLANKS: """
RRRRRRRR
RR..RRRR
RRRRRRRR
........
RRRRRRRR
RRRRR..R
RRRRRRRR
........
RRRRRRRR
R..RRRRR
RRRRRRRR
........
RRRRRRRR
RRRR..RR
RRRRRRRR
........
""",
}
OWN_ICONS = sorted(set(range(KIND_COUNT)) - set(ICON_MATERIALS))    # those pack_icons holds, in order
assert set(ICON_MATERIALS) | set(ICON_PIECES) | set(ICON_ART) == set(range(KIND_COUNT)) and AIR == 0
_ART_COLOURS = {".": BLACK, "R": RED, "Y": YELLOW, "W": WHITE}


def icon(kind: int) -> bytes:
    if kind in ICON_MATERIALS:
        return tile_bytes((ICON_MATERIALS[kind], SHAPE_FULL))
    if kind in ICON_PIECES:
        return tile_bytes((ICON_PIECES[kind], SHAPE_FULL))      # (a piece's backdrop: the cave)
    return encode_tile([[TILE_COLOUR_BASE + _ART_COLOURS[c] for c in line] for line in ICON_ART[kind].split()])


# Digits, three pixels wide and seven lines high, in a cell pair (two
# bytes, four pixels, across) of eight lines, the first blank, to part them
# from the icon above: the left cell's eight bytes, then the right's.
_DIGITS = """
###  #  ### ### # # ### ### ### ### ###
# # ##    #   # # # #   #     # # # # #
# #  #    #   # # # #   #     # # # # #
# #  #  ###  ## ### ### ###   # ### ###
# #  #  #     #   #   # # #   # # #   #
# #  #  #     #   #   # # #   # # #   #
### ### ### ###   # ### ###   # ### ###
"""
_MARKS = {
    "right": """
#.
##
##
##
#.
""",
    "left": """
.#
##
##
##
.#
""",
}


def _digit_pixels(digit: int) -> list[list[int]]:
    lines = [line.ljust(39) for line in _DIGITS.strip("\n").split("\n")]
    return [[PANEL_COLOUR] * 4] + [[DIGIT_COLOUR if c == "#" else PANEL_COLOUR for c in line[digit * 4:digit * 4 + 3]]
                                   + [PANEL_COLOUR] for line in lines]


def digit(digit: int) -> bytes:
    """A digit's 16 bytes: its left cell, then its right."""
    pixels = _digit_pixels(digit)
    return bytes(mode2_byte(pixels[line][2 * column], pixels[line][2 * column + 1])
                 for column in range(2) for line in range(8))


def mark(side: str) -> bytes:
    """An arrowhead's cell, centred on the count's digits: "right" points
    right, before the slot; "left" points left, after it; "blank" is
    neither."""
    if side == "blank":
        return bytes(CELL_BYTES)
    rows = [line for line in _MARKS[side].split()]
    pixels = [[PANEL_COLOUR] * 2] * 2 + [[MARK_COLOUR if c == "#" else PANEL_COLOUR for c in row] for row in rows] \
        + [[PANEL_COLOUR] * 2]
    assert len(pixels) == CELL_BYTES
    return bytes(mode2_byte(*row) for row in pixels)


def socket() -> bytes:
    """An empty cell of the grid: an outline, an icon's size."""
    pixels = [[SOCKET_COLOUR if x in (0, 7) or y in (0, 15) else PANEL_COLOUR for x in range(8)] for y in range(16)]
    return encode_tile(pixels)


def kind_rows(kinds: int) -> int:
    return 1 + ROWS_PER_SLOT_ROW * ((kinds + PACK_COLUMNS - 1) // PACK_COLUMNS)


def panel_rows(kinds: int, station: int = STATION_HAND) -> int:
    return kind_rows(kinds) + ROWS_PER_GRID_ROW * GRID_SIZES[station]


def result(grid: tuple[int, ...], station: int = STATION_HAND) -> tuple[int, int] | None:
    """What the grid makes, and how many, if anything."""
    index = crafting.match(grid, station)
    return None if index is None else (RECIPES[index].makes, RECIPES[index].count)


def panel(screen_start: int, counts: tuple[int, ...], hand: int, kinds: list[int] | None = None,
          grid: tuple[int, ...] = EMPTY_GRID, station: int = STATION_HAND) -> dict[int, int]:
    """The screen bytes the panel draws, by address: of `kinds`, or, by
    default, those shown on opening with `hand`, and of the grid."""
    kinds = shown(counts) if kinds is None else kinds
    image = {}
    for row in range(PANEL_TOP, PANEL_TOP + panel_rows(len(kinds), station)):
        for column in range(PANEL_LEFT, PANEL_LEFT + PANEL_COLUMNS):
            address = cell_address(screen_start, column, row)
            for line in range(CELL_BYTES):
                image[address + line] = mode2_byte(PANEL_COLOUR, PANEL_COLOUR)

    def put(column: int, row: int, data: bytes) -> None:
        address = cell_address(screen_start, column, row)
        for line in range(CELL_BYTES):
            image[address + line] = data[line]

    def slot(left: int, top: int, kind: int, count: int, right: str, left_mark: str) -> None:
        """An icon from column left + 1, row top, its count below, and the
        arrowheads either side of the count."""
        picture = icon(kind)
        for cell in range(8):
            put(left + 1 + cell % 4, top + cell // 4, picture[cell * 8:cell * 8 + 8])
        if count >= 10:
            tens = digit(count // 10)
            put(left + 1, top + 2, tens[:8])
            put(left + 2, top + 2, tens[8:])
        units = digit(count % 10)
        put(left + 3, top + 2, units[:8])
        put(left + 4, top + 2, units[8:])
        put(left, top + 2, mark(right))
        put(left + 5, top + 2, mark(left_mark))

    for i, kind in enumerate(kinds):
        left = PANEL_LEFT + i % PACK_COLUMNS * SLOT_CELLS + 1
        top = PANEL_TOP + 1 + i // PACK_COLUMNS * ROWS_PER_SLOT_ROW
        marks = ("right", "left") if kind == hand else ("blank", "blank")
        slot(left, top, kind, counts[kind], *marks)

    size = GRID_SIZES[station]
    grid_top = PANEL_TOP + kind_rows(len(kinds))
    left = grid_left(size)
    for row in range(size):
        for column in range(size):
            kind = grid[row * GRID_MAX + column]
            picture = socket() if kind == EMPTY else icon(kind)
            for cell in range(8):
                put(left + column * GRID_PITCH + cell % 4, grid_top + row * ROWS_PER_GRID_ROW + cell // 4,
                    picture[cell * 8:cell * 8 + 8])
    made = result(grid, station)
    if made is not None:
        slot(left + size * GRID_PITCH, grid_top, made[0], made[1], "right", "blank")
    return image
