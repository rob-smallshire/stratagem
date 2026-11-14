# Stratagem architecture

Stratagem is an open-world digging and building game in the spirit of
Terraria, using techniques from Exile: a large tile world, a smart-scrolling
16-colour view and a physics-driven object system. This document describes
how it fits the machines; `docs/game-design.md` describes the game; `docs/platform-notes.md` holds the hardware facts
it relies on, and `docs/decisions.md` records decisions as they are made.

## Targets and constraints

- Machines with 32K main RAM, 20K shadow RAM and at least 64K sideways RAM:
  the BBC B+ 128K, the Model B with Integra-B, and the Master 128 (since
  2026-11-14, tested in b2, as Beebium does not emulate it yet).
- We use 48K of sideways RAM (three banks), leaving one bank free for the
  user's own ROM images, such as MMFS. (Since the game moved to a second
  processor (`tube-game.md`), the host uses one bank, for the render
  region; the other two hold the store of changed chunks. A fourth bank,
  if free (the filing system in ROM), holds the game's music, MBANK. The
  host-only game this document was written for was dropped on
  2026-10-21.)
- The OS and the filing system stay resident. All file access is through OS
  calls (OSFILE, OSGBPB, OSFIND), so the game runs from DFS, MMFS, ADFS or
  over Econet with NFS/ANFS. We use only the memory the OS gives to
  applications, hook vectors politely, and survive BREAK.

## One memory model for all machines

Every target has the same shape: two 20K banks of RAM share the addresses
`&3000`-`&7FFF`, and the CPU sees one at a time.

| | User RAM (program, loads) | Screen RAM | Switching (*screen on*) |
|---|---|---|---|
| B+ 128K | main | shadow | run code at `&A000`-`&AFFF` with ANDY paged in |
| Integra-B | shadow (SHEN set) | main | set MEMSEL (ROMSEL bit 7, kept in `&F4`) |
| Master 128 | main | shadow (LYNNE) | set ACCCON X |

On each machine, OS file loads to `&3000`-`&7FFF` land in user RAM, not
the screen. The game is written against this model, with a small
machine layer chosen at load time:

- `screen_on` / `screen_off`, which switch the CPU's view of
  `&3000`-`&7FFF`. On the B+ the view follows the PC instead, so these
  page ANDY in and out, and only code in `&A000`-`&AFFF` sees the screen.
- `select_bank`, which pages a sideways RAM bank in while preserving the
  machine's other ROMSEL bits, and keeps `&F4` in step.

The rule that follows: **code that writes the screen, and everything it
reads while doing so, lives outside `&3000`-`&7FFF`.** This means it must
be in low RAM (`&0000`-`&2FFF`) or at `&8000`-`&BFFF`.

### The render region

The renderer, its tile and sprite graphics, and its work buffers live in a
12K render region at `&8000`-`&AFFF`, with the code at `&A000`-`&AFFF`:

- On the B+ the render region is ANDY, the 12K private RAM that no OS or
  filing system ROM uses. Code there is the only code that can write the
  screen.
- On the Integra-B and the Master it is the lower 12K of the render bank,
  one of our three sideways RAM banks. The screen is paged in with MEMSEL
  or ACCCON X while the render code runs.

The upper 4K of the render bank (`&B000`-`&BFFF`) is visible alongside the
region on every machine (on the B+, ANDY covers only `&8000`-`&AFFF`).

On the B+, render code must stay a few bytes clear of `&A000` and `&B000`.
On every machine it must not raise errors (BRK clears the paging bits), and
it keeps `&F4` up to date whenever it changes ROMSEL.

### Memory map

| Range | Size | Contents |
|---|---|---|
| `&0000`-`&008F` | 144 | Zero page (ours: `&00`-`&8F`) |
| `&0100`-`&18FF` | | OS and filing system workspace, stack, vectors |
| OSHWM-`&2FFF` | 5.75K at OSHWM `&1900` | **Low RAM**, always visible: the machine layer, IRQ handler, bank-call trampolines, buffers shared between game and renderer (strip and sprite lists) |
| `&3000`-`&7FFF` | 20K | **User RAM**: main loop, game logic, object tables, chunk cache |
| `&3000`-`&7FFF` | 20K | **Screen RAM** (16K screen at `&4000` plus a 4K render-only area at `&3000`, see below) |
| `&8000`-`&AFFF` | 12K | **Render region**: graphics `&8000`-`&9FFF`, render code `&A000`-`&AFFF` |
| Bank R `&B000`-`&BFFF` | 4K | Render bank upper 4K: tables the renderer reads |
| Bank W | 16K | World: procedural generator, chunk directory and modified-chunk store |
| Bank G | 16K | Game: objects, physics, AI, sound |

On the B+, bank R's lower 12K is spare, because ANDY holds the render region.

The interrupt handler, the bank-switching trampolines and the vectors we
hook must be in low RAM, the only memory that is always visible.

OSHWM depends on the filing system, so the loader reads it (OSBYTE `&83`).
If low RAM is too small, it reports that and stops, rather than overwriting
filing system workspace. NFS and ANFS values are yet to be measured.

## Screen

An Exile-style MODE 2 derivative: 16 colours at 2 pixels per byte, split
into two groups of eight (one for tiles, one for objects), so a
four-colour sprite can be recoloured by palette. The palette handling is
kept in one module, so that a Video NULA's programmable palette can later
give true 16 colours.

Screen memory is 16K at `&4000` with the hardware wrap set for 16K: 64
character columns (128 pixels) by 32 rows. Only 31 rows (248 lines) are
displayed; the 32nd is hidden. Tiles are 8 x 16 pixels, so each is eight
cells (character cells of 8 bytes): four across, two down.

## Scrolling

Scrolling moves the CRTC start address, so the unit is a cell: 2 pixels
horizontally and 8 lines vertically. Studying Exile (see
`docs/reference/exile/README.md`), Stratagem keeps its camera ideas and
improves on its drawing:

- **Tear-free at 50 Hz.** Exile wipes and redraws an exposed strip while it
  is on screen, scrolls at most at 25 Hz, and one axis per update. Here,
  because only 31 of the 32 rows are displayed, a new top or bottom row is
  always the hidden row, and is drawn before the flip, unseen. New columns
  are drawn just after vertical sync, a row at a time, so each cell is
  finished long before the beam reaches it. Both axes can move in one
  frame; the corner cells belong to the columns.
- **A camera window.** The camera keeps the focus (the player, later)
  inside a window around the centre, so small movements don't scroll. The
  window shifts against the direction of travel by a lead that eases in, as
  Exile's scrolling velocity does, to show more of what lies ahead. The
  step grows with the distance outside the window (up to 2 columns a
  frame), and the view is redrawn only if the focus leaves it.
- **A tile cache.** A 32 x 32 ring of tile numbers in low RAM holds the
  tiles of the view. The world bank fills a new tile row or column only
  when the camera crosses a tile boundary, and the renderer reads tiles
  straight from it (as collision code will). Exile instead calls its world
  function for every strip, and each tile row is exposed twice and each
  tile column four times.

Each frame: wait for vertical sync; set the start address; draw the new
columns' rows above the sprite; remove the sprite, redraw any changed
tile, and draw the sprite; draw the rest of the new columns (each phase
measured to finish thousands of cycles before the beam reaches its rows);
then read input, move the player, dig or place, plan the camera, update the
tile cache and draw a new row into the hidden row. In the worst
case (two columns and a row) this takes about 30,000 of a frame's 40,000
cycles, leaving roughly a quarter for the game; `render_columns` is the
first place to optimise.

## World

A 256 x 256 tile world, two bytes per tile: a material and a shape
(`tools/stratagem/tiles.py`). A shape is a 4 x 4 grid of solid quarter-cells
(2 pixels by 4 lines), made by eroding a whole tile from one side to four
depths: flat (partly dug), 45 degree and 22.5 degree ramps, from any side,
giving 61 shapes. The shape byte also holds a background bit (sky or cave,
by whether the tile is at or above its column's surface), which shows
through its empty parts. Each material has two 256-byte pages of graphics
(one per background) of four cell variants (full, top half, bottom half,
empty), and a table gives each shape's cells' offsets, so any material
draws in any shape. Collision is by 16-bit masks (`find_hits` in
`asm/player.asm`). The generator rounds off surface steps and cave corners
with ramps.

The world is never stored whole, since 64K is too much:

- Immutable terrain (bedrock, water, lava, portals; see `game-design.md`)
  is never modified, so it needs no storage beyond the generator and the
  map overlay.
- The base world is procedural, computed from (x, y) by a fast hash-driven
  generator, as in Exile, so unmodified land costs nothing.
- Modified land is stored as chunks of 8 x 8 tiles (128 bytes). A
  directory of one byte per chunk (1K for 32 x 32 chunks) maps each chunk
  to a slot in the modified-chunk store, or to "procedural". About 13K of
  bank W holds 104 modified chunks, about a tenth of the world; compressing
  them, and spilling them to disc, are to come.
  When the store fills, chunks spill to disc with OSGBPB, which is also the
  basis of saving a game.
- The game can grow later through several worlds on disc, each a 256 x 256
  world with its own seed, map overlay and modified chunks.
- `tile_at(x, y)` checks the directory and reads a stored chunk, or calls
  the generator.

The renderer never calls `tile_at` itself, because bank W is not visible
while the screen is paged in. Instead it reads the tile cache in low RAM,
which the world bank fills.

## Frame structure (sketch, beyond scrolling)

1. After vertical sync: flip, then restore and redraw sprites in the order
   the beam reaches them.
2. Game update (screen off): input, physics, objects, world edits.
3. Prepare: plan the camera, update the tile cache, draw the hidden row.
4. The IRQ handler (in low RAM) handles timer events: palette splits (for
   example, Exile's water line) and sound.

## Build and test

- `uv run strat-build` assembles each program in
  `tools/stratagem/build.py`'s `PROGRAMS` onto `build/stratagem.ssd`.
  Labels go to `build/labels/<NAME>.txt`, which tests use to look up
  addresses by name.
- `uv run pytest` runs the tests. Emulator tests take the `machine`
  fixture and run on both the B+128K and the Integra-B in Beebium. Pure
  6502 routines can be tested quickly in py65.
- Third-party sources are indexed in `docs/reference/` for navigation.
