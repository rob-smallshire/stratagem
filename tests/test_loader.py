"""STRAT's loader shows the loading screen while it loads the game, then
gives the machine back as the game expects it (asm/host_low.asm,
asm/loading_screen.asm)."""

from conftest import RUN_TIMEOUT_EMULATED_SECONDS
from stratagem.build import GENERATED_DIRPATH
from stratagem.loading_screen import LOADING_SCHEME, SCREEN_SIZE, SCREEN_START, palette_writes

IRQ1V = 0x0204
SYSTEM_VIA_IER = 0xFE4E
USER_VIA_IER = 0xFE6E


def test_loader_shows_the_loading_screen_then_starts_the_game(tube_bbc, tube_machine, game_build):
    bbc = tube_bbc
    labels = game_build.labels["HOST"]
    peek = bbc.memory.address.peek
    bbc.disc.set_spin_up_delay(False)
    bbc.boot_disc(str(game_build.disc_filepath))

    bbc.debugger.run_to(labels["loading_screen_on"], timeout=120)
    irq1v = peek[IRQ1V] | peek[IRQ1V + 1] << 8
    system_ier, user_ier = peek[SYSTEM_VIA_IER], peek[USER_VIA_IER]

    bbc.debugger.run_to(labels["control_written"], timeout=120)
    screen = bbc.memory.region(tube_machine.screen_region).peek[SCREEN_START:SCREEN_START + SCREEN_SIZE]
    assert bytes(screen) == (GENERATED_DIRPATH / "loading_screen.bin").read_bytes(), "the picture isn't on the screen"
    palette = bbc.video_ula.palette
    assert [palette[index] for index in range(16)] == [p & 15 ^ 7 for p in palette_writes(LOADING_SCHEME)]
    assert peek[labels["host_frame_count"]] == 0, "the game started under the loading screen"

    bbc.debugger.run_to(labels["host_init"], timeout=120)
    assert peek[IRQ1V] | peek[IRQ1V + 1] << 8 == irq1v, "IRQ1V wasn't given back"
    assert (peek[SYSTEM_VIA_IER], peek[USER_VIA_IER]) == (system_ier, user_ier), "the VIAs' interrupts weren't"
    started = bbc.run_until_or_timeout(lambda: peek[labels["host_frame_count"]] >= 2, RUN_TIMEOUT_EMULATED_SECONDS)
    assert started, "the game did not start"
