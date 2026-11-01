# Building, soil and support

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
  is carried as loose stone; stone put back is soil, not rock; soil dug is
  nothing at all. Crafting is the one way up: work and a tool turn wood
  into planks, stone into a pickaxe's head, and later ore into bars and
  stone into bricks.
- **Building is a craft.** Structures are made of refined, made things:
  planks, ladders, ropes, platforms, later bricks, each held up by the
  rules for its kind. Raw material can be dumped, not built with.
- **The world can trap you.** Digging a hole you can't climb out of is
  allowed (decided 2026-11-01). A careful explorer carries a way out:
  stone to heap as soil a step at a time, or a ladder.

## The ladder of entropy

**Rock → stone (carried) → soil (put down) → nothing (dug).**

| State | What it is | Becomes |
|---|---|---|
| Undisturbed | the world as generated: grass, soil, stone, ore, gems, bedrock | dug: stone, ore and gems are carried; grass and soil are nothing |
| Carried | a kind in the pack: stone, ore, gem, wood | crafted: something made; stone placed: soil |
| Made | planks, torches, the workbench, pickaxes; later ladders, ropes, platforms, bricks | placed: a built piece, held by its rule |
| Soil | the world's soil, and stone put down | dug: nothing |

Soil and spoil are one: there is no carried soil, and no second kind of
fill. Digging grass or soil yields nothing (so the pack no longer fills
with earth faster than anything uses it); stone put down is soil, the
lesser material, in the world's own soil's look; soil dug is gone. Soil
has no use beyond this, and that is its place: where entropy ends. Ore
and gems can't be put down: too valuable to dump.

## Soil

- **Put down** with SPACE, from stone in hand, where a block can go now:
  an empty tile (air or sky), ahead, above or below, clear of the miner
  (placing ahead takes the first column wholly ahead of the miner, since
  2026-11-01).
- **It stays where it's put,** as the world's own soil does: digging is
  tidy, and nothing comes down on its own.

### Subsidence: tried, and dropped (2026-11-01)

Soil held from below only, failing slowly and by chance, was built
(all soil loose, the world's too; no strength sideways; a tile that failed
dropping into the space below) and then taken out. It made digging near
the surface messy and confusing, the ground dropping in whole tiles showed
the tile grid that the rest of the game hides, and it had no purpose in
play to set against that. The ladder of entropy above stays. The
experiments, the model and the game's code are in the history (commits
`73b14a1` to `74dcfa6`; `stratagem.subsidence`, `asm/subsidence.asm`).

So soil put down is terrain again, and a bridge of it stands: the
principle that nothing put down spans is, for soil, not kept. Built pieces
keep their rules below.

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

The first wood comes from felling trees. Planks place nothing today
(`inventory.PLACES`); they would place the plank block, or the platform,
by recipe or by choice. Ladders are the
first way out of a hole that doesn't spend earth, and the first way down a
shaft that doesn't need digging steps.

## In the game (built 2026-11-01)

- **Inventory:** no carried soil; grass and soil yield nothing; stone
  places soil; ore and gems place nothing (`inventory.YIELDS`, `PLACES`).
  The miner starts with the torches in hand. Planks place nothing yet.
- **A tile keeps its background** whatever is put down or dug there
  (`target_background`): soil put down in the sky and dug again leaves
  sky; a shaft the miner digs from the surface is cave, black, below it,
  as its tiles were generated.

## Open questions

- **Soil put down over a drop:** it stays, so soil bridges the chasms
  that the built pieces' spans are meant to make hard. A rule at placing
  (soil only onto something solid beneath it) would keep it tidy without
  anything coming down later.
- **Soil on built pieces:** may a platform hold soil, and a ladder stand
  on it?
- **The workbench and torches** keep their own rules (the bench from
  below, torches by any solid neighbour).
