from pathlib import Path

import pytest

from piano_synth.manifest import discover_dataset
from piano_synth.pitch import (
    midi_to_scientific_name,
    sequence_to_expected_midi,
)


def create_fake_88_key_dataset(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    for index in range(1, 89):
        midi = sequence_to_expected_midi(index)
        label = midi_to_scientific_name(midi)
        path = directory / f"{index:02d}-{label}.m4a"
        path.write_bytes(f"fake-{index}".encode())

def test_discover_standard_88_key_names(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw" / "88keys"
    decoded = tmp_path / "decoded"

    create_fake_88_key_dataset(raw)

    manifest = discover_dataset(raw, decoded)

    assert len(manifest.records) == 88

    first = manifest.records[0]
    middle_c = manifest.records[39]
    last = manifest.records[-1]

    assert first.sequence_index == 1
    assert first.source_label == "A0"
    assert first.midi_expected == 21

    assert middle_c.sequence_index == 40
    assert middle_c.source_label == "C4"
    assert middle_c.midi_expected == 60

    assert last.sequence_index == 88
    assert last.source_label == "C8"
    assert last.midi_expected == 108

    assert all(
        not record.review_notes
        for record in manifest.records
    )

def test_discover_reports_label_mismatch(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw" / "88keys"
    decoded = tmp_path / "decoded"
    raw.mkdir(parents=True)

    (raw / "01-A#0.m4a").write_bytes(b"fake")

    manifest = discover_dataset(raw, decoded)

    assert manifest.records[0].midi_expected == 21
    assert manifest.records[0].source_label == "A#0"
    assert manifest.records[0].review_notes

def test_discover_rejects_malformed_audio_filename(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw" / "88keys"
    decoded = tmp_path / "decoded"
    raw.mkdir(parents=True)

    (raw / "1-A0.m4a").write_bytes(b"fake")

    with pytest.raises(ValueError, match="do not match"):
        discover_dataset(raw, decoded)