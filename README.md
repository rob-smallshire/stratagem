# Stratagem

> **Unfinished, and in development.** Stratagem is a game being made, not a
> game to play yet: the world, digging, building, light, the day and its
> music are there, but much of the game isn't, and anything here may change.

<p align="center">
  <img src="art/cover/stratagem-poster.png" width="40%"
       alt="The cover art: a miner with a pickaxe and a pack on a clifftop, looking out over forests, rivers, mountains and a castle, with layered rock, caves and crystals beneath">
  <img src="docs/images/in-game.png" width="54%"
       alt="The game at dusk: the miner beside a cutting dug into a hillside, a torch lit in it, a tree, and the sky glowing magenta above the hills">
</p>
<p align="center"><em>The cover art, and the game at dusk, in the Beebium emulator.</em></p>

Stratagem is an open-world digging and building game for the BBC Micro, in
the spirit of *Terraria*, made with technology like *Exile*'s: a world of
256 × 256 tiles, generated as it's needed and smoothly scrolled, with a
miner who digs, carries, crafts and builds in it. Light comes from the sun
by day and from torches by night; the day turns, and an orchestral score
for the Music 5000 follows it. Nature is the game's subject: immense,
ancient and indifferent, to be discovered rather than conquered.

It is written in 6502 assembly (beebasm), with its tables generated and its
behaviour tested from Python.

## What it runs on

- **A BBC Micro B+ 128K, or a Model B with an Integra-B board**, each with
  at least three free 16K banks of sideways RAM. A fourth holds the game's
  music. (The Master 128 is planned.)
- **A 6502 second processor:** a 3 MHz 65C02, or a 4 MHz 65C102. The game
  runs on the second processor; the BBC Micro draws what it sends.
- **A Music 5000**, if you have one, for the music. Without one, the game
  is silent.

The OS and the filing system stay resident: the game loads with ordinary
OS calls.

It is developed and tested in the
[Beebium](https://github.com/rob-smallshire/beebium) emulator, and is
untested elsewhere, including on real hardware. In Beebium, import
`presets/stratagem-b-plus-128k-65c02.json` (File > Import Presets...), a
B+ 128K with a 3 MHz 65C02, insert `build/stratagem.ssd` and press
Shift-Break.

## Building

Requires [uv](https://docs.astral.sh/uv/) and
[beebasm](https://github.com/stardot/beebasm) on the `PATH`.

```sh
uv run strat-build                    # build/stratagem.ssd
uv run pytest -m "not slow"           # the quick tests, in Beebium and py65
uv run pytest                         # all of them, on both machines
uv run --group test strat-screenshot  # the screenshot above, from the game
```

## Finding out more

- [The miner's manual](docs/manual.md): the keys, the pack, making things.
- [The game design](docs/game-design.md), and
  [building, soil and support](docs/building.md).
- [The game on the Tube](docs/tube-game.md): how it is built, as it stands.
- [The decision log](docs/decisions.md): why things are as they are.
- [The musical direction](docs/musical-direction.md), and
  [the music's style](art/music/style.md).

## Licence

MIT: see [LICENSE](LICENSE).
