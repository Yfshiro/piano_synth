from pathlib import Path

from piano_synth.models import DatasetManifest, KeyRecord
from piano_synth.pitch import (
    midi_to_scientific_name,
    sequence_to_expected_midi,
)
from piano_synth.validation import validate_manifest


def make_record(
    index: int,
    source_path: Path,
) -> KeyRecord:
    midi = sequence_to_expected_midi(index)

    return KeyRecord(
        record_id=f"key-{index:03d}",
        sequence_index=index,
        source_path=str(source_path),
        source_sha256="0" * 64,
        source_label=midi_to_scientific_name(midi),
        midi_expected=midi,
    )

def test_manifest_requires_88_records_for_dataset_validation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "01-A0.m4a"
    source.write_bytes(b"test")

    manifest = DatasetManifest(
        source_root=str(tmp_path),
        decoded_root=str(tmp_path / "decoded"),
        records=[make_record(1, source)],
    )

    issues = validate_manifest(manifest)
    codes = {issue.code for issue in issues}

    assert "KEY_COUNT" in codes
    assert "SEQUENCE_COVERAGE" in codes
    assert "SOURCE_LABEL_MISMATCH" not in codes