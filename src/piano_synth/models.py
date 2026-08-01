from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecordStatus(StrEnum):
    DISCOVERED = "discovered"
    DECODED = "decoded"
    ANALYZED = "analyzed"
    REVIEW = "review"
    VERIFIED = "verified"
    REJECTED = "rejected"


class AnalysisMetadata(BaseModel):
    algorithm: str
    algorithm_version: str
    parameters: dict[str, float | int | str]
    source_sha256: str


class AudioMetadata(BaseModel):
    sample_rate: int
    channels: int
    frames: int
    duration_seconds: float
    peak: float
    clipped: bool


class KeyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    sequence_index: int = Field(ge=1, le=88)
    source_path: str
    source_sha256: str
    source_label: str | None = None

    decoded_path: str | None = None
    decoded_sha256: str | None = None
    audio: AudioMetadata | None = None

    midi_expected: int = Field(ge=21, le=108)
    detected_f0_hz: float | None = Field(default=None, gt=0)
    midi_detected: int | None = None
    pitch_error_cents: float | None = None
    detection_confidence: float | None = Field(default=None, ge=0, le=1)

    midi_final: int | None = Field(default=None, ge=21, le=108)
    scientific_name: str | None = None
    status: RecordStatus = RecordStatus.DISCOVERED
    review_notes: list[str] = Field(default_factory=list)
    analysis: AnalysisMetadata | None = None

    @model_validator(mode="after")
    def verified_record_is_complete(self) -> KeyRecord:
        if self.status == RecordStatus.VERIFIED:
            if self.midi_final is None or self.scientific_name is None:
                raise ValueError("Verified records require midi_final and scientific_name")
            if self.decoded_path is None or self.decoded_sha256 is None:
                raise ValueError("Verified records require a decoded WAV")
        return self


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    dataset_version: str = "0.1.0"
    dataset_id: str = "piano-88keys"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_root: str
    decoded_root: str
    expected_midi_min: int = 21
    expected_midi_max: int = 108
    records: list[KeyRecord]

    @model_validator(mode="after")
    def reject_duplicate_identities(self) -> DatasetManifest:
        record_ids = [record.record_id for record in self.records]
        indexes = [record.sequence_index for record in self.records]

        if len(record_ids) != len(set(record_ids)):
            raise ValueError("Duplicate record_id in manifest")
        if len(indexes) != len(set(indexes)):
            raise ValueError("Duplicate sequence_index in manifest")
        return self


class NoteEvent(BaseModel):
    pitch: int = Field(ge=21, le=108)
    start_beat: float = Field(ge=0)
    duration_beats: float = Field(gt=0)
    velocity: int = Field(ge=1, le=127)
    track_id: str = "piano"


class PedalEvent(BaseModel):
    beat: float = Field(ge=0)
    value: int = Field(ge=0, le=127)


class Track(BaseModel):
    track_id: str
    name: str
    gain_db: float = 0.0
    pan: float = Field(default=0.0, ge=-1.0, le=1.0)
    notes: list[NoteEvent] = Field(default_factory=list)
    pedal: list[PedalEvent] = Field(default_factory=list)


class TempoPoint(BaseModel):
    beat: float = Field(ge=0)
    bpm: float = Field(gt=0)


class RenderProject(BaseModel):
    sample_rate: int = Field(default=48000, ge=8000, le=192000)
    tempo: list[TempoPoint] = Field(default_factory=lambda: [TempoPoint(beat=0, bpm=120)])
    tracks: list[Track]