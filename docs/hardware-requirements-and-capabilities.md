# Stratagem Game Progress

# Stratagem: Hardware Platform and Storage Architecture

I think the discussions so far point towards a rather distinctive ambition for Stratagem: **a new BBC Micro game designed to exploit the capabilities of a fully expanded system, while remaining a well-behaved application of the BBC Micro operating system.**

That's an interesting combination. Historically, games tended to target the lowest common denominator and commandeer the machine. Stratagem can take the opposite approach: demand more hardware, but respect the operating system and its abstractions.

There are several architectural decisions worth separating, because they have different implications for performance, compatibility and implementation complexity.

## 1\. The hardware specification

Here's my understanding of the intended target.

| Component | Requirement or direction |
|--------|--------|
| Host CPU | Standard 2 MHz BBC Micro 6502 |
| Host main RAM | 32 KB |
| Shadow RAM | 32 KB, required |
| Sideways RAM | 64 KB, required |
| Filing-system reservation | 16 KB sideways RAM |
| Second processor | 3 or 4 MHz 65C02, proposed |
| Parasite RAM | 64 KB |
| Graphics | 16 logical colours, 8 physical colours |
| Operating system | Resident MOS, retained and usable |
| Filing system | Existing MOS-compatible filing system |
| Storage | Floppy, hard disc or Econet file server |
| World size | 256 × 256 tiles per world |
| World structure | Fixed, designed progression through multiple worlds |

With the parasite, that's nominally **192 KB of physical RAM**, of which 32 KB is shadow display RAM and 16 KB of sideways RAM is reserved for filing-system use.

This is emphatically not a conventional BBC Micro configuration. Nor should it be.

### The memory is not homogeneous

The important constraint isn't total capacity but where memory resides and how it can be accessed.

- Main RAM is directly accessible by the host CPU, subject to MOS workspace and other reservations.
- Shadow RAM holds the display without consuming the equivalent portion of ordinary main RAM, assuming the target machine provides the required access arrangements.
- Sideways RAM is bank-switched in 16 KB windows.
- Parasite RAM is a separate address space, accessible through Tube communication rather than shared-memory operations.

So the eventual architecture must be designed around **locality of data and ownership of responsibilities**, not just a nominal 192 KB budget.

I'd also be careful to distinguish 64 KB of physical parasite RAM from the memory actually available to a running program. The Tube environment, program code, stack, vectors and workspace all need room.

## 2\. The second processor: an architectural choice

I think the case for requiring a 65C02 second processor is stronger than simply accelerating the physics.

It gives Stratagem two independently executing CPUs with relatively natural responsibilities.

**Host · 2 MHz**

Tile and sprite rendering

Display management

Sound and input

MOS and filing-system services

Storage I/O and cache staging

**Parasite · 3–4 MHz**

World generation and modifications

Continuous physics and collision

Mining and construction

Game rules and entities

Simulation-side caches

Tube: input, state changes, rendering and storage messages

The strongest argument for this split is concurrency. While the parasite advances the simulation, the host can render the previous state. That gives the machine more useful work per unit of elapsed time than merely moving the whole game to a faster processor.

### But there is a complication

The host currently runs everything, and that working implementation is valuable.

Moving the simulation to the parasite introduces a communication boundary into operations that are currently local. Collision detection, for example, must not require a Tube round trip for every tile lookup.

I would therefore adopt one fundamental rule\:

**The parasite must own enough terrain state to perform physics and collision detection entirely locally.**

The host can maintain a separate rendering cache. Duplication of a modest amount of terrain data is preferable to constant cross-processor communication.

That also means we should resist designing a protocol that transfers every intermediate operation. Transfer completed state changes and batches of updates instead.

### Is the parasite actually mandatory?

My inclination is to make it the intended target, but not immediately make it a prerequisite for development.

The existing host-only implementation is a valuable reference. It can provide regression tests for the migrated physics and world-generation algorithms.

However, I wouldn't commit to maintaining two production architectures indefinitely. Supporting both could easily become a burden that constrains the very capabilities you're trying to unlock.

A single Tube-based architecture with a clear minimum hardware specification seems more consistent with the project's goals.

## 3\. Retaining MOS and the filing system

This is perhaps the most unusual aspect of the design.

Most BBC Micro games assume ownership of the computer. Stratagem instead intends to coexist with the MOS, use its filing-system abstraction and preserve the user's choice of storage.

That gives us a potentially attractive compatibility matrix.

| Filing system | Storage medium | Principal concern |
|--------|--------|--------|
| DFS | Floppy disc | Capacity, directory limits, seek latency |
| ADFS | Floppy or hard disc | Disc latency and buffering |
| SCSI filing system | Hard disc or solid-state storage | Implementation-specific compatibility |
| ANFS | Econet file server | Network latency and server availability |
| Other MOS-compatible systems | Various | Correct use of documented OS interfaces |

The central design principle should be that **Stratagem depends on filing-system capabilities, not particular filing-system implementations**\.

In practice, that means using the standard MOS interfaces where possible\:

- `OSFILE` for file-level operations.
- `OSFIND` for opening and closing files.
- `OSGBPB` for block transfers.
- `OSARGS` for file positioning and metadata where supported.
- `OSBYTE` and `OSWORD` for appropriate operating-system services.

I would avoid direct disc-controller access entirely.

### An important distinction: preserving MOS versus preserving all MOS behaviour

A game can retain MOS and still be rather unfriendly to the operating environment.

For example, it might overwrite workspace expected by a filing system, assume a particular sideways ROM arrangement, interfere with interrupt handling, or make assumptions about Tube host code.

I'd aim for something stronger than merely keeping the MOS ROM present\:

**Stratagem should preserve the operating-system contracts on which the configured filing system depends.**

That means being disciplined about memory ownership, vectors, interrupts, sideways RAM and the Tube host environment.

It also suggests that supporting a particular machine configuration should be a conscious compatibility decision, rather than an accident of which memory locations happen to be free.

### The Tube environment needs investigation

There's an architectural subtlety here that deserves attention before committing to the host/parasite split.

Conventional Tube applications execute on the parasite and use host-side services to access the MOS. But Stratagem also wants substantial custom host-side functionality for rendering, input and storage scheduling.

Those responsibilities must coexist.

We have at least two options\:

**Option A: Retain the conventional Tube host environment.** Extend it with game-specific communication and rendering functionality while preserving its operating-system services.

**Option B: Implement a custom host runtime.** Own the host-side Tube protocol and explicitly provide the MOS services required by the parasite.

Option A is attractive for compatibility, but we shouldn't assume it will be straightforward to integrate an elaborate renderer into the existing Tube host machinery.

Option B offers control but entails considerably more implementation and testing.

I would investigate this early, ideally with a minimal demonstration that runs a parasite program, draws through a host-side renderer and performs ordinary filing-system operations.

That experiment could eliminate a great deal of architectural uncertainty.

## 4\. Floppy support as a first-class requirement

Supporting floppies is a particularly interesting decision because it prevents us from assuming that storage is fast, plentiful or randomly accessible at low cost.

But it doesn't necessarily mean that floppy limitations should constrain the whole game.

The key insight from our earlier discussion is that **the game can control when it needs storage**, rather than requiring uniformly low-latency access throughout play.

### The dual-drive model

```svg
<svg viewBox="0 0 130 120" width="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="5" width="90" height="108" rx="5" fill="#34485c" stroke="#172635" stroke-width="2" /><rect x="34" y="11" width="62" height="34" rx="3" fill="#e7e8db" /><rect x="48" y="15" width="34" height="26" rx="2" fill="#6c7883" /><circle cx="65" cy="28" r="8" fill="#d7d8d0" /><rect x="34" y="55" width="62" height="48" rx="3" fill="#e9bb67" /><text x="65" y="75" text-anchor="middle" font-size="10" font-weight="bold" fill="#392b17">STRATAGEM</text><text x="65" y="89" text-anchor="middle" font-size="9" fill="#392b17">WORLD DATA</text></svg>
```

**Drive 0 · Game disc**

Write-protected

```svg
<svg viewBox="0 0 130 120" width="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="5" width="90" height="108" rx="5" fill="#485b54" stroke="#23352d" stroke-width="2" /><rect x="34" y="11" width="62" height="34" rx="3" fill="#e7e8db" /><rect x="48" y="15" width="34" height="26" rx="2" fill="#6c7883" /><circle cx="65" cy="28" r="8" fill="#d7d8d0" /><rect x="34" y="55" width="62" height="48" rx="3" fill="#9fd2a5" /><text x="65" y="75" text-anchor="middle" font-size="10" font-weight="bold" fill="#25442e">STRATAGEM</text><text x="65" y="89" text-anchor="middle" font-size="9" fill="#25442e">PLAYER DATA</text></svg>
```

**Drive 1 · Player disc**

Writable

The game disc contains the immutable world definitions, generation parameters, assets and other designed content.

The player disc contains the player's modifications, inventory, progression, discoveries and constructed objects.

This is a clean separation, and it could extend naturally to installations on hard discs or file servers.

However, I wouldn't bake drive numbers into the storage architecture. They should be configuration details. ADFS, DFS and Econet have different naming and volume conventions.

### DFS capacity is a serious design constraint

A conventional 80-track, double-sided, double-density DFS disc provides roughly 400 KB across two independently catalogued sides, each with its own catalogue and a maximum of 31 files.

That means a dual-drive system offers useful capacity, but not unlimited capacity.

For example, consider a modification record containing\:

- One byte for X coordinate.
- One byte for Y coordinate.
- One byte for replacement tile or material.

That's three bytes per modified tile, before indexes and metadata.

Illustrative modification storage

Modified tiles

> **Slider**
>
> Current value unavailable.
>
> **Range:** 0 to 65536
>
> **Step:** 256

Bytes per modification 

- 2
- 3
- 4
Current selection unavailable.

Raw storage

## KiB

Of a nominal 200 KiB side

## %

Raw modification records only, excluding catalogue, indexes, checkpoints and other player data. Two-byte records assume a suitable packed representation.

The important point is that a world may eventually become heavily modified. Sparse override records are excellent initially, but a dense representation can become more efficient.

For instance, if a world uses one byte per tile, a complete replacement map occupies 64 KB. That gives us a useful upper bound on tile-state storage for one world, before compression.

I would seriously consider **region-based storage with adaptive encoding**\: sparse overrides for lightly modified regions, and compressed dense snapshots for heavily modified ones.

A compact container file holding many regions would also avoid exhausting the DFS catalogue.

## 5\. Storage scheduling as a gameplay feature

This is where the earlier discussion arrived at something I think is genuinely distinctive.

Rather than treating filing-system latency as an implementation nuisance, Stratagem can be designed with natural opportunities for I/O.

| Opportunity | Gameplay explanation | Storage activity |
|--------|--------|--------|
| Player inactive for 10 seconds | Player pauses | Opportunistic dirty-data writeback |
| Cooking or eating | Energy replenishment | Save modifications, possibly prefetch |
| Sleeping | Rest and passage of time | Checkpoint and cache maintenance |
| World transition | Portal, lift, passage or teleporter | Save old world, load new world |
| Low cache capacity | Resource pressure | Controlled checkpoint or pause |

The common idea is **cooperative scheduling between the game and its storage system**\.

The game supplies opportunities for potentially blocking I/O. The storage subsystem decides what useful work to perform.

### An important refinement: durability versus performance

I'd distinguish three operations that we've sometimes conflated\:

1. **Writeback\:** Write dirty terrain data to storage.
2. **Checkpoint\:** Establish a consistent, recoverable saved state.
3. **Compaction\:** Reorganise saved data to reclaim space or improve future access.

These don't necessarily need to happen together.

For example, after ten seconds of inactivity, Stratagem might write pending modifications without performing a full checkpoint. Sleeping could establish a durable checkpoint, while a world transition might additionally perform compaction if necessary.

I'd also avoid assuming that every save can be made atomic through a single MOS call. On floppies, a power failure or interrupted write can leave partially updated data.

A robust format might use two checkpoint generations, sequence numbers and checksums, so that the previous valid checkpoint survives an interrupted update. The precise design will depend on capacity and write-amplification constraints.

## 6\. Fixed worlds and deliberate progression

The decision to use fixed, designed worlds simplifies storage considerably.

Each world is 256×256 tiles, generated from known parameters and supplemented with authored content. Only the player's modifications need persistent storage.

Unmineable geological barriers, portals and transport devices provide controlled transitions between worlds.

Illustrative world progression

```svg
<svg viewBox="0 0 330 215" width="100%" xmlns="http://www.w3.org/2000/svg"><g stroke="#9b9b9b" stroke-width="2.5" fill="none"><path d="M165 48 V73 H80 V95" /><path d="M165 73 H250 V95" /><path d="M80 131 V157 H165 V176" /><path d="M250 131 V157 H165" /></g><g font-size="11" text-anchor="middle"><rect x="100" y="10" width="130" height="38" rx="7" fill="#397b53" /><text x="165" y="26" fill="white" font-weight="bold">Surface world</text><text x="165" y="40" fill="white" font-size="9">Starting location</text><rect x="8" y="95" width="144" height="36" rx="7" fill="#9c7144" /><text x="80" y="117" fill="white">Underground caverns</text><rect x="178" y="95" width="144" height="36" rx="7" fill="#566b83" /><text x="250" y="117" fill="white">Distant highlands</text><rect x="100" y="176" width="130" height="35" rx="7" fill="#754b78" /><text x="165" y="197" fill="white">Deep world</text></g><g fill="#888" font-size="9"><text x="90" y="67">Shaft</text><text x="238" y="67">Portal</text><text x="165" y="151" text-anchor="middle">Unlocked passage</text></g></svg>
```

Conceptual connectivity, not a proposed final map.

This offers several technical advantages\:

- World transitions are predictable I/O boundaries.
- Assets can be organised into world-specific packages.
- Progression can control when expensive content must be loaded.
- Floppy-disc swaps can happen at meaningful transitions.
- The complete game can span multiple discs without requiring all content to be resident.

It also allows world content to be arranged on discs according to expected progression, reducing disc swapping.

One qualification: a fixed world graph doesn't necessarily imply fixed storage requirements. Players may revisit worlds repeatedly and modify them extensively, so the persistent-state system still needs to accommodate arbitrary player activity.

## 7\. A storage architecture I'd explore

I'd separate the game into four logical subsystems.

**World simulation**

Physics, mining, construction, entities and procedural generation. Operates entirely on resident state during active play.

**World cache**

Active terrain regions, modification overlays, dirty-state tracking and region residency.

**Persistence manager**

Checkpoints, journals, compaction, world loading, writeback policy and recovery.

**MOS storage adapter**

Standard filing-system calls, file handles, paths and transfer buffers.

The important separation is between the persistence manager, which understands Stratagem's data structures, and the storage adapter, which understands MOS file operations.

That should let us test persistence independently of real hardware.

It also provides an excellent opportunity for Beebium: the same game can be tested against emulated floppy, hard-disc and network storage, with different latency and failure characteristics.

## 8\. The questions I'd resolve next

I think there are five important areas of uncertainty, in roughly this order.

**1\. The Tube host architecture**

Can we preserve conventional Tube MOS services while running a substantial custom host-side graphics and I/O engine? This is the biggest architectural risk in the proposed multiprocessor design.

---

**2\. Actual memory ownership**

Which portions of host main RAM, shadow RAM and sideways RAM are available on each supported machine? In particular, how do we preserve filing-system workspace and the intended 16 KB sideways reservation?

---

**3\. The portable storage contract**

Which MOS filing-system operations and guarantees can we safely depend on across DFS, ADFS, SCSI implementations and Econet? In particular, file positioning, block transfers, error handling and naming conventions.

---

**4\. World modification storage**

What are the actual memory and disc requirements for realistic player activity? The existing prototype should provide useful measurements. Those will inform region size, compression, indexing and checkpoint strategy.

---

**5\. Storage latency budgets**

How much data can we transfer during a typical cooking, sleeping or world-transition pause on the slowest supported medium? Real measurements will be more useful than theoretical transfer rates.

## 9\. One further possibility: progressive exploitation of hardware

There's an interesting distinction between **minimum hardware requirements** and **the capabilities the game can exploit**\.

You've deliberately rejected the historical commercial requirement to support the base BBC Micro. That doesn't mean every supported configuration must have identical performance characteristics.

For example, the game could have one architectural design but adapt its caching behaviour to available resources.

A 3 MHz parasite could run the same simulation as a 4 MHz parasite, perhaps with a lower update rate in demanding circumstances. A hard disc could permit more aggressive prefetching than a floppy. A fast Econet server might support convenient frequent checkpoints.

But I would avoid introducing separate feature sets unless there's a compelling gameplay reason. A single game with different performance and loading characteristics is much easier to test and maintain.

## My suggested next step

Before designing the storage format in detail, I'd concentrate on a **small Tube-based architectural prototype**\.

It needn't implement Stratagem's full gameplay. It only needs to demonstrate that\:

1. The parasite can maintain a mutable tile world and run simulation independently.
2. The host can render it efficiently while maintaining the necessary MOS environment.
3. The two processors can exchange bounded, batched messages without compromising responsiveness.
4. The host can perform filing-system operations through the configured filing system, including while the parasite is running or deliberately paused.
5. The system can recover cleanly from a failed storage operation.

That experiment would test the most consequential assumption in the entire design.

After that, I'd benchmark persistence against actual DFS floppies, ADFS and Econet, using representative modification datasets.

**The overarching ambition is compelling: Stratagem should be a game that treats the BBC Micro as a capable, expandable, multiprocessor computer with an operating system—not as a 32 KB games console.**

That seems a much more interesting target for a new BBC Micro game than trying to reproduce the constraints under which commercial developers worked forty years ago.

## Prompt:
19/10/2026, 18:31:50

One correction. DFS does not support double-density. I think a 40 track single-sided drive is 100K, double-sided 200K and  80-track double-sided 400k. There were double-density file systems like Watford DDFS, but Acorn DFS wasn't among them. Still, if we do this right, there's no reason my Stratagem should not benefit from more capacious floppy file systems. I like the idea of software which can take advantage of the available hardware.

## Response:
19/10/2026, 18:31:54 · gpt-6

Quite right. I conflated the capacity of double-sided, double-density media with Acorn DFS's single-density format.

The correct capacities for standard Acorn DFS, using 256-byte sectors and 10 sectors per track, are\:

| Drive configuration | Capacity |
|--------|--------|
| 40-track, single-sided | 100 KB |
| 40-track, double-sided | 200 KB |
| 80-track, single-sided | 200 KB |
| 80-track, double-sided | 400 KB |

Each side has a separate DFS catalogue, so an 80-track double-sided disc is effectively two 200 KB volumes. Actual usable file space is slightly less because of the catalogues.

And your broader point suggests a design principle I'd explicitly adopt for Stratagem\:

**Require a capable baseline, but avoid imposing artificial ceilings on more capable configurations.**

That has several implications.

### 1\. Let the filing system determine storage capacity

Stratagem shouldn't have an internal assumption that a floppy holds 100 KB or 200 KB, or that a particular number of worlds fits on a disc.

Instead, its persistence layer should work with logical files and whatever capacity the filing system provides.

That could encompass Acorn DFS, Watford DDFS, ADFS, SCSI hard discs and Econet without separate game implementations.

The lowest-common-denominator constraints should apply to the *portable file format*, not necessarily to the amount of content a particular installation can hold.

### 2\. Separate compatibility from optimisation

I'd distinguish between a portable storage backend and optional optimisations.

For example\:

| Capability | Baseline behaviour | Enhanced behaviour |
|--------|--------|--------|
| Storage capacity | Multiple floppy volumes | Large volumes with fewer swaps |
| File access | Sequential block transfers | Larger caches and prefetching |
| Saving | Deliberate checkpoints | More frequent opportunistic saves |
| World loading | Explicit transitions | Potentially faster transitions |
| Game content | Core designed worlds | Additional world packages |
| Cache management | Conservative | Exploit additional available RAM |

Most importantly, these are variations in performance and convenience, not necessarily gameplay rules.

A player using a hard disc shouldn't have an easier game than somebody using floppies.

### 3\. Avoid unnecessary hardware detection

One subtle point: I wouldn't necessarily try to identify every filing system.

If Stratagem can perform its operations through standard MOS interfaces, it generally shouldn't care whether a file lives on DFS, DDFS, ADFS or an Econet server.

There may be reasons to discover specific capabilities, but I'd prefer testing or configuring those capabilities rather than maintaining a catalogue of filing-system identities.

For example, the player could configure whether to use a single storage volume, separate game and save volumes, or a multi-disc installation.

### 4\. Treat additional RAM similarly

The same philosophy applies to memory.

You have a deliberately high baseline: shadow RAM, sideways RAM and potentially a 65C02 second processor.

But if somebody has more sideways RAM than the minimum, it would be attractive to exploit it for additional asset caches, reducing disc access.

The complication is that sideways RAM isn't universally free for applications. It may contain filing systems, utilities or other resident software. Stratagem would need to discover and claim available banks without trampling existing software.

I would be cautious about treating a configured 64 KB sideways RAM expansion as four freely disposable banks unless the game has explicitly reserved them.

### 5\. A capability-oriented platform model

I think the right abstraction is a small set of capabilities rather than a list of supported machines.

For example\:

- Shadow screen available.
- Minimum game-owned sideways RAM available.
- Tube 65C02 available, with sufficient RAM.
- MOS-compatible filing system operational.
- Writable save volume available.
- Optional additional memory or storage capacity.

The game could check these at startup, report missing requirements and configure its caches accordingly.

This also suggests a pleasant deployment model: **the same Stratagem executable could run on a suitably expanded BBC B, B+ or Master, with the machine's available resources determining how efficiently it operates.**

There will be genuine machine-specific details to accommodate, particularly shadow-screen control and memory mapping, but those can be confined to a small hardware abstraction layer.

I think the most important design distinction emerging here is between *hardware requirements* and *hardware assumptions*\.

You're happy to require unusual hardware. What you don't want is software that unnecessarily assumes the rest of the system is no more capable than the minimum configuration.

That's a philosophy very much in keeping with the BBC Micro's original expansion architecture—and one that relatively few commercial games fully exploited.

## Prompt:
19/10/2026, 18:33:51

I think we can do a lot in a separate program loader to characterise the available hardware a condense it down to a sort of capability description that can be used by the game. Then the capability detection code doesn't need to use any space needed later by the game.

## Response:
19/10/2026, 18:33:53 · gpt-6

Yes. And I'd go a little further: **the loader could act as a hardware discovery, resource allocation and configuration stage**, leaving Stratagem itself with a compact description of the environment it has been given.

This is particularly attractive on the BBC Micro because some hardware detection routines are necessarily intrusive. Testing RAM banks, probing a Tube processor, or identifying shadow-screen arrangements may require temporary workspace, changes to memory mappings, or code that has no further use once the game starts.

There's no reason to keep any of that code resident.

## A three-stage startup

**Stage 1 — Loader and hardware discovery**

Identify host model, shadow RAM, sideways RAM banks, Tube processor, filing system and available memory. Run any intrusive probes before game state exists.

**Stage 2 — Resource allocation and configuration**

Reserve game-owned RAM banks, establish host/parasite memory layouts, select storage volumes and initialise the Tube environment. Produce a compact capability descriptor.

**Stage 3 — Stratagem runtime**

Load the game into its final memory locations, discard the loader and run using the supplied configuration. No repeated hardware probing.

## What belongs in the capability descriptor?

I'd favour a small, versioned binary structure rather than a collection of machine-specific flags scattered throughout the game.

Something along these lines\:

Illustrative capability descriptor

| Version and length | 2 bytes |
|--------|--------|
| Host hardware class | 1 byte |
| Feature flags | 2 bytes |
| Shadow RAM configuration | 1 byte |
| Available sideways RAM bank mask | 2 bytes |
| Allocated game RAM bank mask | 2 bytes |
| Parasite type and speed class | 2 bytes |
| Storage configuration | 2 bytes |
| Memory layout identifier | 1 byte |

About 15 bytes in this example, before any optional extension fields.

I'd distinguish between three categories of information.

**Detected capabilities\:** What hardware and operating-system services are actually available.

**Allocated resources\:** Which memory banks and other resources Stratagem is permitted to use.

**Selected policy\:** How the game should use those resources—for example, which volume contains player data, or how aggressively to cache world assets.

These aren't quite the same thing. A machine might have eight sideways RAM banks, but Stratagem may only be allocated three.

## A particularly useful refinement: capabilities, not identities

I'd try to avoid having the game ask questions like\:

`IF machine = MASTER THEN ...`

Instead, it should ask questions such as\:

`IF shadow_display_available THEN ...`

Machine identity can still matter in the hardware abstraction layer, but most of the game should operate on the resources actually available.

This becomes especially valuable if you're supporting unusual configurations: expanded BBC Bs, B+ machines, Masters, third-party RAM expansions, and different Tube implementations.

## The loader could also optimise the runtime

There's another possibility worth exploring: **selecting or patching specialised code during loading**\.

For example, the loader might choose between different routines for\:

- Shadow-screen access on different host machines.
- Sideways RAM banking.
- Tube communication.
- Memory copying and rendering.
- Available processor instructions.

Instead of repeatedly checking capabilities at runtime, Stratagem could use a small table of function addresses, or have the loader patch known call sites.

For performance-critical 6502 code, that could be worthwhile.

I'd favour selecting preassembled routines over extensive self-modifying code, but either is possible.

## Where the descriptor lives

This deserves some care.

The loader can disappear, but its descriptor must survive in a known location. It could reside in a reserved area of main RAM, or be passed directly to the parasite during startup.

I'd probably use **a small fixed-address bootstrap descriptor**, then copy its contents into the host and parasite's respective runtime configuration structures.

That way, neither processor needs to retain a dependency on the loader's memory layout.

One subtlety: the descriptor shouldn't contain pointers to temporary loader data. Anything it references must remain valid after the loader has been overwritten.

## One additional opportunity: preflight validation

The loader could establish that the machine is actually capable of running Stratagem *before* loading the full game.

For example\:

- Verify that shadow RAM is usable.
- Find sufficient free sideways RAM banks.
- Confirm the required 65C02 parasite and its memory.
- Check that the configured filing system can read the game data.
- Verify that a suitable writable player-data volume exists.
- Report any missing requirements using ordinary MOS text output.

This would produce a much better experience than crashing or corrupting memory when a requirement isn't met.

And because the loader can use conventional MOS output, error messages needn't consume precious graphics or font resources in the final game.

## The remaining subtlety: resource ownership

I'd make one distinction explicit: **discovering a resource is not necessarily the same as acquiring exclusive ownership of it**\.

Sideways RAM is the obvious example. A bank might be writable, but that doesn't automatically mean it's safe to overwrite.

Likewise, some memory belongs to MOS or the current filing system even if a simple RAM test suggests it exists.

The loader should establish a resource allocation that remains valid for the lifetime of the game, rather than merely reporting physical capabilities.

That suggests a compact startup contract\:

> The loader guarantees that every resource described as allocated is available for Stratagem's exclusive use until the game exits.

This is a much stronger and more useful promise than simply reporting what hardware was detected.

And it leads to an architectural principle I particularly like: **the loader understands the machine; the game understands the capabilities.**

For Stratagem, that could be the foundation of a surprisingly portable runtime across the entire family of expanded BBC Micro systems.



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)