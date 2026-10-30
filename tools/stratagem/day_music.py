"""The game's music (docs/musical-direction.md): the five pieces of a
musical day (art/music/Stratagem_*.mid), arranged for the Music 5000 and
encoded for the sequencer (stratagem.sequencer), to be played now and
then by the game's musical director, each once, to its end.

An arrangement is data: each track a part (an instrument of the board's
orchestra, a level, a place in the stereo field, its articulation and
its decorations), and the conductor's dynamics over the piece's passages.

The files' timing is regularised first, so that what repeats in the music
repeats in the score:

- A grid of STEPS_PER_QUARTER (30), which holds eighths, triplets and
  quintuplets exactly, and a step stays a tick or more up to 100 beats a
  minute.
- Rolled chords (onsets in a part a few steps apart, one after another)
  are spaced ROLL_STEP apart.
- A note's silence before its part's next note, when there is one within
  a beat, is the part's articulation: so a note's slot is the time to the
  next, a musical length, and the silence folds into it as its gap.

    uv run python -m stratagem.day_music       # how they fit, and renders
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path

from stratagem import midi, sequencer
from stratagem.music5000 import CENTRE, DB_PER_STEP, INSTRUMENTS

MUSIC_DIRPATH = Path(__file__).resolve().parents[2] / "art" / "music"
TICKS_PER_SECOND = 50
STEPS_PER_QUARTER = 30
STEPS_PER_BAR = 4 * STEPS_PER_QUARTER
TAIL_STEPS = STEPS_PER_BAR          # for the last releases to die away
HEADROOM_DB = 4
PHRASE_GAP = STEPS_PER_BAR          # a bar's rest ends a phrase
DECORATION_GAP = STEPS_PER_QUARTER  # and a beat's, a decoration's
QUIETER_QUANTUM = 4                 # amplitude steps: 1.5dB
ROLL_SPREAD = 4                     # steps: onsets this close, one after another, are a roll...
ROLL_STEP = 3                       # ... and are spaced so

# Stereo: 8 all left, 11-15 five sixths to one sixth left, 0 all right.
LEFT, FAR_LEFT, HALF_LEFT, NEAR_LEFT, NEAR_RIGHT, RIGHT = 8, 11, 12, 14, 15, 0
OPPOSITE = {11: 15, 12: 14, 13: 13, 14: 12, 15: 11, 8: 0, 0: 8}


@dataclass(frozen=True)
class Echo:
    beats: float                    # later
    db: float                       # quieter
    transpose: int = 0              # semitones
    detune: int = 0


@dataclass(frozen=True)
class Part:
    """How a track is played, from a bar on (Arrangement.parts)."""
    instrument: str
    level_db: float = 0
    pan: int | None = None          # None: the instrument's
    priority: int = 1               # higher takes a channel first
    transpose: int = 0              # semitones
    articulation: int = 2           # steps of silence before the part's next note
    ensemble_db: float | None = None    # doubled, detuned, on the other side, so much quieter
    ensemble_detune: int = 1
    echoes: tuple[Echo, ...] = ()   # on the other side
    spread: tuple[int, ...] = ()    # a chord's notes, low to high, across the stereo field
    keep: int = 1                   # every so many of its onsets (thinning)
    nudges: tuple[float, ...] = ()  # beats, each onset in turn: off the clock
    octave_db: float | None = None  # doubled an octave up, so much quieter


@dataclass(frozen=True)
class Arrangement:
    name: str
    filename: str
    beats_per_minute: int
    parts: dict[str, Part | list[tuple[float, Part]]]     # a track's, or from each bar on
    dynamics: list[tuple[float, float]]     # (bar from 1, dB); straight lines between

    def part(self, track: str, step: int) -> Part:
        """The track's part at a step."""
        parts = self.parts[track]
        if isinstance(parts, Part):
            return parts
        return [part for bar, part in parts if bar_step(bar) <= step][-1]

    @property
    def ticks_per_step(self) -> float:
        return TICKS_PER_SECOND * 60 / self.beats_per_minute / STEPS_PER_QUARTER


@dataclass(frozen=True)
class Placed:
    start: int
    end: int
    pitch: int
    part: str
    db: float
    pan: int
    detune: int = 0
    optional: int = 0


def bar_step(bar: float) -> int:
    return round((bar - 1) * STEPS_PER_BAR)


def regular_onsets(starts: list[float]) -> dict[float, int]:
    """A part's onsets, exact, to steps: rounded, and each roll's spaced
    ROLL_STEP apart from its first."""
    onsets = sorted(set(starts))
    steps: dict[float, int] = {}
    index = 0
    while index < len(onsets):
        roll = [onsets[index]]
        while index + len(roll) < len(onsets) and onsets[index + len(roll)] - roll[-1] <= ROLL_SPREAD:
            roll.append(onsets[index + len(roll)])
        first = round(roll[0])
        for place, onset in enumerate(roll):
            steps[onset] = first + place * ROLL_STEP if len(roll) > 1 else first
        index += len(roll)
    return steps


def articulated(notes: list[Placed], gap: int) -> list[Placed]:
    """A part's notes, each ending gap steps before the part's next onset
    when that comes within a beat of its end (or before it: no overlaps)."""
    onsets = sorted({n.start for n in notes})
    out = []
    for note in notes:
        following = next((o for o in onsets if o > note.start), None)
        if following is not None and following - note.end <= STEPS_PER_QUARTER:
            note = replace(note, end=max(note.start + 1, following - gap))
        out.append(note)
    return out


def spread(notes: list[Placed], places: tuple[int, ...]) -> list[Placed]:
    by_start: dict[int, list[int]] = {}
    for index, note in enumerate(notes):
        by_start.setdefault(note.start, []).append(index)
    notes = list(notes)
    for chord in by_start.values():
        for place, index in enumerate(sorted(chord, key=lambda i: notes[i].pitch)):
            notes[index] = replace(notes[index], pan=places[min(place, len(places) - 1)])
    return notes


def arranged(arrangement: Arrangement) -> list[Placed]:
    song = midi.read(MUSIC_DIRPATH / arrangement.filename)
    scale = STEPS_PER_QUARTER / song.division
    notes: list[Placed] = []
    for track in song.tracks:
        if not track.notes:
            continue
        onsets = regular_onsets([n.start * scale for n in track.notes])
        groups = sorted(set(onsets.values()))
        placed = []
        for n in track.notes:
            start = onsets[n.start * scale]
            part = arrangement.part(track.name, start)
            group = groups.index(start)
            if group % part.keep:
                continue
            if part.nudges:
                start = max(0, start + round(part.nudges[group % len(part.nudges)] * STEPS_PER_QUARTER))
            end = max(start + 1, start + round(n.length * scale))
            pan = part.pan if part.pan is not None else INSTRUMENTS[part.instrument].stereo
            placed.append(Placed(start, end, n.pitch + part.transpose, track.name,
                                 part.level_db + 20 * math.log10(n.velocity / 127), pan))
        placed.sort(key=lambda p: (p.start, p.pitch))
        by_part: dict[Part, list[Placed]] = {}
        for p in placed:
            by_part.setdefault(arrangement.part(track.name, p.start), []).append(p)
        for part, some in by_part.items():
            some = articulated(some, part.articulation)
            notes += spread(some, part.spread) if part.spread else some
    return notes + decorations(arrangement, notes)


def decorations(arrangement: Arrangement, notes: list[Placed]) -> list[Placed]:
    """Ensembles and echoes, on the other side, placed only where a channel
    is free: a whole phrase or none of it."""
    extra = []
    for note in notes:
        part = arrangement.part(note.part, note.start)
        other = OPPOSITE.get(note.pan, note.pan)
        if part.octave_db is not None:
            extra.append(replace(note, pitch=note.pitch + 12, db=note.db + part.octave_db, optional=1))
        if part.ensemble_db is not None:
            extra.append(replace(note, db=note.db + part.ensemble_db, detune=part.ensemble_detune, pan=other,
                                 optional=1))
        for order, echo in enumerate(part.echoes):
            later = round(echo.beats * STEPS_PER_QUARTER)
            extra.append(replace(note, start=note.start + later, end=note.end + later, db=note.db + echo.db,
                                 pitch=note.pitch + echo.transpose, detune=echo.detune, pan=other,
                                 optional=2 + order))
    return extra


def sequencer_notes(arrangement: Arrangement) -> list[sequencer.Note]:
    notes = []
    for p in arranged(arrangement):
        part = arrangement.part(p.part, p.start)
        quieter = round(sequencer.quieter_for(p.db) / QUIETER_QUANTUM) * QUIETER_QUANTUM
        notes.append(sequencer.Note(p.start, p.end, p.pitch, p.part, part.instrument, quieter, p.pan, p.detune,
                                    part.priority, p.optional))
    return notes


def conductor_points(arrangement: Arrangement) -> list[tuple[int, float]]:
    return [(bar_step(bar), -(db - HEADROOM_DB) / DB_PER_STEP) for bar, db in arrangement.dynamics]


def voices(arrangement: Arrangement) -> tuple[list[sequencer.Voice], int, int]:
    """The notes on channels, the piece's length in steps, and how many
    decorations found no channel."""
    notes = sequencer_notes(arrangement)
    placed, dropped = sequencer.allocate(notes, arrangement.ticks_per_step, PHRASE_GAP, DECORATION_GAP)
    return placed, max(n.end for n in notes) + TAIL_STEPS, dropped


def piece(arrangement: Arrangement) -> sequencer.Piece:
    placed, end, _ = voices(arrangement)
    return sequencer.encode([sequencer.voice_events(v, end) for v in placed],
                            sequencer.conductor_events(conductor_points(arrangement), end),
                            arrangement.ticks_per_step, ending=sequencer.END)


# The pieces (docs/musical-direction.md has the brief, and the notes these
# follow). Each fades in from nothing and dissolves at its end: it arrives
# unannounced, out of silence. Their peaks rank below the overture's:
# Daylight and Underground highest, then Dawn, Dusk and Night. On the
# surface no echo (open air has none): space is width and level; a solo is
# one player, never doubled; near is centred, with vibrato, far is to one
# side, quieter, still. Underground is another world: drones with no
# beginning, glass in detuned pairs that beat, and echoes, one answering a
# fifth above.

STRINGS_SPREAD = (FAR_LEFT, CENTRE, NEAR_RIGHT)
WIDE_SPREAD = (LEFT, CENTRE, RIGHT)
OFF_THE_CLOCK = (0, 1, -0.5, 1.5, 0.5, -1, 2, 0)    # beats, onset by onset

DAWN = Arrangement("dawn", "Stratagem_Dawn_Awakening.mid", 80, {
    # First Light thin, filling out into Sunrise; the violins rising in
    # slowly; the horn arriving from far to near; the end receding.
    "Solo flute": Part("flute", 2, priority=3),
    "Oboe": Part("oboe", 1, priority=3),
    "Clarinet": Part("clarinet", -1, priority=2),
    "French horn": [(1, Part("far_horn", -4, pan=FAR_LEFT, priority=3)),
                    (21, Part("horn", 1, priority=3))],
    "Violins": [(1, Part("still_strings", -4, priority=2, ensemble_db=-4)),
                (18, Part("violin", -2, priority=2, ensemble_db=-4))],
    "Violas": [(1, Part("strings", -6, spread=STRINGS_SPREAD)), (28, Part("strings", -9, spread=STRINGS_SPREAD))],
    "Cellos": [(1, Part("cello", -3)), (28, Part("cello", -6))],
    "Contrabass": [(1, Part("bass", 2, priority=2)), (28, Part("bass", -1, priority=2))],
    "Harp": [(1, Part("harp", -4, pan=NEAR_LEFT, keep=2)), (11, Part("harp", -3, pan=NEAR_LEFT))],
}, [(1, -26), (3.5, -12), (10, -9), (11, -7), (18, -4), (24, -1), (27, -1), (29, -5), (30, -10), (31, -24)])

DAYLIGHT = Arrangement("daylight", "Stratagem_Daylight_Open_World.mid", 96, {
    # Room: the harp halved in the Journey, the horn's motif alone in its
    # register; the strings wide rather than loud; the trumpets joining
    # under the horn; a broad diminuendo, towards the horizon.
    "Horn": Part("horn", 2, priority=3),
    "Trumpet": Part("trumpet", -4, priority=3),
    "Flute": Part("flute", 1, priority=3),
    "Oboe": Part("oboe", 0, priority=3),
    "Clarinet": Part("clarinet", -1, priority=2),
    "Strings": Part("strings", -5, spread=WIDE_SPREAD, ensemble_db=-4),
    "Violas": Part("strings", -7, pan=HALF_LEFT),
    "Cellos": Part("cello", -2),
    "Bass": Part("bass", 2, priority=2),
    "Harp": [(1, Part("harp", -4, pan=NEAR_LEFT)), (10, Part("harp", -5, pan=NEAR_LEFT, keep=2)),
             (26, Part("harp", -4, pan=NEAR_LEFT))],
    "Timpani": Part("timpani", 3, priority=2, transpose=-12),
}, [(1, -24), (4, -6), (9, -5), (10, -3), (24, -2), (26, 0), (31, 1), (33, 1), (35.5, -4), (36.5, -9),
    (37, -24)])

DUSK = Arrangement("dusk", "Stratagem_Dusk_Reflection.mid", 80, {
    # The colour drains at 0:30: the strings' doubling and vibrato go, and
    # the celesta and bassoon sound exposed; the horn's Homeward warm and
    # central again; the ending left open (no tonic added).
    "Oboe": Part("oboe", 2, priority=3),
    "Solo horn": Part("horn", 1, priority=3, pan=CENTRE),
    "Flute": Part("flute", -1, priority=2),
    "Clarinet": Part("clarinet", -1, priority=2),
    "Bassoon": Part("bassoon", 0, priority=2, articulation=4),
    "Celesta": Part("celesta", -2, priority=2, pan=HALF_LEFT, transpose=12),
    "Violins": [(1, Part("violin", -3, priority=2, ensemble_db=-4)), (21, Part("violin", -4, priority=2))],
    "Violas": [(1, Part("strings", -6, spread=STRINGS_SPREAD, ensemble_db=-5)),
               (11, Part("still_strings", -8, spread=STRINGS_SPREAD)),
               (21, Part("strings", -7, spread=STRINGS_SPREAD))],
    "Cellos": [(1, Part("cello", -3)), (11, Part("still_cello", -5)), (21, Part("cello", -4))],
    "Contrabass": Part("bass", 0, priority=2),
    "Harp": Part("harp", -3, pan=NEAR_LEFT),
}, [(1, -22), (3, -2), (10, 0), (11, -4), (20, -5), (21, -2), (27, -1), (29, -5), (30, -9), (31, -22)])

NIGHT = Arrangement("night", "Stratagem_Night_Solitude.mid", 72, {
    # Wide, dry and far: the horn far to the left, the celesta high on the
    # right, the strings low in the middle, nothing with vibrato, nothing
    # echoed, and the isolated sounds off the clock. At the turn to D major
    # (bar 24) the one warmth: the horn near, with vibrato, the strings
    # doubled once, the conductor up a little. The timpani a heartbeat.
    "Solo horn": [(1, Part("far_horn", -3, pan=LEFT, priority=3)), (24, Part("horn", 0, priority=3))],
    "Flute": Part("flute", -2, priority=2),
    "Clarinet": Part("clarinet", -2, priority=2, pan=NEAR_LEFT),
    "Bassoon": Part("bassoon", -1, priority=2, articulation=4),
    "Oboe": Part("still_oboe", -2, priority=2, pan=NEAR_RIGHT),
    "Celesta": Part("celesta", -2, priority=2, pan=RIGHT, transpose=12, nudges=OFF_THE_CLOCK),
    "String ensemble": [(1, Part("still_strings", -5, spread=STRINGS_SPREAD)),
                        (24, Part("strings", -4, spread=STRINGS_SPREAD, ensemble_db=-5))],
    "Cellos": [(1, Part("still_cello", -2, pan=CENTRE)), (24, Part("cello", -2, pan=CENTRE))],
    "Contrabass": Part("bass", 2, priority=2, pan=CENTRE),
    "Harp": Part("harp", -4, pan=FAR_LEFT, nudges=OFF_THE_CLOCK[3:] + OFF_THE_CLOCK[:3]),
    "Timpani": Part("timpani", -2, priority=2, transpose=-12, pan=CENTRE),
}, [(1, -20), (3, -2), (10, 0), (11, -3), (21, -3), (23, -1), (24, 2), (26, 1), (27, -3),
    (28, -20)])

UNDERGROUND = Arrangement("underground", "Stratagem_Underground_Deep_Time.mid", 72, {
    # Another world. Drones with no beginning, stone-still; glass, pure
    # tones in a detuned pair an octave up, beating slowly, where the other
    # pieces have strings; the cave answering, late, quieter, on the far
    # side, the celesta's second answer a fifth above; the bass doubled an
    # octave up, to be heard. The Hidden World the one great swell: horns
    # and trombones in the middle, the strings wide, the echoes giving way;
    # then settling on a bare D.
    "Low strings": [(1, Part("drone", 0, pan=CENTRE)), (19, Part("cello", 0, pan=CENTRE))],
    "Contrabass": Part("bass", 3, priority=2, pan=CENTRE, octave_db=-9),
    "String ensemble": [(1, Part("glass", -2, transpose=12, ensemble_db=-1, ensemble_detune=2)),
                        (19, Part("strings", -3, spread=WIDE_SPREAD, ensemble_db=-4))],
    "French horn": Part("horn", 2, priority=3, pan=CENTRE, ensemble_db=-4),
    "Bassoon": Part("bassoon", 1, priority=3, articulation=4, echoes=(Echo(2, -12),)),
    "Clarinet": [(1, Part("clarinet", -1, priority=2, echoes=(Echo(2, -10), Echo(4, -18)))),
                 (19, Part("clarinet", -1, priority=2))],
    "Flute": [(1, Part("flute", -2, priority=2, echoes=(Echo(2, -10),))), (19, Part("flute", -1, priority=2))],
    "Harp": [(1, Part("harp", -3, pan=NEAR_LEFT, nudges=OFF_THE_CLOCK, echoes=(Echo(1.5, -10),))),
             (19, Part("harp", -3, pan=NEAR_LEFT))],
    "Celesta": Part("celesta", 0, priority=2, pan=NEAR_RIGHT, transpose=12, nudges=OFF_THE_CLOCK[5:] + OFF_THE_CLOCK[:5],
                    echoes=(Echo(2, -8), Echo(4, -14, transpose=7))),
    "Trombone": Part("trombone", 0, priority=3, pan=CENTRE),
}, [(1, -28), (4, -12), (9, -10), (10, -10), (18, -10), (19, -6), (23, 0), (25, 1), (26, -3), (27, -8),
    (28, -28)])

ARRANGEMENTS = [DAWN, DAYLIGHT, DUSK, NIGHT, UNDERGROUND]


def pieces() -> dict[str, sequencer.Piece]:
    return {a.name: piece(a) for a in ARRANGEMENTS}


def generate(generated_dirpath: Path) -> None:
    """m5_day.asm: the five pieces, in the player's format, for MBANK."""
    lines = ["\\ Generated by stratagem.day_music: do not edit."]
    for name, encoded in pieces().items():
        lines += sequencer.piece_source(name, encoded)
    (generated_dirpath / "m5_day.asm").write_text("\n".join(lines) + "\n")


def main() -> None:
    import sys
    from stratagem.build import PROJECT_DIRPATH
    from stratagem.m5_synth import render, write_wav
    out_dirpath = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_DIRPATH / "build" / "features"
    import numpy as np
    from stratagem import overture
    total, renders = 0, {}
    for arrangement in ARRANGEMENTS:
        placed, end, dropped = voices(arrangement)
        encoded = piece(arrangement)
        total += encoded.size()
        seconds = end * arrangement.ticks_per_step / TICKS_PER_SECOND
        print(f"{arrangement.name:12} {len(encoded.voices):2} channels, {seconds:5.1f}s, {encoded.size():5} bytes "
              f"({len(encoded.patterns)} patterns), {dropped} decorations without a channel")
        player = sequencer.SequencePlayer(encoded)
        renders[arrangement.name] = render(player, player.ticks())
    player = sequencer.SequencePlayer(overture.sequencer_piece())
    renders["overture"] = render(player, player.ticks())
    # All at one gain, the loudest's peak, so they keep their levels; and
    # each one's loudest three seconds against the overture's.
    peak = max(np.abs(audio).max() for audio in renders.values())
    loudest = {}
    for name, audio in renders.items():
        power = np.concatenate([[0], np.cumsum(audio.mean(axis=1) ** 2)])
        window = 3 * len(audio) // max(1, round(len(audio) / 46875))
        loudest[name] = 10 * math.log10(max((power[window:] - power[:-window]) / window))
    for name, audio in renders.items():
        write_wav(audio, out_dirpath / f"{name}-synth.wav", peak)
        print(f"  {name:12} loudest 3s {loudest[name] - loudest['overture']:+5.1f}dB from the overture's")
    print(f"all five: {total} bytes; renders in {out_dirpath}, at one gain")


if __name__ == "__main__":
    main()
