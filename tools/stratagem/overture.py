"""The Stratagem Overture (art/music/Stratagem_Overture.mid) as a piece for
the sequencer (stratagem.sequencer), for the title screen, arranged for the
Music 5000 (art/music/style.md is the mood).

Each MIDI track becomes a part, an instrument of music5000's orchestra
with a level; a note's velocity makes it quieter or louder from there, to
the nearest 1.5dB (the strings' slow swells, written into their
velocities chord by chord, would otherwise break every pattern). Times
are in steps, a twentieth of a quarter, at 96 beats a minute: 1.5625
ticks a step.

The arrangement, beyond the file:

- Dynamics over the whole, the conductor's: a quiet opening that swells
  into bar 5, the woodwinds' B minor a little withdrawn, a swell into the
  tutti at bar 25, a bare coda, and a last chord that opens out and dies
  away.
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
  likewise, and the melody echoed, quieter, on the other side. Each goes
  in phrases split at a beat's rest, a whole phrase or none of it.

    uv run python -m stratagem.overture     # how it fits
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path

from stratagem import midi, sequencer
from stratagem.music5000 import DB_PER_STEP, INSTRUMENTS, note_number

MIDI_FILEPATH = Path(__file__).resolve().parents[2] / "art" / "music" / "Stratagem_Overture.mid"
TICKS_PER_SECOND = 50
BEATS_PER_MINUTE = 96
STEPS_PER_QUARTER = 20
TICKS_PER_STEP = TICKS_PER_SECOND * 60 / BEATS_PER_MINUTE / STEPS_PER_QUARTER    # 1.5625
STEPS_PER_BAR = 4 * STEPS_PER_QUARTER
TAIL_STEPS = 2 * STEPS_PER_BAR          # silence before it plays again
HEADROOM_DB = 4                         # below full, for the swells
PHRASE_GAP = STEPS_PER_BAR              # a bar's rest ends a phrase
DECORATION_GAP = STEPS_PER_QUARTER      # and a beat's, a decoration's
QUIETER_QUANTUM = 4                     # amplitude steps: 1.5dB

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

# Stereo positions: 8 all left, 11-15 five sixths to one sixth left, 0 all right.
STRING_SPREAD = (11, 13, 15)            # a chord's notes, low to high
OPPOSITE = {11: 15, 12: 14, 13: 13, 14: 12, 15: 11, 8: 0, 0: 8}

# Dynamics: (bar, dB) points, from bar 1; straight lines between.
DYNAMICS = [(1, -15), (4.5, -4), (5, -2), (9, 0), (12.5, 0), (13, -3), (23.5, -3), (25, 2),
            (33, 3), (36.5, 4), (37, -5), (39.5, -5), (40, -2), (41, 4), (42, -6), (43, -20)]


def bar_step(bar: float) -> int:
    """The step at which a bar (from 1) starts, or part way into it."""
    return round((bar - 1) * STEPS_PER_BAR)


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


def file_notes(song: midi.Song) -> list[Placed]:
    scale = STEPS_PER_QUARTER / song.division
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


def roll(pitch: str, from_bar: float, to_bar: float, velocities: tuple[int, int]) -> list[Placed]:
    """A timpani roll: strokes every eighth of a beat, louder as it goes."""
    start, end = bar_step(from_bar), bar_step(to_bar)
    stroke = STEPS_PER_QUARTER / 8
    count = int((end - start) / stroke)
    return [Placed(round(start + i * stroke), round(start + (i + 1) * stroke), note_number(pitch), "Timpani",
                   round(velocities[0] + (velocities[1] - velocities[0]) * i / max(1, count - 1)))
            for i in range(count)]


def ending(notes: list[Placed]) -> list[Placed]:
    """A last chord of D under the horns' and trumpets' D, held, after a
    timpani roll through the half bar before."""
    last, held = bar_step(40), bar_step(41.75)
    notes = [replace(n, end=held) if n.start >= last else n for n in notes]
    chord = [("Strings", p, 70) for p in ("D4", "F#4", "A4", "D5")] + \
            [("Cellos", p, 64) for p in ("D3", "A3")] + [("Bass", "D2", 70)]
    notes = spread_strings(notes + [Placed(last, held, note_number(p), track, v) for track, p, v in chord])
    stroke = round(1.28 * STEPS_PER_QUARTER)
    return notes + [Placed(last, last + stroke, note_number("D2"), "Timpani", 90)] + roll("D2", 39.5, 40, (30, 80))


def decorations(notes: list[Placed]) -> list[Placed]:
    """Each melody doubled, detuned; the strings' chords likewise; the
    melodies echoed on the other side, a dotted eighth later."""
    echo = round(0.75 * STEPS_PER_QUARTER)
    extra = []
    for note in notes:
        pan = note.pan if note.pan is not None else INSTRUMENTS[note.instrument].stereo
        other = OPPOSITE.get(pan, pan)
        if note.track in MELODIES:
            extra.append(replace(note, level_db=-4, detune=1, pan=other, optional=1))
            extra.append(replace(note, start=note.start + echo, end=note.end + echo, level_db=-13,
                                 pan=other, optional=2))
        elif note.track == "Bass":
            extra.append(replace(note, level_db=-2, detune=1, pan=other, optional=1))
        elif note.track == "Strings":
            extra.append(replace(note, level_db=-3, detune=2, pan=other, optional=3))
    return extra


def arranged(song: midi.Song) -> list[Placed]:
    notes = file_notes(song)
    notes = [replace(n, pitch=n.pitch + TRANSPOSE[n.track]) if n.track in TRANSPOSE else n for n in notes]
    notes = spread_strings(notes)
    notes += roll("A1", 24.5, 25, (25, 70))
    notes = ending(notes)
    return notes + decorations(notes)


def sequencer_notes(filepath: Path = MIDI_FILEPATH) -> list[sequencer.Note]:
    notes = []
    for placed in arranged(midi.read(filepath)):
        instrument, level_db, _, priority = TRACKS[placed.track]
        db = level_db + placed.level_db + 20 * math.log10(placed.velocity / 127)
        pan = placed.pan if placed.pan is not None else INSTRUMENTS[instrument].stereo
        notes.append(sequencer.Note(placed.start, placed.end, placed.pitch, placed.track, instrument,
                                    sequencer.quieter_for(db), pan, placed.detune, priority, placed.optional))
    return notes


def conductor_points() -> list[tuple[int, float]]:
    """The dynamics, as (step, amplitude steps quieter): never louder than
    full, with the headroom."""
    return [(bar_step(bar), -(db - HEADROOM_DB) / DB_PER_STEP) for bar, db in DYNAMICS]


def sequencer_voices(filepath: Path = MIDI_FILEPATH) -> tuple[list[sequencer.Voice], int, int]:
    """The notes on channels, the piece's length in steps, and how many
    decorations found no channel."""
    notes = [replace(n, quieter=round(n.quieter / QUIETER_QUANTUM) * QUIETER_QUANTUM)
             for n in sequencer_notes(filepath)]
    voices, dropped = sequencer.allocate(notes, TICKS_PER_STEP, PHRASE_GAP, DECORATION_GAP)
    return voices, max(n.end for n in notes) + TAIL_STEPS, dropped


def sequencer_piece(filepath: Path = MIDI_FILEPATH) -> sequencer.Piece:
    voices, end, _ = sequencer_voices(filepath)
    return sequencer.encode([sequencer.voice_events(v, end) for v in voices],
                            sequencer.conductor_events(conductor_points(), end), TICKS_PER_STEP)


def main() -> None:
    voices, end, dropped = sequencer_voices()
    piece = sequencer_piece()
    print(f"{len(piece.voices)} channels, {end} steps ({end * TICKS_PER_STEP / TICKS_PER_SECOND:.1f}s), "
          f"{piece.size()} bytes ({len(piece.patterns)} patterns); {dropped} decorations without a channel")
    for index, (voice, stream) in enumerate(zip(voices, piece.voices)):
        parts = sorted({n.part for n in voice.notes})
        print(f"  channel {index}: {len(stream)} bytes, {', '.join(parts)}")


if __name__ == "__main__":
    main()
