# CLAUDE.md

Stratagem is a BBC Micro game in 6502 assembly (beebasm): an open-world
digging and building game using Exile-like technology. It targets the B+128K
and the Model B with Integra-B (the Master 128 later), keeps the OS and
filing system resident, and is tested in the Beebium emulator.

- `docs/implementation-record.md`: the game as built so far: start here.
- `docs/next-steps.md`: the agreed plan ahead.
- `docs/tube-game.md`: the game, which runs on a 6502 second processor;
  `docs/tube-prototypes.md`, how we got there.
- `docs/tile-set.md`: the planned tile set (pieces, objects, back walls) and
  how the format and renderer could carry it.
- `docs/inventory-and-crafting.md`: how other games hold, show and craft
  things, and the proposed design for Stratagem.
- `docs/loading-screen.md`: the cover shown with the flash bit switched
  every line, loading beneath it, and what we learned.
- `docs/manual.md`: the player's manual: keys, the pack, the first shapes.
- `docs/game-design.md`: the game design (from `docs/concept.md`, the original
  concept discussion).
- `docs/architecture.md`: memory model, memory map, screen, world, frame.
- `docs/platform-notes.md`: hardware and OS facts, marked verified/unsure.
- `docs/decisions.md`: decision log; add to it when a decision is made.
- `docs/reference/`: committed indexes into third-party sources. The sources
  themselves are in the gitignored `docs/local/`.

## Commands

```bash
uv run strat-build        # assemble -> build/stratagem.ssd, labels in build/labels/
uv run pytest             # builds first; emulator tests run on each machine
uv run pytest -m "not slow"   # the quick run, about a minute: one short case of each kind
uv run pytest tests/test_daylight.py   # or just the tests that cover the change
uv run python -m stratagem.index_disassembly SRC INDEX   # index a Level 7 disassembly
```

## Conventions

- The game is two programs: `asm/host.asm` (the host: `STRAT`, its loader,
  run by !BOOT; `MAIN`; `RENDER`, the render region) and `asm/parasite.asm`
  (the second processor: `PGAME`, `PWORLD`, `PLIGHT`). Each assembles its
  parts together, one label namespace each. `PROBE` is a separate
  diagnostic; the other sources are prototypes.
  Sources are listed in `SOURCES` in `tools/stratagem/build.py`; assemble
  from the project root (INCLUDE paths are relative to it). Each part
  CLEARs its address range before its ORG.
- Tables are generated from Python (`tools/stratagem/gen_tables.py` into
  `build/generated/`): never hand-edit them. `world.py`, `tiles.py` and
  `screen.py` model the 6502 exactly; tests compare byte for byte (py65 for
  `tile_at`, Beebium screen memory for the view).
- Declare variables with ORG/SKIP so that they become labels; tests look up
  addresses by label name, never by a hard-coded address.
- Code that writes the screen, and the data it reads, must be outside
  `&3000`-`&7FFF` (see the memory model). Never write `&FE34` without
  branching on the machine: it is ACCCON on the B+ but RAMSEL on the
  Integra-B.
- Beebium's `run_*` helpers leave the machine stopped. Wait on sentinels,
  not wall-clock time.
