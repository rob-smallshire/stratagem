"""The musical day's second scores: five pieces composed for the board's
orchestra (docs/musical-direction.md), written here as phrases and
saved as MIDI files (art/music/Stratagem_*.mid) for stratagem.day_music
to arrange, as it arranges the overture's.

The first five (art/music, from the brief) were too alike: each in 4/4,
between 72 and 96 beats a minute, each 92 seconds, and all scored for
the same full orchestra. These differ in metre, key, tempo, length and
texture, and share the overture's motto, its opening rise (a fourth,
then two steps: A D E F# in D), each in its own way:

- Dawn, 6/8, G Lydian: birdsong (flute, oboe, clarinet, calling across
  the stereo field) over rippling harp; at sunrise the motto, slow, on
  the horn; then high, on the violins.
- Daylight, 4/4 and brisk, A major: plucked strings and bass, a celesta
  ostinato, and a striding tune begun by the motto in quicker notes; a
  shift to F, broad, on the strings, and back.
- Dusk, 3/4, E flat: a cello's song, the motto backwards (falling), over
  a harp's lilting accompaniment; the clarinet's song in C minor; ending
  open, on the fourth chord.
- Night, 5/4 and slow, B Dorian: a lone low flute, the motto in minor;
  stars on the celesta, off the clock; a far horn answering, in canon.
- Underground, 7/8, C Phrygian: a plucked ostinato, drips that echo,
  drones and glass; the motto bent (a minor second) on the trombone; in
  the Hidden World the motto rising from A flat into C major.

A phrase is a string of notes: a pitch (c4, f#5, bb3; chords joined by
+; r a rest), then optionally /length in quarters (2, 1.5, 1/3), kept
until changed, and > for an accent. Bar lines | are only for reading.

    uv run python -m stratagem.day_scores     # writes the MIDI files
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

import mido

MUSIC_DIRPATH = Path(__file__).resolve().parents[2] / "art" / "music"
TICKS_PER_QUARTER = 480
VELOCITY = 96
ACCENT = 24
PITCH_CLASSES = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
TOKEN = re.compile(r"(?P<pitches>r|[a-g][#b]?-?\d(?:\+[a-g][#b]?-?\d)*)(?:/(?P<length>[\d.]+(?:/\d+)?))?"
                   r"(?P<accent>>?)$")


def pitch(name: str) -> int:
    """A note's MIDI number: c4 is 60."""
    number = PITCH_CLASSES[name[0]] + 12 * (int(name[1:].lstrip("#b")) + 1)
    return number + name[1:2].count("#") - name[1:2].count("b")


@dataclass(frozen=True)
class Note:
    start: Fraction                 # quarters
    length: Fraction
    pitch: int
    velocity: int


def phrase(text: str, start: Fraction | float = 0, velocity: int = VELOCITY) -> tuple[list[Note], Fraction]:
    """A phrase's notes from a start, and its end."""
    at, length, notes = Fraction(start), Fraction(1), []
    for token in text.split():
        if token == "|":
            continue
        match = TOKEN.match(token)
        if not match:
            raise ValueError(f"not a note: {token}")
        if match["length"]:
            length = Fraction(match["length"]) if "/" in match["length"] else Fraction(float(match["length"]))
        if match["pitches"] != "r":
            louder = ACCENT if match["accent"] else 0
            notes += [Note(at, length, pitch(name), min(127, velocity + louder))
                      for name in match["pitches"].split("+")]
        at += length
    return notes, at


@dataclass
class Score:
    name: str
    filename: str
    beats_per_minute: int
    beats_per_bar: Fraction         # quarters
    signature: tuple[int, int]
    parts: dict[str, list[Note]] = field(default_factory=dict)

    def at(self, bar: float, beat: float = 0) -> Fraction:
        """A time in quarters, from bar 1 and its beat 0."""
        return (Fraction(bar) - 1) * self.beats_per_bar + Fraction(beat)

    def add(self, part: str, text: str, bar: float, beat: float = 0, velocity: int = VELOCITY) -> Fraction:
        """The phrase into the part at a bar; the bar (fractional) where it ends."""
        notes, end = phrase(text, self.at(bar, beat), velocity)
        self.parts.setdefault(part, []).extend(notes)
        return end / self.beats_per_bar + 1

    def add_harmony(self, part: str, text: str, bar: float, chords: list[str], velocity: int = VELOCITY) -> None:
        """A harmony under the phrase, from its chords, a bar each, into the part."""
        notes, _ = phrase(text, self.at(bar), velocity)
        self.parts.setdefault(part, []).extend(chord_below(notes, chords, self.at(bar), self.beats_per_bar))

    def midi(self) -> mido.MidiFile:
        song = mido.MidiFile(type=1, ticks_per_beat=TICKS_PER_QUARTER)
        conductor = mido.MidiTrack([
            mido.MetaMessage("track_name", name=self.name, time=0),
            mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(self.beats_per_minute), time=0),
            mido.MetaMessage("time_signature", numerator=self.signature[0], denominator=self.signature[1], time=0),
        ])
        song.tracks.append(conductor)
        for channel, (name, notes) in enumerate(self.parts.items()):
            events = []
            for note in notes:
                on, off = (round(t * TICKS_PER_QUARTER) for t in (note.start, note.start + note.length))
                events += [(off, 0, note.pitch, 0), (on, 1, note.pitch, note.velocity)]
            track = mido.MidiTrack([mido.MetaMessage("track_name", name=name, time=0)])
            last = 0
            for tick, on, number, velocity in sorted(events):
                track.append(mido.Message("note_on" if on else "note_off", channel=channel % 16, note=number,
                                          velocity=velocity if on else 64, time=tick - last))
                last = tick
            song.tracks.append(track)
        return song

    def write(self, dirpath: Path = MUSIC_DIRPATH) -> Path:
        filepath = dirpath / self.filename
        self.midi().save(filepath)
        return filepath


def bars(chords: list[tuple[str, int]]) -> list[tuple[int, str]]:
    """(chord, bars) in turn, from bar 1, as (bar, chord) for each bar."""
    out, bar = [], 1
    for chord, count in chords:
        out += [(bar + i, chord) for i in range(count)]
        bar += count
    return out


# Dawn: 6/8 (a bar three quarters), the dotted quarter at 52.

DAWN_RIPPLES = {"G": "g3 d4 g4 b4 g4 d4", "A/G": "g3 e4 a4 c#5 a4 e4", "Em7": "e3 b3 d4 g4 d4 b3",
                "C": "c3 g3 b3 e4 b3 g3", "D": "d3 a3 d4 f#4 a4 f#4"}
DAWN_ROOTS = {"G": "g2", "A/G": "g2", "Em7": "e2", "C": "c2", "D": "d2"}
DAWN_CHORDS = {"G": "d4+g4+b4", "A/G": "e4+a4+c#5", "Em7": "d4+g4+b4", "C": "e4+g4+b4", "D": "d4+f#4+a4"}
DAWN_CALLS = {
    "flute": {"rise": "d6/1/6 b5 d6 b5 g6/2/3 e6/1/3 d6/1", "lydian": "c#6/1/6 d6 c#6 d6 e6/1 d6/1/2"},
    "oboe": {"fall": "a5/1/2 g5 e5/1 d5", "steps": "b5/1/3 a5 g5 e5/1.5"},
    "clarinet": {"run": "d5/1/3 e5 f#5 g5/1.5", "trill": "g5/1/6 a5 g5 a5 b5/1"},
}
DAWN_BIRDS = [
    ("flute", "rise", 2, 0), ("oboe", "fall", 4, 0.5), ("flute", "rise", 5, 1.5), ("clarinet", "run", 6, 1.5),
    ("oboe", "steps", 7, 1.5), ("flute", "lydian", 8, 0), ("flute", "rise", 9, 1.5), ("oboe", "fall", 10, 1.5),
    ("clarinet", "trill", 11, 1.5), ("flute", "rise", 12, 0), ("clarinet", "trill", 20, 1.5),
    ("flute", "rise", 24, 1.5), ("oboe", "steps", 25, 1.5), ("flute", "lydian", 26, 0), ("clarinet", "run", 26, 1.5),
    ("flute", "lydian", 27, 1.5), ("oboe", "fall", 28, 0), ("clarinet", "trill", 28, 1.5), ("flute", "rise", 29, 1.5),
    ("oboe", "steps", 30, 1.5), ("flute", "rise", 31, 0),
]


def dawn() -> Score:
    score = Score("Dawn Chorus", "Stratagem_Dawn_Chorus.mid", 78, Fraction(3), (6, 8))
    harmony = bars([("G", 4), ("G", 2), ("A/G", 2), ("Em7", 2), ("C", 2),
                    ("G", 2), ("A/G", 2), ("Em7", 2), ("C", 2), ("D", 2), ("G", 2), ("G", 2), ("A/G", 2),
                    ("G", 4)])
    # The ground: a low G, its fifth joining; the roots changing, two bars
    # each, from bar 5; the double bass under them from sunrise (bar 13).
    score.add("Cellos", "g2/6 g2+d3/6", 1)
    for bar, chord in harmony[4:28:2]:
        score.add("Cellos", f"{DAWN_ROOTS[chord]}/6", bar)
        score.add("Strings", f"{DAWN_CHORDS[chord]}/6", bar)
        if bar >= 13:
            score.add("Bass", f"{DAWN_ROOTS[chord][0]}{DAWN_ROOTS[chord][1:-1]}1/6", bar)
    score.add("Cellos", "g2+d3/12", 29)
    for bar, chord in harmony[4:28]:
        score.add("Harp", " ".join(f"{n}/1/2" for n in DAWN_RIPPLES[chord].split()), bar)
    # Sunrise: the motto on the horn, slowly; then on the violins, high.
    score.add("Horn", "d4/3 | g4/1.5 a4 | b4/3 | c#5/1.5 b4 | g4 b4 | e5/3 | d5/1.5 b4 | g4/3 | a4/3 | "
                      "f#4/1.5 a4 | g4/6", 13)
    score.add("Violins", "d5/3 | g5/1.5 a5 | b5/6 | a5/1.5 g5 | g5/3", 25)
    for player, call, bar, beat in DAWN_BIRDS:
        score.add(player.capitalize(), DAWN_CALLS[player][call], bar, beat)
    return score


# Daylight: 4/4, the quarter at 98.

DAYLIGHT_BASS = {"A": ("a1", "e2", "a2"), "D": ("d2", "a2", "d3"), "F#m": ("f#1", "c#2", "f#2"),
                 "G": ("g1", "d2", "g2"), "E": ("e1", "b1", "e2"), "F": ("f1", "c2", "f2"),
                 "Bb": ("bb1", "f2", "bb2"), "Dm": ("d2", "a2", "d3"), "C": ("c2", "g2", "c3"),
                 "E7": ("e1", "b1", "e2")}
DAYLIGHT_CHORDS = {"A": "c#4+e4+a4", "D": "d4+f#4+a4", "F#m": "c#4+f#4+a4", "G": "d4+g4+b4", "E": "b3+e4+g#4",
                   "F": "c4+f4+a4", "Bb": "d4+f4+bb4", "Dm": "d4+f4+a4", "C": "c4+e4+g4", "E7": "b3+d4+g#4"}
DAYLIGHT_TUNE = ("e4/1 a4/1/2 b4 c#5/1.5 b4/1/2 | a4 b4 c#5 e5 f#5/1 e5 | c#5 a4/1/2 b4 c#5/1 e5 | "
                 "d5 g4 b4/2 | e4/1 a4/1/2 b4 c#5/1.5 e5/1/2 | f#5/1 e5/1/2 d5 a4/1 b4 | "
                 "a4/1/2 b4 c#5 d5 e5/1 g#4 | a4/3 r/1")
DAYLIGHT_TUNE_HARMONY = ["A", "D", "F#m", "G", "A", "D", "E", "A"]
DAYLIGHT_SKY = "c5/2 f5/1 g5 | a5/4 | bb5/2 a5/1 f5 | d5/4 | f5/2 e5/1 d5 | a5/4 | g5/2 e5/1 c5 | b4/2 d5/1 g#5"
DAYLIGHT_SKY_HARMONY = ["F", "F", "Bb", "Bb", "Dm", "Dm", "C", "E7"]
DAYLIGHT_COUNTER = "e5/4 | f#5 | e5/2 c#5 | d5/4 | e5 | f#5/2 a5 | g#5/4 | a5"
# The celesta's ostinato, bent to each chord: the sky's (in F), the tune's.
DAYLIGHT_OSTINATO = {"F": "c6 f5 g5 f5 a5 f5 g5 f5", "Bb": "d6 f5 g5 f5 bb5 f5 g5 f5",
                     "Dm": "d6 f5 a5 f5 c6 f5 a5 f5", "C": "c6 e5 g5 e5 d6 e5 g5 e5",
                     "A": "a5 e5 b5 e5 c#6 e5 b5 e5", "D": "a5 f#5 b5 f#5 d6 f#5 b5 f#5",
                     "F#m": "a5 e5 b5 e5 c#6 e5 b5 e5", "G": "a5 d5 b5 d5 d6 d5 b5 d5",
                     "E": "g#5 e5 b5 e5 b5 e5 b5 e5"}


def chord_below(notes: list[Note], chords: list[str], start: Fraction, beats_per_bar: Fraction) -> list[Note]:
    """A harmony under a tune: under each note the highest of its bar's
    chord's notes at least a minor third below."""
    out = []
    for note in notes:
        chord = chords[int((note.start - start) / beats_per_bar)]
        classes = {pitch(name) % 12 for name in DAYLIGHT_CHORDS[chord].split("+")}
        under = next(p for p in range(note.pitch - 3, 0, -1) if p % 12 in classes)
        out.append(Note(note.start, note.length, under, note.velocity))
    return out


def daylight() -> Score:
    score = Score("The Open Road", "Stratagem_Daylight_Open_Road.mid", 98, Fraction(4), (4, 4))
    harmony = (["A", "A"] + DAYLIGHT_TUNE_HARMONY * 2 + DAYLIGHT_SKY_HARMONY + DAYLIGHT_TUNE_HARMONY
               + ["A", "A"])
    for bar, chord in enumerate(harmony[:-1], 1):
        root, fifth, octave = DAYLIGHT_BASS[chord]
        score.add("Bass", f"{root}/1.5 {fifth}/1/2 {octave}/1 {fifth}", bar)
        score.add("Pizzicato", " ".join([f"r/1/2 {DAYLIGHT_CHORDS[chord]}"] * 4), bar)
        if 3 <= bar <= 34 and chord != "E7":
            score.add("Celesta", " ".join(f"{n}/1/2" for n in DAYLIGHT_OSTINATO[chord].split()), bar)
        if 11 <= bar <= 34:
            score.add("Strings", f"{DAYLIGHT_CHORDS[chord]}/4", bar)
    score.add("Bass", "a1/1", 36)
    score.add("Pizzicato", "c#4+e4+a4/1", 36)
    # The tune: the horn's; the trumpet's, the horn a third below; then the
    # sky, broad, in F; then everyone's.
    score.add("Horn", DAYLIGHT_TUNE, 3)
    score.add("Trumpet", DAYLIGHT_TUNE, 11)
    score.add_harmony("Horn", DAYLIGHT_TUNE, 11, DAYLIGHT_TUNE_HARMONY)
    score.add("Oboe", DAYLIGHT_COUNTER, 11)
    score.add("Violins", DAYLIGHT_SKY, 19)
    score.add("Horn", "f4/8 | f4/8 | f4/4 a4 | g4 g#4", 19)
    score.add("Timpani", "e3/1/3 e3 e3 e3 e3 e3", 26, 2)
    score.add("Trumpet", DAYLIGHT_TUNE, 27, velocity=VELOCITY + 8)
    score.add_harmony("Horn", DAYLIGHT_TUNE, 27, DAYLIGHT_TUNE_HARMONY, velocity=VELOCITY + 8)
    score.add("Flute", re.sub(r"([a-g][#b]?)(\d)", lambda m: m[1] + str(int(m[2]) + 1), DAYLIGHT_TUNE), 27)
    for bar, chord in enumerate(DAYLIGHT_TUNE_HARMONY, 27):
        score.add("Trombone", f"{DAYLIGHT_BASS[chord][2]}/4", bar)
        score.add("Timpani", f"{'a3' if chord in ('A', 'D', 'F#m') else 'e3'}/1>", bar)
    for bar in (1, 2):
        score.add("Timpani", "a3/1> r/1 e3/1 r", bar)
    # The tag: the motto, up an octave, to a high A.
    score.add("Trumpet", "e5/1 a5/1/2 b5 c#6/2 | a5/4", 35, velocity=VELOCITY + 8)
    score.add("Horn", "c#5/1 e5/1/2 e5 e5/2 | a4/4", 35, velocity=VELOCITY + 8)
    score.add("Timpani", "a3/1> r/1 e3/1 e3 | a3/1>", 35)
    score.add("Trombone", "a2/4 | a2/4", 35)
    return score


# Dusk: 3/4, the quarter at 66.

DUSK_HARP = {"Eb": ("eb2", "g3+bb3", "eb3"), "Cm": ("c2", "eb3+g3", "c3"), "Ab": ("ab1", "c3+eb3", "ab2"),
             "Bb": ("bb1", "d3+f3", "bb2"), "Fm": ("f2", "ab2+c3", "f3"), "Abm": ("ab1", "b2+eb3", "ab2"),
             "Eb/Bb": ("bb1", "eb3+g3", "bb2"), "Bb7": ("bb1", "d3+ab3", "f3"), "Cm/Bb": ("bb1", "eb3+g3", "c3"),
             "G": ("g1", "b2+d3", "g2"), "Abmaj7": ("ab1", "c3+g3", "eb3")}
DUSK_CHORDS = {"Eb": "g3+bb3+eb4", "Cm": "g3+c4+eb4", "Ab": "ab3+c4+eb4", "Bb": "f3+bb3+d4", "Fm": "f3+ab3+c4",
               "Abm": "ab3+b3+eb4", "Eb/Bb": "g3+bb3+eb4", "Bb7": "f3+ab3+d4", "Cm/Bb": "g3+c4+eb4",
               "G": "g3+b3+d4", "Abmaj7": "g3+c4+eb4"}
DUSK_SONG = ("g4/2 f4/1 | eb4/2 bb3/1 | c4/1.5 d4/1/2 eb4/1 | f4/3 | ab4/2 g4/1 | f4/2 d4/1 | eb4/1 f4 g4 | bb3/3 | "
             "g4/2 f4/1 | eb4/2 bb3/1 | c4/1.5 d4/1/2 eb4/1 | ab4/3 | g4/2 eb4/1 | f4/2 d4/1 | eb4/3")
DUSK_CLARINET = "eb5/2 d5/1 | c5/2 g4/1 | ab4/1 bb4 c5 | d5/3 | eb5/2 f5/1 | g5/2 eb5/1 | d5/1.5 c5/1/2 b4/1 | c5/3"


def dusk() -> Score:
    score = Score("Long Shadows", "Stratagem_Dusk_Long_Shadows.mid", 66, Fraction(3), (3, 4))
    harmony = (["Eb", "Cm", "Ab", "Bb", "Fm", "Bb", "Cm", "Bb", "Eb", "Cm", "Ab", "Abm", "Eb/Bb", "Bb7", "Eb", "Eb",
                "Cm", "Cm/Bb", "Ab", "G", "Cm", "Eb", "G", "Ab", "Eb", "Cm", "Ab", "Abmaj7", "Abmaj7"])
    for bar, chord in enumerate(harmony, 1):
        low, middle, high = DUSK_HARP[chord]
        score.add("Harp", f"{low}/1 {middle} {high}" if bar < 29 else f"{low}/1 {middle}/2", bar)
        if bar >= 3:
            score.add("Strings", f"{DUSK_CHORDS[chord]}/3", bar)
        if bar >= 9:
            score.add("Bass", f"{low}/3", bar)
    # The song, the motto backwards; the clarinet's in C minor, the cello
    # under it; the song again, the violins with it, left open.
    score.add("Cello", DUSK_SONG, 1)
    score.add("Clarinet", "g4/1 f4 eb4", 16)
    score.add("Clarinet", DUSK_CLARINET, 17)
    score.add("Cello", "c4/3 | bb3 | ab3 | g3 | c4 | bb3 | b3 | c4", 17)
    score.add("Horn", "b3/3 | bb3 | ab3 | g3", 12)
    coda = "g4/2 f4/1 | eb4/2 bb3/1 | c4/1.5 d4 | eb4/6"
    score.add("Cello", coda, 25)
    score.add("Violins", re.sub(r"([a-g][#b]?)(\d)", lambda m: m[1] + str(int(m[2]) + 1), coda), 25)
    return score


# Night: 5/4, the quarter at 54.

NIGHT_HARMONY = [("B", 4), ("G", 2), ("Em", 2), ("B", 2), ("G", 1), ("A", 1), ("F#", 1), ("B", 2)]
NIGHT_LOW = {"B": ("b1", "f#2"), "G": ("g1", "d3"), "Em": ("e1", "b2"), "A": ("a1", "e3"), "F#": ("f#1", "c#3")}
NIGHT_CHORDS = {"B": "f#4+a4+c#5", "G": "f#4+b4+d5", "Em": "g4+d5+f#5", "A": "e4+a4+c#5", "F#": "f#4+a#4+c#5"}
NIGHT_STARS = ["f#6", "b6", "d6", "a6", "e6", "b5", "f#6", "c#6"]


def night() -> Score:
    score = Score("Night Watch", "Stratagem_Night_Watch.mid", 54, Fraction(5), (5, 4))
    bar = 1
    for chord, count in NIGHT_HARMONY:
        low, fifth = NIGHT_LOW[chord]
        last = chord == "B" and bar == 14
        score.add("Bass", f"{low}/{5 * count}", bar)
        score.add("Cellos", f"{fifth}/{5 * count}", bar)
        score.add("Strings", f"{NIGHT_CHORDS[chord] if not last else 'f#4+b4+c#5'}/{5 * count}", bar)
        for each in range(bar, bar + count):
            if 3 <= each <= 12:
                score.add("Harp", f"{low[:-1]}2/2 {fifth[:-1]}3/3", each)
        bar += count
    # Stars, twice a bar (day_music sets them off the clock).
    for index, bar in enumerate(b for b in range(2, 15) for _ in range(2)):
        star = NIGHT_STARS[index % len(NIGHT_STARS)]
        if bar == 13 and star in ("a6", "d6"):
            star = "f#6"
        score.add("Celesta", f"{star}/1", bar, 2.5 * (index % 2) + 0.5)
    # The flute alone, the motto in minor; the clarinet's, a bar before the
    # far horn's, in canon; at the one major chord, the horn near.
    score.add("Flute", "f#4/2 b4/1 c#5 d5 | e5/3 d5/1 c#5 | b4/5 | a4/2 b4/1 d5/2 | f#5/3 e5/2 | "
                       "d5/1 c#5 b4 a4/2 | b4/5", 3)
    score.add("Clarinet", "f#3/2 b3/1 c#4 d4 | g#4/3 f#4/2 | e4/3 d4/2 | c#4/5", 9)
    score.add("Far horn", "f#3/2 b3/1 c#4 d4 | e4/5", 10)
    score.add("Horn", "a#3/5", 13)
    score.add("Flute", "c#5/3 a#4/2 | d5/2 c#5/3 | c#5/5", 13)
    return score


# Underground: 7/8 (a bar three and a half quarters), the eighth at 168.

UNDERGROUND_PULSE = {"C": "c2/1 c2 db2/1/2 c2 g1", "Ab": "ab1/1 ab1 bb1/1/2 ab1 eb1",
                     "Bb": "bb1/1 bb1 c2/1/2 bb1 f1", "C major": "c2/1 c2 d2/1/2 c2 g1"}
UNDERGROUND_GLASS = [(5, "c5+g5"), (7, "db5+ab5"), (9, "eb5+bb5"), (11, "c5+g5"), (13, "db5+ab5"),
                     (15, "bb4+f5"), (23, "db5+ab5"), (25, "c5+g5")]
UNDERGROUND_DRIPS = ["c6", "g5", "eb6", "db6", "bb5", "c6", "f6", "g5"]
UNDERGROUND_DRIP_BEATS = [0.5, 2, 1, 3, 2.5, 0, 1.5]


def underground() -> Score:
    score = Score("Seams", "Stratagem_Underground_Seams.mid", 84, Fraction(7, 2), (7, 8))
    pulse = ["C"] * 16 + ["Ab", "Ab", "Bb", "Bb", "C major", "C major"] + ["C"] * 3
    for bar, chord in enumerate(pulse, 1):
        score.add("Pulse", UNDERGROUND_PULSE[chord], bar)
    score.add("Pulse", "c2/1", 26)
    score.add("Drone", "c3/56 | ab2/7 | bb2/7 | c3/21", 1)
    score.add("Drone", "g3/42 | eb3/7 | f3/7 | g3/14", 5)
    for bar, chord in UNDERGROUND_GLASS:
        score.add("Glass", f"{chord}/7", bar)
    drips = [b for b in list(range(3, 17)) + list(range(23, 27)) for _ in range(1 + b % 2)]
    for index, bar in enumerate(drips):
        score.add("Drips", f"{UNDERGROUND_DRIPS[index % len(UNDERGROUND_DRIPS)]}/1/2", bar,
                  UNDERGROUND_DRIP_BEATS[index % len(UNDERGROUND_DRIP_BEATS)])
    # The motto bent, a minor second, on the trombone; the bassoon's answer.
    score.add("Trombone", "g2/3.5 | c3/1.5 db3/2 | eb3/7", 9)
    score.add("Bassoon", "g3/3.5 | f3/1.5 eb3/1 db3 | c3/7", 13)
    for bar in (13, 14, 15, 16, 17, 19, 21):
        score.add("Timpani", {17: "ab2", 19: "bb2"}.get(bar, "c3") + "/1>", bar)
    # The Hidden World: the motto from A flat, rising into C major.
    score.add("Horn", "eb4/2 ab4/1.5 | bb4 c5/2 | d5/3.5 | f5/1.5 d5/2 | e5/7", 17)
    score.add("Strings", "c4+eb4+ab4/7 | d4+f4+bb4/7 | e4+g4+c5/7", 17)
    score.add("Trombone", "ab2/7 | bb2/7 | c3/7", 17)
    return score


SCORES = [dawn, daylight, dusk, night, underground]


def main() -> None:
    for score in SCORES:
        print(score().write())


if __name__ == "__main__":
    main()
