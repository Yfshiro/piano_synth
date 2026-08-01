from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import mido
import yaml

def round_beat(value: float, digits: int = 6) -> int | float:
    """精简拍数，避免输出大量浮点误差。"""
    rounded = round(value, digits)

    if abs(rounded - round(rounded)) < 10 ** (-digits):
        return int(round(rounded))

    return rounded

def make_track_id(index: int, name: str) -> str:
    """根据 MIDI 轨道名称生成唯一、可读的 track_id。"""
    cleaned = re.sub(r"[^0-9a-zA-Z_\-]+", "_", name.strip()).strip("_")

    if not cleaned:
        cleaned = f"track_{index + 1}"

    return f"{cleaned}_{index + 1}".lower()

def default_pan(index: int, total: int) -> float:
    """给多轨 MIDI 设置轻微声像，避免所有轨道完全重叠。"""
    if total <= 1:
        return 0.0

    if total == 2:
        return -0.2 if index == 0 else 0.2

    position = index / (total - 1)
    return round(-0.3 + position * 0.6, 3)

def extract_tempo(mid: mido.MidiFile) -> list[dict[str, Any]]:
    """从整个 MIDI 中提取速度变化事件。"""
    tempo_events = []

    for track_index, track in enumerate(mid.tracks):
        absolute_tick = 0

        for message_index, message in enumerate(track):
            absolute_tick += message.time

            if message.type == "set_tempo":
                bpm = mido.tempo2bpm(message.tempo)

                tempo_events.append(
                    {
                        "_tick": absolute_tick,
                        "_track": track_index,
                        "_order": message_index,
                        "beat": round_beat(
                            absolute_tick / mid.ticks_per_beat
                        ),
                        "bpm": round(float(bpm), 6),
                    }
                )

    tempo_events.sort(
        key=lambda item: (
            item["_tick"],
            item["_track"],
            item["_order"],
        )
    )

    # 同一个 tick 若有多个速度事件，采用最后一个。
    by_tick = {}

    for event in tempo_events:
        by_tick[event["_tick"]] = event

    result = []

    for tick in sorted(by_tick):
        event = by_tick[tick]
        bpm = event["bpm"]

        if abs(bpm - round(bpm)) < 1e-6:
            bpm = int(round(bpm))

        result.append(
            {
                "beat": event["beat"],
                "bpm": bpm,
            }
        )

    # MIDI 中没有速度信息时，按照标准默认速度 120 BPM。
    if not result:
        result.append(
            {
                "beat": 0,
                "bpm": 120,
            }
        )

    # 格式要求通常应从第 0 拍定义速度。
    elif result[0]["beat"] != 0:
        result.insert(
            0,
            {
                "beat": 0,
                "bpm": 120,
            },
        )

    return result

def extract_track_name(track: mido.MidiTrack, index: int) -> str:
    for message in track:
        if message.type == "track_name" and message.name.strip():
            return message.name.strip()

    return f"Track {index + 1}"

def extract_track_events(
    track: mido.MidiTrack,
    ticks_per_beat: int,
    track_id: str,
    include_drums: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    提取单条 MIDI 轨道的音符和延音踏板。

    活跃音符使用 (channel, pitch) 作为键，并以队列方式处理
    同音高重叠音符。
    """
    absolute_tick = 0
    active_notes: dict[tuple[int, int], list[dict[str, int]]] = defaultdict(list)

    notes = []
    pedal = []

    for message in track:
        absolute_tick += message.time

        channel = getattr(message, "channel", 0)
        is_drum_channel = channel == 9

        if is_drum_channel and not include_drums:
            continue

        if message.type == "note_on" and message.velocity > 0:
            active_notes[(channel, message.note)].append(
                {
                    "start_tick": absolute_tick,
                    "velocity": message.velocity,
                }
            )

        elif (
            message.type == "note_off"
            or (
                message.type == "note_on"
                and message.velocity == 0
            )
        ):
            key = (channel, message.note)

            if active_notes[key]:
                started = active_notes[key].pop(0)
                start_tick = started["start_tick"]
                duration_ticks = absolute_tick - start_tick

                if duration_ticks <= 0:
                    continue

                # 只保留标准 88 键钢琴范围。
                if not 21 <= message.note <= 108:
                    continue

                notes.append(
                    {
                        "pitch": int(message.note),
                        "start_beat": round_beat(
                            start_tick / ticks_per_beat
                        ),
                        "duration_beats": round_beat(
                            duration_ticks / ticks_per_beat
                        ),
                        "velocity": int(started["velocity"]),
                        "track_id": track_id,
                    }
                )

        elif (
            message.type == "control_change"
            and message.control == 64
        ):
            pedal.append(
                {
                    "beat": round_beat(
                        absolute_tick / ticks_per_beat
                    ),
                    "value": int(message.value),
                }
            )

    notes.sort(
        key=lambda item: (
            item["start_beat"],
            item["pitch"],
            item["duration_beats"],
        )
    )

    pedal.sort(key=lambda item: item["beat"])

    return notes, pedal

def remove_duplicate_pedal_events(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    精简连续状态相同的踏板事件。

    CC64 的具体数值仍保留；只有相邻事件数值完全一致时才删除。
    """
    result = []
    previous_value = None

    for event in events:
        if event["value"] == previous_value:
            continue

        result.append(event)
        previous_value = event["value"]

    return result

def convert_midi(
    input_path: Path,
    output_path: Path,
    sample_rate: int = 48000,
    include_drums: bool = False,
) -> None:
    mid = mido.MidiFile(str(input_path))

    extracted_tracks = []

    for midi_track_index, midi_track in enumerate(mid.tracks):
        name = extract_track_name(midi_track, midi_track_index)
        track_id = make_track_id(midi_track_index, name)

        notes, pedal = extract_track_events(
            track=midi_track,
            ticks_per_beat=mid.ticks_per_beat,
            track_id=track_id,
            include_drums=include_drums,
        )

        # 忽略仅包含元信息、没有音符和踏板的 MIDI 轨道。
        if not notes and not pedal:
            continue

        extracted_tracks.append(
            {
                "track_id": track_id,
                "name": name,
                "notes": notes,
                "pedal": remove_duplicate_pedal_events(pedal),
            }
        )

    score_tracks = []

    for index, track in enumerate(extracted_tracks):
        score_track = {
            "track_id": track["track_id"],
            "name": track["name"],
            "gain_db": -3.0,
            "pan": default_pan(index, len(extracted_tracks)),
            "notes": track["notes"],
            "pedal": track["pedal"],
        }

        score_tracks.append(score_track)

    score = {
        "sample_rate": sample_rate,
        "tempo": extract_tempo(mid),
        "tracks": score_tracks,
    }

    with output_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(
            score,
            file,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=1000,
        )

    total_notes = sum(len(track["notes"]) for track in score_tracks)
    total_pedal = sum(len(track["pedal"]) for track in score_tracks)

    print(f"转换完成：{output_path}")
    print(f"MIDI PPQ：{mid.ticks_per_beat}")
    print(f"有效轨道：{len(score_tracks)}")
    print(f"音符总数：{total_notes}")
    print(f"踏板事件：{total_pedal}")
    print(f"速度事件：{len(score['tempo'])}")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="将 MIDI 文件转换为钢琴模拟程序使用的 YAML 乐谱。"
    )

    parser.add_argument(
        "input",
        type=Path,
        help="输入 MIDI 文件路径",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="输出 YAML 文件路径",
    )

    parser.add_argument(
        "--sample-rate",
        type=int,
        default=48000,
        help="输出采样率，默认为 48000",
    )

    parser.add_argument(
        "--include-drums",
        action="store_true",
        help="保留 MIDI 第 10 通道的打击乐事件",
    )

    args = parser.parse_args()

    input_path = args.input

    if not input_path.exists():
        raise FileNotFoundError(f"找不到 MIDI 文件：{input_path}")

    if args.output is None:
        output_path = input_path.with_suffix(".yaml")
    else:
        output_path = args.output

    convert_midi(
        input_path=input_path,
        output_path=output_path,
        sample_rate=args.sample_rate,
        include_drums=args.include_drums,
    )
# python .\midi\midi_read.py ".\midi\千本樱.mid" -o ".\examples\千本樱.yaml"

# 假设 MIDI 文件位于项目目录 D:\code\python\midi，在 PowerShell 中执行：
# & C:\Users\LENOVO\.conda\envs\music\python.exe `
#   D:\code\python\midi\midi_read.py `
#   "D:\code\python\midi\千本樱.mid" `
#   -o "D:\code\python\piano_synth\examples\千本樱.yaml"

# 如果文件不在当前目录，将 MIDI 文件实际路径替换进去。可以先查看当前目录下的 MIDI 文件名：

if __name__ == "__main__":
    main()
