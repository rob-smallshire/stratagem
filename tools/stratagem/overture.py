"""The Stratagem Overture (art/music/Stratagem_Overture.mid) as a Music 5000
score (stratagem.music5000), for the title screen.

Each MIDI track becomes an instrument of music5000's orchestra, with a level;
a note's velocity makes it quieter or louder from there. Times are
quantised to the player's 50 ticks a second at 32 ticks a quarter, 93.75
beats a minute (the MIDI file's is 96). Every note starts on a sixteenth,
or two thirds of one, so the timing keeps; lengths shorter than a whole
beat, its articulation, keep to within a tick.

The notes are given to the board's sixteen channels as they come, each to a
channel that has finished its last note's release, the one this track used
last if it can, else to the one released longest ago; if every channel is
busy, a release is cut short, the same track's if it can (a chord struck
again, legato). A note struck again while it sounds ends the
first.

    uv run python -m stratagem.overture     # how it fits
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from stratagem import midi
from stratagem.music5000 import (CHANNELS, DB_PER_STEP, FULL, INSTRUMENTS, Event, Score, timed)

MIDI_FILEPATH = Path(__file__).resolve().parents[2] / "art" / "music" / "Stratagem_Overture.mid"
TICKS_PER_QUARTER = 32
TAIL_TICKS = 4 * TICKS_PER_QUARTER  # a bar's silence before it plays again

# Track name -> instrument, level (dB), and priority: higher takes a channel first.
TRACKS = {
    "Horn": ("horn", -1, 3),
    "Trumpets": ("trumpet", 0, 3),
    "Violins": ("violin", -2, 3),
    "Flute": ("flute", 0, 3),
    "Oboe": ("oboe", -1, 3),
    "Clarinet": ("clarinet", -1, 3),
    "Trombones": ("trombone", -8, 2),
    "Bass": ("bass", -2, 2),
    "Timpani": ("timpani", 0, 2),
    "Harp": ("harp", -3, 1),
    "Cellos": ("cello", -9, 1),
    "Strings": ("strings", -10, 1),
}


@dataclass
class Placed:
    start: int
    end: int
    pitch: int
    track: str
    quieter: int


def volume_steps(level_db: float, velocity: int) -> int:
    """Amplitude steps below full: the track's level and the velocity's,
    20 log10(velocity / 127)."""
    db = level_db + 20 * math.log10(velocity / 127)
    return min(FULL, max(0, round(-db / DB_PER_STEP)))


def notes(song: midi.Song) -> list[Placed]:
    scale = TICKS_PER_QUARTER / song.division
    placed = []
    for track in song.tracks:
        if track.name not in TRACKS:
            assert not track.notes, f"no instrument for track '{track.name}'"
            continue
        _, level_db, _ = TRACKS[track.name]
        sounding: dict[int, Placed] = {}
        for note in sorted(track.notes, key=lambda n: n.start):
            start, end = round(note.start * scale), round((note.start + note.length) * scale)
            previous = sounding.get(note.pitch)
            if previous and previous.end > start:
                previous.end = start
            p = Placed(start, max(end, start + 1), note.pitch, track.name, volume_steps(level_db, note.velocity))
            sounding[note.pitch] = p
            placed.append(p)
    return [p for p in placed if p.end > p.start]


@dataclass
class Channel:
    events: list[Event]
    time: int = 0                   # the end of its last event
    released: int = 0               # when its last note's release ends
    track: str | None = None
    instrument: str | None = None
    quieter: int | None = None


def allocate(placed: list[Placed]) -> tuple[list[Channel], int]:
    """The notes on channels, and how many releases were cut short."""
    channels = [Channel([]) for _ in range(CHANNELS)]
    cut = 0
    priority = {name: p for name, (_, _, p) in TRACKS.items()}
    for note in sorted(placed, key=lambda n: (n.start, -priority[n.track], -n.pitch)):
        free = [c for c in channels if c.time <= note.start]
        assert free, f"no channel for a note at tick {note.start}"
        released = [c for c in free if c.released <= note.start]
        if released:
            same = [c for c in released if c.track == note.track]
            channel = same[0] if same else min(released, key=lambda c: c.released)
        else:
            same = [c for c in free if c.track == note.track]
            channel = min(same or free, key=lambda c: c.time)
            cut += 1
        instrument, _, _ = TRACKS[note.track]
        if channel.instrument is None:      # (a stream starts with one)
            channel.events.append(("instrument", instrument))
            channel.instrument = instrument
        if note.start > channel.time:
            channel.events += timed("rest", note.start - channel.time)
        if channel.instrument != instrument:
            channel.events.append(("instrument", instrument))
            channel.instrument = instrument
        if channel.quieter != note.quieter:
            channel.events.append(("volume", note.quieter))
            channel.quieter = note.quieter
        channel.events += timed("note", note.end - note.start, note.pitch)
        channel.time = note.end
        channel.released = note.end + INSTRUMENTS[instrument].release_ticks()
        channel.track = note.track
    return [c for c in channels if c.events], cut


def score(filepath: Path = MIDI_FILEPATH) -> tuple[Score, int]:
    channels, cut = allocate(notes(midi.read(filepath)))
    end = max(c.time for c in channels) + TAIL_TICKS
    for channel in channels:
        channel.events += timed("rest", end - channel.time)
    return Score([c.events for c in channels]), cut


SCORE, RELEASES_CUT = score()


def main() -> None:
    streams = SCORE.streams()
    print(f"{len(SCORE.voices)} channels, {SCORE.ticks()} ticks ({SCORE.ticks() / 50:.1f}s), "
          f"{sum(map(len, streams))} bytes; {RELEASES_CUT} releases cut short")
    for index, (voice, stream) in enumerate(zip(SCORE.voices, streams)):
        tracks = sorted({e[1] for e in voice if e[0] == "instrument"})
        print(f"  channel {index}: {len(stream)} bytes, {', '.join(tracks)}")


if __name__ == "__main__":
    main()
