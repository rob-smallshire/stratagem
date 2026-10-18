# Stratgem Elements

## Prompt:
18/10/2026, 17:25:24

Terraria seems like a good game concept for a port to retro hardware, of course with massive simplifications. What are the key elements of this game? I'm thinking of using something based on the Exile game engine.

## Response:
18/10/2026, 17:25:35 · gpt-6

> **Searched 5 websites**
>
> 
>
> Worked for 12s

I think Terraria is an excellent candidate for radical simplification onto retro hardware. And Exile is a particularly interesting starting point, because it already implements some of the hardest parts of a game like Terraria: a large, persistent, explorable 2D environment, sophisticated physics, object interactions, and creatures with autonomous behaviours.

In fact, there's an interesting argument that **Exile already has much of Terraria's moment-to-moment gameplay, but lacks Terraria's central progression and world-modification mechanics.**

The trick would be to identify which parts of Terraria create its extraordinarily compelling gameplay loop, rather than trying to reproduce its enormous catalogue of objects, monsters, crafting recipes and biomes.

## 1\. What makes Terraria Terraria?
[![Terraria: confira as melhores dicas para mandar bem no game](https://images.openai.com/static-rsc-4/HYIUj7DkkEkjXYVFuNB6ZL3ImLgjdIiX1alD3qVeKTIdpjeMZPhtvcYrNtwvxYRTv4nGTL_s_Ndf2oaxXEfOmyjD9V8DLXzEoqGz4SIE4s3D85azwM8qG6q6uIDGTM_oO18tdiURLNfnVLerSHVMIOAshkOpYDh-jniN4ev-IWEev5l_k5yIROgK_tNoObaO?purpose=fullsize)](https://www.techtudo.com.br/noticias/2014/12/terraria-confira-melhores-dicas-para-mandar-bem-no-game.ghtml)

[![Image](https://images.openai.com/static-rsc-4/j7hcZufngh9yhepkSW1MLfyn3jHp9nhoeNVBzCugHOOEKllO5Uw2uCKcSLyie9iOTgS7ETiPLUWw1fTsjYDNFVhiyPrsIivaNOvFtSghjAjs2KwGOd2qd8Lb1Gw1ubdlZVEFZAQe6us7NeFbve0In9_3mIqpBCDrkv9C3nu6ioVbrhuUG3zBZ1ykVT8J088q?purpose=fullsize)](https://store.steampowered.com/news/posts/?enddate=1706208644&feed=steam_community_announcements)

[![Terraria, guía para novatos ¿Y ahora qué?](https://images.openai.com/static-rsc-4/manxAGAbcj95ramElIdQCRI9IN3DvQoXDI4QQUS5ur9iOjMUrnzYR2W0j04cGKX4k2nLNtPZfdKBqR1dBSJs8AiTSxQLUGok7al8QKnlQl_r_fbeipUpyTj78rGRLJFJrFpmCMZUrlFUgZH33NH4X59y15Rnadvuzvhs0xgD6m1HoAZfz1FITvUY_7jt2_mD?purpose=fullsize)](https://www.bananatic.com/es/juegos/terraria-gu-a-para-novatos-y-ahora-qu-7388)

[![Exile (1988)](https://images.openai.com/static-rsc-4/7UPOcS5r1tqUbTFCSX6-bminIIddgCaguvjnURayTef4Q_W6NmXolnZ08BCjEU4oDRgiZT4qyc1dtzfVH5o_oNJFoiOfkgHwHUoOvspZSbp3xG2-rLYZuNU5WMGRoAPOW379uNpqf_3Hhz4phmKAW8h2Q3KsTIcBI02KANM3ZTWHmTr5J7u-Qj9G7uelipKF?purpose=fullsize)](https://www.igdb.com/games/exile)

[![【テラリア#6】地下に広がる氷の世界、そしてVSクトゥルフの目！ | 流離いのテラリア日記](https://images.openai.com/static-rsc-4/KFL1JeDspdm_2opf5ehJZ6rOCC_0HlSu4-mzLchWmszxOAwHvlhUu4nVrbG0rYfWZjFLCpkoAvPCuiQV1ea1EOR-IsD4L-nr-tkax0F73nErpmeSV3huY_1xRuJSYPoyd0JJ-kiq_q0ruY8OzDeCCVLSbUAaQfzbHN1Yx40RxCfLZipJQ6IKOQ9oJivZ-ibO?purpose=fullsize)](https://ameblo.jp/wandering-terrarian1209/entry-12753193922.html)

[![Steam Community :: Terraria](https://images.openai.com/static-rsc-4/4VgYH1h-HwNhBrBykrZZt5ZRvvpSPToRKSeaoB7GFmhkUyQQUTDuGCgVVUUGyfOKzSLgLrxMx5y44q9juSqvaZgqU9D08rUBJNPJngFYDSQtTV-9KZckXVWu4mapfqeuJmnvuyr89APExNvd-bxgWTTOo4odRN3ry6O5Ne88PVtCCwQUvjtJtJOjYNbypMaj?purpose=fullsize)](https://steamcommunity.com/app/105600/screenshots/)

[![Terraria: Crafting 101 - Recipes and Complete Station | GamesCrack.org](https://images.openai.com/static-rsc-4/NLzHYR9VyBItOZS1ugTYgQrPE3pm7xgjAKXbNpG4Ln_ugOAPdWmaxfAz199g3I9Ady_L4uFfoh0MW3KGaOsWPrxZnw9FzH-pmwJt4d8lAdCyzdH68QzjlMbSeCVaFwluHC_9b0raTlxtwWpAa6cWsOvm5Y1x4Iid-NW7WMwWOx_NHhLrRwjEllJUiK6Ez5gR?purpose=fullsize)](https://gamescrack.org/terraria/crafting-101/)

I would divide Terraria into six essential systems.

| System | What it contributes | Importance |
|--------|--------|--------|
| **Exploration** | Discovering caves, resources, secrets, enemies and new environments | Essential |
| **Terrain modification** | Digging, tunnelling, placing blocks and constructing shelters | Essential |
| **Resource gathering** | Mining, collecting, harvesting and looting | Essential |
| **Crafting and equipment** | Turning discoveries into new capabilities | Essential |
| **Combat and progression** | Increasingly dangerous encounters, better equipment, bosses | Very high |
| **World simulation** | Day/night cycles, creatures, liquids, environmental hazards, NPCs | Selective |

The most important thing is how these systems reinforce one another.

You explore to find resources. You use resources to make tools. Better tools allow you to reach places that were previously inaccessible or too dangerous. Those places contain better resources, and so on.

This is the part I would preserve almost intact.

## 2\. What Exile already provides

Exile was remarkably ambitious for a 6502 machine. Several of its design choices are highly relevant.

| Exile feature | Terraria equivalent or opportunity |
|--------|--------|
| Large, scrollable world | Terraria's expansive 2D world |
| Gravity, inertia and collisions | Platforming and environmental interaction |
| Autonomous creatures | Enemies, wildlife and NPCs |
| Objects with physical properties | Dropped resources, weapons and equipment |
| Carrying and manipulating objects | Inventory and item interactions |
| Explosions and environmental interactions | Mining, demolition and hazards |
| Persistent changes to world state | Player construction and excavation |

There is, however, one architectural distinction that changes almost everything.

**Exile is primarily an object-and-geometry simulation. Terraria is primarily a tile-world simulation.**

Terraria's terrain is made of individually addressable, destructible, replaceable cells. That makes excavation and construction straightforward to represent, even if it creates its own challenges for rendering and simulation.

Exile's sophisticated object physics could be reused conceptually, but I would be wary of retaining its existing terrain representation if that prevents efficient digging and building.

My inclination would be a hybrid: **tile-based terrain, Exile-style physics for moving objects and creatures.**

That would preserve much of Exile's character while adding the defining mechanic of Terraria.

There's an especially useful discovery here: Exile's terrain is already tile-based, but its 256×256 world is generated by a deterministic function rather than stored as a conventional map. The reconstructed engine computes terrain from coordinates using roughly 500 bytes of code, plus about 1 KB of hand-placed data. \[[How Exile builds a world](https://bbcexile.com/how-exile-works/02-landscape-generation/?utm_source=chatgpt.com); [How Exile draws the world](https://bbcexile.com/how-exile-works/03-graphics/?utm_source=chatgpt.com)\]

That suggests a much more interesting approach than replacing Exile's landscape engine outright.

## 3\. A procedural world with a modification overlay

Keep the original concept of generating terrain on demand, but introduce a sparse collection of player modifications.

Terrain lookup

**get\_tile(x, y)**

Look up the requested coordinate

**Modification overlay**

Dug or placed blocks

**Procedural generator**

Original world terrain

Overlay wins when present

**Final tile for rendering and collisions**

The complication is that a heavily excavated or constructed world eventually makes a sparse overlay inefficient. You might use chunk-level bitmaps, with chunks allocated only when modified, or maintain a small hot cache with a compressed persistent representation.

For scale, a 256×256 world contains 65,536 cells\:

| Representation | Storage |
|--------|--------|
| 1 bit per tile | 8 KB |
| 2 bits per tile | 16 KB |
| 4 bits per tile | 32 KB |
| 8 bits per tile | 64 KB |

A one-byte tile identifier is attractive, but even on a BBC Master it would consume substantial memory. A procedural base plus sparse modifications is much more appealing.

## 4\. What I would simplify

I wouldn't attempt to reproduce Terraria's hundreds of enemies, extensive crafting trees, or elaborate boss progression. \[[Official Terraria Wiki](https://terraria.wiki.gg/wiki/Homepage?utm_source=chatgpt.com); [Guide:Game progression graph](https://terraria.wiki.gg/wiki/Guide%3AGame_progression_graph?utm_source=chatgpt.com)\]

Instead, I'd aim for something like this\:

- **World\:** One procedurally generated 256×256 map, with three or four underground environments.
- **Materials\:** Perhaps 8-12 terrain types, including soil, rock, ores, water and indestructible bedrock.
- **Crafting\:** Around 20 recipes, with simple combinations and a small number of crafting stations.
- **Tools\:** Pickaxe, weapon, digging explosives, building tool and perhaps a jetpack.
- **Enemies\:** Five or six creature types using Exile-like physical behaviours.
- **Progression\:** Three tiers of tools and equipment, plus two or three major encounters.
- **Construction\:** Place and remove blocks, create platforms, doors and basic shelters.
- **Persistence\:** Save the world seed, terrain modifications, inventory and progression flags.

I'd particularly preserve Terraria's **light and darkness** mechanic. Torches provide an excellent reason to gather resources and prepare before exploring deeper caves. On a four-colour BBC display, sophisticated dynamic lighting may be impractical, but simple tile-level illumination or visibility would be sufficient.

And I wouldn't sacrifice the physical interactions that make Exile distinctive. Explosions that propel objects, creatures that interact with terrain, and things that roll or bounce are worth more than another dozen crafting recipes.

## 5\. The first playable prototype

I'd build a very small vertical slice\:

1. Generate and scroll a terrain map.
2. Add a controllable player with gravity and collisions.
3. Allow digging and block placement.
4. Introduce two resources, wood and stone.
5. Craft a better pickaxe.
6. Add one enemy that guards a more valuable resource.

That would already test whether the exploration-excavation-crafting loop is enjoyable on the hardware.

One important design choice is whether to retain Exile's jetpack-based movement or adopt Terraria's platforming. The jetpack makes exploration easier, but risks making tunnels, platforms, ladders and player-built structures less important. I'd probably begin with walking and jumping, and make the jetpack a significant later upgrade.

## 6\. A potentially better game than a miniature Terraria

There's another possibility I find particularly appealing: rather than making a stripped-down Terraria, make a **Terraria-inspired successor to Exile**\.

That would give you a different emphasis\:

- Terraria contributes mining, construction, crafting and long-term progression.
- Exile contributes physics, emergent creature behaviour and environmental puzzles.
- The resulting game has a relatively small number of objects, but many ways for those objects to interact.

In other words, fewer *things*, but more *behaviours*\.

One of the great strengths of Exile was that its world felt like a system rather than a collection of scripted encounters. I'd want to retain that.

There is also a valuable technical resource worth investigating: [the recent bit-exact TypeScript reconstruction of Exile](https://bbcexile.com/?utm_source=chatgpt.com)\. It includes detailed examinations of the landscape generator, physics, rendering and creature AI. That's potentially an excellent reference for building a new engine rather than starting from the original assembly alone. \[[EXILE](https://bbcexile.com/?utm_source=chatgpt.com); [Why I rebuilt Exile, and how](https://bbcexile.com/how-exile-works/00-why-and-how/?utm_source=chatgpt.com)\]

**The question I'd settle next is the target hardware.** A 32 KB BBC Model B would demand an ingenious, very constrained implementation. A Master 128 with sideways RAM would give us rather more freedom, and a 65C02 Tube second processor could change the architecture considerably. In particular, it would influence whether the world simulation and renderer should run together on the host or be separated.

## Prompt:
18/10/2026, 17:28:50

So we can introduce levels or even parallel worlds which we can load an save from disc. That would increase the world size, but limit what we need to keep on hand at any moment. A but like the normal world and the nether in Minecraft.

## Response:
18/10/2026, 17:28:52 · gpt-6

Yes, and I think this is a particularly good fit for the BBC Micro. **Disc-backed worlds could make the *total* size of the game almost independent of the available RAM**, while keeping the active simulation small enough to be sophisticated.

The Minecraft analogy is useful, but I'd distinguish two ideas: *regions* within a world, and *parallel worlds* connected by portals. They can share almost all their implementation.

## A hierarchy of worlds

I'd consider three levels\:

| Level | Purpose | Storage |
|--------|--------|--------|
| **Universe** | Player progression, inventory, unlocked portals, world directory | Small global save |
| **World** | Independent environment with its own terrain, creatures, resources and rules | One or more disc files |
| **Region** | Portion of a world currently being explored | Loaded into RAM |

For example\:

**Universe**

Global player state and world connections

Surface

Forests, caves, villages

Underworld

Lava, rare ores, monsters

Frozen world

Ice, ruins, exotic materials

**Active region**

Terrain, creatures, objects and physics in RAM

The important distinction is that only the active region needs to be simulated. Everything else is essentially frozen, apart from any global processes you deliberately implement.

## Regions versus worlds

I would initially make world transitions explicit, rather than attempting seamless streaming.

For example, reaching a cave entrance, lift, teleportation device or portal could trigger a disc load. The game could even use an animation or a short transition screen to disguise the delay.

This avoids several nasty problems\:

- Creatures crossing unloaded region boundaries.
- Physics objects spanning two regions.
- Continuous terrain and collision queries across unloaded regions.
- Unpredictable disc access during gameplay.

It also makes each region independently testable.

Later, if desired, you could implement a cache of neighbouring regions, allowing some transitions without loading from disc.

## The really interesting possibility: world-specific physics

Minecraft's Nether isn't just another area with different graphics. Its environment changes the player's priorities.

Exile's physics engine gives you a wonderful opportunity to go further.

Imagine different worlds with different physical parameters\:

| World | Physical variation | Gameplay consequence |
|--------|--------|--------|
| Surface | Normal gravity, atmosphere | Familiar exploration and construction |
| Underworld | High temperature, hazardous gases | Protective equipment and resource management |
| Moon | Low gravity, no atmosphere | Long jumps, oxygen supplies, projectile trajectories |
| Ocean | Buoyancy and drag | Swimming, floating objects, underwater construction |
| Machine world | Low gravity, moving mechanisms | Mechanical puzzles and automated machinery |

Crucially, you wouldn't necessarily need five distinct engines. You'd have one engine with a small number of world-specific parameters and behaviours.

And the crafting system would give players reasons to visit different worlds: perhaps materials from the Underworld are required to build equipment that permits exploration of the Moon.

## Storage becomes an interesting design constraint

Suppose a world is divided into 32×32-tile regions.

At four bits per tile, each region requires just 512 bytes of uncompressed terrain, before modifications, creatures and other state.

A 256×256-tile world would have 64 regions, consuming 32 KB for its entire terrain map. Ten such worlds would require only 320 KB of terrain storage.

That is quite manageable on ADFS or a hard disc, although ordinary floppy capacity and access latency would influence how many worlds could coexist.

With procedural generation, the baseline terrain needn't even be stored. Only the world seed and modifications require persistence.

For modified regions, I'd favour a representation that can switch between sparse edits and a complete tile array as modification density increases.

## One design decision I'd make early

**Separate the world model from the active simulation.**

The world model answers questions such as\:

- What terrain exists at coordinate `(x, y)`?
- Has this tile been modified?
- What persistent objects belong to this region?
- What resources have been collected?
- Which portals connect this region to others?

The active simulation manages moving objects, physics, creature AI and player interactions.

On entering a region, persistent objects are instantiated as active simulation objects. On leaving, their persistent state is serialised.

This separation also creates an interesting opportunity for Beebium: the same world-generation and save-file code could be exercised and tested on a modern host, without running the entire game.

## One further thought: the disc as a universe

Rather than merely treating discs as storage devices, you could make them part of the game's fiction.

A disc might contain a whole new world, with its own seed, terrain generator parameters, resources and creatures. Players could exchange world discs, or generate new worlds.

You could even have a permanent *home world* where the player builds a base, and separate exploration worlds that can be visited, mined and eventually exhausted.

This makes a useful distinction between persistent construction and disposable exploration.

And it creates a rather attractive form of extensibility: **a game that can acquire entirely new worlds without modifying its executable.**

My inclination would be to start with explicit transitions between reasonably large regions, and introduce parallel worlds using exactly the same mechanism. You can subsequently make some transitions seamless without changing the underlying world model.

The next architectural question, I think, is whether the player should be allowed to modify *every* terrain tile, or whether the world should contain a mixture of destructible material and permanent geometry. That decision has enormous implications for both storage and gameplay.

## Prompt:
18/10/2026, 17:31:45

I think some indestructible materials are a good way to constrain storage. These could be like Minecraft bedrock or even water.

## Response:
18/10/2026, 17:31:46 · gpt-6

Yes. And I think the more interesting opportunity is to use **indestructible terrain as a deliberate part of world design**, rather than merely as an implementation concession.

In particular, I'd distinguish *immutable terrain* from *impassable terrain*\. Water is an excellent example: it can be traversed, but not excavated or collected in the way soil or stone can.

That gives us several useful terrain categories\:

| Terrain | Traversable | Modifiable | Behaviour |
|--------|--------|--------|--------|
| Air | Yes | Yes | Can receive placed blocks |
| Soil | No | Yes | Easily excavated |
| Stone | No | Yes | Requires better tools |
| Ore | No | Yes | Yields resources |
| Bedrock | No | No | Permanent boundaries |
| Water | Yes | No | Buoyancy, drag, perhaps oxygen depletion |
| Lava | Hazardous | No | Damage and perhaps heat |
| Portal | Yes | No | Transfers between worlds |

The clever part is that **immutable terrain doesn't need to be represented in the modification data at all**\. It can be generated procedurally, or defined by a compact, fixed map.

## Make modifiable terrain a scarce resource

Rather than allowing every solid tile to be destroyed, we could generate a world with a permanent geological skeleton.

Illustrative 32×16 region

Conceptual layout: the grey geological skeleton remains fixed, while soil and ore deposits can be excavated.

This has a useful consequence: the level designer can guarantee that certain structures, passages and boundaries will survive whatever the player does.

It also means that large areas of the map never require modification records.

## Water is particularly interesting

I'd strongly favour static water initially, rather than attempting Minecraft-style fluid simulation.

Water could simply be a property of particular coordinates, with physics applied to objects occupying them\:

- Reduced effective gravity through buoyancy.
- Velocity-dependent drag.
- Different movement controls.
- Oxygen consumption.
- Perhaps electrical or thermal interactions.

That's very much in the spirit of Exile: a small number of physical rules producing interesting emergent behaviour.

There's a subtle complication, though. If water occupies a fixed region and the player can dig into the surrounding soil, what happens when the excavation reaches the water?

I'd propose that water represents a **permanent volume**, rather than a fluid that flows into neighbouring empty tiles. It might look slightly artificial, but it makes the behaviour entirely deterministic and requires no fluid-state storage.

Alternatively, water could be represented by immutable rectangular or irregular regions, with an invisible boundary defining the extent of each body of water.

## Constrain modification capacity explicitly

We could go further and give each region a fixed budget for modifications.

For example, a 32×32 region could have\:

- 128 bytes for a sparse modification bitmap.
- 128 bytes for new tile values or compact change records.
- A separate small allowance for persistent objects.

That establishes a strict upper bound on storage, but we'd need a sensible policy when the budget is exhausted. Simply refusing to dig would be unpleasant.

A better solution might be to design regions with relatively few modifiable cells, so that **the worst-case storage requirement is known in advance**\.

If a region contains only 128 mutable cells, and each can occupy one of four states, all possible modifications require just 32 bytes at two bits per cell, provided the mutable cells have a deterministic indexing scheme.

That's a very attractive representation.

## An alternative: immutable geometry, mutable contents

Another possibility is to take inspiration from Exile's object system and make most of the environment immutable, but treat resources as removable objects embedded in the landscape.

For example, a cave wall might be permanent, while ore deposits attached to it can be mined. Trees, crystals, machinery and other objects could be removed, collected or replaced.

This sacrifices some of Terraria's free-form excavation, but preserves the discovery, collection and crafting loop while dramatically reducing the amount of mutable terrain.

I wouldn't go that far initially, because **digging tunnels and creating new routes is such a central part of Terraria's appeal**\.

The compromise I'd favour is a permanent bedrock skeleton interspersed with substantial pockets of destructible material. The player can reshape those pockets extensively, but cannot fundamentally destroy the world's topology.

And there's an interesting design benefit: permanent geological structures make it possible to create environmental puzzles that remain solvable even after extensive player excavation.

One question worth exploring next is whether construction should be allowed anywhere in empty space, or only at predefined buildable locations. Unrestricted construction, rather than excavation, might turn out to be the larger storage problem.



**Stratagem** is the name we'll use. It's growing on me. It's a particularly satisfying name because the wordplay works on several levels\:

- **Strata** — geological layers, excavation and underground exploration.
- **Gem** — precious minerals to discover, mine and collect.
- **Stratagem** — an ingenious plan or scheme, suggesting puzzles, tactics and inventive use of the physics engine.

And unlike *Exterra*, it stands entirely on its own as a name, without depending on the player recognising either *Exile* or *Terraria*\.

It also sounds convincingly like a lost Acornsoft title from 1987. I can imagine **STRATAGEM** in large lettering on a BBC Micro game box.

There's even a nice opportunity to make the pun central to the gameplay: gems could be more than collectibles. Different gems might be essential ingredients for crafting, activating portals, or unlocking new worlds.

One reservation: *stratagem* is an established word, and there are already games and other products using it, so we'd need to check for trademark conflicts and repository availability before committing.

Between the two, I'd now favour **Stratagem** for the game and `stratagem` for the repository. It's clever without being laboured, and the geological meaning makes it more specific to the actual gameplay.

The only thing I wouldn't do is spell it **StrataGem**\. The pun is much better when the reader discovers it for themselves.

## Prompt:
18/10/2026, 17:48:54

Stratagem it is.

## Response:
18/10/2026, 17:48:55 · gpt-6

**Stratagem** it is\!

A fine name for a BBC Micro game: geology, gems, ingenuity, and a pleasingly understated pun.

For the repository description\:

*Stratagem — A Terraria-inspired mining, crafting and exploration game with Exile-style physics for the BBC Micro.*

`stratagem` is a good working repository name, subject to availability and trademark checks.

Now we can get on with the prototype.
