"""A compact score format for the Music 5000, for music in the game as well
as on the title: a prototype, in Python, of an encoder and of the player
that would run it (stratagem.music5000 has the board and the instruments).

Music is notes on a musical clock, not on the player's 50Hz tick: a piece
has its steps (a quarter is so many), and a tempo, the steps a tick, which
the player adds up; every voice advances by the steps that have passed. So
a bar is the same number of steps wherever it falls, and repeats encode
the same, at any tempo.

A piece is notes, each in a part (an instrument, a level, a stereo place):

1. Each part is split into lines, one note at a time (a chord's notes,
   top down, onto its lines in order), and each line into phrases at its
   rests of a bar or so.
2. Phrases are given to the board's sixteen channels, a whole phrase to
   one channel, so that what repeats in the music repeats in a channel's
   events: the same part's line goes back to its channel if it can, and a
   phrase that finds no free channel cuts another's release short, or is
   placed note by note. Optional notes (decorations), in phrases of their
   own, take what is left, in their order: a whole phrase or none of it,
   cutting nothing short.
3. The dynamics of the whole are the conductor's: a level that every
   voice follows, changed in straight lines.

Each voice's events are then tokens (a note is an interval from the last
and a slot, a rest after it folded in as its gap), and what repeats, across
all the voices, becomes patterns, called (Re-Pair). An interval rather than
a pitch makes a phrase transposed the same tokens. The Stratagem Overture
(stratagem.overture) is 1.7K so, against 9.7K as the title's player has it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from stratagem.music5000 import (AMPLITUDE, ATTACK, CHANNELS, CONTROL, DB_PER_STEP, DECAY, FULL, INSTRUMENTS,
                                  LOWEST_NOTE, PITCHES, RELEASE, SUSTAIN, VIBRATO_UP, WAVE_NUMBERS, WAVE_SELECT,
                                  Player)

MAX_LENGTH = 255                    # steps in one event


@dataclass(frozen=True)
class Note:
    start: int                      # steps
    end: int
    pitch: int                      # MIDI note number
    part: str
    instrument: str
    quieter: int                    # amplitude steps below the conductor's level (signed)
    pan: int
    detune: int = 0
    priority: int = 0               # higher takes a channel first
    optional: int = 0               # 0: the score's; else a decoration, placed in this order


def quieter_for(db: float) -> int:
    return round(-db / DB_PER_STEP)


def release_steps(instrument_name: str, steps: int, ticks_per_step: float) -> int:
    """Steps from a note's end until its release has died away, at most."""
    instrument = INSTRUMENTS[instrument_name]
    ticks, level, decaying = round(steps * ticks_per_step), 0, False
    for _ in range(ticks):
        if not decaying:
            level = min(FULL, level + instrument.attack)
            decaying = level == FULL
        else:
            level = max(instrument.sustain, level - instrument.decay)
    return math.ceil(-(-level // instrument.release) / ticks_per_step)


# Lines and phrases

def lines(notes: list[Note]) -> list[list[Note]]:
    """A part's notes, one at a time: a chord's top note on the first line
    free, the next note down on the next, and so on."""
    found: list[list[Note]] = []
    for note in sorted(notes, key=lambda n: (n.start, -n.pitch)):
        line = next((line for line in found if line[-1].end <= note.start), None)
        if line is None:
            found.append(line := [])
        line.append(note)
    return found


def phrases(line: list[Note], gap: int) -> list[list[Note]]:
    """A line split at its rests of gap steps or more."""
    found = [[line[0]]]
    for note in line[1:]:
        if note.start - found[-1][-1].end >= gap:
            found.append([])
        found[-1].append(note)
    return found


@dataclass
class Voice:
    notes: list[Note] = field(default_factory=list)
    busy: list[tuple[int, int]] = field(default_factory=list)      # (start, end of release)
    last: tuple[str, int] | None = None                             # the (part, line) it played last

    def free(self, start: int, end: int) -> bool:
        """Free from start to end, its releases sounding out."""
        return all(e <= start or s >= end for s, e in self.busy)

    def silent(self, start: int, end: int) -> bool:
        """Free from start to end if a release is cut short."""
        return all(n.end <= start or n.start >= end for n in self.notes)

    def take(self, notes: list[Note], key: tuple[str, int], ticks_per_step: float) -> None:
        for note in notes:
            self.notes.append(note)
            self.busy.append((note.start, note.end + release_steps(note.instrument, note.end - note.start,
                                                                    ticks_per_step)))
        self.notes.sort(key=lambda n: n.start)
        self.last = key


def allocate(notes: list[Note], ticks_per_step: float, gap: int, optional_gap: int,
             channels: int = CHANNELS) -> tuple[list[Voice], int]:
    """The notes on channels, phrases split at rests of gap steps (the
    optional, at optional_gap); and how many optional notes found none."""
    voices = [Voice() for _ in range(channels)]
    dropped = 0

    def busy_span(group: list[Note]) -> tuple[int, int]:
        return group[0].start, max(n.end + release_steps(n.instrument, n.end - n.start, ticks_per_step)
                                   for n in group)

    def place(group: list[Note], key: tuple[str, int], cut: bool) -> bool:
        start, end = busy_span(group)
        free = [v for v in voices if (v.silent(start, end) if cut else v.free(start, end))]
        if not free:
            return False
        same = [v for v in free if v.last == key]
        unused = [v for v in free if v.last is None]
        voice = (same or unused or free)[0]
        voice.take(group, key, ticks_per_step)
        return True

    by_part: dict[str, list[Note]] = {}
    for note in notes:
        by_part.setdefault(note.part, []).append(note)
    for optional in sorted({n.optional for n in notes}):
        groups = []
        for part, part_notes in by_part.items():
            for index, line in enumerate(lines([n for n in part_notes if n.optional == optional])):
                groups += [(phrase, (part, index))
                           for phrase in phrases(line, optional_gap if optional else gap)]
        groups.sort(key=lambda g: (g[0][0].start, -g[0][0].priority, -g[0][0].pitch))
        for group, key in groups:
            if optional:
                dropped += 0 if place(group, key, cut=False) else len(group)
            elif not place(group, key, cut=False) and not place(group, key, cut=True):
                for note in group:
                    assert place([note], key, cut=False) or place([note], key, cut=True), f"no channel for {note}"
    return [v for v in voices if v.notes], dropped


# Events: what a voice does, in steps, before encoding
#   ("instrument", name), ("quieter", steps), ("pan", position), ("detune", units),
#   ("note", pitch, steps), ("hold", steps), ("rest", steps)
# and the conductor's: ("level", steps), ("slope", steps a step, 8.8), ("wait", steps).

Event = tuple


def timed(kind: str, steps: int, pitch: int | None = None) -> list[Event]:
    events = []
    while steps > 0:
        part = min(steps, MAX_LENGTH)
        events.append(("note", pitch, part) if kind == "note" else (kind, part))
        kind = "hold" if kind == "note" else kind
        steps -= part
    return events


def voice_events(voice: Voice, end: int) -> list[Event]:
    events: list[Event] = []
    time = 0
    instrument = pan = quieter = None
    detune = 0
    for note in voice.notes:
        if note.start > time:
            events += timed("rest", note.start - time)
        if instrument != note.instrument:
            events.append(("instrument", note.instrument))
            instrument, pan = note.instrument, INSTRUMENTS[note.instrument].stereo
        if pan != note.pan:
            events.append(("pan", note.pan))
            pan = note.pan
        if detune != note.detune:
            events.append(("detune", note.detune))
            detune = note.detune
        if quieter != note.quieter:
            events.append(("quieter", note.quieter))
            quieter = note.quieter
        events += timed("note", note.end - note.start, note.pitch)
        time = note.end
    if end > time:
        events += timed("rest", end - time)
    return events


def conductor_events(points: list[tuple[int, float]], end: int) -> list[Event]:
    """The conductor's level (amplitude steps quieter, in 8.8) through
    points (step, steps quieter), in straight lines: each line a slope,
    from the level the last line actually reached."""
    level = round(points[0][1] * 256)
    time = points[0][0]
    events: list[Event] = [("level", level)] + timed("wait", time)
    for step, quieter in points[1:]:
        if step <= time:
            continue
        span = step - time
        slope = round((quieter * 256 - level) / span)
        if slope:
            events.append(("slope", slope))
        events += timed("wait", span)
        level += slope * span
        if slope:
            events.append(("slope", 0))
        time = step
    if end > time:
        events += timed("wait", end - time)
    return events


def steps_of(events: list[Event]) -> int:
    return sum(e[-1] for e in events if e[0] in ("note", "hold", "rest", "wait"))


# Tokens: the events as the player reads them. A note is its interval from
# the voice's last pitch, a slot (steps to the next event) and a gap (steps
# of its slot it is released for, the voice's gap: set when it changes).
#   ("note", interval, slot), ("hold", steps), ("rest", steps), ("gap", steps),
#   ("pitch", absolute: note number) and the other events as they are.

FOLDED_GAP = 7                      # the longest rest folded into a note before it
LEAP = 24                           # the widest interval; beyond, the pitch is given


def tokens(events: list[Event]) -> list[tuple]:
    out: list[tuple] = []
    pitch, gap = None, 0
    index = 0
    while index < len(events):
        event = events[index]
        index += 1
        if event[0] != "note":
            out.append(event)
            continue
        _, note_pitch, steps = event
        following = events[index] if index < len(events) else None
        rest = following[1] if following and following[0] == "rest" and following[1] <= FOLDED_GAP \
            and steps + following[1] <= MAX_LENGTH else 0
        if rest:
            index += 1
        if rest != gap:
            out.append(("gap", rest))
            gap = rest
        if pitch is None or abs(note_pitch - pitch) > LEAP:
            out.append(("pitch", note_pitch))
            interval = 0
        else:
            interval = note_pitch - pitch
        pitch = note_pitch
        out.append(("note", interval, steps + rest))
    return out


# The format. A voice's stream, a byte at a time:
#   &00-&7F   a note, (byte >> 3) - 8 semitones from the voice's last (-8 to
#             +7), for the slot at byte & 7 in the piece's table of slots
#   &80-&87   GAP: notes from here released this many steps before their
#             slot ends (a rest folded into them)
#   &88-&97   PAN: a stereo position
#   &98-&A7   DETUNE: -8 to +7 units
#   &A8-&B7   INSTRUMENT: the orchestra's (stratagem.music5000), by number
#   &F0 i s   NOTE: an interval (signed) and a slot
#   &F1 n     PITCH: the next note's pitch, from the interval 0 (n, its
#             index in the pitch table)
#   &F2 n     REST for n steps
#   &F3 n     HOLD the note for n more steps
#   &F4 q     QUIETER: amplitude steps below the conductor's level (signed)
#   &F5 k     CALL pattern k: its events, to its RETURN
#   &F6       RETURN
#   &FF       LOOP: back to the stream's start
# The conductor's stream, which has no channel:
#   &F7 l h w TEMPO: steps a tick, w and a fraction (h, l in 65536ths)
#   &F8 l h   LEVEL: amplitude steps quieter for every voice (8.8)
#   &F9 l h   SLOPE: added to the level each step (8.8, signed)
#   &FA n     WAIT n steps
#   &FF       LOOP
# A note sounds for its slot less the gap, then releases: the voice reads
# its next event when the slot is over. All voices are as long, in steps.

SHORT_INTERVALS = range(-8, 8)
SLOTS = 8
GAP, PAN, DETUNE, INSTRUMENT = 0x80, 0x88, 0x98, 0xA8
NOTE, PITCH, REST, HOLD, QUIETER, CALL, RETURN = range(0xF0, 0xF7)
TEMPO, LEVEL, SLOPE, WAIT = range(0xF7, 0xFB)
LOOP = 0xFF
MAX_PATTERNS = 256
MAX_DEPTH = 4                       # calls within calls

INSTRUMENT_NUMBERS = {name: number for number, name in enumerate(INSTRUMENTS)}
INSTRUMENT_NAMES = list(INSTRUMENTS)
assert len(INSTRUMENTS) <= 16


def token_bytes(token: tuple, slots: list[int]) -> bytes:
    kind = token[0]
    if kind == "note":
        _, interval, slot = token
        if interval in SHORT_INTERVALS and slot in slots:
            return bytes([(interval + 8) << 3 | slots.index(slot)])
        return bytes([NOTE, interval & 0xFF, slot])
    if kind == "gap":
        return bytes([GAP + token[1]])
    if kind == "pan":
        return bytes([PAN + token[1]])
    if kind == "detune":
        assert -8 <= token[1] <= 7
        return bytes([DETUNE + (token[1] & 15)])
    if kind == "instrument":
        return bytes([INSTRUMENT + INSTRUMENT_NUMBERS[token[1]]])
    if kind == "pitch":
        return bytes([PITCH, token[1] - LOWEST_NOTE])
    if kind == "rest":
        return bytes([REST, token[1]])
    if kind == "hold":
        return bytes([HOLD, token[1]])
    if kind == "quieter":
        assert -128 <= token[1] <= 127
        return bytes([QUIETER, token[1] & 0xFF])
    if kind == "call":
        return bytes([CALL, token[1]])
    raise ValueError(token)


def conductor_bytes(events: list[Event], steps_per_tick: int) -> bytes:
    """The conductor's stream, from its events, at a tempo (steps a tick,
    in 65536ths)."""
    out = bytearray([TEMPO, steps_per_tick & 0xFF, steps_per_tick >> 8 & 0xFF, steps_per_tick >> 16])
    for event in events:
        kind, value = event
        if kind == "wait":
            out += bytes([WAIT, value])
        else:
            value &= 0xFFFF
            out += bytes([LEVEL if kind == "level" else SLOPE, value & 0xFF, value >> 8])
    return bytes(out + bytes([LOOP]))


# Patterns, found by Re-Pair (Larsson and Moffat): the commonest pair of
# symbols, again and again, becomes a pattern; patterns that don't save
# bytes are put back, and calls kept to MAX_DEPTH deep.

Symbol = tuple


def replace_pair(sequence: list[Symbol], pair: tuple[Symbol, Symbol], symbol: Symbol) -> list[Symbol]:
    out, index = [], 0
    while index < len(sequence):
        if index + 1 < len(sequence) and (sequence[index], sequence[index + 1]) == pair:
            out.append(symbol)
            index += 2
        else:
            out.append(sequence[index])
            index += 1
    return out


def pair_counts(sequences: list[list[Symbol]]) -> dict:
    counts: dict = {}
    for sequence in sequences:
        index = 0
        while index + 1 < len(sequence):
            pair = (sequence[index], sequence[index + 1])
            counts[pair] = counts.get(pair, 0) + 1
            # (a run of one symbol: count its pairs without overlap)
            index += 2 if index + 2 < len(sequence) and sequence[index] == sequence[index + 1] == sequence[
                index + 2] else 1
    return counts


def inline(sequences: list[list[Symbol]], rules: dict, name: Symbol) -> None:
    body = rules.pop(name)
    for sequence in sequences + list(rules.values()):
        if name in sequence:
            sequence[:] = [s for symbol in sequence for s in (body if symbol == name else [symbol])]


def compress(sequences: list[list[Symbol]], slots: list[int]) -> tuple[list[list[Symbol]], dict]:
    sequences = [list(s) for s in sequences]
    rules: dict = {}
    while True:
        counts = pair_counts(sequences + list(rules.values()))
        if not counts:
            break
        pair, count = max(counts.items(), key=lambda item: item[1])
        if count < 2:
            break
        name = ("call", len(rules))
        for sequence in sequences + list(rules.values()):
            sequence[:] = replace_pair(sequence, pair, name)
        rules[name] = list(pair)

    def cost(symbols: list[Symbol]) -> int:
        return sum(len(token_bytes(s, slots)) for s in symbols)

    def depth(name: Symbol) -> int:
        return 1 + max([depth(s) for s in rules[name] if s[0] == "call"], default=0)

    while True:
        uses: dict = {}
        for sequence in sequences + list(rules.values()):
            for symbol in sequence:
                if symbol[0] == "call":
                    uses[symbol] = uses.get(symbol, 0) + 1
        # A pattern costs its body, a RETURN and two bytes in the table; each
        # call saves its body less the two bytes of the CALL.
        gains = {name: uses.get(name, 0) * (cost(body) - 2) - (cost(body) + 3) for name, body in rules.items()}
        worst = min(gains, key=gains.get, default=None)
        if worst is not None and gains[worst] <= 0:
            inline(sequences, rules, worst)
            continue
        deep = [name for name in rules if depth(name) > MAX_DEPTH]
        if deep:
            name = deep[0]
            while depth(name) > 1:          # down the deepest calls to a pattern that calls none
                name = max((s for s in rules[name] if s[0] == "call"), key=depth)
            inline(sequences, rules, name)
            continue
        break
    assert len(rules) <= MAX_PATTERNS
    numbers = {name: ("call", number) for number, name in enumerate(rules)}

    def renumber(symbols: list[Symbol]) -> list[Symbol]:
        return [numbers.get(s, s) for s in symbols]

    return [renumber(s) for s in sequences], {numbers[name]: renumber(body) for name, body in rules.items()}


@dataclass(frozen=True)
class Piece:
    slots: list[int]
    steps_per_tick: int             # 65536ths
    conductor: bytes
    voices: list[bytes]
    patterns: list[bytes]

    def size(self) -> int:
        """Bytes: the streams, the patterns and their table of addresses, the
        slots."""
        return (len(self.conductor) + sum(map(len, self.voices)) + sum(map(len, self.patterns))
                + 2 * len(self.patterns) + len(self.slots))


def encode(voices: list[list[Event]], conductor: list[Event], ticks_per_step: float) -> Piece:
    sequences = [tokens(events) for events in voices]
    counts: dict = {}
    for sequence in sequences:
        for token in sequence:
            if token[0] == "note":
                counts[token[2]] = counts.get(token[2], 0) + 1
    slots = sorted(counts, key=lambda slot: (-counts[slot], slot))[:SLOTS]
    slots += [0] * (SLOTS - len(slots))
    sequences, rules = compress(sequences, slots)

    def assemble(symbols: list[Symbol], end: int) -> bytes:
        return b"".join(token_bytes(s, slots) for s in symbols) + bytes([end])

    return Piece(slots, round(65536 / ticks_per_step), conductor_bytes(conductor, round(65536 / ticks_per_step)),
                 [assemble(s, LOOP) for s in sequences],
                 [assemble(rules[("call", n)], RETURN) for n in range(len(rules))])


# Reading it back

def read_token(stream: bytes, position: int, slots: list[int]) -> tuple[tuple, int]:
    """The token at a position in a voice's stream, and the next position."""
    byte = stream[position]
    if byte < 0x80:
        return ("note", (byte >> 3) - 8, slots[byte & 7]), position + 1
    if byte < PAN:
        return ("gap", byte - GAP), position + 1
    if byte < DETUNE:
        return ("pan", byte - PAN), position + 1
    if byte < INSTRUMENT:
        return ("detune", (byte - DETUNE) - 16 if byte - DETUNE >= 8 else byte - DETUNE), position + 1
    if byte < INSTRUMENT + 16:
        return ("instrument", INSTRUMENT_NAMES[byte - INSTRUMENT]), position + 1
    if byte == NOTE:
        interval = stream[position + 1]
        return ("note", interval - 256 if interval & 0x80 else interval, stream[position + 2]), position + 3
    if byte in (RETURN, LOOP):
        return ("return" if byte == RETURN else "loop",), position + 1
    value = stream[position + 1]
    if byte == PITCH:
        return ("pitch", value + LOWEST_NOTE), position + 2
    if byte == QUIETER:
        return ("quieter", value - 256 if value & 0x80 else value), position + 2
    kind = {REST: "rest", HOLD: "hold", CALL: "call"}[byte]
    return (kind, value), position + 2


def expand(piece: Piece, voice: int) -> list[tuple]:
    """A voice's tokens, its patterns' put in place, to its LOOP."""
    def walk(stream: bytes) -> list[tuple]:
        out, position = [], 0
        while True:
            token, position = read_token(stream, position, piece.slots)
            if token[0] in ("return", "loop"):
                return out
            out += walk(piece.patterns[token[1]]) if token[0] == "call" else [token]
    return walk(piece.voices[voice])


# The player, as the 6502 would run it: one tick per vertical sync.

@dataclass
class VoiceState:
    stream: bytes
    position: int = 0
    returns: list[tuple[bytes, int]] = field(default_factory=list)
    count: int = 0                  # steps left of the current event; 0: read the next
    release_at: int = -1            # release the note when count reaches this
    pitch: int = 0                  # index in the pitch table
    gap: int = 0
    level: int = 0
    phase: int = RELEASE
    quieter: int = 0
    instrument: object = None
    detune: int = 0
    frequency: int = 0
    unit: int = 0
    vibrato_count: int = 0
    lfo: int = 0


@dataclass
class SequencePlayer:
    """tick() advances the conductor and every voice and returns the
    writes it makes to the board, (register offset, value), as
    music5000.Player does."""
    piece: Piece
    voices: list[VoiceState] = field(init=False)
    clock: int = 0                  # the fraction of a step, in 65536ths
    steps_per_tick: int = 0
    conductor_position: int = 0
    conductor_count: int = 0
    level: int = 0                  # the conductor's (8.8)
    slope: int = 0

    def __post_init__(self):
        self.voices = [VoiceState(stream) for stream in self.piece.voices]
        self.conductor(0)               # its tempo and level, before the first tick

    def conductor(self, elapsed: int) -> None:
        self.level += self.slope * elapsed
        self.conductor_count -= elapsed
        stream = self.piece.conductor
        while self.conductor_count <= 0:
            byte = stream[self.conductor_position]
            if byte == LOOP:
                self.conductor_position = 0
                continue
            if byte == WAIT:
                self.conductor_count += stream[self.conductor_position + 1]
                self.conductor_position += 2
            elif byte == TEMPO:
                self.steps_per_tick = int.from_bytes(stream[self.conductor_position + 1:self.conductor_position + 4],
                                                     "little")
                self.conductor_position += 4
            else:
                value = stream[self.conductor_position + 1] | stream[self.conductor_position + 2] << 8
                value -= 0x10000 if value & 0x8000 else 0
                if byte == LEVEL:
                    self.level = value
                else:
                    self.slope = value
                self.conductor_position += 3

    def read(self, channel: int, state: VoiceState, writes: list) -> bool:
        """The voice's events to its next note, hold or rest; whether a
        note started."""
        while True:
            token, position = read_token(state.stream, state.position, self.piece.slots)
            state.position = position
            kind = token[0]
            if kind == "loop":
                state.position = 0
            elif kind == "call":
                state.returns.append((state.stream, state.position))
                assert len(state.returns) <= MAX_DEPTH
                state.stream, state.position = self.piece.patterns[token[1]], 0
            elif kind == "return":
                state.stream, state.position = state.returns.pop()
            elif kind == "gap":
                state.gap = token[1]
            elif kind == "pan":
                writes.append((CONTROL + channel, token[1]))
            elif kind == "detune":
                state.detune = token[1]
            elif kind == "instrument":
                state.instrument = INSTRUMENTS[token[1]]
                writes += [(WAVE_SELECT + channel, WAVE_NUMBERS[state.instrument.wave] << 4),
                           (CONTROL + channel, state.instrument.stereo)]
            elif kind == "quieter":
                state.quieter = token[1]
            elif kind == "pitch":
                state.pitch = token[1] - LOWEST_NOTE
            elif kind == "rest":
                state.count += token[1]
                state.release_at = -1
                state.phase = RELEASE
                return False
            elif kind == "hold":
                state.count += token[1]
                state.release_at = -1
                return False
            else:
                _, interval, slot = token
                state.pitch += interval
                state.count += slot
                state.release_at = state.gap
                pitch = PITCHES[state.pitch]
                state.unit = pitch >> state.instrument.shift & 0xFFFF
                state.frequency = (pitch + state.detune * state.unit) & 0xFFFFFF
                writes += Player.frequency_writes(channel, state)
                state.vibrato_count = state.instrument.vibrato
                state.lfo = 0
                state.phase = ATTACK
                return True

    def tick(self) -> list[tuple[int, int]]:
        writes: list[tuple[int, int]] = []
        self.clock += self.steps_per_tick
        elapsed, self.clock = self.clock >> 16, self.clock & 0xFFFF
        self.conductor(elapsed)
        conducted = self.level >> 8
        for channel, state in enumerate(self.voices):
            state.count -= elapsed
            started = False
            while state.count <= 0:
                started = self.read(channel, state, writes) or started
            if state.count <= state.release_at:
                state.phase = RELEASE
                state.release_at = -1
            instrument = state.instrument
            if not started and instrument and instrument.vibrato:
                if state.vibrato_count:
                    state.vibrato_count -= 1
                else:
                    state.lfo = (state.lfo + 1) & 7
                    step = state.unit if VIBRATO_UP[state.lfo] else -state.unit
                    state.frequency = (state.frequency + step) & 0xFFFFFF
                    writes += Player.frequency_writes(channel, state)
            if state.phase == ATTACK:
                state.level = min(FULL, state.level + instrument.attack)
                if state.level == FULL:
                    state.phase = DECAY
            elif state.phase == DECAY:
                state.level = max(instrument.sustain, state.level - instrument.decay)
                if state.level == instrument.sustain:
                    state.phase = SUSTAIN
            elif state.phase == RELEASE and instrument:
                state.level = max(0, state.level - instrument.release)
            writes.append((AMPLITUDE + channel, max(0, state.level - max(0, state.quieter + conducted))))
        return writes

    def ticks(self) -> int:
        """The piece's length in ticks, once round: the tick that sees its
        last step starts it again."""
        steps = sum(t[-1] for t in expand(self.piece, 0) if t[0] in ("note", "hold", "rest"))
        return -(-steps * 65536 // self.piece.steps_per_tick) - 1
