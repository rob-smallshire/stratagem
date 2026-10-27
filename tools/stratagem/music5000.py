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
import random
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


def noise_wave(seed: int = 5000) -> bytes:
    rng = random.Random(seed)
    return bytes(encode_sample(rng.uniform(-1, 1)) for _ in range(WAVE_BYTES))


WAVES = {
    "sine": harmonic_wave({1: 1.0}),
    "square": harmonic_wave({n: 1 / n for n in range(1, 12, 2)}),
    "saw": harmonic_wave({n: 1 / n for n in range(1, 13)}),
    "organ": harmonic_wave({1: 1.0, 2: 0.5, 4: 0.25, 8: 0.12}),
    "noise": noise_wave(),
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
    """A wave and an envelope, in amplitude steps per tick: up by attack to
    FULL, down by decay to sustain, held, then down by release to silence
    for the note's last release_ticks."""
    wave: str
    attack: int
    decay: int
    sustain: int
    release: int
    release_ticks: int
    stereo: int = CENTRE


@dataclass(frozen=True)
class Voice:
    instrument: Instrument
    events: list[tuple[int | None, int]]      # (note number or None for a rest, ticks)


# The score format, one stream per voice: a note (its index into the pitch
# table, 0 to NOTES - 1) and its length in ticks; REST and a length; or LOOP,
# back to the start.
REST = 0xFE
LOOP = 0xFF


def voice_bytes(voice: Voice) -> bytes:
    out = bytearray()
    for note, ticks in voice.events:
        assert 1 <= ticks <= 255
        if note is None:
            out += bytes([REST, ticks])
        else:
            index = note - LOWEST_NOTE
            assert 0 <= index < NOTES
            assert ticks > voice.instrument.release_ticks
            out += bytes([index, ticks])
    out.append(LOOP)
    return bytes(out)


def parse(text: str, ticks_per_unit: int) -> list[tuple[int | None, int]]:
    """'A4:4 C5:2 r:2' (lengths in units) as events."""
    events = []
    for token in text.split():
        name, units = token.split(":")
        events.append((None if name == "r" else note_number(name), int(units) * ticks_per_unit))
    return events


# The player, as M5PLAY runs it: one tick per vertical sync.

ATTACK, DECAY, SUSTAIN, RELEASE = range(4)


@dataclass
class VoiceState:
    position: int = 0               # into its byte stream
    ticks: int = 1                  # left of the current event; the first tick fetches
    level: int = 0                  # the amplitude written
    phase: int = RELEASE
    note: int | None = None         # the pitch table index sounding


@dataclass
class Player:
    """A model of the player: tick() advances every voice as M5PLAY does
    and returns the writes it makes, (register offset, value)."""
    voices: list[Voice]
    streams: list[bytes] = field(init=False)
    states: list[VoiceState] = field(init=False)

    def __post_init__(self):
        self.streams = [voice_bytes(v) for v in self.voices]
        self.states = [VoiceState() for _ in self.voices]

    def tick(self) -> list[tuple[int, int]]:
        writes = []
        for channel, (voice, stream, state) in enumerate(zip(self.voices, self.streams, self.states)):
            instrument = voice.instrument
            state.ticks -= 1
            if state.ticks == 0:
                if stream[state.position] == LOOP:
                    state.position = 0
                byte, ticks = stream[state.position], stream[state.position + 1]
                state.position += 2
                state.ticks = ticks
                if byte == REST:
                    state.phase = RELEASE
                else:
                    state.note = byte
                    pitch = PITCHES[byte]
                    writes += [(FREQ_LOW + channel, pitch & 0xFF), (FREQ_MIDDLE + channel, pitch >> 8 & 0xFF),
                               (FREQ_HIGH + channel, pitch >> 16)]
                    state.phase = ATTACK
            elif state.ticks == instrument.release_ticks:
                state.phase = RELEASE
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
            writes.append((AMPLITUDE + channel, state.level))
        return writes


# Scores

TICKS_PER_SIXTEENTH = 6             # at 50 ticks a second, 125 beats a minute
MAX_VOICES = 6

LEAD = Instrument("saw", attack=32, decay=2, sustain=0x70, release=6, release_ticks=2, stereo=CENTRE)
ARPEGGIO = Instrument("organ", attack=16, decay=4, sustain=0x58, release=8, release_ticks=1, stereo=LEFT + 1)
BASS = Instrument("square", attack=64, decay=2, sustain=0x68, release=8, release_ticks=2, stereo=CENTRE + 1)
HAT = Instrument("noise", attack=128, decay=24, sustain=0, release=24, release_ticks=1, stereo=RIGHT + 4)
TONE = Instrument("sine", attack=128, decay=0, sustain=FULL, release=128, release_ticks=1, stereo=RIGHT)

CHORDS = [("A", "C", "E"), ("F", "A", "C"), ("C", "E", "G"), ("G", "B", "D"),
          ("A", "C", "E"), ("F", "A", "C"), ("G", "B", "D"), ("E", "G#", "B")]

MELODY = """
    E5:4 A5:4 G5:2 E5:2 C5:4
    D5:4 C5:2 A4:2 C5:8
    E5:4 G5:4 C6:4 B5:2 G5:2
    D6:6 B5:2 G5:8
    E5:4 A5:4 B5:2 C6:2 B5:4
    A5:4 F5:4 C6:4 A5:4
    G5:4 F5:2 E5:2 D5:4 B4:4
    G#4:4 B4:4 E5:8
"""


def arpeggio_text() -> str:
    bars = []
    for root, third, fifth in CHORDS:
        bars.append(" ".join(f"{n}:1" for n in [root + "4", third + "4", fifth + "4", third + "4"] * 4))
    return " ".join(bars).replace("C4", "C5").replace("E4", "E5").replace("D4", "D5")


def bass_text() -> str:
    return " ".join(f"{root}2:2 {root}3:2 {root}2:2 {root}3:2 {root}2:2 {root}3:2 {root}2:2 {root}3:2"
                    for root, _, _ in CHORDS)


TUNE = [
    Voice(LEAD, parse(MELODY, TICKS_PER_SIXTEENTH)),
    Voice(ARPEGGIO, parse(arpeggio_text(), TICKS_PER_SIXTEENTH)),
    Voice(BASS, parse(bass_text(), TICKS_PER_SIXTEENTH)),
    Voice(HAT, parse("r:2 C6:2 " * 32, TICKS_PER_SIXTEENTH)),
]

# One voice, long notes: for measuring pitch.
SCALE_NOTES = ["A3", "A4", "E5", "C6"]
SCALE_TICKS = 25
SCALE = [Voice(TONE, [(note_number(n), SCALE_TICKS) for n in SCALE_NOTES])]

SCORES = {"tune": TUNE, "scale": SCALE}


def score_source(name: str, voices: list[Voice]) -> list[str]:
    """A score's voice table, in the layout of M5PLAY's voice variables, and
    its streams."""
    assert len(voices) <= MAX_VOICES
    pad = MAX_VOICES - len(voices)

    def row(values) -> str:
        return "    EQUB " + ", ".join(f"&{v:02X}" for v in list(values) + [0] * pad)

    instruments = [v.instrument for v in voices]
    lines = [f".score_{name}",
             f"    EQUB {len(voices)}",
             "    EQUB " + ", ".join([f"LO(score_{name}_{i})" for i in range(len(voices))] + ["0"] * pad),
             "    EQUB " + ", ".join([f"HI(score_{name}_{i})" for i in range(len(voices))] + ["0"] * pad),
             row(i.attack for i in instruments),
             row(i.decay for i in instruments),
             row(i.sustain for i in instruments),
             row(i.release for i in instruments),
             row(i.release_ticks for i in instruments),
             row(WAVE_NUMBERS[i.wave] << 4 for i in instruments),
             row(i.stereo for i in instruments)]
    for index, voice in enumerate(voices):
        data = voice_bytes(voice)
        lines.append(f".score_{name}_{index}")
        lines += ["    EQUB " + ", ".join(f"&{b:02X}" for b in data[i:i + 16]) for i in range(0, len(data), 16)]
    return lines


def m5play_source() -> str:
    lines = ["\\ Generated by stratagem.music5000: do not edit.",
             f"MAX_VOICES = {MAX_VOICES}",
             f"WAVES = {len(WAVES) + len(WAVES) % 2}",
             f"REST = &{REST:02X}",
             f"LOOP = &{LOOP:02X}",
             f"FULL = &{FULL:02X}",
             f"PITCH_FIRST = {PITCHES[0]}",
             ".waves"]
    waves = list(WAVES.values())
    waves += [bytes(WAVE_BYTES)] * (len(waves) % 2)     # whole pages
    for wave in waves:
        lines += ["    EQUB " + ", ".join(f"&{b:02X}" for b in wave[i:i + 16]) for i in range(0, WAVE_BYTES, 16)]
    for name, shift in (("low", 0), ("middle", 8), ("high", 16)):
        values = [p >> shift & 0xFF for p in PITCHES]
        lines.append(f".pitch_{name}")
        lines += ["    EQUB " + ", ".join(f"&{v:02X}" for v in values[i:i + 16]) for i in range(0, NOTES, 16)]
    for name, voices in SCORES.items():
        lines += score_source(name, voices)
    return "\n".join(lines) + "\n"


def generate(generated_dirpath) -> None:
    (generated_dirpath / "m5play.asm").write_text(m5play_source())
