"""The world's day (asm/world_clock.asm): a 16-bit clock of frames, its
high byte the time, sent to the host in each packet with whether the
player is underground, for the music's director."""

from conftest import boot_game
from stratagem import daynight
from stratagem.daynight import START_TIME
from stratagem.tiles import BLACK, BLUE, GLOW, MAGENTA, RED, TILE_COLOUR_BASE

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


def test_the_sky_goes_dark_at_night_unless_water_may_show(tube_bbc, game_build):
    """The host's palette (daynight.sky_colours): the glow magenta at dawn
    and dusk, and in dusk's middle the sky magenta and the glow red; at night the sky's blue and the glow black, so that no sky behind a lit
    tile shows as day; but blue while the view may reach water."""
    bbc = tube_bbc
    host, parasite_labels = game_build.labels["HOST"], game_build.labels["PARASITE"]
    boot_game(bbc, game_build)
    parasite = bbc.connect_coprocessor().memory.address
    clock = parasite_labels["zp_time"]
    palette = bbc.video_ula.palette

    def colours():
        return palette[TILE_COLOUR_BASE + BLUE], palette[TILE_COLOUR_BASE + GLOW]

    def set_time(time):
        parasite.bus[clock], parasite.bus[clock + 1] = time & 0xFF, time >> 8
        frames(bbc, host, 4)

    for hours in (12, 17, 18, 23, 3, 6):
        time = round(hours * 0x10000 / 24)
        set_time(time)
        assert colours() == daynight.sky_colours(time >> 8), f"at {hours}h"
    assert colours() == (BLUE, MAGENTA)         # dawn
    set_time(18 * 0x10000 // 24)
    assert colours() == (MAGENTA, RED)          # dusk's middle
    set_time(23 * 0x10000 // 24)
    assert colours() == (BLACK, BLACK)
    for hours in (23, 18):                      # the view far down: water may show
        time = hours * 0x10000 // 24
        set_time(time)
        bbc.debugger.run_to(host["host_glow"], skip_current=True)
        bbc.memory.address.bus[host["zp_camera_y"] + 1] = 1
        frames(bbc, host, 1)
        assert colours() == daynight.sky_colours(time >> 8, 256) == (BLUE, BLUE if hours == 23 else MAGENTA)
