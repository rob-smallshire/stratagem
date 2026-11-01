# Building, spoil and support

How the player changes the world by adding to it: what can be put down,
what holds it up, and what becomes of materials as they pass through the
player's hands. A design to settle before any of it is built; the support
mechanics it relies on are in `docs/tile-set.md` (Support), and run today
for trees.

## The problem

Today anything dug can be put back: soil, stone, ore and gems are placed
as blocks of the original material (decided when placing came in, as in
Terraria). A placed block becomes terrain, and terrain is an anchor at
full strength. So earth can be placed in the open sky and stays there; and
since the world's rock must hold up any tunnel's ceiling, however wide, a
line of placed stone is a cantilever of unlimited reach: any chasm can be
crossed by building straight out over it. That's too easy, and it isn't
the game: an explorer in an indifferent world, not its engineer.

## Principles

- **Only undisturbed rock spans.** The world as generated holds itself up,
  without limit: tunnel ceilings, overhangs and caverns stand. Nothing the
  player puts down does; it is held as its kind of support allows, and no
  further.
- **Materials degrade as they're processed.** Each pass through the
  player's hands loses something, as entropy would have it: rock dug out
  is carried as loose stone; stone put back is spoil, not rock; spoil dug
  again is less still. Crafting is the one way up: work and a tool turn
  wood into planks, stone into a pickaxe's head, and later ore into bars
  and stone into bricks.
- **Building is a craft.** Structures are made of refined, made things:
  planks, ladders, ropes, platforms, later bricks, each held up by the
  rules for its kind. Raw material can be dumped, not built with.
- **The world can trap you.** Digging a hole you can't climb out of is
  allowed (decided 2026-11-01). A careful explorer carries a way out:
  spoil to heap a step at a time, or a ladder.

## The states of a material

| State | What it is | Becomes |
|---|---|---|
| Undisturbed | the world as generated: grass, soil, stone, ore, gems, bedrock | dug: carried, as its kind |
| Carried | a kind in the pack: soil, stone, ore, gem, wood | crafted: something made; placed (soil, stone): spoil |
| Made | planks, torches, the workbench, pickaxes; later ladders, ropes, platforms, bricks | placed: a built piece, held by its rule |
| Spoil | soil or stone put down in the world | dug: soil, or nothing (below) |

Soil and stone stay distinct as carried kinds, because recipes tell them
apart (the stone pickaxe's head is stone). In the world there is only one
kind of fill: spoil, whatever it was made from. Ore and gems are never
spoil: they are too valuable to dump, and can't be placed at all.

## Spoil

- **Placed** with SPACE, from soil or stone in hand, where a block can go
  now: an empty tile (air or sky), ahead, above or below, clear of the
  miner (the aim was fixed on 2026-11-01: placing ahead takes the first
  column wholly ahead of the miner).
- **Held from below only**: by undisturbed ground, by spoil, or by a solid
  built piece beneath it. Nothing from the side, so no bridge, no ledge,
  no overhang: the trunk's rule in the support table (`support.py`,
  BELOW). Strength is the holder's, as for a trunk, so a column of spoil
  on rock stands to any height, and one on a plank platform stands as long
  as the platform does.
- **Unheld, it falls** as pieces fall today: removed, and thrown out as an
  item to be gathered again. Earth put in the sky drops at once. A shaft
  can't be filled from its top (what's dropped down it falls as items to
  the bottom); it is filled from the bottom up, which is also how a hole
  is climbed out of: stand, place below while jumping, stand on it, again.
  Spoil that slides and heaps into what's below it is later, if wanted:
  it would need the support queue to move pieces, not only remove them.
- **One material, one look:** a piece, broken whole, dug quickly with any
  tool or none, opaque to light as rock is. Its graphics show at a glance
  that it isn't the world's own: looser, darker, without the strata or the
  speckle of what it came from.
- **Dug again, it yields** one of:
  - **soil:** a stone put back and dug again comes back as soil, the lesser
    material. Spoil is then a store of soil, and stone degrades through it.
  - **nothing (dust):** spoil is a sink; what's put down is gone when it's
    taken up. The stronger statement of entropy, and it relieves the pack
    (digging fills it with soil faster than anything uses it), but a heap
    built to climb out of a hole is spent once it's dug away.

  The choice is open. Dust is the purer rule; soil the kinder one. Either
  is a single entry in `inventory.YIELDS`.

## Built pieces

As `docs/tile-set.md` plans them, held by their kinds, with a span of 5
(`support.GAME_SPAN`: a roof reaches 5 tiles from a wall, so a bridge needs
a pillar every 10):

| Piece | Made from | Held |
|---|---|---|
| Plank block | planks | from below, or from the side within the span |
| Platform | planks | from below, or from the side within the span; stood on, jumped up through, dropped through with M |
| Ladder | planks | from below; climbable; its top stood on |
| Rope | fibre (vines, later) | from above; climbable; lengthens downwards when placed |
| Brick block | bricks (stone, at a furnace, later) | from below, or from the side within the span |

Planks place nothing today (`inventory.PLACES`); they would place the
plank block, or the platform, by recipe or by choice. Ladders are the
first way out of a hole that doesn't spend earth, and the first way down a
shaft that doesn't need digging steps.

## What changes in the game

When it's built:

- **Inventory:** soil and stone place SPOIL; ore and gems place nothing;
  SPOIL yields soil or nothing; planks (and then ladders, platforms) place
  their pieces.
- **A spoil material:** a piece, with the BELOW rule and a drop of its
  yield, and its graphics; opaque, so placing or losing it changes the sky
  depth as any block does.
- **Support** already runs a queue of changed tiles and lets pieces fall;
  spoil needs no new mechanism, only its row in the rules. Placed blocks
  stop being terrain.
- **The decision** that dug materials can be placed back as blocks is
  superseded (`docs/decisions.md`).
- **Tests:** the actions model places SPOIL; the support model holds and
  drops it; the feature and support lab (`uv run strat-feature-lab`) gains
  spoil, to see heaps, columns and falls before the game changes.

## Open questions

- **Spoil's yield:** soil or nothing (above).
- **What soil is for**, if not for building: recipes (a furnace's clay?
  growing things?), or only spoil. If it has no use, should grass and soil
  yield anything when dug?
- **The first wood:** felling trees is the only source; ladders depend on
  it, and so does the way down. How soon, and how much, matters more once
  earth can't bridge.
- **Spoil on built pieces:** may a platform hold spoil, and a ladder stand
  on it? The rule above says yes (a solid built piece holds it; spoil holds
  what is held from below); a platform holding heavy earth might rather
  break.
- **Falls into the miner:** spoil falling as an item can't hurt; heaps that
  slide, later, would have to be stopped from burying the miner, or not.
- **The workbench and torches** keep their own rules (the bench from
  below, torches by any solid neighbour); placed on spoil, they're held as
  on anything solid.
