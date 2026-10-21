"""The store of changed chunks on the parasite (asm/world.asm): a cache of
the chunks near the view, fetched from the host's store ahead of need. The
game runs in py65 with the host's part played by FakeHost."""

from stratagem.world import CHUNK_SIZE, generate_tile
from test_daylight import KEYS, ParasiteGame

TILE_CACHE_SIZE = 32
# Along the surface and back, then down a shaft and along a tunnel
STORE_SCRIPT = [(300, "Z"), (600, "X"), (200, "ML"), (120, "XL")]


def test_the_cache_fetches_chunks_ahead_of_need(game_build):
    """With far more changed chunks around than the cache holds, every
    chunk a tile is asked of is there already, fetched by the packets as
    the view nears it; and every cached chunk is the host's."""
    game = ParasiteGame(game_build)
    labels, memory = game.labels, game.memory
    # Change every chunk within 5 of the miner's (121, three times the
    # cache), each by setting a tile to what it is, so the world plays the same.
    cx, cy = game.byte("cached_left") // CHUNK_SIZE + 2, game.byte("cached_top") // CHUNK_SIZE + 2
    for chunk_y in range(max(0, cy - 5), cy + 6):
        for chunk_x in range(cx - 5, cx + 6):
            x, y = chunk_x * CHUNK_SIZE, chunk_y * CHUNK_SIZE
            material, shape = generate_tile(x, y)
            memory[labels["zp_world_new_shape"]] = shape
            game.call("set_tile", a=material, x=x, y=y)
            game.host.take_queue()
    assert memory[labels["world_slots_used"]] >= 100
    tiles_checked = 0
    for count, keys in STORE_SCRIPT:
        for _ in range(count):
            game.frame(sum(KEYS[k] for k in keys))
            game.host.check_cache()
            left, right = game.byte("cached_left"), game.byte("cached_right")
            top, bottom = game.byte("cached_top"), game.byte("cached_bottom")
            for y in range(top, bottom + 1):
                for x in range(left, right + 1):
                    index = (y % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + x % TILE_CACHE_SIZE
                    held = memory[labels["tile_cache"] + index], memory[labels["tile_cache_shapes"] + index]
                    assert held == game.tile_at(x, y), f"tile ({x}, {y}) in the tile cache"
                    tiles_checked += 1
    assert game.host.prefetched >= 10, "too few chunks fetched ahead to test"
    assert game.host.fetched == 0, f"{game.host.fetched} chunks were needed before they were fetched"
    print(f"\n{game.host.prefetched} chunks fetched ahead; {tiles_checked} tiles checked")
