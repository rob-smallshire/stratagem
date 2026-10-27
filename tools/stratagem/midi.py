"""Standard MIDI Files, read through mido: the notes of each track, with
their times in ticks, and the meta events that matter for turning them
into a score (tempo, time and key signatures, names, programs).

    uv run python -m stratagem.midi FILE     # summarise a file
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import mido


@dataclass(frozen=True)
class Note:
    start: int                      # ticks
    length: int
    pitch: int                      # MIDI note number
    velocity: int
    channel: int


@dataclass
class Track:
    name: str = ""
    notes: list[Note] = field(default_factory=list)
    programs: list[tuple[int, int, int]] = field(default_factory=list)     # (tick, channel, program)
    controls: list[tuple[int, int, int, int]] = field(default_factory=list)  # (tick, channel, controller, value)
    instrument: str = ""


@dataclass
class Song:
    division: int                   # ticks per quarter note
    tracks: list[Track]
    tempos: list[tuple[int, int]]   # (tick, microseconds per quarter)
    time_signatures: list[tuple[int, int, int]]     # (tick, numerator, denominator)
    key_signatures: list[tuple[int, str, int]]      # (tick, key, unused)
    markers: list[tuple[int, str]]

    @property
    def end(self) -> int:
        return max((n.start + n.length for t in self.tracks for n in t.notes), default=0)

    def seconds(self, tick: int) -> float:
        """A tick's time, through the tempo changes."""
        tempos = sorted(self.tempos) or [(0, 500000)]
        if tempos[0][0] != 0:
            tempos.insert(0, (0, 500000))
        total, (last_tick, last_tempo) = 0.0, tempos[0]
        for at, tempo in tempos[1:]:
            if at >= tick:
                break
            total += (at - last_tick) * last_tempo / 1e6 / self.division
            last_tick, last_tempo = at, tempo
        return total + (tick - last_tick) * last_tempo / 1e6 / self.division


def read(filepath: Path | str) -> Song:
    """A file's notes, by track, and its meta events, through mido."""
    midi = mido.MidiFile(str(filepath))
    song = Song(midi.ticks_per_beat, [], [], [], [], [])
    for midi_track in midi.tracks:
        track = Track(name=midi_track.name)
        sounding: dict[tuple[int, int], list[tuple[int, int]]] = {}    # (channel, pitch) -> [(start, velocity)]
        tick = 0
        for message in midi_track:
            tick += message.time
            if message.type == "note_on" and message.velocity:
                sounding.setdefault((message.channel, message.note), []).append((tick, message.velocity))
            elif message.type in ("note_on", "note_off"):
                starts = sounding.get((message.channel, message.note))
                if starts:
                    start, velocity = starts.pop(0)
                    track.notes.append(Note(start, tick - start, message.note, velocity, message.channel))
            elif message.type == "program_change":
                track.programs.append((tick, message.channel, message.program))
            elif message.type == "control_change":
                track.controls.append((tick, message.channel, message.control, message.value))
            elif message.type == "instrument_name":
                track.instrument = message.name
            elif message.type in ("marker", "cue_marker", "text"):
                song.markers.append((tick, message.text))
            elif message.type == "set_tempo":
                song.tempos.append((tick, message.tempo))
            elif message.type == "time_signature":
                song.time_signatures.append((tick, message.numerator, message.denominator))
            elif message.type == "key_signature":
                song.key_signatures.append((tick, message.key, 0))
        track.notes.sort(key=lambda n: (n.start, n.pitch))
        song.tracks.append(track)
    return song


NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def pitch_name(pitch: int) -> str:
    return f"{NAMES[pitch % 12]}{pitch // 12 - 1}"


def polyphony(notes: list[Note]) -> int:
    """The most notes sounding at once."""
    events = sorted([(n.start, 1) for n in notes] + [(n.start + n.length, -1) for n in notes])
    most = current = 0
    for _, change in events:
        current += change
        most = max(most, current)
    return most


def summary(song: Song) -> str:
    lines = [f"division {song.division} ticks a quarter; {len(song.tracks)} tracks; "
             f"{song.seconds(song.end):.1f}s, {song.end / song.division:.1f} quarters",
             f"tempos {[(t, round(60e6 / u, 1)) for t, u in song.tempos]}",
             f"time signatures {song.time_signatures}",
             f"key signatures {song.key_signatures}"]
    if song.markers:
        lines.append(f"markers {song.markers}")
    everything = [n for t in song.tracks for n in t.notes]
    lines.append(f"all tracks: {len(everything)} notes, at most {polyphony(everything)} at once")
    for index, track in enumerate(song.tracks):
        if not track.notes and not track.programs:
            lines.append(f"track {index} '{track.name}': no notes")
            continue
        pitches = [n.pitch for n in track.notes]
        lengths = Counter(n.length for n in track.notes)
        lines.append(
            f"track {index} '{track.name}' {track.instrument}: {len(track.notes)} notes, "
            f"channels {sorted({n.channel for n in track.notes})}, programs {track.programs}, "
            f"{pitch_name(min(pitches))}-{pitch_name(max(pitches))}, at most {polyphony(track.notes)} at once, "
            f"{song.seconds(track.notes[0].start):.1f}-{song.seconds(track.notes[-1].start):.1f}s, "
            f"velocities {min(n.velocity for n in track.notes)}-{max(n.velocity for n in track.notes)}, "
            f"commonest lengths {lengths.most_common(4)}")
        if track.controls:
            lines.append(f"    controls {Counter((c, v) for _, _, c, v in track.controls).most_common(6)}")
    return "\n".join(lines)


def main() -> None:
    print(summary(read(sys.argv[1])))


if __name__ == "__main__":
    main()
