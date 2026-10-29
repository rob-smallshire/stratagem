"""STRAT's loader shows the title screen until SPACE is pressed, then the
loading page (the keys) while it loads the game, until SPACE is pressed
again, and gives the machine back as the game expects it (asm/host_low.asm,
asm/loading_screen.asm, asm/host_music.asm)."""

import numpy as np

from conftest import BOOT_LOADED, BOOT_TITLE, RUN_TIMEOUT_EMULATED_SECONDS, load_game, press_space
from stratagem.build import GENERATED_DIRPATH
from stratagem import loading_page
from stratagem.loading_screen import LOADING_SCHEME, SCREEN_SIZE, SCREEN_START, palette_writes

IRQ1V = 0x0204
SYSTEM_VIA_IER = 0xFE4E
USER_VIA_IER = 0xFE6E
TITLE_EMULATED_SECONDS = 1.0
POOL_FILL_EMULATED_SECONDS = 10.0
AUDIO_SECONDS_BUFFERED = 1      # a capture may start with up to a second from before


def test_loader_shows_the_title_screen_until_space_then_starts_the_game(tube_bbc, tube_machine, game_build):
    bbc = tube_bbc
    labels = game_build.labels["HOST"]
    peek = bbc.memory.address.peek
    bbc.disc.set_spin_up_delay(False)
    bbc.boot_disc(str(game_build.disc_filepath))

    bbc.debugger.run_to(labels["loading_screen_on"], timeout=120)
    irq1v = peek[IRQ1V] | peek[IRQ1V + 1] << 8
    system_ier, user_ier = peek[SYSTEM_VIA_IER], peek[USER_VIA_IER]
    assert bbc.run_until_or_timeout(lambda: peek[labels["zp_boot_status"]] == BOOT_TITLE,
                                    RUN_TIMEOUT_EMULATED_SECONDS), "the title screen wasn't shown"

    # It waits, the picture up, for SPACE.
    bbc.run_for_emulated_seconds(TITLE_EMULATED_SECONDS)
    assert peek[labels["zp_boot_status"]] == BOOT_TITLE, "it didn't wait for SPACE"
    bbc.debugger.run_to(labels["control_written"])
    screen = bbc.memory.region(tube_machine.screen_region).peek[SCREEN_START:SCREEN_START + SCREEN_SIZE]
    assert bytes(screen) == (GENERATED_DIRPATH / "loading_screen.bin").read_bytes(), "the picture isn't on the screen"
    palette = bbc.video_ula.palette
    assert [palette[index] for index in range(16)] == [p & 15 ^ 7 for p in palette_writes(LOADING_SCHEME)]

    # The loading page, until SPACE again: as the model has it, once the
    # pool has filled, the drips apart.
    load_game(bbc, game_build)
    filled = bbc.run_until_or_timeout(lambda: peek[labels["pool_filled"]] == loading_page.POOL_SIXELS,
                                      POOL_FILL_EMULATED_SECONDS)
    assert filled, "the pool didn't fill"
    shown = loading_page_shown(bbc)
    wanted = loaded_page()
    drips = {(row, loading_page.DRIP_X // 2) for row in loading_page.DRIP_ROWS}
    for row in range(loading_page.ROWS):
        for column in range(loading_page.COLUMNS):
            if (row, column) not in drips:
                assert shown[row][column] == wanted[row][column], f"row {row} column {column}"
    bbc.run_for_emulated_seconds(TITLE_EMULATED_SECONDS)
    assert peek[labels["zp_boot_status"]] == BOOT_LOADED, "it didn't wait for SPACE"
    press_space(bbc)
    bbc.debugger.run_to(labels["host_init"], timeout=120)
    assert peek[IRQ1V] | peek[IRQ1V + 1] << 8 == irq1v, "IRQ1V wasn't given back"
    assert (peek[SYSTEM_VIA_IER], peek[USER_VIA_IER]) == (system_ier, user_ier), "the VIAs' interrupts weren't"
    started = bbc.run_until_or_timeout(lambda: peek[labels["host_frame_count"]] >= 2, RUN_TIMEOUT_EMULATED_SECONDS)
    assert started, "the game did not start"


def loading_page_shown(bbc) -> list[bytes]:
    """The MODE 7 screen, in main RAM on both machines (MODE 7 on the B+,
    shadow MODE 7 on the Integra-B, whose video reads main RAM)."""
    screen = bbc.memory.region("main_ram").peek
    columns = loading_page.COLUMNS
    start = loading_page.SCREEN_START
    return [bytes(screen[start + row * columns:start + (row + 1) * columns]) for row in range(loading_page.ROWS)]


def loaded_page() -> list[bytearray]:
    """The page once loaded: the status line changed, the pool full."""
    rows = loading_page.page()
    rows[loading_page.STATUS_ROW][loading_page.STATUS_COLUMN:] = loading_page.status_line(loading_page.STATUS_LOADED)
    for address, value in loading_page.pool_steps():
        offset = address - loading_page.SCREEN_START
        rows[offset // loading_page.COLUMNS][offset % loading_page.COLUMNS] = value
    return rows


def test_the_overture_plays_under_the_title_and_the_loading_then_stops(tube_music_bbc, tube_machine, game_build):
    """With a Music 5000, the overture plays under the title, a tick a
    frame, while the flash bit is still switched in every line's blanking;
    then on under the loading page, while the game loads and after; SPACE
    there silences it before the game starts."""
    from conftest import boot_to_title
    from test_loading_screen import BLANKING_COLUMNS, LINES_PER_FRAME
    from test_music5000 import capture
    bbc = tube_music_bbc
    labels = game_build.labels["HOST"]
    boot_to_title(bbc, game_build)
    bbc.run_for_emulated_seconds(6.0)           # past the quiet opening
    for _ in range(3 * LINES_PER_FRAME):
        bbc.debugger.run_to(labels["control_written"], skip_current=True)
        assert bbc.crtc.state.column in BLANKING_COLUMNS, f"written at column {bbc.crtc.state.column}"
    audio = capture(bbc, 2.0)[AUDIO_SECONDS_BUFFERED * 48000:]
    assert np.abs(audio).max() > 150, "the title is silent"   # (still the quiet opening)

    press_space(bbc)
    audio = capture(bbc, 2.0)[AUDIO_SECONDS_BUFFERED * 48000:]
    assert bbc.memory.address.peek[labels["zp_boot_status"]] != BOOT_LOADED, "it loaded too soon to tell"
    assert np.abs(audio).max() > 150, "the loading is silent"
    load_game_wait(bbc, labels)
    audio = capture(bbc, 2.0)[AUDIO_SECONDS_BUFFERED * 48000:]
    assert np.abs(audio).max() > 150, "the loading page is silent once loaded"

    press_space(bbc)
    started = bbc.run_until_or_timeout(lambda: bbc.memory.address.peek[labels["host_frame_count"]] >= 2,
                                       RUN_TIMEOUT_EMULATED_SECONDS)
    assert started, "the game did not start"
    audio = capture(bbc, 2.0)[AUDIO_SECONDS_BUFFERED * 48000:]
    assert np.abs(audio).max() < 50, "the music plays on in the game"


def load_game_wait(bbc, labels) -> None:
    loaded = bbc.run_until_or_timeout(lambda: bbc.memory.address.peek[labels["zp_boot_status"]] == BOOT_LOADED,
                                      RUN_TIMEOUT_EMULATED_SECONDS)
    assert loaded, "the game didn't load"
