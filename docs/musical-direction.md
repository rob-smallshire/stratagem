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

## Underground: another world

The user, after the brief: Underground should be somewhat more at odds
with the other music, a bit otherworldly. On the board, that is timbre
and space the surface pieces never use:

- **Glass** where the other pieces have strings: pure tones an octave up,
  each doubled two units sharp on the other side, so the pair beats
  slowly. Nothing else in the day is a sine.
- **Drones with no beginning:** the low strings swell over 2.5 seconds
  and fade as slowly, without vibrato. Stone doesn't breathe.
- **The cave answers:** echoes, late and quieter on the far side, and the
  celesta's second answer a fifth above, an organum no surface piece has.
- Still to try: the board's **modulation** (a channel switching its
  neighbour between two waves on its own wave's sign: ring- and FM-like
  sounds), which no other piece would use.

## Arranger's notes

An arranger's view of the five pieces (from the `stratagem-art` session). It is drawn from the brief, `art/music/style.md`,
the overture's arrangement and a reading of the MIDI files: their parts,
ranges, velocities, density over time and harmony bar by bar.

### What the files have in common

- **Terraced dynamics.** Every part has one velocity for each passage,
  stepping up or down at the passage's boundary and flat within it. The
  harp and the strings play at the same density all the way through. For
  example, Daylight's harp plays 18 notes every 10 seconds from start to
  finish, and its strings 12. Nothing swells and nothing recedes. The
  conductor is where these pieces will gain or lose most: a hairpin
  through each passage, and a breath before the next.
- **They start and stop abruptly.** Dawn and Daylight start at once with
  harp, cellos and bass, and Dawn ends at its loudest. For music that
  arrives unannounced out of silence, the first 5 to 10 seconds should
  fade in from nothing on the conductor, and the end should dissolve:
  long releases, the parts falling away one by one, and the last sound a
  single voice. The overture is the exception, because a celebration
  ought to land.
- **Isolated sounds come by the clock.** In Night and Underground the
  celesta and the harp play once every 10 seconds, like a metronome.
  "Isolated sounds emerging from the darkness" need irregular gaps:
  move each by a beat or two either way. That costs some compression,
  and memory allows it.
- **A ladder of peaks.** The pieces' loudest moments should rank in
  order: the overture's tutti, then Daylight's Far Horizon and
  Underground's Hidden World, then Dawn's World Revealed, then Dusk, then
  Night. If a daily piece reaches the overture's peak, celebration has
  nothing left to rise to.

### The board's means of expression

The board has no filters or reverb, so warmth, distance and space have to
come from what it does have:

- **Near or far.** A near instrument is centred, has a quick attack and
  vibrato. A far one is placed hard to one side, plays 6 to 9 dB quieter,
  with a slow attack and no vibrato. Two instruments can share a wave as
  "near horn" and "far horn", which costs only an instrument slot.
- **Vibrato as warmth.** The vibrato is fixed, but whether a note has it
  is a choice. Without it a note is still and cold; with it, alive and
  human. Withdraw vibrato as a piece darkens and give it back for the
  reassurance at the end.
- **Detuned doubling means many players.** It warms a string section.
  Keep it off solos: a solo flute or horn is one person, and doubling it
  turns it into a section.
- **Echo means walls.** Open country has no reflections, so the surface
  pieces should take their space from stereo width and level. The cave
  is where echo belongs. Keeping echo for Underground is also what will
  tell it apart from Night, which otherwise shares its material (below).

### Dawn: Awakening

1. **Begin almost from nothing.** The harp plays at the same density from
   the first second, which is daytime behaviour. In First Light, thin it
   to a few notes and let it fill out into Sunrise. Keep the solo flute
   single, with little or no vibrato. Bring the violins in (at 0:30) with
   a slow attack, so that they seem to rise rather than enter.
2. **Let the horn arrive from a distance.** Play its first phrase (0:53)
   as a far horn: off to one side, quiet, no vibrato. Bring it to the
   centre with vibrato for the next phrase, as the violins climb. Then
   let the end recede rather than stop at the summit: strings first,
   then the horn, with the harp's last notes alone. Dawn hands over to
   the day's own sounds.

### Daylight: The Open World

1. **Make room.** As written, this is the densest piece: 605 notes, with
   harp and strings going all the time. "Space" here means fewer notes.
   Halve the harp in The Journey so that the horn's ascending motif is
   alone in its register. Keep the cellos' rhythmic figure (they go from
   4 to 16 notes every 10 seconds at 0:30): that is the travelling. Keep
   the strings' ensemble doubling, but spread their chords wide, so that
   the landscape is wide rather than loud.
2. **Trumpets join, they don't announce.** "Not martial or triumphant":
   when the trumpets enter (1:15), keep them below the horn in level, in
   harmony with it, with a soft attack, at most a mild timpani swell
   under them, and no stab chords. The file already lets the strings and
   bass fall back in the last 10 seconds. Shape that into a long, broad
   decrescendo, so that the piece ends looking at the horizon rather than
   arriving at it.

### Dusk: Reflection

1. **Let the colour drain.** The file already thins Lengthening Shadows:
   the violins drop out and the harp nearly stops. The board can make
   this audible: in the Golden Hour the strings are doubled and have
   vibrato. At 0:30, take away the doubling and the vibrato, and lower
   the conductor a little. The celesta and bassoon should then sound
   exposed, the first touch of the cool.
2. **Keep the ending open.** The last bars are C sharp, E, G: a dominant
   without its root. That is the "without quite resolving" the brief asks
   for. Don't let the arrangement add a tonic in the bass. The solo horn's
   Homeward is low (A3 to F#4), so give it its vibrato back, centre it,
   and give its last notes, and the chord's, the longest release in the
   piece.

### Night: Solitude

1. **Wide, dry and far.** Put the solo horn hard to one side, quiet, as
   a far horn, and the celesta high on the other side, with the strings
   low in the centre. Use no echo: the night is open air, and the
   emptiness between the sides is the solitude. Keep vibrato off
   everything until A Light in the Window.
2. **The light in the window.** At 1:20 the harmony turns from D minor to
   D major (F sharp). Make that the one moment of warmth: the horn comes
   to the centre with vibrato, a single detuned doubling under the
   strings, and the conductor rises by a few dB, no more. In Something in
   the Darkness, the timpani's three notes should be a heartbeat felt
   rather than heard: low, centred, a long release, well below the
   strings.

### Underground: Deep Time

1. **The cave answers.** Echo is this piece's identity. Echo the celesta
   and the clarinet late (half a bar or more), quieter and on the far
   side, and perhaps a second, fainter repeat: drips and calls in a
   chamber. Have the drones enter with very slow attacks, over seconds,
   so that they have no beginning, and without vibrato: stone doesn't
   breathe. As the overture found, the low end on the board is thin.
   Level the contrabass and low strings up, and double the contrabass
   an octave higher, quietly, so that G1 can be heard on small speakers.
2. **The Hidden World has to be magnificent.** As written, it peaks at
   velocity 53 to 57, hardly louder than the descent. Make it the
   conductor's one great swell: the horns and trombones in the centre,
   the strings spread wide, the timpani rolling under the brightening
   to D major (1:00), and the echo giving way as the tutti fills the
   channels. Then pull back for the last bars, which settle on a bare D.

### Where I'd push on the brief

- **Night and Underground share their opening.** Both begin on D, E, F
  and A over a G1 contrabass, at 72 beats a minute, with celesta and harp
  once every 10 seconds. A player who hears one at dusk on the surface
  and the other in a cave will hear the same piece. Their staging should
  separate them: Night wide, dry and far; Underground central, enclosed
  and echoing. Rewriting one of the openings would separate them further.
  The more distinctive transformation of the overture's opening motif
  (the bassoon's, at 0:30) could come at the start of Underground.
- **Make each passage playable alone.** With long silences between
  visits, the same 90 seconds return often, and a three-passage form
  becomes recognisable. If each passage can start from silence and end
  cleanly, the director gains variety for almost no memory. For example,
  it could play Night's Something in the Darkness alone, or play
  Underground's Hidden World alone at the discovery of a great cavern,
  which the brief already wants. That would leave the overture for
  achievements.
- **Daylight's "long periods of natural ambience" belong to the
  director, not the piece.** The piece can't contain silence enough for
  that. Give it breathing room inside, by thinning (above), and leave the
  long silences to the director.
- **Celesta and bassoon on shared waves.** The celesta's character is
  all envelope: an instant attack, a fast decay, no sustain and a short
  release, on the brightest wave there is, played an octave up. Two
  detuned channels give it its shimmer, and that is the one solo where
  doubling helps. The bassoon is the clarinet's or the oboe's wave, low,
  with a slower attack and a short release. It reads as a bassoon more
  through its register and its staccato than through its timbre.

## How the pieces are arranged

`tools/stratagem/day_music.py` holds each arrangement as data, after the
notes above: each track a part (an instrument, a level, a place, its
articulation, its decorations), which may change from a given bar; and
the conductor's dynamics, which fade each piece in from nothing and
dissolve it at its end. `uv run python -m stratagem.day_music` prints how
each fits and renders all six (the overture too) to `build/features/`,
at one gain, so they keep their levels.

- **The timing regularised:** a grid of 30 steps a quarter (eighths,
  triplets and quintuplets exact; a step a tick or more up to 100 beats a
  minute); rolled chords spaced evenly; each part's articulation (a few
  steps of silence before its next note), so that a note's slot is a
  musical length.
- **New instruments,** sharing the overture's waves: celesta (the
  brightest wave, struck, an octave up), bassoon (the oboe's wave, still,
  short), a far horn (slower, no vibrato, nearer silent), still strings,
  cello and oboe (no vibrato), a drone and glass. The format takes 32
  instruments; the title's player has tables only for the overture's 13.
- **Dawn:** the harp halved and the violins still in First Light, rising
  in with vibrato at 0:53; the horn's first phrase far to the left, near
  and centred from its second; the strings falling away before the horn
  at the end.
- **Daylight:** the harp halved in the Journey; the strings wide (hard
  left, centre, hard right) and doubled; the trumpets 6dB under the horn;
  a broad diminuendo over the last three bars.
- **Dusk:** at 0:30 the strings' doubling and vibrato go and the
  conductor drops 4dB, leaving the celesta and bassoon exposed; vibrato
  back for Homeward, the horn central; the open ending kept.
- **Night:** horn far left, celesta high right, strings and cellos still
  in the centre, no echo; celesta and harp off the clock; at bar 24, the
  turn to D major, the horn near with vibrato, the strings doubled once,
  the conductor up 2dB.
- **Underground:** as above; then the Hidden World's swell from bar 19,
  horns and trombone central, the strings wide in place of the glass,
  the echoes giving way.

Measured (the model's renders):

| Piece | Channels | Bytes | Loudest 3s, from the overture's |
|---|---|---|---|
| Dawn | 16 | 907 | -5.5dB |
| Daylight | 16 | 1,127 | -3.0dB |
| Dusk | 16 | 846 | -9.4dB |
| Night | 12 | 720 | -11.4dB |
| Underground | 16 | 1,069 | -5.1dB |
| Overture | 16 | 1,658 | 0 |

All six: 6.3K, about half the bank's room for pieces. Regularised, the
day's five are 4.7K arranged against 3.9K plain: the decorations and the
changes by bar cost more than the regular timing saves.

## The second day

Heard together, the first five were indistinct: each in 4/4, at 72 to 96
beats a minute, each 92 seconds, all for the full orchestra, in much the
same textures. They are kept (`FIRST_DAY` in `day_music.py`, the MIDI
files in `art/music/`), but the game now plays a second day, composed
for the board with more freedom (`tools/stratagem/day_scores.py`, which
writes `art/music/Stratagem_{Dawn_Chorus,Daylight_Open_Road,
Dusk_Long_Shadows,Night_Watch,Underground_Seams}.mid`). Each piece has
its own metre, key, tempo and texture, and what holds them together is
the orchestra, the hall (dry above ground, echoing below) and the
overture's motto: its opening rise, a fourth and then two steps (A D E F#).

| Piece | Metre, tempo | Key | Texture | The motto |
|---|---|---|---|---|
| Dawn Chorus | 6/8, 78 | G Lydian | birdsong (flute, oboe, clarinet) across the field, rippling harp, the ground still until sunrise | slow, on the horn at sunrise; high, on the violins |
| The Open Road | 4/4, 98 | A, a shift to F | plucked strings and bass, a celesta ostinato bent to each chord, the tune passed from horn to trumpet to all | quick, opening a striding tune |
| Long Shadows | 3/4, 66 | E flat | a cello's song over the harp's lilt; the clarinet's in C minor; ending open on the fourth chord | backwards, falling |
| Night Watch | 5/4, 54 | B Dorian | a lone low flute; stars on the celesta, off the clock; the harp's slow clock far left | in minor; the clarinet and a far horn in canon |
| Seams | 7/8, 84 | C Phrygian | a plucked ostinato, drips echoing (one a fifth above), drones and glass | bent a semitone on the trombone; from A flat rising into C major, the Hidden World |

New instruments, on the overture's waves: pizzicato (the strings' wave,
struck, gone in half a second), a plucked bass, and a drip (a pure tone,
struck, ringing a second and more).

Measured (the model's renders):

| Piece | Length | Channels | Bytes | Loudest 3s, from the overture's |
|---|---|---|---|---|
| Dawn Chorus | 77s | 16 | 776 | -5.7dB |
| The Open Road | 91s | 16 | 1,120 | -2.4dB |
| Long Shadows | 83s | 13 | 744 | -10.2dB |
| Night Watch | 88s | 14 | 536 | -12.5dB |
| Seams | 68s | 16 | 896 | -4.4dB |

The five: 4.1K, against the first day's 4.7K, since ostinatos and
repeated accompaniments make patterns. Night is the sparsest, and the
smallest.

## The director

In MBANK (`asm/mbank.asm`), ticked as the music is: while a piece plays,
the tick is the piece's; in the silences between, the director counts
down, which costs almost nothing.

- **The world's day:** the parasite keeps a clock (`asm/world_clock.asm`):
  a 16-bit count of frames, a day of 21.8 minutes (midnight at 0, noon at
  &8000), from 5 o'clock, stopped while the pack is open. Each packet
  carries the time, the clock's high byte, in 256ths of a day
  (`PACKET_TIME`), and whether the player's feet are three tiles or more
  below the surface (`PACKET_WORLD`). The world's light follows it
  (`docs/tube-game.md`, Day and night).
- **The piece for the moment:** Underground, if the player is
  underground; otherwise by the time: Dawn from 5 o'clock, Daylight from
  7, Dusk from 18, Night from 20 (`tube_layout.asm`, as times: &35, &4A,
  &C0, &D5).
- **When:** 15 seconds of silence at the start, then the first piece for
  certain (at 5 o'clock, Dawn: the world waking with the player); after
  each piece, two minutes and up to 2:43 more of silence; then every 30
  seconds a chance of a third of the piece for the moment, half that if
  it was the last played. A piece plays to its end, whatever happens.
- **The silences, as they fall** (simulated exactly: the director's own
  LFSR, all 128 seeds, three hours each on the surface): median 3.8
  minutes, mean 4.8; half between 2.8 and 5.8, 5% to 95% from 2.2 to 9.7,
  the longest 25. Music plays about a quarter of the time. Kept so:
  continuous music tires. Two quirks, accepted for now: Dawn's and Dusk's
  windows (109 seconds each) are shorter than the least quiet, so after
  the first Dawn they come about a tenth of the time each, against
  Daylight's and Night's two fifths; and the LFSR moves a bit a draw, so
  successive chances are correlated, lengthening the tail.
- **The overture** is in the bank, for celebration; nothing asks for it
  yet.
- `tests/test_game_music.py` checks that Dawn comes first, after the quiet
  start; that the bank's player plays it as the model does; and that the
  director is quiet for two minutes or more after it ends.
  `tests/test_world_clock.py` checks the clock and the underground flag.

## Not yet

- **Celebration:** moments for the overture (and a great cavern's
  discovery for the Hidden World) need the game to name them.

- **Each passage playable alone,** as the notes propose: the director
  would gain variety, and the Hidden World alone could mark a great
  cavern's discovery.
- **Night and Underground's shared opening:** staging now separates them;
  rewriting one opening would separate them further.
