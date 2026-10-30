"""The world's day (asm/world_clock.asm): the hour, and whether the player
is underground, sent to the host in each packet for the music's
director."""

from conftest import boot_game

HOURS, HOUR_FRAMES, START_HOUR = 24, 2500, 5       # asm/tube_layout.asm
WORLD_UNDERGROUND = 0x80
DIG_DOWN_FRAMES = 150


def frames(bbc, labels, count):
    for _ in range(count):
        bbc.debugger.run_to(labels["host_frame_shown"], skip_current=True)


def test_the_day_starts_at_dawn_turns_its_hours_and_knows_underground(tube_bbc, game_build):
    bbc = tube_bbc
    host, parasite_labels = game_build.labels["HOST"], game_build.labels["PARASITE"]
    boot_game(bbc, game_build)
    peek = bbc.memory.address.peek
    frames(bbc, host, 2)
    assert peek[host["host_world"]] == START_HOUR, "not dawn, on the surface"

    # Near the hour's end, then over it: the next hour.
    parasite = bbc.connect_coprocessor().memory.address
    frames_address = parasite_labels["world_frames"]
    parasite.bus[frames_address] = (HOUR_FRAMES - 3) & 0xFF
    parasite.bus[frames_address + 1] = (HOUR_FRAMES - 3) >> 8
    frames(bbc, host, 6)
    assert peek[host["host_world"]] == START_HOUR + 1

    # The last hour turns to the first.
    parasite.bus[parasite_labels["world_hour"]] = HOURS - 1
    parasite.bus[frames_address] = (HOUR_FRAMES - 3) & 0xFF
    parasite.bus[frames_address + 1] = (HOUR_FRAMES - 3) >> 8
    frames(bbc, host, 6)
    assert peek[host["host_world"]] == 0

    # Digging down.
    bbc.keyboard.key_down("M")
    bbc.keyboard.key_down("L")
    frames(bbc, host, DIG_DOWN_FRAMES)
    bbc.keyboard.key_up("M")
    bbc.keyboard.key_up("L")
    frames(bbc, host, 2)
    assert peek[host["host_world"]] & WORLD_UNDERGROUND, "not underground, dug down"
