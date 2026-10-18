"""The game draws and scrolls the world exactly as the models do, every frame."""

import pytest
from beebium.client import Beebium

from conftest import boot_until_ready
from stratagem import camera
from stratagem.camera import MARKER_COLUMNS, MARKER_LINES, Camera
from stratagem.screen import CELL_BYTES, SCREEN_END, SCREEN_START, render_view, wrap
from stratagem.tiles import tile_graphics
from stratagem.world import tile_at

MARKER_COLOUR = 0x3F       # asm/render.asm
SCREENSHOT_DIRPATH_NAME = "screenshots"
GRAPHICS = tile_graphics()


def _signed(byte: int) -> int:
    return byte - 256 if byte & 0x80 else byte


def read_state(bbc: Beebium, labels: dict[str, int]) -> tuple[Camera, int, int]:
    """The camera state, the input it was last stepped with, and the screen start."""
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
    return state, peek[labels["zp_input"]], word("zp_screen_start")


def expected_screen(state: Camera, screen_start: int) -> dict[int, int]:
    image = render_view(screen_start, state.camera_x, state.camera_y, tile_at, GRAPHICS)
    column, line = camera.marker_screen_position(state)
    for l in range(line, line + MARKER_LINES):
        for c in range(column, column + MARKER_COLUMNS):
            address = wrap(screen_start + (l >> 3) * 512 + c * CELL_BYTES) + (l & 7)
            image[address] ^= MARKER_COLOUR
    return image


TILE_CACHE_SIZE = 32       # asm/layout.asm


def assert_tile_cache_holds_view(bbc: Beebium, labels: dict[str, int], state: Camera) -> None:
    cache = bbc.memory.address.peek[labels["tile_cache"]:labels["tile_cache"] + TILE_CACHE_SIZE ** 2]
    wrong = []
    for ty in range(state.camera_y >> 1, (state.camera_y + camera.VIEW_ROWS - 1 >> 1) + 1):
        for tx in range(state.camera_x >> 2, (state.camera_x + camera.VIEW_COLUMNS - 1 >> 2) + 1):
            if cache[(ty % TILE_CACHE_SIZE) * TILE_CACHE_SIZE + tx % TILE_CACHE_SIZE] != tile_at(tx, ty):
                wrong.append((tx, ty))
    assert wrong[:8] == [], f"{len(wrong)} cached tiles are wrong"


def assert_screen_matches_model(bbc: Beebium, machine, labels: dict[str, int]) -> Camera:
    state, _, screen_start = read_state(bbc, labels)
    assert_tile_cache_holds_view(bbc, labels, state)
    expected = expected_screen(state, screen_start)
    actual = bbc.memory.region(machine.screen_region).peek[SCREEN_START:SCREEN_END]
    differences = [hex(a) for a, b in expected.items() if actual[a - SCREEN_START] != b]
    assert differences[:8] == [], f"{len(differences)} displayed screen bytes differ at {state}"
    return state


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


@pytest.mark.parametrize("keys", [["X"], ["Z"], ["M"], ["K"], ["X", "M"], ["Z", "K"]],
                         ids=lambda keys: "+".join(keys))
def test_every_frame_matches_model_while_scrolling(game, machine, keys):
    bbc, labels = game
    previous, _, _ = read_state(bbc, labels)
    moved = 0
    for frame in range(90):
        if frame == 0:
            for key in keys:
                bbc.keyboard.key_down(key)
        if frame == 60:
            for key in keys:
                bbc.keyboard.key_up(key)
        next_frame(bbc, labels)
        state = assert_screen_matches_model(bbc, machine, labels)
        _, inputs, _ = read_state(bbc, labels)
        assert state == camera.step(previous, inputs)
        moved += abs(state.dx) + abs(state.dy)
        previous = state
    assert moved > 10, "the camera hardly moved"
