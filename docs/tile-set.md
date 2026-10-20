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
| Light | opaque, transparent; a light source (and its strength) |
| Needs | support from below, above or a side, or nothing: a torch needs a wall or floor, a rope something above, a tree the ground, a door both. Breaking a support breaks what it held |
| Toughness | hits to break, and the tool tier needed |
| Drops | the item it gives |
| Drawn | behind the miner, or in front |
| Object | a rule for finding its other parts (door, bench, tree) |

Items are separate from tiles: an item may place a tile (planks, a ladder),
or not (a pickaxe, an iron bar). Crafting is a table of recipes (items in,
an item out, a station needed), generated from Python, and neither costly
nor risky.

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
double every material's graphics; so pieces, and terrain over the new
backgrounds, must be drawn over their background as the cell is drawn:

    LDA piece,Y : TAX : LDA backdrop,Y : AND clear_mask,X : ORA piece,Y

where `clear_mask` is a 256-byte table giving, for any screen byte, the
pixels that are colour 8 (the tile group's black, which shows the
background). A piece is then 64 bytes, whatever its background, and the
same mask lets the miner be drawn *behind* a piece drawn in front (next
steps, item 1), for free.

The cost is in the renderer: every path that draws a cell (new rows, new
columns, changed tiles, and the light's list, which today sends each
cell's one graphics address) learns the second, composed, form. The fast
pre-composed path stays for terrain over sky or cave, which is most of the
screen.

### The memory budget

The renderer can see only the render bank while the screen is paged in:
16K, mostly used (the ten materials are 5K, the miner's frames 1.2K). Free
in the Tube game: about 0.8K below `&A000` and the 4K at `&B000`-`&BFFF`.
About 4.8K, then:

| | Bytes |
|---|---|
| Four backdrops (sky, cave, plank wall, stone wall), 64 each | 256 |
| `clear_mask` | 256 |
| 50 pieces at 64 bytes | 3,200 |
| Item sprites (for pieces that fly out), a dozen small ones | about 600 |
| Spare | about 500 |

The torch's 512 bytes return to the pool when it becomes a piece. Fifty
pieces is enough for the set below, with room for a second look of some.

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

## To prototype

1. **A lab in Python**, as the lighting lab: a scene with a tree, a vine, a
   hut (back walls, a door, a ladder, a platform, a bench, a torch inside),
   drawn with the composed pieces and lit; the miner in front of and behind
   pieces. Decides the look and the format.
2. **The renderer's composed path** on the host, measured, and the light's
   list carrying it. This is where the risk is.
3. **Property tables**, replacing material number tests, with no change in
   behaviour (the tests must stay green).
4. **Climbing and platforms** in the player's model and on the 6502.
5. **Trees** grown by the generator, felled by the rule, wood counted.
6. **Placing** pieces from an inventory, and the first recipes.
7. **Flying pieces** (the object list), measured on both sides.
