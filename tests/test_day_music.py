"""The musical day's pieces (stratagem.day_music), as the sequencer's model
plays them: each once, to its END; each arriving out of silence; and all
of them, with the overture, within the bank's room for pieces. And the
scores (stratagem.day_scores) as saved, in art/music."""

import pytest

from stratagem import day_music, day_scores, overture, sequencer

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


@pytest.mark.parametrize("score", day_scores.SCORES, ids=lambda s: s.__name__)
def test_a_score_is_saved_as_written(score, tmp_path):
    written = score()
    assert written.write(tmp_path).read_bytes() == (day_scores.MUSIC_DIRPATH / written.filename).read_bytes(), \
        "art/music is stale: uv run python -m stratagem.day_scores"


@pytest.mark.parametrize("arrangement, next_hour", [(day_music.DAYLIGHT, day_music.DUSK_HOUR),
                                                    (day_music.NIGHT, day_music.DAWN_HOUR)],
                         ids=["daylight", "night"])
def test_daylight_and_night_end_with_the_quiet_to_run_before_the_next(arrangement, next_hour):
    """Started at its latest start, the piece ends, and its least silence
    after, before the next period (Dusk's, Dawn's) begins."""
    start = day_music.latest_start(arrangement, next_hour)
    seconds = sequencer.SequencePlayer(day_music.piece(arrangement)).ticks() / day_music.TICKS_PER_SECOND
    ends = start * day_music.TIME_SECONDS + seconds + day_music.QUIET_MIN_SECONDS
    assert ends <= day_music.period_time(next_hour) * day_music.TIME_SECONDS
