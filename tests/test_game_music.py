"""The game's music, in a fourth sideways RAM bank (asm/mbank.asm): it
ticks from the vertical sync event, except while the host waits for
vertical sync to draw ahead of the beam, when the tick is owed and paid
once the frame is drawn (host_music_owed, asm/host_main.asm)."""

from conftest import boot_game

FRAMES = 150
SCRIPT_KEYS = [["M", "L"], ["X", "L"], ["Z"]]


def test_the_games_music_waits_for_the_frame_and_loses_no_tick(tube_music_bbc, game_build):
    """Walking and digging, every vertical sync is a tick, and the host
    is back from its wait for vertical sync, and drawing, before the beam
    reaches the top of the display, as without the music."""
    bbc = tube_music_bbc
    host, mbank = game_build.labels["HOST"], game_build.labels["MBANK"]
    boot_game(bbc, game_build)
    crtc = bbc.crtc.state
    lines_per_row = crtc.max_scanline + 1
    display_top = ((crtc.vtotal + 1 - crtc.vsync_pos) * lines_per_row + crtc.vtotal_adj) * 128

    bbc.debugger.run_to(host["host_frame_shown"], skip_current=True)    # (no event under way)
    owed_before = bbc.memory.address.peek[host["host_ticks_owed"]]
    points = {host["music_event"]: "event", mbank["music_tick"]: "tick",
              host["host_after_vsync"]: "after", host["host_frame_shown"]: "shown"}
    for address in points:
        bbc.debugger.add_breakpoint(address)
    counts = {"event": 0, "tick": 0, "after": 0, "shown": 0}
    latest = 0
    for keys in SCRIPT_KEYS:
        for key in keys:
            bbc.keyboard.key_down(key)
        shown = counts["shown"]
        while counts["shown"] < shown + FRAMES // len(SCRIPT_KEYS):
            bbc.debugger.run_and_wait_for_stop(timeout=60)
            what = points[bbc.cpu.pc]
            counts[what] += 1
            if what == "after":
                latest = max(latest, bbc.crtc.state.cycles_since_vsync)
        for key in keys:
            bbc.keyboard.key_up(key)
    bbc.debugger.clear_breakpoints()

    owed = bbc.memory.address.peek[host["host_ticks_owed"]]
    assert counts["tick"] + owed == counts["event"] + owed_before, f"{counts}, {owed_before} then {owed} owed"
    assert latest < display_top, f"back from vertical sync {latest} cycles after it, the display at {display_top}"
