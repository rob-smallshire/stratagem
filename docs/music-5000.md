# The Music 5000: driving it directly

Experiments in playing music on the Hybrid Music 5000 without its ROM
software (AMPLE), for the title screen, the loading screen and perhaps the
game. Beebium emulates the board (`--hybrid-music-5000`, from 0.15.0); its
own documentation is `docs/music-5000.md` and `docs/music5000/` in the
Beebium tree, and the `beebium-music-5000` session knows it well.

The code: `tools/stratagem/music5000.py` (the encodings, waves, pitches
and instruments), `tools/stratagem/sequencer.py` (the score format, its
encoder, and a model of the player), `asm/music5000.asm` (the player),
`asm/m5play.asm` (`M5PLAY`, which plays a tune from the vertical sync event;
`M5SCALE`, one voice of long notes; `M5LOAD`, the music while a file loads
again and again), `asm/m5title.asm` (`M5TITLE`, the title screen with
music), `tools/stratagem/overture.py` (the Stratagem Overture, from MIDI),
`tools/stratagem/midi.py` (MIDI files, through mido),
`tests/test_music5000.py`, `tests/test_sequencer.py`. `uv run
strat-m5-record` records the overture to `build/features/overture.wav`;
`uv run strat-m5-synth` renders it without the emulator (see below).

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

The player: one tick a frame, from the OS's vertical sync event (`EVNTV`,
OSBYTE 14,4), up to sixteen voices, each a channel, and a conductor. The
score format is the sequencer's (below): notes on a musical clock, in
patterns. An instrument is a wave and an envelope of attack, decay,
sustain and release, in amplitude steps a tick, and a place in the stereo
field; a voice's level makes it so many steps quieter, and the
conductor's makes every voice quieter. Waves are made from harmonics in
Python.

The first player read a stream of two-byte events a voice, timed in ticks;
what's measured below of four voices and of 1100 cycles a tick was of
that one.

What we measured, on both machines (`tests/test_music5000.py`):

- **It plays as the model says:** the conductor's level, and each voice's
  envelope, phase, steps, pitch, level and frequency, match the Python
  model's, tick by tick, through the whole overture and into its loop.
- **In tune:** M5SCALE's notes come out within 0.3% of their pitch.
- **The cost to the host:** with four voices (the first tune), about 350
  cycles a tick (175us), 766 at most. With the overture's sixteen, about
  1100 (under 3% of a frame); about 3000 when every voice starts a note at
  once, and up to 6300 (3ms, 16% of a frame) when they also change
  instrument and volume. The 1 MHz bus stretches each write to `&FDxx` by a
  cycle or two, a small part of that; the player's own logic is the rest.

## The Stratagem Overture

`art/music/Stratagem_Overture.mid`, twelve orchestral tracks, 40 bars, is
the title's music; `art/music/style.md` says what it is to evoke. It is in
four parts: D major, I-vi-IV-V, the theme on the horn, then violins and
trumpets (bars 1-12); B minor, oboe, flute and clarinet (13-24); D major,
tutti, trombone chords and a violin ostinato (25-36); a coda, horn and
trumpets in octaves (37-40).

`stratagem.overture` arranges it for the board; its docstring has the
details.

- **Each track is an instrument** of the orchestra in `stratagem.music5000`:
  a wave (a guess at its spectrum), an envelope, vibrato or none, a level,
  and a place in the stereo field. A note's velocity makes it quieter from
  the track's level (20 log10(v / 127) dB).
- **Time:** 96 beats a minute, in steps of a twentieth of a quarter (1.5625
  ticks).
- **Shaped dynamics,** which the file doesn't have: a quiet opening that
  swells, a withdrawn B minor, a swell and a timpani roll into the tutti, a
  bare coda, and a last full chord of D: the conductor's.
- **Weight:** the first version sounded high and thin, so the bass,
  cellos, trombones and timpani are louder than the file has them, the bass
  is doubled (detuned), the timpani and the violins play an octave down
  (the violins' ostinato reached D7), and the violins' wave is softer. That
  moved about 6dB from above 1kHz to below 250Hz.
- **Space:** the strings' chords spread across the stereo field; where a
  channel is free, each melody is doubled on a second channel slightly
  detuned (an ensemble), and echoed, quieter, on the other side.
- **Sixteen channels,** a phrase of a part's line to each, as the
  sequencer places them. The decorations take only what's left, never
  displacing the score: 168 notes of 609 fit, mostly in the opening and
  the woodwinds' section (the tutti fills all sixteen).
- **The player's vibrato:** a triangle of eight ticks (6.25Hz), two units
  either side, the unit being the note's frequency shifted right (by 8: 6.8
  cents); it starts some ticks into a note. The same unit detunes.
- **The cost,** with vibrato on most voices: about 2550 cycles a tick
  (6% of a frame); 13800 at most, when the piece starts again and every
  voice reads its first events while the last chord's sixteen still
  vibrate. Under the title, whose line interrupt takes more than half the
  CPU, that still fits a frame.

### After the board: processing its output

`uv run strat-m5-master` simulates what an analogue or simple digital chain
after a real board's output might add (`tools/stratagem/m5_master.py` has
the details): a low cut at 25Hz; EQ, +6dB shelf below 120Hz, +2dB at 250Hz
and at 3kHz; gentle valve- or tape-like saturation; bus compression, 2.5:1
above -20dBFS; a concert hall's reverb, 2.2s, a quarter of the mix; a
little stereo width. It writes `build/features/overture-processed.wav`
from the recording.

`docs/auditorium.md` proposes the same chain for Beebium, in real time, on
the emulator's whole mix.

## In STRAT's title

STRAT plays the overture under the title (`asm/host_music.asm`): MUSIC, the
player and the score (5.4K: 1.1K of code, 2.2K of waves and tables, 0.6K
of variables, the overture's 1.7K), is assembled with the host at `&3000` and
loaded into user RAM once the picture is on the shadow screen, where the
picture was; MAIN overwrites it later. The title's wait for SPACE ticks the
music at each vertical sync, as M5TITLE does, and SPACE silences the board
before the game loads. `tests/test_loader.py` checks, on a machine with
the board, that it plays, that the flash bit is still switched in every
line's blanking, and that the game is silent.

## Under the title screen: M5TITLE

While the title shows, the System VIA's interrupts are off, so there's no
vertical sync event. But the System VIA still sets its flag for the
vertical sync (CA1) each frame, so the title's main loop watches the flag
and ticks the music, while the line interrupt switches the flash bit as
before. Nothing in the interrupt changes.

- The ticks come once a frame, within 60us (a line's interrupt may come
  first).
- **The music moved the switch.** The line's handler polls timer 1 every
  10 cycles or so, and with the music running in the foreground, the
  instruction it interrupts varies, so the write moved by up to 10
  columns: a few lines in a thousand landed at column 80-82, where they can
  show at the end of a line. With the idle loop of LOADSCR it had landed at
  the same column every line. Waiting 3us longer (`SWITCH_COUNT` 28, from
  31) puts every write at column 85-96, inside the blanking, on both
  machines; the tests check every line of three frames.

## While a file loads: M5LOAD

The music from the vertical sync event, while the idle loop loads a file
through the OS, again and again (MAIN, 4K; a 20K file took 2.8s a
load on the B+, 2.05s on the Integra-B, in Beebium).

- The event keeps coming. Ticks are at most 0.3ms late on the B+ and 0.6ms
  on the Integra-B (the DFS holds interrupts off at times), and none is
  missed: inaudible.
- So music can play under a loading screen that has nothing timed to the
  line, through any filing system that leaves interrupts on most of the
  time.

## A compact score: the sequencer

The first player's score was the performance, tick by tick: the overture
was 9.7K, a third of it volume changes (the dynamics, written into every
long note) and a quarter holds between them; and the channel each note got
scattered its lines, so what repeats in the music didn't repeat in the
score. For music in the game, where memory is short,
`tools/stratagem/sequencer.py` is a format, an encoder and a model of the
player, which `asm/music5000.asm` runs. It isn't fitted to the overture: a
piece is notes in parts, from MIDI or from Python.

- **A musical clock.** Events are in steps (the overture: a twentieth of a
  quarter); the tempo, the piece's, is steps a tick (16-bit fraction), which
  the player adds up: a carry is a step. At 96 bpm a quarter is 31.25
  ticks, so in ticks a bar of quavers is 16, 15, 16 ... and repeats don't
  encode the same; in steps they do, at any tempo. A step lasts a tick at
  least (20 steps a quarter allows 150 bpm), so a tick passes one step at
  most. The clock starts a hair short of a step, so the first tick reads
  step 0.
- **A conductor.** The dynamics of the whole are a level that every voice
  follows, in straight lines (a slope a step): the overture's swells cost
  130 bytes, not 5K.
- **Phrases kept together.** Each part is split into lines, one note at a
  time, and lines into phrases at a bar's rest; a phrase goes to one
  channel, its line's last if free. Decorations go in whole phrases (split
  at a beat's rest) or not at all: more fit than before (168 notes, from
  111), and they repeat what they decorate.
- **Tokens.** A note is a byte: an interval from the voice's last (-8 to
  +7) and one of the piece's eight commonest slots; a short rest after it
  is folded in as the voice's gap (MML's `q`). Intervals make a phrase
  transposed the same bytes. Pan, detune, instrument and gap are a byte;
  rest, hold, level, pitch and call are two.
- **Patterns.** Re-Pair over all the voices' tokens: the commonest pair
  becomes a pattern, again and again, then patterns that don't save bytes
  are put back, and calls are kept four deep. A pattern costs a RETURN and
  two bytes of address; a call, two bytes.
- **Levels to 1.5dB.** The strings' slow swells, written into their
  velocities chord by chord, otherwise break every pattern.

The overture so is **1,662 bytes** (1,009 in the voices' streams, 40
patterns of 435, 130 the conductor's), against 9,658. Expanded, the
encoding gives back every voice's tokens; played by the model, every note
starts on its tick and channel (`tests/test_sequencer.py`). By ear, it is
indistinguishable from the first player's.

- **The player** (`asm/music5000.asm`) reads a voice's bytes only at its
  steps' end; a call pushes its place on the voice's stack (four deep, 128
  bytes for all sixteen), and a note's unit for vibrato is the pitch's top
  two bytes shifted right once at most (every instrument's shift is 8 or
  9). Its vibrato is inline: most voices vibrate every tick.

`uv run strat-m5-synth` renders a player model's writes to audio with a
software board (`tools/stratagem/m5_synth.py`; its output filter fitted
to Beebium's), to `build/features/overture-synth.wav`. Its rendering of
the first player's overture followed Beebium's recording (the level over
time correlated at 0.98), and the sequencer's version agreed with that one
within about 1dB a section; the decorations differ (more violins doubled,
fewer trumpets).

## To try next

- **Music in the game.** The host's frame is busy, but a tick is cheap: 6%
  of a frame on average for sixteen voices with vibrato, less for fewer.
  The game's host already has the vertical sync; a piece is a K or two, and
  the player and its tables 3.3K (the waves, 1.8K of it, needed only to
  start the board). "Play one of these patterns", chosen at random, would
  let a few phrases vary for as long as the game is played.
- **The overture, interpreted.** The mood (`art/music/style.md`) and the
  board's sound suggest changes (see the decisions to come).
- **Detecting the board,** so that a machine without one needn't load
  MUSIC: it can't be read back, so perhaps ask the player.
- **Modulation** (the alternate bank): a channel switches its neighbour
  between the two banks on its own wave's sign, which gives ring- and
  FM-like sounds.
- **The Music 5000 as an option:** detect it (it can't be read back, so
  perhaps ask the player), and fall back to the SN76489 or silence.
