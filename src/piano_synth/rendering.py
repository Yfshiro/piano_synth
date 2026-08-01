from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from .models import DatasetManifest, NoteEvent, RenderProject, Track
from .timing import TempoMap


@dataclass(frozen=True)
class ScheduledNote:
    note: NoteEvent
    start_sample: int
    key_up_sample: int
    damper_sample: int | None
    track_gain: float
    track_pan: float


def db_to_gain(db: float) -> float:
    return 10.0 ** (db / 20.0)


def equal_power_pan(pan: float) -> tuple[float, float]:
    if not -1.0 <= pan <= 1.0:
        raise ValueError("Pan must be in [-1, 1]")
    angle = (pan + 1.0) * math.pi / 4.0
    return math.cos(angle), math.sin(angle)


def velocity_gain(velocity: int, gamma: float = 1.6) -> float:
    if not 1 <= velocity <= 127:
        raise ValueError("Velocity must be in [1, 127]")
    return (velocity / 127.0) ** gamma


def trim_leading_silence(
    audio: np.ndarray,
    threshold_db: float = -55.0,
    pre_roll_samples: int = 32,
) -> np.ndarray:
    if audio.size == 0:
        return audio

    mono_level = np.max(np.abs(audio), axis=1)
    threshold = 10.0 ** (threshold_db / 20.0)
    active = np.flatnonzero(mono_level >= threshold)

    if active.size == 0:
        return audio

    onset = max(0, int(active[0]) - pre_roll_samples)
    return audio[onset:]


def apply_attack_fade(audio: np.ndarray, sample_rate: int, milliseconds: float = 1.0) -> None:
    fade_length = min(
        len(audio),
        max(1, round(sample_rate * milliseconds / 1000.0)),
    )
    audio[:fade_length] *= np.linspace(
        0.0,
        1.0,
        fade_length,
        dtype=np.float32,
    )[:, None]


def apply_damped_release(
    audio: np.ndarray,
    release_start: int,
    release_samples: int,
) -> np.ndarray:
    if release_start >= len(audio):
        return audio

    release_samples = max(1, release_samples)
    available = min(release_samples, len(audio) - release_start)
    output_end = release_start + available
    output = audio[:output_end].copy()

    # 平滑到接近静音，避免键松处产生不连续点击。
    time = np.linspace(0.0, 1.0, available, endpoint=True, dtype=np.float32)
    envelope = np.exp(-7.0 * time).astype(np.float32)
    envelope[-1] = 0.0
    output[release_start:output_end] *= envelope[:, None]
    return output


class SampleLibrary:
    def __init__(
        self,
        manifest: DatasetManifest,
        target_sample_rate: int,
        trim_threshold_db: float = -55.0,
    ) -> None:
        self.target_sample_rate = target_sample_rate
        self.trim_threshold_db = trim_threshold_db
        self.paths: dict[int, Path] = {}

        for record in manifest.records:
            if record.midi_final is not None and record.decoded_path is not None:
                self.paths[record.midi_final] = Path(record.decoded_path)

        expected = set(range(21, 109))
        missing = sorted(expected - set(self.paths))
        if missing:
            raise ValueError(
                f"Sample library is incomplete; missing MIDI mappings: {missing}"
            )

        self._cache: dict[int, np.ndarray] = {}

    def load(self, midi: int) -> np.ndarray:
        if midi in self._cache:
            return self._cache[midi]

        audio, source_rate = sf.read(
            self.paths[midi],
            dtype="float32",
            always_2d=True,
        )

        if not np.all(np.isfinite(audio)):
            raise ValueError(f"Sample MIDI {midi} contains NaN or Inf")

        if source_rate != self.target_sample_rate:
            channels = [
                librosa.resample(
                    audio[:, channel],
                    orig_sr=source_rate,
                    target_sr=self.target_sample_rate,
                    res_type="soxr_hq",
                )
                for channel in range(audio.shape[1])
            ]
            audio = np.column_stack(channels).astype(np.float32)

        if audio.shape[1] == 1:
            audio = np.repeat(audio, 2, axis=1)
        elif audio.shape[1] > 2:
            audio = audio[:, :2]

        audio = trim_leading_silence(
            audio,
            threshold_db=self.trim_threshold_db,
        ).astype(np.float32, copy=True)
        apply_attack_fade(audio, self.target_sample_rate)

        self._cache[midi] = audio
        return audio


def _pedal_release_beat(track: Track, key_up_beat: float) -> float | None:
    events = sorted(track.pedal, key=lambda event: event.beat)
    pedal_down = False

    for event in events:
        if event.beat > key_up_beat:
            break
        pedal_down = event.value >= 64

    if not pedal_down:
        return key_up_beat

    for event in events:
        if event.beat > key_up_beat and event.value < 64:
            return event.beat

    # None表示踏板到曲末都没有抬起，让录音自然衰减。
    return None


def schedule_project(project: RenderProject) -> list[ScheduledNote]:
    tempo_map = TempoMap(project.tempo)
    scheduled: list[ScheduledNote] = []

    for track in project.tracks:
        for note in track.notes:
            if note.track_id != track.track_id:
                raise ValueError(
                    f"Note track_id {note.track_id!r} does not match "
                    f"containing track {track.track_id!r}"
                )

            key_up_beat = note.start_beat + note.duration_beats
            damper_beat = _pedal_release_beat(track, key_up_beat)

            scheduled.append(
                ScheduledNote(
                    note=note,
                    start_sample=tempo_map.beat_to_sample(
                        note.start_beat,
                        project.sample_rate,
                    ),
                    key_up_sample=tempo_map.beat_to_sample(
                        key_up_beat,
                        project.sample_rate,
                    ),
                    damper_sample=(
                        tempo_map.beat_to_sample(
                            damper_beat,
                            project.sample_rate,
                        )
                        if damper_beat is not None
                        else None
                    ),
                    track_gain=db_to_gain(track.gain_db),
                    track_pan=track.pan,
                )
            )

    return sorted(
        scheduled,
        key=lambda item: (item.start_sample, item.note.pitch),
    )


def render_project(
    project: RenderProject,
    library: SampleLibrary,
    master_gain_db: float = -12.0,
    release_seconds: float = 0.35,
    tail_seconds: float = 2.0,
) -> np.ndarray:
    if release_seconds <= 0:
        raise ValueError("release_seconds must be positive")
    if tail_seconds < 0:
        raise ValueError("tail_seconds cannot be negative")

    scheduled = schedule_project(project)
    if not scheduled:
        return np.zeros((1, 2), dtype=np.float32)

    release_samples = max(1, round(release_seconds * project.sample_rate))
    rendered_notes: list[tuple[int, np.ndarray]] = []
    final_sample = 1

    for item in scheduled:
        source = library.load(item.note.pitch)
        local_audio = source.copy()

        if item.damper_sample is not None:
            release_start = max(
                0,
                item.damper_sample - item.start_sample,
            )
            local_audio = apply_damped_release(
                local_audio,
                release_start,
                release_samples,
            )

        gain = velocity_gain(item.note.velocity) * item.track_gain
        left_pan, right_pan = equal_power_pan(item.track_pan)

        local_audio[:, 0] *= gain * left_pan
        local_audio[:, 1] *= gain * right_pan

        rendered_notes.append((item.start_sample, local_audio))
        final_sample = max(final_sample, item.start_sample + len(local_audio))

    final_sample += round(tail_seconds * project.sample_rate)
    output = np.zeros((final_sample, 2), dtype=np.float32)

    for start_sample, note_audio in rendered_notes:
        end_sample = min(final_sample, start_sample + len(note_audio))
        output[start_sample:end_sample] += note_audio[: end_sample - start_sample]

    output *= db_to_gain(master_gain_db)

    if not np.all(np.isfinite(output)):
        raise FloatingPointError("Rendered audio contains NaN or Inf")

    return output


def write_wav(
    path: Path,
    audio: np.ndarray,
    sample_rate: int,
    subtype: str = "FLOAT",
) -> None:
    if audio.ndim != 2 or audio.shape[1] != 2:
        raise ValueError("Output audio must have shape (frames, 2)")
    if not np.all(np.isfinite(audio)):
        raise ValueError("Cannot write audio containing NaN or Inf")

    supported = {"FLOAT", "PCM_16", "PCM_24"}
    if subtype not in supported:
        raise ValueError(f"Subtype must be one of {sorted(supported)}")

    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if subtype != "FLOAT" and peak > 1.0:
        raise ValueError(
            f"Integer PCM export would clip: peak={peak:.6f}. "
            "Reduce master_gain_db explicitly."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio, sample_rate, subtype=subtype)