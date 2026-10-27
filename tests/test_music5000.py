"""The Music 5000, driven directly by M5PLAY without AMPLE
(stratagem.music5000, asm/m5play.asm): the encodings, the player against its
model, tick for tick, and the sound the board makes."""

import struct
import threading

import numpy as np
import pytest

from stratagem.music5000 import (DAC_LEVELS, FULL, PITCHES, SCALE, SCALE_NOTES, SCALE_TICKS, TUNE,
                                 Player, amplitude_for, decode_sample, encode_sample, frequency_of,
                                 frequency_register, note_hz, note_number)

MUSIC_5000 = "--hybrid-music-5000"
AUDIO_RATE = 48000
FIELD = 2                           # the Music 5000's in the audio frames


def test_samples_are_sign_and_log_magnitude():
    assert DAC_LEVELS[0] == 0 and DAC_LEVELS[127] == 8031
    assert encode_sample(1.0) == 0xFF and encode_sample(-1.0) == 0x7F
    assert encode_sample(0.0) == 0x80
    for value in (0.9, 0.3, -0.05, -0.6):
        assert abs(decode_sample(encode_sample(value)) - value) < 0.03 * abs(value) + 0.005


def test_amplitude_steps_are_a_sixteenth_of_a_halving():
    assert amplitude_for(0) == FULL
    assert amplitude_for(-6.02) == FULL - 16
    assert amplitude_for(-200) == 0


def test_pitches():
    assert note_number("A4") == 69 and note_number("C#5") == 73 and note_number("Bb3") == 58
    assert abs(frequency_of(frequency_register(440)) - 440) < 0.002
    assert all(p & 1 == 0 for p in PITCHES)


def test_the_voices_of_the_tune_keep_time():
    lengths = {sum(ticks for _, ticks in voice.events) for voice in TUNE}
    assert len(lengths) == 1


# M5PLAY in Beebium

def capture(bbc, seconds: float) -> np.ndarray:
    """The Music 5000's (left, right), the next seconds of it, as an (n, 2)
    array. The stream is in emulated time: it is drained while the machine
    runs in short slices, so none is dropped (a gap in its sequence)."""
    fmt = bbc.audio.format
    stride = fmt.source_count * 4
    wanted = int(seconds * AUDIO_RATE)
    frames, sequences = [], []
    done = threading.Event()

    def drain():
        for chunk in bbc.audio.subscribe(chunk_size=480):
            sequences.append((chunk.sequence, chunk.sample_count))
            for i in range(chunk.sample_count):
                frames.append(struct.unpack_from("<2h", chunk.samples, i * stride + FIELD * 4))
            if len(frames) >= wanted:
                break
        done.set()

    bbc.debugger.stop()
    thread = threading.Thread(target=drain, daemon=True)
    thread.start()
    while not done.is_set():
        bbc.run_for_emulated_seconds(0.25)
    thread.join()
    for (sequence, count), (following, _) in zip(sequences, sequences[1:]):
        assert following == sequence + count, "audio frames were dropped"
    return np.array(frames[:wanted], dtype=np.float64)


def frequency(signal: np.ndarray) -> float:
    """From upward zero crossings, interpolated."""
    a, b = signal[:-1], signal[1:]
    rising = np.nonzero((a < 0) & (b >= 0))[0]
    crossings = rising + -a[rising] / (b[rising] - a[rising])
    if len(crossings) < 3:
        return 0.0
    return (len(crossings) - 1) * AUDIO_RATE / (crossings[-1] - crossings[0])


def test_m5scale_plays_its_notes_in_tune(launch_bbc, machine, game_build):
    from conftest import boot_until_ready
    bbc = launch_bbc(machine, extra_args=[MUSIC_5000])
    boot_until_ready(bbc, game_build, "M5PLAY", command="*RUN M5SCALE")
    note_seconds = SCALE_TICKS / 50
    audio = capture(bbc, 2.5 + 2 * len(SCALE_NOTES) * note_seconds)[int(2.5 * AUDIO_RATE):]
    left, right = audio[:, 0], audio[:, 1]
    assert np.abs(right).max() > 1000 and np.abs(left).max() == 0, "the tone is on the right only"

    # Measure a tenth of a second at a time; where its halves agree, a note
    # is steady.
    window = AUDIO_RATE // 10
    heard = []
    for i in range(0, len(right) - window, window):
        first, second = frequency(right[i:i + window // 2]), frequency(right[i + window // 2:i + window])
        if first and abs(first - second) / first < 0.005:
            heard.append(frequency(right[i:i + window]))
    expected = [note_hz(note_number(n)) for n in SCALE_NOTES]
    for hz in heard:
        nearest = min(expected, key=lambda e: abs(e - hz))
        assert abs(hz - nearest) / nearest < 0.003, f"{hz:.1f}Hz isn't a note of the scale"
    assert {min(expected, key=lambda e: abs(e - hz)) for hz in heard} == set(expected)


def test_m5play_plays_the_tune_as_the_model_does(launch_bbc, machine, game_build):
    from conftest import boot_until_ready
    bbc = launch_bbc(machine, extra_args=[MUSIC_5000])
    labels = boot_until_ready(bbc, game_build, "M5PLAY", command="*RUN M5PLAY")
    peek = bbc.memory.address.peek
    voices = len(TUNE)

    def played():
        return [tuple(peek[labels[name] + v] for name in ("voice_level", "voice_phase", "voice_ticks"))
                for v in range(voices)]

    def modelled(player):
        return [(s.level, s.phase, s.ticks) for s in player.states]

    # Catch the model up with the ticks already played, then follow the
    # player through the whole tune and into its loop.
    player = Player(TUNE)
    bbc.debugger.run_to(labels["music_tick_end"])
    for ticks in range(1, 2000):
        player.tick()
        if modelled(player) == played():
            break
    else:
        pytest.fail("the player's state isn't one the model reaches")
    loop_ticks = sum(t for _, t in TUNE[0].events)
    costs = []
    for tick in range(loop_ticks + 50):
        bbc.debugger.run_to(labels["music_tick"], skip_current=True)
        start = bbc.debugger.cycle_count
        bbc.debugger.run_to(labels["music_tick_end"])
        costs.append(bbc.debugger.cycle_count - start)
        player.tick()
        assert played() == modelled(player), f"tick {ticks + tick}"
    # A frame is 40000 cycles: the tick is about 1% of it, 2% at most.
    assert np.mean(costs) < 400 and max(costs) < 800, (np.mean(costs), max(costs))

    audio = capture(bbc, 3.5)[AUDIO_RATE:]
    assert np.abs(audio).max() > 1000, "it's silent"
    assert np.abs(audio).max() < 32000, "it clips"
