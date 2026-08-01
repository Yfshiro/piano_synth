from __future__ import annotations

from dataclasses import dataclass

from .models import TempoPoint


@dataclass(frozen=True)
class TempoSegment:
    start_beat: float
    start_seconds: float
    bpm: float


class TempoMap:
    def __init__(self, points: list[TempoPoint]) -> None:
        if not points:
            raise ValueError("Tempo map cannot be empty")

        ordered = sorted(points, key=lambda point: point.beat)
        if ordered[0].beat != 0:
            raise ValueError("Tempo map must start at beat 0")

        beats = [point.beat for point in ordered]
        if len(beats) != len(set(beats)):
            raise ValueError("Tempo points cannot share the same beat")

        self._segments: list[TempoSegment] = []
        elapsed = 0.0

        for index, point in enumerate(ordered):
            if index:
                previous = ordered[index - 1]
                elapsed += (point.beat - previous.beat) * 60.0 / previous.bpm
            self._segments.append(TempoSegment(point.beat, elapsed, point.bpm))

    def beat_to_seconds(self, beat: float) -> float:
        if beat < 0:
            raise ValueError("Beat cannot be negative")

        segment = self._segments[0]
        for candidate in self._segments:
            if candidate.start_beat > beat:
                break
            segment = candidate

        return segment.start_seconds + (beat - segment.start_beat) * 60.0 / segment.bpm

    def beat_to_sample(self, beat: float, sample_rate: int) -> int:
        return round(self.beat_to_seconds(beat) * sample_rate)