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
  side (superseded: see "No cavities" below). Changed chunks are 128 bytes (104 fit in the world bank);
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
- **No cavities:** a dig always opens space next to the space the player is
  in. Digging erodes from the side nearest the player (when that leaves no
  exact shape, the largest shape within what is left). Diagonal digging is
  worked column by column, nearest first; going down, in a column: across,
  then the step (cut back to a ramp even if partly dug), then down; going up,
  the step, then up. "Most left" applies only across, at the player's
  height. tests/test_digging_model.py checks it in every direction.

## 2026-10-19

- **Lighting direction** (from the lighting lab, `uv run strat-lighting-lab`,
  modelled in `tools/stratagem/lighting.py`; ideas in `lighting-tactics.md`):
  a light level per tile, 0-15, drawn by a world-aligned 4 x 4 Bayer black
  dither. Daylight falls straight down each column and spreads a little;
  torches and the miner's light spread through open tiles, never through
  walls. Light soaks into walls at a higher cost, so their faces are lit and
  they darken inwards. Light is interpolated per character cell, since the
  renderer chooses a mask per cell anyway. Open space below the surface gets
  a dark backdrop, so light shows in it. First step: render with fixed
  levels, to measure the cost.

## 2026-10-20

- **A second processor:** the game moves to a 65C02 second processor (3 MHz
  or faster), the host drawing what it sends (`docs/tube-game.md`). The
  host-only game is kept, on its own disc, as the reference and for
  comparison.
- **Light:** the miner's light is the smooth per-block light with soft
  shadows (corner-averaged, 5:1:1:1), brightened by daylight; the host draws
  only the cells whose pixels change, from a list the parasite sends.
- **No double buffering:** the Integra-B can't show shadow RAM, so the game
  must work with one screen; drawing stays ahead of the beam.
- **The Tube game is accepted:** played on a B+128K with a 3 MHz 65C02, it
  plays smoothly, with no visible problems; the occasional late frame went
  unnoticed. Torches, with per-tile light beside the miner's per-block light,
  look right. Development carries on from the Tube game.
- **Daylight down shafts:** the look of the lab's "down shafts, with a glow"
  (sunlight spreading through open tiles, the old stand-in four levels
  dimmer beneath it, so shallow caves can still be made out), built
  cheaply: by columns (`lighting.shaft_sun`), from each column's sky depth,
  at the cost of light seeping a little through rock and not creeping down
  slopes. The full model needed a 2K window, background work and about
  12,000 cycles a frame; this needs 1K of tables and about 1,200.
- **A tile set planned ahead** (`docs/tile-set.md`): terrain erodes; pieces
  (trees, ladders, ropes, platforms, built blocks, doors, stations) are
  whole tiles that break whole, with a part number in the shape byte, so
  objects are rules over tiles, not a table; a two-bit background for back
  walls; property tables in place of material tests. Tiles stay two fixed
  bytes where read every frame; changed chunks are to be packed (about 21
  bytes instead of 128, measured) before spilling to disc.
- **Pieces are drawn through slots:** the host keeps every piece in its
  program RAM and composes each pair of piece and backdrop in the tile
  cache once, into a slot that the renderer draws as an ordinary material
  (56 slots at `&B100`), rather than composing as each cell is drawn (80-130
  cycles more a cell, in every drawing path). Pieces have their own masks,
  so black stays black. The torch is the first piece.
- **Daylight tapers down shafts:** sunlight loses a level for each 4 tiles
  below the column's surface, so a shaft darkens slowly as it deepens (the
  glow fades over about 11 tiles; this over about 60). Chosen in the
  daylight lab over a narrower reach (2 columns) and a dimmer start for the
  shaft's walls.
- **Built things don't stop daylight:** making daylight stop at walls (a
  roofed hut dark inside, light kept out of caves beside shafts) was built
  and measured, at about 700 cycles a frame more on average, up to 9,400 in
  the worst frame, and nearly all the parasite's spare memory, then undone.
  Darkness inside a building isn't worth that. Pieces (built blocks, doors,
  trees) are clear to daylight: a column's sky depth passes through them, so
  they are lit as the sky over them, and so is what they enclose. Terrain
  still sets the sky depth, as before. The property tables give pieces this
  (the light property).
- **The radial table packed, not computed:** the miner's light reads its
  radial table about 100 times a frame (276 at most). Computing the level
  from squares would take 0.4K but about 1,200 cycles a frame more
  (estimated); folding left and right doesn't fit the inner loop, whose
  index also reads the grid of excess. Packing the rows, exact only where a
  block's excess can be other than FAR and overlapping where they agree,
  takes 3.9K where the table was 12K, at about 140 cycles a frame.
- **The host-only game is dropped:** Stratagem is a game for a BBC with a
  6502 second processor (a B+ 128K or a Model B with Integra-B, and the
  Master later). The host-only game's own files and disc are gone; what it
  shared with the Tube game stays. Its tests now run on the parasite's code
  (py65) or were covered by the Tube game's (frames in Beebium).
- **The host keeps the store of changed chunks:** in its two spare
  sideways banks (255 chunks, a quarter of the world, against the
  parasite's 104), with the parasite to hold only a cache of those near the
  view, fetched ahead of need: the host draws each frame inside its OSWRCH
  handler, so a chunk asked for when needed could wait most of a frame.
  Changes go to both copies, so the parasite never writes a chunk back. A
  first step keeps the parasite's whole store and checks the host's copy
  against it. Packing chunks, if needed, belongs between the two.
- **The parasite caches the store's chunks, fetched ahead:** 40 slots for
  the at most 36 chunks within a chunk of the tile cache, one fetched a
  frame through the packet as the view nears it; the view needs 20 frames
  to cross a chunk, so even margins all round need no prediction of where
  the miner goes. Chunks are dropped in turn from beyond the wanted ones,
  with nothing queued for them; a chunk wanted at once is fetched by
  `COMMAND_FETCH`, counted, and never needed in the tests.
- **Built things need holding up:** every piece is held from below, from
  above, or from below or the side within a span (a strength that drops by
  one for each step sideways from something held from below), as a small
  cellular automaton run only when tiles change (`tile-set.md`, Support).
  Unlike Terraria, built blocks fall without support, which makes building
  a matter of where the pillars go; the span (3 to 5) is to be chosen by
  playing.
- **Trees are features placed a column at a time:** a table of a byte a
  column (the covering tree's trunk offset and height) made with the
  surface heights, so a tile's tree part costs one look-up, not a search
  (`features.py`). Leaves are held by the canopy over their trunk, and edge
  leaves hold only what is above them, so touching trees stand and fall
  apart.
- **The span is 5:** chosen from the feature lab's structures; a roof of 8
  between walls holds, a ledge reaches 5 from its wall, and a crossing needs
  a pillar every 10 tiles (`support.GAME_SPAN`).
- **Support on the 6502 keeps strength in the shape byte:** a piece's
  strength in bits 0-2, so a check needs only its neighbours, and changes
  spread through a queue a few tiles a frame. Torches are left out until
  a falling torch can leave the torches' list.
- **A felled tree is seen to fall, and drops wood to pick up:** a piece
  falls only every 4 frames, so a tree comes apart over most of a second;
  each part of its trunk drops a log, an item drawn as a sprite, which
  falls to the ground and is picked up by touching it (as in Terraria),
  rather than wood going straight into the inventory, or logs as tiles
  (coarse, and costly in changed tiles). The sprites' machinery will serve
  later dropped items and creatures.
- **Dropped items burst out and are gathered in, not piled up:** a broken
  trunk's logs spray out ballistically, bounce, rest half a second, then
  fly to the miner and are his (the loot burst and magnet of many games).
  They show how many there are, then are gone in about a second, so few
  items are out at once and the sprites' cost and flicker are brief. Logs
  that piled up (sand-like) and were picked up with a key looked good, but
  kept many sprites on screen, flickering as the miner walked, and cost
  more to move.

## 2026-10-23

- **Sprite priority by colour group, per piece:** a piece in front has
  `PIECE_FRONT` in its shape byte and is composed with its pixels in the
  sprite colour group; sprites leave their pixels out over that group, as
  Exile does. The choice is per tile, not per material, so each tree can be
  in front or behind by the hash of its trunk column (about half are in
  front), and later doors and furniture can use the same bit. A second set
  of tree materials was the alternative, but material numbers are short
  (slots start at 24). The cost on the host is a compare per sprite byte
  (288 cycles for the miner), and about 35 cycles more for each byte over
  a pixel in front. Items, drawn after the miner, pass behind him too.
- **Inventory counts are BCD bytes, capped at 99:** a count takes a byte
  whatever its cap, and 99 is the most two digits show. As BCD the cap is
  the byte's own, the clamp is the carry, and drawing a count needs no
  conversion, only its nibbles. The arithmetic is on the 65C02 parasite,
  which clears decimal mode on interrupts (`inventory-and-crafting.md`).
- **Crafting is a shaped grid with a key for each cell:** T Y U / G H J /
  B N M (and the Master's keypad) are the cells, and the arrow keys move
  the material chosen, so a recipe is drawn, not dragged with a cursor. A list of makeable recipes, as in Terraria, was the
  alternative: easier, but with nothing to discover. Minecraft's players
  learnt its shapes from each other and a wiki; ours learn them from a
  small manual, as period games had, from shapes that look like their
  things, and from finds in the world, and a recipe book keeps what's
  been made or found (`inventory-and-crafting.md`).
- **Kinds carried, and the hand until it can be chosen:** wood, soil,
  stone, ore and gems are counted apart; dug grass is soil, and ore and
  gems can be placed back as blocks, as in Terraria. Until the pack screen
  lets the hand be chosen, it follows the kind last dug, and placing with
  none of it left moves it to the first kind carried, so the miner can
  always put back what he has. Item kinds are inventory kinds, so a
  gathered item adds to its own count.
- **Inventory counts are binary after all, not BCD:** BCD saved only the
  conversion to digits, which the paused pack screen can afford, and it
  forbade `INC` and `DEC` on counts, a rule easy to break later. In play a
  gain is a compare and an `INC` (15 cycles; BCD's was 19) and a spend a
  `DEC`. The cap stays at 99, the most two digits show.
- **No signal when a count is full:** at 99 the extra is lost silently,
  which is spoil disposal for bulk materials; rare kinds seldom reach the
  cap, the pack screen shows the counts, and finds that matter are owned
  bits, which can't overflow. Left to the player's diligence until playing
  shows otherwise.
- **The pack pauses by the parasite sending the pack's packet instead of
  the game's:** P is read like any key, the parasite runs no game frame
  while the pack is open and sends a short packet (the kinds shown, their
  counts, the hand), and the host draws the panel from it; closing is a
  game frame with no input that redraws the view, as a camera jump does.
  The host stays a drawer of packets, and nothing new is needed to resume.
  The panel spans the top of the view, black, over the view left as it
  is; dimming the rest by palette is for later. The kinds shown are fixed
  on opening, so the hand moving off a kind with none left doesn't shift
  the others; and a move redraws only the arrowheads, as redrawing the
  panel showed it half drawn for a frame. P opens it for now.
- **A second byte of input, for TAB:** P filled the input byte, so the host
  writes `MAILBOX_KEYS` too, in the same transfer, with `MAILBOX_FETCHED`
  moved down to `&8C`. Crafting's keys will need more than another byte
  can hold, so the crafting screen will send keys its own way; this byte is
  for play. TAB cycles only through kinds held that place something, as
  it is for placing; the pack chooses any.
- **The hand is shown as one more item:** the parasite appends it to the
  packet's items for a second after any change of hand, marked as by the
  miner, so the host draws it with the items' code, each frame, last. A
  host-side icon of its own would have needed new drawing code and a
  timer on the host. Each kind gets a 6 x 5 item picture rather than its
  8 x 16 tile icon, which the sprite code (three bytes wide) can't draw.

## 2026-10-24

- **The host scans the keyboard itself:** OSBYTE `&81` cost about 270
  cycles a key, 2,429 a frame for play's nine, and crafting will add a
  dozen more. Writing each key's number to the System VIA's port A and
  reading bit 7, as the MOS does inside, costs about 31; the keys are a
  table, read with interrupts held off and the MOS's scanning stopped,
  then restarted. The MOS still sees the keyboard between frames.
- **Crafting's first kinds:** planks, torches and the workbench join the
  inventory as kinds 5 to 7, so they show in the pack. Torches are counted:
  T spends one, and the miner starts with 8 (`STARTING_TORCHES`), enough
  to reach ore and wood for more. Soil, stone, ore and gems use their
  tile's graphics in the render region's material pages as their icons, so
  only the other kinds' icons take room (a table of addresses, by kind,
  finds each).
- **The hand's grid:** the grid holds what's been taken from the counts,
  so a recipe's cost is its shape, and closing the pack gives it back.
  Shapes match anywhere in the grid, not mirrored (the torch, ore over
  wood, would read the same either way). Made things go straight into
  the counts, not out as items: the game is paused, and the counts
  changing is feedback enough. The cell keys come as a number (the first
  held), not bits, so nine cells and three more keys fit in one byte.
  A kind once shown stays shown while the pack is open; one gained joins,
  redrawing the panel. The host redraws only the counts and cells that
  changed, so a key's redraw (about 6,000 cycles) fits inside a frame.
- **Z and X choose in the pack, not the arrow keys:** they move the miner
  left and right in play, so moving the hand left and right with them
  feels natural. They step through the kinds in order, across rows, so
  there are no keys for up and down (K and M would have been the obvious
  ones, but M is a cell of the 3 x 3 grid). Both hands are now on the
  left of the keyboard for choosing and laying out; DELETE, RETURN and
  COPY stay on the right.
- **The grid's keys move a key left, to R T Y / F G H / V B N:** that
  keeps them clear of Z X and of K M, so all four of play's movement keys
  move the hand in the pack, up and down a row included.
- **The pack shows only kinds held:** at first it also showed the hand
  whatever its count, so a new game opened on "soil 0". Now opening moves
  the hand to the first kind held if its own isn't; with nothing held, the
  pack shows only the grid and the hand stays. A kind that runs out while
  the pack is open still stays, at 0, until it closes, so slots don't move
  while crafting.
- **Torches are placed with SPACE, like anything else; T is gone:** a torch
  is a kind that places the torch material, aimed as a block is (not into
  the miner's own tile, as T dropped it). TAB and the pack choose it. The
  limit of 24 in the world stays (`TORCH_MAX`, now in `inventory.py`).
- **Planks are red,** like the wood they come from: the first icon, yellow
  with staggered joints, read as bricks. Boards with dark seams now.
- **A torch with nowhere to go goes in the miner's own tile:** aimed like a
  block, a torch often had no room (the ground rising ahead at the start,
  a narrow tunnel), so, as T did, it falls back to the tile at the middle
  of the miner, if that is empty. It still waits out the dig's cooldown.
  PGAME has 8 bytes left, so the checks live in PLIGHT (`torch_room`,
  `torch_own_tile`).
- **L makes, and TAB chooses, in the pack:** L, the act key in play (dig),
  makes what the grid lays out, in place of RETURN; TAB moves the hand to
  the next kind shown, round again, as it cycles the hand in play, but to
  any kind, wood and planks included, since those are what's crafted
  with. More of the pack's keys are now play's.
- **Digging no longer puts what's dug in hand:** mining, the hand was
  nearly always the thing just dug, which is rarely what you want to
  place. The hand now changes only by choice (TAB, the pack), or when it
  runs out.
- **Tools, planned:** by hand, soil and grass take 4 digs and stone, ore
  and gems can't be dug; trees still break whole, so wood, planks, the
  workbench and a wooden pickaxe (a T of planks, at the bench) are the way
  out. Pickaxes are kinds in the pack, the best held used, and wear out
  after a number of digs (about 60 for wood, 130 for stone, as in
  Minecraft), breaking with no warning shown, a count spent.
- **The workbench is one tile, a passable piece held from below:**
  `tile-set.md` planned it as two tiles; one is enough to start, and its
  picture is the pack's icon. Dug, it breaks whole and comes back as an
  item, as a tree's part gives wood. "Near" is within 3 tiles across and 2
  up or down of the miner's tile, found once, on opening the pack.
