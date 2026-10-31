"""The Music 5000, driven directly: the board's encodings, wave tables, a
pitch table and an orchestra of instruments, for the player that plays
music without AMPLE (asm/music5000.asm; stratagem.sequencer has its score
format and its model).

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
    # Harmonics to the twelfth, heard on small speakers; their signs (sine
    # phases) chosen for the lowest peak, so the fundamental stays strong.
    "timpani": harmonic_wave({1: 1.0, 2: 0.7, 3: -0.55, 4: 0.42, 5: -0.32, 6: -0.24, 7: 0.17, 8: -0.12,
                              10: -0.07, 12: 0.04}),
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


# Instruments

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


# How a voice plays an instrument's envelope, a phase at a time; and its
# vibrato's triangle: up a unit into each tick, or down.
ATTACK, DECAY, SUSTAIN, RELEASE = range(4)
VIBRATO_UP = [1, 1, 1, 0, 0, 0, 0, 1]

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
    # The game's (docs/musical-direction.md), after the title's: the title's
    # player has tables only for those (TITLE_INSTRUMENTS).
    # Struck, bright and brief, its character all envelope.
    "celesta": Instrument("trumpet", attack=128, decay=6, sustain=0, release=10, stereo=13),
    # A reed in the low register, still, its notes short.
    "bassoon": Instrument("oboe", attack=8, decay=1, sustain=0x74, release=10, stereo=14),
    # Far: a slower attack, no vibrato, nearer silent sustain.
    "far_horn": Instrument("horn", attack=4, decay=1, sustain=0x70, release=4, stereo=11, shift=9),
    # Still: no vibrato, colder.
    "still_strings": Instrument("strings", attack=4, decay=1, sustain=0x74, release=5, stereo=12, shift=9),
    "still_cello": Instrument("cello", attack=4, decay=1, sustain=0x74, release=5, stereo=14, shift=9),
    "still_oboe": Instrument("oboe", attack=16, decay=1, sustain=0x78, release=8, stereo=13, shift=9),
    # A drone with no beginning: over 2.5s to full, and as long to fade.
    "drone": Instrument("cello", attack=1, decay=0, sustain=FULL, release=1, stereo=13, shift=9),
    # Glass: a pure tone, swelling and fading slowly; a pair detuned beats.
    "glass": Instrument("sine", attack=2, decay=0, sustain=FULL, release=2, stereo=13, shift=8),
    # Plucked: struck, and dying away in half a second, a bass's in a
    # little under a second; a drip, pure, ringing a second and more.
    "pizzicato": Instrument("strings", attack=128, decay=5, sustain=0, release=8, stereo=12),
    "plucked_bass": Instrument("bass", attack=128, decay=3, sustain=0, release=6, stereo=13),
    "drip": Instrument("sine", attack=128, decay=2, sustain=0, release=3, stereo=15),
}
TITLE_INSTRUMENTS = 13              # the overture's orchestra, first
MAX_INSTRUMENTS = 32
assert len(INSTRUMENTS) <= MAX_INSTRUMENTS


def tables_source() -> list[str]:
    """The player's waves, pitches and instruments, and their constants."""
    waves = list(WAVES.values())
    waves += [bytes(WAVE_BYTES)] * (len(waves) % 2)     # whole pages
    assert len(waves) <= WAVE_COUNT
    lines = [f"MAX_VOICES = {MAX_VOICES}",
             f"WAVES = {len(waves)}",
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
    assert all(i.shift >= 8 for i in instruments), "a unit is the pitch's top two bytes, shifted"
    for name, values in (("attack", [i.attack for i in instruments]), ("decay", [i.decay for i in instruments]),
                         ("sustain", [i.sustain for i in instruments]), ("release", [i.release for i in instruments]),
                         ("wave", [WAVE_NUMBERS[i.wave] << 4 for i in instruments]),
                         ("stereo", [i.stereo for i in instruments]),
                         ("shift", [i.shift - 8 for i in instruments]),      # (8 or more)
                         ("vibrato", [i.vibrato for i in instruments])):
        lines += [f".instrument_{name}s", "    EQUB " + ", ".join(f"&{v:02X}" for v in values[:TITLE_INSTRUMENTS])]
        # (The game's instruments only where the includer has them all)
        lines += ["IF FULL_ORCHESTRA", "    EQUB " + ", ".join(f"&{v:02X}" for v in values[TITLE_INSTRUMENTS:]),
                  "ENDIF"]
    return [f"MAX_INSTRUMENTS = {MAX_INSTRUMENTS}"] + lines
