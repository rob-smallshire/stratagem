"""The game draws and scrolls the world view exactly as the model does."""

import pytest
from beebium.client import Beebium

from conftest import boot_until_ready
from stratagem.screen import SCREEN_END, SCREEN_START, TILE_COLUMN_STEP, TILE_ROW_STEP, render_view, wrap
from stratagem.tiles import tile_graphics
from stratagem.world import view_tiles

SCREENSHOT_DIRPATH_NAME = "screenshots"

# asm/main.asm
INITIAL_VIEW_X = 120
INITIAL_VIEW_Y = 44


def screen_bytes(bbc: Beebium, machine) -> bytes:
    return bytes(bbc.memory.region(machine.screen_region).peek[SCREEN_START:SCREEN_END])


def view_state(bbc: Beebium, labels: dict[str, int]) -> tuple[int, int, int]:
    peek = bbc.memory.address.peek
    start = labels["zp_screen_start"]
    return peek[labels["zp_view_x"]], peek[labels["zp_view_y"]], peek[start] | peek[start + 1] << 8


def expected_screen_start(view_x: int, view_y: int) -> int:
    return wrap(SCREEN_START + (view_x - INITIAL_VIEW_X) * TILE_COLUMN_STEP
                + (view_y - INITIAL_VIEW_Y) * TILE_ROW_STEP)


def assert_view_matches_model(bbc: Beebium, machine, labels: dict[str, int]) -> None:
    view_x, view_y, screen_start = view_state(bbc, labels)
    assert screen_start == expected_screen_start(view_x, view_y)
    expected = render_view(screen_start, view_tiles(view_x, view_y), tile_graphics())
    actual = screen_bytes(bbc, machine)
    differences = [hex(SCREEN_START + i) for i in range(len(actual)) if actual[i] != expected[i]]
    assert differences[:8] == [], f"{len(differences)} screen bytes differ"


def run_main_loops(bbc: Beebium, labels: dict[str, int], count: int) -> None:
    for _ in range(count):
        bbc.debugger.run_to(labels["main_loop"], skip_current=True)


@pytest.fixture
def game(launch_bbc, machine, game_build):
    bbc = launch_bbc(machine)
    labels = boot_until_ready(bbc, game_build, "STRATAGEM")
    bbc.debugger.run_to(labels["main_loop"], skip_current=True)
    return bbc, labels


def test_initial_view_matches_model(game, machine, game_build):
    bbc, labels = game
    assert view_state(bbc, labels)[:2] == (INITIAL_VIEW_X, INITIAL_VIEW_Y)
    assert_view_matches_model(bbc, machine, labels)
    bbc.debugger.run()
    bbc.run_for_emulated_seconds(0.06)
    screenshot_dirpath = game_build.disc_filepath.parent / SCREENSHOT_DIRPATH_NAME
    screenshot_dirpath.mkdir(exist_ok=True)
    bbc.video.capture_frame().save_png(str(screenshot_dirpath / f"view-{machine.name}.png"))


@pytest.mark.parametrize("keys, dx, dy", [
    (["X"], 1, 0),
    (["Z"], -1, 0),
    (["M"], 0, 1),
    (["K"], 0, -1),
    (["X", "M"], 1, 1),
])
def test_scrolling_matches_model(game, machine, keys, dx, dy):
    bbc, labels = game
    steps = 9      # enough to wrap the screen start around in every direction
    for key in keys:
        bbc.keyboard.key_down(key)
    run_main_loops(bbc, labels, steps * 2)     # one scroll step every two frames
    for key in keys:
        bbc.keyboard.key_up(key)
    run_main_loops(bbc, labels, 4)
    view_x, view_y, _ = view_state(bbc, labels)
    assert (view_x - INITIAL_VIEW_X, view_y - INITIAL_VIEW_Y) == (dx * steps, dy * steps)
    assert_view_matches_model(bbc, machine, labels)
