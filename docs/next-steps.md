# Next steps

The agreed plan, as of 2026-10-19. Each step should end the way the work so
far has: a Python model of the behaviour, the 6502 checked against it (py65
for pure routines, Beebium for whole frames on both machines), coverage
checks that the interesting cases really happen, and a commit. See
`implementation-record.md` for the game as built, and `decisions.md` for the
decision log.

The suggested order is 2 and 3 together (they make digging rewarding), then
4 (atmosphere), with 1 and 5 slotting in wherever convenient.

## 1. Sprite priority with the spare palette bit

The miner should be able to pass *behind* some things: grass blades, a water
surface, ladders, later torches and furniture.

- Tiles are drawn in logical colours 8-15 and sprites in 0-7, and the palette
  maps both groups to the same eight physical colours. So every screen pixel
  already records whether it is terrain: in MODE 2, bit 7 of a byte for the
  left pixel and bit 6 for the right (`AND #&C0`).
- Extend this so that *foreground* terrain pixels are marked, and have
  `render_sprite` (in `asm/render.asm`) leave sprite pixels out where the
  screen pixel is foreground: compute a per-byte mask from the screen byte
  as well as the sprite's own mask. Exile does exactly this (see the sprite
  plotting notes in `docs/reference/exile/README.md`).
- Which pixels are foreground is a property of the material graphics, so it
  belongs in `tiles.py` (and the generated material pages).
- Cost: a few cycles per sprite byte; the sprite is drawn after vsync, ahead
  of the beam, so measure the margins again (see Beam safety in the record).
- Test: the screen model (`expected_screen` in `tests/test_tube_game.py`)
  applies the same rule; add a scene with the player in front of and behind
  foreground pixels.
- Trees: each tree in front of the miner or behind, at random (from the
  generator's hash, by trunk column), for a sense of depth. So for trees the
  choice is per tree, not per material: a bit in the part's shape byte, or
  a second set of tree materials.

## 2. An on-screen display (HUD)

The player can't see how many blocks they carry. Start with the inventory
count; leave room for health and the item in hand.

- The view is 31 character rows of the 32 in screen memory; there is no
  spare screen for a panel. Options: overlay the HUD on the view (redrawn
  each frame, with save-under like the sprite, at a fixed view position), or
  shorten the view (fewer rows, R6) and use a separate small screen area
  with a mid-frame CRTC change (harder; Exile's water line shows mid-frame
  palette changes are practical). Recommend the overlay first.
- Digits: a tiny 4 x 5 font, generated from Python, in the render region.
- Mind the beam: draw it where and when the beam isn't.

## 3. Crafting and the first progression loop

The Terraria loop: dig, collect, craft, dig better. A first slice:

- **Inventory by material**, not one count: soil, stone, ore, gems (and wood
  once there are trees). A small table of counts.
- **A crafting action** (a key, or standing at a crafting station placed in
  the world) turning materials into items.
- **The first items:**
  - a better pickaxe: more quarters per dig (`QUARTERS_PER_DIG` in
    `actions.py` becomes per tool), so stone takes two digs, not four;
  - the double jump, which is already behind `ABILITY_DOUBLE_JUMP` and on from
    the start: make it earned instead (`STARTING_ABILITIES = 0`).
- Then the next flight stages, as decided: thrust boots (a recharging burst),
  a fuelled Exile-style jetpack, longer endurance. Fuel ties flight to
  mining.
- Keep the data in tables generated from Python, with the rules in models.

## 4. Light and darkness

The concept doc picked this out as worth keeping from Terraria: underground
is dark, so torches matter and caves feel deep.

- Tile-level light, not per pixel: a light level per tile in the tile cache
  (the shape byte's spare bit, or a third plane), computed from sky exposure
  and placed torches.
- Drawing dark tiles: on a standard ULA there are only eight colours, so
  "dark" means black or a sparse dither; with a Video NULA, the tile colour
  group can be given a dim palette. Design for both.
- Torches: a placeable item that lights a radius; recompute light only
  locally when one is placed or dug out.

## 5. Spilling changed chunks to disc (and saving games)

The world bank holds 104 changed 8 x 8 chunks (128 bytes each); a keen
tunneller will fill them, and then digging is quietly refused.

- When the store is full, write the least recently used chunks to a file
  through the OS (OSFIND/OSGBPB, so it works on DFS, MMFS, ADFS and
  Econet), and read them back when needed. The directory entry can mark a
  chunk as "on disc".
- Compression first, before the disc: most of a changed chunk is still
  what the generator made. Measured by the chunk lab (`uv run
  strat-chunk-lab`, random mining, 181 chunks): a chunk has 14 tiles
  changed on average (median 12, at most 48); 63% of changed tiles are dug
  out, 36% partly dug, 1% anything else. Stored as two 8-byte maps (which
  tiles differ from the generator's; which of those are dug out), then a
  byte for each partly dug tile (its shape) and two for any other, a chunk
  takes 21 bytes on average (at most 36; a quarried room 16), against 128
  now. In 16-byte granules that is about 31 bytes, so about 420 chunks
  instead of 104 in the same 13K: four times as much digging before the
  store is full. Fall back to the raw 128 bytes when that is smaller (a
  base packed with placed pieces).
- Decoding: `tile_at` would read a decoded chunk, from a small cache of
  them (a few chunks of 128 bytes, the most recently used), decoded when
  the tile cache fills a row or column; a change re-encodes the chunk. So
  frames cost what they do now, except when a chunk is decoded or
  re-encoded. The store needs an allocator for chunks of varying size
  (granules, compacted when fragmented).
- This is also how games are saved, and the basis for several worlds on
  disc (a world is a seed plus its changed chunks).
- Disc access during play stalls the game; do it at moments the player
  won't mind, or between frames in small pieces.

## Smaller items noted along the way

- **Beebium:** all the fixes from our reports are pushed to Beebium's
  `origin/master` (not yet released as v0.11.0). When it is released, move
  to it and:
  - use `video.screen_region()` (#195) instead of the per-machine region in
    `tests/conftest.py`;
  - turn the beam-race measurements into a test, with watchpoint conditions
    on the beam position (#186, #196), for example `write && shadow_access
    && addr >= ... && crtc_row > ...`;
  - check the run-state table (#191) against our use of the client.
- **Performance:** the worst frame (scrolling two columns and a row) took
  about 30,000 of 40,000 cycles before digging and slopes were added; measure
  again. Reading the keys through OSBYTE costs 2,600 cycles a frame on the
  Integra-B (IBOS hooks BYTEV); scanning the keyboard directly would save
  most of it. `render_columns` is the next place to optimise.
- **Art:** tiles and the miner are placeholder art drawn by code; grass on
  slopes loses its green top. Tiles and sprites should come from images.
- **Master 128:** the memory model allows for it (ACCCON X), but Beebium
  doesn't emulate it yet (#189).
- **NFS/ANFS:** PAGE (OSHWM) under the Econet filing systems hasn't been
  measured; the loader assumes `&1900`.
