# Decisions

A running log of design decisions. Add to it whenever one is made.

## 2026-10-18

- **Targets:** B+128K and Model B with Integra-B first, then the Master 128.
  32K main + 20K shadow + 48K sideways RAM; one 16K bank is left free for
  the user's ROMs.
- **OS stays resident:** all file access goes through the OS and the
  current filing system (DFS, MMFS, ADFS, NFS/ANFS).
- **Screen:** an Exile-style 16-colour MODE 2 derivative with two
  eight-colour palette groups; keep palette code isolated so that Video
  NULA can be supported later.
- **Toolchain:** beebasm; Python tools under `tools/stratagem` run with uv;
  tests use pytest with Beebium for whole-machine tests and py65 for pure
  routines.
- **Machine detection:** IBOS by OSBYTE `&49` (X=`&FF` returns `&49`)
  before the OS version from OSBYTE `&00`, which IBOS makes report 2.
- **Memory model:** user RAM and screen RAM share `&3000`-`&7FFF` on every
  target; the renderer runs from a 12K render region at `&8000`-`&AFFF`
  (ANDY on the B+, a sideways bank elsewhere). See `architecture.md`.
- **Screen geometry:** 128 x 256 pixels, 16K at `&4000` with a 16K hardware
  wrap, as in Exile Enhanced; screen-side `&3000`-`&3FFF` is render-only RAM.
- **World size:** 256 x 256 tiles. A bigger game comes later from several
  worlds stored on disc.
- **Tiles:** 8 x 16 pixels (4 bytes x 16 lines = 64 bytes; roughly square
  given MODE 2's wide pixels), so the view is 16 x 16 tiles and the world is
  16 x 16 screens.
- **Keys:** Z left, X right, K up, M down, L action, plus SPACE and SHIFT:
  an emerging standard that suits emulators and real machines. Other keys
  may be added.
- **Scrolling:** cell granularity (2 pixels, 8 lines); 31 of 32 rows
  displayed so new rows are drawn hidden; new columns drawn after vsync
  ahead of the beam; both axes per frame; a camera window with an eased
  lead; a 32 x 32 tile cache in low RAM. See `architecture.md`.
- **Progression:** follow a Terraria-like progression. Flight is earned in
  stages, starting with a double jump (then, for example, thrust boots, a
  fuelled Exile-style jetpack, longer endurance).
- **Graphics detail** is set aside for now; tile *shapes* (slopes, partly
  dug tiles) are in scope, as they change play.
- **Double jump** is the first flight stage: a fresh press of K in the air,
  restored on landing, gated by an ability bit (on from the start until it
  can be earned).
- **Gradual digging:** each dig removes quarters of a tile from the side
  dug from (grass 4, soil 2, stone/ore/gems 1 per dig), visibly; the tile
  goes into the inventory when the last quarter goes. Tiles are kinds
  (material + dug state); collision is by solid rectangles; walking into a
  ledge up to a tile high climbs exactly its height.
- **Two-byte tiles:** material + shape (+ background bit), for flexibility.
  Shapes are erosions of a 4 x 4 quarter-cell grid from any side: flat,
  45 and 22.5 degree ramps (61 shapes); digging erodes from a shape's own
  side. Changed chunks are 128 bytes (104 fit in the world bank);
  compression or disc spill can follow. Walking follows slopes up (ledge
  climbing) and down (ground snapping).
- **Language workspace:** `&0400`-`&07FF` holds non-pointer variables now
  that zero page is full (`asm/variables.asm`).
- **Diagonal digging:** holding a horizontal and a vertical direction with L
  digs a 45 degree sloping tunnel: dig whatever is solid in the path of a
  one-tile diagonal step (across then down, or up then across), lowest
  first, but first shape the step into a ramp (the floor under the leading
  edge going down, the tile ahead at the feet going up). While L is held, K
  aims rather than jumps.
- **No climbing while digging down:** with L and M held, slopes and ledges
  ahead aren't climbed, so a diagonal dig cuts down into a rising slope
  instead of walking up it. Digging straight ahead into a slope still walks
  up it: digging down a little first, to make a pit, is part of the game.
- **Even digging:** when several tiles need digging (a wall as high as the
  player, or the path of a diagonal step), dig the one with the most solid
  left (the lowest, of equals), so they are cut back together.
