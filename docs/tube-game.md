# Stratagem on the Tube

The game running on a 6502 second processor, with the host drawing what it
sends: `uv run strat-build` makes `build/stratagem.ssd`. This is the game;
the host-only game it grew from was dropped on 2026-10-21 (`decisions.md`).
The prototypes that led here are in `tube-prototypes.md`.

## Playing it

Needs a BBC B+ 128K or a Model B with Integra-B, with a 6502 second
processor (a 3 MHz 65C02, or the 4 MHz 65C102).

- In Beebium, import `presets/stratagem-b-plus-128k-65c02.json` (File >
  Import Presets...): a B+ 128K with a 3 MHz 65C02. From the command line,
  add `--tube-65c02` to the server's options: from Beebium 0.12.0 an
  Integra-B so launched boots across the Tube (one saved by an earlier
  version still needs `*CONFIGURE TUBE` and Ctrl-Break once).
- Insert `build/stratagem.ssd` and Shift-Break.

The keys are those of `implementation-record.md`, and T:

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
| `asm/camera.asm`, `cache.asm`, `scroll.asm`, `pixels.asm` | parasite | the camera, the tile cache, scrolling |
| `asm/view.asm`, `render.asm` | host | drawing rows, columns and the sprite |

The parasite runs `player.asm`, `actions.asm`, `camera.asm`, `cache.asm`
and `world.asm`, written first for the host-only game; the host runs
`view.asm` and `render.asm`, with its own zero page at `&57`-`&8F` (the
Tube host's code and variables have `&00`-`&56`).

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
shows through its clear pixels (`tiles.PIECES`; `docs/tile-set.md`): the
torch, and the nine parts of a tree. Pieces are materials after the drawn
ones (`DRAWN_COUNT`), with no pages of their own in the render region: they
are only ever drawn through slots. The host keeps each piece's graphics and mask
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

### Trees

The generator grows trees on the surface (`world.tree_part`): a root on
the grass, a trunk of 1 to 4 tiles and a canopy three wide and two high,
placed a column at a time with `WORLD_COVER`, a byte a column (the
covering tree's trunk offset + 1, 0 for none, and its height). So
`generate_tile` finds a tile of sky's part with one look-up and a
subtraction from the trunk's surface height. A tree part's shape byte holds
its strength (`support.py`: the span on the trunk's column, one less beside
it), for support. Trees are passable and clear to light.

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
where it meets a cave. Light ignores what lies between the column and the tile, so it can
seep a few tiles through rock, and it doesn't creep down slopes away from
the shaft: the price of being cheap. The glow is the first game's
stand-in, `fixed_light`, 4 levels dimmer: it shades the rock below the
surface and lets shallow caves be made out.

Daylight is worked out as tiles enter the tile cache (tables of the deepest
sky depth within 1 to 4 columns of each make that quick, and tell at once
when a tile is too deep to be lit). Digging a tile that changes a column's
sky depth relights the tiles within reach, a row a frame, queued as the
torches' changes are; one that doesn't relights just the tile and the floor
below it.

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

The radial table is packed (`gen_tables.packed_radial`): 3.9K where a
table of every offset a pass might read was 12K. A pass reads it only for
blocks of tiles within a tile of the pool's window, and beyond the window a
block's excess is FAR, which darkens it whatever it reads; so a row need
only be exact within 38 pixels of the miner's centre across, and rows only
76 lines down, and rows overlap where their zeros agree. Each cell row
finds its row's address from a table by |dy|, so the inner loop is
unchanged. Folding left and right would halve it again, but the loop's
index also reads the grid of excess, which doesn't fold.

### The store of changed chunks

The host holds the store, in its two spare sideways banks: 255 changed
chunks of 128 bytes, a quarter of the world. The parasite's directory
gives each changed chunk's slot there, and the parasite caches 40 of them
(5K in PWORLD), as `world.asm` describes:

- **Changes go to both.** `set_tile` changes the cached chunk and queues the
  change (the slot and the tile's offset, material and shape, or for a
  chunk's first change the whole chunk), and each packet carries as many
  queued changes as fit after its changed tiles; the host copies them into
  its banks as it reads the packet (`host_store`). So a cached chunk is
  dropped without writing it back, once nothing is queued for it. If the
  queue fills (32 changes), `set_tile` refuses, as when the store is full.
- **Fetched ahead.** The wanted chunks are those within a chunk of the tile
  cache, at most 6 x 6. Whenever they change, or a chunk is dropped, the
  parasite looks for a changed one that isn't cached, and asks for one a
  frame at the end of the packet (`cache_prefetch`): the host copies it into
  the parasite (`host_fetch`) before it writes the mailbox, so it is there
  when the next frame starts. The view moves a chunk in 20 frames at the
  fastest, so a new edge of 6 is fetched long before it is reached.
- **Dropped in turn.** A slot is taken free, or else from a chunk beyond the
  wanted ones with nothing queued for it.
- **Fetched at once** if a tile is asked of a chunk that isn't cached
  (`cache_miss`): `COMMAND_FETCH`, the slot and the address, over OSWRCH;
  the host copies the chunk once it has drawn the frame it is drawing, and
  sets `MAILBOX_FETCHED`. It shouldn't happen in play; `cache_misses`
  counts it, and the tests require none while fetching ahead.

Chunks could be packed between the two, at no cost to `tile_at`.

## Checking it

`tests/test_tube_game.py` plays on both machines (digging deep first, as
near the surface daylight outshines the miner's light), and checks the
displayed screen byte for byte every frame against the models: the host's
tiles, lit by the brighter of daylight (and torchlight) and the model's
light, with the sprite. One script drops torches, and checks they are in
view and light tiles beyond daylight.

`test_host_keeps_the_store` (in the same file) digs and drops a torch on
both machines, checks that nothing was fetched at once, then drops the
chunks round the miner from the cache, spoils them and digs on, so that the
dig fetches at once; then checks each cached chunk against the host's banks,
byte for byte. In py65, with `FakeHost` (`tests/conftest.py`) playing the
host's part: `tests/test_store.py` changes three times as many chunks round
the start as the cache holds, and plays along the surface and down a shaft,
checking every frame that the tile cache holds the world's tiles, that
every cached chunk is the host's, and at the end that every chunk came
ahead of need; `tests/test_world.py` fills the store and reads chunks back
through misses; `tests/test_daylight.py` checks the cache each frame too.

`tests/test_pieces.py` checks slots in py65: given, shown, their
visibility copied and freed by a sweep on the parasite, and composed on the
host as `tiles.compose` does.

`tests/test_daylight.py` plays the parasite alone in py65 (the host played
by a hook), down a shaft from the surface and along a tunnel, and whenever
relighting is done checks every tile in the tile cache against
`lighting.shaft_sun` and the glow, from the world as the parasite holds it,
and each column's sky depth.

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

Slots add about 30 cycles a frame (17,333 against 17,306 over the same
490 frames; with torches dropped, 18,827 against 18,801 over 794, the
worst frame unchanged).

Packing the radial table costs about 140 cycles a frame (17,455 against
17,311 over the same 490 frames; the worst 108,475 against 108,166), and
frees 8.3K. Every read over those frames where the excess isn't FAR reads
the model's value.

The store: taking the changes costs the host about 100 cycles a frame on
average while digging (Beebium, 300 frames on the B+), and about 3,700 in a
frame that carries a whole chunk (4,600 at most, with tiles); copying a
chunk to the parasite about 4,800, at most one a frame. The parasite pays
about 150 cycles a frame for the changes (2,600 in a frame that sends a
chunk), and for the cache about 230 a frame on average and 1,750 in a frame
that fetches (2,500 at most), with 121 changed chunks round the start
(py65, which doesn't count the Tube's interrupts for each byte moved). Over
test_daylight's 490 frames the mean frame is 17,836 (17,455 before the
store moved), the worst unchanged. PWORLD's tables end at `&A07B`, leaving
7.1K free below daylight's.

Dropping a torch floods twice (the torch's pool, then the miner's, as the
tile changed) and relights its surroundings: about 118,000 cycles, so the
host can miss a frame then.

## Not yet

- Picking torches up; torches that flicker; more than 24.
- The flood's spike: spreading it over two frames, or making it cheaper.
- The list can hold 255 cells; beyond that, cells could be left unlit.
- Untested beyond Beebium; the Master 128 not yet.
