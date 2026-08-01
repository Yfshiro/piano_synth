import pytest

from piano_synth.pitch import (
    frequency_to_nearest_midi,
    midi_to_frequency,
    midi_to_scientific_name,
    parse_scientific_pitch,
    pitch_error_cents,
    scientific_name_to_midi,
    sequence_to_expected_midi,
    sequence_to_expected_name,
)


def test_standard_pitch() -> None:
    assert midi_to_frequency(69) == pytest.approx(440.0)
    assert frequency_to_nearest_midi(440.0) == 69
    assert pitch_error_cents(440.0, 69) == pytest.approx(0.0)

def test_piano_boundaries() -> None:
    assert sequence_to_expected_midi(1) == 21
    assert sequence_to_expected_midi(88) == 108

    assert sequence_to_expected_name(1) == "A0"
    assert sequence_to_expected_name(88) == "C8"

    assert midi_to_scientific_name(21) == "A0"
    assert midi_to_scientific_name(108) == "C8"

def test_central_c_mapping() -> None:
    assert sequence_to_expected_midi(40) == 60
    assert sequence_to_expected_name(40) == "C4"
    assert scientific_name_to_midi("C4") == 60

def test_a4_mapping() -> None:
    assert sequence_to_expected_midi(49) == 69
    assert sequence_to_expected_name(49) == "A4"
    assert scientific_name_to_midi("A4") == 69

@pytest.mark.parametrize(
    ("label", "midi"),
    [
        ("A0", 21),
        ("A#0", 22),
        ("B0", 23),
        ("C1", 24),
        ("C4", 60),
        ("A4", 69),
        ("B7", 107),
        ("C8", 108),
    ],
)
def test_scientific_name_to_midi(
    label: str,
    midi: int,
) -> None:
    assert scientific_name_to_midi(label) == midi
    assert midi_to_scientific_name(midi) == label

def test_parse_scientific_pitch() -> None:
    parsed = parse_scientific_pitch("C#4")

    assert parsed.label == "C#4"
    assert parsed.note_name == "C#"
    assert parsed.octave == 4
    assert parsed.midi == 61

@pytest.mark.parametrize(
    "label",
    [
        "",
        "H4",
        "C##4",
        "4C",
        "A#",
        "C4-extra",
    ],
)
def test_invalid_scientific_name(label: str) -> None:
    with pytest.raises(ValueError):
        scientific_name_to_midi(label)

@pytest.mark.parametrize("index", [0, 89])
def test_invalid_sequence_index(index: int) -> None:
    with pytest.raises(ValueError):
        sequence_to_expected_midi(index)

@pytest.mark.parametrize(
    ("frequency_hz", "midi", "expected_cents"),
    [
        (440.0, 69, 0.0),
        (880.0, 69, 1200.0),
        (220.0, 69, -1200.0),
        (midi_to_frequency(70), 69, 100.0),
        (midi_to_frequency(68), 69, -100.0),
    ],
)
def test_pitch_error_relative_to_reference_midi(
    frequency_hz: float,
    midi: int,
    expected_cents: float,
) -> None:
    assert pitch_error_cents(
        frequency_hz,
        midi,
    ) == pytest.approx(expected_cents)

@pytest.mark.parametrize(
    "frequency_hz",
    [
        0.0,
        -1.0,
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_invalid_frequency(frequency_hz: float) -> None:
    with pytest.raises(ValueError):
        frequency_to_nearest_midi(frequency_hz)

    with pytest.raises(ValueError):
        pitch_error_cents(frequency_hz, 69)

@pytest.mark.parametrize(
    ("index", "expected_midi"),
    [
        (1, 21),
        (2, 22),
        (40, 60),
        (49, 69),
        (88, 108),
    ],
)
def test_sequence_mapping(
    index: int,
    expected_midi: int,
) -> None:
    assert sequence_to_expected_midi(index) == expected_midi