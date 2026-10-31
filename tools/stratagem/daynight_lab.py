"""The day and night lab: the world's light through the day, and the sky.

    uv run strat-daynight-lab [OUTPUT_DIRPATH]

The sun's level through the day is a table by the time, the world clock's
high byte (256ths of a day, midnight at 0, noon at 128): broad daylight
around noon, a dark night around midnight, and sigmoid ramps for dawn and
dusk. Daylight (the game's: by columns, tapered, with the glow) is dimmed
by subtraction, FULL less the sun's level, then brightened by the torches
and the miner's light as now. All of it is drawn with the light's dither.

The sky is one or two logical colours of its own (the palette sets them),
lit at the sun's level, and drawn in one of four ways:

- blue: blue, dithered at the sun's level.
- palette: one colour, changed through dawn and dusk.
- horizon: as palette, brighter near the hills at dawn and dusk.
- two-tone: as horizon, with a warm colour low and the sky's colour high,
  dithered into each other.
- game: two-tone as the game could draw it, a tile at a time, the warm
  pixels fixed in the sky's graphics, shown by the palette.
- soft: blue high and a warm colour low, the warm never more than
  WARM_MOST of the lit pixels, and a smaller boost: magenta alone; yellow
  and magenta; magenta and red.

Writes curve.png (the sun's level through the day), day.png (the scene at
a series of times, the first four ways) soft.png (the soft ways), and twilight.png (the two-tone ways, into the
night).
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from stratagem import lighting
from stratagem.daylight_lab import glow, surface
from stratagem.lighting import BAYER, FULL
from stratagem.lighting_lab import (RGB, TORCH_ART, _clear, _solid_pixels, art_rows, draw_sprite, mine_scene,
                                    player_light, region_pixels, sheet, tile_levels, torches_spread)
from stratagem.sprites import frame_pixels
from stratagem.tiles import (BACKGROUND_SKY, BLACK, BLUE, MAGENTA, RED, SKY, TILE_LINE_HEIGHT, TILE_PIXEL_WIDTH,
                             YELLOW)

TIMES = 256                     # a day, in the clock's high byte
NOON = TIMES // 2
HOUR = TIMES / 24


@dataclass(frozen=True)
class Curve:
    """The sun's level by the time, symmetric about noon: FULL through the
    day; a quick sigmoid ramp at dawn and dusk (hours) down to the
    twilight's levels; then a slow one, the twilight, on the night's side,
    down to black around midnight. Light leaks over the horizon into the
    night; the dark doesn't leak into the day."""
    dawn: float = 6             # hours: the quick ramp's middle
    width: float = 0.4          # hours: from a quarter of the way up to three quarters, about 2.2 widths
    twilight: float = 2.5       # levels: the slow ramp's height (2, 1, then 0, rounded)
    twilight_middle: float = 3.25
    twilight_width: float = 0.6

    def level(self, time: int) -> int:
        hours = min(time, TIMES - time) / HOUR      # symmetric about noon: the morning's hour
        quick = 1 / (1 + math.exp(-(hours - self.dawn) / self.width))
        slow = 1 / (1 + math.exp(-(hours - self.twilight_middle) / self.twilight_width))
        return min(FULL, round((FULL - self.twilight) * quick + self.twilight * slow))

    def table(self) -> list[int]:
        return [self.level(t) for t in range(TIMES)]


def warmth(time: int, curve: Curve) -> float:
    """How far into dawn or dusk: 1 in the ramp's middle, falling away either side."""
    hours = min(time, TIMES - time) / HOUR
    return math.exp(-((hours - curve.dawn) / (2.5 * curve.width)) ** 2)


# Pseudo logical colours for the sky: its colour, and the warm colour low.
SKY_HIGH, SKY_LOW = 8, 9


# The soft two-tone ways: the sky blue above, the warm colour low, never
# denser than WARM_MOST of the sky's lit pixels, no brighter than the sun
# allows, by the warmth: each way's warm colours, from the ramp's edges to
# its middle (dawn's, then dusk's).
WARM_MOST = 0.6
SOFT_WAYS = {
    "soft magenta": ((MAGENTA, MAGENTA), (MAGENTA, MAGENTA)),
    "soft yellow, magenta": ((MAGENTA, YELLOW), (YELLOW, MAGENTA)),
    "soft magenta, red": ((MAGENTA, RED), (MAGENTA, RED)),
}

# As the game could draw it: the sky's light and its warm pixels a tile at
# a time, by the tile's height above its column's surface; the warm pixels
# fixed in the sky's graphics (GAME_BANDS of them, densest at the hills),
# shown by the palette alone: the warm colour blue, or magenta from
# GAME_WARM_FROM warmth.
GAME_BANDS = 4
GAME_WARM_FROM = 0.3


def sky_colours(time: int, curve: Curve, way: str) -> tuple[int, int]:
    """The physical colours of the sky's two logical colours at a time."""
    if way == "blue":
        return BLUE, BLUE
    w = warmth(time, curve)
    dusk = time > NOON
    if way in SOFT_WAYS:
        edge, middle = SOFT_WAYS[way][dusk]
        return BLUE, (middle if w > 0.6 else edge)
    if way == "game":
        return BLUE, (MAGENTA if w >= GAME_WARM_FROM else BLUE)
    if w < 0.25:
        return BLUE, BLUE
    if way == "two-tone":
        low = (RED if w > 0.7 else MAGENTA) if dusk else (YELLOW if w > 0.7 else RED)
        return (MAGENTA if w > 0.7 and dusk else BLUE), low
    one = (RED if w > 0.7 else MAGENTA) if dusk else (YELLOW if w > 0.7 else MAGENTA)
    return one, one


HORIZON_TILES = 6               # how high above the hills the warmth reaches
HORIZON_BOOST = 6               # levels brighter at the hills, at the ramp's middle


def picture(scene, tiles, light, sun: int, time: int, curve: Curve, way: str,
            window: tuple[int, int, int, int], scale: int = 1) -> Image.Image:
    pixels = region_pixels(tiles)
    levels = tile_levels(light, smooth=False)
    # The sky's pixels: sky tiles, and the open parts of tiles in front of it.
    sky = np.block([[np.full((TILE_LINE_HEIGHT, TILE_PIXEL_WIDTH), tile[0] == SKY)
                     | ((tile[1] & BACKGROUND_SKY != 0) & (_solid_pixels(tile) == 0)) for tile in row]
                    for row in tiles])
    height_px, width_px = pixels.shape
    heights = surface(scene, np.zeros((1, width_px // TILE_PIXEL_WIDTH)))
    ys, xs = np.indices(pixels.shape)
    above = np.array(heights)[xs // TILE_PIXEL_WIDTH] * TILE_LINE_HEIGHT - ys     # lines above the hills
    near = np.clip(1 - above / (HORIZON_TILES * TILE_LINE_HEIGHT), 0, 1)
    w = warmth(time, curve)
    sky_level = np.full(pixels.shape, sun, dtype=float)
    if way in ("horizon", "two-tone"):
        sky_level = sky_level + HORIZON_BOOST * w * near
    thresholds = BAYER[ys % 4, xs % 4]
    if way == "game":
        band = np.clip(GAME_BANDS - (above - 1) // TILE_LINE_HEIGHT, 0, GAME_BANDS) / GAME_BANDS  # by tile
        sky_level = sky_level + np.rint(HORIZON_BOOST / 2 * w * band)
        warm = thresholds < np.rint(band * 16 * WARM_MOST)
    elif way in SOFT_WAYS:
        sky_level = sky_level + HORIZON_BOOST / 2 * w * near
        warm = thresholds < np.rint(near * 16 * WARM_MOST * w)
    else:
        warm = (way == "two-tone") & (thresholds < np.rint(near * 16 * min(1, 2 * w)))
    sky_colour = np.where(warm, SKY_LOW, SKY_HIGH)
    pixels = np.where(sky, sky_colour, pixels)
    levels = np.where(sky, np.minimum(FULL, np.rint(sky_level)).astype(int), levels)
    lit = lighting.lit_pixels(pixels, levels, scene.left * TILE_PIXEL_WIDTH, 0)
    for x, y in scene.torches:
        rx, ry = scene.in_region(x, y)
        draw_sprite(lit, art_rows(TORCH_ART), rx * TILE_PIXEL_WIDTH + 2, ry * TILE_LINE_HEIGHT + 6)
    px, py = scene.in_region(*scene.player)
    miner = frame_pixels("stand", False)
    draw_sprite(lit, miner, px * TILE_PIXEL_WIDTH + 1, (py + 1) * TILE_LINE_HEIGHT - len(miner))
    wx, wy, ww, wh = window
    rx, ry = scene.in_region(wx, wy)
    crop = lit[ry * TILE_LINE_HEIGHT:(ry + wh) * TILE_LINE_HEIGHT, rx * TILE_PIXEL_WIDTH:(rx + ww) * TILE_PIXEL_WIDTH]
    high, low = sky_colours(time, curve, way)
    palette = np.array(RGB + [RGB[high], RGB[low]], dtype=np.uint8)
    image = Image.fromarray(palette[crop])
    return image.resize((image.width * 2 * scale, image.height * scale), Image.NEAREST)


def curve_picture(curve: Curve, marks: list[int]) -> Image.Image:
    width, height, pad = 768, 260, 30
    image = Image.new("RGB", (width + 2 * pad, height + 2 * pad), (40, 40, 48))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=14)
    x_of = lambda t: pad + t * width / TIMES
    y_of = lambda level: pad + height - level * height / FULL
    for hour in range(0, 25, 3):
        x = x_of(hour * HOUR)
        draw.line([(x, pad), (x, pad + height)], fill=(70, 70, 80))
        draw.text((x - 8, pad + height + 6), f"{hour:02}", fill=(200, 200, 200), font=font)
    for level in (0, 5, 10, 15):
        draw.text((4, y_of(level) - 7), str(level), fill=(200, 200, 200), font=font)
    table = curve.table()
    draw.line([(x_of(t), y_of(table[t])) for t in range(TIMES)], fill=(255, 220, 80), width=2)
    for t in marks:
        draw.ellipse([x_of(t) - 4, y_of(table[t]) - 4, x_of(t) + 4, y_of(table[t]) + 4], outline=(120, 200, 255))
    return image


def main() -> None:
    output_dirpath = Path(sys.argv[1] if len(sys.argv) > 1 else "build/lighting")
    output_dirpath.mkdir(parents=True, exist_ok=True)
    curve = Curve()
    scene = mine_scene()
    tiles = scene.region_tiles()
    clear = _clear(tiles)
    daylight = np.maximum(lighting.shaft_sunlight(clear, surface=surface(scene, clear)), glow(scene, clear))
    others = np.maximum(torches_spread(scene, clear), player_light(scene, clear))
    times = [round(h * HOUR) for h in (12, 17, 17.5, 17.75, 18, 18.25, 18.5, 19, 20, 21, 22, 0)]
    curve_picture(curve, times).save(output_dirpath / "curve.png")
    window = (scene.x0 - 2, 34, 24, 26)
    for name, ways in (("day.png", ["blue", "palette", "horizon", "two-tone"]), ("soft.png", ["blue", *SOFT_WAYS]),
                       ("twilight.png", ["two-tone", "soft magenta", "game"])):
        sheet(panels_for(scene, tiles, daylight, others, curve, times, window, ways), len(times)).save(
            output_dirpath / name)
    print(f"Wrote {output_dirpath}: curve.png, day.png, soft.png, twilight.png; the table: {curve.table()}")


def panels_for(scene, tiles, daylight, others, curve, times, window, ways):
    panels = []
    for way in ways:
        for t in times:
            sun = curve.table()[t]
            light = np.maximum(np.maximum(daylight - (FULL - sun), 0), others)
            label = f"{way}, {t / HOUR:05.2f}h, sun {sun}"
            panels.append((label, picture(scene, tiles, light, sun, t, curve, way, window)))
    return panels


if __name__ == "__main__":
    main()
