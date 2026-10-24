"""A model of the pack screen (asm/pack.asm on the parasite, render_pack in
asm/render.asm on the host), exactly as the 6502 does it.

PACK (P) opens the pack, and the game pauses: nothing moves, and each
frame's packet is a short one, the pack's. It shows the kinds held (a count
above 0) and the kind in hand, whatever its count, in kind order, as they
are on opening (nothing changes them while the game is paused), eight
across: each as its icon, a tile's 8 x 16 pixels, with its count below,
and the hand marked by arrowheads either side of its count. The arrow keys
move the hand across the kinds shown, a key press each step, and only the
arrowheads are redrawn (redrawing the panel would show it half drawn, for
a frame); PACK again
closes the pack, and the view is redrawn whole, as after a jump of the
camera, on a frame with no other input.

The panel is drawn over the view, PANEL_TOP rows down, PANEL_COLUMNS cells
wide and centred: a blank row, then for each row of kinds two rows of
icons, a row of counts and a blank row. A slot is SLOT_CELLS cells across:
a blank cell, an arrowhead's cell, the icon's four (the count's two digits
below it), an arrowhead's cell and a blank cell.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from stratagem.camera import INPUT_DOWN, INPUT_LEFT, INPUT_RIGHT, INPUT_UP
from stratagem.inventory import (KIND_BENCH, KIND_COUNT, KIND_GEM, KIND_ORE, KIND_PLANKS, KIND_SOIL, KIND_STONE,
                                 KIND_TORCH, KIND_WOOD, cycle)
from stratagem.screen import CELL_BYTES, VIEW_COLUMNS, cell_address, encode_tile, mode2_byte
from stratagem.tiles import (AIR, BLACK, GEM, ORE, RED, SHAPE_FULL, SOIL, STONE, TILE_COLOUR_BASE, TORCH, TRUNK, WHITE,
                             YELLOW, tile_bytes)

INPUT_PACK = 128                    # P: open or close the pack
KEY_CYCLE = 1                       # TAB, in the second byte of input: cycle the hand

PACK_COLUMNS = 8                    # kinds across
SLOT_CELLS = 8
PANEL_COLUMNS = PACK_COLUMNS * SLOT_CELLS
PANEL_LEFT = (VIEW_COLUMNS - PANEL_COLUMNS) // 2
PANEL_TOP = 1
ROWS_PER_SLOT_ROW = 4
assert PANEL_LEFT >= 0

PANEL_COLOUR = 0                    # black, in the sprite colour group
DIGIT_COLOUR = 7                    # white
MARK_COLOUR = 3                     # yellow


@dataclass(frozen=True)
class Pack:
    open: bool = False
    held: int = 0                   # the input last frame, for key presses
    draw: bool = False              # the panel needs drawing this frame
    moved: bool = False             # the hand moved: redraw the arrowheads
    closed: bool = False            # it closed this frame: redraw the view
    kinds: tuple[int, ...] = ()     # the kinds shown, since it opened
    held_keys: int = 0              # the second byte of input last frame


def shown(counts: tuple[int, ...], hand: int) -> list[int]:
    """The kinds the pack shows, in order."""
    return [kind for kind in range(KIND_COUNT) if counts[kind] or kind == hand]


def step(pack: Pack, counts: tuple[int, ...], hand: int, inputs: int, keys: int = 0) -> tuple[Pack, int]:
    """One frame's input to the pack, before the game's: `inputs` and the
    second byte, `keys`. Returns the pack and the hand; the game runs this
    frame only if the pack isn't open. In play, TAB (KEY_CYCLE) cycles the
    hand (inventory.cycle)."""
    pressed = inputs & ~pack.held
    pressed_keys = keys & ~pack.held_keys
    pack = replace(pack, held=inputs, held_keys=keys, draw=False, moved=False, closed=False)
    if not pack.open:
        if pressed & INPUT_PACK:
            return replace(pack, open=True, draw=True, kinds=tuple(shown(counts, hand))), hand
        if pressed_keys & KEY_CYCLE:
            return pack, cycle(counts, hand)
        return pack, hand
    if pressed & INPUT_PACK:
        return replace(pack, open=False, closed=True), hand
    kinds = pack.kinds
    index = kinds.index(hand)
    moved = index
    if pressed & INPUT_LEFT and moved > 0:
        moved -= 1
    if pressed & INPUT_RIGHT and moved < len(kinds) - 1:
        moved += 1
    if pressed & INPUT_UP and moved >= PACK_COLUMNS:
        moved -= PACK_COLUMNS
    if pressed & INPUT_DOWN and moved + PACK_COLUMNS < len(kinds):
        moved += PACK_COLUMNS
    return replace(pack, moved=moved != index), kinds[moved]


# The icons: each kind's picture, a tile's 64 bytes (screen.encode_tile):
# a material's whole tile, which the render region's material pages hold
# already (ICON_MATERIALS), a piece's over the cave, or a picture of its own.
ICON_MATERIALS = {KIND_SOIL: SOIL, KIND_STONE: STONE, KIND_ORE: ORE, KIND_GEM: GEM}
ICON_PIECES = {KIND_WOOD: TRUNK, KIND_TORCH: TORCH}
ICON_ART = {
    KIND_PLANKS: """
YYYYYRYY
YYYYYRYY
YYYYYRYY
RRRRRRRR
YYRYYYYY
YYRYYYYY
YYRYYYYY
RRRRRRRR
YYYYYYRY
YYYYYYRY
YYYYYYRY
RRRRRRRR
YRYYYYYY
YRYYYYYY
YRYYYYYY
RRRRRRRR
""",
    KIND_BENCH: """
........
...WWW..
....R...
....R...
YYYYYYYY
YYYYYYYY
RRRRRRRR
.R....R.
.R....R.
.R....R.
.RRRRRR.
.R....R.
.R....R.
.R....R.
.R....R.
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


def panel_rows(kinds: int) -> int:
    return 1 + ROWS_PER_SLOT_ROW * ((kinds + PACK_COLUMNS - 1) // PACK_COLUMNS)


def panel(screen_start: int, counts: tuple[int, ...], hand: int, kinds: list[int] | None = None) -> dict[int, int]:
    """The screen bytes the panel draws, by address: of `kinds`, or, by
    default, those shown on opening with `hand`."""
    kinds = shown(counts, hand) if kinds is None else kinds
    image = {}
    for row in range(PANEL_TOP, PANEL_TOP + panel_rows(len(kinds))):
        for column in range(PANEL_LEFT, PANEL_LEFT + PANEL_COLUMNS):
            address = cell_address(screen_start, column, row)
            for line in range(CELL_BYTES):
                image[address + line] = mode2_byte(PANEL_COLOUR, PANEL_COLOUR)

    def put(column: int, row: int, data: bytes) -> None:
        address = cell_address(screen_start, column, row)
        for line in range(CELL_BYTES):
            image[address + line] = data[line]

    for i, kind in enumerate(kinds):
        left = PANEL_LEFT + i % PACK_COLUMNS * SLOT_CELLS + 1
        top = PANEL_TOP + 1 + i // PACK_COLUMNS * ROWS_PER_SLOT_ROW
        picture = icon(kind)
        for cell in range(8):
            put(left + 1 + cell % 4, top + cell // 4, picture[cell * 8:cell * 8 + 8])
        count = counts[kind]
        if count >= 10:
            tens = digit(count // 10)
            put(left + 1, top + 2, tens[:8])
            put(left + 2, top + 2, tens[8:])
        units = digit(count % 10)
        put(left + 3, top + 2, units[:8])
        put(left + 4, top + 2, units[8:])
        if kind == hand:
            put(left, top + 2, mark("right"))
            put(left + 5, top + 2, mark("left"))
    return image
