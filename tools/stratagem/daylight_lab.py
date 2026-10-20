"""The daylight lab: daylight down dug shafts, against the game's stand-in.

    uv run strat-daylight-lab [OUTPUT_DIRPATH]

Draws the lighting lab's mine scene (a shaft into a cave, tunnels, shallow
natural caves under the hills), untouched and dug, lit by daylight alone,
each way: as now (`lighting.fixed_light`: a level less per tile below the
original surface, open or not), and as proposed (`lighting.sunlight`:
direct light down every open column, pools spreading from it, walls lit at
their faces), plain or with a faint glow from the surface left in, so that
shallow caves can still be made out. Then screen-sized views of each with
the torches and the miner's light. Writes daylight.png and views.png.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from stratagem import lighting
from stratagem.world import World
from stratagem.lighting_lab import Scene, _clear, mine_scene, picture, player_light, sheet, torches_spread

GLOW_LOSS = 4       # the glow: the stand-in, this many levels darker


def as_now(scene, clear):
    rows, columns = clear.shape
    return np.array([[lighting.fixed_light(scene.left + i, j) for i in range(columns)] for j in range(rows)])


def glow(scene, clear):
    return np.maximum(0, as_now(scene, clear) - GLOW_LOSS)


METHODS = [
    ("as now", as_now),
    ("down shafts", lambda scene, clear: lighting.sunlight(clear)),
    ("down shafts, walls soak less", lambda scene, clear: lighting.sunlight(clear, wall_step=2)),
    ("down shafts, with a glow", lambda scene, clear: np.maximum(lighting.sunlight(clear), glow(scene, clear))),
    ("down shafts, rock as now", lambda scene, clear: np.maximum(lighting.sunlight(clear),
                                                                 np.where(clear, 0, as_now(scene, clear)))),
]


def main() -> None:
    output_dirpath = Path(sys.argv[1] if len(sys.argv) > 1 else "build/lighting")
    output_dirpath.mkdir(parents=True, exist_ok=True)
    dug = mine_scene()
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
                for window in ((scene.x0, 40, 16, 16), (scene.x0 + 4, 50, 16, 16)):
                    views.append((label, picture(scene, tiles, lit, backdrop=True, window=window, scale=2)))
    sheet(panels, len(METHODS)).save(output_dirpath / "daylight.png")
    sheet(views, 2).save(output_dirpath / "views.png")
    print(f"Wrote {output_dirpath}")


if __name__ == "__main__":
    main()
