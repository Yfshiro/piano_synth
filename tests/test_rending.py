import numpy as np
import pytest

from piano_synth.rendering import (
    apply_damped_release,
    equal_power_pan,
    trim_leading_silence,
    velocity_gain,
)


def test_equal_power_pan_center() -> None:
    left, right = equal_power_pan(0.0)
    assert left == pytest.approx(2**-0.5)
    assert right == pytest.approx(2**-0.5)


def test_velocity_is_not_linear() -> None:
    assert velocity_gain(64) < 64 / 127


def test_trim_leading_silence() -> None:
    audio = np.zeros((100, 2), dtype=np.float32)
    audio[50:, :] = 0.5

    trimmed = trim_leading_silence(
        audio,
        threshold_db=-40,
        pre_roll_samples=0,
    )

    assert len(trimmed) == 50
    assert trimmed[0, 0] == pytest.approx(0.5)


def test_damped_release_ends_at_zero() -> None:
    audio = np.ones((1000, 2), dtype=np.float32)
    released = apply_damped_release(
        audio,
        release_start=400,
        release_samples=200,
    )

    assert len(released) == 600
    assert released[-1, 0] == pytest.approx(0.0)
    assert np.all(np.isfinite(released))