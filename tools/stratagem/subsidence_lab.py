"""The subsidence lab: soil held from below only, failing slowly and by
chance (stratagem.subsidence), on scenes dug into the real world.

    uv run strat-subsidence-lab [OUTPUT_DIRPATH]

Scenes, each run until nothing is at risk (or for TIMEOUT_SECONDS):

- a tunnel through the soil, under the grass;
- a room five wide and a pocket one wide, at the soil's base;
- a tunnel under a tree;
- a tunnel in the rock, just under the soil;
- a shaft, down through the soil into the rock;
- soil put down: a column on the ground, and a bridge across a shaft.

Each under the rules tried: all soil loose, or only soil put down (natural
soil anchored, as terrain is today); and two chances of failing. Writes
subsidence.png (each scene over time, a row per rule) and prints how long
each took to settle, how much fell, and the most at risk at once.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

from stratagem.lighting_lab import RGB, sheet
from stratagem.subsidence import ALL_SOIL, PLACED_SOIL, Rules, Subsidence
from stratagem.tiles import STONE, tile_pixels
from stratagem.world import HEIGHTS, World

FRAMES_PER_SECOND = 50
SNAPSHOT_SECONDS = (0, 5, 20, 60, 180)
TIMEOUT_SECONDS = 600
X0 = 60                                 # the stretch the scenes are dug in


def soil_rows(world: World, x: int) -> tuple[int, int]:
    """The grass's row, and the first row of rock under it."""
    h = HEIGHTS[x]
    y = h + 1
    while world.tile_at(x, y)[0] != STONE:
        y += 1
    return h, y


def tunnel_in_soil(model: Subsidence) -> tuple[int, int]:
    for x in range(X0 + 4, X0 + 16):
        h, _ = soil_rows(model.world, x)
        model.dig(x, h + 3)
        model.dig(x, h + 2)
    return X0, HEIGHTS[X0] - 6


def room_and_pocket(model: Subsidence) -> tuple[int, int]:
    """At the soil's base, just above the rock: a room five wide, and a
    pocket one wide (its roof wedged between solid sides)."""
    for x in [*range(102, 107), 109]:
        _, rock = soil_rows(model.world, x)
        model.dig(x, rock - 1)
        model.dig(x, rock - 2)
    return 94, HEIGHTS[106] - 8


def under_a_tree(model: Subsidence) -> tuple[int, int]:
    for x in range(77, 84):
        h, _ = soil_rows(model.world, x)
        model.dig(x, h + 4)
        model.dig(x, h + 3)
    return 70, HEIGHTS[80] - 10


def tunnel_in_rock(model: Subsidence) -> tuple[int, int]:
    for x in range(X0 + 4, X0 + 16):
        _, rock = soil_rows(model.world, x)
        model.dig(x, rock + 2)
        model.dig(x, rock + 1)
    return X0, HEIGHTS[X0] - 6


def shaft(model: Subsidence) -> tuple[int, int]:
    for x in (X0 + 9, X0 + 10):
        h, rock = soil_rows(model.world, x)
        for y in range(h, rock + 4):
            model.dig(x, y)
    return X0, HEIGHTS[X0] - 6


def put_down(model: Subsidence) -> tuple[int, int]:
    """On treeless ground: a column of soil put down, and a bridge put out
    across a shaft from its rim."""
    x = 71
    for y in range(HEIGHTS[x] - 4, HEIGHTS[x]):
        model.place(x, y)
    for column in (74, 75, 76):
        top, rock = soil_rows(model.world, column)
        for y in range(top, rock + 3):
            model.dig(column, y)
    rim = HEIGHTS[73]
    for column in range(73, 77):
        if model.open(column, rim - 1):
            model.place(column, rim - 1)
    return 64, HEIGHTS[71] - 10


SCENES = [("a tunnel through the soil", tunnel_in_soil),
          ("a room and a pocket at the soil's base", room_and_pocket),
          ("a tunnel under a tree", under_a_tree),
          ("a tunnel in the rock, under the soil", tunnel_in_rock),
          ("a shaft through the soil", shaft),
          ("soil put down: a column, a bridge", put_down)]
RULES = [("all soil loose, 1/64", Rules(ALL_SOIL, slump=0)),
         ("all soil loose, 1/256", Rules(ALL_SOIL, chance=1 / 256, slump=0)),
         ("only soil put down, 1/64", Rules(PLACED_SOIL, slump=0)),
         ("all soil, 1/64, slumping 1/512: the game's", Rules(ALL_SOIL))]
WINDOW = (24, 18)


def picture(world: World, left: int, top: int) -> Image.Image:
    width, height = WINDOW
    pixels = np.block([[np.array(tile_pixels(*world.tile_at(left + i, top + j))) for i in range(width)]
                       for j in range(height)])
    image = Image.fromarray(np.array(RGB, dtype=np.uint8)[pixels])
    return image.resize((image.width * 2, image.height), Image.NEAREST)


def run(scene, rules: Rules):
    model = Subsidence(World(), rules, trees=True)
    left, top = scene(model)
    shots, most, busiest = [], 0, 0
    snapshots = [s * FRAMES_PER_SECOND for s in SNAPSHOT_SECONDS]
    settled = None
    while model.frame <= TIMEOUT_SECONDS * FRAMES_PER_SECOND:
        if model.frame in snapshots:
            shots.append((model.frame, picture(model.world, left, top)))
        if not model.queue and settled is None:
            settled = model.frame
            if model.frame >= snapshots[-1]:
                break
        most = max(most, len(model.queue))
        busiest = max(busiest, int(model.step() is not None))
    return shots, settled, model.gone, most, busiest


def main() -> None:
    output_dirpath = Path(sys.argv[1] if len(sys.argv) > 1 else "build/features")
    output_dirpath.mkdir(parents=True, exist_ok=True)
    panels = []
    for name, scene in SCENES:
        for rule_name, rules in RULES:
            shots, settled, gone, most, busiest = run(scene, rules)
            when = f"{settled / FRAMES_PER_SECOND:.0f}s" if settled is not None else f"not in {TIMEOUT_SECONDS}s"
            print(f"{name:38} {rule_name:26} settled {when:>10}, {gone:3} gone, at most {most:3} at risk, "
                  f"{busiest} failed in a frame")
            panels += [(f"{rule_name}, {frame // FRAMES_PER_SECOND}s", image) for frame, image in shots]
    sheet(panels, len(SNAPSHOT_SECONDS)).save(output_dirpath / "subsidence.png")
    print(f"Wrote {output_dirpath / 'subsidence.png'}")


if __name__ == "__main__":
    main()

