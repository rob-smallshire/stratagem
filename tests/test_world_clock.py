"""The world's day (asm/world_clock.asm): a 16-bit clock of frames, its
high byte the time, sent to the host in each packet with whether the
player is underground, for the music's director."""

from conftest import boot_game
from stratagem.daynight import START_TIME

WORLD_UNDERGROUND = 0x80
DIG_DOWN_FRAMES = 150


def frames(bbc, labels, count):
    for _ in range(count):
        bbc.debugger.run_to(labels["host_frame_shown"], skip_current=True)


def test_the_day_starts_at_dawn_turns_and_knows_underground(tube_bbc, game_build):
    bbc = tube_bbc
    host, parasite_labels = game_build.labels["HOST"], game_build.labels["PARASITE"]
    boot_game(bbc, game_build, time=START_TIME)
    peek = bbc.memory.address.peek
    frames(bbc, host, 2)
    assert peek[host["host_time"]] == START_TIME >> 8, "not the first full daylight"
    assert peek[host["host_world"]] == 0, "not on the surface"

    parasite = bbc.connect_coprocessor().memory.address
    clock = parasite_labels["zp_time"]

    def set_clock(frame):
        parasite.bus[clock], parasite.bus[clock + 1] = frame & 0xFF, frame >> 8

    # Near a time's end, then over it: the next.
    set_clock(0x6000 - 3)
    frames(bbc, host, 6)
    assert peek[host["host_time"]] == 0x60

    # The last time of the day turns to midnight.
    set_clock(0x10000 - 3)
    frames(bbc, host, 6)
    assert peek[host["host_time"]] == 0

    # Digging down.
    bbc.keyboard.key_down("M")
    bbc.keyboard.key_down("L")
    frames(bbc, host, DIG_DOWN_FRAMES)
    bbc.keyboard.key_up("M")
    bbc.keyboard.key_up("L")
    frames(bbc, host, 2)
    assert peek[host["host_world"]] == WORLD_UNDERGROUND, "not underground, dug down"


def test_a_test_can_start_the_day_at_noon(tube_bbc, game_build):
    """boot_game's time (world_start_time) is set before the game starts."""
    bbc = tube_bbc
    boot_game(bbc, game_build, time=0x8000)
    host = game_build.labels["HOST"]
    frames(bbc, host, 2)
    assert bbc.memory.address.peek[host["host_time"]] == 0x80
