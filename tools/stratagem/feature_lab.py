"""The feature and support lab: trees as features of the generator, and
pieces held up by support (docs/tile-set.md, Support), drawn.

    uv run strat-feature-lab [OUTPUT_DIRPATH]

Writes, into build/features/:

    forest.png      the generated surface with its trees, in stretches
    support.png     structures built by hand, held up with a span of 3 and
                    of 5: as built, with what isn't held outlined, and after
                    it has fallen
    collapse.png    frames of things coming down: a tree felled at its
                    trunk, a bridge undermined, a roof losing a wall
    collapse.gif    the same, moving

and prints what trees cost: how many there are, the most distinct pairs of
piece and backdrop any view of the surface needs (slots: 56), and the
look-ups a tile takes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from stratagem import features, support
from stratagem.lighting_lab import RGB, sheet
from stratagem.piece_lab import BACKDROPS, PIECES, Cell, over
from stratagem.tiles import GRASS, MAGENTA, SHAPE_FULL, SOIL, STONE, tile_pixels
from stratagem.world import HEIGHTS, WORLD_SIZE, generate_tile

W, H = 8, 16                # a tile's pixels and lines
VIEW_COLUMNS = 16           # tiles across a view
SPANS = (3, 5)
PER_FRAME = 2               # pieces falling a frame


# Drawing

def draw(cells, outline=(), scale: int = 2) -> Image.Image:
    """Cells as pixels: terrain whole, pieces over their backdrops; the
    pieces at `outline` ringed in magenta."""
    height, width = len(cells), len(cells[0])
    pixels = np.zeros((height * H, width * W), dtype=int)
    for y, row in enumerate(cells):
        for x, cell in enumerate(row):
            if cell.terrain is not None:
                tile = np.array(tile_pixels(cell.terrain, getattr(cell, "shape", SHAPE_FULL)))
            else:
                tile = BACKDROPS[cell.back]
                if cell.piece:
                    tile = over(PIECES[cell.piece][0], tile, "masked")
            pixels[y * H:(y + 1) * H, x * W:(x + 1) * W] = tile
    for x, y in outline:
        block = pixels[y * H:(y + 1) * H, x * W:(x + 1) * W]
        block[0, :] = block[-1, :] = block[:, 0] = block[:, -1] = MAGENTA
    image = Image.fromarray(np.array(RGB, dtype=np.uint8)[pixels])
    return image.resize((image.width * 2 * scale, image.height * scale), Image.NEAREST)


def layout(rows: list[list[tuple[str, Image.Image]]]) -> Image.Image:
    """Rows of labelled panels, each its own size."""
    font = ImageFont.load_default(size=20)
    label_height, gap = 32, 12
    width = max(sum(image.width + gap for _, image in row) for row in rows) + gap
    height = sum(max(image.height for _, image in row) + label_height + gap for row in rows) + gap
    out = Image.new("RGB", (width, height), (40, 40, 48))
    draw = ImageDraw.Draw(out)
    y = gap
    for row in rows:
        x = gap
        for label, image in row:
            draw.text((x, y + 4), label, fill=(230, 230, 230), font=font)
            out.paste(image, (x, y + label_height))
            x += image.width + gap
        y += max(image.height for _, image in row) + label_height + gap
    return out


def whole_trees(x0: int, x1: int) -> tuple[int, int]:
    """Widen columns x0 to x1 (exclusive) so as not to cut a tree."""
    if features.COVER[x0] is not None:
        x0 = features.COVER[x0][0] - 1
    if features.COVER[x1 - 1] is not None:
        x1 = features.COVER[x1 - 1][0] + 2
    return x0, x1


# The forest: the generated surface

def surface_cells(x0: int, x1: int, y0: int, y1: int):
    cells = []
    for y in range(y0, y1):
        row = []
        for x in range(x0, x1):
            material, piece = features.tile_at(x, y)
            cell = Cell(terrain=material, piece=piece, back="sky" if y <= HEIGHTS[x] else "cave")
            if material is not None:
                cell.shape = generate_tile(x, y)[1]     # its generated shape, for drawing
            row.append(cell)
        cells.append(row)
    return cells


def forest_stretches(count: int, width: int) -> list[tuple[int, int, int, int]]:
    """The stretches of the surface `width` columns wide with the most trees."""
    starts = sorted(range(1, WORLD_SIZE - width - 1),
                    key=lambda x0: -sum(x0 <= t < x0 + width for t in features.TRUNKS))
    chosen = []
    for x0 in starts:
        if all(abs(x0 - c) >= width for c in chosen):
            chosen.append(x0)
        if len(chosen) == count:
            break
    stretches = []
    for x0 in chosen:
        top = min(HEIGHTS[x0:x0 + width]) - features.TRUNK_MAX - 5
        stretches.append((x0, x0 + width, top, max(HEIGHTS[x0:x0 + width]) + 3))
    return stretches


def most_pairs() -> tuple[int, int]:
    """The most distinct (piece, backdrop) pairs in any view of the surface
    (VIEW_COLUMNS across, and tall enough for every tree), and where."""
    best, where = 0, 0
    for x0 in range(0, WORLD_SIZE - VIEW_COLUMNS):
        pairs = set()
        for x in range(x0, x0 + VIEW_COLUMNS):
            for y in range(HEIGHTS[x] - features.TRUNK_MAX - 4, HEIGHTS[x] + 1):
                material, piece = features.tile_at(x, y)
                if piece:
                    pairs.add((piece, "sky" if y <= HEIGHTS[x] else "cave"))
        if len(pairs) > best:
            best, where = len(pairs), x0
    return best, where


# Built structures

GROUND = 12


def flat(width: int, height: int = 16):
    cells = [[Cell(back="sky" if y <= GROUND else "cave") for _ in range(width)] for y in range(height)]
    for y in range(GROUND, height):
        for x in range(width):
            cells[y][x].terrain = GRASS if y == GROUND else SOIL if y < GROUND + 3 else STONE
    return cells


def put(cells, x, y, piece):
    cells[y][x].piece, cells[y][x].terrain = piece, None


def dig(cells, x0, y0, x1, y1):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            cells[y][x].terrain = None
            cells[y][x].back = "cave"


def structures():
    """Things built by hand on flat ground: (name, cells, a tile to remove
    for the collapse)."""
    out = []

    cells = flat(16)                    # a hut: a roof eight across between its walls
    for y in range(GROUND - 4, GROUND):
        put(cells, 3, y, "planks")
        put(cells, 12, y, "planks")
    for x in range(3, 13):
        put(cells, x, GROUND - 5, "bricks")
    put(cells, 7, GROUND - 4, "rope")
    put(cells, 7, GROUND - 3, "rope end")
    put(cells, 4, GROUND - 3, "torch")     # on the wall
    out.append(("hut, roof 8 between walls", cells, (12, GROUND - 1)))

    cells = flat(18)                    # a bridge over a gap 9 wide, on a pillar
    dig(cells, 4, GROUND, 12, GROUND + 2)
    for x in range(3, 15):
        put(cells, x, GROUND - 1, "planks")
    for y in range(GROUND, GROUND + 3):
        put(cells, 8, y, "planks")
    put(cells, 2, GROUND - 1, "ladder")
    out.append(("bridge, gap 9, a pillar", cells, (8, GROUND + 2)))

    cells = flat(16)                    # a ledge out from a wall, and a platform
    for y in range(GROUND - 6, GROUND):
        put(cells, 2, y, "bricks")
    for x in range(3, 9):
        put(cells, x, GROUND - 6, "platform")
    for y in range(GROUND - 5, GROUND - 1):
        put(cells, 6, y, "vine")
    put(cells, 6, GROUND - 1, "vine end")
    out.append(("ledge 6 out from a wall", cells, (2, GROUND - 1)))

    cells = flat(16)                    # trees with touching canopies, and leaves out of reach
    for trunk in (3, 6, 11):
        put(cells, trunk, GROUND - 1, "root")
        for y in range(GROUND - 3, GROUND - 1):
            put(cells, trunk, y, "trunk")
        for i, name in enumerate(("left", "over trunk", "right")):
            put(cells, trunk - 1 + i, GROUND - 4, f"canopy {name}")
        for i, name in enumerate(("top left", "top", "top right")):
            put(cells, trunk - 1 + i, GROUND - 5, f"canopy {name}")
    put(cells, 13, GROUND - 4, "canopy right")      # beyond the canopy's edge
    out.append(("trees touching, a leaf too far", cells, (6, GROUND - 2)))
    return out


def copy(cells):
    out = []
    for row in cells:
        out.append([])
        for c in row:
            cell = Cell(terrain=c.terrain, piece=c.piece, back=c.back, front=c.front)
            if hasattr(c, "shape"):
                cell.shape = c.shape
            out[-1].append(cell)
    return out


def remove(cells, at):
    x, y = at
    cells[y][x].piece = None
    if cells[y][x].terrain is not None:
        cells[y][x].terrain = None
        cells[y][x].back = "cave"


def main() -> None:
    output_dirpath = Path(sys.argv[1] if len(sys.argv) > 1 else "build/features")
    output_dirpath.mkdir(parents=True, exist_ok=True)

    stretches = forest_stretches(3, 40)
    sheet([(f"columns {x0}-{x1 - 1}", draw(surface_cells(x0, x1, y0, y1), scale=1))
           for x0, x1, y0, y1 in stretches], 1).save(output_dirpath / "forest.png")

    rows = []
    for name, cells, _ in structures():
        row = []
        for span in SPANS:
            built = copy(cells)
            row.append((f"{name}, span {span}", draw(built, support.unheld(built, span))))
            support.collapse(built, span, (0, 0), 10 ** 6)
            row.append(("after", draw(built)))
        rows.append(row)
    layout(rows).save(output_dirpath / "support.png")

    # A tree with a neighbour whose canopy touches it, framed on whole trees
    tree_x = next(x for x in features.TRUNKS if x + features.TREE_SPACING in features.TRUNKS)
    x0 = tree_x - 1 - (features.TREE_SPACING if tree_x - features.TREE_SPACING in features.TRUNKS else 0) - 2
    x1 = tree_x + features.TREE_SPACING + 2 + 2
    x0, x1 = whole_trees(x0, x1)
    y0, y1 = min(HEIGHTS[x0:x1]) - features.TRUNK_MAX - 5, max(HEIGHTS[x0:x1]) + 3
    felled = surface_cells(x0, x1, y0, y1)
    scenes = [("a tree felled at its trunk", felled, (tree_x - x0, HEIGHTS[tree_x] - 2 - y0), 3)]
    for name, cells, at in structures():
        if name.startswith(("bridge", "hut", "trees")):
            scenes.append((name + ", undermined", copy(cells), at, 3))
    strips, gif_frames, lines = [], [], []
    for name, cells, at, span in scenes:
        remove(cells, at)
        frames = [draw(cells, support.unheld(cells, span), scale=1)]
        fell = support.collapse(copy(cells), span, at, PER_FRAME)
        replay = copy(cells)
        for falling in fell:
            for x, y in falling:
                replay[y][x].piece = None
            frames.append(draw(replay, support.unheld(replay, span), scale=1))
        lines.append(f"  {name}: {sum(map(len, fell))} pieces fall over {len(fell)} frames ({PER_FRAME} a frame)")
        strips.append([(f"{name}, frame by frame:", Image.new("RGB", (1, 1)))])
        strips.append([(str(i), f) for i, f in enumerate(frames)])
        gif_frames += frames + [frames[-1]] * 4
    layout(strips).save(output_dirpath / "collapse.png")
    size = (max(f.width for f in gif_frames), max(f.height for f in gif_frames))
    canvas = [Image.new("RGB", size) for _ in gif_frames]
    for c, f in zip(canvas, gif_frames):
        c.paste(f, (0, 0))
    canvas[0].save(output_dirpath / "collapse.gif", save_all=True, append_images=canvas[1:], duration=200, loop=0)

    pairs, where = most_pairs()
    print(f"{len(features.TRUNKS)} trees on the surface")
    print(f"most piece and backdrop pairs in a view {VIEW_COLUMNS} across: {pairs} (at column {where}; slots: 56)")
    print("a tile's tree look-up: COVER[x] (offset and height), HEIGHTS[trunk], compares")
    print("collapses:")
    print("\n".join(lines))
    print(f"Wrote {output_dirpath}")


if __name__ == "__main__":
    main()
