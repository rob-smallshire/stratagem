# CLAUDE.md

Stratagem is a BBC Micro game in 6502 assembly (beebasm): an open-world
digging and building game using Exile-like technology. It targets the B+128K
and the Model B with Integra-B (the Master 128 later), keeps the OS and
filing system resident, and is tested in the Beebium emulator.

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
uv run python -m stratagem.index_disassembly SRC INDEX   # index a Level 7 disassembly
```

## Conventions

- Each program is a beebasm source in `asm/` that SAVEs a file of the same
  name, listed in `PROGRAMS` in `tools/stratagem/build.py`. Assemble from
  the project root (INCLUDE paths are relative to it).
- Declare variables with ORG/SKIP so that they become labels; tests look up
  addresses by label name, never by a hard-coded address.
- Code that writes the screen, and the data it reads, must be outside
  `&3000`-`&7FFF` (see the memory model). Never write `&FE34` without
  branching on the machine: it is ACCCON on the B+ but RAMSEL on the
  Integra-B.
- Beebium's `run_*` helpers leave the machine stopped. Wait on sentinels,
  not wall-clock time.
