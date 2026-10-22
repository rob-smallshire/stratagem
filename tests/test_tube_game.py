"""The Tube game (docs/tube-game.md): every frame, the host shows exactly
what the models say it should, given the tiles it holds: each cell lit by
the brighter of its tile's daylight and the parasite's smooth miner's light
(lighting.smooth_miner_light, soft shadows), and the player's sprite."""

import pytest

from conftest import RUN_TIMEOUT_EMULATED_SECONDS
from stratagem import camera, lighting, player, sprites
from stratagem.player import Player
from stratagem.screen import CELL_BYTES, SCREEN_END, SCREEN_START, render_view, wrap
from stratagem.tiles import (BACKGROUND_SKY, FIRST_PIECE, SHAPE_FULL, SLOT_COUNT, TORCH, slot_of,
                             tile_bytes)

TILE_CACHE_SIZE = 32       # asm/layout.asm
FRAMES = sprites.sprite_frames()
# Each digs deep first: near the surface, daylight outshines the miner's light.
DIG_DEEP = [(300, ["M", "L"])]
SCRIPTS = {
    "tunnel-right-and-down": DIG_DEEP + [(80, ["X", "L"]), (60, ["X", "M", "L"]), (30, ["Z"]), (20, ["K"]),
                                         (20, [])],
    "tunnel-left-and-up": DIG_DEEP + [(80, ["Z", "L"]), (60, ["Z", "K", "L"]), (30, ["X"]), (20, [])],
    "drop-torches": DIG_DEEP + [(60, ["X", "L"]), (3, ["T"]), (20, []), (80, ["X", "L"]), (3, ["T"]), (20, []),
                                (60, ["Z"]), (30, ["M", "L"]), (20, [])],
    # The tree beside the start (column 127): its root dug, it falls.
    "fell-a-tree": [(12, ["Z", "L"]), (30, [])],
}


def word(peek, address: int) -> int:
    return peek[address] | peek[address + 1] << 8


def _signed(byte: int) -> int:
    return byte - 256 if byte & 0x80 else byte


def host_tiles(bbc, labels):
    """The tiles the host holds, by world position (wrapping): a slot as the
    piece it was composed from (tiles.py), over its backdrop."""
    size = TILE_CACHE_SIZE ** 2
    peek = bbc.memory.address.peek
    materials = peek[labels["tile_cache"]:labels["tile_cache"] + size]
    shapes = peek[labels["tile_cache_shapes"]:labels["tile_cache_shapes"] + size]
    lights = peek[labels["tile_cache_light"]:labels["tile_cache_light"] + size]
    slot_pairs = peek[labels["host_slot_pair"]:labels["host_slot_pair"] + SLOT_COUNT]

    def at(x, y):
        index = (y % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + x % TILE_CACHE_SIZE
        tile = materials[index], shapes[index]
        slot = slot_of(tile)
        if slot is not None:
            pair = slot_pairs[slot]
            tile = FIRST_PIECE + (pair >> 1), SHAPE_FULL | (BACKGROUND_SKY if pair & 1 else 0)
        return tile, lights[index] // lighting.LIGHT_SCALE
    return at


def expected_screen(bbc, labels):
    peek = bbc.memory.address.peek
    camera_x, camera_y = word(peek, labels["zp_camera_x"]), word(peek, labels["zp_camera_y"])
    hero = Player(x=word(peek, labels["zp_player_x"]), y=word(peek, labels["zp_player_y"]))
    screen_start = word(peek, labels["zp_screen_start"])
    plan_dx = _signed(peek[labels["zp_plan_dx"]]) if not peek[labels["host_flags"]] else 0
    tiles = host_tiles(bbc, labels)
    left, right = camera_x >> 2, (camera_x + camera.VIEW_COLUMNS - 1) >> 2
    top, bottom = camera_y >> 1, (camera_y + camera.VIEW_ROWS - 1) >> 1
    miner = lighting.smooth_miner_light(lambda x, y: lighting.transparent(tiles(x, y)[0]), hero.px, hero.py,
                                        lambda x, y: left <= x <= right and top <= y <= bottom, soft=True)
    new_columns = (set(range(camera.VIEW_COLUMNS - plan_dx, camera.VIEW_COLUMNS)) if plan_dx > 0
                   else set(range(0, -plan_dx)))

    def level(u, v):
        day = tiles(u // 4, v // 2)[1]
        if u - camera_x in new_columns:         # drawn after the light's list, as daylight
            return day
        return max(day, miner.get((u, v), 0))

    def mask_at(u, v, line):
        return lighting.mask_byte(level(u, v), u % 2, line)

    image = render_view(screen_start, camera_x, camera_y, lambda x, y: tiles(x, y)[0], tile_bytes, mask_at)
    frame = FRAMES[peek[labels["zp_player_frame"]]]
    column = (hero.px >> 1) - camera_x
    line = hero.py - camera_y * 8
    for l in range(player.PLAYER_HEIGHT):
        for c in range(sprites.SPRITE_COLUMNS):
            address = wrap(screen_start + ((line + l) >> 3) * 512 + (column + c) * CELL_BYTES) + ((line + l) & 7)
            i = l * sprites.SPRITE_COLUMNS + c
            image[address] = image[address] & frame[i] | frame[sprites.SPRITE_BYTES + i]
    return image


@pytest.mark.slow
@pytest.mark.parametrize("script", SCRIPTS.values(), ids=SCRIPTS.keys())
def test_tube_game_frames_match_model(tube_bbc, tube_machine, game_build, script):
    bbc = tube_bbc
    labels = game_build.labels["HOST"]
    peek = bbc.memory.address.peek
    bbc.disc.set_spin_up_delay(False)
    bbc.boot_disc(str(game_build.disc_filepath))
    started = bbc.run_until_or_timeout(lambda: peek[labels["host_frame_count"]] >= 2, RUN_TIMEOUT_EMULATED_SECONDS)
    assert started, "the game did not start"
    frames = 0
    for count, keys in script:
        for key in keys:
            bbc.keyboard.key_down(key)
        for _ in range(count):
            bbc.debugger.run_to(labels["host_frame_shown"], skip_current=True)
            expected = expected_screen(bbc, labels)
            actual = bbc.memory.region(tube_machine.screen_region).peek[SCREEN_START:SCREEN_END]
            differences = [hex(a) for a, b in expected.items() if actual[a - SCREEN_START] != b]
            assert differences[:8] == [], f"frame {frames}: {len(differences)} screen bytes differ"
            frames += 1
        for key in keys:
            bbc.keyboard.key_up(key)
    if any("T" in keys for _, keys in script):
        # Torches were dropped, and they light the tiles around them.
        camera_x, camera_y = word(peek, labels["zp_camera_x"]), word(peek, labels["zp_camera_y"])
        tiles = host_tiles(bbc, labels)
        view = [(x, y) for y in range(camera_y >> 1, (camera_y + camera.VIEW_ROWS - 1 >> 1) + 1)
                for x in range(camera_x >> 2, (camera_x + camera.VIEW_COLUMNS - 1 >> 2) + 1)]
        assert any(tiles(x, y)[0][0] == TORCH for x, y in view), "no torch in view"
        assert any(tiles(x, y)[1] > lighting.fixed_light(x, y) for x, y in view), "nothing lit by a torch"


STORE_SLOT_BYTES = 128      # asm/tube_layout.asm
CHUNK_SIZE, CHUNKS_ACROSS = 8, 32
STORE_SCRIPT = [(150, ["M", "L"]), (60, ["X", "L"]), (2, ["T"]), (30, ["Z", "L"]), (10, [])]


def play(bbc, labels, script):
    for count, keys in script:
        for key in keys:
            bbc.keyboard.key_down(key)
        for _ in range(count):
            bbc.debugger.run_to(labels["host_frame_shown"], skip_current=True)
        for key in keys:
            bbc.keyboard.key_up(key)


def test_host_keeps_the_store(tube_bbc, tube_machine, game_build):
    """The host holds every changed chunk, and the parasite a cache of them:
    each cached chunk is the host's, byte for byte, once the packets have
    carried the changes; and a chunk dropped from the cache is fetched again
    at once (COMMAND_FETCH) when a tile of it is changed."""
    bbc = tube_bbc
    labels = game_build.labels["HOST"]
    plabels = game_build.labels["PARASITE"]
    peek = bbc.memory.address.peek
    bbc.disc.set_spin_up_delay(False)
    bbc.boot_disc(str(game_build.disc_filepath))
    started = bbc.run_until_or_timeout(lambda: peek[labels["host_frame_count"]] >= 2, RUN_TIMEOUT_EMULATED_SECONDS)
    assert started, "the game did not start"
    parasite = bbc.connect_coprocessor().memory.address
    play(bbc, labels, STORE_SCRIPT)
    assert parasite.peek[plabels["cache_misses"]] == 0, "a chunk was needed before it was fetched"

    # Drop the chunks around the miner from the cache, spoiling
    # their slots, and dig down: the dig asks for the chunk before the view
    # moves, so before anything fetches it ahead.
    x = word(parasite.peek, plabels["zp_player_x"]) // 16 // 8         # sixteenths; tiles are 8 pixels
    y = word(parasite.peek, plabels["zp_player_y"]) // 16 // 16        # ... by 16 lines
    dropped = 0
    chunks = {(tx // CHUNK_SIZE, ty // CHUNK_SIZE) for tx in (x - 1, x, x + 1) for ty in (y, y + 1, y + 2)}
    for chunk_x, chunk_y in chunks:     # (y is the top of the miner's box)
        slot = parasite.peek[plabels["world_directory"] + chunk_y * CHUNKS_ACROSS + chunk_x]
        cache_slot = parasite.peek[plabels["cache_of"] + slot] if slot else 0
        if cache_slot:
            parasite.bus[plabels["cache_of"] + slot] = 0
            parasite.bus[plabels["cache_holds"] + cache_slot] = 0
            base = plabels["world_slots"] + (cache_slot - 1) * STORE_SLOT_BYTES
            for i in range(STORE_SLOT_BYTES):
                parasite.bus[base + i] = 0xEE
            dropped += 1
    assert dropped, "the miner's chunk isn't cached"
    play(bbc, labels, [(8, ["M", "L"]), (10, [])])
    assert parasite.peek[plabels["cache_misses"]] >= 1, "the dropped chunk wasn't fetched at once"

    for _ in range(4):          # until the queue is sent
        bbc.debugger.run_to(labels["host_frame_shown"], skip_current=True)
    assert parasite.peek[plabels["store_head"]] == parasite.peek[plabels["store_tail"]]
    used = parasite.peek[plabels["world_slots_used"]]
    assert used >= 3, "too few chunks changed to test"
    banks = [peek[labels["host_store_banks"] + i] for i in range(2)]
    cached = 0
    for slot in range(1, used + 1):
        cache_slot = parasite.peek[plabels["cache_of"] + slot]
        if not cache_slot:
            continue
        bank = bbc.memory.region(f"bank_{banks[(slot - 1) // 128]}").peek
        address = 0x8000 + (slot - 1) % 128 * STORE_SLOT_BYTES
        base = plabels["world_slots"] + (cache_slot - 1) * STORE_SLOT_BYTES
        held = parasite.peek[base:base + STORE_SLOT_BYTES]
        assert bank[address:address + STORE_SLOT_BYTES] == held, f"slot {slot}"
        cached += 1
    assert cached >= 2
