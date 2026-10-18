"""Screen geometry and MODE 2 pixel encoding.

Screen memory is 16K at &4000, with the hardware wrap set for a 16K screen:
64 CRTC character columns (one byte, two pixels, wide) by 32 character rows
of 8 lines. Within a character row, byte (column * 8 + line) holds line
`line` of column `column`. Only VIEW_ROWS = 31 rows are displayed: the 32nd
is hidden, and is where a new row is drawn before it is scrolled into view.

The world is drawn in cells, one character (8 bytes) each. World cell
(u, v) is column u (0-1023, two pixels wide) of character row v (0-511,
eight lines high); it shows quarter u % 4 of half v % 2 of tile
(u // 4, v // 2).
"""

from __future__ import annotations

from collections.abc import Callable

SCREEN_START = 0x4000
SCREEN_SIZE = 0x4000
SCREEN_END = SCREEN_START + SCREEN_SIZE
COLUMNS = 64
ROWS = 32
ROW_BYTES = COLUMNS * 8   # 512
CELL_BYTES = 8

VIEW_COLUMNS = COLUMNS
VIEW_ROWS = ROWS - 1      # the last row is hidden
VIEW_LINES = VIEW_ROWS * 8

TILE_WIDTH_PIXELS = 8
TILE_HEIGHT_LINES = 16
TILE_WIDTH_BYTES = TILE_WIDTH_PIXELS // 2   # 4 cells
TILE_BYTES = TILE_WIDTH_BYTES * TILE_HEIGHT_LINES   # 64
CELLS_PER_TILE_X = 4
CELLS_PER_TILE_Y = 2


def wrap(address: int) -> int:
    """Wrap an address into the screen, as the hardware does."""
    return SCREEN_START + (address - SCREEN_START) % SCREEN_SIZE


def mode2_byte(left: int, right: int) -> int:
    """Encode two logical colours (0-15) as a MODE 2 screen byte.

    Bits 7, 5, 3, 1 hold the left pixel's colour bits 3, 2, 1, 0, and bits
    6, 4, 2, 0 the right pixel's.
    """
    byte = 0
    for bit in range(4):
        if left >> bit & 1:
            byte |= 1 << (2 * bit + 1)
        if right >> bit & 1:
            byte |= 1 << (2 * bit)
    return byte


def mode2_pixels(byte: int) -> tuple[int, int]:
    """Decode a MODE 2 screen byte into its (left, right) logical colours."""
    left = right = 0
    for bit in range(4):
        left |= (byte >> (2 * bit + 1) & 1) << bit
        right |= (byte >> (2 * bit) & 1) << bit
    return left, right


def encode_tile(pixels: list[list[int]]) -> bytes:
    """Encode a tile, given as 16 rows of 8 logical colours, as its eight
    cells: the top half's four columns of eight lines, then the bottom's."""
    assert len(pixels) == TILE_HEIGHT_LINES and all(len(row) == TILE_WIDTH_PIXELS for row in pixels)
    data = bytearray()
    for half in range(CELLS_PER_TILE_Y):
        for column in range(TILE_WIDTH_BYTES):
            for line in range(8):
                row = pixels[half * 8 + line]
                data.append(mode2_byte(row[2 * column], row[2 * column + 1]))
    return bytes(data)


def cell_offset(u: int, v: int) -> int:
    """The offset of world cell (u, v) within its tile's graphics."""
    return (v % CELLS_PER_TILE_Y) * 32 + (u % CELLS_PER_TILE_X) * CELL_BYTES


def cell_address(screen_start: int, column: int, row: int) -> int:
    """The screen address of view cell (column, row)."""
    return wrap(screen_start + row * ROW_BYTES + column * CELL_BYTES)


def render_view(screen_start: int, camera_x: int, camera_y: int,
                tile_at: Callable[[int, int], int], graphics: list[bytes]) -> dict[int, int]:
    """The expected bytes of the displayed screen, as a mapping from address
    to byte, with the view's top-left cell, world cell (camera_x, camera_y),
    at screen_start."""
    image = {}
    for row in range(VIEW_ROWS):
        v = camera_y + row
        for column in range(VIEW_COLUMNS):
            u = camera_x + column
            data = graphics[tile_at(u // CELLS_PER_TILE_X, v // CELLS_PER_TILE_Y)]
            offset = cell_offset(u, v)
            address = cell_address(screen_start, column, row)
            for line in range(CELL_BYTES):
                image[address + line] = data[offset + line]
    return image
