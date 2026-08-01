from __future__ import annotations

from dataclasses import dataclass

from .models import RenderProject
from .timing import TempoMap


@dataclass(frozen=True)
class ProjectIssue:
    severity: str
    code: str
    message: str


def validate_project(project: RenderProject) -> list[ProjectIssue]:
    issues: list[ProjectIssue] = []
    track_ids = [track.track_id for track in project.tracks]

    if len(track_ids) != len(set(track_ids)):
        issues.append(
            ProjectIssue("ERROR", "DUPLICATE_TRACK", "track_id必须唯一")
        )

    if not project.tracks:
        issues.append(ProjectIssue("WARNING", "EMPTY_PROJECT", "工程没有音轨"))

    tempo_map = TempoMap(project.tempo)

    for track in project.tracks:
        if not track.notes:
            issues.append(
                ProjectIssue(
                    "INFO",
                    "EMPTY_TRACK",
                    f"音轨{track.track_id!r}没有音符",
                )
            )

        pedal_beats = [event.beat for event in track.pedal]
        if pedal_beats != sorted(pedal_beats):
            issues.append(
                ProjectIssue(
                    "WARNING",
                    "UNSORTED_PEDAL",
                    f"音轨{track.track_id!r}的踏板事件未排序",
                )
            )

        ordered_notes = sorted(
            track.notes,
            key=lambda note: (note.pitch, note.start_beat),
        )

        for note in track.notes:
            if note.track_id != track.track_id:
                issues.append(
                    ProjectIssue(
                        "ERROR",
                        "TRACK_MISMATCH",
                        f"音符track_id={note.track_id!r}，"
                        f"但位于音轨{track.track_id!r}",
                    )
                )

            duration_seconds = (
                tempo_map.beat_to_seconds(
                    note.start_beat + note.duration_beats
                )
                - tempo_map.beat_to_seconds(note.start_beat)
            )
            if duration_seconds < 0.01:
                issues.append(
                    ProjectIssue(
                        "WARNING",
                        "VERY_SHORT_NOTE",
                        f"MIDI {note.pitch}时值小于10 ms",
                    )
                )

        previous_by_pitch: dict[int, float] = {}
        for note in ordered_notes:
            previous_end = previous_by_pitch.get(note.pitch)
            if previous_end is not None and note.start_beat < previous_end:
                issues.append(
                    ProjectIssue(
                        "INFO",
                        "SAME_PITCH_OVERLAP",
                        f"音轨{track.track_id!r}中MIDI {note.pitch}"
                        "存在合法但需留意的同音重叠",
                    )
                )
            previous_by_pitch[note.pitch] = max(
                previous_end or 0.0,
                note.start_beat + note.duration_beats,
            )

    return issues