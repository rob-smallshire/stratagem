# Stratagem architecture

Stratagem is an open-world digging and building game in the spirit of
Terraria, using techniques from Exile: a large tile world, a smart-scrolling
16-colour view and a physics-driven object system. This document describes
how it fits the machines; `docs/game-design.md` describes the game; `docs/platform-notes.md` holds the hardware facts
it relies on, and `docs/decisions.md` records decisions as they are made.

## Targets and constraints

- Machines with 32K main RAM, 20K shadow RAM and at least 64K sideways RAM:
  the BBC B+ 128K, the Model B with Integra-B, and the Master 128 (later:
  Beebium does not emulate it yet).
- We use 48K of sideways RAM (three banks), leaving one bank free for the
  user's own ROM images, such as MMFS.
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

Geometry: 128 x 256 pixels, as in Exile
Enhanced. That is 64 character columns by 32 rows, 16K at `&4000`, with the
hardware wrap set for a 16K screen. Scrolling is by CRTC start address,
with new strips plotted at the leading edges.

This leaves screen-side `&3000`-`&3FFF` as 4K that only render code can
see, a good place for more graphics. A full 160-pixel-wide 20K screen
remains possible; it costs that 4K and a quarter more plotting per redraw.

## World

A 256 x 256 tile world, one byte per tile (type and flip,
as in Exile). The world is never stored whole, since 64K is too much:

- Immutable terrain (bedrock, water, lava, portals; see `game-design.md`)
  is never modified, so it needs no storage beyond the generator and the
  map overlay.
- The base world is procedural, computed from (x, y) by a fast hash-driven
  generator, as in Exile, so unmodified land costs nothing.
- Modified land is stored as chunks of 8 x 8 tiles (64 bytes). A
  directory of one byte per chunk (1K for 32 x 32 chunks) maps each chunk
  to a slot in the modified-chunk store, or to "procedural". About 12K of
  bank W holds about 190 modified chunks, roughly a fifth of the world.
  When the store fills, chunks spill to disc with OSGBPB, which is also the
  basis of saving a game.
- The game can grow later through several worlds on disc, each a 256 x 256
  world with its own seed, map overlay and modified chunks.
- `tile_at(x, y)` checks the directory and reads a stored chunk, or calls
  the generator.

The renderer never calls `tile_at` itself, because bank W is not visible
while the screen is paged in. Instead, game code fills a strip buffer in
low RAM with the tile numbers and palettes for the next strip, and the
renderer draws from that.

## Frame structure (sketch)

1. Game update (screen off): input, physics, objects, world edits.
2. Prepare (screen off): decide the scroll, fill strip buffers for exposed
   edges, build the sprite list.
3. Render (screen on, in the render region): unplot or restore old
   sprites, plot strips, plot sprites, then set the CRTC start address at
   a safe point in the frame.
4. The IRQ handler (in low RAM) handles vsync and timer events: palette
   splits (for example, Exile's water line) and sound.

## Build and test

- `uv run strat-build` assembles each program in
  `tools/stratagem/build.py`'s `PROGRAMS` onto `build/stratagem.ssd`.
  Labels go to `build/labels/<NAME>.txt`, which tests use to look up
  addresses by name.
- `uv run pytest` runs the tests. Emulator tests take the `machine`
  fixture and run on both the B+128K and the Integra-B in Beebium. Pure
  6502 routines can be tested quickly in py65.
- Third-party sources are indexed in `docs/reference/` for navigation.
