"""The game draws and scrolls the world exactly as the models do, every frame."""

from dataclasses import replace

import pytest
from beebium.client import Beebium

from conftest import boot_until_ready
from stratagem import actions, camera, lighting, player, sprites
from stratagem.actions import Hands
from stratagem.camera import Camera
from stratagem.player import Player
from stratagem.screen import CELL_BYTES, SCREEN_END, SCREEN_START, render_view, wrap
from stratagem.tiles import tile_bytes
from stratagem.world import World, tile_at

SCREENSHOT_DIRPATH_NAME = "screenshots"
FRAMES = sprites.sprite_frames()


def _signed(byte: int) -> int:
    return byte - 256 if byte & 0x80 else byte


def read_state(bbc: Beebium, labels: dict[str, int]) -> tuple[Camera, Player, int, int]:
    """The camera and player, the input they were last stepped with, and the
    screen start."""
    peek = bbc.memory.address.peek

    def word(name: str) -> int:
        return peek[labels[name]] | peek[labels[name] + 1] << 8

    state = Camera(
        focus_x=word("zp_focus_x"),
        focus_y=word("zp_focus_y"),
        lead=_signed(peek[labels["zp_lead"]]),
        camera_x=word("zp_camera_x"),
        camera_y=word("zp_camera_y"),
        dx=_signed(peek[labels["zp_plan_dx"]]),
        dy=_signed(peek[labels["zp_plan_dy"]]),
        redraw=peek[labels["zp_redraw"]] != 0,
    )
    hero = Player(
        x=word("zp_player_x"), y=word("zp_player_y"),
        vx=_signed(peek[labels["zp_player_vx"]]), vy=_signed(peek[labels["zp_player_vy"]]),
        on_ground=peek[labels["zp_player_on_ground"]] != 0,
        facing=_signed(peek[labels["zp_player_facing"]]),
        jump_held=peek[labels["zp_player_jump_held"]] != 0,
        air_jumps=peek[labels["zp_player_air_jumps"]],
    )
    return state, hero, peek[labels["zp_input"]], word("zp_screen_start")


def expected_light(state: Camera, hero: Player, world_tile_at=tile_at):
    """Each tile's light: daylight, and the miner's light within the view
    (which is what the tile cache holds)."""
    left, right = state.camera_x >> 2, (state.camera_x + camera.VIEW_COLUMNS - 1) >> 2
    top, bottom = state.camera_y >> 1, (state.camera_y + camera.VIEW_ROWS - 1) >> 1
    pool = lighting.miner_light(lambda x, y: lighting.transparent(world_tile_at(x, y)),
                                *lighting.miner_tile(hero.px, hero.py),
                                lambda x, y: left <= x <= right and top <= y <= bottom)
    return lambda x, y: lighting.lit_level(x, y, pool)


def expected_screen(state: Camera, hero: Player, screen_start: int, world_tile_at=tile_at) -> dict[int, int]:
    image = render_view(screen_start, state.camera_x, state.camera_y, world_tile_at, tile_bytes,
                        lighting.cell_masks(expected_light(state, hero, world_tile_at)))
    frame = FRAMES[sprites.frame_for(hero)]
    column = (hero.px >> 1) - state.camera_x
    line = hero.py - state.camera_y * 8
    for l in range(player.PLAYER_HEIGHT):
        for c in range(sprites.SPRITE_COLUMNS):
            address = wrap(screen_start + ((line + l) >> 3) * 512 + (column + c) * CELL_BYTES) + ((line + l) & 7)
            i = l * sprites.SPRITE_COLUMNS + c
            image[address] = image[address] & frame[i] | frame[sprites.SPRITE_BYTES + i]
    return image


TILE_CACHE_SIZE = 32       # asm/layout.asm


def assert_tile_cache_holds_view(bbc: Beebium, labels: dict[str, int], state: Camera, hero: Player,
                                 world_tile_at=tile_at) -> None:
    light_at = expected_light(state, hero, world_tile_at)
    size = TILE_CACHE_SIZE ** 2
    materials = bbc.memory.address.peek[labels["tile_cache"]:labels["tile_cache"] + size]
    shapes = bbc.memory.address.peek[labels["tile_cache_shapes"]:labels["tile_cache_shapes"] + size]
    lights = bbc.memory.address.peek[labels["tile_cache_light"]:labels["tile_cache_light"] + size]
    wrong = []
    for ty in range(state.camera_y >> 1, (state.camera_y + camera.VIEW_ROWS - 1 >> 1) + 1):
        for tx in range(state.camera_x >> 2, (state.camera_x + camera.VIEW_COLUMNS - 1 >> 2) + 1):
            index = (ty % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + tx % TILE_CACHE_SIZE
            if (materials[index], shapes[index]) != world_tile_at(tx, ty) or \
                    lights[index] != light_at(tx, ty) * lighting.LIGHT_SCALE:
                wrong.append((tx, ty))
    assert wrong[:8] == [], f"{len(wrong)} cached tiles are wrong"


def assert_screen_matches_model(bbc: Beebium, machine, labels: dict[str, int],
                                world_tile_at=tile_at) -> tuple[Camera, Player]:
    state, hero, _, screen_start = read_state(bbc, labels)
    assert_tile_cache_holds_view(bbc, labels, state, hero, world_tile_at)
    expected = expected_screen(state, hero, screen_start, world_tile_at)
    actual = bbc.memory.region(machine.screen_region).peek[SCREEN_START:SCREEN_END]
    differences = [hex(a) for a, b in expected.items() if actual[a - SCREEN_START] != b]
    assert differences[:8] == [], f"{len(differences)} displayed screen bytes differ at {state}, {hero}"
    return state, hero


def next_frame(bbc: Beebium, labels: dict[str, int]) -> None:
    bbc.debugger.run_to(labels["frame_shown"], skip_current=True)


@pytest.fixture
def game(launch_bbc, machine, game_build):
    bbc = launch_bbc(machine)
    labels = boot_until_ready(bbc, game_build, "STRATAGEM")
    next_frame(bbc, labels)
    return bbc, labels


def test_initial_view_matches_model(game, machine, game_build):
    bbc, labels = game
    assert_screen_matches_model(bbc, machine, labels)
    bbc.debugger.run()
    bbc.run_for_emulated_seconds(0.06)
    screenshot_dirpath = game_build.disc_filepath.parent / SCREENSHOT_DIRPATH_NAME
    screenshot_dirpath.mkdir(exist_ok=True)
    bbc.video.capture_frame().save_png(str(screenshot_dirpath / f"view-{machine.name}.png"))


KEY_INPUTS = {"Z": camera.INPUT_LEFT, "X": camera.INPUT_RIGHT, "K": camera.INPUT_UP, "M": camera.INPUT_DOWN,
              "L": camera.INPUT_ACTION, "SPACE": camera.INPUT_PLACE}
QUICK_SCRIPTS = {"dig-down"}       # the rest are marked slow
SCRIPTS = {
    "walk-right": [(90, ["X"]), (30, [])],
    "walk-left": [(90, ["Z"]), (30, [])],
    "jump": [(90, ["K"]), (30, [])],
    "jump-right": [(90, ["X", "K"]), (30, [])],
    "jump-left": [(90, ["Z", "K"]), (30, [])],
    "double-jump": [(6, ["K"]), (10, []), (6, ["K"]), (60, [])],
    "dig-down": [(60, ["M", "L"]), (20, [])],
    "tunnel-right": [(90, ["X", "L"]), (10, [])],
    "dig-down-then-build": [(40, ["M", "L"]), (30, ["SPACE"]), (30, ["K", "SPACE"]), (20, ["X"])],
    "tunnel-down-left": [(150, ["Z", "M", "L"]), (10, [])],
    "tunnel-down-right": [(150, ["X", "M", "L"]), (10, [])],
    "dig-into-slope-left": [(40, ["X"]), (150, ["Z", "M", "L"]), (10, [])],
    "dig-into-slope-right": [(40, ["Z"]), (150, ["X", "M", "L"]), (10, [])],
    "tunnel-up-right": [(60, ["M", "L"]), (150, ["X", "K", "L"]), (10, [])],
}


def press(bbc: Beebium, keys: list[str], down: bool) -> None:
    for key in keys:
        if key == "SPACE":
            (bbc.keyboard.key_down if down else bbc.keyboard.key_up)(" ")
        else:
            (bbc.keyboard.key_down if down else bbc.keyboard.key_up)(key)


@pytest.mark.parametrize("script", [script if name in QUICK_SCRIPTS else pytest.param(script, marks=pytest.mark.slow)
                                    for name, script in SCRIPTS.items()], ids=SCRIPTS.keys())
def test_every_frame_matches_model_while_playing(game, machine, script):
    bbc, labels = game
    peek = bbc.memory.address.peek
    world = World()
    hands = Hands()
    previous, previous_hero, _, _ = read_state(bbc, labels)
    moved = changes = 0
    for frames, keys in script:
        press(bbc, keys, True)
        for _ in range(frames):
            next_frame(bbc, labels)
            _, _, inputs, _ = read_state(bbc, labels)
            expected_hero = player.step(previous_hero, inputs, world.tile_at)
            hands, action, _ = actions.act(hands, expected_hero, inputs, world)
            changes += action != actions.NONE
            state, hero = assert_screen_matches_model(bbc, machine, labels, world.tile_at)
            assert hero == expected_hero
            assert (peek[labels["inventory"]], peek[labels["cooldown"]]) == (hands.inventory, hands.cooldown)
            direction = (1 if inputs & camera.INPUT_RIGHT else 0) - (1 if inputs & camera.INPUT_LEFT else 0)
            focus_x, focus_y = player.focus(expected_hero)
            assert state == camera.plan_camera(replace(previous, focus_x=focus_x, focus_y=focus_y), direction)
            moved += abs(state.dx) + abs(state.dy)
            previous, previous_hero = state, hero
        press(bbc, keys, False)
    if any("L" in keys or "SPACE" in keys for _, keys in script):
        assert changes > 3, "hardly anything was dug or placed"
