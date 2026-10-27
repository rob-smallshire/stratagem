# Art

Hand-made source artwork. These are masters: game assets are generated from
them by the build (into `build/generated/`, never committed), and the docs
and README refer to them directly.

- `cover/stratagem-poster.png`: the disc cover, a poster, 1060 x 1484.
  For the README.
- `cover/stratagem-4x3.png`: the cover adapted to 4:3, 1448 x 1086, the
  display's shape. To be reduced to a MODE 2 loading screen.
- `music/Stratagem_Overture.mid`: the Stratagem Overture, a MIDI file of
  twelve orchestral tracks, 40 bars at 96 beats a minute. The basis of the
  title screen's music (`tools/stratagem/overture.py` turns it into a Music
  5000 score). The title only: the game will have its own music.
- `music/style.md`: the music's inspiration and the mood it is to set.
