"""Screen geometry and MODE 2 pixel encoding.

The view is 128 x 256 MODE 2 pixels: 64 CRTC character columns (one byte,
two pixels, wide) by 32 character rows of 8 lines, 16K at &4000 with the
hardware wrap set for a 16K screen. Within a character row, byte
(column * 8 + line) holds line `line` of column `column`.
"""

from __future__ import annotations

SCREEN_START = 0x4000
SCREEN_SIZE = 0x4000
SCREEN_END = SCREEN_START + SCREEN_SIZE
COLUMNS = 64
ROW_BYTES = COLUMNS * 8   # 512

TILE_WIDTH_PIXELS = 8
TILE_HEIGHT_LINES = 16
TILE_WIDTH_BYTES = TILE_WIDTH_PIXELS // 2   # 4 character columns
TILE_BYTES = TILE_WIDTH_BYTES * TILE_HEIGHT_LINES   # 64
VIEW_TILES = 16           # the view is 16 x 16 tiles
TILE_COLUMN_STEP = TILE_WIDTH_BYTES * 8     # 32: screen bytes between horizontally adjacent tiles
TILE_ROW_STEP = ROW_BYTES * 2               # 1024: screen bytes between vertically adjacent tiles


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
    """Encode a tile, given as 16 rows of 8 logical colours, in screen order:
    the top character row (four columns of eight lines), then the bottom."""
    assert len(pixels) == TILE_HEIGHT_LINES and all(len(row) == TILE_WIDTH_PIXELS for row in pixels)
    data = bytearray()
    for char_row in range(2):
        for column in range(TILE_WIDTH_BYTES):
            for line in range(8):
                row = pixels[char_row * 8 + line]
                data.append(mode2_byte(row[2 * column], row[2 * column + 1]))
    return bytes(data)


def tile_address(screen_start: int, tile_x: int, tile_y: int) -> int:
    """The screen address of the top-left byte of view tile (tile_x, tile_y)."""
    return wrap(screen_start + tile_y * TILE_ROW_STEP + tile_x * TILE_COLUMN_STEP)


def render_view(screen_start: int, tiles: list[list[int]], graphics: list[bytes]) -> bytearray:
    """Render a 16 x 16 view (tiles[y][x] tile numbers) into a 16K image of
    &4000-&7FFF, with the view's top-left tile at screen_start."""
    image = bytearray(SCREEN_SIZE)
    for tile_y in range(VIEW_TILES):
        for tile_x in range(VIEW_TILES):
            data = graphics[tiles[tile_y][tile_x]]
            address = tile_address(screen_start, tile_x, tile_y)
            for half in range(2):
                base = wrap(address + half * ROW_BYTES) - SCREEN_START
                image[base:base + 32] = data[half * 32:half * 32 + 32]
    return image
