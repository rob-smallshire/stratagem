"""The game's music, in a fourth sideways RAM bank (asm/mbank.asm): it
ticks from the vertical sync event, except while the host waits for
vertical sync to draw ahead of the beam, when the tick is owed and paid
once the frame is drawn (host_music_owed, asm/host_main.asm)."""

from conftest import boot_game
from stratagem import day_music, sequencer

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
    points = {host["music_event"]: "event", mbank["mbank_tick"]: "tick",
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


MUSIC_BANK_INDEX = 3                # asm/tube_layout.asm
PIECE_DAWN = 1                      # asm/mbank.asm
FIRST_QUIET_SECONDS, QUIET_MIN_TICKS = 15, 120 * 50
MODEL_TICKS = 300


def music_bank(bbc, host):
    """MBANK's sideways RAM, as its own addresses."""
    bank = bbc.memory.address.peek[host["ram_banks"] + MUSIC_BANK_INDEX]
    return bbc.memory.region(f"bank_{bank}").peek


def test_the_director_starts_with_dawn_plays_it_as_the_model_does_then_waits(tube_music_bbc, game_build):
    """After a quiet start, the first piece, the hour being dawn, is Dawn;
    the bank's player plays it as the model does; and when it ends, the
    director is quiet for at least QUIET_MIN."""
    bbc = tube_music_bbc
    host, mbank = game_build.labels["HOST"], game_build.labels["MBANK"]
    boot_game(bbc, game_build)
    start = bbc.debugger.cycle_count
    bank = lambda: music_bank(bbc, host)
    started = bbc.run_until_or_timeout(lambda: bank()[mbank["voice_count"]] != 0, FIRST_QUIET_SECONDS + 10)
    assert started, "no piece started"
    seconds = (bbc.debugger.cycle_count - start) / 2e6
    assert FIRST_QUIET_SECONDS - 1 < seconds < FIRST_QUIET_SECONDS + 2, f"after {seconds:.1f}s"
    assert bank()[mbank["director_last"]] == PIECE_DAWN

    def played(peek):
        return [peek[mbank["music_level"]] | peek[mbank["music_level"] + 1] << 8] + [
            tuple(peek[mbank[name] + v] for name in ("voice_level", "voice_phase", "voice_steps", "voice_pitch"))
            + (peek[mbank["voice_freq_low"] + v] | peek[mbank["voice_freq_middle"] + v] << 8
               | peek[mbank["voice_freq_high"] + v] << 16,)
            for v in range(peek[mbank["voice_count"]])]

    def modelled(player):
        return [player.level] + [(s.level, s.phase, s.count, s.pitch, s.frequency) for s in player.voices]

    # The piece started at the tick: each tick of the bank's player since
    # (wherever it ran: from the event, or owed) matches the model's.
    player = sequencer.SequencePlayer(day_music.piece(day_music.DAWN))
    bbc.debugger.add_breakpoint(mbank["music_tick"])
    for tick in range(MODEL_TICKS):
        bbc.debugger.run_and_wait_for_stop(timeout=60)
        player.tick()
        bbc.debugger.run_to(mbank["music_tick_end"], skip_current=True)     # (stopped at music_tick's breakpoint)
        assert played(bank()) == modelled(player), f"tick {tick}"
    bbc.debugger.clear_breakpoints()

    ended = bbc.run_until_or_timeout(lambda: bank()[mbank["voice_count"]] == 0, 120)
    assert ended, "the piece didn't end"
    bbc.run_for_emulated_seconds(0.1)
    quiet = bank()[mbank["director_quiet"]] | bank()[mbank["director_quiet"] + 1] << 8
    assert quiet >= QUIET_MIN_TICKS - 10, f"{quiet} ticks quiet"
