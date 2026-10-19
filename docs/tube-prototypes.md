# Tube prototypes

Prototypes for deciding how Stratagem uses a 65C02 second processor
alongside the expanded host (see
`docs/hardware-requirements-and-capabilities.md`). Each answers one question
by measurement, on both targets in Beebium.

1. Tube plumbing: what each way of moving data costs the host.
2. Light on the parasite: per-cell light centred on the miner's exact
   position, and how many cells change per frame.
3. Host drawing with the memory freed: masked, pre-dithered, dark fills.
4. Double buffering (B+ only: the Integra-B's video reads only main RAM)
   against a single screen with raster-timed updates.

## 1. Tube plumbing

`asm/tube_proto.asm` (`TUBEH` in the host at `&2000`, `TUBEP` in the
parasite at `&1000`), measured by `tests/test_tube_proto.py` (run with `-s`).
The host extends OSWRCH and OSWORD as Second Processor Elite does, and
pulls and pushes 256-byte blocks through `&0406` as ADFS does (three NOPs
per byte: the parasite's polled loop must keep up).

Host cycles (2 MHz), 3 MHz 65C02 parasite, Beebium 0.11.0:

| Exchange | B+128K | Integra-B |
|---|---|---|
| OSWRCH stream, per byte (idle loop, WRCHV, handler) | 90.5 | 91.9 |
| Host pulls 256 bytes (type 6), with claim and release | 6,108 | 6,108 |
| Host pushes 256 bytes (type 7), with claim and release | 5,844 | 5,844 |
| OSWORD, 128 bytes each way | 8,907 | 9,079 |
| Empty OSWORD round trip | 263 | 266 |
| A 2-byte OSWRCH command | 167 | 167 |

- Bulk data costs about 20 host cycles a byte by block transfer (plus about
  900 for claim, set-up and release), against about 90 through OSWRCH and
  35 each way through OSWORD.
- OSWRCH suits commands: up to 24 bytes queue in R1 without stopping the
  parasite. Anything larger stalls the parasite while the host catches up.
- During a block transfer the parasite is in its interrupt handler, so
  both processors are busy for its duration (about 3 ms).

## 2. Light on the parasite

The model is `lighting.smooth_miner_light`: a level per character cell
(2 pixels by 8 lines), falling off with distance from the middle of the
miner's box, so the pool glides with the miner. Each tile's cells lose the
excess path cost that the tile flood (as now) finds, so walls and corners
still shape it. `uv run strat-glide-lab` walks the miner through the mine
scene and writes `build/lighting/glide-{tile,cell}.{gif,png}`.

Cells changed per frame over that walk (93 frames: walking, jumping):

| Miner's light | level | mask | pixels |
|---|---|---|---|
| By tile (as now) | 58.5 mean, 480 max | 44.0, 364 | 20.1, 164 |
| By cell | 125.8, 333 | 65.6, 201 | 27.3, 92 |

Only a change of a cell's pixels needs a redraw, and the parasite can tell
exactly: `lighting.cell_visibility` gives each cell of each tile kind a bit
per Bayer threshold that falls on a coloured pixel, and a change shows only
if a marked threshold lies between the old and new mask classes (checked
against real pixel differences for every kind, cell and pair of levels).
So smooth light asks the host to redraw about 27 cells a frame, at most 92:
fewer than the tile-at-a-time light's bursts of 164. (These counts are for
the first model, whose walls' faces copied the open ground beside them; with
faces lit at their own distance, it is 21 a frame.)

`asm/smooth_light.asm` (`SMOOTH`) is the parasite pass, checked against the
model block for block and queue for queue by `tests/test_smooth_light.py`,
which times it in py65's 65C02 (run with `-s`). It reads a 16K radial table,
a tile map standing in for the parasite's world, per-kind visibility pages
and a grid of each block's excess (filled by the flood); it keeps a plane of
block levels (4K).

Light per cell first cost 55,000 cycles a pass while walking. Light per block
of two cells (4 pixels by 8 lines: square, and as wide as the Bayer pattern)
halves the work and looks the same (`glide-block.gif`); what the host
redraws is unchanged (19.9 cells a frame against 21.1). A pass now covers
only the tiles within reach of the miner now or at the last pass, does
nothing if nothing has changed, and sets up each row with a few bytes.

65C02 cycles a pass (a 3 MHz frame is 60,000; 4 MHz, 80,000):

| | per cell | per block |
|---|---|---|
| Walking the mine scene, mean | 34,311 | 24,648 |
| Walking, max | 76,464 | 69,884 |
| Random ground (walking and falling speeds), mean | 37,500-43,700 | 29,300-36,300 |
| First pass (clears the grid; lights the pool from nothing) | 66,700-87,500 | 91,800-112,700 |

Per block, while walking: the blocks themselves 7,700 (107 tiles, 2
blocks each, 17 cycles a block); changed blocks 8,200 (about 55 a pass,
each cell's visibility tested); the flood 4,000 on average, but about 25,000
when the miner enters a tile, which sets the maximum; rows 4,700.

### Soft shadows

`smooth_miner_light(..., soft=True)`, now the parasite's light, blends each
block's excess with the tiles around it (`lighting.soft_blend`): half its
own tile's, half that at its tile's nearest corner (the four tiles' average,
rounded), so 5:1:1:1, a tile the pool doesn't reach counting as
MINER_LEVEL. Shadows fade over a tile, as the pool does, instead of
stopping at tile edges. Interpolating (9:3:3:1) looked the same and cost
half as much again; the four blocks around a corner share its average. The
host redraws about the same as with hard shadows (18.7 cells a frame).
`build/lighting/shadows.png` sets hard and soft side by side.

### The flood

The flood is generated from the model, unrolled (an entry's neighbours at
fixed addresses), after reading each window tile's clear flag from the map
a row at a time: 5,300 cycles instead of about 20,000, but about 10K of
code. When the miner enters a tile, the flood and the soft blend together
cost about 22,000: reading the map 4,000, the flood 5,300, the excess 2,500,
the corners 3,300 and the blocks 7,500.

Blending only tiles the light can reach would save almost nothing: 77 of
the window's 81 can be lit.

| 65C02 cycles a pass | hard, looped flood | soft (9:3:3:1), unrolled | soft (corners), unrolled |
|---|---|---|---|
| Walking, mean | 24,648 | 24,255 | 23,323 |
| Walking, max | 69,884 | 72,642 | 66,404 |
| Random ground, mean | 29,300-36,300 | 28,100-34,800 | 26,900-32,500 |
| Random ground, max | 61,400-79,300 | 60,400-77,100 | 53,600-72,100 |

The maximum is a pass where the miner enters a tile: the flood and blend
(about 22,000), and many changed blocks (up to 144, about 25,000 to test
and queue: each is about 177 cycles, little of it avoidable), as the
excess shifts with the miner's tile.

## 3. Host drawing from the Tube

`asm/tube_draw.asm` (`TDRAWH`, `TDRAWP`), checked and timed by
`tests/test_tube_draw.py` (run with `-s`). The parasite lists, per cell to
redraw, everything the host needs: the mask's low byte, the cell graphics'
address and the screen address (5 bytes). The host reads the list a byte at
a time (transfer type 0: each read raises an NMI in the parasite, which
puts the next byte in R3) and only copies, through the masks or straight
at full light. It reads each entry while drawing the cell before, a byte
every two lines: long enough for the parasite to refill R3 (about 25 host
cycles at 3 MHz), so those reads need not poll. A list ends with an entry's
worth of padding, read ahead and ignored.

Host cycles (2 MHz), 3 MHz 65C02 parasite:

| | B+128K | Integra-B |
|---|---|---|
| A list (claim, set-up, count, first entry, release) | 1,053 | 1,046 |
| Each further cell, dimmed | 214 | 205 |
| Each further cell, full light | 178 | 181 |

Reading each entry before drawing (a subroutine per byte, polling) cost
315 and 280 a cell: the host waited for the parasite. The renderer's own
redraw of a tile costs about 350 a cell, finding each cell's graphics,
light and screen address itself.

So the smooth light's redraws (prototype 2: 27 cells a frame on average,
92 at most) cost the host about 6,700 cycles a frame, 20,400 at most.
