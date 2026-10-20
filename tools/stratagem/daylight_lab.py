"""The daylight lab: daylight down dug shafts, against the stand-in.

    uv run strat-daylight-lab [OUTPUT_DIRPATH]

Draws the lighting lab's mine scene (a shaft into a cave, tunnels, shallow
natural caves under the hills), untouched and dug, lit by daylight alone,
each way: as before (`lighting.fixed_light`: a level less per tile below the
original surface, open or not); spreading down shafts (`lighting.sunlight`),
with the glow (the stand-in, dimmed, so that shallow caves can be made out);
and by columns (`lighting.shaft_sun`), losing 3 or 2 a column, reaching 4
columns or 2, untapered or (as the game does) tapered: a level less for
each 4 tiles below the surface, so that it dims slowly down a shaft. The
dug scene has a hut of soil on the hill to the right, roofed: light by
columns stops at walls, so the hut is dark inside. Then screen-sized views
of each with the torches and the miner's light. Writes daylight.png and
views.png.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from stratagem import lighting
from stratagem.tiles import SHAPE_FULL, SOIL
from stratagem.world import HEIGHTS, World
from stratagem.lighting_lab import Scene, _clear, mine_scene, open_up, picture, player_light, sheet, torches_spread

def build_hut(world: World, left: int = 84, right: int = 88, floor: int = 39, roof: int = 35) -> None:
    """A hut of soil blocks: walls at `left` and `right`, a roof, and its
    floor levelled."""
    for x in range(left, right + 1):
        for y in range(roof, floor + 1):
            if y in (roof, floor) or x in (left, right):
                world.set_tile(x, y, (SOIL, SHAPE_FULL))
            else:
                open_up(world, x, y)


def as_now(scene, clear):
    rows, columns = clear.shape
    return np.array([[lighting.fixed_light(scene.left + i, j) for i in range(columns)] for j in range(rows)])


def glow(scene, clear):
    rows, columns = clear.shape
    return np.array([[lighting.glow(scene.left + i, j) for i in range(columns)] for j in range(rows)])


def surface(scene, clear):
    return [HEIGHTS[scene.left + i] for i in range(clear.shape[1])]


METHODS = [
    ("as now", as_now),
    ("down shafts, with a glow", lambda scene, clear: np.maximum(lighting.sunlight(clear), glow(scene, clear))),
    ("by columns, step 3 (untapered)", lambda scene, clear: np.maximum(lighting.shaft_sunlight(clear),
                                                                       glow(scene, clear))),
    ("by columns, step 2 (untapered)", lambda scene, clear: np.maximum(lighting.shaft_sunlight(clear, 2),
                                                                       glow(scene, clear))),
    ("by columns, reach 2, tapered",
     lambda scene, clear: np.maximum(lighting.shaft_sunlight(clear, reach=2, surface=surface(scene, clear)),
                                     glow(scene, clear))),
    ("by columns, as the game: tapered",
     lambda scene, clear: np.maximum(lighting.shaft_sunlight(clear, surface=surface(scene, clear)),
                                     glow(scene, clear))),
]


def main() -> None:
    output_dirpath = Path(sys.argv[1] if len(sys.argv) > 1 else "build/lighting")
    output_dirpath.mkdir(parents=True, exist_ok=True)
    dug = mine_scene()
    build_hut(dug.world)
    untouched = Scene(World(), dug.x0, dug.y0, dug.width, dug.height, player=dug.player)
    scenes = [("untouched", untouched), ("dug", dug)]

    panels, views = [], []
    for scene_name, scene in scenes:
        tiles = scene.region_tiles()
        clear = _clear(tiles)
        for label, method in METHODS:
            light = method(scene, clear)
            panels.append((f"{scene_name}: {label}", picture(scene, tiles, light, backdrop=True, scale=1)))
            if scene_name == "dug":
                lit = np.maximum.reduce([light, torches_spread(scene, clear), player_light(scene, clear)])
                for window in ((scene.x0, 40, 16, 16), (scene.x0 + 4, 50, 16, 16), (scene.x0 + 20, 30, 16, 16)):
                    views.append((label, picture(scene, tiles, lit, backdrop=True, window=window, scale=2)))
    sheet(panels, len(METHODS)).save(output_dirpath / "daylight.png")
    sheet(views, 3).save(output_dirpath / "views.png")
    print(f"Wrote {output_dirpath}")


if __name__ == "__main__":
    main()
