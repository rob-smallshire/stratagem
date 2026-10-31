"""The world's day and night (docs/tube-game.md), from the clock's time:
the clock's high byte, 256ths of a day, midnight at 0 and noon at 128.

- The sun's level, 0 to FULL: full through the day; a quick sigmoid ramp
  at dawn and dusk down to the twilight's levels; then a slow one on the
  night's side, down to black around midnight. Light leaks over the
  horizon into the night; the dark doesn't leak into the day. Daylight is
  dimmed by subtraction: a tile's daylight less FULL less the sun's level.
- The sky's glow at dawn and dusk: the sky's tiles in the BANDS rows above
  their column's surface are drawn with warm pixels among the blue (the
  tile group's cyan, GLOW, which the host's palette makes blue, or magenta
  while the sky glows), densest at the hills; and lit more brightly than
  the sun's level, by a boost by the time and the band.

    uv run python -m stratagem.daynight     # the table, and the glow's times
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from stratagem.tiles import (BLUE, GLOW, MAGENTA, SKY, SLOT_SHAPES, TILE_COLOUR_BASE, TILE_HEIGHT_LINES,
                             TILE_WIDTH_PIXELS)
from stratagem.world import HEIGHTS

TIMES = 256
NOON = TIMES // 2
HOUR = TIMES / 24
FULL = 15

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]     # as lighting.BAYER


def nearest(value: float) -> int:
    return math.floor(value + 0.5)


@dataclass(frozen=True)
class Curve:
    """The sun's level by the time, symmetric about noon."""
    dawn: float = 6             # hours: the quick ramp's middle
    width: float = 0.4          # hours: from a quarter of the way up to three quarters, about 2.2 widths
    twilight: float = 2.5       # levels: the slow ramp's height (2, 1, then 0)
    twilight_middle: float = 3.25
    twilight_width: float = 0.6

    def morning_hours(self, time: int) -> float:
        return min(time, TIMES - time) / HOUR

    def level(self, time: int) -> int:
        hours = self.morning_hours(time)
        quick = 1 / (1 + math.exp(-(hours - self.dawn) / self.width))
        slow = 1 / (1 + math.exp(-(hours - self.twilight_middle) / self.twilight_width))
        return min(FULL, nearest((FULL - self.twilight) * quick + self.twilight * slow))

    def table(self) -> list[int]:
        return [self.level(t) for t in range(TIMES)]

    def warmth(self, time: int) -> float:
        """How far into dawn or dusk: 1 in the quick ramp's middle."""
        return math.exp(-((self.morning_hours(time) - self.dawn) / (2.5 * self.width)) ** 2)


CURVE = Curve()

# The glow.
BANDS = 4                       # rows above the surface
GLOW_MOST = 0.6                 # of the band at the hills' pixels, warm
BOOST_MOST = 3                  # levels brighter at the hills, in the ramp's middle
GLOW_FROM = 0.3                 # warmth: the warm pixels magenta from here


def band_weight(band: int) -> float:
    """Band 0 at the hills, BANDS - 1 the highest."""
    return (BANDS - band) / BANDS


def warm_pixels(band: int) -> int:
    """Of each 16 pixels of a band (by the Bayer matrix), how many are warm."""
    return nearest(band_weight(band) * 16 * GLOW_MOST)


def band_pixels(band: int) -> list[list[int]]:
    """A sky tile of a band: GLOW among BLUE."""
    return [[GLOW if BAYER[y % 4][x % 4] < warm_pixels(band) else BLUE for x in range(TILE_WIDTH_PIXELS)]
            for y in range(TILE_HEIGHT_LINES)]


def band_of(x: int, y: int) -> int | None:
    """The glow's band of a tile of sky at (x, y): rows 0 and 1 above its
    column's surface (or the surface row, dug) are band 0; None above the
    bands."""
    above = HEIGHTS[x] - y
    if above < 0:
        return None
    band = max(0, above - 1)
    return band if band < BANDS else None


def drawn(x: int, y: int, tile: tuple[int, int]) -> tuple[int, int]:
    """A tile as the host has it: sky in a band, as the band's graphics
    (sky's cave page, by a slot's pseudo-shape)."""
    material, shape = tile
    if material != SKY:
        return tile
    band = band_of(x, y)
    return tile if band is None else (SKY, SLOT_SHAPES[band])


def boost(time: int) -> int:
    """The band at the hills' boost, 0 to BOOST_MOST."""
    return nearest(BOOST_MOST * CURVE.warmth(time))


def band_boost(boost_level: int, band: int) -> int:
    return nearest(boost_level * band_weight(band))


def glowing(time: int) -> bool:
    return CURVE.warmth(time) >= GLOW_FROM


def glow_colour(time: int) -> int:
    return MAGENTA if glowing(time) else BLUE


def glow_times() -> list[tuple[int, int]]:
    """The times the sky glows, as [from, until) pairs: dawn's, then dusk's."""
    times, start = [], None
    for t in range(TIMES + 1):
        on = t < TIMES and glowing(t)
        if on and start is None:
            start = t
        elif not on and start is not None:
            times.append((start, t))
            start = None
    return times


def level(daylight: int, time: int, band: int | None = None) -> int:
    """A tile's daylight (0 to FULL, undimmed), at the time: dimmed, and
    for sky in a band, boosted."""
    lit = max(0, daylight - (FULL - CURVE.level(time)))
    if band is not None:
        lit = min(FULL, lit + band_boost(boost(time), band))
    return lit


def table() -> bytes:
    """By the time: the sun's level, and the boost in bits 4-5."""
    return bytes(CURVE.level(t) | boost(t) << 4 for t in range(TIMES))


def tables_source() -> list[str]:
    """daynight.asm's tables: the day's, and the boost by band."""
    (dawn_from, dawn_until), (dusk_from, dusk_until) = glow_times()
    lines = ["\\ Generated by stratagem.daynight: do not edit.",
             f"DAYNIGHT_BANDS = {BANDS}",
             f"GLOW_LOGICAL = {TILE_COLOUR_BASE + GLOW}",
             f"GLOW_BLUE = {BLUE}",
             f"GLOW_MAGENTA = {MAGENTA}",
             f"GLOW_DAWN_FROM = {dawn_from}",
             f"GLOW_DAWN_UNTIL = {dawn_until}",
             f"GLOW_DUSK_FROM = {dusk_from}",
             f"GLOW_DUSK_UNTIL = {dusk_until}",
             f"SKY_BAND_SHAPE_0 = {SLOT_SHAPES[0]}",
             f"SKY_BAND_SHAPE_1 = {SLOT_SHAPES[1]}",
             f"SKY_BAND_SHAPE_2 = {SLOT_SHAPES[2]}",
             f"SKY_BAND_SHAPE_3 = {SLOT_SHAPES[3]}"]
    return lines


def parasite_tables_source() -> list[str]:
    lines = ["\\ Generated by stratagem.daynight: do not edit.",
             "\\ By the time: the sun's level, and the boost (bits 4-5).",
             ".daynight_table"]
    data = table()
    lines += ["    EQUB " + ", ".join(f"&{b:02X}" for b in data[i:i + 16]) for i in range(0, TIMES, 16)]
    lines += ["\\ The boost by band: boost * 4 + band.", ".daynight_band_boosts"]
    lines += ["    EQUB " + ", ".join(str(band_boost(b, band)) for band in range(BANDS)) for b in range(BOOST_MOST + 1)]
    lines += ["\\ The sky's glow band shapes, by band.", ".daynight_band_shapes",
              "    EQUB " + ", ".join(str(SLOT_SHAPES[band]) for band in range(BANDS))]
    return lines


def generate(generated_dirpath) -> None:
    """daynight.asm (constants, for both programs) and daynight_tables.asm
    (the parasite's tables)."""
    (generated_dirpath / "daynight.asm").write_text("\n".join(tables_source()) + "\n")
    (generated_dirpath / "daynight_tables.asm").write_text("\n".join(parasite_tables_source()) + "\n")


def main() -> None:
    changes = [(t, CURVE.level(t)) for t in range(TIMES) if t == 0 or CURVE.level(t) != CURVE.level(t - 1)]
    print("the sun's level from:", ", ".join(f"{t / HOUR:05.2f}h {v}" for t, v in changes))
    print("the glow:", ", ".join(f"{a / HOUR:05.2f}h-{b / HOUR:05.2f}h" for a, b in glow_times()))
    print("boosts:", sorted({boost(t) for t in range(TIMES)}), "warm pixels by band:",
          [warm_pixels(b) for b in range(BANDS)])


if __name__ == "__main__":
    main()

