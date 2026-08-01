from __future__ import annotations

import math
import subprocess
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import logging

logger = logging.getLogger(__name__)

from .manifest import sha256_file
from .models import (
    AnalysisMetadata,
    AudioMetadata,
    DatasetManifest,
    RecordStatus,
)
from .pitch import (
    frequency_to_nearest_midi,
    midi_to_scientific_name,
    pitch_error_cents,
    sequence_to_expected_midi,
)

ANALYSIS_ALGORITHM = "librosa-pyin-expected-midi-median"
ANALYSIS_VERSION = "1.1.2"

VOICED_PROBABILITY_MIN = 0.5
LOCAL_SEARCH_SEMITONES = 1.0
MINIMUM_PERIODS_PER_FRAME = 4.0
SUPPORTED_FRAME_LENGTHS = (2048, 4096, 8192, 16384)
MAX_TRANSITION_RATE = 1.0
DETECTION_CONFIDENCE_REVIEW_THRESHOLD = 0.10

def midi_to_frequency(midi: int) -> float:
    """Convert a MIDI note number to equal-tempered frequency in Hz."""
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def choose_frame_length(
    sample_rate: int,
    expected_frequency_hz: float,
) -> int:
    if expected_frequency_hz >= 2000.0:
        return 2048

    if expected_frequency_hz >= 1000.0:
        return 4096

    required = math.ceil(
        sample_rate
        * MINIMUM_PERIODS_PER_FRAME
        / expected_frequency_hz
    )

    for frame_length in SUPPORTED_FRAME_LENGTHS:
        if frame_length >= required:
            return frame_length

    return SUPPORTED_FRAME_LENGTHS[-1]

def expected_frequency_range(
    expected_midi: int,
    global_fmin_hz: float,
    global_fmax_hz: float,
    semitones: float = LOCAL_SEARCH_SEMITONES,
) -> tuple[float, float]:
    """
    Build a local pitch-search range around the expected MIDI note.

    The global minimum and maximum still act as hard safety limits.
    """
    if global_fmin_hz <= 0:
        raise ValueError(
            f"fmin_hz must be positive, got {global_fmin_hz}"
        )

    if global_fmax_hz <= global_fmin_hz:
        raise ValueError(
            "fmax_hz must be greater than fmin_hz: "
            f"{global_fmin_hz} >= {global_fmax_hz}"
        )

    if semitones <= 0:
        raise ValueError(
            f"Search semitones must be positive, got {semitones}"
        )

    expected_hz = midi_to_frequency(expected_midi)
    frequency_ratio = 2.0 ** (semitones / 12.0)

    local_fmin_hz = expected_hz / frequency_ratio
    local_fmax_hz = expected_hz * frequency_ratio

    effective_fmin_hz = max(global_fmin_hz, local_fmin_hz)
    effective_fmax_hz = min(global_fmax_hz, local_fmax_hz)

    if effective_fmin_hz >= effective_fmax_hz:
        raise ValueError(
            f"Invalid pitch-search range for MIDI {expected_midi}: "
            f"{effective_fmin_hz:.3f}–{effective_fmax_hz:.3f} Hz"
        )

    return effective_fmin_hz, effective_fmax_hz


def decode_record(
    source: Path,
    destination: Path,
    overwrite: bool = False,
) -> None:
    """Decode a source recording to 24-bit PCM WAV with ffmpeg."""
    if destination.exists() and not overwrite:
        return

    destination.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y" if overwrite else "-n",
        "-i",
        str(source),
        "-map_metadata",
        "0",
        "-c:a",
        "pcm_s24le",
        str(destination),
    ]

    subprocess.run(command, check=True)


def inspect_audio(path: Path) -> AudioMetadata:
    """Read basic metadata and peak information from a decoded WAV file."""
    info = sf.info(path)
    audio, _ = sf.read(
        path,
        dtype="float32",
        always_2d=True,
    )

    peak = float(np.max(np.abs(audio))) if audio.size else 0.0

    return AudioMetadata(
        sample_rate=info.samplerate,
        channels=info.channels,
        frames=info.frames,
        duration_seconds=info.duration,
        peak=peak,
        clipped=peak >= 0.9999,
    )


def estimate_fundamental_with_yin(
    audio: np.ndarray,
    sample_rate: int,
    *,
    fmin_hz: float,
    fmax_hz: float,
    frame_length: int,
    hop_length: int,
) -> tuple[float, float]:
    """
    Use constrained YIN as a fallback when pYIN produces no voiced frames.

    librosa.yin does not return a voiced probability. The confidence
    returned here is based on the proportion and consistency of frames
    close to the median estimate.
    """
    yin_f0 = librosa.yin(
        audio,
        sr=sample_rate,
        fmin=fmin_hz,
        fmax=fmax_hz,
        frame_length=frame_length,
        hop_length=hop_length,
    )

    yin_values = np.asarray(yin_f0, dtype=float)
    finite = yin_values[np.isfinite(yin_values)]

    if finite.size == 0:
        raise ValueError(
            "YIN produced no finite frequency estimates"
        )

    # YIN often returns exactly fmin or fmax for noise, silence, or frames
    # without a clear periodic signal. Discard values close to the search
    # boundaries.
    boundary_margin_cents = 5.0
    lower_boundary_hz = (
        fmin_hz
        * 2.0 ** (boundary_margin_cents / 1200.0)
    )
    upper_boundary_hz = (
        fmax_hz
        / 2.0 ** (boundary_margin_cents / 1200.0)
    )

    interior = finite[
        (finite > lower_boundary_hz)
        & (finite < upper_boundary_hz)
    ]

    if interior.size == 0:
        raise ValueError(
            "All YIN estimates were at the search boundaries"
        )

    initial_median_hz = float(np.median(interior))

    cents_from_median = np.abs(
        1200.0
        * np.log2(interior / initial_median_hz)
    )

    consistency_threshold_cents = 35.0
    consistent = interior[
        cents_from_median <= consistency_threshold_cents
    ]

    if consistent.size == 0:
        raise ValueError(
            "YIN produced no mutually consistent estimates"
        )

    estimated_f0_hz = float(np.median(consistent))

    if (
        not math.isfinite(estimated_f0_hz)
        or estimated_f0_hz <= 0
    ):
        raise ValueError(
            "YIN produced an invalid fundamental frequency"
        )

    # librosa.yin does not provide voiced_probability. Use two measurable
    # quantities as a conservative fallback confidence:
    #
    # 1. How many finite interior estimates agree with the median.
    # 2. How many total YIN frames produced an interior estimate.
    consistency_ratio = (
        consistent.size / interior.size
    )
    usable_frame_ratio = (
        interior.size / yin_values.size
    )

    confidence = float(
        consistency_ratio * usable_frame_ratio
    )

    return estimated_f0_hz, confidence

def estimate_fundamental(
    path: Path,
    expected_midi: int,
    fmin_hz: float = 25.0,
    fmax_hz: float = 5000.0,
) -> tuple[float, float]:
    """
    Estimate the fundamental frequency near an already known piano key.

    The expected MIDI value is used as an anchor so that pYIN cannot
    accidentally select a strong second or third harmonic far away from
    the true fundamental.
    """
    audio, sample_rate = librosa.load(
        path,
        sr=None,
        mono=True,
    )

    if audio.size == 0:
        raise ValueError(f"Empty audio: {path}")

    if sample_rate <= 0:
        raise ValueError(
            f"Invalid sample rate {sample_rate}: {path}"
        )

    audio, _ = librosa.effects.trim(
        audio,
        top_db=45,
    )

    if len(audio) < sample_rate // 10:
        raise ValueError(
            f"Audio is too short after trimming: {path}"
        )

    expected_hz = midi_to_frequency(expected_midi)

    effective_fmin_hz, effective_fmax_hz = expected_frequency_range(
        expected_midi=expected_midi,
        global_fmin_hz=fmin_hz,
        global_fmax_hz=fmax_hz,
    )

    frame_length = choose_frame_length(
        sample_rate=sample_rate,
        expected_frequency_hz=expected_hz,
    )

    hop_length = frame_length // 4

    # librosa requires fmax to remain below the Nyquist frequency.
    nyquist_hz = sample_rate / 2.0
    effective_fmax_hz = min(
        effective_fmax_hz,
        nyquist_hz * 0.99,
    )

    if effective_fmin_hz >= effective_fmax_hz:
        raise ValueError(
            f"Pitch range exceeds Nyquist limit for {path}: "
            f"{effective_fmin_hz:.3f}–{effective_fmax_hz:.3f} Hz"
        )

    f0, voiced_flag, voiced_probability = librosa.pyin(
        audio,
        sr=sample_rate,
        fmin=effective_fmin_hz,
        fmax=effective_fmax_hz,
        frame_length=frame_length,
        hop_length=hop_length,
        max_transition_rate=MAX_TRANSITION_RATE,
    )

    f0_values = np.asarray(f0, dtype=float)
    voiced_flags = np.asarray(voiced_flag, dtype=bool)
    probabilities = np.asarray(
        voiced_probability,
        dtype=float,
    )

    finite_and_voiced = (
        np.isfinite(f0_values)
        & voiced_flags
        & np.isfinite(probabilities)
    )

    reliable = (
        finite_and_voiced
        & (probabilities >= VOICED_PROBABILITY_MIN)
    )

    if np.any(reliable):
        selected = reliable
    elif np.any(finite_and_voiced):
        # Preserve a usable result for quiet or difficult piano samples.
        # The returned confidence still exposes the low-certainty result.
        selected = finite_and_voiced
    else:
        try:
            return estimate_fundamental_with_yin(
                audio,
                sample_rate,
                fmin_hz=effective_fmin_hz,
                fmax_hz=effective_fmax_hz,
                frame_length=frame_length,
                hop_length=hop_length,
            )
        except ValueError as exc:
            raise ValueError(
                f"No reliable fundamental detected: {path}; "
                f"pYIN produced no voiced frames and "
                f"YIN fallback failed: {exc}"
            ) from exc

    selected_f0 = f0_values[selected]
    selected_probabilities = probabilities[selected]

    estimated_f0_hz = float(np.median(selected_f0))
    confidence = float(np.median(selected_probabilities))

    if not math.isfinite(estimated_f0_hz) or estimated_f0_hz <= 0:
        raise ValueError(
            f"Invalid fundamental frequency detected: {path}"
        )

    return estimated_f0_hz, confidence


def _estimate_with_yin(
    audio: np.ndarray,
    sample_rate: int,
    *,
    fmin_hz: float,
    fmax_hz: float,
    frame_length: int,
    hop_length: int,
) -> tuple[float, float]:
    """
    Estimate a constrained fundamental with YIN.

    This is used when pYIN does not produce sufficiently reliable voiced
    frames. The returned confidence is deliberately conservative because
    librosa.yin does not return a voiced probability.
    """
    yin_f0 = librosa.yin(
        audio,
        sr=sample_rate,
        fmin=fmin_hz,
        fmax=fmax_hz,
        frame_length=frame_length,
        hop_length=hop_length,
    )

    finite = yin_f0[np.isfinite(yin_f0)]

    if finite.size == 0:
        raise ValueError(
            "YIN did not produce a finite fundamental estimate"
        )

    # Reject estimates pressed against the search boundaries. These are
    # commonly produced by unpitched or silent frames.
    lower_guard = fmin_hz * (2.0 ** (5.0 / 1200.0))
    upper_guard = fmax_hz / (2.0 ** (5.0 / 1200.0))

    interior = finite[
        (finite > lower_guard)
        & (finite < upper_guard)
    ]

    if interior.size == 0:
        raise ValueError(
            "YIN estimates were confined to the search boundaries"
        )

    median_hz = float(np.median(interior))

    cents_from_median = np.abs(
        1200.0 * np.log2(interior / median_hz)
    )

    consistent = interior[cents_from_median <= 35.0]

    if consistent.size == 0:
        raise ValueError(
            "YIN did not produce a stable fundamental estimate"
        )

    f0_hz = float(np.median(consistent))

    # YIN has no voiced probability. Use the proportion of mutually
    # consistent frames as a conservative fallback confidence.
    confidence = float(
        consistent.size / max(interior.size, 1)
    )

    return f0_hz, confidence

def _remove_previous_analysis_notes(notes: list[str]) -> list[str]:
    """
    Remove messages generated by an earlier analysis run while preserving
    discovery-time/manual review notes.
    """
    generated_prefixes = (
        "Detected MIDI ",
        "Pitch offset ",
        "Decoded recording reaches clipping threshold",
        "Processing failed:",
    )

    return [
        note
        for note in notes
        if not note.startswith(generated_prefixes)
    ]


def decode_and_analyze_manifest(
    manifest: DatasetManifest,
    cents_review_threshold: float = 35.0,
    fmin_hz: float = 25.0,
    fmax_hz: float = 5000.0,
    overwrite: bool = False,
) -> DatasetManifest:
    """Decode and perform expected-MIDI-anchored pitch analysis."""
    decoded_root = Path(manifest.decoded_root)

    for record in manifest.records:
        # Avoid accumulating duplicate messages after --overwrite runs.
        AUTOMATIC_REVIEW_PREFIXES = (
            "Processing failed:",
            "Detected MIDI ",
            "Pitch error ",
            "Detection confidence ",
        )
        record.review_notes = [
            note
            for note in record.review_notes
            if not note.startswith("Processing failed:")
        ]
        try:
            source = Path(record.source_path)
            destination = decoded_root / f"{record.record_id}.wav"

            decode_record(
                source,
                destination,
                overwrite=overwrite,
            )

            record.decoded_path = str(destination.resolve())
            record.decoded_sha256 = sha256_file(destination)
            record.audio = inspect_audio(destination)
            record.status = RecordStatus.DECODED

            sample_rate = int(librosa.get_samplerate(destination))
            f0_hz, confidence = estimate_fundamental(
                destination,
                expected_midi=record.midi_expected,
                fmin_hz=fmin_hz,
                fmax_hz=fmax_hz,
            )

            detected_midi = frequency_to_nearest_midi(f0_hz)

            # This must be measured relative to the manifest's expected
            # piano key, not relative to the nearest detected MIDI note.
            cents = pitch_error_cents(
                f0_hz,
                record.midi_expected,
            )

            expected_hz = midi_to_frequency(
                record.midi_expected
            )
            effective_fmin_hz, effective_fmax_hz = (
                expected_frequency_range(
                    expected_midi=record.midi_expected,
                    global_fmin_hz=fmin_hz,
                    global_fmax_hz=fmax_hz,
                )
            )
            frame_length = choose_frame_length(
                sample_rate=sample_rate,
                expected_frequency_hz=expected_hz,
            )

            record.detected_f0_hz = f0_hz
            record.midi_detected = detected_midi
            record.pitch_error_cents = cents
            record.detection_confidence = confidence

            record.analysis = AnalysisMetadata(
                algorithm=ANALYSIS_ALGORITHM,
                algorithm_version=ANALYSIS_VERSION,
                parameters={
                    "global_fmin_hz": fmin_hz,
                    "global_fmax_hz": fmax_hz,
                    "effective_fmin_hz": effective_fmin_hz,
                    "effective_fmax_hz": effective_fmax_hz,
                    "expected_midi": record.midi_expected,
                    "expected_frequency_hz": expected_hz,
                    "local_search_semitones": LOCAL_SEARCH_SEMITONES,
                    "frame_length": frame_length,
                    "hop_length": frame_length // 4,
                    "voiced_probability_min": VOICED_PROBABILITY_MIN,
                    "max_transition_rate": MAX_TRANSITION_RATE,
                },
                source_sha256=record.source_sha256,
            )

            reasons: list[str] = []

            if detected_midi != record.midi_expected:
                reasons.append(
                    f"Detected MIDI {detected_midi}, "
                    f"expected {record.midi_expected}"
                )
            elif abs(cents) > cents_review_threshold:
                reasons.append(
                    f"Pitch offset {cents:+.2f} cents "
                    f"exceeds threshold "
                    f"{cents_review_threshold:.2f}"
                )

            if record.audio.clipped:
                reasons.append(
                    "Decoded recording reaches clipping threshold"
                )

            if confidence < DETECTION_CONFIDENCE_REVIEW_THRESHOLD:
                reasons.append(
                    f"Detection confidence {confidence:.3f} is below "
                    f"threshold "
                    f"{DETECTION_CONFIDENCE_REVIEW_THRESHOLD:.3f}"
                )

            for reason in reasons:
                if reason not in record.review_notes:
                    record.review_notes.append(reason)
            record.status = (
                RecordStatus.REVIEW
                if reasons
                else RecordStatus.ANALYZED
            )

        except Exception as exc:
            record.detected_f0_hz = None
            record.midi_detected = None
            record.pitch_error_cents = None
            record.detection_confidence = None
            record.analysis = None
            logger.exception(
                "Failed to process record %s",
                record.record_id,
            )
            record.status = RecordStatus.REVIEW
            record.review_notes.append(
                f"Processing failed: {exc}"
            )

    return manifest


def accept_detected_mapping(
    manifest: DatasetManifest,
) -> DatasetManifest:
    """
    Verify only records whose detected MIDI agrees with the sequence-based
    expected MIDI mapping.

    A mismatched automatic detection must not overwrite the known 88-key
    sequence mapping.
    """
    for record in manifest.records:
        if record.decoded_path is None:
            continue

        if record.midi_detected is None:
            record.status = RecordStatus.REVIEW
            continue

        if record.midi_detected != record.midi_expected:
            message = (
                f"Detected MIDI {record.midi_detected}, "
                f"expected {record.midi_expected}"
            )

            if message not in record.review_notes:
                record.review_notes.append(message)

            record.midi_final = None
            record.status = RecordStatus.REVIEW
            continue

        record.midi_final = record.midi_expected
        record.scientific_name = midi_to_scientific_name(
            record.midi_final
        )
        record.status = RecordStatus.VERIFIED

    return manifest


def accept_expected_mapping(
    manifest: DatasetManifest,
) -> DatasetManifest:
    """
    Verify the known sequence-based 88-key mapping after manual review.

    midi_detected is preserved as diagnostic evidence. The final mapping
    is derived from sequence_index and must agree with midi_expected.
    """
    for record in manifest.records:
        expected_midi = sequence_to_expected_midi(
            record.sequence_index
        )

        if record.midi_expected != expected_midi:
            message = (
                f"Stored expected MIDI {record.midi_expected}, "
                f"sequence requires {expected_midi}"
            )
            if message not in record.review_notes:
                record.review_notes.append(message)

            record.midi_final = None
            record.scientific_name = None
            record.status = RecordStatus.REVIEW
            continue

        if (
            record.decoded_path is None
            or record.detected_f0_hz is None
            or record.analysis is None
        ):
            message = (
                "Cannot verify expected mapping without decoded "
                "audio and completed pitch analysis"
            )
            if message not in record.review_notes:
                record.review_notes.append(message)

            record.midi_final = None
            record.scientific_name = None
            record.status = RecordStatus.REVIEW
            continue

        was_review = record.status == RecordStatus.REVIEW

        record.midi_final = expected_midi
        record.scientific_name = midi_to_scientific_name(
            expected_midi
        )
        record.status = RecordStatus.VERIFIED

        if was_review:
            verification_note = (
                "Sequence mapping manually verified; final MIDI uses "
                "the known 88-key order."
            )
            if verification_note not in record.review_notes:
                record.review_notes.append(verification_note)

    return manifest