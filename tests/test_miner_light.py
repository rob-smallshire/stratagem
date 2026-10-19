"""The 6502 miner's light matches the model: in random ground, over a run of
moves, the light plane holds the brighter of daylight and the miner's pool,
and exactly the tiles whose light changed are queued for redrawing."""

import random

import pytest

from mos6502 import Machine6502
from stratagem import lighting
from stratagem.build import read_disc_file
from stratagem.tiles import AIR, GRASS, SHAPE_FULL, SKY, SOIL, STONE
from stratagem.world import HEIGHTS, RAMP_BOTTOM_LEFT, RAMP_TOP_LEFT, RAMP_TOP_RIGHT

TILE_CACHE_SIZE = 32       # asm/layout.asm
VIEW_TILES_ACROSS = 17     # the tile cache holds the view's tiles, at most
VIEW_TILES_DOWN = 16


@pytest.fixture
def machine(game_build):
    machine = Machine6502()
    for name in ("STRAT", "MAIN", "WORLD"):
        machine.load(*read_disc_file(game_build.disc_filepath, name))
    return machine


def random_tile(rng: random.Random) -> tuple[int, int]:
    roll = rng.random()
    if roll < 0.45:
        return AIR, SHAPE_FULL
    if roll < 0.55:
        return SKY, SHAPE_FULL
    return rng.choice([GRASS, SOIL, STONE]), rng.choice([SHAPE_FULL] * 4 + [RAMP_TOP_LEFT, RAMP_TOP_RIGHT,
                                                                           RAMP_BOTTOM_LEFT])


@pytest.mark.parametrize("seed", range(6))
def test_miner_light_matches_model(machine, game_build, seed):
    labels = game_build.labels["STRATAGEM"]
    memory = machine.mpu.memory
    rng = random.Random(seed)
    # A view's worth of random tiles in the cache, near the surface so
    # that daylight varies across it.
    left = rng.randrange(8, 200)
    top = max(HEIGHTS[left] - 6, 0)
    right, bottom = left + VIEW_TILES_ACROSS - 1, top + VIEW_TILES_DOWN - 1
    tiles = {(x, y): random_tile(rng) for x in range(left, right + 1) for y in range(top, bottom + 1)}
    for name, value in (("cached_left", left), ("cached_right", right), ("cached_top", top),
                        ("cached_bottom", bottom), ("light_valid", 0), ("light_dirty", 0xFF),
                        ("light_queue_count", 0)):
        memory[labels[name]] = value
    light_plane = labels["tile_cache_light"]

    def index(x: int, y: int) -> int:
        return (y % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + x % TILE_CACHE_SIZE

    for (x, y), (material, shape) in tiles.items():
        memory[labels["tile_cache"] + index(x, y)] = material
        memory[labels["tile_cache_shapes"] + index(x, y)] = shape
        memory[light_plane + index(x, y)] = lighting.fixed_light(x, y) * lighting.LIGHT_SCALE

    def clear_at(x: int, y: int) -> bool:
        return lighting.transparent(tiles[(x, y)])

    def inside(x: int, y: int) -> bool:
        return left <= x <= right and top <= y <= bottom

    for move in range(40):
        before = {tile: memory[light_plane + index(*tile)] for tile in tiles}
        # The miner anywhere in the view, sometimes near its edges.
        px = rng.randrange(left * 8 - 3, (right + 1) * 8 - 3)
        py = rng.randrange(top * 16 - 12, (bottom + 1) * 16 - 12)
        for name, value in (("zp_player_x", px << 4), ("zp_player_y", py << 4)):
            memory[labels[name]] = value & 0xFF
            memory[labels[name] + 1] = value >> 8
        if move % 7 == 3:       # sometimes a tile changes, as if dug
            tile = rng.choice(list(tiles))
            tiles[tile] = AIR, SHAPE_FULL
            memory[labels["tile_cache"] + index(*tile)] = AIR
            memory[labels["tile_cache_shapes"] + index(*tile)] = SHAPE_FULL
            memory[labels["light_dirty"]] = 0xFF
        machine.call(labels["update_light"], max_steps=200_000)

        pool = lighting.miner_light(clear_at, *lighting.miner_tile(px, py), inside)
        wrong = [tile for tile in tiles
                 if memory[light_plane + index(*tile)] != lighting.lit_level(*tile, pool) * lighting.LIGHT_SCALE]
        assert wrong[:8] == [], f"move {move}: {len(wrong)} tiles lit wrongly"
        count = memory[labels["light_queue_count"]]
        queued = {(memory[labels["light_queue_x"] + i], memory[labels["light_queue_y"] + i]) for i in range(count)}
        changed = {tile for tile in tiles if memory[light_plane + index(*tile)] != before[tile]}
        assert queued == changed, f"move {move}"
        assert count == len(changed), f"move {move}: a tile queued twice"
        memory[labels["light_queue_count"]] = 0      # as redraw_light_queue leaves it
