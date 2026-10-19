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
fewer than the tile-at-a-time light's bursts of 164.

`asm/smooth_light.asm` (`SMOOTH`) is the parasite pass, checked against the
model cell for cell and queue for queue by `tests/test_smooth_light.py`,
which times it in py65's 65C02 (run with `-s`). It keeps a plane of cell
levels (8K) and reads a 16K radial table, a tile map standing in for the
parasite's world, and per-kind visibility pages. A pass covers only the
tiles within reach of the miner's centre now or at the last pass.

65C02 cycles a pass (a 3 MHz frame is 60,000; 4 MHz, 80,000):

| | mean | max |
|---|---|---|
| Walking the mine scene | 34,311 | 76,464 |
| Random ground, walking and falling speeds | 37,500-43,700 | 67,000-87,000 |
| First pass (the whole pool from nothing) | 66,700-87,500 | |

About 40% of a pass is the cells themselves (16 cycles each, unrolled
four to a tile), a third handling changed cells, and the rest rows and the
flood (only when the miner changes tile or tiles change).
