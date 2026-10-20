# Stratagem on the Tube

The game running on a 6502 second processor, with the host drawing what it
sends. Built alongside the host-only game: `uv run strat-build` makes
`build/stratagem.ssd` (host-only, as before) and `build/stratagem-tube.ssd`
(this). The prototypes that led here are in `tube-prototypes.md`.

## Playing it

Needs a BBC B+ 128K or a Model B with Integra-B, with a 6502 second
processor (a 3 MHz 65C02, or the 4 MHz 65C102).

- In Beebium, import `presets/stratagem-b-plus-128k-65c02.json` (File >
  Import Presets...): a B+ 128K with a 3 MHz 65C02. From the command line,
  add `--tube-65c02` to the server's options: from Beebium 0.12.0 an
  Integra-B so launched boots across the Tube (one saved by an earlier
  version still needs `*CONFIGURE TUBE` and Ctrl-Break once).
- Insert `build/stratagem-tube.ssd` and Shift-Break.

The keys are the host-only game's (`implementation-record.md`), and T:

| Keys | Action |
|---|---|
| Z, X | Walk left, right |
| K | Jump; in the air, a fresh press jumps again |
| L | Dig, ahead; with M, down; with K, up; with both, diagonally |
| SPACE | Place a soil block |
| T | Drop a torch where the miner stands (in air: up to 24) |

Dig down a few tiles to leave the daylight: the miner's light shows below,
and daylight follows down the shaft.

## How it works

The parasite runs the game: input, movement, digging, the camera, the
world (its generator and changed-chunk store), the tile cache, and the
miner's light. The host keeps the OS and filing system, and draws.

Each frame:

1. The parasite waits until the host has read its last packet (a frame
   count in its mailbox catches up), takes the input the host wrote there,
   moves the player, digs or places, plans the camera, brings its tile cache
   up to date, and lights the miner's surroundings.
2. It writes a packet into one of two buffers: the camera, the player, any
   new strips of tiles (each tile's material, shape and daylight), a
   changed tile, and the light's draw list (each cell to redraw: its masks,
   its graphics' address, its screen address). Then it tells the host which
   buffer, by OSWRCH (`COMMAND_FRAME`).
3. The host's OSWRCH hook reads the packet's first part over the Tube (a
   byte at a time), writes the tiles into its own tile cache, writes the
   input it reads into the parasite's mailbox, and draws the new row into
   the hidden row. Then, at vertical sync, it flips, draws the new columns
   ahead of the beam, the changed tile, the light's list (reading it from
   the Tube as it draws: `render_light.asm`), and the sprite.

While the host draws a frame, the parasite works out the next.

| File | Where | What |
|---|---|---|
| `asm/host.asm` | host | STRAT (loader, hook, trampolines), MAIN (each frame), RENDER (+ `render_light.asm`) |
| `asm/parasite.asm` | parasite | PGAME, PWORLD, PLIGHT; its memory map |
| `asm/tube_layout.asm` | both | buffers, mailbox, packet layout, host addresses |
| `asm/parasite_main.asm` | parasite | the frame, packets, strips of tiles |
| `asm/miner_light.asm` | parasite | the light: flood, soft blend, pass, draw list, resets |
| `asm/torches.asm` | parasite | torches |
| `asm/daylight.asm` | parasite | daylight: sky depths, sunlight by columns, the glow |
| `asm/pieces.asm` | parasite | pieces' slots: giving, sweeping, showing |
| `asm/host_main.asm` | host | reading packets, the mailbox, drawing |
| `asm/camera.asm`, `cache.asm`, `view.asm`, `scroll.asm`, `pixels.asm` | shared | split out of `main.asm` |

The host-only game's code is shared where it can be: the parasite runs
`player.asm`, `actions.asm`, `camera.asm`, `cache.asm` and `world.asm`
unchanged, with the same zero page and variables; the host runs `view.asm`
and `render.asm` unchanged, with its own zero page at `&57`-`&8F` (the Tube
host's code and variables have `&00`-`&56`).

### Torches

A torch is a material (`tiles.TORCH`), passable, dropped into the empty
tile the miner stands in (`asm/torches.asm`). Its light is the miner's flood
from its tile, but fixed and per tile, kept with daylight in the tile
cache's light plane: the host draws it with the tiles, and the miner's
light shows only where brighter. Each torch's pool is kept (24 at most), so
tiles entering the cache are lit by it. When a tile changes within a
torch's reach, the torch is flooded again and the tiles whose light changes
are queued, with their new light, and sent as changed tiles, three a frame
(so a torch's light spreads in over a few frames). The parasite's tile cache
takes a tile's new light only when it is sent, so the miner's light always
compares against what the host shows. Torches can't yet be picked up.

### Pieces and slots

A piece is a material drawn whole over a backdrop, the background that
shows through its clear pixels (`tiles.PIECES`; `docs/tile-set.md`). The
torch is the only one so far. The host keeps each piece's graphics and mask
(128 bytes) and each backdrop's (64) in its program RAM, and draws pieces
through slots: 56 composed pairs of piece and backdrop in the render bank
at `&B100`-`&BEFF`, each drawn as an ordinary material (7 materials from
`SLOT_MATERIAL`, each page holding four slots as its four cell variants,
drawn whole with pseudo-shapes 61-63), so the renderer is unchanged.

On the parasite (`asm/pieces.asm`), each pair in the tile cache has a
slot. When a piece's tile is sent and its pair has none, it is given a free
one (its visibility, for the light, copied in), and the tile goes after
`PIECE_COMPOSE`, the slot, the piece and the backdrop; the host composes
the slot before reading the tile (`host_compose`, about 1,800 cycles with
reading). When no slot is free, the tile cache is swept and the slots whose
pairs have left it are freed; if there are still none, the piece is sent as
its backdrop alone. The light looks a piece tile's slot up for the graphics
the host draws it with.

### Daylight

`lighting.shaft_sun`, brightened by the glow (`asm/daylight.asm`). Each
column's sky depth, its first opaque tile, is kept for the whole world. An
open tile is lit fully above its column's sky depth, else from the nearest
column within 4 open to the sky at its row, 3 levels less a column away; a
wall fully at its column's sky depth, 4 less a tile below it, from a column
open to the sky beside it, and, as a floor, as brightly as the open tile
above it; then a level less for each 4 tiles the tile is below its
column's surface (`SHAFT_TAPER`). So daylight falls down a dug shaft,
dimming slowly as it goes (four times more slowly than the glow), and pools
where it meets a cave.

Light stops at walls: it reaches a tile along its row only through open
tiles (a wall, through walls first, then open tiles), and soaks down into a
wall from its column's sky depth only through walls. So a roofed hut is
dark inside, and light doesn't seep through rock into a cave beside a
shaft. It doesn't creep down slopes away from the shaft: the price of
being cheap. The glow is the host-only game's stand-in, `fixed_light`, 4
levels dimmer, below the original surface only: it shades the rock below
the surface and lets shallow caves be made out. A tile at or above the
surface is in the sun unless something built covers it, and then dark.

Daylight is worked out as tiles enter the tile cache (tables of the deepest
sky depth within 1 to 4 columns of each make that quick, and tell at once
when a tile is too deep to be lit). To find whether light passes, the
nearest column open to the sky each way is found from the sky depths, and
only the tiles between it and the tile are read: from the tile cache where
it holds them (`sun_bounds`: both cached and in view, which differ while
the cache is being filled), otherwise from the world. A tile changed so
that it lets light through differently (the game notes whether it did as
it sets the tile) relights the tiles within reach, a row a frame, queued as
the torches' changes are: if its column's sky depth changes, from the
highest of the tile and the old and new sky depths to 4 below the lowest;
otherwise its row, the floors below it, and those that light soaks down to
through it.

The daylight lab (`uv run strat-daylight-lab`) draws it against the fuller
model we chose the look from (`lighting.sunlight`, which spreads light
through open tiles a row at a time, and costs too much here).

### The light

`lighting.smooth_miner_light(..., soft=True)`, brightened by each tile's
daylight. A level per block of two cells (4 pixels by 8 lines), from a
radial table less each block's excess (the extra cost of the path the tile
flood found, blended between tiles: soft shadows). A plane holds each
block's miner's level; where it changes, each cell whose look changes (a
coloured pixel's threshold lies between the old and new masks) goes on the
list. The host draws new rows and columns, and changed tiles, as daylight
alone; the parasite resets those blocks (to 0), so the next pass lights them.
Cells in new columns are drawn after the list, so they are lit a frame late.

## Checking it

`tests/test_tube_game.py` plays on both machines (digging deep first, as
near the surface daylight outshines the miner's light), and checks the
displayed screen byte for byte every frame against the models: the host's
tiles, lit by the brighter of daylight (and torchlight) and the model's
light, with the sprite. One script drops torches, and checks they are in
view and light tiles beyond daylight.

`tests/test_pieces.py` checks slots in py65: given, shown, their
visibility copied and freed by a sweep on the parasite, and composed on the
host as `tiles.compose` does.

`tests/test_daylight.py` plays the parasite alone in py65 (the host played
by a hook), down a shaft from the surface and along a tunnel, and whenever
relighting is done checks every tile in the tile cache against
`lighting.shaft_sun` and the glow, from the world as the parasite holds it,
and each column's sky depth. Another builds a roofed hut around the miner,
a block a frame as the game places them, and checks the same, and that the
hut is dark inside.

## Costs

Measured while digging and tunnelling (529 frames):

- **Host** (2 MHz, a frame is 40,000 cycles): reading the packet and
  drawing a new row about 4,000; drawing at the flip about 7,000; the rest
  waits for vertical sync. About 1 frame in 100 is dropped, when the
  parasite is late.
- **Parasite** (py65's 65C02 count; at 3 MHz a frame is 60,000 cycles):
  about 21,000 a frame on average, a third of a frame. The light's flood,
  when the miner enters a tile or tiles change, is the spike: about 33,000
  (reading the window from the cache 9,800, the flood 9,200, the soft blend
  12,000); with a new tile row from the world (generating it, up to 29,000)
  or many changed blocks, a frame can take up to about 97,000.

Daylight adds about 1,200 cycles a frame on average while digging down a
shaft and along a tunnel (17,300 against 16,100 in py65 over the same
490 frames), and frames over 60,000 go from 16 to 20.

The taper costs nothing measurable (17,311 against 17,333 over the same
490 frames).

Stopping at walls costs about 700 cycles a frame more on average (18,045
against 17,311 over the same 490 frames), and frames over 60,000 go from 20
to 25. The worst frame, which fills a new strip of tiles beside the shaft
and floods the miner's light, goes from 108,166 to 117,540: lighting a
tile beside a shaft now reads the tiles between, about 145 cycles each.

Slots add about 30 cycles a frame (17,333 against 17,306 over the same
490 frames; with torches dropped, 18,827 against 18,801 over 794, the
worst frame unchanged).

Dropping a torch floods twice (the torch's pool, then the miner's, as the
tile changed) and relights its surroundings: about 118,000 cycles, so the
host can miss a frame then.

## Not yet

- Picking torches up; torches that flicker; more than 24.
- The flood's spike: spreading it over two frames, or making it cheaper.
- The list can hold 255 cells; beyond that, cells could be left unlit.
- Untested beyond Beebium; the Master 128 not yet.
- The parasite's memory is nearly full: a few dozen bytes are free (15 in
  PLIGHT, 6 in the variables at `&0400`, and alignment gaps in PGAME).
  The light's radial table (12K) and the changed-chunk store (13K) are the
  large items to look at first.
