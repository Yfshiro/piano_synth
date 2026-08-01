from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .models import DatasetManifest, KeyRecord
from .pitch import (
    midi_to_scientific_name,
    scientific_name_to_midi,
    sequence_to_expected_midi,
)

FILE_PATTERN = re.compile(
    r"^(?P<index>\d{2})-"
    r"(?P<label>[A-G]#?-?\d+)"
    r"\.(?P<extension>m4a|mp4|aac|wav)$",
    re.IGNORECASE,
)

def sha256_file(
    path: Path,
    chunk_size: int = 1024 * 1024,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)

    return digest.hexdigest()

def normalize_pitch_label(label: str) -> str:
    label = label.strip()

    if len(label) < 2:
        return label

    return label[0].upper() + label[1:]

def discover_dataset(
    raw_directory: Path,
    decoded_directory: Path,
) -> DatasetManifest:
    raw_directory = raw_directory.resolve()
    decoded_directory = decoded_directory.resolve()

    if not raw_directory.exists():
        raise FileNotFoundError(
            f"Raw dataset directory does not exist: {raw_directory}"
        )

    if not raw_directory.is_dir():
        raise NotADirectoryError(
            f"Raw dataset path is not a directory: {raw_directory}"
        )

    candidates: list[tuple[int, str, int, Path]] = []
    malformed_files: list[str] = []

    for path in raw_directory.iterdir():
        if not path.is_file():
            continue

        if path.suffix.lower() not in {".m4a", ".mp4", ".aac", ".wav"}:
            continue

        match = FILE_PATTERN.fullmatch(path.name)
        if match is None:
            malformed_files.append(path.name)
            continue

        sequence_index = int(match.group("index"))
        source_label = normalize_pitch_label(match.group("label"))

        try:
            label_midi = scientific_name_to_midi(source_label)
        except ValueError as exc:
            raise ValueError(
                f"Invalid pitch label in file {path.name!r}: {exc}"
            ) from exc

        candidates.append(
            (
                sequence_index,
                source_label,
                label_midi,
                path.resolve(),
            )
        )

    if malformed_files:
        formatted = "\n".join(
            f"  - {name}" for name in sorted(malformed_files)
        )
        raise ValueError(
            "The following audio files do not match "
            "'NN-PITCH.extension':\n"
            f"{formatted}"
        )

    candidates.sort(key=lambda item: item[0])

    if not candidates:
        raise ValueError(
            f"No supported audio files were found in {raw_directory}"
        )

    seen_indexes: set[int] = set()
    records: list[KeyRecord] = []

    for sequence_index, source_label, label_midi, path in candidates:
        if sequence_index in seen_indexes:
            raise ValueError(
                f"Duplicate sequence index: {sequence_index:02d}"
            )

        seen_indexes.add(sequence_index)

        if not 1 <= sequence_index <= 88:
            raise ValueError(
                f"Sequence index outside [01, 88]: {path.name}"
            )

        midi_expected = sequence_to_expected_midi(sequence_index)
        expected_name = midi_to_scientific_name(midi_expected)
        review_notes: list[str] = []

        if source_label != expected_name:
            review_notes.append(
                f"Filename label {source_label} does not match "
                f"sequence-derived pitch {expected_name}"
            )

        if label_midi != midi_expected:
            review_notes.append(
                f"Filename MIDI {label_midi} does not match "
                f"sequence-derived MIDI {midi_expected}"
            )

        records.append(
            KeyRecord(
                record_id=f"key-{sequence_index:03d}",
                sequence_index=sequence_index,
                source_path=str(path),
                source_sha256=sha256_file(path),
                source_label=source_label,
                midi_expected=midi_expected,
                review_notes=review_notes,
            )
        )

    return DatasetManifest(
        source_root=str(raw_directory),
        decoded_root=str(decoded_directory),
        records=records,
    )

def load_manifest(path: Path) -> DatasetManifest:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"Manifest root must be a mapping: {path}")

    return DatasetManifest.model_validate(data)

def save_manifest(
    manifest: DatasetManifest,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest.updated_at = datetime.now(UTC)

    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            manifest.model_dump(mode="json"),
            handle,
            allow_unicode=True,
            sort_keys=False,
        )