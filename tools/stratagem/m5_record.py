"""Record what M5PLAY plays on the Music 5000, in Beebium, to a WAV file for
listening: from the first note, normalised (the board's own level is low:
one channel at full scale is a sixteenth of full scale).

    uv run strat-m5-record [SECONDS] [OUTPUT_FILEPATH]

Writes build/features/overture.wav by default: the whole overture, on the
B+ 128K.
"""

from __future__ import annotations

import struct
import sys
import threading
import wave
from pathlib import Path

import numpy as np
from beebium.client import Beebium

from stratagem.build import PROJECT_DIRPATH, build
from stratagem.overture import SCORE

AUDIO_RATE = 48000
FIELD = 2                           # the Music 5000's in the audio frames
TICKS_PER_SECOND = 50


def record(seconds: float) -> np.ndarray:
    game_build = build()
    labels = game_build.labels["M5PLAY"]
    with Beebium.launch(variant="model-b-plus-128k", preset="model-b-plus-128k",
                        extra_args=["--hybrid-music-5000"]) as bbc:
        bbc.system.set_speed_multiplier(0.0)
        bbc.run_for_emulated_seconds(2.0)           # to the BASIC prompt
        bbc.disc.set_spin_up_delay(False)
        bbc.disc.drive(0).insert(str(game_build.disc_filepath))
        bbc.debugger.ensure_running()
        bbc.keyboard.type("*RUN M5PLAY\r")
        bbc.debugger.run_to(labels["music_tick"], timeout=60)   # the first tick

        fmt = bbc.audio.format
        stride = fmt.source_count * 4
        wanted = int(seconds * AUDIO_RATE)
        frames: list[tuple[int, int]] = []
        done = threading.Event()

        def drain():
            for chunk in bbc.audio.subscribe(chunk_size=480):
                for i in range(chunk.sample_count):
                    frames.append(struct.unpack_from("<2h", chunk.samples, i * stride + FIELD * 4))
                if len(frames) >= wanted:
                    break
            done.set()

        thread = threading.Thread(target=drain, daemon=True)
        thread.start()
        while not done.is_set():
            bbc.run_for_emulated_seconds(0.25)
        thread.join()
    audio = np.array(frames[:wanted], dtype=np.float64)
    # The stream holds up to a second from before the subscription: start
    # at the first sound.
    loud = np.nonzero(np.abs(audio).max(axis=1) > 0)[0]
    return audio[loud[0]:] if loud.size else audio


def write_wav(audio: np.ndarray, filepath: Path) -> None:
    peak = np.abs(audio).max() or 1
    samples = np.round(audio * (0.9 * 32767 / peak)).astype("<i2")
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(filepath), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(AUDIO_RATE)
        out.writeframes(samples.tobytes())


def main() -> None:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else SCORE.ticks() / TICKS_PER_SECOND + 1
    filepath = Path(sys.argv[2]) if len(sys.argv) > 2 else PROJECT_DIRPATH / "build" / "features" / "overture.wav"
    audio = record(seconds)
    write_wav(audio, filepath)
    print(f"{filepath}: {len(audio) / AUDIO_RATE:.1f}s")


if __name__ == "__main__":
    main()
