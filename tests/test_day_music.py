"""The musical day's pieces (stratagem.day_music), as the sequencer's model
plays them: each once, to its END; each arriving out of silence; and all
of them, with the overture, within the bank's room for pieces."""

import pytest

from stratagem import day_music, overture, sequencer

PIECES_BUDGET = 10 * 1024           # of MBANK's 16K, beside the player and its tables


@pytest.mark.parametrize("arrangement", day_music.ARRANGEMENTS, ids=lambda a: a.name)
def test_a_piece_plays_once_to_its_end(arrangement):
    piece = day_music.piece(arrangement)
    player = sequencer.SequencePlayer(piece)
    ticks = player.ticks()
    for _ in range(ticks + 2):
        player.tick()
    assert not player.playing, "it didn't end"
    assert player.tick() == [], "it ticks on, ended"


@pytest.mark.parametrize("arrangement", day_music.ARRANGEMENTS, ids=lambda a: a.name)
def test_a_piece_arrives_out_of_silence(arrangement):
    """The conductor starts at least 16dB down from the piece's loudest."""
    levels = [db for _, db in arrangement.dynamics]
    assert levels[0] <= max(levels) - 16
    assert levels[-1] <= max(levels) - 16


def test_the_pieces_fit():
    total = sum(day_music.piece(a).size() for a in day_music.ARRANGEMENTS) + overture.sequencer_piece().size()
    assert total <= PIECES_BUDGET, f"{total} bytes"
