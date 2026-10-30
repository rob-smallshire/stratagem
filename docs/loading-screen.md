# The loading screen: what we tried and what we learned

The cover art shown in MODE 1 with more colours than MODE 1 has, by
switching the Video ULA's flash bit every scan line, and an attempt to keep
it up, unspoilt, while the game loads beneath it through the OS. The
picture works. Loading beneath it works, but not cleanly. This is the
record of how far it got and why, and of the direction taken from here.

The code: `tools/stratagem/loading_screen.py` (the dither, the screen
bytes, a simulation of what the ULA shows), `tools/stratagem/loading_lab.py`
(`uv run strat-loading-lab`, comparison sheets in `build/features/`),
`asm/loading_screen.asm` (the interrupt), `asm/loadscr.asm` (LOADSCR, the
picture alone) and `show_loading_screen` in `asm/host_low.asm` (STRAT's
loader). Tests: `tests/test_loading_screen.py`, `tests/test_loader.py`.

## The picture

MODE 1 shows four logical colours. Set some of them to *flashing* physical
colours (8-15) and the flash bit in the ULA's control register (`&FE20`,
bit 0) swaps each for its complement: red and cyan, green and magenta, blue
and yellow, black and white. Toggle the bit every line and even lines show
one of each pair, odd lines the other.

- **Six colours, KWCY/KWRB.** Black and white steady, the other two
  logical colours flashing cyan/red and yellow/blue. Control `&D8` on even
  lines, `&D9` on odd. With all four flashing, eight colours show, but no
  line has both black and white, so nothing is darker than a sixth or
  lighter than five sixths in linear light: the cover's black outlines go
  grey. Seven (steady black) was close; six keeps the whites crisper. The
  lab compares all of these with plain MODE 1 and MODE 2.
- **The dither knows each line's palette.** Error diffusion pushes error
  down onto a line with the other palette, which makes it up there: even
  lines can't show white nor odd lines black, but between them they
  average to the grey asked for. Mix in linear light and choose the
  nearest colour there too (choosing in Oklab made flat greys lighter).
- **The art** is `art/cover/stratagem-4x3.png`, scaled to 320x256 and
  dithered. On a 4:3 display MODE 1's pixels are not square; a picture
  composed for the screen it will be shown on does better than one
  scaled to it.
- **Beebium shows it exactly** from 0.15.0 (it draws the flash bit from the
  pixel after the write, beebium #226), so a test compares a captured
  frame of LOADSCR with the simulation, line for line.

## Switching every line

The switch must land in the horizontal blanking, every line, for the whole
frame.

- **Timing.** With interlace off (`*TV 0,1`), a frame is 312 lines of
  exactly 64us, and the User VIA's timers count at 1MHz from the same
  crystal. So timer 1, free-running with a latch of 62 (a period of 64us),
  interrupts at the same place in every line. Both timers are started once,
  just after a vertical sync seen on the System VIA's CA1.
- **Where a write takes effect.** A write to `&FE20` at CRTC column c
  shows from about column c - 2. With 80 columns displayed (of 128) the
  safe window is column 82 round to column 1 of the next line, 48 columns,
  24us.
- **The handler is entered early and waits.** Timer 1 interrupts about
  20us before the switch is due; the handler spins on timer 1's count
  until it is below `SWITCH_COUNT`, then writes. So another interrupt that
  delays it, but is over in time, costs nothing. A longer lead buys more
  slack but takes the CPU from the loading: about 45us of each 64 starved
  it (it looked like a hang); about 20us costs a few percent.
- **The line's parity comes from timer 2, not from counting.** Timer 2,
  left counting down at 1MHz, changes bit 6 every 64us; a frame is an even
  number of lines and the count wraps every 65536us, a multiple of 128, so
  bit 6 is the line's parity in every frame. A late or missed interrupt
  then costs one line, not the rest of the frame. `T2_START` puts the change
  in bit 6 about 4-5us before the handler reads it, so a handler delayed
  by most of a line still sets the parity of the line being drawn. From
  `&0C` (at 64 columns) it reads the wrong line.
- **The machines differ.** The Integra-B's vertical sync comes about 3us
  later in a line than the B+'s, so the same constants land the write at
  columns 77-78 on the B+ and 71-72 on the Integra-B. Measure on both.
- **Only our interrupt.** The System VIA's interrupts (the OS's 100Hz
  clock, the keyboard, vsync) are switched off while it runs, and the
  User VIA's too, apart from timer 1. `loading_screen_off` gives back the
  IERs, the User VIA's ACR and IRQ1V.

## Loading beneath it

STRAT shows the picture, then loads RENDER, MAIN, PWORLD, PLIGHT and PGAME
through the OS, and starts PGAME through the Tube host itself, so the
picture stays up to the last. The constraint, from the start: nothing
fitted to a particular filing system. Some games keep such a screen clean
by driving the disc controller themselves; that would tie the game to one
DFS and rule out MMFS, ADFS or a network. So the handler takes the filing
system's interrupts as they come.

What we measured, on DFS 2.26 in Beebium (scripts that log every late
switch with the code it interrupted, and frames captured mid-load):

- **The DFS's NMIs.** Its per-byte NMI handler (at `&0D00`) takes about
  50-65 cycles, with an NMI every 128-134 cycles, beating against the
  128-cycle line. A run of them holds the line's interrupt off.
- **The DFS's stretches with interrupts off.** Between 60us and 575us (up
  to 9 lines) at a time, after which it re-enables them and waits for the
  sector (late interrupts are taken in its sector-wait loop, `&8E60`-
  `&8E67`). A whole line, or several, is then shown in the wrong palette.
- **Not the Tube.** The Tube host's handshake did not show up as a cause.
  Loads over the Tube to the parasite were the *better* case.
- **Narrowing the screen helped.** At 80 columns, 7-25% of lines were late
  while the parasite's files loaded. Narrowed to 64 columns (256 pixels,
  CRTC R1 = 64, R2 moved to centre it; 16K), the blanking is 64 columns
  and the switch can move earlier: 0.4-2.2% late, nearly all by under 8
  columns, and about 0.1% skipped. Loads into the host's own memory
  (RENDER, MAIN) stay worse: 6-9% late, 1.2% skipped. (Undone since: the
  title screen, with nothing loading beneath it, is full width.)
- **What it looks like.** About a third of captured frames show some wrong
  lines, mostly in the first two seconds, while RENDER and MAIN load. A
  frame captured mid-frame mixes two frames, which shows as one apparently
  wrong line per capture: don't count that one.
- **Doing the Tube transfers ourselves would make it worse.** Loading the
  parasite's files into host memory and sending them on would push every
  file through the worse host-load path, on this DFS at least.

So a picture switched every line, with loading beneath it through an
unmodified filing system, is close but not clean, and cleaner only by
fitting to the filing system, which we won't do.

## The direction from here

The picture is good in its own right, so it is now a **title screen**,
shown with nothing loading beneath it, where the switching is exact
(LOADSCR's test sees every switch in the blanking, every line, on both
machines), and with its full 320 pixels back. STRAT shows it until SPACE
is pressed, with the Stratagem Overture on the Music 5000
(`docs/music-5000.md`). Then comes a plainer **loading page**, in MODE 7
teletext, with nothing timed to the line, so the filing system can do as
it likes (`tools/stratagem/loading_page.py`, `asm/loading_page.asm`):

- **The title** in mosaic graphics, as the cover has it: chunky letters in
  strata, yellow at the top, red, and a dark (magenta) band beneath.
  Teletext changes colour only at a control cell, so the strata are rows,
  and with one colour a row there is no cell lost between the letters.
- **A cave:** a yellow ceiling, with small stalactites and one large one
  over the left, and the keys to its right, in cyan and white.
- **The progress bar is a pool,** in the floor beneath the stalactite.
  Drips form at its tip, fall (accelerating, with a streak when fast) and
  fill the pool a sixel each: 48 of them. The pool follows an estimate of
  the bytes loaded, from the files' lengths (OSFILE 5, so any filing
  system): 140 bytes a frame, never past the end of the file loading, and
  caught up as each file is done. The animation starts only once the files
  are measured: started before, while the disc spun up, it owed the whole
  pool at once (no bytes to a sixel yet), and the pool was full seconds
  before the load was done. Once the game is loaded, "PRESS SPACE TO
  START", and a drip now and then.
- **Hold graphics** on the floor's rows, so the colour changes either side
  of the pool show the floor and the water, not black cells.
- The animation runs from the vertical sync event, with the music, and
  writes the screen directly; the page is MODE 7, not shadowed, for that
  (`docs/tube-game.md` has why, and what it costs the Integra-B).
- `tests/test_loader.py` compares the page, once the pool is full, with the
  model's, byte for byte, the drips apart, on both machines.

- With the System VIA's interrupts off, the OS doesn't scan the keyboard,
  so `wait_for_space` (`asm/host_low.asm`) reads it itself, as the game
  does. The line's interrupt doesn't touch the System VIA, so it needn't
  hold interrupts off to do so.
- The tests boot the game through STRAT, so `boot_game` in
  `tests/conftest.py` presses SPACE at the title, and again on the loading
  page once the game has loaded.
- Ideas not pursued for a loading picture, should one come back: load the
  host's files first, before the picture shows; compress them, so less
  time is spent in host loads; a steady-colour margin in the dither; art
  composed for the narrower screen (256x256 MODE 1 pixels, about 1.07:1 on
  4:3).
