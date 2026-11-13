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
- **Two hands and a tool belt on the function keys:** L digs with the
  tool in the tool hand, SPACE places the hand, so digging and building
  never fight over one hand, as they do in Minecraft. The belt's ten slots
  are the red function keys, a Beeb's natural tool bar: loaded in the pack
  (a function key with a tool as the hand), chosen in play. Play reads the
  function keys only every fourth frame, which costs 72 cycles a frame on
  average rather than 288. A slot holds a kind, not one tool.
- **Digging by the tool in hand:** bare hands dig soil and grass a quarter
  at a time and can't dig stone, ore or gems; the wooden pickaxe digs as
  the miner did before; the stone pickaxe twice as fast in stone and ore.
  The parasite swaps PGAME's per-material table for the tool's row when the
  tool in use can change, rather than looking it up on every dig, which
  would have meant changing the digging code in full PGAME. Tools wear by
  digs of the ground, not chops, and break silently (60 and 130 digs).
- **Placing: passable things may overlap the miner, and a hand that moves
  on waits for a new press.** A workbench was hard to place on flat ground,
  since the tile ahead usually overlaps the miner, which is right for a
  solid block but not for a bench or a torch, which can be walked through.
  And with SPACE held, placing the last bench moved the hand to the torches
  and placed one on it six frames later: now when the hand moves on by
  itself, the new kind is shown above the miner but not placed until SPACE
  is released and pressed again (`zp_place_wait`).
- **The belt is on the keys 1 to 9, not f0 to f9:** the function keys can
  need a modifier on an emulator's host keyboard, and most map f0 to the
  host's F10, breaking the order; the digits are always where expected,
  and nearer to hand. Nine slots, not ten. A belt key in the pack also
  takes its slot into the tool hand, so the belt's arrowheads move there,
  and hanging a tool also chooses it.
- **A belt key always shows its tool:** pressing the number of the tool
  already in hand showed nothing, which looked like the key had failed.
  Now any press shows the slot's tool above the miner for a second.
  Showing both hands all the time, beside the miner, was considered and
  set aside for now: about twice the host's cost every frame, and the
  pictures would lie over a tunnel's walls.
- **Bare hands are shown, as a blue outline:** like the pack's empty cells.
  Choosing an empty slot shows it, and so does a tool breaking with none of
  its kind left, which otherwise went unnoticed; a break with a spare shows
  the spare.
- **0 shows the tool in use, with its slot's number:** any tool shown above
  the miner now has its belt slot's number beside it, as a second item
  picture; 0 shows it on demand without choosing anything.
- **A kind run out, in the open pack, is an empty socket:** its icon and a
  0 gave the impression, at a glance, that it was held. It keeps its place,
  so nothing shuffles, but is drawn as the blue outline that means empty
  elsewhere, with no count.
- **The belt holds tools, not kinds:** a slot held a kind, so one pickaxe
  made could hang in three slots. Now a belt key in the pack moves a tool
  between the pack and the slot, out of the pack's counts and back, and
  each slot's tool has its own wear; one that breaks leaves its slot empty.
  The pack keeps a total of its tools' wear for each kind: one given back
  adds to it, one taken carries as much as it can. So the digs left in all
  your tools of a kind are exactly kept, nothing is repaired by moving it,
  and nothing is lost.
- **The loading screen is the cover in MODE 1, six colours:** black and
  white steady, the other two logical colours flashing cyan/red and
  yellow/blue, with the flash bit switched every line, so lines alternate
  KWCY and KWRB (stratagem.loading_screen, LOADSCR). With all four
  flashing, eight colours show but no line has both black and white, so
  the cover's black outlines go grey; steady black alone (seven colours)
  was close, but the six keep the whites crisper. Each switch is made by
  a User VIA timer 1 interrupt every line, which takes the line's parity
  from timer 2's count, so a late interrupt costs one line, not the rest
  of the frame.
- **The loader shows the loading screen while the game loads:** STRAT
  selects a shadow MODE 1 and copies the cover to the screen, then loads
  everything beneath it through the OS and its filing system, and starts
  PGAME through the Tube host itself, so the picture stays up to the
  last. Nothing in it is fitted to a particular filing system: rather than
  read the disc controller (as some games do, for the same effect), it
  takes the filing system's interrupts as they come. The line's interrupt
  is taken early and waits, so a delay that is over in time costs
  nothing, and timer 2's parity changes just before it is read, so a
  delayed switch still sets the line being drawn. What's left, while a
  file is read, is the start of some lines in the other palette and
  sometimes a whole line.
- **The cover becomes a title screen, with a plainer loading screen after
  it:** loading beneath the picture through an unmodified filing system
  spoils some lines (the DFS's NMIs and its stretches with interrupts
  off), and only fitting to the filing system would make it clean. The
  picture, shown with nothing loading, is exact, so it stands alone as
  the title (music may come later), and the game loads after it under a
  screen with nothing timed to the line: a MODE 2 title and a progress
  bar, say. The work and its measurements are in `docs/loading-screen.md`.
- **The title plays the Stratagem Overture on the Music 5000, driven
  directly:** no AMPLE ROM is needed (the board only synthesises; envelopes
  and sequencing are the host's), so STRAT plays it with its own player,
  from the MIDI file (`art/music/Stratagem_Overture.mid`) arranged for the
  board's sixteen channels (`docs/music-5000.md`). It loads MUSIC whether
  or not a board is fitted, since the board can't be detected; the game
  itself will have other music, adapted differently.
- **Music is a compact score, interpreted: the sequencer's format
  replaces the first player's:** notes on a musical clock (steps, a tempo
  in steps a tick), the dynamics a conductor's level, a note a byte (an
  interval and one of the piece's commonest lengths), and what repeats,
  across all the voices, patterns that are called (found by Re-Pair). It
  isn't fitted to the overture: pieces in the game, from MIDI or from
  Python, encode the same way. The overture is 1.7K so, from 9.7K, and
  sounds the same; MUSIC is 5.4K, from 12.7K. A step lasts a tick at
  least, which keeps the player simple (`docs/music-5000.md`).
- **After the title, a loading page in MODE 7, with the keys:**
  the world's keys, a bar a step a file, and the music playing on from the
  vertical sync event while the game loads; then "Press SPACE to start",
  so the keys can be read at leisure. MODE 7 for its text, which is
  nearly free, rather than for memory: in a shadow mode all of user RAM is
  free anyway. RENDER and MAIN load clear of MUSIC (`GAME_BUFFER`), and
  MAIN is copied into place once the music stops. The event's handler is
  in low RAM, and pages main RAM in around the tick: on the Integra-B the
  VDU drivers' MEMSEL would otherwise show it the screen.
- **The loading page is a teletext cave, and its progress bar a pool**
  that drips from a stalactite fill, a sixel each, following an estimate
  of the bytes loaded; the title in mosaic letters banded in strata, as on
  the cover. It is MODE 7, not shadowed, on both machines, so the
  interrupt can write its screen directly: on the Integra-B, writing a
  shadow screen with MEMSEL let a filing system's NMI load into the screen
  instead of user RAM. So the Integra-B copies MUSIC to main RAM first, and
  MAIN waits in a store bank until the game's shadow MODE 2 is on.
- **The game's music on the Music 5000, in a fourth sideways RAM bank,
  when one is free:** the user's own ROM images (a filing system) were to
  have it, but music is optional, so a filing system in ROM leaves it to
  the music, and without it the game is silent. The music's tick waits
  while the host races the beam after vertical sync, and is paid once the
  frame is drawn: ticked at vsync it made the host late for the display's
  top; deferred, the host's timing is unchanged and no frame is dropped
  (`docs/music-5000.md`). Main RAM above MAIN (about 16K in the game) could
  hold it instead, but would cost MAIN its room to grow.
- **The game's music is an occasional visitor, chosen by a director from
  the world's state:** the five pieces of a musical day and the overture,
  each played once, to its end, between long silences (two minutes and
  more), as Minecraft does; Underground below the surface, otherwise the
  piece for the hour of a world's day that the parasite now keeps (a
  20-minute day, since 21.8). Each piece arranged as
  data after an arranger's notes (fading in and dissolving, peaks ranked
  below the overture's, echo only underground), Underground made
  otherworldly. Compressed together the pieces shared almost nothing, so
  each keeps its own patterns: all six are 6.3K
  (`docs/musical-direction.md`).
- **The world's day is a 16-bit count of frames:** 65,536 frames, 21.8
  minutes at 50 a second, wrapping at midnight with no comparison; noon at
  &8000, so a curve symmetric about midnight and noon reads alike either
  side; the high byte the time, in 256ths of a day (about 5 seconds), to
  index the light's table and to send the host (`PACKET_TIME`). Hours are
  no longer whole numbers of frames, but nothing needs them: the
  director's phases are thresholds on the time.
- **Day and night by subtraction, with a glowing sky:** the sun's level by
  the time, full through a long day, quick sigmoid ramps at dawn and dusk,
  a long shallow twilight on the night's side and a black midnight (light
  leaks over the horizon into the night; the dark doesn't leak into the
  day); daylight dimmed by subtracting from it, so shafts and caves go
  dark first; the sky dithered by the same masks, its lowest four rows in
  bands of a warm colour that the palette makes magenta at dawn and dusk.
  The warm colour takes the tile group's cyan: gems became green and
  magenta, water's highlights white. Chosen from the day and night lab
  (`strat-daynight-lab`), as the game could draw it: bands a tile high,
  warm pixels fixed in the sky's graphics and shown by the palette.
- **Only undisturbed rock spans; placed raw material is spoil:** the world
  as generated holds itself up, so tunnels stand; nothing put down does.
  Soil and stone stay distinct when carried (recipes need stone), but put
  down either becomes spoil, one material, held from below only, falling
  when unheld; ore and gems can't be placed. Materials degrade as they are
  processed, and crafting is the way up: building is with made things
  (planks, ladders, ropes, platforms) under the span rules. Digging a hole
  you can't climb out of is allowed. Spoil's yield when dug again (soil,
  or nothing) is open (`docs/building.md`). Not yet built: placing is as
  before until then.
- **Soil is where entropy ends; spoil is soil:** rock dug is carried as
  stone; stone put down is soil; grass and soil dug are nothing. No carried
  soil. Soil put down is held from below only and subsides slowly, from
  below upwards, by chance, the work spread over frames; whether the
  world's own soil is loose too, or stays anchored, is open, with the
  subsidence lab's experiments (`docs/building.md`, Subsidence) favouring
  loose. Built 2026-11-01 with all soil loose, subsidence only in the tile
  cache (around the miner).
- **Soil has no strength sideways:** only a tile directly undermined is
  at risk of subsiding; no arch, no slumping of faces. A cut into a
  hillside stands as dug, and a small excavation stays small (with
  slumping, small digs grew into craters cutting back into the hills).
- **Soil that fails drops a tile:** into the empty tile below, rather than
  vanishing; slowly and by chance, as sand in some games but slower. Soil
  is kept until mined; tunnels in soil fill and the ground sinks. It never
  drops onto the miner, and leaves sky where the tile above it is sky.
- **The director's moratoria, and the day's turns for certain:** Daylight
  and Night start only early enough to end in their own period with the
  least quiet still to run before Dusk and Dawn (about 14:04 and 1:07,
  from the pieces' lengths); Dawn and Dusk play for certain when the
  director considers within them. No cheerful daylight spills into dusk,
  nor night into dawn, and the turns of the day are marked every day.
- **The sky follows the ground, and goes dark at night:** the glow's bands
  count from each column's sky floor (its first tile that doesn't show the
  sky), so they follow ground that has sunk; a tile keeps its background
  (sky or cave) whatever is put down, dug or dropped there. At night
  (the sun below level 3) the host's palette makes the sky's blue and the
  glow black, so sky behind a tile lit by a torch or the miner no longer
  shows as day; the twilight's faint sky dither (levels 1 and 2) is lost
  to it. Water shares the blue, but never shares the view with the sky.
- **Subsidence dropped; the ladder of entropy kept:** soil no longer
  fails when undermined. It made digging near the surface messy and
  confusing, its whole-tile drops showed the tile grid the game otherwise
  hides, and it served nothing in play. Soil put down stays where it's
  put, as terrain; stone still puts down only soil, and soil dug is
  nothing. Supersedes the subsidence entries above. The sky floor and the
  night palette stay (soil put down in the sky moves the floor).
- **Nothing is put down in mid-air:** but for a torch (which may go on a
  wall), what is placed needs a floor, the tile beneath it solid and not
  passable; checked once, at placing, with nothing checked after. So soil
  can't bridge a drop, with no subsidence to bring it down.
- **Dusk is warmer than dawn:** in dusk's middle (warmth from 0.7) the
  sky is magenta and the glow's pixels red, by the host's palette alone,
  the brightness curve unchanged; dawn keeps blue and magenta. The two
  sequences meet at blue by day and black by night, and tell evening from
  morning at a glance (the day/night lab's two-tone way).
- **DFS only on the B+ and the Integra-B; an ADFS image for the Master:**
  measured in Beebium on both machines, an ADFS 1.30 ROM raises the host's
  PAGE to &1F00, ANFS 4.18 to &1C00 and NFS 3.65 to &1B00, even with DFS
  selected, all above STRAT's &1900. ADFS and the network filing systems
  aren't supported on these machines; the build makes an ADFS L copy of the
  disc (`build/stratagem.adl`) all the same, for the Master, where PAGE
  stays low. CI (`.github/workflows/ci.yml`) builds both and runs every
  test.
