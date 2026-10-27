# The Music 5000: driving it directly

Experiments in playing music on the Hybrid Music 5000 without its ROM
software (AMPLE), for the title screen, the loading screen and perhaps the
game. Beebium emulates the board (`--hybrid-music-5000`, from 0.15.0); its
own documentation is `docs/music-5000.md` and `docs/music5000/` in the
Beebium tree, and the `beebium-music-5000` session knows it well.

The code: `tools/stratagem/music5000.py` (the encodings, waves, pitches,
score format, and a model of the player), `asm/m5play.asm` (`M5PLAY`, which
plays a tune; `M5SCALE`, one voice of long notes), `tests/test_music5000.py`.

## What the board does, and what's left to the host

The board is a fixed-program DSP on the 1 MHz bus: sixteen channels, each a
24-bit frequency added to a phase every sample (46875 a second), a 128-byte
wave looked up at the phase's top seven bits, an amplitude added in the log
domain, and a stereo position. That is all it does. Envelopes, vibrato,
note lengths and sequencing are the host's: AMPLE is one program that does
them, from a 100Hz interrupt, and nothing it sets up is needed otherwise.
**So the ROM isn't needed.** M5PLAY plays without it, on the B+ and the
Integra-B.

- **Its RAM, 2K, write-only,** through JIM: write a page to `&FCFF`, then
  `&FD00`-`&FDFF` is that page. Pages `&30`-`&3F` (bit 0 ignored) are eight
  blocks of 256: fourteen waves at `&000`-`&6FF`, then the registers, a row
  of sixteen (a byte per channel) for each: frequency low, middle and high
  (`+&00`, `+&10`, `+&20`), wave select (`+&50`, upper nibble), amplitude
  (`+&60`), control (`+&70`: bit 5 modulate, bit 4 invert, bits 3-0
  stereo). The normal bank is at `&700`, the alternate (used only with
  modulation) at `&780`; both are in page `&3E`.
- **Sharing the page register.** `&FCFF` can't be read: a read loads it
  from the floating bus (so no read-modify-write, and no indexed store
  whose dummy read lands on it). The OS keeps a copy at `&EE`: write `&EE`
  first, then `&FCFF`; an interrupt-time writer saves `&EE`, does its
  writes, and puts both back from it. AMPLE does exactly this. (Beebium
  doesn't model the corruption a read causes, so tests won't catch one.)
- **Samples and amplitudes are logarithmic.** A wave byte is a sign (bit 7
  set: positive) and a 7-bit log magnitude, as the AM6070 DAC takes it:
  chord in bits 6-4, step in 3-0. The amplitude adds to the magnitude:
  `&80` is full, each step down about 0.38dB (16 to a halving), and 0
  silent. A new amplitude takes effect at the channel's next wave wrap, so
  with waves that start at zero, envelopes and note-offs don't click.
  Frequency changes take effect at once, phase-continuous, so vibrato and
  slides are free of clicks too.
- **Starting it.** On a real board RAM, phases and amplitudes start random
  (Beebium starts them at zero), and BREAK clears only the normal bank. So
  clear all 2K, write the waves, and set every channel running (a non-zero
  frequency) at amplitude 0, so that each takes the 0 at its next wrap.
- **The level is low by design:** one channel at full scale is about a
  sixteenth of full scale out.

## M5PLAY

A player of four voices, one tick a frame, from the OS's vertical sync
event (`EVNTV`, OSBYTE 14,4). Each voice is a channel with a stream of
notes and rests (a byte for the note, an index into a 96-note pitch table,
and a byte for its length in ticks), and an instrument: a wave, and an
envelope of attack, decay, sustain and release in amplitude steps per tick.
The tune is a placeholder: eight bars in A minor, lead, arpeggio, bass and
a noise hi-hat. Waves are made from harmonics in Python.

What we measured, on both machines (`tests/test_music5000.py`):

- **The cost to the host:** a tick of four voices is about 350 cycles
  (175us), 766 at most, under 1% of a frame on average, 2% at the worst.
  The 1 MHz bus stretches each write to `&FDxx` by a cycle or two, which is
  a small part of that; the player's own logic is the rest.
- **It plays as the model says:** each voice's level, phase and ticks match
  the Python model's, tick by tick, through the whole tune and its loop.
- **In tune:** M5SCALE's notes come out within 0.3% of their pitch.
- Recordings: `build/features/m5play-<machine>.wav` (made by a scratch
  script; the tests don't write them).

## To try next

- **Music under the title screen.** The System VIA's interrupts are off
  then, so there is no vertical sync event: tick from the line interrupt's
  count of lines, or from the title's main loop.
- **Music while the game loads,** through the OS and the filing system.
  The vertical sync event keeps running, but how late do the ticks come,
  with the DFS holding interrupts off?
- **Music in the game:** the host's frame is busy, but a tick is cheap.
- **Modulation** (the alternate bank): a channel switches its neighbour
  between the two banks on its own wave's sign, which gives ring- and
  FM-like sounds.
