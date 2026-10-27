# The Music 5000: driving it directly

Experiments in playing music on the Hybrid Music 5000 without its ROM
software (AMPLE), for the title screen, the loading screen and perhaps the
game. Beebium emulates the board (`--hybrid-music-5000`, from 0.15.0); its
own documentation is `docs/music-5000.md` and `docs/music5000/` in the
Beebium tree, and the `beebium-music-5000` session knows it well.

The code: `tools/stratagem/music5000.py` (the encodings, waves, pitches,
score format, and a model of the player), `asm/music5000.asm` (the player),
`asm/m5play.asm` (`M5PLAY`, which plays a tune from the vertical sync event;
`M5SCALE`, one voice of long notes; `M5LOAD`, the music while a file loads
again and again), `asm/m5title.asm` (`M5TITLE`, the title screen with
music), `tools/stratagem/overture.py` (the Stratagem Overture, from MIDI),
`tools/stratagem/midi.py` (MIDI files, through mido),
`tests/test_music5000.py`. `uv run strat-m5-record` records the overture
to `build/features/overture.wav`.

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
OSBYTE 14,4), up to sixteen voices, each a channel. A voice is a stream of
events, two bytes each: a note (an index into a 96-note pitch table) and its
length in ticks; HOLD (keep it on) or REST (release it) and a length; a
change of instrument or volume. An instrument is a wave and an envelope of
attack, decay, sustain and release, in amplitude steps a tick, and a place
in the stereo field; a voice's volume makes it so many steps quieter. Waves
are made from harmonics in Python.

What we measured, on both machines (`tests/test_music5000.py`):

- **It plays as the model says:** each voice's envelope, phase, ticks and
  volume match the Python model's, tick by tick, through the whole overture
  and into its loop.
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
- **Time:** 96 beats a minute, 31.25 ticks a quarter, each note's start and
  end to the nearest tick.
- **Shaped dynamics,** which the file doesn't have: a quiet opening that
  swells, a withdrawn B minor, a swell and a timpani roll into the tutti, a
  bare coda, and a last full chord of D. Long notes change volume as they
  sound.
- **Weight:** the first version sounded high and thin, so the bass,
  cellos, trombones and timpani are louder than the file has them, the bass
  is doubled (detuned), the timpani and the violins play an octave down
  (the violins' ostinato reached D7), and the violins' wave is softer. That
  moved about 6dB from above 1kHz to below 250Hz.
- **Space:** the strings' chords spread across the stereo field; where a
  channel is free, each melody is doubled on a second channel slightly
  detuned (an ensemble), and echoed, quieter, on the other side.
- **Sixteen channels.** The sustained parts move from chord to chord on
  the same channels, legato; the other notes take a channel whose release
  has finished, or cut one short. The decorations take only what's left,
  never displacing the score: about a third of them fit, mostly in the
  opening and the woodwinds' section (the tutti fills all sixteen).
- **The player's vibrato:** a triangle of eight ticks (6.25Hz), two units
  either side, the unit being the note's frequency shifted right (by 8: 6.8
  cents); it starts some ticks into a note. The same unit detunes.
- **The cost,** with vibrato on most voices: about 2700 cycles a tick, up
  to 12000 when many voices start notes at once. Under the title, whose
  line interrupt takes more than half the CPU, that still fits a frame.

### After the board: processing its output

`uv run strat-m5-master` simulates what an analogue or simple digital chain
after a real board's output might add (`tools/stratagem/m5_master.py` has
the details): a low cut at 25Hz; EQ, +6dB shelf below 120Hz, +2dB at 250Hz
and at 3kHz; gentle valve- or tape-like saturation; bus compression, 2.5:1
above -20dBFS; a concert hall's reverb, 2.2s, a quarter of the mix; a
little stereo width. It writes `build/features/overture-processed.wav`
from the recording.

## In STRAT's title

STRAT plays the overture under the title (`asm/host_music.asm`): MUSIC, the
player and the score (12.7K), is assembled with the host at `&3000` and
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

## To try next

- **Music in the game.** The host's frame is busy, but a tick is cheap: 1%
  of a frame on average, 2% at worst, for four voices. The game's host
  already has the vertical sync; the score could come from the parasite.
- **The overture, interpreted.** The mood (`art/music/style.md`) and the
  board's sound suggest changes (see the decisions to come).
- **Detecting the board,** so that a machine without one needn't load
  MUSIC: it can't be read back, so perhaps ask the player.
- **Modulation** (the alternate bank): a channel switches its neighbour
  between the two banks on its own wave's sign, which gives ring- and
  FM-like sounds.
- **The Music 5000 as an option:** detect it (it can't be read back, so
  perhaps ask the player), and fall back to the SN76489 or silence.
