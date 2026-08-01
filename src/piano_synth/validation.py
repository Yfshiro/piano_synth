from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .manifest import sha256_file
from .models import DatasetManifest, RecordStatus
from .pitch import (
    PIANO_KEY_COUNT,
    PIANO_MIDI_MAX,
    PIANO_MIDI_MIN,
    midi_to_scientific_name,
    scientific_name_to_midi,
    sequence_to_expected_midi,
)


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    record_id: str | None = None

def validate_manifest(
    manifest: DatasetManifest,
    require_verified: bool = False,
    verify_hashes: bool = False,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if manifest.expected_midi_min != PIANO_MIDI_MIN:
        issues.append(
            ValidationIssue(
                "ERROR",
                "MIDI_MIN",
                f"expected_midi_min should be {PIANO_MIDI_MIN}",
            )
        )

    if manifest.expected_midi_max != PIANO_MIDI_MAX:
        issues.append(
            ValidationIssue(
                "ERROR",
                "MIDI_MAX",
                f"expected_midi_max should be {PIANO_MIDI_MAX}",
            )
        )

    if len(manifest.records) != PIANO_KEY_COUNT:
        issues.append(
            ValidationIssue(
                "ERROR",
                "KEY_COUNT",
                f"Expected {PIANO_KEY_COUNT} records, "
                f"found {len(manifest.records)}",
            )
        )

    indexes = sorted(
        record.sequence_index for record in manifest.records
    )
    expected_indexes = list(range(1, PIANO_KEY_COUNT + 1))

    if indexes != expected_indexes:
        missing_indexes = sorted(set(expected_indexes) - set(indexes))
        unexpected_indexes = sorted(set(indexes) - set(expected_indexes))

        issues.append(
            ValidationIssue(
                "ERROR",
                "SEQUENCE_COVERAGE",
                f"Sequence indexes must cover 1 through 88 exactly; "
                f"missing={missing_indexes}, "
                f"unexpected={unexpected_indexes}",
            )
        )

    record_ids = [record.record_id for record in manifest.records]
    if len(record_ids) != len(set(record_ids)):
        issues.append(
            ValidationIssue(
                "ERROR",
                "DUPLICATE_RECORD_ID",
                "record_id values are not unique",
            )
        )

    verified_midis: list[int] = []
    ordered_records = sorted(
        manifest.records,
        key=lambda item: item.sequence_index,
    )

    for record in ordered_records:
        expected_midi = sequence_to_expected_midi(
            record.sequence_index
        )
        expected_name = midi_to_scientific_name(expected_midi)

        if record.midi_expected != expected_midi:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "EXPECTED_MIDI_MISMATCH",
                    f"Stored midi_expected={record.midi_expected}; "
                    f"sequence requires {expected_midi}",
                    record.record_id,
                )
            )

        if record.source_label != expected_name:
            issues.append(
                ValidationIssue(
                    "WARNING",
                    "SOURCE_LABEL_MISMATCH",
                    f"Source label is {record.source_label!r}; "
                    f"sequence requires {expected_name!r}",
                    record.record_id,
                )
            )
        elif record.source_label is not None:
            try:
                source_midi = scientific_name_to_midi(
                    record.source_label
                )
                if source_midi != expected_midi:
                    issues.append(
                        ValidationIssue(
                            "WARNING",
                            "SOURCE_LABEL_MIDI_MISMATCH",
                            f"Source label maps to MIDI {source_midi}; "
                            f"sequence requires MIDI {expected_midi}",
                            record.record_id,
                        )
                    )
            except ValueError as exc:
                issues.append(
                    ValidationIssue(
                        "WARNING",
                        "INVALID_SOURCE_LABEL",
                        str(exc),
                        record.record_id,
                    )
                )

        source = Path(record.source_path)

        if not source.exists():
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "SOURCE_MISSING",
                    str(source),
                    record.record_id,
                )
            )
        elif not source.is_file():
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "SOURCE_NOT_FILE",
                    str(source),
                    record.record_id,
                )
            )
        elif verify_hashes:
            current_hash = sha256_file(source)
            if current_hash != record.source_sha256:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "SOURCE_HASH_CHANGED",
                        "Source file content no longer matches manifest",
                        record.record_id,
                    )
                )

        if (
            record.analysis is not None
            and record.analysis.source_sha256
            != record.source_sha256
        ):
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "STALE_ANALYSIS",
                    "Analysis was generated from a different source hash",
                    record.record_id,
                )
            )

        if (
            record.midi_detected is not None
            and not (
                PIANO_MIDI_MIN
                <= record.midi_detected
                <= PIANO_MIDI_MAX
            )
        ):
            issues.append(
                ValidationIssue(
                    "WARNING",
                    "DETECTED_OUTSIDE_PIANO",
                    f"Detected MIDI is {record.midi_detected}",
                    record.record_id,
                )
            )

        if require_verified and record.status != RecordStatus.VERIFIED:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "NOT_VERIFIED",
                    f"Record status is {record.status.value}",
                    record.record_id,
                )
            )

        if record.status == RecordStatus.VERIFIED:
            if record.midi_final is None:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "FINAL_MIDI_MISSING",
                        "Verified record has no midi_final",
                        record.record_id,
                    )
                )
            else:
                verified_midis.append(record.midi_final)

                final_name = midi_to_scientific_name(
                    record.midi_final
                )
                if record.scientific_name != final_name:
                    issues.append(
                        ValidationIssue(
                            "ERROR",
                            "NAME_MISMATCH",
                            f"scientific_name should be {final_name}",
                            record.record_id,
                        )
                    )

            if record.decoded_path is None:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "DECODED_PATH_MISSING",
                        "Verified record has no decoded_path",
                        record.record_id,
                    )
                )
            else:
                decoded_path = Path(record.decoded_path)

                if not decoded_path.exists():
                    issues.append(
                        ValidationIssue(
                            "ERROR",
                            "DECODED_MISSING",
                            str(decoded_path),
                            record.record_id,
                        )
                    )
                elif (
                    verify_hashes
                    and record.decoded_sha256 is not None
                    and sha256_file(decoded_path)
                    != record.decoded_sha256
                ):
                    issues.append(
                        ValidationIssue(
                            "ERROR",
                            "DECODED_HASH_CHANGED",
                            "Decoded WAV content no longer matches manifest",
                            record.record_id,
                        )
                    )

    for left_record, right_record in zip(
        ordered_records,
        ordered_records[1:],
        strict=False,
    ):
        left_f0 = left_record.detected_f0_hz
        right_f0 = right_record.detected_f0_hz

        if left_f0 is None or right_f0 is None:
            continue

        if right_f0 <= left_f0:
            issues.append(
                ValidationIssue(
                    "WARNING",
                    "NON_ASCENDING_DETECTION",
                    (
                        f"Detected fundamental frequency "
                        f"{right_f0:.3f} Hz is not greater than "
                        f"the previous frequency "
                        f"{left_f0:.3f} Hz "
                        f"({left_record.record_id} -> "
                        f"{right_record.record_id})"
                    ),
                    right_record.record_id,
                )
            )

    if verified_midis:
        if len(verified_midis) != len(set(verified_midis)):
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "DUPLICATE_MIDI",
                    "Verified MIDI mappings are not unique",
                )
            )

        if require_verified:
            expected_midis = list(
                range(
                    PIANO_MIDI_MIN,
                    PIANO_MIDI_MAX + 1,
                )
            )

            if sorted(verified_midis) != expected_midis:
                missing_midis = sorted(
                    set(expected_midis) - set(verified_midis)
                )
                unexpected_midis = sorted(
                    set(verified_midis) - set(expected_midis)
                )

                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "MIDI_COVERAGE",
                        "Verified records must cover MIDI 21 through "
                        f"108 exactly once; missing={missing_midis}, "
                        f"unexpected={unexpected_midis}",
                    )
                )


    return issues