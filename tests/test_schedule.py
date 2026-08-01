import pytest
from pydantic import ValidationError

from piano_synth.models import (
    NoteEvent,
    PedalEvent,
    RenderProject,
    Track,
)
from piano_synth.rendering import schedule_project
TEST_SAMPLE_RATE = 8000

def test_pedal_extends_note_until_release() -> None:
    project = RenderProject(
        sample_rate=TEST_SAMPLE_RATE,
        tracks=[
            Track(
                track_id="piano",
                name="Piano",
                notes=[
                    NoteEvent(
                        pitch=60,
                        start_beat=0,
                        duration_beats=1,
                        velocity=80,
                        track_id="piano",
                    )
                ],
                pedal=[
                    PedalEvent(beat=0, value=127),
                    PedalEvent(beat=3, value=0),
                ],
            )
        ],
    )

    scheduled = schedule_project(project)

    assert len(scheduled) == 1

    note = scheduled[0]

    # 默认120 BPM：1拍为0.5秒。
    assert note.start_sample == 0
    SECONDS_PER_BEAT = 60.0 / 120.0

    expected_key_up = round(
        1.0 * SECONDS_PER_BEAT * TEST_SAMPLE_RATE
    )
    expected_damper = round(
        3.0 * SECONDS_PER_BEAT * TEST_SAMPLE_RATE
    )

    assert note.key_up_sample == expected_key_up
    assert note.damper_sample == expected_damper

def test_unreleased_pedal_uses_natural_sample_decay() -> None:
    project = RenderProject(
        sample_rate=TEST_SAMPLE_RATE,
        tracks=[
            Track(
                track_id="piano",
                name="Piano",
                notes=[
                    NoteEvent(
                        pitch=60,
                        start_beat=0,
                        duration_beats=1,
                        velocity=80,
                        track_id="piano",
                    )
                ],
                pedal=[
                    PedalEvent(beat=0, value=127),
                ],
            )
        ],
    )

    scheduled = schedule_project(project)

    assert len(scheduled) == 1

    note = scheduled[0]

    assert note.start_sample == 0
    assert note.key_up_sample == 4000

    # 踏板在工程结束前没有抬起，让原始采样自然衰减。
    assert note.damper_sample is None
def test_render_project_rejects_invalid_sample_rate() -> None:
    with pytest.raises(ValidationError):
        RenderProject(
            sample_rate=1000,
            tracks=[],
        )

def test_render_project_accepts_minimum_sample_rate() -> None:
    project = RenderProject(
        sample_rate=8000,
        tracks=[],
    )

    assert project.sample_rate == 8000