# Musical direction

What the game's music is for, when it plays, and how each piece is to be
rendered on the Music 5000. `art/music/style.md` is the musical identity;
`docs/music-5000.md` is the engineering (the board, the player, the
score format, the measurements). This document is the brief, and the
decisions taken in arranging to it.

## Music as an occasional visitor

There is no continuous background music. A simple musical director
chooses when to play a piece, from the state of the world:

- Long stretches of silence, with environmental sound effects providing
  the atmosphere. The silence itself is a feature, as in Minecraft.
- A modest probability of starting an appropriate piece every few
  minutes.
- Music selected according to daylight, depth, location and perhaps
  player activity.
- A minimum quiet interval after each piece.
- Special musical moments reserved for discoveries, spectacular
  landscapes or significant achievements. The overture is kept for
  celebratory use.

The music shouldn't respond at once to every change in circumstances:
that would make it a mechanical accompaniment rather than an organic part
of the experience. A piece that has started plays to its end, whatever
happens meanwhile; the director reads the world only when it chooses the
next.

## A musical day in Stratagem

Five pieces, each about a minute and a half, on the overture's themes
(`art/music/`). None is set in stone: each may be optimised and adjusted
to fit the memory, and improved artistically, to accentuate the emotional
response it reaches for.

### 1. Dawn: Awakening

`Stratagem_Dawn_Awakening.mid`, 80 beats a minute.

A delicate woodwind melody, perhaps with a solo horn and gradually
emerging strings. Optimistic but restrained: a sense of the world coming
alive. A gentler, more pastoral companion to the overture, retaining its
musical identity rather than introducing an unrelated theme.

- 0:00-0:30, **First Light.** Harp, delicate flute phrases and quiet
  strings. The world is waking.
- 0:30-0:53, **Sunrise.** Woodwinds and increasingly warm strings suggest
  the landscape emerging from darkness.
- 0:53-1:30, **The World Revealed.** The overture's horn melody returns,
  gradually accompanied by higher strings. A sense of space, optimism and
  possibility.

### 2. Daylight: The Open World

`Stratagem_Daylight_Open_World.mid`, 96 beats a minute.

The broadest, most expansive material: the joy of setting out into a
magnificent landscape with no particular destination in mind. Occasional
soaring statements of the main theme, separated by long periods of
natural ambience. Where the Moross, Copland and Williams influences come
together most strongly.

- 0:00-0:23, **The Open Country.** Pastoral flute and oboe melodies over
  flowing harp and strings. Sunshine, green valleys, distant mountains.
- 0:23-1:01, **The Journey.** The familiar ascending motif emerges in the
  French horn. More rhythmic movement suggests travelling across an
  immense landscape.
- 1:01-1:32, **The Far Horizon.** The theme returns with fuller
  orchestration, and the trumpets join as the music opens towards a broad
  conclusion.

Optimistic and adventurous without being martial or triumphant. The world
is beautiful, but it isn't there to be conquered.

### 3. Dusk: Reflection

`Stratagem_Dusk_Reflection.mid`, 80 beats a minute.

Slower, warmer, more introspective. A fragment of the main theme in the
strings; a gentle harmonic ambiguity as daylight fades. The beauty of the
fading day, giving way to an awareness that darkness is approaching: not
quite danger, not yet, but a gentle reminder that the wilderness is no
longer entirely welcoming.

- 0:00-0:30, **The Golden Hour.** Warm strings, lyrical oboe and gentle
  harp figures. A touch of nostalgia, as though the day has been well
  spent.
- 0:30-1:00, **Lengthening Shadows.** The harmony darker and more
  ambiguous; the orchestration thins to isolated woodwinds and celesta.
  The world grows quieter, and perhaps a little less reassuring.
- 1:00-1:30, **Homeward.** A tender, restrained return of the ascending
  motif in the French horn: shelter, warmth and the prospect of rest,
  without quite resolving the uncertainty.

Not an ominous countdown to nightfall: the music should encourage the
player to think about shelter without making the approaching darkness
feel like an arbitrary game mechanic.

### 4. Night: Solitude

`Stratagem_Night_Solitude.mid`, 72 beats a minute.

Sparse orchestration, low strings, distant horns, occasional celesta.
Not frightening, but vulnerability and the immense indifference of
nature. The world is still magnificent, but darkness changes our
relationship with it: mysterious, immense, potentially dangerous.

- 0:00-0:32, **The Gathering Darkness.** Sparse strings, a solitary horn
  and occasional celesta notes. Familiar material in a minor key.
- 0:32-1:12, **Something in the Darkness.** Darker harmonies, low
  woodwinds and restrained timpani suggest distant, unseen threats.
  Nothing attacks; the music merely reminds us that we're not necessarily
  alone.
- 1:12-1:32, **A Light in the Window.** A warmer harmonic colour. The horn
  recalls the ascending motif: the reassurance of shelter.

No horror-film conventions, no combat music: being alone in an enormous
wilderness after sunset, knowing that somewhere out there are things best
avoided. The ending offers a little reassurance without dispelling the
mystery.

### 5. Underground: Deep Time

`Stratagem_Underground_Deep_Time.mid`, 72 beats a minute.

A separate musical world, largely independent of the surface clock.
Mysterious, spacious, sometimes unsettling; discovering a vast cavern
might occasionally trigger a magnificent orchestral passage. Geological
time made audible: slow harmonic changes, sustained low strings, isolated
sounds emerging from the darkness, a familiar melody transformed by its
surroundings.

- 0:00-0:30, **Descent.** Deep string drones, ambiguous harmonies and
  isolated celesta notes: entering somewhere ancient.
- 0:30-1:00, **Deep Time.** Woodwinds and bassoon introduce a slower,
  darker transformation of the overture's opening motif. Space and
  stillness dominate.
- 1:00-1:30, **The Hidden World.** The harmony brightens, with horns,
  strings and woodwinds suggesting the revelation of an immense
  subterranean chamber.

Mysterious, occasionally intimidating, but fundamentally magnificent: the
player is discovering something extraordinary, not entering a dungeon
full of monsters.

### The overture

`Stratagem_Overture.mid`, the title's, kept in the game for celebration:
significant achievements and discoveries.

## The constraints

- **Memory:** the game's music lives in the fourth sideways RAM bank,
  16K, when it is free (`docs/music-5000.md`, MBANK). The player, its
  tables and waves take about 3.3K, leaving about 12K for the pieces.
- **Sixteen channels,** each one note at a time, shared by every part.
- **Fourteen waves** on the board, all in use by the overture's orchestra:
  a new instrument shares a wave and differs in its envelope. **Sixteen
  instruments** in the format.
- **Envelopes** are attack, decay, sustain and release, in amplitude
  steps a tick; vibrato, a fixed triangle. No filters: a timbre is its
  wave.
- **Time** is in steps on a musical clock, at least a tick (20ms) each.

## What was measured, plainly arranged

Each track an instrument, each note's velocity its level, no dynamics or
decorations; encoded as the overture is:

| Piece | Notes | Channels | Bytes |
|---|---|---|---|
| Dawn | 227 | 16 | 797 |
| Daylight | 605 | 16 | 1,080 |
| Dusk | 175 | 16 | 778 |
| Night | 124 | 15 | 638 |
| Underground | 118 | 16 | 585 |
| Overture (arranged) | | 16 | 1,658 |
| **Together, apart** | | | **5,536** |

So all six fit, with room to spare, even before anything is shared.

**Compressed together, they shared almost nothing:** 6,196 bytes, more
than apart. Of 122 patterns found across the six, 12 were used by more
than one piece, and those were long rests and an instrument's set-up, not
music. The reasons are in the files' timing, not in the music:

- Each piece articulates differently (a note ends 3, 5, 11 or 18 steps
  before the next), and a note's length in the score is the time to the
  next event with only a short silence folded in. So the same rhythm
  encodes as different lengths in different pieces, and the format's
  eight lengths a piece cover only 47% of the notes across the six.
- Triplets fall between the steps (20 to a quarter), so they round
  unevenly, and a repeated triplet figure is not the same bytes twice.
- Rolled chords and arpeggios start a few steps apart, unevenly.

## How the pieces are arranged

(Filled in as each piece is arranged.)
