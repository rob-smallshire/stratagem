"""The loading page: a MODE 7 teletext page, shown while the game loads
(asm/loading_page.asm, in MUSIC).

- The title, STRATAGEM, in mosaic graphics, as the cover has it: chunky
  rock letters in strata, yellow at the top to red and a dark band
  beneath. Teletext changes colour only at a control cell, so each row of
  the title is one colour, and the strata are the rows.
- The ceiling of a cave in yellow, with a stalactite hanging over the
  left, and the keys to its right.
- Drips that form at the stalactite's tip, fall, and fill a pool in the
  floor a sixel at a time: the pool is the progress bar.

Coordinates are in sixels: x 0-79 (two a cell), y 0-74 (three a cell).
Column 0 of each row holds the row's first control code.
"""

from __future__ import annotations

ROWS, COLUMNS = 25, 40
SCREEN_START = 0x7C00

ALPHA_CYAN, ALPHA_WHITE = 0x86, 0x87
GRAPHICS = {"red": 0x91, "yellow": 0x93, "blue": 0x94, "magenta": 0x95}
HOLD_GRAPHICS = 0x9E
SPACE = 0x20
MOSAIC = 0xA0                   # a graphics cell with no sixels; add SIXEL_BITS
# (SPACE is blank in graphics too, and what MODE 7 clears the screen to)
# Sixel bits within a cell: (x % 2, y % 3) -> bit.
SIXEL_BITS = {(0, 0): 1, (1, 0): 2, (0, 1): 4, (1, 1): 8, (0, 2): 16, (1, 2): 64}

# The title: STRATAGEM, twelve sixels high, in four rows of colour.
TITLE_ROW = 0
TITLE_BANDS = ("yellow", "yellow", "red", "magenta")
LETTERS = {
    "S": [".#####.",
          "#######",
          "##...##",
          "##.....",
          "####...",
          ".#####.",
          "..#####",
          "....###",
          ".....##",
          "##...##",
          "#######",
          ".#####."],
    "T": ["#######",
          "#######",
          "..###..",
          "..###..",
          "..###..",
          "..###..",
          "..###..",
          "..###..",
          "..###..",
          "..###..",
          "..###..",
          "..###.."],
    "R": ["######.",
          "#######",
          "##...##",
          "##...##",
          "##..###",
          "######.",
          "#####..",
          "##.###.",
          "##..###",
          "##...##",
          "##...##",
          "##...##"],
    "A": ["...##...",
          "..####..",
          "..####..",
          ".##..##.",
          ".##..##.",
          "##....##",
          "########",
          "########",
          "##....##",
          "##....##",
          "##....##",
          "##....##"],
    "G": [".#####.",
          "#######",
          "##...##",
          "##.....",
          "##.....",
          "##.####",
          "##.####",
          "##...##",
          "##...##",
          "##...##",
          "#######",
          ".#####."],
    "E": ["######",
          "######",
          "##....",
          "##....",
          "##....",
          "#####.",
          "#####.",
          "##....",
          "##....",
          "##....",
          "######",
          "######"],
    "M": ["##.....##",
          "###...###",
          "####.####",
          "##.###.##",
          "##..#..##",
          "##.....##",
          "##.....##",
          "##.....##",
          "##.....##",
          "##.....##",
          "##.....##",
          "##.....##"],
}
TITLE = "STRATAGEM"
LETTER_GAP = 1

# The cave.
CEILING_ROW = 5                 # solid; the row below it jagged
STALACTITE_TIP = (11, 44)       # its point: x, y
STALACTITE_TOP = 18
DRIP_X = STALACTITE_TIP[0]
DRIP_TOP = STALACTITE_TIP[1] + 1    # where a drip forms
FLOOR_ROW = 22                  # two rows of floor, the pool in them
POOL_COLUMNS = range(4, 8)      # the water's cells; the controls either side
POOL_LEFT_CONTROL, POOL_RIGHT_CONTROL = 3, 8
POOL_TOP = FLOOR_ROW * 3
POOL_BOTTOM = (FLOOR_ROW + 2) * 3 - 1
POOL_SIXELS = len(POOL_COLUMNS) * 2 * (POOL_BOTTOM - POOL_TOP + 1)
DRIP_ROWS = range(DRIP_TOP // 3, FLOOR_ROW)     # the cells a drip passes through
assert DRIP_TOP % 3 == 0 and DRIP_X // 2 in POOL_COLUMNS

# The keys, right of the stalactite.
KEYS_ROW, KEYS_COLUMN = 8, 12
KEYS = [("Z", "LEFT"), ("X", "RIGHT"), ("K", "JUMP"), ("L", "DIG"), ("K/M + L", "UP/DOWN"),
        ("SPACE", "PLACE"), ("TAB", "NEXT"), ("1-9", "TOOLS"), ("P", "PACK")]
STATUS_ROW, STATUS_COLUMN = 21, 12
STATUS_LOADING = "LOADING"
STATUS_LOADED = "PRESS SPACE TO START"
STATUS_WIDTH = COLUMNS - STATUS_COLUMN - 1


def title_sixels() -> set[tuple[int, int]]:
    width = sum(len(LETTERS[c][0]) for c in TITLE) + LETTER_GAP * (len(TITLE) - 1)
    x0 = 2 + (2 * COLUMNS - 2 - width) // 2
    sixels = set()
    for letter in TITLE:
        glyph = LETTERS[letter]
        for y, line in enumerate(glyph):
            sixels |= {(x0 + x, TITLE_ROW * 3 + y) for x, c in enumerate(line) if c == "#"}
        x0 += len(glyph[0]) + LETTER_GAP
    return sixels


def _jag(x: int) -> int:
    """The ceiling's depth below its solid row, at x: small stalactites."""
    return (0, 1, 2, 1, 0, 1, 3, 2, 1, 0, 2, 1, 1, 4, 2, 0, 1, 2, 0, 1, 1, 3, 1, 0)[x * 7 % 24]


def cave_sixels() -> set[tuple[int, int]]:
    """The ceiling, the stalactite and the floor (the pool's cells apart)."""
    sixels = set()
    top = CEILING_ROW * 3
    for x in range(2, 2 * COLUMNS):
        sixels |= {(x, y) for y in range(top, top + 3 + _jag(x))}
    tip_x, tip_y = STALACTITE_TIP
    for y in range(STALACTITE_TOP, tip_y + 1):
        t = (tip_y - y) / (tip_y - STALACTITE_TOP)
        left, right = round(tip_x - 6 * t), round(tip_x + 4 * t)
        sixels |= {(x, y) for x in range(left, right + 1)}
    floor_columns = set(range(2, COLUMNS)) - set(POOL_COLUMNS) - {POOL_LEFT_CONTROL, POOL_RIGHT_CONTROL}
    for y in range(POOL_TOP, POOL_BOTTOM + 1):
        for column in floor_columns:
            sixels |= {(2 * column + dx, y) for dx in (0, 1) if not (y == POOL_TOP and (2 * column + dx) % 9 == 4)}
    return sixels


def mosaic(sixels: set[tuple[int, int]], column: int, row: int) -> int:
    return MOSAIC + sum(bit for (dx, dy), bit in SIXEL_BITS.items() if (2 * column + dx, 3 * row + dy) in sixels)


def key_line(key: str, action: str) -> bytes:
    """A line of the keys: the key in cyan, dots, and what it does in white,
    to the right edge."""
    dots = COLUMNS - KEYS_COLUMN - 4 - len(key) - len(action)
    return bytes([ALPHA_CYAN]) + key.encode() + b" " + b"." * dots + b" " + bytes([ALPHA_WHITE]) + action.encode()


def status_line(text: str) -> bytes:
    return bytes([ALPHA_WHITE]) + text.ljust(STATUS_WIDTH).encode()


def page() -> list[bytearray]:
    """The page as first shown: rows of 40 bytes, the pool empty, no drip."""
    rows = [bytearray([SPACE] * COLUMNS) for _ in range(ROWS)]
    title = title_sixels()
    for band, colour in enumerate(TITLE_BANDS):
        row = TITLE_ROW + band
        rows[row][0] = GRAPHICS[colour]
        rows[row][1:] = bytes(mosaic(title, c, row) for c in range(1, COLUMNS))
    cave = cave_sixels()
    for row in range(CEILING_ROW, DRIP_TOP // 3):
        rows[row][0] = GRAPHICS["yellow"]
        rows[row][1:] = bytes(mosaic(cave, c, row) for c in range(1, COLUMNS))
    for row in range(DRIP_TOP // 3, FLOOR_ROW):
        rows[row][0] = GRAPHICS["blue"]
    for index, (key, action) in enumerate(KEYS):
        rows[KEYS_ROW + index][KEYS_COLUMN:] = key_line(key, action)
    rows[STATUS_ROW][STATUS_COLUMN:] = status_line(STATUS_LOADING)
    # The floor: hold graphics, so that the colour changes either side of the
    # pool show the cell before them, not a gap.
    for row in (FLOOR_ROW, FLOOR_ROW + 1):
        rows[row][0] = GRAPHICS["yellow"]
        rows[row][1] = HOLD_GRAPHICS
        rows[row][2:] = bytes(mosaic(cave, c, row) for c in range(2, COLUMNS))
        rows[row][POOL_LEFT_CONTROL] = GRAPHICS["blue"]
        rows[row][POOL_RIGHT_CONTROL] = GRAPHICS["yellow"]
    for row in rows:
        assert len(row) == COLUMNS
    return rows


def pool_order() -> list[tuple[int, int]]:
    """The pool's sixels in the order they fill: from the bottom, a row at a
    time, left to right."""
    return [(x, y) for y in range(POOL_BOTTOM, POOL_TOP - 1, -1)
            for x in range(2 * POOL_COLUMNS[0], 2 * (POOL_COLUMNS[-1] + 1))]


def pool_steps() -> list[tuple[int, int]]:
    """For each sixel of water, the screen address of its cell and the
    cell's byte once it has filled."""
    filled, steps = set(), []
    for x, y in pool_order():
        filled.add((x, y))
        steps.append((SCREEN_START + (y // 3) * COLUMNS + x // 2, mosaic(filled, x // 2, y // 3)))
    return steps


def vdu_stream(rows: list[bytearray]) -> bytes:
    """The VDU codes that draw the page on a MODE 7 screen just cleared:
    each row's runs, split where there are four spaces or more, after a
    move of the cursor. The last row isn't written, so the screen never
    scrolls."""
    stream = bytearray()
    for y, row in enumerate(rows[:ROWS - 1]):
        x = 0
        while x < COLUMNS:
            if row[x] == SPACE:
                x += 1
                continue
            last = x
            for i in range(x, COLUMNS):
                if row[i] != SPACE:
                    last = i
                elif i - last >= 4:
                    break
            stream += bytes([31, x, y]) + row[x:last + 1]
            x = last + 1
    return bytes(stream)


def _bytes_lines(data: bytes) -> list[str]:
    return ["    EQUB " + ", ".join(f"&{b:02X}" for b in data[i:i + 16]) for i in range(0, len(data), 16)]


def source() -> str:
    rows = page()
    steps = pool_steps()
    drip_cells = [SCREEN_START + row * COLUMNS + DRIP_X // 2 for row in DRIP_ROWS]
    drip_ys = range(DRIP_TOP, POOL_TOP)
    lines = ["\\ Generated by stratagem.gen_tables from tools/stratagem/loading_page.py", ""]
    lines += [f"LOADING_SCREEN_START = &{SCREEN_START:04X}",
              f"DRIP_TOP = {DRIP_TOP}", f"POOL_TOP = {POOL_TOP}", f"POOL_SIXELS = {POOL_SIXELS}",
              f"DRIP_CELLS = {len(drip_cells)}", f"MOSAIC = &{MOSAIC:02X}", ""]
    lines += [".loading_page_vdu"] + _bytes_lines(vdu_stream(rows)) + [".loading_page_vdu_end"]
    for name, text in (("status_loading", STATUS_LOADING), ("status_loaded", STATUS_LOADED)):
        lines += [f".{name}"] + _bytes_lines(bytes([31, STATUS_COLUMN, STATUS_ROW]) + status_line(text)) + \
                 [f".{name}_end"]
    lines += ["\\ Each drip cell's address, top down", ".drip_cell_low"] + \
        _bytes_lines(bytes(a & 0xFF for a in drip_cells)) + [".drip_cell_high"] + \
        _bytes_lines(bytes(a >> 8 for a in drip_cells))
    lines += ["\\ For each y from DRIP_TOP, its drip cell and its sixel's bit", ".drip_y_cell"] + \
        _bytes_lines(bytes((y - DRIP_TOP) // 3 for y in drip_ys)) + [".drip_y_bit"] + \
        _bytes_lines(bytes(SIXEL_BITS[(DRIP_X % 2, y % 3)] for y in drip_ys))
    lines += ["\\ For each sixel of water, its cell's address and byte", ".pool_cell_low"] + \
        _bytes_lines(bytes(a & 0xFF for a, _ in steps)) + [".pool_cell_high"] + \
        _bytes_lines(bytes(a >> 8 for a, _ in steps)) + [".pool_cell_byte"] + \
        _bytes_lines(bytes(b for _, b in steps))
    return "\n".join(lines) + "\n"
