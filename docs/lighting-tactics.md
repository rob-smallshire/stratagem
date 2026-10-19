# Stratagem Lighting

# Stratagem: Lighting Model and Rendering Design

The objective is to give Stratagem convincing Terraria-style lighting, particularly underground, using algorithms that are computationally inexpensive, visually attractive, and compatible with a tile-based world and continuous player movement.

The guiding principle is\:

**Lighting should look plausible, rather than being physically accurate.**

We can separate the problem into three largely independent concerns\:

1. **Light sources\:** Where illumination originates, including sunlight, torches, glowing materials and the player.
2. **Light propagation\:** How illumination spreads through the world, attenuates with distance, and interacts with terrain.
3. **Light rendering\:** How a tile's illumination level affects its appearance on screen.

This separation allows us to experiment with different propagation algorithms without changing the renderer, or different rendering techniques without changing the lighting model.

## 1\. Representing illumination

Start with a scalar illumination value per tile, perhaps in the range 0–15.

| Level | Interpretation | Approximate appearance |
|--------|--------|--------|
| 15 | Fully illuminated | Original tile colours |
| 12 | Bright | Slight dithering |
| 8 | Moderate | Half the coloured pixels |
| 4 | Dim | Mostly black |
| 1 | Barely visible | Occasional coloured pixels |
| 0 | Darkness | Entirely black |

Four bits per tile would be sufficient. An 8-bit value might be more convenient computationally, with quantisation occurring during rendering.

Crucially, the illumination field is independent of the underlying tile graphics. Rock, soil, vegetation and constructed materials all receive the same illumination treatment.

## 2\. Rendering illumination using black dithering

The BBC Micro's limited physical colour palette makes conventional colour darkening unattractive. Instead, we can simulate decreasing brightness by replacing progressively more coloured pixels with black.

Equivalently, the renderer can simply omit coloured pixels according to a dither mask.

This preserves the original palette and gives us many apparent brightness levels without requiring additional physical colours.

### Ordered dithering

A 4×4 Bayer matrix is a particularly useful starting point\:

$$
B=\begin{bmatrix}
0&8&2&10\\
12&4&14&6\\
3&11&1&9\\
15&7&13&5
\end{bmatrix}
$$

For illumination $L$ between 0 and 16, retain a coloured pixel when\:

$$
B(x\bmod4,y\bmod4)<L
$$

Otherwise render black.

Progressive illumination of a coloured tile

The 4×4 matrix gives 17 possible coverage levels, including complete darkness and full brightness.

An 8×8 matrix would give finer gradations, but its larger spatial pattern may be more noticeable at low resolutions.

### Implementation considerations

The dither mask should be integrated into the tile renderer. A pixel is rendered in its normal colour if the mask permits it, or black otherwise.

Several optimisations are possible\:

- Precompute masks for each illumination level.
- Precompute illuminated tile variants if memory permits.
- Use bytewise masks and logical operations rather than processing individual pixels.
- Exploit the BBC Micro's planar-within-byte pixel encoding when combining tile data and masks.

For MODE 2, care is needed because each byte contains two interleaved 4-bit logical pixel values. A precomputed mask can nevertheless be used to clear the bits corresponding to selected pixels.

**One subtle issue is dither alignment.** The pattern should ideally remain stable relative to world coordinates, not move across the tiles as the camera scrolls. Otherwise, the pattern may appear to shimmer or crawl.

A further choice is whether illumination is uniform across an entire tile or interpolated between neighbouring tile values. I'd begin with uniform illumination. The slight blockiness may actually suit the visual style.

---

## 3\. Local light sources: torches and the player

The simplest approach is to give each light source a finite radius and a precomputed illumination kernel.

A kernel is a small array describing how much light reaches each relative tile position.

For example, a torch might have a radius of six tiles.

### Radial light kernels

A simple radial falloff is\:

$$
L(x,y)=\max\left(0,L_{\max}-k\sqrt{x^2+y^2}\right)
$$

There is no reason to calculate square roots at runtime. Generate the kernel offline and store its integer values.

Example 13×13 torch kernel

Illustrative radial illumination kernel. Values are quantised to 0–15; this diagram does not account for walls.

The kernel can be applied by taking the maximum of the existing illumination and the kernel value\:

$$
L_{\text{new}}(x,y)=\max(L_{\text{old}}(x,y),K(x-x_s,y-y_s))
$$

This is very cheap, but there's an important limitation: **a radial kernel illuminates through walls**\.

There are several ways to address that.

## 4\. Terrain-aware light propagation

The alternative is to propagate illumination through neighbouring tiles, with attenuation determined by distance and material.

For example\:

| Material | Attenuation |
|--------|--------|
| Air | 1 |
| Water | 2 |
| Glass or translucent material | 2 |
| Soil | Blocks |
| Rock | Blocks |

These are illustrative gameplay values, not physical measurements.

A simple four-neighbour propagation rule is\:

$$
L(x,y)=\max\left(
S(x,y),
L(x-1,y)-a,
L(x+1,y)-a,
L(x,y-1)-a,
L(x,y+1)-a
\right)
$$

where $S$ is the locally emitted illumination and $a$ is the attenuation cost of entering the tile. Values are clamped to zero.

This is a discrete relaxation problem: repeatedly update tiles until illumination stabilises.

### Four-neighbour flood fill

The most straightforward algorithm propagates light north, south, east and west.

Advantages include simplicity, low memory requirements and straightforward implementation.

Its principal drawback is that distance is measured in Manhattan geometry, producing diamond-shaped illumination around isolated sources.

### Eight-neighbour propagation

Including diagonal neighbours produces rounder light pools.

Diagonal propagation can use a slightly greater attenuation than cardinal propagation, although integer quantisation makes the exact choice important.

There is a trade-off: allowing diagonal propagation can cause light to leak through the corners of otherwise opaque walls. We can prevent that by checking the two orthogonally adjacent tiles before allowing diagonal transmission.

### Iterative directional sweeps

An alternative to a queue-based flood fill is to sweep repeatedly over the illumination buffer.

For example\:

1. Top-left to bottom-right.
2. Bottom-right to top-left.
3. Repeat if necessary.

Each tile updates its illumination from its neighbours.

This requires no flood-fill queue, and accesses memory sequentially.

However, two sweeps aren't guaranteed to produce the final correct field. Light travelling around complicated obstacles may require additional passes.

For Stratagem, that may be acceptable. We could use a fixed number of sweeps and accept some approximation.

One important implementation detail: **when a torch is removed, or a wall is constructed, old illumination must be cleared or invalidated before recalculation**\. A max-only propagation algorithm cannot remove previously accumulated light.

---

## 5\. Combining kernels and terrain propagation

I think a hybrid approach deserves particular attention.

A radial kernel gives us an attractive, rounded falloff. Terrain propagation gives us occlusion and illumination around corners.

There are several possible hybrids.

**Option A: Kernel with line-of-sight tests.** For each tile in the kernel, determine whether a wall blocks the path to the source. This gives attractive shadows, but individual visibility tests can be expensive.

**Option B: Propagation with radial distance limits.** Use a flood fill to determine which tiles are reachable by light, but use the radial kernel to determine brightness. This is cheap, although a light ray may effectively travel around a wall without losing the additional brightness expected from the longer route.

**Option C: Distance-cost propagation.** Propagate an integer distance or attenuation cost through the terrain. Convert that cost to brightness using a lookup table. This naturally darkens passages around corners.

Of these, **Option C is probably the strongest general-purpose candidate**\.

We can tune the falloff table independently of the propagation algorithm. Light can remain bright near its source, then fall off rapidly near the edge of its range.

The resulting illumination needn't be perfectly circular. Some irregularity may actually improve the cave atmosphere.

---

## 6\. Daylight from above

Sunlight deserves separate treatment from local light sources.

A torch emits from a point. Sunlight effectively arrives from above across the entire surface.

A simple approach is to perform a vertical pass through the world.

For each column\:

1. Start with full daylight above the surface.
2. Propagate downward through air.
3. Stop or attenuate sharply when encountering solid terrain.
4. Allow sunlight to enter shafts and cave entrances.
5. Spread the resulting illumination laterally into adjacent spaces.

The vertical pass can be exceptionally cheap.

### Direct sunlight versus ambient skylight

I'd distinguish two components\:

**Direct skylight** travels vertically down open columns, potentially maintaining high brightness over considerable distances.

**Diffuse skylight** spreads sideways from those columns, losing intensity with distance.

This is important because otherwise a deep, narrow shaft becomes dark simply because it's deep, even though it has an unobstructed opening to the sky.

Conceptual sunlight propagation

```svg
<svg viewBox="0 0 320 214" width="100%" xmlns="http://www.w3.org/2000/svg"><rect width="320" height="214" fill="#171e30" /><rect width="320" height="37" fill="#6088b2" /><g stroke="#f8df86" stroke-width="2" opacity=".8"><path d="M35 2 V38 M75 2 V38 M115 2 V38 M155 2 V38 M195 2 V38 M235 2 V38 M275 2 V38" /></g><path d="M0 37 H132 V150 H188 V37 H320 V214 H0Z" fill="#615343" /><path d="M132 37 V150 H188 V37" fill="#b6a25b" opacity=".55" /><path d="M133 150 H187 V177 H235 V195 H85 V177 H133Z" fill="#1d2226" /><path d="M145 150 H175 V175 H219 V185 H101 V175 H145Z" fill="#86784c" opacity=".48" /><g stroke="#f6dd86" stroke-width="2" stroke-dasharray="5 5" opacity=".85"><path d="M145 40 V165 M160 40 V165 M175 40 V165" /></g><g fill="#fff" font-size="10"><text x="8" y="27">Daylight</text><text x="197" y="63">Opaque rock</text><text x="196" y="163">Diffuse light</text></g><path d="M181 166 L194 166" stroke="#fff" stroke-width="1" /></svg>
```

Direct skylight descends through an open shaft; diffuse light spills sideways into the cave.

For a 256×256 world, we could even maintain a small amount of information about which columns have an unobstructed route to the sky.

When a player excavates a shaft, this information is updated, potentially illuminating a previously dark cavern.

That is precisely the sort of interaction that would make digging feel consequential.

A complication is overhangs and irregular cave entrances. A vertical-only sunlight model won't illuminate areas beneath an overhang very naturally. The lateral propagation pass helps substantially.

## 7\. Combining multiple light sources

The simplest composition rule is maximum brightness\:

$$
L(x,y)=\max(L_{\text{sun}},L_{\text{torch1}},L_{\text{torch2}},\ldots)
$$

This is cheap and avoids overexposure.

However, two torches placed close together won't make an area brighter than one torch.

An alternative is additive lighting with saturation\:

$$
L(x,y)=\min(15,\sum_i L_i(x,y))
$$

That produces more convincing overlap but requires more bookkeeping, particularly when removing lights.

A compromise is to use maximum illumination initially. If overlapping torches look unnatural, introduce a limited additive contribution later.

For example, the strongest light source could dominate, with a small contribution from the second strongest.

I'd postpone that complexity until visual testing demonstrates a need.

## 8\. The player's light source

The player should probably have a small amount of intrinsic illumination, even without a torch.

This needn't be justified physically. It's a gameplay convenience that prevents the player from becoming completely invisible underground.

We could distinguish\:

- **Ambient player visibility\:** A weak light extending one or two tiles.
- **Carried torch\:** A stronger light extending perhaps six tiles.
- **Placed torch\:** Similar illumination, but fixed in world coordinates.
- **Special equipment\:** Larger radius, different falloff, or other effects.

Since the player moves continuously rather than on the tile grid, there's a choice about how the light follows them.

The simplest approach is to anchor the light source to the player's current tile. The light field updates only when the player crosses a tile boundary.

This might cause visible stepping in the illumination, particularly with large tiles.

A refinement is to shift or interpolate the kernel according to the player's sub-tile position, but I'd only implement that if the stepping is objectionable.

---

## 9\. Update strategy

Lighting doesn't need to be recalculated every video frame.

We can distinguish several kinds of changes.

| Event | Required update |
|--------|--------|
| Player moves within same tile | Usually none |
| Player enters another tile | Update local light |
| Torch placed or removed | Update affected region |
| Tile excavated | Update local occlusion and possibly sunlight |
| Tile constructed | Update local occlusion |
| Day/night transition | Update skylight intensity |
| Camera scrolls | Calculate newly visible lighting |

The illumination field can be calculated for the visible region plus a margin large enough to accommodate light sources just outside the screen.

For persistent torches, we'd also need to consider sources outside that margin whose light can reach the viewport.

### Incremental versus full recalculation

Initially, I'd favour **recalculating a modest local illumination buffer from scratch** whenever necessary.

It's simpler, easier to test, and avoids complicated invalidation logic.

If that proves too expensive, incremental updates can be introduced later.

This is especially attractive because lighting is derived state. It doesn't need to be saved to disc: the terrain modifications and placed light sources are sufficient to reconstruct it.

---

## 10\. A practical first implementation

I'd propose the following initial configuration.

| Property | Initial choice |
|--------|--------|
| Illumination resolution | One value per tile |
| Illumination range | 0–15 |
| Rendering | 4×4 ordered black dithering |
| Player light | Radius 2–3 tiles |
| Torch light | Radius 6–8 tiles |
| Propagation | Four-neighbour attenuation, possibly eight-neighbour later |
| Occlusion | Solid tiles block light |
| Sunlight | Vertical direct pass plus lateral diffusion |
| Multiple lights | Maximum illumination |
| Update frequency | On tile changes and light movement |
| Persistence | Save light sources, not illumination |

This is intentionally modest. Most of the visual impact should come from the combination of darkness, local illumination and terrain occlusion, rather than sophisticated light physics.

## 11\. Questions worth exploring experimentally

I think four questions will determine the final design.

**How many brightness levels are visually useful?** A 4×4 Bayer matrix supports 17 levels, but perhaps only eight are perceptually distinguishable at the game's tile size. We should test that on actual BBC Micro output.

**How much should solid terrain block light?** Completely opaque rock is simple, but slight illumination of the first solid tile adjacent to a cave may make the walls easier to read. A useful rule could be to illuminate the exposed surface of a solid tile without allowing light to propagate through it.

**How should daylight behave underground?** Direct vertical skylight plus diffuse propagation seems promising, but the balance between the two will strongly affect the atmosphere.

**How should moving lights interact with dithering?** A tile-level light field may visibly jump when the player crosses tile boundaries. Whether that matters depends on tile dimensions, player speed and the renderer's existing behaviour.

---

## My preferred direction

I'd prototype three things in order\:

1. **Dithered illumination in the tile renderer**, initially with manually assigned brightness levels. This establishes whether the visual technique works.
2. **Precomputed radial kernels for the player and torches**, initially ignoring terrain occlusion. This establishes the appearance and performance of local lighting.
3. **Terrain-aware propagation and sunlight**, using a simple attenuation model and a separate vertical skylight pass.

This sequence keeps the renderer independent of the eventual lighting algorithm and makes it easy to compare alternatives.

The particularly appealing thing about Stratagem is that the terrain is mutable. Illumination can therefore become part of the reward for excavation: opening a passage, breaking through into a cavern, or digging a shaft to the surface can transform the appearance of an entire area.

**The most important effect isn't that a torch makes nearby tiles brighter. It's that darkness makes the unexplored world mysterious, and the player's actions progressively reveal it.**



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)