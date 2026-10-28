"""A software Music 5000, for listening to a player model's writes without
the emulator: sixteen channels, each a 24-bit phase stepped by its
frequency every sample, a wave looked up at the phase's top seven bits, the
amplitude added in the log domain and decoded as the DAC does, and a
stereo position. A new amplitude takes effect at the channel's next phase
wrap, as on the board. Its output filter is a second-order low-pass at
2kHz, fitted to Beebium's (2.5dB RMS from 300Hz to 14kHz).

    uv run strat-m5-synth [OUTPUT_FILEPATH]

renders the sequencer's overture (stratagem.sequencer) to
build/features/overture-sequenced.wav, and the title's (stratagem.overture,
as M5PLAY plays it) to overture-model.wav beside it, for comparison.

Not modelled: the board's stereo, which is a channel's share of six time
slots, here a gain each side. Its rendering of the title's overture
follows Beebium's recording: the level over time correlates at 0.98.
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
from scipy import signal

from stratagem.build import PROJECT_DIRPATH
from stratagem.music5000 import (AMPLITUDE, CHANNELS, CONTROL, DAC_LEVELS, FREQ_HIGH, FREQ_LOW, FREQ_MIDDLE,
                                 FULL, SAMPLE_RATE, WAVE_BYTES, WAVE_SELECT, WAVES)

TICKS_PER_SECOND = 50
WAV_RATE = 48000
PHASE_BITS = 24
INDEX_SHIFT = PHASE_BITS - 7

WAVE_TABLE = np.array([list(w) for w in WAVES.values()], dtype=np.int64)
SIGN = np.where(WAVE_TABLE & 0x80, 1, -1)
MAGNITUDE = WAVE_TABLE & 0x7F
LEVELS = np.array(DAC_LEVELS, dtype=np.float64)
OUTPUT_FILTER = signal.butter(2, 2000, fs=SAMPLE_RATE, output="sos")


def left_share(position: int) -> float:
    """A stereo position's share of the left: 0-7 right, 8-10 left, 11-15
    five sixths down to one sixth."""
    if position < 8:
        return 0.0
    if position < 11:
        return 1.0
    return (16 - position) / 6


class Board:
    def __init__(self):
        self.frequency = [0] * CHANNELS
        self.wave = [0] * CHANNELS
        self.amplitude = [0] * CHANNELS        # in effect
        self.pending = [0] * CHANNELS          # written, waiting for a wrap
        self.left = [left_share(0)] * CHANNELS
        self.phase = [0] * CHANNELS

    def write(self, register: int, value: int) -> None:
        kind, channel = register & 0xF0, register & 0x0F
        if kind == FREQ_LOW:
            self.frequency[channel] = self.frequency[channel] & 0xFFFF00 | value & 0xFE
        elif kind == FREQ_MIDDLE:
            self.frequency[channel] = self.frequency[channel] & 0xFF00FF | value << 8
        elif kind == FREQ_HIGH:
            self.frequency[channel] = self.frequency[channel] & 0x00FFFF | value << 16
        elif kind == WAVE_SELECT:
            self.wave[channel] = value >> 4
        elif kind == AMPLITUDE:
            self.pending[channel] = value
        elif kind == CONTROL:
            self.left[channel] = left_share(value & 15)

    def render(self, samples: int) -> np.ndarray:
        out = np.zeros((samples, 2))
        steps = np.arange(1, samples + 1, dtype=np.int64)
        for channel in range(CHANNELS):
            frequency, phase = self.frequency[channel], self.phase[channel]
            old, new = self.amplitude[channel], self.pending[channel]
            if frequency == 0 or old == 0 and new == 0:
                if frequency and old != new:
                    self.amplitude[channel] = new
                continue
            phases = phase + frequency * steps
            amplitude = np.full(samples, old)
            if old != new:
                wrap = -(-((1 << PHASE_BITS) - phase) // frequency) - 1      # the first sample after a wrap
                if wrap < samples:
                    amplitude[wrap:] = new
                    self.amplitude[channel] = new
            index = (phases >> INDEX_SHIFT) & (WAVE_BYTES - 1)
            wave = self.wave[channel]
            code = MAGNITUDE[wave][index] + amplitude - FULL
            value = np.where(code >= 0, LEVELS[np.clip(code, 0, 127)], 0) * SIGN[wave][index]
            left = self.left[channel]
            out[:, 0] += value * left
            out[:, 1] += value * (1 - left)
            self.phase[channel] = int(phases[-1]) & ((1 << PHASE_BITS) - 1)
        return out


def render(player, ticks: int) -> np.ndarray:
    """A player's ticks (music5000.Player or sequencer.SequencePlayer) as
    audio, at the board's rate."""
    board = Board()
    blocks, owed = [], 0
    for _ in range(ticks):
        for register, value in player.tick():
            board.write(register, value)
        owed += SAMPLE_RATE
        samples, owed = owed // TICKS_PER_SECOND, owed % TICKS_PER_SECOND
        blocks.append(board.render(samples))
    return signal.sosfilt(OUTPUT_FILTER, np.concatenate(blocks), axis=0)


def write_wav(audio: np.ndarray, filepath: Path) -> None:
    """At 48kHz, as Beebium records (strat-m5-master reads it), normalised."""
    audio = signal.resample_poly(audio, WAV_RATE // 375, SAMPLE_RATE // 375, axis=0)
    peak = np.abs(audio).max() or 1
    samples = np.round(audio * (0.9 * 32767 / peak)).astype("<i2")
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(filepath), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(WAV_RATE)
        out.writeframes(samples.tobytes())


def main() -> None:
    from stratagem import overture, sequencer
    from stratagem.music5000 import Player
    features_dirpath = PROJECT_DIRPATH / "build" / "features"
    sequenced_filepath = Path(sys.argv[1]) if len(sys.argv) > 1 else features_dirpath / "overture-sequenced.wav"
    piece = overture.sequencer_piece()
    player = sequencer.SequencePlayer(piece)
    write_wav(render(player, player.ticks()), sequenced_filepath)
    model_filepath = sequenced_filepath.with_name("overture-model.wav")
    write_wav(render(Player(overture.SCORE), overture.SCORE.ticks()), model_filepath)
    print(f"{sequenced_filepath} ({piece.size()} bytes)\n{model_filepath}")


if __name__ == "__main__":
    main()
