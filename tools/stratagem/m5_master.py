"""What analogue or simple digital processing after a real Music 5000's
output might do for the overture, simulated on a recording of Beebium's
(strat-m5-record): a mastering chain of the kind a mixer and an effects
unit or two would give.

    uv run strat-m5-master [INPUT_FILEPATH] [OUTPUT_FILEPATH]

reads build/features/overture.wav and writes overture-processed.wav beside
it. The chain, in order:

1. High-pass at 25Hz: no rumble or offset (any mixer's low cut).
2. EQ, as a mixer's channel EQ or a graphic equaliser would: a low shelf,
   +6dB below 120Hz (weight); a broad +2dB at 250Hz (warmth); a broad
   +2dB at 3kHz (presence, against the board's steep output filter).
3. Gentle saturation, as a valve or tape stage: harmonics that make the
   bass heard on small speakers, and round off peaks. A third of the
   signal is driven through tanh.
4. Bus compression, as a dbx 160 or any stereo compressor: 2.5:1 above
   -20dBFS, on a 30ms average, smoothed over 200ms. It lifts the quiet
   passages and glues the parts together.
5. Reverb, a concert hall, as a digital reverb unit: 2.2s, darker as it
   decays (the highs die in 1.1s, the lows last 2.6s), early reflections,
   25ms before the tail, a quarter of the mix, nothing below 150Hz sent
   to it (no mud).
6. Stereo width: the side (left minus right) +2dB.
7. Normalised to -1dBFS.
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
from scipy import signal

from stratagem.build import PROJECT_DIRPATH

RATE = 48000


def read_wav(filepath: Path) -> np.ndarray:
    with wave.open(str(filepath)) as source:
        assert source.getframerate() == RATE and source.getnchannels() == 2 and source.getsampwidth() == 2
        data = source.readframes(source.getnframes())
    return np.frombuffer(data, "<i2").reshape(-1, 2).astype(np.float64) / 32768


def write_wav(audio: np.ndarray, filepath: Path) -> None:
    samples = np.round(np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(filepath), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(samples.tobytes())


# Biquads, from Robert Bristow-Johnson's Audio EQ Cookbook.

def peaking(hz: float, db: float, q: float) -> tuple[np.ndarray, np.ndarray]:
    a, w = 10 ** (db / 40), 2 * np.pi * hz / RATE
    alpha = np.sin(w) / (2 * q)
    b = [1 + alpha * a, -2 * np.cos(w), 1 - alpha * a]
    d = [1 + alpha / a, -2 * np.cos(w), 1 - alpha / a]
    return np.array(b) / d[0], np.array(d) / d[0]


def low_shelf(hz: float, db: float, slope: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    a, w = 10 ** (db / 40), 2 * np.pi * hz / RATE
    alpha = np.sin(w) / 2 * np.sqrt((a + 1 / a) * (1 / slope - 1) + 2)
    cos, root = np.cos(w), 2 * np.sqrt(a) * alpha
    b = [a * ((a + 1) - (a - 1) * cos + root), 2 * a * ((a - 1) - (a + 1) * cos), a * ((a + 1) - (a - 1) * cos - root)]
    d = [(a + 1) + (a - 1) * cos + root, -2 * ((a - 1) + (a + 1) * cos), (a + 1) + (a - 1) * cos - root]
    return np.array(b) / d[0], np.array(d) / d[0]


def high_pass(hz: float, order: int = 2) -> np.ndarray:
    return signal.butter(order, hz, "highpass", fs=RATE, output="sos")


def apply(audio: np.ndarray, filter_ba: tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    return signal.lfilter(*filter_ba, audio, axis=0)


def equalise(audio: np.ndarray) -> np.ndarray:
    audio = signal.sosfilt(high_pass(25), audio, axis=0)
    audio = apply(audio, low_shelf(120, 6))
    audio = apply(audio, peaking(250, 2, 0.8))
    return apply(audio, peaking(3000, 2, 0.9))


def saturate(audio: np.ndarray, drive: float = 2.0, mix: float = 1 / 3) -> np.ndarray:
    peak = np.abs(audio).max() or 1
    x = audio / peak
    driven = np.tanh(drive * x) / np.tanh(drive)
    return peak * ((1 - mix) * x + mix * driven)


def one_pole(x: np.ndarray, seconds: float) -> np.ndarray:
    k = np.exp(-1 / (seconds * RATE))
    return signal.lfilter([1 - k], [1, -k], x, axis=0)


def compress(audio: np.ndarray, threshold_db: float = -20, ratio: float = 2.5) -> np.ndarray:
    audio = audio / (np.abs(audio).max() or 1)
    level = np.sqrt(np.maximum(one_pole((audio ** 2).mean(axis=1), 0.03), 1e-12))
    level_db = 20 * np.log10(level)
    over = np.maximum(0, level_db - threshold_db)
    gain_db = one_pole(-over * (1 - 1 / ratio), 0.2)
    return audio * 10 ** (gain_db / 20)[:, None]


def hall_impulse(seconds: float = 3.0, seed: int = 5000) -> np.ndarray:
    """A stereo impulse response: decorrelated noise in three bands, each
    decaying at its own rate, after a pre-delay and early reflections."""
    rng = np.random.default_rng(seed)
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    tail = np.zeros((n, 2))
    bands = [(None, 400, 2.6), (400, 3000, 2.2), (3000, None, 1.1)]     # (low Hz, high Hz, RT60 s)
    for low, high, rt60 in bands:
        noise = rng.standard_normal((n, 2))
        if low and high:
            sos = signal.butter(2, [low, high], "bandpass", fs=RATE, output="sos")
        elif high:
            sos = signal.butter(2, high, "lowpass", fs=RATE, output="sos")
        else:
            sos = signal.butter(2, low, "highpass", fs=RATE, output="sos")
        tail += signal.sosfilt(sos, noise, axis=0) * np.exp(-6.91 * t / rt60)[:, None]
    pre_delay = int(0.025 * RATE)
    impulse = np.zeros((n + pre_delay, 2))
    impulse[pre_delay:] = tail * np.minimum(1, t / 0.08)[:, None]      # the tail builds over 80ms
    for ms, gain, side in ((11, 0.5, 0), (17, 0.45, 1), (23, 0.35, 0), (31, 0.3, 1), (41, 0.22, 0), (53, 0.18, 1)):
        impulse[int(ms / 1000 * RATE), side] += gain * np.abs(tail).max()
    return impulse / np.sqrt((impulse ** 2).sum(axis=0))


def reverberate(audio: np.ndarray, wet: float = 0.25) -> np.ndarray:
    send = signal.sosfilt(high_pass(150), audio, axis=0)
    impulse = hall_impulse()
    tail = np.stack([signal.fftconvolve(send[:, c], impulse[:, c])[:len(audio)] for c in (0, 1)], axis=1)
    tail *= np.sqrt((audio ** 2).mean()) / (np.sqrt((tail ** 2).mean()) or 1)
    return (1 - wet) * audio + wet * tail


def widen(audio: np.ndarray, side_db: float = 2) -> np.ndarray:
    mid, side = (audio[:, 0] + audio[:, 1]) / 2, (audio[:, 0] - audio[:, 1]) / 2 * 10 ** (side_db / 20)
    return np.stack([mid + side, mid - side], axis=1)


def master(audio: np.ndarray) -> np.ndarray:
    audio = equalise(audio)
    audio = saturate(audio)
    audio = compress(audio)
    audio = reverberate(audio)
    audio = widen(audio)
    return audio * (10 ** (-1 / 20) / (np.abs(audio).max() or 1))


def main() -> None:
    features_dirpath = PROJECT_DIRPATH / "build" / "features"
    source_filepath = Path(sys.argv[1]) if len(sys.argv) > 1 else features_dirpath / "overture.wav"
    output_filepath = Path(sys.argv[2]) if len(sys.argv) > 2 else source_filepath.with_name(
        source_filepath.stem + "-processed.wav")
    write_wav(master(read_wav(source_filepath)), output_filepath)
    print(output_filepath)


if __name__ == "__main__":
    main()
