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
| L | Dig, ahead; with M, down; with K, up; with both, diagonally. Digging ahead or up and down breaks a tree's part whole, for wood: beside a tree, its root goes first, and the tree falls |
| SPACE | Place the kind in hand, chosen with TAB or the pack, ahead (a block clear of the miner; a torch or a workbench may overlap him). With none of it left, the hand moves on to the first kind carried that places something, shown, and SPACE places it when pressed again |
| TAB | Cycle the hand to the next kind held that places something |
| P | Open the pack, pausing the game; P again closes it |
| Z X K M | In the pack: move the hand across the kinds shown |
| R T / F G | In the pack: the crafting grid's cells |

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
   the Tube as it draws: `render_light.asm`), and the sprite, behind pieces in front.

While the host draws a frame, the parasite works out the next.

| File | Where | What |
|---|---|---|
| `asm/host.asm` | host | STRAT (loader, hook, trampolines), MAIN (each frame), RENDER (+ `render_light.asm`), LSCREEN |
| `asm/loading_screen.asm` | host | the loading screen's interrupt, in STRAT (and LOADSCR) |
| `asm/parasite.asm` | parasite | PGAME, PWORLD, PLIGHT; its memory map |
| `asm/tube_layout.asm` | both | buffers, mailbox, packet layout, host addresses |
| `asm/parasite_main.asm` | parasite | the frame, packets, strips of tiles |
| `asm/miner_light.asm` | parasite | the light: flood, soft blend, pass, draw list, resets |
| `asm/torches.asm` | parasite | torches |
| `asm/daylight.asm` | parasite | daylight: sky depths, sunlight by columns, the glow |
| `asm/pieces.asm` | parasite | pieces' slots: giving, sweeping, showing |
| `asm/support.asm`, `items.asm` | parasite | support (what falls), items (the wood that drops) |
| `asm/host_main.asm` | host | reading packets, the mailbox, drawing |
| `asm/camera.asm`, `cache.asm`, `scroll.asm`, `pixels.asm` | parasite | the camera, the tile cache, scrolling |
| `asm/view.asm`, `render.asm` | host | drawing rows, columns, the items and the sprite |

### Loading

STRAT, run by !BOOT, checks the machine, then shows the loading screen
(`stratagem.loading_screen`): it selects a shadow MODE 1 with interlace
off, loads LSCREEN into user RAM and copies it to the screen, through the
render region, by a small copier it puts at `&A008` (the only code that
sees the screen on the B+). Then it starts switching the Video ULA's flash
bit every line, from a User VIA timer interrupt with the System VIA's
interrupts off, and loads RENDER, MAIN, PWORLD, PLIGHT and PGAME beneath
the picture, all through the OS, so any filing system will do. Last, it
gives the VIAs and IRQ1V back, selects the game's shadow MODE 2, and starts
PGAME in the parasite itself, through the Tube host (`&0406`, type 4), as
`*RUN` would.

The picture is MODE 1 narrowed to 64 columns (256 pixels, 16K), so that
the horizontal blanking, where the flash bit must be switched, is 64
columns of the 128 rather than 48. While a file is read, the filing
system's interrupts (the DFS's NMI for each byte; its own stretches with
interrupts off) delay some switches. The handler is entered about 20us
early and waits, so a delay over by then costs nothing; one that runs on
past it shows the start of a line in the other palette. On the DFS, in
Beebium, 0.4-2.2% of lines are late while the parasite's files load over
the Tube, nearly all by under 8 columns, and about 0.1% are skipped (the
whole line in the other palette). Loads into the host's own memory
(RENDER, MAIN) are worse: 6-9% late, 1.2% skipped.

The parasite runs `player.asm`, `actions.asm`, `camera.asm`, `cache.asm`
and `world.asm`, written first for the host-only game; the host runs
`view.asm` and `render.asm`, with its own zero page at `&57`-`&8F` (the
Tube host's code and variables have `&00`-`&56`).

### Torches

A torch is a material (`tiles.TORCH`), passable, and a kind: with the
torches in hand, SPACE places one as it places a block, in the empty tile
aimed at, or, with none, in the miner's own tile (the one holding the
middle of the player's box) if that is empty, as the T key once dropped it
(`place` in `asm/actions.asm`; `torch_room`, `torch_own_tile` and
`torch_place` in `asm/torches.asm`). Its light is the miner's flood
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
covering tree's trunk offset + 1, 0 for none, its height, and
`COVER_FRONT`). So
`generate_tile` finds a tile of sky's part with one look-up and a
subtraction from the trunk's surface height. A tree part's shape byte holds
its strength (`support.py`: the span on the trunk's column, and beside it
where the canopy rests on the ground, else one less). Trees are passable
and clear to light. The grass under a trunk is always flat, never a slope:
a tree on a hillside stands on a terrace a tile wide, rooted, not floating
over the slope.

A straight dig (ahead, up or down) breaks a tree's part whole, at one dig,
for a piece of wood: in aiming, a part counts as whole,
so beside a tree its root, the lowest, goes first, and support brings the
rest down. Digging diagonally passes through trees, as walking does.

### The inventory

The miner carries a count of each kind (`inventory.py`, `asm/inventory.asm`):
wood, soil, stone, ore and gems, up to 99 of each. A tile dug away
entirely gives one of the kind its material yields (dug grass is soil);
the hand stays as it was; a felled tree's logs, gathered in, are
wood. SPACE places the kind in hand, as its material; with none of it
left, the hand moves first to the first kind carried that places
something; a hand that places nothing (wood, chosen in the pack) places
nothing. TAB moves the hand to the next kind after it, in kind order and
round again, that is held and places something (`hand_cycle`). The pack
(below) shows the counts and chooses any kind held.

Whenever the hand changes (TAB, a dig of another kind, placing with none
left, the pack), it is shown above the miner for a second
(`HAND_FRAMES`, 50), as its kind's item picture, `HAND_GAP` (2) lines over
his head (`items.hand_shown`, `hand_emit`): the parasite sends it after
the items, as one more, marked as by the miner so that the host draws it
each frame as he moves, last. So the host needed no new code, only room
for one more item (`ITEMS_DRAWN`). Each kind has an item picture now
(`sprites.py`): a log, a clod of soil, a chunk of stone (white: black is
clear in a sprite), ore, a gem; they'll do for dropped blocks too. While
shown it costs the host about 1,300 cycles a frame (831 to draw it, 486
to restore under it) and the parasite about 270; otherwise the parasite
24. Memory: 144 bytes of pictures and 20 of save buffer in the render
region's graphics (252 bytes left there), 8 in low RAM; 133 bytes in
PLIGHT, 2 of variables and 6 in PGAME, which has 19 left before its next
page.

TAB came after the input byte was full (P took bit 7), so the host writes
a second byte of input, `MAILBOX_KEYS` (TAB is `KEY_CYCLE`), before the
input and the count of packets read; `MAILBOX_FETCHED` moved down to `&8C`
to make room, and the mailbox is `&8C`-`&8F`. The pack's keys are pressed
when they go down (`pack_keys_held`), as P is.

Each count is a byte, `inventory` + kind, up to `COUNT_MAX` (99). A gain
(`inventory_gain`) is the compare with the cap and an `INC`, 15 cycles, or
29 with its call; finding the kind a dig yields and setting the hand adds
14. A place's spend is a `DEC`, 11 cycles with loading the hand. Either
happens only on the frame of a dig, a place or a gathered log. Memory: 6
bytes of variables (5 counts and the hand), 36 bytes of code and tables
in PLIGHT, and 38 more in PGAME's digging and placing.

### Keys

The host reads the keys itself each frame (`read_input`, `scan_keys`), as
OS 1.20's `interrogateKeyboard` does, but for all of them at once, with
interrupts held off: it stops the keyboard's own scanning (System VIA
latch bit 3, `3` to port B), sets port A's direction to `&7F`, and for
each key in a table writes its internal key number (an INKEY number's
`-n - 1`) to port A and reads its state in bit 7; then lets the scanning
start again (`&0B`). A key costs about 31 cycles. Play's eight keys take
353 cycles a frame (and the belt's nine keys every fourth frame), and the
pack's twenty-seven 885 (P, Z X K M, TAB, DELETE, L, COPY, the nine cell
keys and the nine belt keys; the cells' scan stops at the first held), with interrupts held off for as long. Which keys are read, and the
bits they set, is a table (`key_table`): play's, and the pack's. (The game
first read its keys with OSBYTE `&81`, at about 270 cycles a key; see
`decisions.md`, 2026-10-24.)

### The pack

P opens the pack (`pack.py`, `asm/pack.asm`; `render_pack` in
`render.asm`), and the game pauses. The parasite runs no game frame while
it is open: each frame it takes the input and sends the pack's packet
instead (`PACKET_PACK`): the kinds shown, their counts and the hand's
place among them. The kinds shown are those held (a count above 0), in
kind order; if the hand isn't among them, opening moves it to the first.
A kind shown stays shown while the pack is open, even at 0 (see
Crafting). The host draws the panel across the top of the view: a blank
row, then, for each row of eight kinds, their icons (a tile's 8 x 16
pixels), their counts below in a 3 x 7 font, right-aligned, and
arrowheads either side of the hand's count. The rest of the view is left
as it is, sprite and items included. While the pack is open the host
reads P, Z X K M and the grid's keys instead of the game's keys, and a
press of Z or X moves the hand a kind back or on, from the end of one row
to the start of the next, and of K or M a row up or down; only the
arrowheads are redrawn (`PACKET_PACK_MOVED`), since redrawing the
panel showed it half drawn for a frame. P again closes the pack: that
frame is the game's, with no input, and redraws the view whole, as after
a jump of the camera (`pack_plan_camera`).

Costs, measured:

- In play, on the parasite, 84 cycles a frame to see whether P or TAB
  was pressed; on the host, each of P and TAB is one more key in the scan
  (see Keys), about 31 cycles.
- Opening, on the host: 31,551 cycles with one kind shown, 47,550 with
  five, most of it clearing the panel's five rows. So the panel may take
  two frames to appear, the beam overtaking it; once per opening.
- Moving the hand: 608 to 2,960 cycles on the host, about 490 on the
  parasite.
- Memory: on the host, 528 bytes of icons, digits and arrowheads in the
  render region's graphics (425 bytes left there), 448 bytes of code in its
  code (2,032 left), about 130 in MAIN and 48 in low RAM; on the parasite,
  299 bytes in PLIGHT, 14 bytes of variables and 5 in PGAME, which now has
  28 bytes before its next page.

### Crafting

Below the kinds the pack shows the crafting grid (`crafting.py`,
`asm/crafting.asm`; `docs/inventory-and-crafting.md`, Making), the hand's
2 x 2 for now, and what it makes. The hand is the brush: a cell's key
(R T / F G, as they lie on the keyboard) puts one of the hand's kind in
the cell, from its count, or takes it back, or swaps it; DELETE empties
the grid; L makes what it lays out, and lays the shape out again
from the counts, as far as they go (held, again every 8 frames, after 20);
COPY lays out the next recipe in the book, each recipe made once. Closing
the pack empties the grid back into the counts. The recipes so far:
planks (4) from wood, torches (2) from ore over wood, the workbench from
four planks (`docs/manual.md` shows them as the player sees them).

- **Keys:** in the pack, the host reads DELETE, L, COPY and TAB into the
  second byte of input (`KEY_CLEAR`, `KEY_MAKE`, `KEY_BOOK`, `KEY_NEXT`:
  TAB moves the hand to the next kind shown, round again), and the
  first cell key held as a number in its low four bits (`scan_cell`, 1 on,
  0 none), so nine cells fit beside them; the parasite takes a change of
  that number as a press.
- **Matching:** the grid is trimmed to its rows and columns with anything
  in them, and compared, cell for cell, with each recipe of that size the
  station allows (`craft_match`), from generated tables of each recipe's
  size, result, count, station and cells.
- **What's shown:** a kind once shown stays shown while the pack is open
  (`pack_seen`), so slots don't move as counts run out, drawn as an empty
  socket with no count once there are none, so the pack doesn't seem to
  hold what it doesn't; a kind gained, by
  making it, joins them, and the panel is drawn again (`PACKET_PACK_DRAW`).
  Otherwise a change of the counts or the grid sends `PACKET_PACK_CHANGED`,
  and the host redraws only the counts, grid cells and result that differ
  from what it drew (`render_pack_changed`). The packet adds the grid's
  size, its nine cells and what it makes and how many.
- **The panel:** the grid's cells are drawn as icons, or, empty, as a
  socket (a blue outline), five cells apart; the result as a slot, with an
  arrowhead pointing at its count.

Costs, measured:

- On the host: a key press's redraw, 5,808 cycles on average, 8,301 at
  worst (a count and a cell, and the result); the panel drawn whole, on
  opening or when a kind joins, now 89,929 to 106,263 (three more rows of
  clearing for the grid), so it may show over two or three frames, then
  stays put. The arrowheads, 2,412 to 4,804.
- On the parasite, paused: a pack frame takes 2,058 cycles on average,
  2,871 at worst. `craft_match` is 548 on average (738 worst), `craft_make`
  777 (1,248).
- Memory: on the host, 68 bytes of graphics (the socket and the grid's
  columns; 143 left), 399 bytes of code in the render region (1,646 left),
  111 bytes in MAIN and 30 in low RAM; on the parasite, 833 bytes in PLIGHT
  and 52 bytes of variables. The kinds' icons for soil, stone, ore and gems
  are their tiles in the material pages, which saved 256 bytes.

### The workbench

The workbench is a piece (`tiles.BENCH`, its picture in `piece_art.py`),
passable, held from below (`support.py`, "bench"): with one in hand, SPACE
places it as a block, and a dig breaks it whole, thrown out as an item
(`items.DROPS`) to be gathered in again. Opening the pack, the parasite
looks for one within 3 tiles across and 2 up or down of the miner's tile
(`craft_station`, `crafting.station_near`): if there is one, the grid is
3 x 3 (R T Y / F G H / V B N), and the bench's recipes can be made.

At the bench: a wooden pickaxe from a T of planks (PPP / .P. / .P.) and a
stone pickaxe from stone and planks (SSS / .P. / .P.), kinds in the pack
(`inventory.TOOLS`). The pack's graphics (icons, digits, arrowheads, the
socket) are now in the render region's code area, leaving its graphics
area room for more item pictures.

- Memory: the bench's piece graphics are 128 bytes in MAIN, which now
  ends at `&3F80`, 128 bytes short of the screen. `place` moved from
  PGAME to PLIGHT (`asm/place.asm`) to make room for the material tables'
  new entries.

### The tool belt

The miner has two hands: the hand, which SPACE places, and the tool hand,
which L digs with. The tool hand holds one of the belt's nine slots, on
the keys 1 to 9, each empty or holding a tool, its own, out of the pack's
counts, with the digs it has done (`pack.py`: `Pack.belt`,
`Pack.belt_wear`, `Pack.slot`; `belt`, `belt_wear`, `belt_slot` on the
parasite). A belt key takes its slot into the tool hand, in play or in the
pack (an empty slot is bare hands); in the pack it first moves a tool:
from a slot holding one back into the pack, the hand moving to its kind;
or, into an empty slot, one of the hand's kind from the pack. The pack
keeps a total of the digs done by its tools of each kind (`Pack.wear`;
`pack_wear_low` and `_high`, two bytes, since 99 stone pickaxes can have
done 12,771): a tool given back adds its wear, and one taken gets as much
of the total as one tool can carry, one dig short of breaking, so moving
tools never repairs them, and worn ones come out first. The tool in use is
shown above the miner for a second, as the hand is, whenever its belt key
is pressed, even if it is already in hand, and when it breaks, its slot
then empty: bare hands, shown as a blue outline like the pack's empty
cells (`items.show_hand`,
`items.EMPTY_PICTURE`: the hand if both change at once). A tool is shown
with its belt slot's number beside it, one more item picture (the numbers
1 to 9 are item frames, `items.NUMBER_FIRST`); 0 shows the tool in use
again, choosing nothing. Drawing the number costs what an item costs, only
while the tool is shown; its frames take 270 bytes of the render region's
graphics area, which has 237 left.

The pack shows the belt below the grid: each slot's icon or a
socket, its key's number below it, and arrowheads either side of the tool
hand's, redrawn when it moves.

- Keys: the digit keys, not the function keys, which under emulation can
  need a modifier, and whose f0 is often the host's F10. The host reads
  them every fourth frame in play, every frame in the pack, as the number
  of the first held (1 on, key 1 first), into
  a fourth byte of the mailbox (`MAILBOX_TOOLS`, `&8C`; `MAILBOX_FETCHED`
  moved to `&8B`).
- Costs, measured: the host's key scan in play is 353 cycles on three
  frames in four and 615 on the fourth (419 on average); in the pack, 885.
  Drawing the panel whole at a bench (ten kinds, the 3 x 3 grid and the
  belt) takes 173,631 to 216,093 cycles, about five frames, on opening; a
  key's redraw 2,576 to 9,195 (5,690 on average).
- Memory: the render region's code area has 799 bytes left, MAIN's code
  about 160 before its page.

### Digging by tool

What a dig does depends on the tool in use: the tool hand's, if any of
that kind is left, otherwise bare hands (`actions.TOOL_QUARTERS`, quarters
of a tile a dig removes):

| | Grass | Soil | Stone | Ore | Gem |
|---|---|---|---|---|---|
| Bare hands | 1 | 1 | — | — | — |
| Wooden pickaxe | 4 | 2 | 1 | 1 | 1 |
| Stone pickaxe | 4 | 4 | 2 | 2 | 1 |

So by hand soil takes four digs and stone can't be dug; a tree's part
still breaks whole at one, by hand, which is the way to wood, planks, a
workbench and a wooden pickaxe. The wooden pickaxe digs as the miner did
before tools.

Each dig of the ground (not a chop) wears the tool in use, its belt slot's:
at its durability (60 for wood, 130 for stone) it breaks, and the slot is
empty. Nothing shows the wear.

- On the parasite, PGAME's `material_quarters` is the tool in use's row,
  copied from PLIGHT's `tool_quarters` by `tool_update` at the start, when a
  belt key chooses a slot, when the pack closes and when a tool breaks,
  so the digging code is as it was; `tool_wear` is one call in the dig.
- Costs, measured: `tool_wear` 49 cycles a dig, 450 when the tool breaks;
  `tool_update` 382 to 422, only on those events. Nothing per frame.
- Memory: the pack's and crafting's workspace moved out of `&0400`-`&07FF`,
  which is full, to after PLIGHT.

### In front and behind

Each tree stands in front of the miner or behind him, as the hash says for
its trunk's column (`world.in_front`, about half of them), for a sense of
depth: its parts' shape bytes have `PIECE_FRONT` (bit 7). Every pixel on the
screen says whether a sprite may be drawn over it: tiles are drawn in the
tile colour group (logical colours 8-15) and sprites in the sprite colour
group (0-7), both mapped to the same colours, and a piece in front is
composed into its slot with its own pixels in the sprite colour group
(`tiles.compose`: its data AND `FRONT_COLOURS`). A pair in front is its own
pair (+ `FRONT_PAIR`), and so its own slot, with the visibility of the pair
behind; the light's dither keeps colour bit 3, so a dimmed pixel stays in
its group.

`sprite_draw` leaves a sprite's pixels out over any pixel in the sprite
colour group (`sprites.drawn_byte`): a byte at or above `&C0` (both pixels
tiles) is drawn as before; below, the screen's pixels in the sprite group
are kept, through a 192-byte table of the drawable bits
(`sprite_drawable`). So the miner passes behind trees in front, and items,
drawn after him, pass behind him too. It is meant for doors, furniture and
grass later: any piece can be in front.

### Support

`asm/support.asm`, the cellular automaton of `support.py`, run only where
tiles change. A piece's strength is in its shape byte's bits 0-2; each
material's rule (how it is held, what it holds, its family) is a generated
byte (`support_rule`). `call_set_tile` queues the changed tile and its
neighbours; each frame up to 6 are checked (`support_step`), each working
its strength out again from its neighbours: if it has changed it is
stored, or at 0 the piece falls, to sky or cave, which queues its
neighbours in turn, and is sent as a changed tile (no more than the packet
has room for). A piece falls only every 4 frames (`FALL_FRAMES`): a piece
due to fall sooner is checked again next frame. So a felled tree is seen to
come apart, from the cut upwards, over most of a second. Pieces are clear to light and passable, so a fall changes
neither daylight nor the miner's light. Torches don't fall yet (one that
did would have to leave the torches' list).

### Items

`items.py`, done exactly by `asm/items.asm`. The root and each part of a
trunk throw out a log as they break, dug or fallen (`items.DROPS`; the
canopy drops nothing): an item, 6 pixels by 5 lines, sprayed from its tile
upwards and to one side (`SPRAY_VX`, `SPRAY_VY`, by a count of items
thrown). A log flies under gravity, at most a quarter-cell a frame each
way; it bounces back off a solid quarter-cell beside it at half speed,
and off one under it at half speed (losing half its speed across), or
comes to rest if landing slower than `BOUNCE_MIN`; one still flying after
`FLY_FRAMES` (40) is gathered. It rests for `REST_FRAMES` (25), then is
gathered: it flies to the miner through anything, faster each frame (to
`GATHER_MAX`, 4 pixels and lines), and is his, into the inventory, when it touches
him. Items pass through each other. So a felled tree's logs burst out, show
how many there are, and are gone in about a second; at most 8 are out at
once (more go straight into the inventory). One flying where the tile it would
look at isn't in the tile cache is gathered at once. This is the loot
burst and magnet of many games (Exile's objects have velocities and
bounce too, but by angle and magnitude: `apply_tile_collision_to_position_and_velocity`).

The packet carries the items in view, after the chunk to fetch: each one's
view column, line and frame (the item frames follow the player's in
`render.asm`). Only those clear of the outer `MAX_STEP_X` columns and
wholly in view are sent, so that no new column or row is ever drawn where
an item was drawn, which would be restored over it. The host draws them as
the sprite is drawn, saving the screen under each, last of all (after the
sprite and the new columns, so as not to delay the columns past the beam),
and restores them, last first, before the sprite and the changed tiles. If nothing is redrawn under them (no list, no changed tiles: the
count's `ITEMS_UNTOUCHED`), the items at the start of the list drawn where
and as they will be drawn again are left as they are, unless one meets the
miner's sprite, this frame or last (`ITEM_BY_MINER` in its frame: the
sprite is restored and drawn each frame, over it): on the surface,
where daylight outshines the miner's light, logs lying still cost the host
almost nothing.

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

`tests/test_support.py` cuts a tree's trunk in py65 and plays until
nothing is left to check, then checks that what fell, and every strength
left, are what `support.py` says, and the tile cache the world; and digs at
the tree beside the start, which must give wood and fall. The Tube game's
`fell-a-tree` script does the same in Beebium, every frame checked.

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

A felled tree (10 pieces) came down over 9 frames, before the falls were
paced (now 35); checking cost the parasite about 1,400 cycles a frame
while it fell (3,100 at most), and the busiest frame of the fall,
relighting what fell, about 52,500 (py65).

Items (py65, a felled tree's 5 logs thrown out and gathered in, 123 frames,
the miner standing by): while any are out (59 frames), moving them costs
the parasite about 4,000 cycles a frame (5,800 at most: a flying log about
1,000, a gathering one about 500), and sending them about 1,400; with none
out, both together about 120. Over those frames the mean frame is 9,500,
the worst 86,100 (the felling's first frame). On the host (Beebium, the B+), 3 logs lying still with
nothing redrawn under them cost about 580 cycles a frame; when they must
be redrawn, about 1,800 each (restoring 600, drawing 1,200), so 8 would
cost about 14,000.

Drawing the miner costs the host 3,036 cycles over tiles, 288 more than
before sprites could pass behind things (a compare a byte); wholly behind a
piece in front, 5,680 (py65, `test_sprites.py`). Composing a slot in front
costs about 2,500 cycles, once, against 1,800 for one behind.

Dropping a torch floods twice (the torch's pool, then the miner's, as the
tile changed) and relights its surroundings: about 118,000 cycles, so the
host can miss a frame then.

## Not yet

- Picking torches up; torches that flicker; more than 24.
- Items redrawn are drawn last, so near the top of the view the beam may
  pass one between its restoring and its drawing, and it flickers, in
  frames that redraw under it; they are out for only a second or so. Items
  pass behind the miner, and vanish a few columns inside the view's
  sides. Wood isn't spent yet.
- The pack: five kinds only (icons are 64 bytes each, so 24
  would need room beyond the render region's graphics).
- The flood's spike: spreading it over two frames, or making it cheaper.
- The list can hold 255 cells; beyond that, cells could be left unlit.
- Untested beyond Beebium; the Master 128 not yet.
