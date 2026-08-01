如果旋律中间变速，只需要在 YAML 的 `tempo` 列表中增加新的速度点。

每个速度点包含：

```yaml
- beat: 从第几拍开始生效
  bpm: 新的速度
```

例如：

```yaml
tempo:
  - beat: 0
    bpm: 120

  - beat: 8
    bpm: 160

  - beat: 16
    bpm: 80
```

表示：

- 第 `0～8` 拍：120 BPM
- 第 `8～16` 拍：160 BPM
- 第 `16` 拍之后：80 BPM

速度变化不会改变音符的 `start_beat`。音符仍然按照全曲的绝对拍数填写，程序会根据每一段的 BPM 自动换算成秒和采样位置。

---

## 完整示例

下面是一段包含两次变速的完整 YAML：

```yaml
sample_rate: 48000

tempo:
  # 第 0 拍开始：120 BPM
  - beat: 0
    bpm: 120

  # 第 4 拍开始：加速到 180 BPM
  - beat: 4
    bpm: 180

  # 第 8 拍开始：减速到 90 BPM
  - beat: 8
    bpm: 90

tracks:
  - track_id: right
    name: Right Hand
    gain_db: -4.0
    pan: 0.15

    notes:
      # 120 BPM 区间
      - pitch: 60
        start_beat: 0
        duration_beats: 1
        velocity: 90
        track_id: right

      - pitch: 62
        start_beat: 1
        duration_beats: 1
        velocity: 92
        track_id: right

      - pitch: 64
        start_beat: 2
        duration_beats: 1
        velocity: 94
        track_id: right

      - pitch: 65
        start_beat: 3
        duration_beats: 1
        velocity: 96
        track_id: right

      # 从第 4 拍开始变为 180 BPM
      - pitch: 67
        start_beat: 4
        duration_beats: 1
        velocity: 100
        track_id: right

      - pitch: 69
        start_beat: 5
        duration_beats: 1
        velocity: 102
        track_id: right

      - pitch: 71
        start_beat: 6
        duration_beats: 1
        velocity: 104
        track_id: right

      - pitch: 72
        start_beat: 7
        duration_beats: 1
        velocity: 106
        track_id: right

      # 从第 8 拍开始减速为 90 BPM
      - pitch: 72
        start_beat: 8
        duration_beats: 1
        velocity: 100
        track_id: right

      - pitch: 71
        start_beat: 9
        duration_beats: 1
        velocity: 96
        track_id: right

      - pitch: 69
        start_beat: 10
        duration_beats: 1
        velocity: 92
        track_id: right

      - pitch: 67
        start_beat: 11
        duration_beats: 1
        velocity: 88
        track_id: right

    pedal: []

  - track_id: left
    name: Left Hand
    gain_db: -7.0
    pan: -0.15

    notes:
      # 120 BPM 区间
      - pitch: 48
        start_beat: 0
        duration_beats: 4
        velocity: 74
        track_id: left

      # 180 BPM 区间
      - pitch: 43
        start_beat: 4
        duration_beats: 4
        velocity: 80
        track_id: left

      # 90 BPM 区间
      - pitch: 45
        start_beat: 8
        duration_beats: 4
        velocity: 76
        track_id: left

    pedal: []
```

---

## 实际时间如何计算

上述示例中：

### 第 0～4 拍：120 BPM

120 BPM 下，每拍时长为：

```text
60 / 120 = 0.5 秒
```

前 4 拍总时长：

```text
4 × 0.5 = 2 秒
```

因此第 4 拍位于：

```text
2.0 秒
```

### 第 4～8 拍：180 BPM

180 BPM 下，每拍时长为：

```text
60 / 180 = 0.3333 秒
```

这 4 拍的总时长：

```text
4 × 0.3333 ≈ 1.3333 秒
```

因此第 8 拍位于：

```text
2.0 + 1.3333 = 3.3333 秒
```

### 第 8 拍之后：90 BPM

90 BPM 下，每拍时长为：

```text
60 / 90 ≈ 0.6667 秒
```

因此第 12 拍位于：

```text
3.3333 + 4 × 0.6667 ≈ 6.0 秒
```

也就是说，虽然 YAML 中一共有 12 拍，但由于中间发生两次变速，实际音频长度约为 6 秒，而不是简单地用一个 BPM 计算。

---

## 音符跨越变速点时怎么办

假设一个音符从第 3 拍开始，持续 3 拍：

```yaml
- pitch: 60
  start_beat: 3
  duration_beats: 3
  velocity: 90
  track_id: right
```

同时速度设置为：

```yaml
tempo:
  - beat: 0
    bpm: 120

  - beat: 4
    bpm: 180
```

该音符覆盖第 3～6 拍，跨越了第 4 拍的变速点。

实际时长应当分段计算：

```text
第 3～4 拍：
1 × 60 / 120 = 0.5 秒

第 4～6 拍：
2 × 60 / 180 ≈ 0.6667 秒

总时长：
0.5 + 0.6667 ≈ 1.1667 秒
```

YAML 不需要拆成两个音符，仍然写成一个连续音符即可：

```yaml
- pitch: 60
  start_beat: 3
  duration_beats: 3
  velocity: 90
  track_id: right
```

前提是你的 `timing.py` 在计算结束时间时采用：

```python
start_seconds = beat_to_seconds(
    note.start_beat,
    tempo_map,
)

end_seconds = beat_to_seconds(
    note.start_beat + note.duration_beats,
    tempo_map,
)

duration_seconds = end_seconds - start_seconds
```

不要使用：

```python
# 不推荐：跨越变速点时会算错
duration_seconds = (
    note.duration_beats
    * 60
    / current_bpm
)
```

因为后者只使用音符开始时的 BPM，无法正确处理跨越速度变化点的长音。

---

## 渐快或渐慢怎么办

当前 `tempo` 是离散速度点，因此它表达的是“到某一拍立即改变 BPM”。

例如：

```yaml
tempo:
  - beat: 0
    bpm: 120

  - beat: 8
    bpm: 140
```

表示在第 8 拍直接从 120 BPM 跳到 140 BPM。

如果想模拟渐快，可以加入多个速度点：

```yaml
tempo:
  - beat: 0
    bpm: 120

  - beat: 4
    bpm: 126

  - beat: 5
    bpm: 132

  - beat: 6
    bpm: 140

  - beat: 7
    bpm: 150

  - beat: 8
    bpm: 160
```

如果想模拟渐慢：

```yaml
tempo:
  - beat: 0
    bpm: 160

  - beat: 12
    bpm: 150

  - beat: 13
    bpm: 138

  - beat: 14
    bpm: 124

  - beat: 15
    bpm: 108

  - beat: 16
    bpm: 90
```

速度点越密集，渐变听起来越平滑；但是当前模型本质上仍是阶梯式变化。

最后校验并渲染：

```powershell
piano-synth validate-project `
    examples/tempo-change.yaml

piano-synth render `
    data/manifests/88keys.yaml `
    examples/tempo-change.yaml `
    data/output/tempo-change.wav `
    --subtype PCM_24 `
    --master-gain-db -12 `
    --release-seconds 0.35 `
    --tail-seconds 2.0
```