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
