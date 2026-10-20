"""The piece lab: the planned tile set (docs/tile-set.md), drawn.

    uv run strat-piece-lab [OUTPUT_DIRPATH]

A scene built by hand, not generated: a forest, a hut (plank walls, a brick
roof, a plank back wall, doors, a window, a torch, a workbench, a chest), a
ladder down a shaft into a cave, a basement with a stone back wall, a
furnace and an anvil, a platform, vines, a rope, grass and mushrooms; and
the miner in five places, two of them behind a tree drawn in front.

Each piece is a whole tile (8 pixels by 16 lines), drawn over a backdrop
(sky, cave, a plank back wall, a stone back wall) two ways:

    masked       the piece has its own mask: '.' shows the backdrop, black
                 is black (64 bytes of graphics and 64 of mask)
    black-clear  black shows the backdrop, so pieces cost only 64 bytes, and
                 a 256-byte table finds the clear pixels of any screen byte

Writes pieces.png (each piece over each backdrop, both ways), scene.png
(the whole scene, both ways, unlit and lit) and views.png (close-ups), and
prints what the graphics cost.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from stratagem import lighting
from stratagem.lighting import FULL
from stratagem.lighting_lab import RGB, backdrop_pixels, draw_sprite, sheet
from stratagem.sprites import frame_pixels
from stratagem.tiles import (BLACK, BLUE, GRASS, RED, SHAPE_FULL, SOIL, STONE, TILE_LINE_HEIGHT,
                             TILE_PIXEL_WIDTH, TORCH_ART, TORCH_LEFT, TORCH_TOP, tile_pixels)

W, H = TILE_PIXEL_WIDTH, TILE_LINE_HEIGHT
COLOURS = {"K": 0, "R": 1, "G": 2, "Y": 3, "B": 4, "M": 5, "C": 6, "W": 7}
CLEAR = -1


def _hash(x: int, y: int, salt: int = 0) -> int:
    h = (x * 73 + y * 151 + salt * 97) & 0xFF
    h ^= h >> 3
    return (h * 29 + 11) & 0xFF


def art(text: str, width: int = W, height: int = H) -> np.ndarray:
    """Rows of characters: '.' clear, K black, R G Y B M C W colours."""
    rows = [line for line in text.split("\n") if line.strip()]
    rows += ["." * width] * (height - len(rows))
    assert len(rows) == height and all(len(r) == width for r in rows), text
    return np.array([[CLEAR if c == "." else COLOURS[c] for c in row] for row in rows])


def split(big: np.ndarray, columns: int, rows: int) -> list[list[np.ndarray]]:
    """A picture of columns x rows tiles, as [row][column] tiles."""
    return [[big[j * H:(j + 1) * H, i * W:(i + 1) * W] for i in range(columns)] for j in range(rows)]


# Trees: a canopy three tiles wide and two high (dithered leaves, as in
# Stryker's Run, so that backdrop shows through), over a trunk.

def _canopy() -> np.ndarray:
    width, height = 3 * W, 2 * H
    out = np.full((height, width), CLEAR)
    cx, cy = (width - 1) / 2, height * 0.55
    for y in range(height):
        for x in range(width):
            # Pixels are twice as wide as tall: measure in lines.
            dx, dy = (x - cx) * 2 / (width * 1.0), (y - cy) / (height * 0.58)
            lump = (_hash(x // 2, y // 3, 5) - 128) / 900
            if dx * dx + dy * dy > 1 + lump:
                continue
            depth = y / height
            noise = _hash(x, y, 7)
            if noise < 50 + 120 * depth * depth:
                out[y, x] = COLOURS["K"]
            elif noise > 235 - 40 * (1 - depth) and depth < 0.5:
                out[y, x] = COLOURS["Y"]
            else:
                out[y, x] = COLOURS["G"]
    # The trunk's top, among the lowest leaves.
    for y in range(height - 5, height):
        for x in range(W + 2, W + 6):
            if out[y, x] == CLEAR or _hash(x, y, 9) < 120:
                out[y, x] = COLOURS["K"] if _hash(x, y, 3) < 70 else COLOURS["R"]
    return out


TRUNK = art("""
..RRKR..
..RKRR..
..RRRK..
..KRRR..
..RRKR..
..RRRR..
..RKRR..
..RRRK..
..RRKR..
..KRRR..
..RRRR..
..RKRR..
..RRKR..
..RRRK..
..RKRR..
..RRRR..
""")
TRUNK_KNOT = art("""
..RRKR..
..RKRR..
..RRRK..
..KRRRRK
..RRKRRR
..RRRR.K
..RKRR..
..RRRK..
..RRKR..
..KRRR..
KRRRRR..
RRKKRR..
.K.RRK..
..RRRK..
..RKRR..
..RRRR..
""")
ROOT = art("""
..RRKR..
..RKRR..
..RRRK..
..KRRR..
..RRKR..
..RRRR..
..RKRR..
..RRRK..
..RRKR..
..KRRR..
..RRRR..
.RRKRRR.
.RKRRKRR
RRK.RRKR
RK..KRRR
K....KRK
""")

VINE = art("""
...G....
...G....
....G...
...GG...
..GG.G..
...G....
....G...
....GG..
...G.GG.
...G....
....G...
...G....
..GG....
.G.G....
...G....
....G...
""")
VINE_END = art("""
...G....
....G...
...GG...
..G.G...
....G...
...G....
...G....
..GGG...
...G....
""")
TUFT = art("""
........
........
........
........
........
........
........
........
........
........
......G.
.G....G.
.G.G.GG.
GG.G.G..
.GGGGG.G
GGGGGGGG
""")
MUSHROOM = art("""
........
........
........
........
........
........
........
........
..RRR...
.RWRRR..
RRRRWRR.
RWRRRRR.
...WW...
...WW...
...WW...
..WWW...
""")
PLANKS = art("""
KKKKKKKK
YYYRYYYK
YRYYYYYK
YYYYYRYK
KKKKKKKK
YYKYYRYY
RYKYYYYY
YYKYRYYY
KKKKKKKK
YYYRYYYK
YRYYYYYK
YYYYYRYK
KKKKKKKK
YYKYYRYY
RYKYYYYY
YYKYRYYY
""")
BRICKS = art("""
WWWWWWWW
RRRWRRRR
RRRWRRRR
RRRWRRRK
WWWWWWWW
RRRRRRRW
RRRRRRRW
RRRKRRRW
WWWWWWWW
RRRWRRRR
RRRWRRRR
RRRWRRRK
WWWWWWWW
RRRRRRRW
RRRRRRRW
RRRKRRRW
""")
PLATFORM = art("""
YYYYYYYY
YRYYYRYY
KKKKKKKK
.K....K.
..K..K..
""")
LADDER = art("\n".join(".RYYYYR." if row % 4 == 2 else ".R....R." for row in range(H)))
ROPE = art("\n".join("...YR..." if row % 2 else "...RY..." for row in range(H)))
ROPE_END = art("\n".join(["...YR...", "...RY..."] * 5 + ["..YRY...", "..Y.R...", ".Y...R.."]))
DOOR_TOP = art("\n".join(["KKKKKKKK"] + ["KYYYYYYK" if row == 8 else "KRYRRYRK" for row in range(1, H)]))
DOOR_BOTTOM = art("\n".join(
    ["KKKKKKKK" if row == H - 1 else "KYYYYYYK" if row == 8 else "KRYRRYWK" if row == 3 else "KRYRRYRK"
     for row in range(H)]))
DOOR_OPEN_TOP = art("\n".join(["KKK....."] + ["KRY....."] * (H - 1)))
DOOR_OPEN_BOTTOM = art("\n".join(["KRY....."] * (H - 1) + ["KKK....."]))
WINDOW = art("""
KKKKKKKK
KCCCKCCK
KCWCKCCK
KCCCKCCK
KCCCKCCK
KCCCKCWK
KCCCKCCK
KKKKKKKK
KCCWKCCK
KCCCKCCK
KCCCKCCK
KCCCKCCK
KWCCKCCK
KCCCKCCK
KCCCKCCK
KKKKKKKK
""")
TORCH = np.full((H, W), CLEAR)
for _j, _row in enumerate(TORCH_ART.split()):
    for _i, _c in enumerate(_row):
        if _c != ".":
            TORCH[TORCH_TOP + _j, TORCH_LEFT + _i] = COLOURS[_c]
BENCH = split(art("""
................
................
................
................
................
..W.............
..WRRRR......Y..
YYYYYYYYYYYYYYYY
RRRRRRRRRRRRRRRR
KKKKKKKKKKKKKKKK
.RK..........KR.
.RK..........KR.
.RK..........KR.
.RK..........KR.
.RK..........KR.
.RK..........KR.
""", 2 * W, H), 2, 1)[0]
ANVIL = split(art("""
................
................
................
................
................
................
................
................
..WWWWWWWWWWWW..
WWWWWWWWWWWWW...
.KWWWWWWWWWWK...
...KWWWWWWWK....
....WWWWWWW.....
...WWWWWWWWW....
..WWWWWWWWWWW...
..KKKKKKKKKKK...
""", 2 * W, H), 2, 1)[0]
CHEST = art("""
........
........
........
........
........
........
.KKKKKK.
KYRRRRYK
KRRRRRRK
KYYYYYYK
KRRWWRRK
KRRKWRRK
KRRRRRRK
KYRRRRYK
KRRRRRRK
KKKKKKKK
""")


def _furnace() -> np.ndarray:
    width, height = 2 * W, 2 * H
    out = np.full((height, width), CLEAR)
    cx = (width - 1) / 2
    for y in range(height):
        for x in range(width):
            dx = (x - cx) / (width / 2)
            top = 6 + 10 * dx * dx
            if y < top:
                continue
            mortar = y % 5 == 0 or (x + 3 * (y // 5)) % 5 == 0
            out[y, x] = COLOURS["K"] if mortar else COLOURS["W"]
    for y in range(18, 29):                     # the fire's mouth
        for x in range(5, 11):
            n = _hash(x, y, 11)
            out[y, x] = COLOURS["Y"] if n < 70 + (y - 18) * 8 else COLOURS["R"] if n < 200 else COLOURS["K"]
    return out


CANOPY = split(_canopy(), 3, 2)
FURNACE = split(_furnace(), 2, 2)

# The pieces: name -> (graphic, blocks light, blocks the miner).
PIECES = {
    "canopy top left": (CANOPY[0][0], False, False),
    "canopy top": (CANOPY[0][1], False, False),
    "canopy top right": (CANOPY[0][2], False, False),
    "canopy left": (CANOPY[1][0], False, False),
    "canopy over trunk": (CANOPY[1][1], False, False),
    "canopy right": (CANOPY[1][2], False, False),
    "trunk": (TRUNK, False, False),
    "trunk, knot": (TRUNK_KNOT, False, False),
    "root": (ROOT, False, False),
    "vine": (VINE, False, False),
    "vine end": (VINE_END, False, False),
    "grass tuft": (TUFT, False, False),
    "mushroom": (MUSHROOM, False, False),
    "planks": (PLANKS, True, True),
    "bricks": (BRICKS, True, True),
    "platform": (PLATFORM, False, False),
    "ladder": (LADDER, False, False),
    "rope": (ROPE, False, False),
    "rope end": (ROPE_END, False, False),
    "door top": (DOOR_TOP, True, True),
    "door bottom": (DOOR_BOTTOM, True, True),
    "door open top": (DOOR_OPEN_TOP, False, False),
    "door open bottom": (DOOR_OPEN_BOTTOM, False, False),
    "window": (WINDOW, False, True),
    "torch": (TORCH, False, False),
    "bench left": (BENCH[0], False, False),
    "bench right": (BENCH[1], False, False),
    "furnace top left": (FURNACE[0][0], True, True),
    "furnace top right": (FURNACE[0][1], True, True),
    "furnace left": (FURNACE[1][0], True, True),
    "furnace right": (FURNACE[1][1], True, True),
    "anvil left": (ANVIL[0], False, False),
    "anvil right": (ANVIL[1], False, False),
    "chest": (CHEST, False, False),
}


# Backdrops: what shows through a tile's clear parts.

def _backdrop(colour_at) -> np.ndarray:
    return np.array([[colour_at(x, y) for x in range(W)] for y in range(H)])


BACKDROPS = {
    "sky": _backdrop(lambda x, y: BLUE),
    "cave": _backdrop(backdrop_pixels),
    # Back walls are dim, so that what stands in front of them reads.
    "plank wall": _backdrop(lambda x, y: RED if x not in (3, 7) and (x + 2 * y) % 4 == 0 else BLACK),
    "stone wall": _backdrop(lambda x, y: BLUE if (y % 8 == 0 or x == (0 if y // 8 % 2 else 4)) and (x + y) % 2
                            else BLACK),
}

MODES = ["masked", "black-clear"]


def over(piece: np.ndarray, back: np.ndarray, mode: str) -> np.ndarray:
    """A piece drawn over a backdrop."""
    clear = piece == CLEAR
    if mode == "black-clear":
        clear |= piece == BLACK
    return np.where(clear, back, piece)


def front_mask(piece: np.ndarray, mode: str) -> np.ndarray:
    """The pixels of a piece drawn in front of the miner."""
    mask = piece != CLEAR
    if mode == "black-clear":
        mask &= piece != BLACK
    return mask


# The scene.

@dataclass
class Cell:
    terrain: int | None = None      # a material, drawn whole (SHAPE_FULL)
    piece: str | None = None
    back: str = "cave"
    front: bool = False             # the piece is drawn in front of the miner


WIDTH, HEIGHT = 44, 30
SURFACE = 12


def build_scene() -> list[list[Cell]]:
    cells = [[Cell(back="sky" if y < SURFACE else "cave") for x in range(WIDTH)] for y in range(HEIGHT)]

    def put(x, y, piece, front=False, back=None):
        cells[y][x].piece, cells[y][x].front = piece, front
        if back:
            cells[y][x].back = back

    for x in range(WIDTH):
        for y in range(SURFACE, HEIGHT):
            cells[y][x].terrain = GRASS if y == SURFACE else SOIL if y < SURFACE + 5 else STONE

    def dig(x0, y0, x1, y1):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                cells[y][x].terrain = None

    # A forest: canopies touching, every third column; two trees in front.
    for n, trunk_x in enumerate((2, 5, 8, 11, 14)):
        front = trunk_x in (5, 11)
        for j, row in enumerate(("top", "")):
            for i, side in enumerate((" left", "", " right")):
                name = {"top": "canopy top", "": "canopy"}[row] + side
                if name == "canopy":
                    name = "canopy over trunk"
                put(trunk_x - 1 + i, 7 + j, name, front)
        put(trunk_x, 9, "trunk, knot" if n % 2 else "trunk", front)
        put(trunk_x, 10, "trunk", front)
        put(trunk_x, 11, "root", front)
    for x in (0, 17, 28, 30, 41):
        put(x, 11, "grass tuft", True)

    # A hut: plank walls, a brick roof, a plank back wall, two doors, a window.
    for x in range(19, 29):
        put(x, 6, "bricks")
    for y in range(7, 12):
        put(19, y, "planks")
        put(28, y, "planks")
        for x in range(20, 28):
            cells[y][x].back = "plank wall"
    put(19, 10, "door top")
    put(19, 11, "door bottom")
    put(28, 10, "door open top", back="plank wall")
    put(28, 11, "door open bottom", back="plank wall")
    put(28, 8, "window", back="plank wall")
    put(21, 8, "torch")
    put(22, 11, "bench left")
    put(23, 11, "bench right")
    put(26, 11, "chest")

    # A ladder down a shaft from the hut's floor into a cave.
    dig(24, SURFACE, 24, 20)
    for y in range(11, 21):
        put(24, y, "ladder")

    # The cave, a basement walled off in it, a platform, vines and a rope.
    dig(4, 20, 41, 26)
    dig(9, 19, 16, 19)
    dig(30, 21, 38, 26)
    for y in range(20, 27):
        put(27, y, "bricks")
        for x in range(19, 27):
            cells[y][x].back = "stone wall"
    for x in range(19, 27):
        put(x, 19, "bricks")
    cells[19][24].piece = "ladder"
    put(27, 25, "door open top", back="stone wall")
    put(27, 26, "door open bottom", back="stone wall")
    put(20, 25, "furnace top left")
    put(21, 25, "furnace top right")
    put(20, 26, "furnace left")
    put(21, 26, "furnace right")
    put(22, 22, "torch")
    put(25, 26, "anvil left")
    put(26, 26, "anvil right")
    put(26, 22, "torch")
    for x in range(31, 37):
        put(x, 23, "platform")
    for x, length in ((7, 3), (11, 5), (14, 2)):
        top = 19 if 9 <= x <= 16 else 20
        for y in range(top, top + length - 1):
            put(x, y, "vine")
        put(x, top + length - 1, "vine end")
    for y in range(20, 25):
        put(40, y, "rope")
    put(40, 25, "rope end")
    put(6, 26, "mushroom", True)
    put(15, 26, "mushroom", True)
    put(13, 23, "torch")
    put(35, 22, "torch")
    return cells


# Where the miner stands: (tile x, tile y of the feet, what to show).
MINERS = [(5, 11, "behind a tree"), (8, 11, "in front of a tree"), (25, 11, "in the hut"),
          (24, 16, "on the ladder"), (33, 22, "on the platform"), (16, 26, "behind a mushroom")]

LIGHT_SOURCES = {"torch": FULL, "furnace left": 12, "furnace right": 12}


def light_of(cells) -> np.ndarray:
    clear = np.array([[c.terrain is None and not (c.piece and PIECES[c.piece][1]) for c in row] for row in cells])
    sun = lighting.shaft_sunlight(clear)
    sources = np.array([[LIGHT_SOURCES.get(c.piece, 0) for c in row] for row in cells])
    lamps = lighting.spread(sources, clear, 2, 3)
    lamps = lighting.spread(lamps, clear, None, wall_step=4)
    return np.maximum(sun, lamps)


def scene_pixels(cells, mode: str) -> tuple[np.ndarray, np.ndarray]:
    """The scene's pixels, and the mask of pixels drawn in front of sprites."""
    pixels = np.zeros((HEIGHT * H, WIDTH * W), dtype=int)
    front = np.zeros(pixels.shape, dtype=bool)
    for y, row in enumerate(cells):
        for x, c in enumerate(row):
            if c.terrain is not None:
                tile = np.array(tile_pixels(c.terrain, SHAPE_FULL))
            else:
                tile = BACKDROPS[c.back]
                if c.piece:
                    piece = PIECES[c.piece][0]
                    tile = over(piece, tile, mode)
                    if c.front:
                        front[y * H:(y + 1) * H, x * W:(x + 1) * W] = front_mask(piece, mode)
            pixels[y * H:(y + 1) * H, x * W:(x + 1) * W] = tile
    return pixels, front


def picture(cells, mode: str, lit: bool, window=None, scale: int = 1) -> Image.Image:
    pixels, front = scene_pixels(cells, mode)
    if lit:
        light = light_of(cells)
        levels = np.repeat(np.repeat(light, H, axis=0), W, axis=1)
        pixels = lighting.lit_pixels(pixels, levels)
    under = pixels.copy()
    miner = frame_pixels("stand", False)
    for x, y, _ in MINERS:
        draw_sprite(pixels, miner, x * W + 1, (y + 1) * H - len(miner))
    pixels = np.where(front, under, pixels)
    x0, y0, width, height = window or (0, 0, WIDTH, HEIGHT)
    crop = pixels[y0 * H:(y0 + height) * H, x0 * W:(x0 + width) * W]
    image = Image.fromarray(np.array(RGB, dtype=np.uint8)[crop])
    return image.resize((image.width * 2 * scale, image.height * scale), Image.NEAREST)


def catalogue(mode: str) -> Image.Image:
    """Every piece (down) over every backdrop (across)."""
    names = list(PIECES)
    pixels = np.zeros((len(names) * (H + 2), len(BACKDROPS) * (W + 2)), dtype=int)
    for j, name in enumerate(names):
        for i, back in enumerate(BACKDROPS.values()):
            pixels[j * (H + 2):j * (H + 2) + H, i * (W + 2):i * (W + 2) + W] = over(PIECES[name][0], back, mode)
    image = Image.fromarray(np.array(RGB, dtype=np.uint8)[pixels])
    return image.resize((image.width * 2 * 3, image.height * 3), Image.NEAREST)


def costs(cells) -> list[str]:
    pieces, backdrops = len(PIECES), len(BACKDROPS)
    used = {(c.piece, c.back) for row in cells for c in row if c.piece and c.terrain is None}
    return [
        f"{pieces} pieces, {backdrops} backdrops (64 bytes each: {64 * backdrops})",
        f"  black-clear: {64 * pieces} bytes, and 256 for the clear-pixel table: {64 * pieces + 256}",
        f"  masked: {128 * pieces} bytes",
        f"  pre-composed over each backdrop: {64 * pieces * backdrops} bytes "
        f"(this scene uses {len(used)} pairs: {64 * len(used)})",
    ]


def main() -> None:
    output_dirpath = Path(sys.argv[1] if len(sys.argv) > 1 else "build/pieces")
    output_dirpath.mkdir(parents=True, exist_ok=True)
    cells = build_scene()
    sheet([(mode, catalogue(mode)) for mode in MODES], 2).save(output_dirpath / "pieces.png")
    sheet([(f"{mode}, {'lit' if lit else 'unlit'}", picture(cells, mode, lit))
           for lit in (False, True) for mode in MODES], 2).save(output_dirpath / "scene.png")
    windows = [("forest", (0, 5, 18, 8)), ("hut", (17, 5, 13, 8)), ("cave", (3, 18, 18, 10)),
               ("basement and platform", (18, 18, 25, 10))]
    sheet([(f"{label}, {mode}", picture(cells, mode, True, window, scale=3))
           for label, window in windows for mode in MODES], 2).save(output_dirpath / "views.png")
    print("\n".join(costs(cells)))
    print(f"Wrote {output_dirpath}")


if __name__ == "__main__":
    main()
