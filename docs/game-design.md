# Stratagem game design

The working design, distilled from `concept.md` (the original concept
discussion) and later decisions. `architecture.md` covers how it is built.

Stratagem: a Terraria-inspired mining, crafting and exploration game with
Exile-style physics for the BBC Micro. It is not a miniature Terraria but a
Terraria-inspired successor to Exile: **fewer things, more behaviours**. The
world should feel like a system rather than a set of scripted encounters.

## The core loop

Explore to find resources; use resources to make tools; better tools reach
places that were inaccessible or too dangerous; those places hold better
resources. The six systems, in priority order:

| System | Notes |
|---|---|
| Exploration | Caves, resources, secrets, creatures, environments |
| Terrain modification | Digging, tunnelling, placing blocks, shelters |
| Resource gathering | Mining, collecting, looting |
| Crafting and equipment | About 20 recipes, a few stations, three tool tiers |
| Combat and progression | Five or six Exile-like creature types, two or three major encounters |
| World simulation | Selective: light and darkness, static water, hazards |

Exile's physics are worth more than another dozen recipes: explosions that
propel objects, creatures that interact with terrain, things that roll and
bounce.

## Terrain

Tile-based terrain with Exile-style physics for moving objects and
creatures. A permanent geological skeleton of immutable terrain, with
substantial pockets of destructible material: the player can reshape the
pockets extensively but cannot destroy the world's topology. This keeps
puzzles solvable whatever the player digs, and immutable tiles never need
modification records. It also bounds the storage: changed chunks are kept
whole (128 bytes for 8 x 8 tiles), and the host's spare 32K holds 255 of the
world's 1,024, so a world whose skeleton takes up much of it can have all
its pockets changed (2026-10-21; packing chunks is the next step, if
needed).

| Terrain | Traversable | Modifiable | Behaviour |
|---|---|---|---|
| Air | yes | yes | can receive placed blocks |
| Soil | no | yes | easily excavated |
| Stone | no | yes | needs better tools |
| Ore, gems | no | yes | yield resources |
| Bedrock | no | no | permanent boundaries |
| Water | yes | no | buoyancy, drag, perhaps oxygen |
| Lava | hazardous | no | damage, perhaps heat |
| Portal | yes | no | transfers between worlds |

Water is a permanent, static volume, not a simulated fluid: digging next to
it does not make it flow. Gems may be crafting ingredients, portal keys or
ways to unlock worlds.

Open question: whether construction is allowed anywhere in empty space or
only at buildable locations. Unrestricted construction may be the larger
storage problem.

## Worlds

| Level | Purpose | Storage |
|---|---|---|
| Universe | Player progression, inventory, unlocked portals, world directory | small global save |
| World | A 256 x 256 environment with its own seed, terrain, resources and rules | disc files: seed plus modifications |
| Active area | The part being explored and simulated | RAM |

Transitions between worlds are explicit (a portal, a lift, a cave mouth)
and may load from disc behind a transition screen, rather than streaming
seamlessly. This avoids creatures and physics spanning unloaded areas and
unpredictable disc access during play. A permanent home world for building
a base can sit alongside exploration worlds.

Worlds can differ in a few physical parameters of one engine: gravity,
atmosphere, buoyancy, drag, temperature. For example, a surface world, an
underworld (heat, gases), a moon (low gravity, no air) and an ocean
(buoyancy). Crafting gives reasons to travel between them.

## Player

Walking and jumping first. A jetpack is a significant later upgrade, so that
tunnels, platforms, ladders and player-built structures matter. Light and
darkness, with torches as a reason to prepare before going deeper, done as
simple tile-level illumination or visibility.

## First playable prototype (vertical slice)

1. Generate and scroll a terrain map.
2. A controllable player with gravity and collisions.
3. Digging and block placement.
4. Two resources, wood and stone.
5. Craft a better pickaxe.
6. One enemy guarding a more valuable resource.

## References

- `concept.md`: the original concept discussion.
- [bbcexile.com](https://bbcexile.com/): a bit-exact TypeScript
  reconstruction of Exile with articles on its landscape generation,
  graphics, physics and creature AI. A useful companion to the Level 7
  disassemblies.
