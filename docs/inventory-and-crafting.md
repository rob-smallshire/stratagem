# Inventory and crafting

A design discussion, 2026-10-23: how the miner's belongings could be held,
shown, chosen and inspected, and how crafting could follow from them. It
looks at how open-world crafting games do it, separates the choices they
make, and proposes a design for Stratagem with the questions still open. A
permanent on-screen display (HUD) is set aside: it costs drawing time every
frame, and the games below show it isn't needed (see
[Without a HUD](#without-a-hud)).

## Where we are

- `inventory`: one count (up to 99) of dug blocks of any material. The place
  key (SPACE) puts back `PLACED_TILE`, whatever was dug.
- `wood`: logs gathered in from felled trees (`items.py`). Nothing spends
  it, and nothing shows it.
- Torches: dropped with T, at most 24 in the world, never picked up; not
  counted as held.
- Dropped items exist as sprites that burst out and are gathered in. The
  same machinery can show anything small near the miner for a moment.
- Keys: Z X K M (move), L (dig, act), SPACE (place), T (torch).

So the miner carries things, but can't see what, choose what, or make
anything.

## How other games do it

### Terraria

- **Holding:** 50 slots (a hotbar of 10 and 40 more), plus coin and ammo
  slots. Materials stack to 9,999 (999 before 1.4.4), tools and weapons
  take a slot each. Chests hold more.
- **Showing:** the hotbar is always on screen, with health, mana and buffs.
  ESC opens the full inventory over the world, which keeps running.
  Picked-up items float a label ("Wood (12)") over the player.
- **Choosing:** the number keys or the mouse wheel select a hotbar slot.
  What's selected is what you swing, place or use.
- **Crafting:** the inventory screen lists every recipe you can make now,
  given what you carry and the stations near you (a workbench, a furnace,
  an anvil and so on, within a few tiles). It's a scrolling list of
  results, not a grid. You click one to make it, or hold to make many.
  New stations widen the list. The Guide NPC shows what an item is used
  in. There are hundreds of recipes, and many players use the wiki.
- **For us:** recipes shown only when they can be made. Stations as pieces
  in the world, and progress by building the next station. The list
  needs no knowledge and no experimenting, so it's well suited to a small
  screen.

### Minecraft

- **Holding:** 36 slots (a hotbar of 9 and 27 more), plus armour and an
  off-hand slot. Most items stack to 64, some to 16, tools to 1. Chests,
  shulker boxes and ender chests hold more.
- **Showing:** Minecraft does have a HUD: the hotbar, hearts, hunger,
  experience and armour are always on screen (F1 hides them). It's small
  and at the edge. The item in hand is also drawn in the miner's hand.
  E opens the inventory, but single-player keeps running behind it.
- **Choosing:** 1-9 or the mouse wheel.
- **Crafting:** shaped recipes on a grid: 2 x 2 in the inventory, 3 x 3 at
  a crafting table. A pickaxe is the shape of a pickaxe. Furnaces smelt
  with fuel over time while you do other things. Recipes were discovered
  by experiment or the wiki until the recipe book (2017), which unlocks a
  recipe when you first pick up one of its ingredients.
- **For us:** the grid is charming but needs a cursor, item dragging and a
  wiki. On a keyboard-only BBC it would be slow to use and opaque to
  learn. Two things are worth taking:
  - recipes unlocked by picking up an ingredient;
  - a furnace that works over time, in the world, while you're away.

### Zelda: Breath of the Wild (and Tears of the Kingdom)

- **Holding:** a pause menu with tabs: weapons, bows, shields, armour,
  materials, food, key items. Weapon slots are few, wear out and are
  expanded by a quest (Korok seeds). Materials stack to 999.
- **Showing:** a minimal HUD (hearts, stamina when used, a minimap, the
  equipped items), which can be reduced further (Pro HUD) or hidden. The
  menu pauses the world.
- **Choosing:** the d-pad quick menu, with the world slowed, picks weapon,
  shield, bow or rune.
- **Crafting:** cooking. Hold up to five ingredients and drop them in a
  pot. The result follows from their categories and effects, and needs no
  recipe. Recipes you've made are remembered in the food's description.
  Upgrades (armour) are done by fairies for materials. In Tears of the
  Kingdom, fusing joins any two things physically, and Ultrahand builds
  machines from parts.
- **For us:** crafting as experiment with physical things in the world,
  not a menu. The pause-menu inventory, with nothing on screen in play,
  is the model for not having a HUD. Exile's physics suggest a Stratagem
  version: put things on a station in the world, and something comes out.

### Valheim

- **Holding:** a grid of 32 slots, with weight limiting what you carry.
- **Crafting:** a list, like Terraria, at a station (workbench, forge),
  near which you must be. Stations are upgraded by placing extensions next
  to them. A recipe appears once you've held one of its ingredients, so
  the list grows as you explore and never shows what you've never seen.
- **For us:** discovery by holding. It's the gentlest way to reveal
  recipes without a wiki and without a long list of things you can't
  make.

### Don't Starve

- **Holding:** 15 slots and a few equipment slots, always on screen.
- **Crafting:** tabs down the side of the screen (tools, light, survival
  and so on), always visible. Each shows what you could make, and what is
  missing. Advanced recipes must first be prototyped at a science machine,
  near which they become available. Once made, they can be made anywhere.
- **For us:** "learn at the station, make anywhere afterwards", and showing
  what's missing for a recipe as well as what you can make.

### Subnautica

- **Holding:** a grid where items take different sizes (a Tetris-like
  backpack).
- **Crafting:** a fabricator station with a menu tree. Blueprints come
  from scanning fragments found while exploring, so finding things in the
  world unlocks what you can build.
- **For us:** exploration unlocking recipes. It fits Stratagem's loop
  (explore, gather, craft, reach new places): a gem or a ruin found deep
  down could teach a recipe.

### Exile (BBC Micro, 1988)

- **Holding:** one object held in hand, and five pockets as a stack. Store
  pushes the held object onto the top, and retrieve pops the last one
  stored. Weapons (jetpack, pistol and so on) are chosen separately and
  share an energy store. Any object can be pocketed, whatever its size.
- **Crafting:** none. Things are combined physically: carry a key to a
  door, a fluffy to a fire, a grenade to a nest.
- **For us:** this is the closest hardware. Showing almost nothing works
  when what you carry is small and you remember it. A stack is simple, but
  it gets awkward past a few things, and digging gathers dozens of things.

### Elite (BBC Micro, 1984)

- **Holding:** the cargo hold, as counts of commodities (tonnes, grams, kg)
  with a total capacity, and equipment as fitted or not, not counted.
- **Showing:** separate full screens on the function keys (inventory,
  status, market), drawn in text, with nothing on the flight view.
- **For us:** counts by kind are compact, plain, and need no slot
  management. Equipment is owned rather than carried. A separate screen is
  cheap on this hardware, because it's drawn once.

### Others, briefly

- **Stardew Valley:** recipes learned from people, television and levels,
  and machines that turn inputs into outputs over time.
- **Factorio:** making an item makes its missing intermediate items too,
  from raw materials, and a queue makes things in the background.
- **Core Keeper and Starbound:** Terraria's model. In Starbound, picking up
  materials teaches recipes.

## Without a HUD

The games that show least (Breath of the Wild, Exile, Elite) still tell
the player three things at the moment they matter:

1. **Something was gained.** We have this already: the logs fly into the
   miner. A brief label or icon above him would add how many.
2. **What's in hand,** when it changes, and when it's used up.
3. **That the pack is full,** when something can't be taken.

Everything else waits for the player to ask, in a paused screen. That
fits the BBC: a paused screen costs drawing time once, not every frame, and
needs no racing the beam.

## The choices

### How things are held

| Model | Who | Good | Costly |
|---|---|---|---|
| Slots and stacks | Terraria, Minecraft, Valheim | familiar; capacity makes chests and bases matter | moving stacks about; needs a cursor UI; lists of slots to show |
| Counts by kind | Elite, BotW's materials | one byte per kind; nothing to manage; one place for each thing | capacity needs a separate rule (a cap per kind, or a total) |
| A stack of objects | Exile | tiny; physical | awkward beyond a handful; no counts |
| Owned, not counted | Elite's equipment, Zelda's key items, Metroid | tools and upgrades as progression flags; nothing to lose | only for things you have one of |

### How the item in hand is chosen

- A hotbar with number keys (Terraria, Minecraft). It needs a HUD to be
  useful.
- A cycle key, with a short display of the new choice (BotW's quick menu
  without the menu).
- Choosing in the paused screen only.

### How crafting is done

| Model | Who | Fit for us |
|---|---|---|
| List of what can be made now | Terraria, Valheim, Don't Starve | high: icons, a cursor down a list, no knowledge needed |
| Shaped grid | Minecraft | low: a cursor UI, and recipes to be learned elsewhere |
| Experiment with ingredients | BotW cooking | medium: playful, but needs many outcomes to be worth it |
| Physical, in the world | Exile, TotK, Minecraft's furnace | high for a few stations: matches Exile's physics and our flying items |

### How recipes are found

All shown, as in Terraria. Unlocked by holding an ingredient, as in
Valheim and Minecraft's recipe book. Learnt at a station, as in Don't
Starve. Found by exploring, as in Subnautica.

## A proposal

### Holding: counts by kind, and things owned

- **Materials and placeables** are counted, a byte each, capped at 99:
  - soil, stone, ore, gems and wood;
  - later bars, fibre and glass;
  - torches, planks, ladders, platforms, doors and benches.

  At most about 24 kinds, so the inventory is a table of 24 bytes. The cap
  makes chests worth having later, without slots to manage now.
- **Tools and upgrades** are owned, not counted: a pickaxe tier, boots,
  the jetpack. They're bits, like `zp_abilities` already. Nothing to
  choose between: the best pickaxe owned is used.
- What's dug becomes its own material, not one general count. Placing
  soil puts soil back. Stone and ore are distinct, so ore can be smelted.

### Seeing: a pack screen, paused

- A key opens the pack, and the world pauses. RETURN is suggested: it's
  free and easy to find.
- The view is overlaid by a panel, or dimmed and overlaid. The panel shows
  what's held as icons with counts, eight across: each icon is a tile's
  8 x 16 graphics, which exist already for materials and pieces, with
  two digits under it.
- A cursor moves with the movement keys. L or SPACE puts the item under
  the cursor in hand. The same key again on RETURN closes the screen.
- On closing, the view is redrawn (`draw_view`, as after a jump of the
  camera), which costs a frame or two, once.

```
 +--------------------------------+
 | PACK                           |
 | [soil][stne][wood][ore ][torc] |
 |  42    17    05    03    09    |
 | [plnk][ladr]                   |
 |  12    04  <                   |
 |--------------------------------|
 | MAKE (workbench near)          |
 | [plnk] 4  <- [wood] 1          |
 | [ladr] 2  <- [plnk] 3          |
 | [door] 1  <- [plnk] 6   short 2|
 +--------------------------------+
```

- Icons and digits need no text. A name for the item under the cursor
  could follow later, which would need a small font of about 400 bytes.

### Choosing: a hand, and a cycle key

- SPACE places what's in hand. Placeable things are the only ones you can
  hold in hand at first.
- A cycle key moves the hand to the next placeable thing held. TAB is
  suggested.
- When the hand changes, or the last of something is placed, its icon is
  shown above the miner for about a second. It's drawn as an item sprite,
  so it costs what an item costs, and only while it's shown.
- The torch key stays as a shortcut, and torches become counted and
  craftable (wood and something that burns).

### Making: a list, by station, unlocked by holding

- The pack screen's second panel lists the recipes known that the
  stations near the miner allow. Stations count as near within the miner's
  light window, or a few tiles. Each recipe shows its result, the count
  made, its ingredients, and what's missing if it can't be made.
- A recipe becomes known when any of its ingredients has been held, as in
  Valheim. So the list starts with a handful and grows as you explore.
  Recipes found by exploring (a gem, a ruin) can come later, as in
  Subnautica.
- L makes one. Holding L makes more, a few a second.
- The thing made pops out of the miner, or the station, as an item, and is
  gathered in, reusing the burst and gather. That's the feedback that
  something happened, with no extra drawing code.
- Hand crafting needs no station, and covers the first few recipes (planks
  and torches), like Minecraft's 2 x 2 grid. The workbench is the first
  thing made, and placed as a piece in the world. It unlocks the rest of
  the wooden recipes, as in `tile-set.md`.

### Later: stations that work in the world

The furnace could be physical rather than a menu, as in Exile's world and
Minecraft's smelting. Ore dropped onto a lit furnace, thrown or placed,
comes out as bars a few seconds later, popping out as items. It's one
behaviour, and it reuses the items' physics. Decide by prototyping once
the list exists.

### A first set of recipes

To be tuned by playing. The shape follows `tile-set.md` and
`game-design.md` (about 20 recipes, three tool tiers).

| Makes | From | Station |
|---|---|---|
| 4 planks | 1 wood | hand |
| 2 torches | 1 wood, 1 ore (or coal later) | hand |
| workbench | 6 planks | hand |
| ladder (2) | 3 planks | workbench |
| platform (4) | 2 planks | workbench |
| door | 6 planks | workbench |
| chest | 8 planks | workbench |
| furnace | 12 stone | workbench |
| bar | 3 ore | furnace |
| anvil | 5 bars | furnace |
| stone pickaxe (tier 2) | 4 stone, 2 planks | workbench |
| iron pickaxe (tier 3) | 4 bars, 2 planks | anvil |
| boots (double jump) | 3 bars, 1 gem | anvil |

Tier 2 makes stone take two digs rather than four, as already planned in
`next-steps.md` (`QUARTERS_PER_DIG` per tool). The double jump moves from
the start to the boots (`STARTING_ABILITIES = 0`).

## How it would be built

- **Model first:** `tools/stratagem/inventory.py` would hold the kinds,
  caps, recipes, stations, discovery and what's makeable near a position,
  with `gen_tables` generating the tables. The 6502 is checked against it
  in py65, as usual.
- **Parasite:**
  - It owns the counts, the known recipes (a bit each: 3 bytes), the hand
    and the owned tools.
  - On opening the pack, it scans the tile cache near the miner for
    stations. That's paused, so time doesn't matter.
  - It answers the host's requests, such as making a recipe, by number.
- **Host:**
  - It draws the panel from what the parasite sends. That's at most
    24 counts and a list of recipe numbers: well under the packet's room.
  - Icons come from the material pages and piece library it already has.
  - Digits are a small 4 x 7 font, about 70 bytes, generated from Python.
    The panel's code lives in MAIN, which has room.
  - Drawn while paused, so no beam racing. Its cost is once, on opening,
    and then per cursor move.
- **Dimming:** the tile colour group (logical 8-15) can be remapped to dim
  colours or black in the palette, for a few cycles, leaving the panel in
  the sprite colour group to stand out. Pieces in front are in that group
  too and would stay bright, so either accept that, or draw a solid panel
  over a view left as it is.
- **Memory:**
  - Parasite: about 24 bytes of counts, 3 of known recipes, and a recipe
    table of about 20 x 6 bytes.
  - Host: the font, and the panel's code, about 1K in MAIN.
  - Neither touches the render region's tight space.
- **Per-frame cost in play:** none, apart from the hand's icon while it's
  shown.

## Open questions

1. Counts by kind with a cap of 99, or slots and stacks? The proposal
   says counts. Slots matter only if capacity is meant to be a pressure.
2. Should the pack pause the world? The proposal says yes. Terraria and
   Minecraft don't pause, and BotW does.
3. Icons only, or names too? A font costs about 400 bytes and some host
   time.
4. Should recipes unlock by holding an ingredient, all be shown, or be
   learnt at stations?
5. Is the furnace a menu station or a physical one? Prototype both.
6. Does dug material keep its kind? The proposal says yes. Then is there
   one cap per kind, or a total that makes the miner choose what to keep?
7. Keys: RETURN for the pack, TAB to cycle the hand?

## Steps

1. Inventory by kind (model, then the 6502): dug material keeps its kind.
   Placing puts back the kind in hand. Wood joins the table.
2. The pack screen: paused, icons and counts, with a cursor to put things
   in hand. Plus the cycle key and the hand's icon above the miner.
3. Recipes: hand crafting (planks, torches, workbench) in the pack
   screen's second panel, with discovery by holding.
4. The workbench as a piece, and the recipes it allows: ladders,
   platforms, doors, the stone pickaxe and its faster digging.
5. The furnace and anvil, bars, the iron pickaxe and the boots, with the
   double jump earned.
