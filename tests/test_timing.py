import pytest

from piano_synth.models import TempoPoint
from piano_synth.timing import TempoMap


def test_constant_tempo() -> None:
    tempo = TempoMap([TempoPoint(beat=0, bpm=120)])
    assert tempo.beat_to_seconds(4) == pytest.approx(2.0)
    assert tempo.beat_to_sample(4, 48000) == 96000


def test_piecewise_tempo() -> None:
    tempo = TempoMap(
        [
            TempoPoint(beat=0, bpm=120),
            TempoPoint(beat=4, bpm=60),
        ]
    )
    assert tempo.beat_to_seconds(4) == pytest.approx(2.0)
    assert tempo.beat_to_seconds(6) == pytest.approx(4.0)


def test_tempo_map_must_start_at_zero() -> None:
    with pytest.raises(ValueError):
        TempoMap([TempoPoint(beat=1, bpm=120)])