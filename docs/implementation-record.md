# Stratagem: the implementation so far

A record of the game as built, as of 2026-10-19 (commit `6b89282`), for us and
for other agents joining the work. For the plan ahead see `next-steps.md`; for
why things are as they are, `decisions.md`; for the hardware facts relied on,
`platform-notes.md`; for the game's intended design, `game-design.md` and
`concept.md`. `architecture.md` describes the memory model and scrolling in
more depth, though where it and this record disagree, this record is newer.

Since 2026-10-20 the game runs on a 6502 second processor, with smooth
light and torches: see `tube-game.md`. On 2026-10-21 the host-only game
described here was dropped (`decisions.md`): its world, physics, digging,
camera and renderer live on in the Tube game (`main.asm` was split into
`camera.asm`, `cache.asm`, `view.asm`, `scroll.asm` and `pixels.asm`), but
its files (`stratagem.asm`, `low.asm`, `main.asm`, `lighting.asm`), its
banking of the world, and its disc are gone. Read what follows as the
history of those parts.

## What it is

Stratagem is a Terraria-inspired digging and building game for the BBC Micro,
using Exile-like technology: a large tile world, smoothly scrolled, with a
physics-driven player. It is written in 6502 assembly (beebasm), and keeps the
OS and filing system resident, loading through ordinary OS calls.

It runs on a **BBC B+ 128K** or a **Model B with Integra-B** (Master 128 later):
machines with 32K main RAM, 20K shadow RAM and at least 64K sideways RAM, of
which it takes 48K, leaving a bank for the user's own ROMs (such as MMFS).

### Playing it

`uv run strat-build` makes `build/stratagem.ssd`; boot it (Shift-Break).

| Keys | Action |
|---|---|
| Z, X | Walk left, right (climbing slopes and ledges up to a tile high) |
| K | Jump; in the air, a fresh press jumps again (double jump) |
| L | Dig, ahead; with M, down; with K, up |
| L with Z or X and M or K | Dig diagonally: a 45 degree sloping tunnel |
| SPACE | Place a soil block, aimed as digging is (K+SPACE jumps and places) |

While L is held, K aims rather than jumps, and, with M, the player doesn't
climb slopes or ledges, so that digging down into a slope works.

The world is 256 x 256 tiles: hills of grass and soil over stone with ore and
gems, blocky caves (with water below row 200), bedrock at the edges, and sky
above. The view is 16 x 15.5 tiles; the camera follows the player.

## Code map

| Path | What |
|---|---|
| `asm/stratagem.asm` | Assembles every part together (one label namespace) and SAVEs four files |
| `asm/low.asm` | `STRAT`, low RAM (`&1900`): paging trampolines, the loader (run by !BOOT), the tile cache |
| `asm/main.asm` | `MAIN`, user RAM (`&3000`): the frame loop, input, camera, applying scrolls, sprite placement |
| `asm/player.asm` | Movement and collision (included in MAIN) |
| `asm/actions.asm` | Digging and placing (included in MAIN) |
| `asm/render.asm` | `RENDER`, the render region (`&8000`): graphics, row/column/sprite drawing |
| `asm/world.asm` | `WORLD`, the world bank (`&8000`): generator, changed-chunk store, cache filling |
| `asm/machine.asm` | Machine detection and finding free sideways RAM |
| `asm/zeropage.asm`, `asm/variables.asm` | Variables: zero page (`&00`-`&8F`, full), then `&0400`-`&07FF` |
| `asm/layout.asm`, `asm/os.asm` | Memory layout constants, OS and hardware addresses |
| `asm/probe.asm` | `PROBE`, a diagnostic: reports the machine and its sideways RAM (`*RUN PROBE`) |
| `tools/stratagem/` | Python: the models, the table generator, the build |
| `tests/` | pytest: py65 tests of routines, Beebium tests of whole frames |
| `docs/reference/exile/` | Indexes into the Level 7 Exile disassemblies (themselves in `docs/local/`) |
| `docs/reference/tube/` | An index into acornaeology's Tube client and host disassemblies (in `~/Code/acornaeology/`) |

The Python models are the specification: `world.py` (generation and the
changed-chunk store), `tiles.py` (materials, shapes, graphics), `screen.py`
(screen layout), `camera.py`, `player.py`, `actions.py` (digging and placing),
`sprites.py`. `gen_tables.py` writes every table and constant the 6502 uses
into `build/generated/`, so there is one source of truth. Never hand-edit
generated files.

## Memory

On every target, 20K of program RAM and 20K of screen share `&3000`-`&7FFF`,
and the CPU sees one at a time:

| | Program RAM | Screen RAM | Render code sees the screen by |
|---|---|---|---|
| B+ 128K | main | shadow | running in ANDY (`&A000`-`&AFFF`, ROMSEL bit 7) |
| Integra-B | shadow (SHEN) | main | MEMSEL (ROMSEL bit 7) |

So the code that writes the screen, and everything it reads, lives outside
`&3000`-`&7FFF`, and on both machines "render mode" is ROMSEL = render bank |
`&80`, kept in step in `&F4`. Never raise errors (BRK) from render code.

| Range | Contents |
|---|---|
| `&0000`-`&0085` | Zero page variables (`&86`-`&8F` free) |
| `&0400`-`&0443` | Further variables (the language workspace: ours, as we replace BASIC) |
| `&1900`-`&1BFA` | STRAT: trampolines and loader |
| `&1C00`-`&23FF` | Tile cache: materials, then shapes (32 x 32 each) |
| `&3000`-`&47DA` | MAIN (6K) in program RAM; the rest of program RAM is free |
| `&4000`-`&7FFF` | The screen (16K, hardware wrap), in screen RAM |
| `&8000`-`&A284` | RENDER: material pages, cell offsets, sprites, code from `&A008` (in ANDY on the B+, the render bank on the Integra-B) |
| world bank `&8000`-`&8477` | WORLD code and tables; directory `&8500`; 104 chunk slots `&8900`-`&BCFF` |
| game bank | Allocated, unused |

The loader detects the machine (IBOS first, by OSBYTE `&49`, as IBOS makes
OSBYTE 0 report a B+), takes the three highest free sideways RAM banks,
selects a shadow MODE 2, and loads RENDER, WORLD and MAIN through OSFILE into
`&3000`, copying the first two into place.

## The screen and scrolling

- A narrowed MODE 2: 128 x 256 pixels, 64 character columns of 8-byte cells,
  16K at `&4000` with the hardware wrap set for 16K. Only 31 of the 32
  character rows are displayed (248 lines); the 32nd is hidden.
- Tiles are 8 x 16 pixels: eight cells, four across and two down.
- Tiles use logical colours 8-15 and sprites 0-7, both mapped to the same
  eight physical colours. Pieces in front (trees, by the hash) are drawn
  in 0-7 too, and sprites leave their pixels out over that group, so the
  miner passes behind them (`tube-game.md`, In front and behind).
- Scrolling moves the CRTC start address a cell at a time: 2 pixels
  horizontally, 8 lines vertically, both axes in a frame if need be.
  - A new top or bottom row always lands in the hidden row, so it is drawn
    before the flip, out of sight.
  - New columns are drawn after vertical sync, top-down, ahead of the beam.
  - Nothing partly drawn is ever displayed.

### The frame

```
wait for vertical sync (OSBYTE 19)
set the CRTC start address (the flip)
draw the new columns' rows above the sprite            -- the beam reaches these first
remove the sprite; redraw a changed tile, if queued; draw the sprite
draw the rest of the new columns
frame_shown:                                            -- tests stop here
read input; move the player; dig or place
plan the camera; move the screen start; update the tile cache;
draw a new row into the hidden row
```

**Beam safety.** Each phase after vsync was measured, on both machines,
walking, jumping, digging and placing, to finish at least 3,600 cycles before
the beam reaches its rows. The picture starts about 5,100 cycles after vsync,
and a character row takes 1,024. A changed tile is redrawn between removing
and redrawing the sprite, because the sprite on screen may overlap it. The
worst frame earlier took about 30,000 of 40,000 cycles; it hasn't been
re-measured since digging and slopes were added.

### The camera (`camera.py`)

A camera window rather than pure centring, after Exile:

- The focus (the player) is kept within a window, columns 24-39 and rows
  11-19 of the view, so small movements don't scroll.
- The window shifts against the direction of travel by a lead that eases,
  one column a frame, towards 12 columns, to show what lies ahead.
- The camera moves at most 2 columns and 1 row a frame.
- The view is redrawn, centred, only if the focus leaves it.

### The tile cache

A 32 x 32 ring of tiles around the view, in low RAM, two planes (materials
and shapes). The world bank fills a new tile row or column only when the
camera crosses a tile boundary. The renderer, collision and digging all read
tiles from it.

## The world

### Tiles: materials and shapes (`tiles.py`)

A tile is two bytes.

- **Material:** air, grass, soil, stone, ore, gem, bedrock, water, sky. Air,
  water and sky are passable. Grass to gem are diggable.
- **Shape:** a 4 x 4 grid of quarter-cells (2 pixels by 4 lines), as a
  16-bit solid mask.
  - Shape 0 is whole.
  - The others are *erosions* from one side: four depths, one per strip,
    in quarters. Flat erosion is a partly dug tile; 45 and 22.5 degree ramps
    give slopes, sloped walls and sloped ceilings from any side.
  - 61 shapes in all, numbered within 64.
- **Background bit** (`BACKGROUND_SKY`), in the shape byte: what shows
  through the empty parts, sky or dark cave. It is set for tiles at or above
  the surface line of their column, by one rule wherever tiles are made.
- **Graphics:** each material has two 256-byte pages (one per background) of
  four cell variants: full, top half, bottom half, empty. A table gives the
  variant of each cell of each shape, so any material draws in any shape at
  almost no cost.

### Generation (`world.py`)

- The material at (x, y) comes from a surface height per column (smooth
  random curves) and a permutation hash: grass on the surface, soil for 4-7
  rows, then stone with ore and gems, and caves from a coarse hash.
- Shapes smooth it:
  - a surface tile with a lower neighbouring column on one side slopes
    down towards it;
  - an underground tile with open space above or below and to one side has
    that corner rounded by a ramp.
- The generator runs in the world bank.

### Changes (`world.py`, `asm/world.asm`)

- A directory of 32 x 32 chunks of 8 x 8 tiles (1K), and 104 slots of 128
  bytes for changed chunks.
- The first change to a chunk copies its generated tiles into a free slot.
- When none is free, changes are refused (spilling to disc is to come).
- `tile_at` reads the store or generates; `set_tile` writes.

## The player (`player.py`, `asm/player.asm`)

A 6 x 24 pixel box. Positions are in sixteenths of a pixel and line, 16-bit.

- **Walking:** eases to 1 pixel a frame (faster on the ground than in the
  air).
- **Jumping:** a jump, with gravity of 4/16 a frame, reaches about 2.5 tiles;
  falls are capped at 6 lines a frame, so the player can never pass through a
  tile.
- **Double jump:** a fresh press of K in the air. It is restored on landing,
  and gated by an ability bit that is on from the start.
- **Collision:** each axis moves separately. The solid quarter-cells the box
  would overlap (shape mask ANDed with the box's region, per tile, from the
  tile cache) stop it flush against the nearest.
- **Ledges:** walking into a ledge up to a tile high climbs exactly its
  height, so slopes are climbed a quarter-cell step at a time. Not while
  digging down.
- **Ground snapping:** a standing player follows the ground down steps of up
  to a quarter-cell (probing 5 lines down), so walking downhill doesn't
  bounce.
- **Sprite:** masked, with save-under. Four poses (stand, two walking, jump),
  mirrored for facing left.

## Digging and placing (`actions.py`, `asm/actions.asm`)

- **Cooldown:** a dig takes 8 frames and a place 6; one action at a time.
- **Gradual digging:** a dig erodes the tile by quarters from the side nearest
  the player.
  - Grass goes in one dig, soil in two, stone, ore and gems in four.
  - When eroding a shape from that side leaves a pattern that isn't a
    shape, the tile becomes the largest shape within what is left, so the
    near side always goes first.
  - When nothing is left, the tile becomes air or sky (by its background)
    and one of its kind (dug grass is soil) goes into the inventory
    (up to 99 of each) and the hand (see `tube-game.md`, The inventory).
- **Aiming:**
  - **Down:** the tile holding the line just below the feet.
  - **Up:** the tile holding the line just above the head.
  - **Ahead:** the column holding the pixel just ahead. Digging takes the
    tile with the most solid left (the lowest, of equals), so a wall as high
    as the player is cut back evenly. Placing takes the lowest empty tile.
- **Placing:** whole soil into air or sky, never overlapping the player.
- **Diagonal digging** makes a 45 degree sloping tunnel, a step at a time:
  - **The path** of a step. Going down: across at the player's height, then
    a tile down (to a tile boundary). Going up: a tile up.
  - **Order:** worked column by column, nearest the player first. Going
    down, in each column: across, then the step, then down. Going up: the
    step, then up.
  - **The step** is cut back to a 45 degree ramp, even if partly dug. Going
    down, it is the floor under the leading edge; going up, the tile ahead at
    the feet.
  - **Otherwise**, in the first part of the path with something in the way:
    across, the tile with the most left; up or down, the nearest.
  - **Never cleared:** the step (going up), and the floor under the player
    (going down).
- **No cavities.** Every dig opens space next to the space the player is in.
  `tests/test_digging_model.py` checks this in every direction, from places
  all over the world.

A change goes to the world bank and the tile cache at once; the screen is
redrawn at the next flip.

## Testing

`uv run pytest` builds and runs 74 tests, about 7 minutes. Everything is
checked against the Python models.

- **py65** (fast, pure routines, flat memory):
  - the world generator over all 65,536 tiles;
  - the changed-chunk store until full;
  - camera planning (18,000 random frames);
  - player movement (18,000 frames on real and randomly dug terrain, with
    checks that climbing, air jumps, shaped floors and ground following
    happen);
  - digging and placing: random inputs, long held diagonal tunnels, and a
    fuzz test of single diagonal digs in random ground, checking each dug
    tile.
- **Model-only** (`test_digging_model.py`):
  - no cavities;
  - 45 degree tunnels in soil and stone;
  - progress through real ground.
- **Beebium**, on both the B+ 128K and the Integra-B:
  - machine detection and bank allocation;
  - the view after boot;
  - scripted play (walking, jumping, double jump, digging down, tunnelling
    in every diagonal, digging into slopes, building).

  Every frame the displayed screen memory must match the models byte for
  byte, the tile cache must match the world, and the player, inventory and
  camera must match their models given the input the game read.

The tests have been proven able to fail by mutating the 6502 deliberately;
do that again when adding tests. Tests stop the emulator at `frame_shown` and
read state by label name, never by address.

Working with Beebium (see `CLAUDE.md` and `platform-notes.md`):

- `run_*` helpers leave the machine stopped.
- Wait for the OS prompt before booting a disc.
- Read the screen through memory regions (`shadow_ram` on the B+, `main_ram`
  on the Integra-B), not CPU addresses, because IBOS leaves MEMSEL set in its
  idle loop.

## People and tools

- **Beebium**, the emulator, and **oaknut-dfs**, the disc image tool, are the
  user's own projects. Report friction with Beebium to the `beebium-stratagem`
  peer session, which files issues (#184-#198 came from this work, and most
  are fixed on Beebium's master), and friction with oaknut to the user.
- `dont-dither-expert` is a peer that knows the same toolchain.
- References: Level 7's Exile disassemblies (`docs/local/`, indexed in
  `docs/reference/exile/`), OS 1.20 (`~/Code/os120`), MOS disassemblies
  (`~/Code/acorn_mos_disassembly`), MMFS source (`~/Code/MMFS`), the IBOS
  source (github.com/kgl2001/IntegraB-OS), and acornaeology's Tube client,
  NFS and ADFS disassemblies (`~/Code/acornaeology/`, indexed in
  `docs/reference/tube/`); `beebium-stratagem` also knows the Tube well.

## Known limitations

- Placeholder art drawn by code; grass on slopes loses its green top; no HUD,
  so the inventory can't be seen.
- No way to choose the hand but digging, no crafting; the double jump is
  free.
- 104 changed chunks, then digging is refused; nothing is saved.
- No enemies, objects, water physics, light or sound.
- Caves come from a coarse hash and are blocky, though their corners are
  rounded.
- Untested: NFS/ANFS (PAGE assumed `&1900`), MMFS, the Master 128, real
  hardware.
