"""The Stratagem Overture (art/music/Stratagem_Overture.mid) as a Music 5000
score (stratagem.music5000), for the title screen, arranged for the board
(art/music/style.md is the mood).

Each MIDI track becomes an instrument of music5000's orchestra, with a level;
a note's velocity makes it quieter or louder from there. Times are
quantised to the player's 50 ticks a second at 96 beats a minute, 31.25
ticks a quarter, each note's start and end to the nearest tick.

The arrangement, beyond the file:

- Dynamics over the whole: a quiet opening that swells into bar 5, the
  woodwinds' B minor a little withdrawn, a swell into the tutti at bar 25,
  a bare coda, and a last chord that opens out and dies away. A long note
  changes volume as it sounds.
- Weight at the bottom and in the middle: the bass, cellos, trombones and
  timpani louder than the file has them, the bass doubled (detuned) where a
  channel is free, the timpani an octave down, and the violins an octave
  down too (their ostinato in the tutti reached D7).
- The strings' chords spread across the stereo field.
- A timpani roll into the tutti, and another into a last full chord of D
  (strings, cellos, bass, timpani) under the horns' and trumpets' D.
- Decorations, placed only where a channel is free and never displacing
  the score's own notes: each melody doubled on a second channel slightly
  detuned (an ensemble rather than one player), the strings' chords
  likewise, and the melody echoed, quieter, on the other side.

The score's notes are given to the board's sixteen channels as they come.
The sustained parts' chords move legato, each onto the channels of the one
before, cutting its release. Other notes go to a channel that has finished
its last note's release, the one this track used last if it can, else to
the one released longest ago; if every channel is busy, a release is cut
short, the same track's if it can. A note struck again while it sounds ends the
first. Decorations then take what is left.

    uv run python -m stratagem.overture     # how it fits
"""

from __future__ import annotations

import math
from functools import cache
from dataclasses import dataclass, replace
from pathlib import Path

from stratagem import midi, sequencer
from stratagem.music5000 import CHANNELS, DB_PER_STEP, FULL, INSTRUMENTS, Event, Score, note_number, timed

MIDI_FILEPATH = Path(__file__).resolve().parents[2] / "art" / "music" / "Stratagem_Overture.mid"
TICKS_PER_SECOND = 50
BEATS_PER_MINUTE = 96
TICKS_PER_QUARTER = TICKS_PER_SECOND * 60 / BEATS_PER_MINUTE    # 31.25
TICKS_PER_BAR = 4 * TICKS_PER_QUARTER
TAIL_TICKS = 2 * round(TICKS_PER_BAR)   # silence before it plays again
HEADROOM_DB = 4                         # below full, for the swells
SEGMENT_TICKS = 6                       # how often a long note's volume may change

# Track name -> instrument, level (dB), stereo position or None (the
# instrument's), and priority: higher takes a channel first.
TRACKS = {
    "Horn": ("horn", -1, None, 3),
    "Trumpets": ("trumpet", -1, None, 3),
    "Violins": ("violin", -2, None, 3),
    "Flute": ("flute", 0, None, 3),
    "Oboe": ("oboe", -1, None, 3),
    "Clarinet": ("clarinet", -1, None, 3),
    "Trombones": ("trombone", -2, None, 2),
    "Bass": ("bass", 2, None, 2),
    "Timpani": ("timpani", 9, None, 2),
    "Harp": ("harp", -5, None, 1),
    "Cellos": ("cello", -4, None, 1),
    "Strings": ("strings", -8, None, 1),
}
# Octaves moved, in semitones: the violins' high line down, for weight
# (their ostinato in the tutti reached D7), and the timpani down.
TRANSPOSE = {"Violins": -12, "Timpani": -12}
MELODIES = ("Horn", "Trumpets", "Violins", "Flute", "Oboe", "Clarinet")
LEGATO = ("Strings", "Cellos", "Bass", "Trombones")     # each chord on the last one's channels

# Stereo positions: 8 all left, 11-15 five sixths to one sixth left, 0 all right.
STRING_SPREAD = (11, 13, 15)            # a chord's notes, low to high
OPPOSITE = {11: 15, 12: 14, 13: 13, 14: 12, 15: 11, 8: 0, 0: 8}

# Dynamics: (bar, dB) points, from bar 1; straight lines between.
DYNAMICS = [(1, -15), (4.5, -4), (5, -2), (9, 0), (12.5, 0), (13, -3), (23.5, -3), (25, 2),
            (33, 3), (36.5, 4), (37, -5), (39.5, -5), (40, -2), (41, 4), (42, -6), (43, -20)]


def bar_tick(bar: float, per_quarter: float = TICKS_PER_QUARTER) -> int:
    """The tick at which a bar (from 1) starts, or part way into it (or the
    step, with per_quarter steps a quarter)."""
    return round((bar - 1) * 4 * per_quarter)


def dynamics_db(tick: float) -> float:
    points = [(bar_tick(b), db) for b, db in DYNAMICS]
    if tick <= points[0][0]:
        return points[0][1]
    for (t0, d0), (t1, d1) in zip(points, points[1:]):
        if tick <= t1:
            return d0 + (d1 - d0) * (tick - t0) / max(1, t1 - t0)
    return points[-1][1]


@dataclass(frozen=True)
class Placed:
    start: int
    end: int
    pitch: int
    track: str
    velocity: int
    level_db: float = 0             # beyond the track's
    pan: int | None = None
    detune: int = 0
    optional: int = 0               # 0: the score's; else a decoration, lower placed first

    @property
    def instrument(self) -> str:
        return TRACKS[self.track][0]

    def quieter(self, tick: int) -> int:
        """Amplitude steps below full at a tick: the track's level, the
        velocity's (20 log10(velocity / 127)), the dynamics and the
        headroom."""
        db = (TRACKS[self.track][1] + self.level_db + 20 * math.log10(self.velocity / 127)
              + dynamics_db(tick) - HEADROOM_DB)
        return min(FULL, max(0, round(-db / DB_PER_STEP)))

    def release_end(self) -> int:
        """When its release is over: as the envelope has it, from the level
        it has reached by its end (from silence: it may be less)."""
        return self.end + release_ticks(self.instrument, self.end - self.start)


@cache
def release_ticks(instrument_name: str, length: int) -> int:
    """Ticks to release a note of this length (from silence) to silence."""
    instrument = INSTRUMENTS[instrument_name]
    level, decaying = 0, False
    for _ in range(length):
        if not decaying:
            level = min(FULL, level + instrument.attack)
            decaying = level == FULL
        else:
            level = max(instrument.sustain, level - instrument.decay)
    return -(-level // instrument.release)


def file_notes(song: midi.Song, per_quarter: float = TICKS_PER_QUARTER) -> list[Placed]:
    scale = per_quarter / song.division
    placed: list[Placed] = []
    for track in song.tracks:
        if track.name not in TRACKS:
            assert not track.notes, f"no instrument for track '{track.name}'"
            continue
        sounding: dict[int, int] = {}       # pitch -> index in placed
        for note in sorted(track.notes, key=lambda n: n.start):
            start, end = round(note.start * scale), round((note.start + note.length) * scale)
            previous = sounding.get(note.pitch)
            if previous is not None and placed[previous].end > start:
                placed[previous] = replace(placed[previous], end=start)
            sounding[note.pitch] = len(placed)
            placed.append(Placed(start, max(end, start + 1), note.pitch, track.name, note.velocity,
                                 pan=TRACKS[track.name][2]))
    return [p for p in placed if p.end > p.start]


def chords(notes: list[Placed], track: str) -> dict[int, list[int]]:
    """A track's notes by start: their indices, low to high."""
    by_start: dict[int, list[int]] = {}
    for index, note in enumerate(notes):
        if note.track == track:
            by_start.setdefault(note.start, []).append(index)
    return {start: sorted(chord, key=lambda i: notes[i].pitch) for start, chord in by_start.items()}


def spread_strings(notes: list[Placed]) -> list[Placed]:
    notes = list(notes)
    for chord in chords(notes, "Strings").values():
        for place, index in enumerate(chord):
            notes[index] = replace(notes[index], pan=STRING_SPREAD[min(place, len(STRING_SPREAD) - 1)])
    return notes


def roll(pitch: str, from_bar: float, to_bar: float, velocities: tuple[int, int],
         per_quarter: float = TICKS_PER_QUARTER) -> list[Placed]:
    """A timpani roll: strokes every eighth of a beat, louder as it goes."""
    start, end = bar_tick(from_bar, per_quarter), bar_tick(to_bar, per_quarter)
    stroke = per_quarter / 8
    count = int((end - start) / stroke)
    return [Placed(round(start + i * stroke), round(start + (i + 1) * stroke), note_number(pitch), "Timpani",
                   round(velocities[0] + (velocities[1] - velocities[0]) * i / max(1, count - 1)))
            for i in range(count)]


def ending(notes: list[Placed], per_quarter: float = TICKS_PER_QUARTER) -> list[Placed]:
    """A last chord of D under the horns' and trumpets' D, held, after a
    timpani roll through the half bar before."""
    last, held = bar_tick(40, per_quarter), bar_tick(41.75, per_quarter)
    notes = [replace(n, end=held) if n.start >= last else n for n in notes]
    chord = [("Strings", p, 70) for p in ("D4", "F#4", "A4", "D5")] + \
            [("Cellos", p, 64) for p in ("D3", "A3")] + [("Bass", "D2", 70)]
    notes = spread_strings(notes + [Placed(last, held, note_number(p), track, v) for track, p, v in chord])
    stroke = round(1.28 * per_quarter)
    return notes + [Placed(last, last + stroke, note_number("D2"), "Timpani", 90)] + roll("D2", 39.5, 40, (30, 80),
                                                                                        per_quarter)


def decorations(notes: list[Placed], per_quarter: float = TICKS_PER_QUARTER) -> list[Placed]:
    """Each melody doubled, detuned; the strings' chords likewise; the
    melodies echoed on the other side, a dotted eighth later."""
    echo_ticks = round(0.75 * per_quarter)
    extra = []
    for note in notes:
        pan = note.pan if note.pan is not None else INSTRUMENTS[note.instrument].stereo
        other = OPPOSITE.get(pan, pan)
        if note.track in MELODIES:
            extra.append(replace(note, level_db=-4, detune=1, pan=other, optional=1))
            extra.append(replace(note, start=note.start + echo_ticks, end=note.end + echo_ticks, level_db=-13,
                                 pan=other, optional=2))
        elif note.track == "Bass":
            extra.append(replace(note, level_db=-2, detune=1, pan=other, optional=1))
        elif note.track == "Strings":
            extra.append(replace(note, level_db=-3, detune=2, pan=other, optional=3))
    return extra


def arranged(song: midi.Song, per_quarter: float = TICKS_PER_QUARTER) -> list[Placed]:
    """The notes, timed in ticks (or in steps, per_quarter a quarter)."""
    notes = file_notes(song, per_quarter)
    notes = [replace(n, pitch=n.pitch + TRANSPOSE[n.track]) if n.track in TRANSPOSE else n for n in notes]
    notes = spread_strings(notes)
    notes += roll("A1", 24.5, 25, (25, 70), per_quarter)
    notes = ending(notes, per_quarter)
    return notes + decorations(notes, per_quarter)


@dataclass
class Channel:
    notes: list[Placed]

    def busy(self) -> list[tuple[int, int]]:
        """From each note's start to the end of its release, or the next
        note's start."""
        notes = sorted(self.notes, key=lambda n: n.start)
        return [(n.start, min(n.release_end(), following.start) if following else n.release_end())
                for n, following in zip(notes, notes[1:] + [None])]

    def free_for(self, note: Placed) -> bool:
        """Free from the note's start to the end of its release, cutting no
        other note's release short."""
        return all(end <= note.start or start >= note.release_end() for start, end in self.busy())

    def last_before(self, tick: int) -> Placed | None:
        before = [n for n in self.notes if n.start < tick]
        return max(before, key=lambda n: n.start) if before else None


def allocate(notes: list[Placed]) -> tuple[list[Channel], int, int]:
    """The notes on channels; how many releases were cut short, and how many
    decorations found no channel."""
    channels = [Channel([]) for _ in range(CHANNELS)]
    cut = 0
    priority = {name: p for name, (_, _, _, p) in TRACKS.items()}
    for note in sorted((n for n in notes if not n.optional),
                       key=lambda n: (n.start, -priority[n.track], -n.pitch)):
        free = [c for c in channels if all(n.end <= note.start for n in c.notes)]
        assert free, f"no channel for a note at tick {note.start}"
        released = [c for c in free if all(n.release_end() <= note.start for n in c.notes)]
        legato = [c for c in free if c.notes and c.notes[-1].track == note.track
                  and note.start - c.notes[-1].end <= TICKS_PER_QUARTER / 2] if note.track in LEGATO else []
        if legato:
            channel = legato[0]
            cut += 1
        elif released:
            same = [c for c in released if c.notes and c.notes[-1].track == note.track]
            channel = same[0] if same else min(released, key=lambda c: c.notes[-1].release_end() if c.notes else -1)
        else:
            same = [c for c in free if c.notes[-1].track == note.track]
            channel = min(same or free, key=lambda c: c.notes[-1].end)
            cut += 1
        channel.notes.append(note)
    dropped = 0
    for note in sorted((n for n in notes if n.optional), key=lambda n: (n.optional, n.start)):
        free = [c for c in channels if c.free_for(note)]
        if not free:
            dropped += 1
            continue
        same = [c for c in free if (last := c.last_before(note.start)) and last.track == note.track]
        channel = (same or free)[0]
        channel.notes.append(note)
        channel.notes.sort(key=lambda n: n.start)
    return [c for c in channels if c.notes], cut, dropped


def channel_events(notes: list[Placed], end: int) -> list[Event]:
    events: list[Event] = []
    time = 0
    instrument = pan = quieter = None
    detune = 0
    for note in sorted(notes, key=lambda n: n.start):
        if instrument is None:              # (a stream starts with one)
            events.append(("instrument", note.instrument))
            instrument, pan = note.instrument, INSTRUMENTS[note.instrument].stereo
        if note.start > time:
            events += timed("rest", note.start - time)
        if instrument != note.instrument:
            events.append(("instrument", note.instrument))
            instrument, pan = note.instrument, INSTRUMENTS[note.instrument].stereo
        wanted_pan = note.pan if note.pan is not None else INSTRUMENTS[note.instrument].stereo
        if pan != wanted_pan:
            events.append(("pan", wanted_pan))
            pan = wanted_pan
        if detune != note.detune:
            events.append(("detune", note.detune))
            detune = note.detune
        # The note, its volume changing as the dynamics do.
        tick, first = note.start, True
        while tick < note.end:
            q = note.quieter(tick)
            if q != quieter:
                events.append(("volume", q))
                quieter = q
            length = min(SEGMENT_TICKS, note.end - tick)
            while tick + length < note.end and note.quieter(tick + length) == q:
                length += 1
            events += timed("note", length, note.pitch) if first else timed("hold", length)
            first = False
            tick += length
        time = note.end
    if end > time:
        events += timed("rest", end - time)
    return events


def score(filepath: Path = MIDI_FILEPATH) -> tuple[Score, int, int]:
    notes = arranged(midi.read(filepath))
    channels, cut, dropped = allocate(notes)
    end = max(n.end for c in channels for n in c.notes) + TAIL_TICKS
    return Score([channel_events(c.notes, end) for c in channels]), cut, dropped


SCORE, RELEASES_CUT, DECORATIONS_DROPPED = score()


# For the sequencer (stratagem.sequencer): the same arrangement in steps,
# a twentieth of a quarter, its dynamics the conductor's.

STEPS_PER_QUARTER = 20
TICKS_PER_STEP = TICKS_PER_QUARTER / STEPS_PER_QUARTER
PHRASE_GAP = 4 * STEPS_PER_QUARTER      # a bar's rest ends a phrase
DECORATION_GAP = STEPS_PER_QUARTER      # and a beat's, a decoration's
QUIETER_QUANTUM = 4                     # amplitude steps


def sequencer_notes(filepath: Path = MIDI_FILEPATH) -> list[sequencer.Note]:
    notes = []
    for placed in arranged(midi.read(filepath), STEPS_PER_QUARTER):
        instrument, level_db, _, priority = TRACKS[placed.track]
        db = level_db + placed.level_db + 20 * math.log10(placed.velocity / 127)
        pan = placed.pan if placed.pan is not None else INSTRUMENTS[instrument].stereo
        notes.append(sequencer.Note(placed.start, placed.end, placed.pitch, placed.track, instrument,
                                    sequencer.quieter_for(db), pan, placed.detune, priority, placed.optional))
    return notes


def conductor_points() -> list[tuple[int, float]]:
    """The dynamics, as (step, amplitude steps quieter): never louder than
    full, with the headroom."""
    return [(bar_tick(bar, STEPS_PER_QUARTER), -(db - HEADROOM_DB) / DB_PER_STEP) for bar, db in DYNAMICS]


def sequencer_voices(filepath: Path = MIDI_FILEPATH) -> tuple[list[sequencer.Voice], int, int]:
    """The notes on channels, the piece's length in steps, and how many
    decorations found no channel. Levels are to the nearest 1.5dB (the
    strings' slow swells, written note by note, otherwise change every
    chord), and decorations are in phrases split at a beat's rest."""
    notes = [replace(n, quieter=round(n.quieter / QUIETER_QUANTUM) * QUIETER_QUANTUM)
             for n in sequencer_notes(filepath)]
    voices, dropped = sequencer.allocate(notes, TICKS_PER_STEP, PHRASE_GAP, DECORATION_GAP)
    return voices, max(n.end for n in notes) + round(TAIL_TICKS / TICKS_PER_STEP), dropped


def sequencer_piece(filepath: Path = MIDI_FILEPATH) -> sequencer.Piece:
    voices, end, _ = sequencer_voices(filepath)
    return sequencer.encode([sequencer.voice_events(v, end) for v in voices],
                            sequencer.conductor_events(conductor_points(), end), TICKS_PER_STEP)


def main() -> None:
    streams = SCORE.streams()
    print(f"{len(SCORE.voices)} channels, {SCORE.ticks()} ticks ({SCORE.ticks() / TICKS_PER_SECOND:.1f}s), "
          f"{sum(map(len, streams))} bytes; {RELEASES_CUT} releases cut short, "
          f"{DECORATIONS_DROPPED} decorations without a channel")
    for index, (voice, stream) in enumerate(zip(SCORE.voices, streams)):
        tracks = sorted({e[1] for e in voice if e[0] == "instrument"})
        print(f"  channel {index}: {len(stream)} bytes, {', '.join(tracks)}")


if __name__ == "__main__":
    main()
