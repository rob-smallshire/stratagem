"""The lighting lab: pictures of the real world lit in different ways.

    uv run strat-lighting-lab [OUTPUT_DIRPATH]

Writes PNGs (by default into build/lighting/) of a stretch of the generated
world with a shaft, tunnels, torches and the miner, under each lighting
method in `lighting.py`, side by side; then screen-sized views of the
favourite. Pictures are drawn at MODE 2 proportions: each pixel twice as
wide as it is tall.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from stratagem import lighting
from stratagem.lighting import FULL
from stratagem.sprites import frame_pixels
from stratagem.tiles import (AIR, BACKGROUND_SKY, BLACK, BLUE, DIGGABLE, PASSABLE, QUARTER_LINES,
                             QUARTER_PIXELS, SHAPE_BITS, SHAPE_FULL, SKY, TILE_LINE_HEIGHT, TILE_PIXEL_WIDTH,
                             solid_quarter_cells, tile_pixels)
from stratagem.world import (HEIGHTS, RAMP_BOTTOM_LEFT, RAMP_BOTTOM_RIGHT, RAMP_TOP_LEFT, RAMP_TOP_RIGHT, World,
                             background_bits)

RGB = [(0, 0, 0), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255), (255, 0, 255), (0, 255, 255),
       (255, 255, 255)]

TORCH_ART = """
.Y..
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

MARGIN = 10     # tiles of world lit beyond the picture, so light from outside it arrives


@dataclass
class Scene:
    """A window on the world: x0, y0 is its top-left tile."""
    world: World
    x0: int
    y0: int
    width: int
    height: int
    torches: list[tuple[int, int]] = field(default_factory=list)
    player: tuple[int, int] = (0, 0)       # the tile the miner stands in (feet)

    # The lit region runs from the top of the world (for daylight) to
    # MARGIN below the window, and MARGIN either side.
    @property
    def left(self) -> int:
        return self.x0 - MARGIN

    def region_tiles(self) -> list[list[tuple[int, int]]]:
        return [[self.world.tile_at(x, y) for x in range(self.left, self.x0 + self.width + MARGIN)]
                for y in range(0, self.y0 + self.height + MARGIN)]

    def in_region(self, x: int, y: int) -> tuple[int, int]:
        return x - self.left, y


def open_up(world: World, x: int, y: int) -> None:
    world.set_tile(x, y, (AIR, SHAPE_FULL | background_bits(x, y)))


def is_open(world: World, x: int, y: int) -> bool:
    material, shape = world.tile_at(x, y)
    return material in PASSABLE


def reshape(world: World, x0: int, y0: int, x1: int, y1: int) -> None:
    """Shape the walls of dug space as the generator shapes cave walls:
    a solid tile open on one side and above (or below) becomes a ramp."""
    for y in range(y0, y1):
        for x in range(x0, x1):
            material, shape = world.tile_at(x, y)
            if material not in DIGGABLE or y <= HEIGHTS[x] or shape & SHAPE_BITS != SHAPE_FULL:
                continue
            left_open, right_open = is_open(world, x - 1, y), is_open(world, x + 1, y)
            if left_open == right_open:
                continue
            if is_open(world, x, y - 1):
                new = RAMP_TOP_LEFT if left_open else RAMP_TOP_RIGHT
            elif is_open(world, x, y + 1):
                new = RAMP_BOTTOM_LEFT if left_open else RAMP_BOTTOM_RIGHT
            else:
                continue
            world.set_tile(x, y, (material, new | (shape & ~SHAPE_BITS)))


def tunnel(world: World, x: int, y: int, dx: int, dy: int, steps: int) -> tuple[int, int]:
    """Dig a tunnel two tiles high from (x, y) (the lower tile), moving dx
    across and dy down at each step; returns where it ended."""
    for _ in range(steps):
        open_up(world, x, y)
        open_up(world, x, y - 1)
        x, y = x + dx, y + dy
    return x - dx, y - dy


def mine_scene() -> Scene:
    """Hills at x 56-87, with natural caves below them; a shaft from the
    surface, and tunnels linking the caves, as a player might dig them."""
    world = World()
    scene = Scene(world, x0=56, y0=36, width=32, height=32)
    x = scene.x0
    for y in range(HEIGHTS[x + 6], 58):           # a shaft down into the cave at rows 58-59
        open_up(world, x + 6, y)
        open_up(world, x + 7, y)
    tunnel(world, x + 8, 59, 1, 0, 1)
    tunnel(world, x + 9, 60, 1, 1, 5)             # down to the cave at rows 64-65
    tunnel(world, x + 16, 65, 1, 0, 4)
    tunnel(world, x + 20, 64, 1, -1, 11)          # and up to the cave at rows 48-53
    reshape(world, scene.x0 - 1, scene.y0, scene.x0 + scene.width + 1, scene.y0 + scene.height)
    scene.torches = [(x + 2, 59), (x + 14, 65), (x + 29, 53)]
    scene.player = (x + 18, 65)
    return scene


# Lighting methods: each takes the scene's tiles and returns light per tile
# of the region.

def _clear(tiles) -> np.ndarray:
    return np.array([[lighting.transparent(tile) for tile in row] for row in tiles])


def _sources(scene: Scene, shape, points, level: int) -> np.ndarray:
    light = np.zeros(shape, dtype=int)
    for x, y in points:
        rx, ry = scene.in_region(x, y)
        light[ry, rx] = level
    return light


WALL_STEP = 4      # light lost per tile soaking into walls; None lights faces only


def _walls(light, clear, wall_step):
    """Light into walls: soaked in at wall_step a tile, or faces only."""
    if wall_step is None:
        return lighting.light_surfaces(light, clear)
    return lighting.spread(light, clear, None, wall_step=wall_step)


def daylight(scene, clear, sun=FULL, diffuse_step=None, wall_step=WALL_STEP):
    light = lighting.sky_light(clear, sun)
    if diffuse_step is not None:
        light = lighting.spread(light, clear, diffuse_step)
    return _walls(light, clear, wall_step)


def torches_kernel(scene, clear):
    light = np.zeros(clear.shape, dtype=int)
    kernel = lighting.radial_kernel(FULL, 2)
    for x, y in scene.torches:
        light = lighting.stamp(light, kernel, *scene.in_region(x, y))
    return light


def torches_spread(scene, clear, diagonal_step=3, wall_step=WALL_STEP):
    light = lighting.spread(_sources(scene, clear.shape, scene.torches, FULL), clear, 2, diagonal_step)
    return _walls(light, clear, wall_step)


def player_light(scene, clear, level=12, wall_step=WALL_STEP):
    light = lighting.spread(_sources(scene, clear.shape, [scene.player], level), clear, 3, 4)
    return _walls(light, clear, wall_step)


def everything(scene, clear, sun=FULL):
    return np.maximum.reduce([
        daylight(scene, clear, sun, diffuse_step=2),
        torches_spread(scene, clear),
        player_light(scene, clear),
    ])


# Drawing

def tile_levels(light: np.ndarray, smooth: bool) -> np.ndarray:
    """Light per pixel of the region: each tile's own level, or, if smooth,
    a level per character cell (2 pixels x 8 lines) interpolated between
    tile centres. The renderer picks a dither mask per cell either way."""
    height, width = light.shape
    if not smooth:
        return np.repeat(np.repeat(light, TILE_LINE_HEIGHT, axis=0), TILE_PIXEL_WIDTH, axis=1)
    cells_x, cells_y = TILE_PIXEL_WIDTH // 2, TILE_LINE_HEIGHT // 8
    padded = np.pad(light, 1, mode="edge").astype(float)
    cell = np.zeros((height * cells_y, width * cells_x))
    for j in range(height * cells_y):
        fy = (j + 0.5) / cells_y - 0.5 + 1
        y = int(np.floor(fy))
        ty = fy - y
        for i in range(width * cells_x):
            fx = (i + 0.5) / cells_x - 0.5 + 1
            x = int(np.floor(fx))
            tx = fx - x
            top = padded[y, x] * (1 - tx) + padded[y, x + 1] * tx
            bottom = padded[y + 1, x] * (1 - tx) + padded[y + 1, x + 1] * tx
            cell[j, i] = top * (1 - ty) + bottom * ty
    cell = np.rint(cell).astype(int)
    return np.repeat(np.repeat(cell, 8, axis=0), 2, axis=1)


def backdrop_pixels(x: int, y: int) -> int:
    """A cave backdrop, for dug and cave space to show light: sparse blue
    specks, as rock behind the open space."""
    return BLUE if (x + 3 * (y // 4)) % 8 == 0 and y % 4 == 1 else BLACK


def region_pixels(tiles, backdrop: bool = False) -> np.ndarray:
    pixels = np.block([[np.array(tile_pixels(*tile)) for tile in row] for row in tiles])
    if backdrop:
        # Where a tile shows the cave behind it, show the backdrop.
        cave = np.block([[np.array(tile_pixels(*tile)) if tile[1] & BACKGROUND_SKY == 0 and tile[0] != SKY
                          else np.full((TILE_LINE_HEIGHT, TILE_PIXEL_WIDTH), -1) for tile in row] for row in tiles])
        solid = np.block([[_solid_pixels(tile) for tile in row] for row in tiles])
        ys, xs = np.indices(pixels.shape)
        pattern = np.vectorize(backdrop_pixels)(xs, ys)
        pixels = np.where((cave >= 0) & (solid == 0), pattern, pixels)
    return pixels


def _solid_pixels(tile) -> np.ndarray:
    """1 where a tile's pixel is its material, 0 where it is open."""
    material, shape = tile
    if material in PASSABLE:
        return np.zeros((TILE_LINE_HEIGHT, TILE_PIXEL_WIDTH), dtype=int)
    cells = set(solid_quarter_cells(material, shape))
    return np.array([[int((y // QUARTER_LINES, x // QUARTER_PIXELS) in cells) for x in range(TILE_PIXEL_WIDTH)]
                     for y in range(TILE_LINE_HEIGHT)])


def draw_sprite(pixels: np.ndarray, art: list[list[int]], left: int, top: int) -> None:
    for j, row in enumerate(art):
        for i, colour in enumerate(row):
            if colour and 0 <= top + j < pixels.shape[0] and 0 <= left + i < pixels.shape[1]:
                pixels[top + j, left + i] = colour


def art_rows(art: str) -> list[list[int]]:
    colours = {".": 0, "R": 1, "G": 2, "Y": 3, "B": 4, "M": 5, "C": 6, "W": 7}
    return [[colours[c] for c in line] for line in art.split()]


def picture(scene: Scene, tiles, light: np.ndarray, smooth: bool = False, backdrop: bool = False,
            window: tuple[int, int, int, int] | None = None, scale: int = 2) -> Image.Image:
    """The scene (or `window`: x0, y0, width, height in tiles) drawn with
    `light`, sprites drawn over it unlit."""
    pixels = region_pixels(tiles, backdrop)
    lit = lighting.lit_pixels(pixels, tile_levels(light, smooth), scene.left * TILE_PIXEL_WIDTH, 0)
    for x, y in scene.torches:
        rx, ry = scene.in_region(x, y)
        draw_sprite(lit, art_rows(TORCH_ART), rx * TILE_PIXEL_WIDTH + 2, ry * TILE_LINE_HEIGHT + 6)
    px, py = scene.in_region(*scene.player)
    miner = frame_pixels("stand", False)
    draw_sprite(lit, miner, px * TILE_PIXEL_WIDTH + 1, (py + 1) * TILE_LINE_HEIGHT - len(miner))
    wx, wy, ww, wh = window or (scene.x0, scene.y0, scene.width, scene.height)
    rx, ry = scene.in_region(wx, wy)
    crop = lit[ry * TILE_LINE_HEIGHT:(ry + wh) * TILE_LINE_HEIGHT, rx * TILE_PIXEL_WIDTH:(rx + ww) * TILE_PIXEL_WIDTH]
    rgb = np.array(RGB, dtype=np.uint8)[crop]
    image = Image.fromarray(rgb)
    return image.resize((image.width * 2 * scale, image.height * scale), Image.NEAREST)


def sheet(panels: list[tuple[str, Image.Image]], columns: int) -> Image.Image:
    font = ImageFont.load_default(size=20)
    label_height, gap = 32, 12
    width, height = panels[0][1].size
    rows = -(-len(panels) // columns)
    out = Image.new("RGB", (columns * (width + gap) + gap, rows * (height + label_height + gap) + gap), (40, 40, 48))
    draw = ImageDraw.Draw(out)
    for n, (label, image) in enumerate(panels):
        x = gap + n % columns * (width + gap)
        y = gap + n // columns * (height + label_height + gap)
        draw.text((x, y + 4), label, fill=(230, 230, 230), font=font)
        out.paste(image, (x, y + label_height))
    return out


def main() -> None:
    output_dirpath = Path(sys.argv[1] if len(sys.argv) > 1 else "build/lighting")
    output_dirpath.mkdir(parents=True, exist_ok=True)
    scene = mine_scene()
    tiles = scene.region_tiles()
    clear = _clear(tiles)
    full = np.full(clear.shape, FULL)

    lit = everything(scene, clear)
    dusk = everything(scene, clear, sun=6)
    methods = [
        ("unlit-as-now", "unlit (as now)", full, {}),
        ("daylight-faces", "daylight down, faces only", daylight(scene, clear, wall_step=None), {}),
        ("daylight-soaked", "daylight down, into walls", daylight(scene, clear), {}),
        ("daylight-spreading", "daylight spreading, into walls", daylight(scene, clear, diffuse_step=2), {}),
        ("torches-kernel", "torches, radial kernel", torches_kernel(scene, clear), {}),
        ("torches-faces", "torches spread, faces only", torches_spread(scene, clear, wall_step=None), {}),
        ("torches-soaked", "torches spread, into walls", torches_spread(scene, clear), {}),
        ("miner", "miner's light, radius 3", player_light(scene, clear), {}),
        ("everything", "everything", lit, {}),
        ("everything-per-cell", "everything, light per cell", lit, {"smooth": True}),
        ("everything-backdrop", "everything, cave backdrop", lit, {"backdrop": True}),
        ("everything-per-cell-backdrop", "per cell, backdrop", lit, {"smooth": True, "backdrop": True}),
        ("dusk", "dusk (sun 6)", dusk, {}),
        ("dusk-per-cell", "dusk, per cell", dusk, {"smooth": True}),
        ("dusk-backdrop", "dusk, backdrop", dusk, {"backdrop": True}),
        ("dusk-per-cell-backdrop", "dusk, per cell, backdrop", dusk, {"smooth": True, "backdrop": True}),
    ]
    panels = []
    for n, (slug, label, light, options) in enumerate(methods):
        image = picture(scene, tiles, light, scale=1, **options)
        image.save(output_dirpath / f"{n:02}-{slug}.png")
        panels.append((label, image))
    sheet(panels, 4).save(output_dirpath / "methods.png")

    x = scene.x0
    views = [
        ("at the shaft head", (x, 36, 16, 16)),
        ("down the shaft", (x, 48, 16, 16)),
        ("the miner's tunnel", (x + 10, 52, 16, 16)),
        ("the far cave", (x + 16, 42, 16, 16)),
    ]
    screens = [(f"{label}{', per cell' if smooth else ''}",
                picture(scene, tiles, lit, smooth, backdrop=True, window=window, scale=2))
               for label, window in views for smooth in (False, True)]
    sheet(screens, 4).save(output_dirpath / "screens.png")
    print(f"Wrote {output_dirpath}")


if __name__ == "__main__":
    main()
