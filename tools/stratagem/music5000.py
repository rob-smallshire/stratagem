"""The Music 5000, driven directly: the board's encodings, wave tables, a
pitch table, a small score format, and a model of M5PLAY's player
(asm/m5play.asm), for an experiment in playing music without AMPLE.

The board (Hybrid Music 5000, on the 1 MHz bus) is a fixed-program DSP:
sixteen channels, each a 24-bit frequency added to a phase every sample
(46875 a second), a wave looked up at the phase's top seven bits, an
amplitude added to it in the log domain, and a stereo position. Its 2K of
RAM is write-only, reached through JIM: &FCFF selects a page, &FD00-&FDFF
is that page. Pages &30-&3F (bit 0 ignored) are eight 256-byte blocks:
fourteen 128-byte waves at &000-&6FF, then the channel registers, a row of
sixteen (one byte per channel) for each register, the normal bank at &700
and the alternate at &780.

Everything else, envelopes and sequencing, is the host's: AMPLE is one
such program, and M5PLAY another.

Samples and amplitudes are logarithmic, as the AM6070 DAC is: a wave byte
is a sign (bit 7 set: positive) and a magnitude code m, chord m >> 4 and
step m & 15, worth 2^chord * (2 * step + 33) - 33 (0 to 8031). The
amplitude a is added to m: the channel outputs m + a - 128, or nothing if
that is below zero. So a = &80 is full volume, and each step down is about
0.38dB (16 to a halving). A new amplitude takes effect at the channel's next
phase wrap, so changing it doesn't click.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

SAMPLE_RATE = 46875
JIM_PAGE = 0xFCFF
JIM_WINDOW = 0xFD00
FIRST_PAGE = 0x30
REGISTER_PAGE = 0x3E                # the channel registers, normal bank at +&00
WAVE_BYTES = 128
WAVE_COUNT = 14
CHANNELS = 16

# Registers, as offsets in REGISTER_PAGE; add the channel.
FREQ_LOW, FREQ_MIDDLE, FREQ_HIGH = 0x00, 0x10, 0x20
WAVE_SELECT = 0x50                  # the wave's number in the upper nibble
AMPLITUDE = 0x60
CONTROL = 0x70                      # bit 5 modulate, bit 4 invert, bits 3-0 stereo
ALTERNATE = 0x80                    # the alternate bank

FULL = 0x80                         # the loudest amplitude
DB_PER_STEP = 20 * math.log10(2) / 16

# Stereo positions (control bits 3-0): the left share of six slots.
CENTRE = 13                         # 3 of 6 left (11-15 are 5 down to 1)
LEFT = 8
RIGHT = 0


def dac_level(code: int) -> int:
    """A magnitude code's level (the DAC's decode law)."""
    chord, step = code >> 4, code & 15
    return (1 << chord) * (2 * step + 33) - 33


DAC_LEVELS = [dac_level(code) for code in range(128)]
FULL_LEVEL = DAC_LEVELS[127]


def encode_sample(value: float) -> int:
    """A linear value, -1 to 1, as a wave byte: sign and nearest magnitude."""
    level = min(abs(value), 1.0) * FULL_LEVEL
    code = min(range(128), key=lambda c: abs(DAC_LEVELS[c] - level))
    return (0x80 if value >= 0 else 0x00) | code


def decode_sample(byte: int) -> float:
    level = DAC_LEVELS[byte & 0x7F] / FULL_LEVEL
    return level if byte & 0x80 else -level


def amplitude_for(db: float) -> int:
    """The amplitude for a gain in dB (0 or less)."""
    return max(0, FULL - round(-db / DB_PER_STEP))


def frequency_register(hz: float) -> int:
    """The 24-bit frequency for a pitch; bit 0 clear (set is phase-set)."""
    return round(hz * (1 << 24) / SAMPLE_RATE) & 0xFFFFFE


def frequency_of(register: int) -> float:
    return register * SAMPLE_RATE / (1 << 24)


# Waves

def harmonic_wave(amplitudes: dict[int, float]) -> bytes:
    """One cycle of a sum of harmonics (harmonic number -> amplitude),
    normalised to full scale."""
    values = [sum(a * math.sin(2 * math.pi * n * i / WAVE_BYTES) for n, a in amplitudes.items())
              for i in range(WAVE_BYTES)]
    peak = max(abs(v) for v in values)
    return bytes(encode_sample(v / peak) for v in values)


WAVES = {
    "sine": harmonic_wave({1: 1.0}),
    "horn": harmonic_wave({1: 1.0, 2: 0.55, 3: 0.3, 4: 0.15, 5: 0.07}),
    "trumpet": harmonic_wave({1: 1.0, 2: 0.9, 3: 0.75, 4: 0.6, 5: 0.45, 6: 0.33, 7: 0.22, 8: 0.14}),
    "trombone": harmonic_wave({1: 1.0, 2: 0.8, 3: 0.6, 4: 0.4, 5: 0.25, 6: 0.15}),
    "violin": harmonic_wave({n: n ** -1.4 for n in range(1, 11)}),
    "strings": harmonic_wave({n: n ** -1.3 for n in range(1, 11)}),
    "cello": harmonic_wave({n: n ** -1.2 for n in range(1, 10)}),
    "bass": harmonic_wave({1: 1.0, 2: 0.75, 3: 0.5, 4: 0.3, 5: 0.18, 6: 0.1}),
    "flute": harmonic_wave({1: 1.0, 2: 0.2, 3: 0.08}),
    "oboe": harmonic_wave({1: 0.45, 2: 0.8, 3: 1.0, 4: 0.75, 5: 0.5, 6: 0.3, 7: 0.18}),
    "clarinet": harmonic_wave({1: 1.0, 2: 0.04, 3: 0.6, 5: 0.35, 7: 0.2, 9: 0.1}),
    "harp": harmonic_wave({1: 1.0, 2: 0.35, 3: 0.15, 4: 0.05}),
    "timpani": harmonic_wave({1: 1.0, 2: 0.5, 3: 0.3, 4: 0.12}),
}
WAVE_NUMBERS = {name: number for number, name in enumerate(WAVES)}


# Pitches: MIDI note numbers, A4 = 69 = 440Hz.

NOTE_NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
LOWEST_NOTE = 24                    # C1
NOTES = 96                          # C1 to B8


def note_number(name: str) -> int:
    """'A4', 'C#5', 'Bb3' as a MIDI note number."""
    pitch = NOTE_NAMES[name[0]]
    rest = name[1:]
    while rest and rest[0] in "#b":
        pitch += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    return 12 * (int(rest) + 1) + pitch


def note_hz(note: int) -> float:
    return 440 * 2 ** ((note - 69) / 12)


PITCHES = [frequency_register(note_hz(LOWEST_NOTE + i)) for i in range(NOTES)]


# Instruments and scores

@dataclass(frozen=True)
class Instrument:
    """A wave, an envelope and a place: up by attack amplitude steps a
    tick to FULL, down by decay to sustain, held; at a note's end, down by
    release to silence. Its unit of pitch, for detuning and vibrato, is the
    note's frequency shifted right by shift (8: 6.8 cents); vibrato, two
    units either side at 6.25Hz, starts vibrato ticks into a note (0: none)."""
    wave: str
    attack: int
    decay: int
    sustain: int
    release: int
    stereo: int = CENTRE
    shift: int = 8
    vibrato: int = 0

    def release_ticks(self) -> int:
        """The longest release, from FULL."""
        return -(-FULL // self.release)


# A voice is a list of events:
#   ("instrument", name)            take an instrument (its wave and stereo now)
#   ("volume", steps)               play this many amplitude steps quieter
#   ("pan", position)               a stereo position other than the instrument's
#   ("detune", units)               detune notes from here on (signed)
#   ("note", note number, ticks)    start a note, for so many ticks
#   ("hold", ticks)                 keep on, for so many more
#   ("rest", ticks)                 release, for so many
# The score format, a stream per voice: a note's index in the pitch table
# (0 to NOTES - 1), HOLD or REST, each with a length in ticks, 1-255;
# INSTRUMENT and an instrument's number; VOLUME and steps; PAN and a
# position; DETUNE and units (two's complement); LOOP, back to the start.
DETUNE = 0xF9
PAN = 0xFA
VOLUME = 0xFB
INSTRUMENT = 0xFC
HOLD = 0xFD
REST = 0xFE
LOOP = 0xFF
Event = tuple


def voice_bytes(voice: list[Event]) -> bytes:
    out = bytearray()
    for event in voice:
        kind = event[0]
        if kind == "instrument":
            out += bytes([INSTRUMENT, list(INSTRUMENTS).index(event[1])])
        elif kind == "volume":
            assert 0 <= event[1] <= FULL
            out += bytes([VOLUME, event[1]])
        elif kind == "pan":
            assert 0 <= event[1] <= 15
            out += bytes([PAN, event[1]])
        elif kind == "detune":
            assert -8 <= event[1] <= 8
            out += bytes([DETUNE, event[1] & 0xFF])
        elif kind == "note":
            index = event[1] - LOWEST_NOTE
            assert 0 <= index < NOTES and 1 <= event[2] <= 255, event
            out += bytes([index, event[2]])
        else:
            assert 1 <= event[1] <= 255, event
            out += bytes([HOLD if kind == "hold" else REST, event[1]])
    out.append(LOOP)
    return bytes(out)


def timed(kind: str, ticks: int, note: int | None = None) -> list[Event]:
    """A note, hold or rest of any length, as events of at most 255 ticks."""
    events = []
    while ticks > 0:
        part = min(ticks, 255)
        if kind == "note":
            events.append(("note", note, part))
            kind = "hold"
        else:
            events.append((kind, part))
        ticks -= part
    return events


def voice_ticks(voice: list[Event]) -> int:
    return sum(event[-1] for event in voice if event[0] in ("note", "hold", "rest"))


def parse(instrument: str, text: str, ticks_per_unit: int, gap: int = 1) -> list[Event]:
    """'A4:4 C5:2 r:2' (lengths in units) as a voice, each note released gap
    ticks before the next."""
    events: list[Event] = [("instrument", instrument)]
    for token in text.split():
        name, units = token.split(":")
        ticks = int(units) * ticks_per_unit
        if name == "r":
            events += timed("rest", ticks)
        else:
            events += timed("note", ticks - gap, note_number(name)) + timed("rest", gap)
    return events


# The player, as M5PLAY runs it: one tick per vertical sync.

ATTACK, DECAY, SUSTAIN, RELEASE = range(4)


@dataclass
class VoiceState:
    position: int = 0               # into its byte stream
    ticks: int = 1                  # left of the current event; the first tick fetches
    level: int = 0                  # the envelope's
    phase: int = RELEASE
    quieter: int = 0                # steps below the envelope
    instrument: Instrument | None = None
    detune: int = 0
    frequency: int = 0
    unit: int = 0
    vibrato_count: int = 0
    lfo: int = 0


@dataclass
class Player:
    """A model of the player: tick() advances every voice as M5PLAY does
    and returns the writes it makes, (register offset, value)."""
    score: "Score"
    streams: list[bytes] = field(init=False)
    states: list[VoiceState] = field(init=False)

    def __post_init__(self):
        self.streams = self.score.streams()
        self.states = [VoiceState() for _ in self.streams]

    def amplitudes(self) -> list[int]:
        return [max(0, s.level - s.quieter) for s in self.states]

    @staticmethod
    def frequency_writes(channel: int, state: VoiceState) -> list[tuple[int, int]]:
        return [(FREQ_LOW + channel, state.frequency & 0xFE), (FREQ_MIDDLE + channel, state.frequency >> 8 & 0xFF),
                (FREQ_HIGH + channel, state.frequency >> 16)]

    def tick(self) -> list[tuple[int, int]]:
        writes = []
        instruments = list(INSTRUMENTS)
        for channel, (stream, state) in enumerate(zip(self.streams, self.states)):
            started = False
            state.ticks -= 1
            if state.ticks == 0:
                while True:
                    byte = stream[state.position]
                    if byte == LOOP:
                        state.position = 0
                        continue
                    argument = stream[state.position + 1]
                    state.position += 2
                    if byte == INSTRUMENT:
                        state.instrument = INSTRUMENTS[instruments[argument]]
                        writes += [(WAVE_SELECT + channel, WAVE_NUMBERS[state.instrument.wave] << 4),
                                   (CONTROL + channel, state.instrument.stereo)]
                    elif byte == VOLUME:
                        state.quieter = argument
                    elif byte == PAN:
                        writes.append((CONTROL + channel, argument))
                    elif byte == DETUNE:
                        state.detune = argument - 256 if argument & 0x80 else argument
                    else:
                        break
                state.ticks = argument
                if byte == REST:
                    state.phase = RELEASE
                elif byte != HOLD:
                    pitch = PITCHES[byte]
                    state.unit = pitch >> state.instrument.shift & 0xFFFF
                    state.frequency = (pitch + state.detune * state.unit) & 0xFFFFFF
                    writes += self.frequency_writes(channel, state)
                    state.vibrato_count = state.instrument.vibrato
                    state.lfo = 0
                    state.phase = ATTACK
                    started = True
            instrument = state.instrument
            if not started and instrument and instrument.vibrato:
                if state.vibrato_count:
                    state.vibrato_count -= 1
                else:
                    state.lfo = (state.lfo + 1) & 7
                    step = state.unit if VIBRATO_UP[state.lfo] else -state.unit
                    state.frequency = (state.frequency + step) & 0xFFFFFF
                    writes += self.frequency_writes(channel, state)
            if state.phase == ATTACK:
                state.level = min(FULL, state.level + instrument.attack)
                if state.level == FULL:
                    state.phase = DECAY
            elif state.phase == DECAY:
                state.level = max(instrument.sustain, state.level - instrument.decay)
                if state.level == instrument.sustain:
                    state.phase = SUSTAIN
            elif state.phase == RELEASE:
                state.level = max(0, state.level - instrument.release)
            writes.append((AMPLITUDE + channel, max(0, state.level - state.quieter)))
        return writes


VIBRATO_UP = [1, 1, 1, 0, 0, 0, 0, 1]    # the triangle: up a unit into each tick, or down


# Scores

@dataclass(frozen=True)
class Score:
    voices: list[list[Event]]

    def streams(self) -> list[bytes]:
        return [voice_bytes(v) for v in self.voices]

    def ticks(self) -> int:
        lengths = {voice_ticks(v) for v in self.voices}
        assert len(lengths) == 1, "the voices keep different time"
        return lengths.pop()


MAX_VOICES = CHANNELS

# An orchestra. Each instrument's wave is a guess at its spectrum, a sum of
# harmonics; its envelope, in amplitude steps (0.38dB) a tick (20ms).
INSTRUMENTS = {
    "tone": Instrument("sine", attack=128, decay=0, sustain=FULL, release=128, stereo=RIGHT),
    "horn": Instrument("horn", attack=10, decay=1, sustain=0x78, release=5, stereo=12, shift=9, vibrato=12),
    "trumpet": Instrument("trumpet", attack=24, decay=2, sustain=0x74, release=6, stereo=14, shift=9, vibrato=14),
    "trombone": Instrument("trombone", attack=10, decay=1, sustain=0x7C, release=5, stereo=15),
    "violin": Instrument("violin", attack=12, decay=1, sustain=0x7A, release=6, stereo=11, shift=8, vibrato=6),
    "strings": Instrument("strings", attack=4, decay=1, sustain=0x74, release=5, stereo=12, shift=9, vibrato=10),
    "cello": Instrument("cello", attack=4, decay=1, sustain=0x74, release=5, stereo=14, shift=9, vibrato=12),
    "bass": Instrument("bass", attack=6, decay=0, sustain=FULL, release=5, stereo=15),
    "flute": Instrument("flute", attack=10, decay=1, sustain=0x78, release=6, stereo=13, shift=9, vibrato=8),
    "oboe": Instrument("oboe", attack=16, decay=1, sustain=0x78, release=8, stereo=13, shift=9, vibrato=8),
    "clarinet": Instrument("clarinet", attack=14, decay=1, sustain=0x78, release=8, stereo=14),
    "harp": Instrument("harp", attack=128, decay=2, sustain=0, release=6, stereo=11),
    "timpani": Instrument("timpani", attack=128, decay=1, sustain=0, release=4, stereo=13),
}

# One voice, long notes: for measuring pitch.
SCALE_NOTES = ["A3", "A4", "E5", "C6"]
SCALE_TICKS = 25
SCALE = Score([parse("tone", " ".join(f"{n}:{SCALE_TICKS}" for n in SCALE_NOTES), 1)])


def scores() -> dict[str, Score]:
    from stratagem import overture
    return {"scale": SCALE, "overture": overture.SCORE}


def score_source(name: str, score: Score) -> list[str]:
    """A score's voice table, in the layout of the player's (its number of
    voices and their streams), and its streams."""
    voices = len(score.voices)
    assert voices <= MAX_VOICES
    pad = ["0"] * (MAX_VOICES - voices)
    lines = [f".score_{name}",
             f"    EQUB {voices}",
             "    EQUB " + ", ".join([f"LO(score_{name}_{i})" for i in range(voices)] + pad),
             "    EQUB " + ", ".join([f"HI(score_{name}_{i})" for i in range(voices)] + pad)]
    for index, data in enumerate(score.streams()):
        lines.append(f".score_{name}_{index}")
        lines += ["    EQUB " + ", ".join(f"&{b:02X}" for b in data[i:i + 16]) for i in range(0, len(data), 16)]
    return lines


def common_source() -> str:
    """The player's constants, waves, pitches and instruments."""
    waves = list(WAVES.values())
    waves += [bytes(WAVE_BYTES)] * (len(waves) % 2)     # whole pages
    assert len(waves) <= WAVE_COUNT
    lines = ["\\ Generated by stratagem.music5000: do not edit.",
             f"MAX_VOICES = {MAX_VOICES}",
             f"WAVES = {len(waves)}",
             f"DETUNE = &{DETUNE:02X}",
             f"PAN = &{PAN:02X}",
             f"VOLUME = &{VOLUME:02X}",
             f"INSTRUMENT = &{INSTRUMENT:02X}",
             f"HOLD = &{HOLD:02X}",
             f"REST = &{REST:02X}",
             f"LOOP = &{LOOP:02X}",
             f"FULL = &{FULL:02X}",
             f"PITCH_FIRST = {PITCHES[0]}",
             ".waves"]
    for wave in waves:
        lines += ["    EQUB " + ", ".join(f"&{b:02X}" for b in wave[i:i + 16]) for i in range(0, WAVE_BYTES, 16)]
    for name, shift in (("low", 0), ("middle", 8), ("high", 16)):
        values = [p >> shift & 0xFF for p in PITCHES]
        lines.append(f".pitch_{name}")
        lines += ["    EQUB " + ", ".join(f"&{v:02X}" for v in values[i:i + 16]) for i in range(0, NOTES, 16)]
    instruments = list(INSTRUMENTS.values())
    for name, values in (("attack", [i.attack for i in instruments]), ("decay", [i.decay for i in instruments]),
                         ("sustain", [i.sustain for i in instruments]), ("release", [i.release for i in instruments]),
                         ("wave", [WAVE_NUMBERS[i.wave] << 4 for i in instruments]),
                         ("stereo", [i.stereo for i in instruments]),
                         ("shift", [i.shift for i in instruments]),
                         ("vibrato", [i.vibrato for i in instruments])):
        lines += [f".instrument_{name}s", "    EQUB " + ", ".join(f"&{v:02X}" for v in values)]
    return "\n".join(lines) + "\n"


def generate(generated_dirpath) -> None:
    """music5000.asm, the player's tables, and m5_<score>.asm, each score."""
    (generated_dirpath / "music5000.asm").write_text(common_source())
    for name, score in scores().items():
        lines = ["\\ Generated by stratagem.music5000: do not edit."] + score_source(name, score)
        (generated_dirpath / f"m5_{name}.asm").write_text("\n".join(lines) + "\n")
