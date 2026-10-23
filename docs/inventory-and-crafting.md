# Inventory and crafting

A design discussion, 2026-10-23: how the miner's belongings could be held,
shown, chosen and inspected, and how crafting could follow from them. It
looks at how open-world crafting games do it, separates the choices they
make, and proposes a design for Stratagem with the questions still open. A
permanent on-screen display (HUD) is set aside: it costs drawing time every
frame, and the games below show it isn't needed (see
[Without a HUD](#without-a-hud)).

## Where we are

- `inventory`: a count (up to 99) of each kind: wood, soil, stone, ore
  and gems (`inventory.py`, step 1, done). Dug material keeps its kind (dug
  grass is soil), and logs gathered in from felled trees are wood. Nothing
  spends wood yet, and nothing shows the counts.
- `hand`: the kind SPACE places: the kind last dug, or, when none of it is
  left, the first kind carried that places something. Choosing it comes
  with the pack screen.
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
  with fuel over time while you do other things.
- **How the shapes were learnt:** mostly by being told, not by experiment.
  Crafting arrived in Indev (early 2010), and Notch announced new recipes
  on his blog and the forums, often with a picture. The shapes look like
  their items, so the common ones could be guessed. Players shared the
  rest, and the community wiki grew with the game; later recipes were
  datamined from each new version. The recipe book (2017), which unlocks
  a recipe when you first pick up one of its ingredients, admitted that
  the game relied on outside help. (From memory, not checked.)
- **For us:** the grid's mouse dragging doesn't suit a BBC keyboard, but
  the grid itself does, with a key for each cell (see
  [Making](#making-a-grid-on-the-keys)). It needs a way to learn the shapes
  without a wiki: a manual, as period games had, and finds in the world.
  Also worth taking: a furnace that works over time, in the world, while
  you're away.

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
3. **That the pack is full,** when something can't be taken. We leave
   this out (decided 2026-10-23): at the cap the extra is simply lost,
   which matters only for bulk materials, and the pack screen shows a 99
   to anyone who looks, as Elite's cargo screen did. Finds that matter are
   owned, not counted, so they can't overflow. Playing may yet show a need.

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
| Shaped grid | Minecraft | high with a key for each cell: no cursor, and shapes to discover, but they must be taught (a manual, finds) |
| Experiment with ingredients | BotW cooking | medium: playful, but needs many outcomes to be worth it |
| Physical, in the world | Exile, TotK, Minecraft's furnace | high for a few stations: matches Exile's physics and our flying items |

### How recipes are found

All shown, as in Terraria. Unlocked by holding an ingredient, as in
Valheim and Minecraft's recipe book. Learnt at a station, as in Don't
Starve. Found by exploring, as in Subnautica. Printed in the manual, as
period games did: Elite's came with a novella and a flight manual, and
most BBC games with at least a card of keys and hints.

## A proposal

### Holding: counts by kind, and things owned

- **Materials and placeables** are counted, a byte each, capped at 99:
  - soil, stone, ore, gems and wood;
  - later bars, fibre and glass;
  - torches, planks, ladders, platforms, doors and benches.

  At most about 24 kinds, so the inventory is a table of 24 bytes. The cap
  makes chests worth having later, without slots to manage now.
  The cap also disposes of spoil. Minecraft's dirt and cobblestone, in
  stacks of 64 across 36 slots, fill the inventory on a long dig, and
  players dump them in lava (the cobblestone problem); Terraria avoids it
  with stacks of 9999. With counts and no slots, soil can't crowd out
  anything, and at 99 the dig still goes through and the extra is lost, so
  a full count works as a trash slot. Nothing signals it: the player's
  diligence, and the pack screen's counts, are enough.
- **Counts are binary bytes, capped at `COUNT_MAX` (99)** (decided
  2026-10-23, after BCD was tried first). In play a gain is `CMP #99`,
  `BCS`, `INC` and a spend is `DEC`, so counts need no rules of their own.
  BCD would have saved the conversion to digits, but that's only needed
  while the pack screen is open and paused: dividing a count by ten, by
  subtraction, is at most about 100 cycles, 24 times on opening.
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
- The pack and the crafting grid are one screen (see
  [Making](#making-a-grid-on-the-keys)). The material chosen there as the
  brush is also what's in hand when the screen closes. The same key
  closes it.
- On closing, the view is redrawn (`draw_view`, as after a jump of the
  camera), which costs a frame or two, once.

```
 +--------------------------------+
 | PACK                           |
 | [soil][stne][wood][ore ][torc] |
 |  42    14    05    03    09    |
 | [plnk][ladr]                   |
 | >10<   04          brush: plnk |
 |--------------------------------|
 | MAKE (workbench near)          |
 |   [stne][stne][stne]           |
 |   [    ][plnk][    ]  -> [pick]|
 |   [    ][plnk][    ]           |
 +--------------------------------+
```

Here the miner has laid out a stone pickaxe: three stone and two planks
have left the counts above (17 to 14, 12 to 10), and the shape is
recognised, so its result shows.

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

### Making: a grid on the keys

A shaped grid, as in Minecraft, but each cell has its own key, so laying
out a recipe is drawing it, with no cursor in the grid (chosen
2026-10-23). One hand chooses the material with the arrow keys, and the
other places it:

```
  cells                   brush                   Master keypad
   T  Y  U                    [up]                   7  8  9
    G  H  J          [left]  [down]  [right]         4  5  6
     B  N  M                                         1  2  3
```

- The **arrow keys** move the brush, a cursor on the pack's icons (eight
  across). Every Beeb has them, at the right of the keyboard, and play
  doesn't use them, so they mean the same everywhere. The left hand takes
  the cells and the right the arrows, which keeps the hands apart.
- A cell's key puts one of the brush's material in that cell, taking it
  from the count. The same key with the same brush takes it back out;
  with another brush it swaps.
- **DELETE** empties the grid back into the pack. (With the right hand on
  the arrows, DELETE, COPY and RETURN are all within its reach.)
- **RETURN** makes the recognised result. Holding it makes more, refilling
  the same shape from the counts, a few a second, until something runs
  short.
- **COPY** steps through the recipe book (below), filling the grid with
  each known shape from the counts. A cell that can't be filled is left
  empty, which shows what's missing. The key's name suits it.
- On the Master 128, the keypad's 7 8 9 / 4 5 6 / 1 2 3 work too, and they
  make a square grid. On the B+ and Integra-B the rows of letters are
  staggered, so the grid leans to the right, but it still reads as a grid
  under the fingers.
- The crafting screen is a mode of its own, paused, so its keys don't clash
  with play (T is the torch and M moves down there).

What's recognised:

- **The grid's size follows the station.** In the hand it's 2 x 2 (T Y /
  G H). Near a workbench it's 3 x 3. A furnace or an anvil near allows
  the recipes that need them. Stations count as near within the miner's
  light window, or a few tiles.
- **Shapes may sit anywhere** in the grid: it's trimmed to the cells used
  before matching, as in Minecraft. Mirror images could also match; to be
  decided by playing.
- **The ingredients are the cells:** one of each per cell, so a recipe's
  cost is its shape.
- The thing made pops out of the miner, or the station, as an item, and is
  gathered in, reusing the burst and gather. That's the feedback that
  something happened, with no extra drawing code.
- The workbench is among the first things made, and is placed as a piece
  in the world, as in `tile-set.md`.

### Learning the shapes: a manual, the world, and a book

Minecraft relied on players telling each other (see
[Minecraft](#minecraft)). We can't count on that, so the game teaches the
shapes itself, in four ways:

- **A small manual,** as period games had: the keys, the setting, and the
  first shapes drawn as grids (planks, torches, the workbench, ladders, a
  door, the stone pickaxe). Enough to start, not everything. It can hint at
  what isn't shown ("the old miners made boots that let them climb the
  air") so that finding the rest is a goal. Written as `docs/manual.md`
  and kept in step with the recipe table, and printable.
- **Shapes that look like their things,** so many can be guessed from the
  manual's examples: a pickaxe of any harder material is the same shape.
- **Finds in the world:** a carved tablet or a page, an item lying in a
  cave or ruin, that teaches one shape when gathered in. A library in a
  ruin, a piece with shelves, could teach several when the miner acts on
  it (L). The rarer things (boots, later the jetpack) are only found this
  way, which makes exploring pay, as Subnautica's fragments do.
- **A recipe book,** in the game: every shape made once, or found, is
  remembered (a bit each), and COPY lays it out again. So nothing has to
  be remembered twice, and the book shows how much has been learnt.

### Later: stations that work in the world

The furnace could be physical rather than a menu, as in Exile's world and
Minecraft's smelting. Ore dropped onto a lit furnace, thrown or placed,
comes out as bars a few seconds later, popping out as items. It's one
behaviour, and it reuses the items' physics. Decide by prototyping once
the list exists.

### A first set of recipes

To be tuned by playing. The shape follows `tile-set.md` and
`game-design.md` (about 20 recipes, three tool tiers).

Shapes are written row by row, `/` between rows and `.` for an empty
cell: W wood, P planks, S stone, O ore, B bars, G gem.

| Makes | Shape | Station | Learnt from |
|---|---|---|---|
| 4 planks | `W` | hand | manual |
| 2 torches | `O/W` | hand | manual |
| workbench | `PP/PP` | hand | manual |
| 3 ladders | `P.P/PPP/P.P` | workbench | manual |
| 4 platforms | `PPP` | workbench | made once |
| door | `PP/PP/PP` | workbench | manual |
| chest | `PPP/P.P/PPP` | workbench | made once |
| furnace | `SSS/S.S/SSS` | workbench | a find |
| bar | `O` | furnace | made once |
| anvil | `BBB/.B./BBB` | furnace | a find |
| stone pickaxe (tier 2) | `SSS/.P./.P.` | workbench | manual |
| iron pickaxe (tier 3) | `BBB/.P./.P.` | anvil | guessed from the stone one |
| boots (double jump) | `B.B/BGB` | anvil | a find only |

"Made once" means it can be guessed, then stays in the book. Bars might
come from a physical furnace instead (below), and then `O` at the
furnace isn't a recipe.

Tier 2 makes stone take two digs rather than four, as already planned in
`next-steps.md` (`QUARTERS_PER_DIG` per tool). The double jump moves from
the start to the boots (`STARTING_ABILITIES = 0`).

## How it would be built

- **Model first:** `tools/stratagem/inventory.py` would hold the kinds,
  caps, recipes, stations, discovery and what's makeable near a position,
  with `gen_tables` generating the tables. The 6502 is checked against it
  in py65, as usual.
- **Parasite:**
  - It owns the counts, the grid (9 bytes of kinds), the recipe
    book (a bit each: 3 bytes), the brush, which is the hand, and the
    owned tools.
  - On opening the pack, it scans the tile cache near the miner for
    stations. That's paused, so time doesn't matter.
  - It answers the host's key presses (brush, cell, make, copy) and sends
    back the counts, the grid and the result to draw.
  - Matching trims the grid to its used rows and columns, then compares
    with each recipe of that size: a few hundred cycles, once per key.
- **Host:**
  - It draws the panel from what the parasite sends. That's at most
    24 counts, 9 cells and a result: well under the packet's room.
  - It reads the crafting keys (about 20, with the keypad's) from a
    table of INKEY numbers, as it reads the game's now.
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
  - Parasite: about 24 bytes of counts, 9 of grid, 3 of recipe book, and
    a recipe table of about 20 x 8 bytes (size, up to 9 cells as
    nibbles, result and count, station).
  - Host: the font, the key table, and the panel's code, about 1.5K in
    MAIN.
  - Neither touches the render region's tight space.
- **Per-frame cost in play:** none, apart from the hand's icon while it's
  shown.

## Open questions

1. Counts by kind, or slots and stacks? The proposal says counts (binary,
   capped at 99: decided). Slots matter only if capacity is meant to be a
   pressure.
2. Should the pack pause the world? The proposal says yes. Terraria and
   Minecraft don't pause, and BotW does.
3. Icons only, or names too? A font costs about 400 bytes and some host
   time.
4. How are shapes learnt? The proposal: the manual, guessing, finds in
   the world, and a book of what's been made or found. Should holding an
   ingredient also reveal shapes, as in Valheim? That would make the
   manual and finds matter less.
5. Is the furnace a menu station or a physical one? Prototype both.
6. Does dug material keep its kind? The proposal says yes. Then is there
   one cap per kind, or a total that makes the miner choose what to keep?
7. Keys: which key opens the pack (P is free; RETURN now makes)? TAB to
   cycle the hand in play?
8. Should movement in play be WASD, with dig and place on K and L? It
   breaks with BBC custom (Z X and * ?) but is what players now expect.
   It's now separate from crafting, which uses the arrows. Try it in the
   emulator.
9. Do mirrored shapes match?

## Steps

1. Done: inventory by kind (model, then the 6502): dug material keeps its
   kind. Placing puts back the kind in hand. Wood joins the table.
2. The pack screen: paused, icons and counts, with the brush chosen by
   the arrow keys as the hand. Plus the cycle key and the hand's icon
   above the miner.
3. The 2 x 2 hand grid on T Y / G H: planks, torches, the workbench.
   The recipe book and COPY. The manual's first pages.
4. The workbench as a piece, and the 3 x 3 grid near it: ladders,
   platforms, doors, the stone pickaxe and its faster digging.
5. The furnace and anvil, bars, the iron pickaxe, finds in the world, and
   the boots, with the double jump earned.
