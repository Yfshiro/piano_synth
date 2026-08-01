from __future__ import annotations

import math
import re
from dataclasses import dataclass

NOTE_NAMES = (
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B",
)

MIDI_MIN = 0
MIDI_MAX = 127

PIANO_MIDI_MIN = 21
PIANO_MIDI_MAX = 108
PIANO_KEY_COUNT = 88

A4_MIDI = 69
A4_FREQUENCY_HZ = 440.0

SCIENTIFIC_PITCH_PATTERN = re.compile(
    r"^(?P<note>[A-G])(?P<sharp>#?)(?P<octave>-?\d+)$"
)

@dataclass(frozen=True)
class ParsedPitch:
    label: str
    note_name: str
    octave: int
    midi: int

def validate_midi(midi: int) -> None:
    """Validate that a MIDI note belongs to the standard 88-key piano."""
    if isinstance(midi, bool) or not isinstance(midi, int):
        raise TypeError(
            f"Piano MIDI must be an integer, got {type(midi).__name__}"
        )

    if not PIANO_MIDI_MIN <= midi <= PIANO_MIDI_MAX:
        raise ValueError(
            f"Piano MIDI must be in "
            f"[{PIANO_MIDI_MIN}, {PIANO_MIDI_MAX}], got {midi}"
        )

def validate_general_midi(midi: int) -> None:
    """Validate a MIDI note against the complete MIDI note range."""
    if isinstance(midi, bool) or not isinstance(midi, int):
        raise TypeError(
            f"MIDI note must be an integer, got {type(midi).__name__}"
        )

    if not MIDI_MIN <= midi <= MIDI_MAX:
        raise ValueError(
            f"MIDI note must be in [{MIDI_MIN}, {MIDI_MAX}], got {midi}"
        )

def validate_frequency(frequency_hz: float) -> None:
    """Validate that a frequency is finite and positive."""
    if isinstance(frequency_hz, bool) or not isinstance(
        frequency_hz,
        (int, float),
    ):
        raise TypeError(
            "Frequency must be a real number, "
            f"got {type(frequency_hz).__name__}"
        )

    if not math.isfinite(frequency_hz) or frequency_hz <= 0:
        raise ValueError(
            f"Frequency must be finite and positive, got {frequency_hz}"
        )

def midi_to_frequency(midi: int) -> float:
    """Convert a MIDI note number to equal-tempered frequency in Hz."""
    validate_general_midi(midi)

    return A4_FREQUENCY_HZ * (
        2.0 ** ((midi - A4_MIDI) / 12.0)
    )

def frequency_to_midi_float(frequency_hz: float) -> float:
    """Convert a frequency to a fractional MIDI note number."""
    validate_frequency(frequency_hz)

    return A4_MIDI + 12.0 * math.log2(
        frequency_hz / A4_FREQUENCY_HZ
    )

def frequency_to_nearest_midi(frequency_hz: float) -> int:
    """Convert a frequency to its nearest MIDI note number."""
    midi_float = frequency_to_midi_float(frequency_hz)

    # Adding 0.5 and taking floor avoids Python's banker's-rounding
    # behavior exactly at a semitone midpoint.
    midi = math.floor(midi_float + 0.5)

    if not MIDI_MIN <= midi <= MIDI_MAX:
        raise ValueError(
            f"Frequency {frequency_hz} Hz is outside the MIDI range"
        )

    return midi

def pitch_error_cents(
    frequency_hz: float,
    midi: int,
) -> float:
    """
    Measure a frequency's offset from a supplied MIDI reference.

    A positive result means the measured frequency is sharp.
    A negative result means it is flat.
    """
    validate_frequency(frequency_hz)
    reference_hz = midi_to_frequency(midi)

    return 1200.0 * math.log2(
        frequency_hz / reference_hz
    )

def midi_to_scientific_name(midi: int) -> str:
    """Convert a MIDI note to scientific pitch notation."""
    validate_general_midi(midi)

    octave = midi // 12 - 1
    return f"{NOTE_NAMES[midi % 12]}{octave}"

def scientific_name_to_midi(label: str) -> int:
    """Convert scientific pitch notation, such as C#4, to MIDI."""
    if not isinstance(label, str):
        raise TypeError(
            f"Pitch label must be a string, got {type(label).__name__}"
        )

    normalized = label.strip()
    match = SCIENTIFIC_PITCH_PATTERN.fullmatch(normalized)

    if match is None:
        raise ValueError(
            f"Invalid scientific pitch label {label!r}; "
            "expected forms such as A0, C#4 or C8"
        )

    note_name = (
        f"{match.group('note')}{match.group('sharp')}"
    )
    octave = int(match.group("octave"))

    note_index = NOTE_NAMES.index(note_name)
    midi = (octave + 1) * 12 + note_index

    if not MIDI_MIN <= midi <= MIDI_MAX:
        raise ValueError(
            f"Scientific pitch {label!r} maps outside "
            f"MIDI [{MIDI_MIN}, {MIDI_MAX}]"
        )

    return midi

def parse_scientific_pitch(label: str) -> ParsedPitch:
    """Parse a scientific pitch label into structured pitch data."""
    midi = scientific_name_to_midi(label)

    return ParsedPitch(
        label=label.strip(),
        note_name=NOTE_NAMES[midi % 12],
        octave=midi // 12 - 1,
        midi=midi,
    )

def sequence_to_expected_midi(sequence_index: int) -> int:
    """
    Map the ordered 1–88 piano-key sequence to MIDI 21–108.
    """
    if (
        isinstance(sequence_index, bool)
        or not isinstance(sequence_index, int)
    ):
        raise TypeError(
            "Sequence index must be an integer, "
            f"got {type(sequence_index).__name__}"
        )

    if not 1 <= sequence_index <= PIANO_KEY_COUNT:
        raise ValueError(
            f"Sequence index must be in "
            f"[1, {PIANO_KEY_COUNT}], got {sequence_index}"
        )

    return PIANO_MIDI_MIN + sequence_index - 1

def sequence_to_expected_name(sequence_index: int) -> str:
    """Map the ordered piano-key sequence to scientific pitch notation."""
    return midi_to_scientific_name(
        sequence_to_expected_midi(sequence_index)
    )