"""The glide lab: the miner's light as the miner walks, by tile and by cell.

    uv run strat-glide-lab [OUTPUT_DIRPATH]

Walks the miner through the lighting lab's mine scene, under the real
player physics, and draws each frame lit by daylight (no torches), plus the
miner's light either a tile at a time (`lighting.miner_light`, as the game
does now) or a cell at a time from the miner's exact position
(`lighting.smooth_miner_light`). Writes a strip of frames and an animation
of each, and prints how many cells' light changes each frame: what the host
would have to redraw.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

from stratagem import lighting, player
from stratagem.camera import INPUT_RIGHT, INPUT_UP
from stratagem.lighting_lab import (RGB, TORCH_ART, _clear, art_rows, daylight, draw_sprite, mine_scene,
                                    region_pixels, sheet)
from stratagem.sprites import frame_pixels
from stratagem.tiles import TILE_LINE_HEIGHT, TILE_PIXEL_WIDTH

SCRIPT = [(44, INPUT_RIGHT), (30, INPUT_RIGHT | INPUT_UP), (20, INPUT_RIGHT)]
WINDOW_TILES = (14, 8)          # across, down: the picture around the miner
SCALE = 3


def walk(scene) -> list[player.Player]:
    x, y = scene.player
    hero = player.Player(x=(x * TILE_PIXEL_WIDTH + 1) << 4,
                         y=((y + 1) * TILE_LINE_HEIGHT - player.PLAYER_HEIGHT) << 4)
    frames = []
    for count, inputs in SCRIPT:
        for _ in range(count):
            hero = player.step(hero, inputs, scene.world.tile_at)
            frames.append(hero)
    return frames


def cell_levels(scene, tile_light: np.ndarray, miner: dict[tuple[int, int], int]) -> np.ndarray:
    """Light per cell of the region: the tile light, brightened by the
    miner's light (cells keyed by world cell)."""
    across, down = lighting.TILE_CELLS_ACROSS, lighting.TILE_CELLS_DOWN
    cells = np.repeat(np.repeat(tile_light, down, axis=0), across, axis=1)
    left_cell = scene.left * across
    for (u, v), level in miner.items():
        i, j = u - left_cell, v
        if 0 <= j < cells.shape[0] and 0 <= i < cells.shape[1]:
            cells[j, i] = max(cells[j, i], level)
    return cells


def tile_cells(pool: dict[tuple[int, int], int]) -> dict[tuple[int, int], int]:
    """A tile pool as cells: each tile's level in all its cells."""
    return {(x * lighting.TILE_CELLS_ACROSS + i, y * lighting.TILE_CELLS_DOWN + j): level
            for (x, y), level in pool.items()
            for j in range(lighting.TILE_CELLS_DOWN) for i in range(lighting.TILE_CELLS_ACROSS)}


def mask_classes(scene, cells: np.ndarray) -> np.ndarray:
    """Which mask each cell is drawn with: levels whose coverage differs
    only in Bayer columns outside a cell's two share its mask."""
    parity = (np.arange(cells.shape[1]) + scene.left * lighting.TILE_CELLS_ACROSS) % 2
    cover = np.where(cells >= lighting.FULL, 16, cells)
    thresholds = [np.sort(lighting.BAYER[:, 2 * p:2 * p + 2].ravel()) for p in (0, 1)]
    return np.where(parity[None, :] == 0,
                    np.searchsorted(thresholds[0], cover, side="left"),
                    np.searchsorted(thresholds[1], cover, side="left"))


def changed_pixels_cells(scene, pixels: np.ndarray, before: np.ndarray, after: np.ndarray) -> int:
    """How many cells look different lit by `after` rather than `before`."""
    def lit(cells):
        levels = np.repeat(np.repeat(cells, lighting.CELL_LINES, axis=0), lighting.CELL_PIXELS, axis=1)
        return lighting.lit_pixels(pixels, levels, scene.left * TILE_PIXEL_WIDTH, 0)
    differ = lit(before) != lit(after)
    rows, columns = before.shape
    return int(np.count_nonzero(differ.reshape(rows, lighting.CELL_LINES, columns, lighting.CELL_PIXELS)
                                .any(axis=(1, 3))))


def frame_image(scene, pixels: np.ndarray, cells: np.ndarray, hero: player.Player) -> Image.Image:
    levels = np.repeat(np.repeat(cells, lighting.CELL_LINES, axis=0), lighting.CELL_PIXELS, axis=1)
    lit = lighting.lit_pixels(pixels, levels, scene.left * TILE_PIXEL_WIDTH, 0)
    for x, y in scene.torches:
        rx, ry = scene.in_region(x, y)
        draw_sprite(lit, art_rows(TORCH_ART), rx * TILE_PIXEL_WIDTH + 2, ry * TILE_LINE_HEIGHT + 6)
    left = hero.px - scene.left * TILE_PIXEL_WIDTH
    draw_sprite(lit, frame_pixels("stand", hero.facing < 0), left, hero.py)
    across, down = WINDOW_TILES[0] * TILE_PIXEL_WIDTH, WINDOW_TILES[1] * TILE_LINE_HEIGHT
    # Centred on the miner, scrolled a cell at a time, as the camera does.
    cx = (left + player.PLAYER_WIDTH // 2 - across // 2) & ~1
    cy = (hero.py + player.PLAYER_HEIGHT // 2 - down // 2) & ~7
    crop = lit[cy:cy + down, cx:cx + across]
    image = Image.fromarray(np.array(RGB, dtype=np.uint8)[crop])
    return image.resize((image.width * 2 * SCALE, image.height * SCALE), Image.NEAREST)


def main() -> None:
    output_dirpath = Path(sys.argv[1] if len(sys.argv) > 1 else "build/lighting")
    output_dirpath.mkdir(parents=True, exist_ok=True)
    scene = mine_scene()
    tiles = scene.region_tiles()
    clear = _clear(tiles)
    scene.torches = []          # the miner's light alone, underground
    base = daylight(scene, clear)
    pixels = region_pixels(tiles, backdrop=True)

    def clear_at(x, y):
        return lighting.transparent(scene.world.tile_at(x, y))

    heroes = walk(scene)
    for name, light_for in [
        ("tile", lambda hero: tile_cells(lighting.miner_light(clear_at, *lighting.miner_tile(hero.px, hero.py)))),
        ("cell", lambda hero: lighting.smooth_miner_light(clear_at, hero.px, hero.py)),
    ]:
        rows, columns = base.shape[0] * lighting.TILE_CELLS_DOWN, base.shape[1] * lighting.TILE_CELLS_ACROSS
        blank = ~(pixels != 0).reshape(rows, lighting.CELL_LINES, columns, lighting.CELL_PIXELS).any(axis=(1, 3))
        images, changes, mask_changes, pixel_changes, previous = [], [], [], [], None
        visible_changes = []
        for hero in heroes:
            cells = cell_levels(scene, base, light_for(hero))
            if previous is not None:
                changes.append(int(np.count_nonzero(cells != previous)))
                mask_changes.append(int(np.count_nonzero(mask_classes(scene, cells) !=
                                                         mask_classes(scene, previous))))
                pixel_changes.append(changed_pixels_cells(scene, pixels, previous, cells))
                visible_changes.append(int(np.count_nonzero((mask_classes(scene, cells) !=
                                                             mask_classes(scene, previous)) & ~blank)))
            previous = cells
            images.append(frame_image(scene, pixels, cells, hero))
        images[0].save(output_dirpath / f"glide-{name}.gif", save_all=True, append_images=images[1:],
                       duration=40, loop=0)
        strip = [(f"frame {n}", images[n]) for n in range(4, 13)]
        sheet(strip, 3).save(output_dirpath / f"glide-{name}.png")
        print(f"{name}: cells changed per frame (mean, max):")
        for what, counts in (("level", changes), ("mask", mask_changes), ("mask, not blank", visible_changes),
                              ("pixels", pixel_changes)):
            moving = [c for c in counts if c]
            print(f"  {what:15} {np.mean(counts):6.1f} {max(counts):4}   "
                  f"{len(moving)} of {len(counts)} frames, mean {np.mean(moving):.1f} when any")
    print(f"Wrote {output_dirpath}")


if __name__ == "__main__":
    main()
