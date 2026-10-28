"""The compact score format (stratagem.sequencer), a prototype in Python:
the encoding against what it encodes, its player against the notes, and
the overture's size."""

from functools import cache

from stratagem import overture, sequencer
from stratagem.music5000 import note_number


@cache
def overture_encoded():
    voices, end, dropped = overture.sequencer_voices()
    events = [sequencer.voice_events(v, end) for v in voices]
    piece = sequencer.encode(events, sequencer.conductor_events(overture.conductor_points(), end),
                             overture.TICKS_PER_STEP)
    return voices, events, piece


def started_notes(piece: sequencer.Piece, ticks: int) -> list[tuple[int, int, int]]:
    """(tick, channel, pitch) of each note the player starts."""
    player = sequencer.SequencePlayer(piece)
    read, started, now = player.read, [], [0]

    def recording(channel, state, writes):
        if read(channel, state, writes):
            started.append((now[0], channel, sequencer.LOWEST_NOTE + state.pitch))
            return True
        return False

    player.read = recording
    for tick in range(ticks):
        now[0] = tick
        player.tick()
    return started


def tick_of(step: int, steps_per_tick: int) -> int:
    """The tick on which a step's events are read: the first that sees the
    step reached (step 0 on the first)."""
    tick = 0
    while step and (tick + 1) * steps_per_tick >> 16 < step:
        tick += 1
    return tick


def test_the_overture_is_a_sixth_of_the_size():
    _, _, piece = overture_encoded()
    assert piece.size() < 1800
    assert sum(map(len, overture.SCORE.streams())) > 5 * piece.size()


def test_the_encoding_reads_back_as_the_tokens():
    _, events, piece = overture_encoded()
    for index, voice in enumerate(events):
        assert sequencer.expand(piece, index) == sequencer.tokens(voice), f"voice {index}"


def test_every_note_starts_on_its_tick_and_channel():
    voices, _, piece = overture_encoded()
    player = sequencer.SequencePlayer(piece)
    wanted = sorted((tick_of(note.start, piece.steps_per_tick), channel, note.pitch)
                    for channel, voice in enumerate(voices) for note in voice.notes)
    assert sorted(started_notes(piece, player.ticks())) == wanted


def test_the_piece_plays_again_from_the_start():
    _, _, piece = overture_encoded()
    ticks = sequencer.SequencePlayer(piece).ticks()
    first = [(channel, pitch) for tick, channel, pitch in started_notes(piece, 1)]
    again = [(channel, pitch) for tick, channel, pitch in started_notes(piece, ticks + 1) if tick == ticks]
    assert first and again == first


def test_a_phrase_transposed_is_one_pattern():
    """Intervals, not pitches: a phrase played again a fourth up is the same
    tokens after its first note, kept once."""
    phrase = ["D4", "F#4", "A4", "F#4", "E4", "G4", "B4", "G4"]
    notes = [sequencer.Note(i * 10, i * 10 + 9, note_number(name) + shift, "Horn", "horn", 0, 13)
             for repeat, shift in enumerate((0, 5, 0, 5)) for i, name in enumerate(phrase, start=repeat * 8)]
    voices, _ = sequencer.allocate(notes, 1.5, 80, 20)
    events = [sequencer.voice_events(v, 320) for v in voices]
    piece = sequencer.encode(events, sequencer.conductor_events([(0, 0)], 320), 1.5)
    assert len(piece.voices) == 1
    assert sum(map(len, piece.patterns)) < 12           # seven notes and a RETURN, give or take
    assert sequencer.expand(piece, 0) == sequencer.tokens(events[0])
