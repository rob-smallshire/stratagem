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
- **Held from below only**: by undisturbed rock, by soil that is held, or
  by a solid built piece beneath it. Nothing from the side, so no bridge,
  no ledge, no overhang. Put down in the sky, or out over a drop, it
  doesn't stay.
- **It subsides, slowly:** not at once, as a felled tree does, but from
  below, upwards, by chance (Subsidence, below). Soil can stand unheld for
  a while; what fails is gone (dust, nothing gathered), and the soil above
  is then at risk in turn. A shaft can't be filled from its top; it is
  filled from the bottom up, which is also how a hole is climbed out of:
  place below while jumping, stand on it, again.

### Natural soil: two options, both open

Soil put down must be held from below, or a bridge of it is the stone
bridge again. The world's own soil is terrain today, held without limit.

1. **Natural soil stays anchored**; only soil put down is held from below
   and subsides. Cheap, and the world stays as it is; but two tiles alike
   to look at behave differently (a soil ceiling over a tunnel stands;
   soil put down can't overhang), told apart by a bit in the tile that the
   player never sees.
2. **All soil is loose**, the world's too (grass is soil with grass on
   it). Soil is loose ground: tunnels belong in rock, and undermining the
   soil brings it down, grass, trees and all, slowly. More truthful, and
   it gives soil a character; and it costs little, as the experiments
   below show.

### Subsidence

Real subsidence is slow: it starts from below and works upwards, and
ground can stand undermined for a long while. So:

- A loose tile is **at risk** while the tile under it is open.
- Each frame a few tiles at risk (4) are **rolled for**; each fails with a
  small chance (1 in 64, or 1 in 256), less when it's wedged between solid
  sides (an arch: the chance divided by 1 + 2 for each solid side). At
  most 2 tiles fail in a frame (each is a changed tile to send).
- A tile that fails is **gone**, which puts the tile above it at risk; a
  tree standing on it comes down, as the support rules already have it.
- **Slumping** (tried, and not in the game: soil has no strength
  sideways, so needs none of this): a face with an open drop beside it deeper than any step
  the hills are generated with (4 tiles or more: their steepest is 3) also
  fails, at a much smaller chance (1 in 512), until no drop beside it is
  so deep. So a soil wall left by digging wears back to a stepped slope,
  and a free-standing heap of soil to 3 high; the hills as generated never
  move.

The experiments (`uv run strat-subsidence-lab`, the model
`stratagem.subsidence`; build/features/subsidence.png), on scenes dug into
the real world:

| Scene | All soil loose, 1/64, slumping | Only soil put down |
|---|---|---|
| A tunnel through the soil, under the grass | its roof goes over about 25s; a trench open to the sky | stands |
| A room 5 wide and a pocket 1 wide at the soil's base | the collapse climbs to the surface and widens: a crater, about 2 minutes | stands |
| A tunnel under a tree | a trench in about 25s; the tree comes down | stands |
| A tunnel in the rock, under the soil | stands (a little soil slumps where its end comes out under the hillside) | stands |
| A shaft through the soil into the rock | slumps to a funnel over about 40s | stands |
| Soil put down: a column, and a bridge over a shaft | the bridge falls within 5s; the column slumps to 3 high, or into the crater beside it | the bridge falls; the column stands |

At 1 in 256 the same happens about three times as slowly. The work is
fixed and small: 4 rolls a frame, at most 2 failures, never more than
about 30 tiles at risk at once in these scenes (a list of them, as the
torches' queue is); the generated hills put nothing at risk.

## Built pieces
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

With option 2: all soil is loose, the world's too. And soil has **no
strength sideways** (decided 2026-11-01, after the first build): no arch,
no slumping. Only a tile directly undermined is at risk, so a cut into a
hillside stands as dug, and a small excavation stays small; with slumping,
small digs grew into craters that cut back into the hills.

And soil that fails **drops a tile**, into the empty tile below, rather
than vanishing (decided 2026-11-01): as sand does in some games, but
slowly and by chance. Soil is kept until it is mined (where entropy takes
it); a tunnel through soil fills from above, and the ground over it sinks
into a hollow. It drops only into air or sky (a torch, a tree's part or
water holds it), as soil (disturbed grass is soil), and never onto the
miner (it waits). The tile it leaves is sky if the tile above it is sky,
so sinking ground shows the sky behind it, not a black cave in the shape
of the hill that was.

- **Inventory:** no carried soil; grass and soil yield nothing; stone
  places soil; ore and gems place nothing (`inventory.YIELDS`, `PLACES`).
  The miner starts with the torches in hand. Planks place nothing yet.
- **Subsidence** (`asm/subsidence.asm`, in PLIGHT, as `stratagem.subsidence`
  exactly): every change by `change_target` (a dig, a placing, a tile
  subsiding), once the tile cache has it, notes the tiles it may have put
  at risk (itself, and the tile above it) into a queue of 64, each once.
  Each frame, after the player's action, 2 are taken from its head and
  rolled for, by MBANK's LFSR stepped 8 times, against a 16-bit threshold
  (1 in 64). One that fails drops: over two frames, as the game changes
  one tile a frame through `change_target` (relit, sent, and noted in
  turn), the tile below becomes soil, then the tile itself empties
  (`subside_pending`); nothing else is rolled for meanwhile. At most one
  a frame, only when the player hasn't changed a tile that frame, and
  never into a tile the miner is in (`subside_miner`, `subside_clear`).
- **Only in the tile cache:** every tile it reads is read from the cache
  (`subside_material`), a quick look; outside it a tile is solid and not
  loose, isn't noted, and if queued waits, unread, until the miner comes
  back. So subsidence happens around the miner. (Read through the world's
  store, `tile_at`, a check cost about 1,200 cycles and a failure frame
  over 100,000.)
- **Costs** (py65, a tunnel three wide dug through the soil beside the
  miner): `subsidence_step` about 1,500 cycles a frame while soil is at
  risk (1,700 at most), against an idle frame's 4,800; noting a changed
  tile about 600; each of a drop's two frames costs as a dig does (about
  65,000, the light's flood and relighting most of it). With slumping,
  these were 2,500 and 4,300.
- **Tests:** `tests/test_subsidence.py`: the model's scenes (a tunnel in
  the soil subsides to the sky; one in the rock stands, and the hills
  stay; a cut into a hillside stands; soil put down over a drop falls; the
  queue's limit), and the parasite frame by frame as the model, in py65:
  its queue, its random generator and the tiles that fail.
- **In the emulator:** a cutting dug into the hillside beside the start:
  over about 20 seconds the soil over it drops in and fills it, the
  hillside settling in steps, sky behind; the tile over the miner waits
  above him (build/subsidence/subsidence-game.png). A shaft the miner
  digs still takes its background from the surface as generated (cave,
  black, below it): digging could follow subsidence's rule.

## Open questions

- **Natural soil:** loose, as built; anchored remains possible (a bit in
  the tile for soil put down).
- **The chance:** 1 in 64, with 2 rolls a frame, is a first guess, to tune
  by playing: slow enough to see coming and get out of, quick enough to
  matter.
- **Soil on built pieces:** may a platform hold soil, and a ladder stand
  on it? The rule above says yes (a solid built piece holds it); a
  platform holding heavy earth might rather break.
- **The miner under subsidence:** what fails is gone, so it can't bury or
  hurt; the miner standing on soil that fails drops with it.
- **The workbench and torches** keep their own rules (the bench from
  below, torches by any solid neighbour); on soil, they're held as on
  anything solid, and fall when it fails.
