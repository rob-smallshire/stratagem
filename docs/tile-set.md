# The tile set (a plan)

A plan for the tiles the game will need beyond terrain: trees, ladders,
ropes, platforms, walls, doors and crafting stations, and how the tile
format, the renderer and the rules can carry them all. Written before
building any of it (2026-10-20), so that trees don't arrive alone, with a
format that can't hold what comes next. Nothing here is decided until a
prototype has shown it: see "To prototype" at the end.

## What the tiles are for

Each kind of tile should earn its place in the loop of `game-design.md`
(explore, gather, craft, reach new places):

| Purpose | Tiles |
|---|---|
| Getting about, before the jetpack | ladders, ropes, platforms; vines (natural ropes) |
| Gathering | trees (wood), vines (fibre), terrain (as now) |
| Building shelter and a base | plank and brick blocks, back walls, doors, windows |
| Crafting | workbench, furnace, anvil |
| Keeping things | chests |
| Light | torches (as now); glowing fungus, lava (later) |
| Atmosphere | grass tufts, mushrooms, stalactites, roots |

Shelter needs a reason: something that comes out at night or in the dark
that can't open doors or cross light. That is a game design question for
the creatures, but the tiles should allow it (doors that creatures treat as
walls; light that they avoid).

## Two families of tile

**Terrain** erodes (`tiles.py`): a material in one of 61 shapes, dug a
quarter at a time, as now. Grass, soil, stone, ore, gem; bedrock and water
don't change.

**Pieces** are whole tiles that never erode: a ladder, a rope, a plank, a
door's top half, a tree's trunk. A piece is broken whole, in one or more
hits by the tool's tier, and drops an item. Built blocks are pieces too:
plank and brick blocks are solid pieces, broken whole, as in Terraria.
Natural terrain erodes; what the player builds breaks whole.

The torch is already a piece in all but name.

## The tile format

Still two bytes; the material says which family.

| Byte | Terrain | Pieces |
|---|---|---|
| Material | which terrain (property tables say so) | which piece kind |
| Shape byte, bits 0-5 | the shape (61 of 64) | the piece's *part*: which part of a larger object, or its state |
| Shape byte, bits 6-7 | the background | the background |

The background grows from one bit to two, using the shape byte's one spare
bit: sky, cave, plank wall, stone wall. Back walls are what you stand in
front of inside a house, as in Terraria, and they show through every empty
part of a tile: behind a ladder, a torch, a door left open, or a half-dug
tile. A back wall is placed into a tile's background without changing what
is in front of it.

The part number makes objects larger than a tile. A door is two parts (top,
bottom), open or closed (the material: a closed door is solid, an open one
passable); a workbench is two parts side by side; a tree is a set of roles
(root, trunk, trunk with branches, canopy left, middle and right, ...).
Rules find an object's other tiles from the part: break any tile of a door
and both go; cut a tree's trunk and every tree tile above goes, and drops
wood. No table of objects is stored: the world's tiles are the objects, so
they cost nothing more to store than dug terrain, and the generator can
grow trees and vines from its hash at no cost until they are changed.

Only chests need more: their contents. That is a small table kept with the
world (a chest's position and its items), saved with the changed chunks.

## Properties, not material numbers

Each material gets a row of properties, generated from Python into tables
the 6502 indexes by material, so that code asks what a tile does rather
than what it is (today a few places compare material numbers: `world.asm`'s
diggable range, the passable table, `torches.asm`'s test for an empty tile).

| Property | Values |
|---|---|
| Family | terrain (erodes), piece (breaks whole), immutable |
| Collision | solid (by shape), passable, platform (stand on it, jump up through it, drop through it with down), climbable (ladder, rope, vine) |
| Light | opaque, transparent (to daylight, every piece is transparent); a light source (and its strength) |
| Needs | how it is held up (Support, below) |
| Toughness | hits to break, and the tool tier needed |
| Drops | the item it gives |
| Drawn | behind the miner, or in front |
| Object | a rule for finding its other parts (door, bench, tree) |

Items are separate from tiles: an item may place a tile (planks, a ladder),
or not (a pickaxe, an iron bar). Crafting is a table of recipes (items in,
an item out, a station needed), generated from Python, and neither costly
nor risky.

## Support

Every piece says how it is held up, and breaking or placing a tile
rechecks its neighbours, which pass the check on: a small cellular
automaton. Built blocks need holding up too (decided 2026-10-21), so
building is about where the pillars go.

| Held | How | Pieces |
|---|---|---|
| From below | by what is under it | tree trunks, wooden ladders, walls, mushrooms, grass, benches, chests |
| From above | by what is over it | ropes, rope ladders, vines, stalactites |
| From below or the side, within a span | by what is under it, or a neighbour beside it, one step further from the ground | roofs, platforms, plank and brick blocks, canopy |
| By any solid neighbour | | torches |
| Both floor and ceiling | both halves as one | doors |

Each piece has a strength: terrain is an anchor, at full strength; a piece
held from below or above takes its holder's; one held only from the side
takes its neighbour's less one; at zero it isn't held, and falls (and
drops its item). So a roof reaches SPAN tiles from a wall and no further,
and a canopy wider than that needs branches. SPAN is a number in the
tables, to choose by playing (3 to 5, say).

- Strength is worked out from the neighbours when something nearby
  changes, never stored, and the span bounds the search.
- Nothing is checked each frame. A collapse goes through a queue, a few
  tiles a frame, as torches' relighting does, so a felled tree comes down
  over several frames.
- Strength only comes from the ground, so nothing holds itself up.
- Which pieces hold others up is a property: ground, blocks, trunks and
  walls do; a rope holds a rope below it and a ladder a ladder above it,
  and nothing else.

## Movement

The player's physics (`player.py`, `player.asm`) gain:

- **Climbing:** on a climbable tile, K and M move up and down, walking moves
  off it, and gravity stops. The top of a ladder can be stood on, as a
  platform.
- **Platforms:** solid only from above, to something falling onto them, and
  not while M is held. Platforms and ladders are Terraria's answer to
  getting about a base without flying, and the game design keeps the
  jetpack for later so that they matter.
- **Doors:** a key, or walking into one, opens it (the material changes,
  both parts, if the space beside is clear).

## Drawing

This is the hard part, and the only part bounded by memory.

The renderer draws a tile from its material's page of graphics against a
background, pre-composed: each material has two pages (cave, sky), each
with four cell variants (512 bytes). Four backgrounds that way would
double every material's graphics. Three ways round it were weighed, and
the first two timed in py65 (a cell, 8 bytes, as the renderer draws it):

| Drawing a cell | Full light | Dimmed |
|---|---|---|
| As now: a pre-composed graphic | 98 | 138 |
| Composed as drawn, black clear (a 256-byte table finds the clear pixels) | 226 | 266 |
| Composed as drawn, the piece with its own mask | 178 | 218 |

Composing as drawn costs 80-130 cycles more a cell, in every path that
draws one (new rows, new columns at the beam, changed tiles, the light's
list), and every one of them would need a second form.

**The third way, recommended: compose once, into a cache of slots.** The
host keeps every piece's graphics, and its mask, in its program RAM (about
18K free in the Tube game, where the renderer can't read but other host
code can), and a cache of slots in the render region: each slot a piece
already composed over one backdrop, 64 bytes. When a tile with a piece
enters the parasite's tile cache, the parasite makes sure its pair (piece,
backdrop) has a slot, and if not, tells the host in the packet (slot, piece,
backdrop: three bytes); the host composes it, about 1,500 cycles (timed),
once. The tile the host gets names the slot as an ordinary material and
shape, so **the renderer doesn't change at all**, and costs what it does
now. The light's list looks the slot up the same way.

- Slots as materials: a material's two pages hold eight whole-tile slots,
  given three pseudo-shapes (there are three spare shape numbers) whose
  cells are all one variant: so slot k of a group is drawn as variant k
  (0-3) of the cave or sky page. The 4K at `&B000`-`&BFFF` holds 56-64
  slots (a page table in place of `material * 2` lets groups sit anywhere).
- How many are needed: the lab's busiest view (a forest, a hut, a cave)
  holds 29 pairs in a screen's 16 x 16 tiles and 41 in the whole scene
  (44 x 30, about the tile cache's 32 x 32). So 56 is enough with room, and
  a slot is freed when its pair leaves the tile cache (a count per slot,
  kept as the cache fills).
- Masked pieces cost nothing at draw time, so pieces keep black as black
  (the lab: black-clear lets the backdrop through black detail, which
  suits leaves but not bark or outlines). At 128 bytes a piece, 18K holds
  over a hundred.
- The miner drawn behind a piece in front uses the piece's mask, kept
  beside the slot (next steps, item 1).

This replaces the budget below and the cache of piece graphics: it is that
cache, holding composed pairs rather than pieces.

### The memory budget (superseded by the slots)

Drawing as composed, the renderer would need everything in the render
bank: 16K, mostly used (the ten materials are 5K, the miner's frames
1.2K). Free in the Tube game: about 0.8K below `&A000` and the 4K at
`&B000`-`&BFFF`, so about fifty pieces at 64 bytes. With slots, the 4K
holds the slots and the pieces live in host program RAM.

### Not variable-length tiles

Tiles stay two fixed bytes wherever they are read at random every frame
(the tile caches, collision, light, drawing): a variable-length tile would
cost on every access. Compactness belongs where tiles are stored: changed
chunks (next steps, item 5: about 21 bytes a chunk instead of 128,
measured) and on disc. The material byte already gives rare, complicated
tiles the same two bytes as soil, with their detail in the tables.

## A first set

| Kind | Parts | Notes |
|---|---|---|
| Tree | about 8 roles | natural, on grass; felled from the top down; drops wood |
| Vine | 2 (length, end) | natural, hanging in caves; climbable; drops fibre |
| Grass tuft, mushroom | 1 each | natural, passable, in front of the miner |
| Plank block, brick block | 1 each | solid pieces |
| Platform | 1 | wood |
| Ladder | 1 | wood; climbable |
| Rope | 2 (length, end) | fibre; climbable; hangs, and lengthens downwards when placed |
| Door | 4 (top and bottom, open and closed) | wood; needs floor and ceiling |
| Window | 1 | transparent solid; glass from sand, later |
| Torch | 1 | as now, needs a wall or floor |
| Workbench | 2 | wood: planks, ladders, platforms, doors, the bench's recipes |
| Furnace | 4 (2 x 2) | stone: bars from ore; a light source |
| Anvil | 2 | iron: tools |
| Chest | 1 | wood; holds items |

About 30 parts, with room to grow. With it, the loop: fell a tree, make a
bench, then planks, a ladder down the shaft, platforms across a cavern, a
door on a hut with a torch inside; dig stone for a furnace, smelt ore, make
an anvil, make a better pickaxe.

## Costs to watch

- **Renderer:** the composed path costs perhaps half as much again per cell
  (an estimate, to measure); new columns are the beam-sensitive case.
- **Felling and breaking objects:** a tree is a dozen changed tiles; they go
  through the changed-tile path a few a frame (as torches' relighting does),
  so a tree comes down over several frames.
- **Support checks:** a few table lookups at each changed tile's neighbours.
- **World storage:** placed pieces are changed tiles, as dug terrain is; a
  large base fills chunks (next steps, item 5, spilling to disc).
- **Generation:** trees and vines need the generator to look a few columns
  or rows around a tile (is there a tree rooted near here?): measure what
  it adds to a new row's 29,000 cycles.

## What the prototypes found

- **The piece lab** (`uv run strat-piece-lab`, into `build/pieces/`): the
  set drawn in a scene. Pieces over backdrops read well; the miner behind a
  tree or a mushroom drawn in front works. Back walls must be dim (sparse
  colour on black), or they swamp what stands in front of them. Dithered
  leaves let the backdrop through, as in Stryker's Run.
- **Daylight leaks into buildings.** Daylight by columns (`shaft_sun`)
  lights a tile from an open column up to 4 away whatever lies between, so
  a roofed hut is lit inside through its walls. For shelter to be dark,
  the light from beside must stop at an opaque tile on its row: a scan of
  up to 4 tiles, for tiles below their own column's sky depth only.
  Measure it before choosing.
- **Daylight passes built things.** Making daylight stop at walls, so
  that a roofed hut is dark inside, was built and measured (about 700 cycles
  a frame more on average, up to 9,400 in the worst frame, and nearly all
  the parasite's spare memory), then undone: pieces are clear to daylight,
  lit as the sky over them, and so is inside a building. See
  `docs/decisions.md`.
- **Drawing:** composing as drawn costs 80-130 cycles more a cell; composing
  once into slots costs about 1,500 cycles a new pair and nothing a frame.
  See Drawing.

## To prototype

1. ~~A lab in Python~~: done (above).
2. ~~Slots in the game~~: done, with the torch as the first piece
   (`docs/tube-game.md`, Pieces and slots). Composing a slot costs the host
   about 1,800 cycles; the parasite pays about 30 cycles a frame. Slots are
   freed by sweeping the tile cache when none is free, rather than by
   counts. The torch's material pages are still in the render region (the
   host-only game shared them); they can go now that it is dropped.
3. ~~Daylight that stops at walls~~: built, measured and undone (above).
4. **Property tables**, replacing material number tests, with no change in
   behaviour (the tests must stay green).
5. **Climbing and platforms** in the player's model and on the 6502.
6. **Trees** grown by the generator, felled by the rule, wood counted.
7. **Placing** pieces from an inventory, and the first recipes.
8. **Flying pieces** (the object list), measured on both sides.
