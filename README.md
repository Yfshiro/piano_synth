
# Piano Synth

一个基于 Python 的钢琴采样分析与乐曲渲染工具。

本项目以完整的 88 键钢琴录音为音源，将原始录音转换为标准 WAV，分析每个录音的基频并建立 MIDI 21（A0）到 MIDI 108（C8）的映射。用户可以使用 YAML 编写乐谱，通过命令行校验乐谱并渲染成立体声 WAV 文件。

当前版本已经实现：

- 扫描并管理 88 键钢琴录音
- 将原始录音解码为标准 WAV
- 自动分析录音基频和 MIDI 音高
- 人工审核并确认完整的 88 键映射
- 使用 YAML 定义速度、音符、力度、轨道和声像
- 支持浮点拍数和左右手独立时间轴
- 支持延音踏板事件
- 使用 88 键直接采样渲染乐曲
- 导出 16 位、24 位或浮点 WAV
- 对 manifest、乐谱和渲染参数进行校验

> 当前渲染器是“88 键直接采样”基线引擎，不需要将一个录音大范围变调。频谱参数合成、Karplus-Strong 物理建模、Piano Roll 和 MIDI 导出属于后续扩展方向。

---

## 1. 快速开始

### 1.1 环境要求

建议使用：

- Windows 10/11
- Python 3.11
- Conda 或 Miniconda
- FFmpeg（用于解码 `.m4a` 等录音）
- PowerShell

检查 Python：

```powershell
python --version
```

检查 FFmpeg：

```powershell
ffmpeg -version
```

### 1.2 创建 Conda 环境

在项目根目录运行：

```powershell
conda env create -f environment.yml
conda activate music
```

如果环境已经创建：

```powershell
conda activate music
```

### 1.3 安装项目

在项目根目录执行 editable 安装：

```powershell
python -m pip install -e .
```

安装后检查命令：

```powershell
piano-synth --help
```

如果修改了源码，但命令仍然表现为旧版本，可以重新安装：

```powershell
python -m pip install -e .
```

查看当前实际加载的源码位置：

```powershell
python -c "import piano_synth.cli as c; print(c.__file__)"
```

它应指向当前项目中的：

```text
src/piano_synth/cli.py
```

---

## 2. 最快的使用方法

项目已经提供示例乐谱：

```text
examples/simple_project.yaml
```

先校验乐谱：

```powershell
piano-synth validate-project `
    examples/simple_project.yaml
```

创建输出目录：

```powershell
New-Item -ItemType Directory -Force data/output | Out-Null
```

渲染乐曲：

```powershell
piano-synth render `
    data/manifests/88keys.yaml `
    examples/simple_project.yaml `
    data/output/simple-project-baseline.wav `
    --subtype PCM_24 `
    --master-gain-db -12 `
    --release-seconds 0.35 `
    --tail-seconds 2.0
```
## 逐行解释
第 1 行：调用渲染命令
piano-synth render `
piano-synth：运行你的钢琴合成器命令行程序。
render：选择“渲染乐曲”功能。
行末的反引号 `：PowerShell 的续行符，表示命令还没有结束，下一行仍属于同一条命令。
也就是说，这一行相当于告诉程序：

启动 Piano Synth，并执行渲染操作。
第 2 行：指定 88 键音源清单
```powershell
data/manifests/88keys.yaml
```
这是第一个位置参数，即 Manifest 文件路径。

这个文件记录了：

MIDI 21～108 对应的 88 个钢琴键；
每个琴键所使用的 WAV 文件；
每条录音的最终 MIDI 映射；
音源路径、哈希和审核状态等信息。
渲染器读取乐谱中的 pitch 后，会通过这个文件找到对应的钢琴录音。

例如乐谱中有：

pitch: 60
程序会在 88keys.yaml 中查找 midi_final: 60 对应的音源，也就是中央 C（C4）的录音。

第 3 行：指定乐谱文件
```powershell
examples/simple_project.yaml
```
这是第二个位置参数，即 需要渲染的乐谱工程。

它通常包含：

输出采样率 sample_rate；
速度及变速点 tempo；
左右手或其他音轨 tracks；
音符的音高、开始拍、时长和力度；
音轨增益和声像；
延音踏板事件。
例如：
```powershell
- pitch: 60
  start_beat: 0
  duration_beats: 2
  velocity: 90
  track_id: right
```
如果要渲染自己的乐谱，只需要替换这一行：

examples/my_song.yaml
第 4 行：指定输出文件
```powershell
data/output/simple-project-baseline.wav
```
这是第三个位置参数，即 渲染结果的保存路径。

这里表示把最终音频保存为：
```powershell
data/output/simple-project-baseline.wav
```

可以修改目录或文件名，例如：

```powershell
data/output/my_song.wav
```
如果 data/output 不存在，可以先创建：

```powershell
New-Item -ItemType Directory -Force data/output | Out-Null
```
如果目标 WAV 已经存在，通常会被新的渲染结果覆盖，具体以程序实现为准。

第 5 行：设置 WAV 位深
```powershell
--subtype PCM_24
```
设置输出 WAV 的编码子类型为 24 位 PCM。

PCM_24 的特点：

每个采样使用 24 位整数保存；
动态范围高于 PCM_16；
适合后续混音、处理和保存母版；
文件会比 16 位 WAV 更大。
常见选择包括：

PCM_16    16 位整数 WAV，兼容性好、文件较小
PCM_24    24 位整数 WAV，动态范围更高
FLOAT     浮点 WAV，适合进一步音频处理
日常高质量导出推荐：
```powershell
--subtype PCM_24
```
第 6 行：设置主输出增益
```powershell
--master-gain-db -12
```
将最终混音的总音量降低 12 dB。

这个参数作用于所有音轨混合后的最终输出。之所以使用负值，是因为多个钢琴音符同时叠加时，振幅可能超过 WAV 可表示范围，从而产生削波和失真。

常见设置：

参数值	效果
0	不降低主增益，密集和弦容易削波
-6	降低 6 dB
-12	较稳妥的常用设置
-18	适合非常密集或响亮的编配
-30	适合大量音符同时发声的测试
如果输出失真，可以改成：
```powershell
--master-gain-db -18
```
如果声音太小且没有削波，可以尝试：
```powershell
--master-gain-db -9
```
第 7 行：设置音符释放时间
```powershell
--release-seconds 0.35
```
设置音符结束后的释放阶段为 0.35 秒。

当一个音符到达 duration_beats 指定的结束位置时，程序不会立即把波形截断，而是在 0.35 秒内逐渐降低音量。这样可以减少：

突然截断；
咔哒声或爆音；
不自然的音符结尾。
常见设置：

数值	听感
0.05	很短，适合断奏，但可能生硬
0.18	较短，适合快速乐曲
0.35	自然且通用
0.60	余音较长，可能让快速段落浑浊
这个参数影响的是每个音符结束后的衰减。

第 8 行：设置整首乐曲的尾音
```powershell
--tail-seconds 2.0
```
在最后一个乐谱事件结束后，再为输出缓冲区保留 2 秒。

这段额外时间用于容纳：

最后几个音符的释放阶段；
延音踏板保留的声音；
钢琴采样本身的自然衰减。
如果不保留尾音，最后一个音符可能在 WAV 结束处被截断。

如果结尾是长和弦或使用了踏板，可以增加为：
```powershell
--tail-seconds 4.0
```
release-seconds 和 tail-seconds 的区别是：

release-seconds：控制每个音符结束后衰减多久；
tail-seconds：控制整首乐曲结束后，输出文件额外保留多久。
参数位置不能随意交换
前三个是不带名称的位置参数，顺序固定：

```powershell
piano-synth render <音源清单> <乐谱文件> <输出文件>
```
即：

1. data/manifests/88keys.yaml
2. examples/simple_project.yaml
3. data/output/simple-project-baseline.wav
后面的 --subtype、--master-gain-db 等是命名选项。这些选项通常可以调整顺序，因为参数名称已经说明了用途。

也可以写成一行
反引号只是为了让 PowerShell 命令更易读。完全等价的单行命令是：
```powershell
piano-synth render data/manifests/88keys.yaml examples/simple_project.yaml data/output/simple-project-baseline.wav --subtype PCM_24 --master-gain-db -12 --release-seconds 0.35 --tail-seconds 2.0
```

需要注意：PowerShell 的续行反引号必须是该行最后一个字符，后面不要再留空格，否则续行可能失效。
---

播放结果：

```powershell
Invoke-Item data/output/simple-project-baseline.wav
```

查看文件：

```powershell
Get-Item data/output/simple-project-baseline.wav
```

---

## 3. 在哪里修改输出路径

`render` 命令接收三个位置参数：

```text
piano-synth render <manifest_path> <project_path> <output_path>
```

第三个参数就是输出路径。

例如输出到：

```text
data/output/my-song.wav
```

使用：

```powershell
piano-synth render `
    data/manifests/88keys.yaml `
    examples/simple_project.yaml `
    data/output/my-song.wav
```

也可以使用其他目录：

```powershell
piano-synth render `
    data/manifests/88keys.yaml `
    examples/simple_project.yaml `
    D:/Music/my-song.wav
```

如果目标目录不存在，请先创建：

```powershell
New-Item -ItemType Directory -Force data/output | Out-Null
```

输出目录建议只保存生成文件，不要把原始录音或 manifest 放在这里。

建议在 `.gitignore` 中忽略渲染结果：

```gitignore
data/output/*
!data/output/.gitkeep
```

---

## 4. 在哪里编写自己的乐谱

乐谱使用 YAML 格式。

示例乐谱位于：

```text
examples/simple_project.yaml
```

可以复制一份作为自己的乐谱：

```powershell
Copy-Item `
    examples/simple_project.yaml `
    examples/my_song.yaml
```

然后编辑：

```text
examples/my_song.yaml
```

渲染时将第二个参数改为自己的乐谱：

```powershell
piano-synth render `
    data/manifests/88keys.yaml `
    examples/my_song.yaml `
    data/output/my_song.wav `
    --subtype PCM_24
```

建议按照以下方式组织文件：

```text
examples/
├── simple_project.yaml
└── my_song.yaml

data/
├── manifests/
│   └── 88keys.yaml
└── output/
    └── my_song.wav
```

---

## 5. 乐谱格式

一个基本乐谱由以下部分组成：

- `sample_rate`：输出采样率
- `tempo`：速度变化点
- `tracks`：音轨列表
- `notes`：每条轨道的音符
- `pedal`：延音踏板事件

示例：

```yaml
sample_rate: 48000

tempo:
  - beat: 0
    bpm: 120

tracks:
  - track_id: right
    name: Right Hand
    gain_db: -3.0
    pan: 0.2
    notes:
      - pitch: 60
        start_beat: 0
        duration_beats: 1
        velocity: 90
        track_id: right

      - pitch: 64
        start_beat: 1
        duration_beats: 1
        velocity: 90
        track_id: right

      - pitch: 67
        start_beat: 2
        duration_beats: 2
        velocity: 96
        track_id: right

    pedal:
      - beat: 0
        value: 127

      - beat: 4
        value: 0

  - track_id: left
    name: Left Hand
    gain_db: -5.0
    pan: -0.2
    notes:
      - pitch: 48
        start_beat: 0
        duration_beats: 2
        velocity: 78
        track_id: left

      - pitch: 43
        start_beat: 2
        duration_beats: 2
        velocity: 78
        track_id: left
```

### 5.1 音符字段

每个音符包含：

| 字段 | 含义 | 范围或示例 |
| --- | --- | --- |
| `pitch` | MIDI 音高 | 21～108 |
| `start_beat` | 开始拍数 | 大于或等于 0 |
| `duration_beats` | 持续拍数 | 大于 0 |
| `velocity` | 力度 | 1～127 |
| `track_id` | 所属轨道 | 如 `left`、`right` |

例如：

```yaml
- pitch: 69
  start_beat: 0.5
  duration_beats: 1.5
  velocity: 100
  track_id: right
```

表示：

- MIDI 69，即 A4
- 在第 0.5 拍开始
- 持续 1.5 拍
- 力度为 100
- 属于右手轨道

`start_beat` 和 `duration_beats` 可以是小数，因此左右手不必按照固定网格对齐。

### 5.2 常用 MIDI 音高

| 音名 | MIDI |
| --- | ---: |
| A0 | 21 |
| C1 | 24 |
| C2 | 36 |
| C3 | 48 |
| C4（中央 C） | 60 |
| A4 | 69 |
| C5 | 72 |
| C6 | 84 |
| C7 | 96 |
| C8 | 108 |

==**具体可见\examples\reference.yaml**==

十二平均律每升高一个半音，MIDI 编号加 1。

例如 C4 大三和弦：

```yaml
notes:
  - pitch: 60
    start_beat: 0
    duration_beats: 2
    velocity: 90
    track_id: right

  - pitch: 64
    start_beat: 0
    duration_beats: 2
    velocity: 86
    track_id: right

  - pitch: 67
    start_beat: 0
    duration_beats: 2
    velocity: 92
    track_id: right
```

### 5.3 轨道字段

| 字段 | 含义 |
| --- | --- |
| `track_id` | 轨道唯一标识 |
| `name` | 显示名称 |
| `gain_db` | 轨道增益，单位 dB |
| `pan` | 左右声像，范围 -1～1 |
| `notes` | 音符列表 |
| `pedal` | 延音踏板事件 |

声像含义：

- `-1.0`：完全靠左
- `0.0`：中央
- `1.0`：完全靠右

推荐不要把左右手完全放在两侧，可以使用较自然的设置：

```yaml
pan: -0.2
```

和：

```yaml
pan: 0.2
```

### 5.4 速度变化

速度通过 `tempo` 列表设置：

```yaml
tempo:
  - beat: 0
    bpm: 100

  - beat: 16
    bpm: 120
```

这表示：

- 第 0 拍开始为 100 BPM
- 第 16 拍开始变为 120 BPM

如果全曲速度不变：

```yaml
tempo:
  - beat: 0
    bpm: 120
```

### 5.5 延音踏板

踏板值范围为 0～127：

```yaml
pedal:
  - beat: 0
    value: 127

  - beat: 4
    value: 0
```

通常：

- `value >= 64`：踩下踏板
- `value < 64`：松开踏板

---

## 6. 校验自己的乐谱

每次渲染前建议先运行：

```powershell
piano-synth validate-project `
    examples/my_song.yaml
```

校验器会检查：

- MIDI 音高是否在 21～108
- 开始拍是否为负数
- 音符时长是否大于 0
- 力度是否在 1～127
- BPM 是否大于 0
- 声像是否在 -1～1
- 轨道标识是否正确
- 速度点和事件时间是否有效

校验通过后再渲染：

```powershell
piano-synth render `
    data/manifests/88keys.yaml `
    examples/my_song.yaml `
    data/output/my_song.wav
```

---

## 7. 渲染参数

查看完整帮助：

```powershell
piano-synth render --help
```

典型命令：

```powershell
piano-synth render `
    data/manifests/88keys.yaml `
    examples/my_song.yaml `
    data/output/my_song.wav `
    --subtype PCM_24 `
    --master-gain-db -12 `
    --release-seconds 0.35 `
    --tail-seconds 2.0
```

### `--subtype`

设置 WAV 编码格式。

常见值：

```text
PCM_16
PCM_24
FLOAT
```

推荐：

```powershell
--subtype PCM_24
```

### `--master-gain-db`

设置主输出增益，单位为 dB。

例如：

```powershell
--master-gain-db -12
```

多个音符同时播放时会叠加能量。为了减少削波，建议从 `-12 dB` 开始，根据实际峰值和听感调整。

### `--release-seconds`

设置音符结束后的释放时间：

```powershell
--release-seconds 0.35
```

数值太小可能产生突兀截断；数值太大可能让快速乐段变得浑浊。

### `--tail-seconds`

设置乐曲末尾保留的尾音：

```powershell
--tail-seconds 2.0
```

如果长音、混响或踏板声音被截断，可以增大该值。

---

## 8. 88 键录音处理流程

如果使用项目中已经确认的：

```text
data/manifests/88keys.yaml
```

通常不需要重复执行本节。

只有在更换录音、重新建设采样库或重新分析音高时，才需要执行以下流程。

### 8.1 扫描录音

```powershell
piano-synth discover --help
```

`discover` 扫描录音文件并创建初始 manifest。

manifest 保存每条录音的：

- 文件路径
- 文件哈希
- 序号
- 预期 MIDI
- 解码文件路径
- 检测基频
- 检测 MIDI
- 最终 MIDI
- 状态
- 审核备注

### 8.2 解码并分析

```powershell
piano-synth analyze --help
```

`analyze` 会：

1. 将原始录音解码为 WAV；
2. 读取采样率、通道数、时长和峰值；
3. 估计基频；
4. 将基频换算为 MIDI 音高；
5. 计算音分偏差；
6. 标记低置信度或音高异常记录。

### 8.3 查看分析报告

```powershell
piano-synth report `
    data/manifests/88keys.yaml
```

报告包含：

- 预期 MIDI
- 检测 MIDI
- 最终 MIDI
- 最终音名
- 基频
- 音分误差
- 状态
- 审核备注

### 8.4 确认最终映射

当前采样库已按照钢琴 88 键顺序人工确认：

```powershell
piano-synth accept-expected `
    data/manifests/88keys.yaml `
    --confirmation ACCEPT_EXPECTED `
    --verify-hashes
```

该命令使用已知顺序将 88 条录音映射到 MIDI 21～108，同时保留自动检测结果作为审核证据。

如果完全信任自动检测结果，也可以查看：

```powershell
piano-synth accept-detected --help
```

对于钢琴最高音区，基频检测更容易受到弱基频、泛音和录音压缩影响，因此不建议未经人工审核就直接接受检测结果。

### 8.5 严格校验采样库

```powershell
piano-synth validate-manifest `
    data/manifests/88keys.yaml `
    --require-verified `
    --verify-hashes
```

当前数据可能保留以下警告：

```text
[WARNING] DETECTED_OUTSIDE_PIANO: Detected MIDI is 109 (key-088)
```

这是自动检测结果的警告。只要 `key-088` 已经人工确认到 C8/MIDI 108，并且校验中没有 `ERROR`，就不会阻止渲染。

---

## 9. 常用命令

显示全部命令：

```powershell
piano-synth --help
```

### 扫描录音

```powershell
piano-synth discover --help
```

### 分析录音

```powershell
piano-synth analyze --help
```

### 查看采样库报告

```powershell
piano-synth report `
    data/manifests/88keys.yaml
```

### 校验采样库

```powershell
piano-synth validate-manifest `
    data/manifests/88keys.yaml `
    --require-verified
```

### 校验乐谱

```powershell
piano-synth validate-project `
    examples/simple_project.yaml
```

### 渲染乐谱

```powershell
piano-synth render `
    data/manifests/88keys.yaml `
    examples/simple_project.yaml `
    data/output/simple-project-baseline.wav
```

---

## 10. 运行测试

运行全部测试：

```powershell
pytest
```

运行覆盖率检查：

```powershell
pytest --cov=piano_synth --cov-report=term-missing
```

当前测试主要覆盖：

- 数据模型
- 音高换算
- 时间换算
- 部分采样渲染
- manifest 基础逻辑

CLI、完整预处理流程和端到端渲染仍需要继续增加测试覆盖率。

---

## 11. 项目结构

典型目录结构如下：

```text
piano_synth/
├── configs/
│   └── default.yaml
├── data/
│   ├── manifests/
│   │   └── 88keys.yaml
│   ├── output/
│   └── ...
├── examples/
│   └── simple_project.yaml
├── src/
│   └── piano_synth/
│       ├── __init__.py
│       ├── cli.py
│       ├── manifest.py
│       ├── models.py
│       ├── pitch.py
│       ├── preprocess.py
│       ├── project_validation.py
│       ├── rendering.py
│       ├── timing.py
│       └── validation.py
├── tests/
├── environment.yml
└── pyproject.toml
```

---

## 12. 核心设计原理

### 12.1 事件驱动乐谱

项目没有采用“每一列代表一拍”的固定矩阵，而是把每个音符保存为独立事件：

```text
音高 + 开始拍 + 持续拍数 + 力度 + 轨道
```

这样可以表达：

- 0.25、0.5、1.5 等浮点拍数
- 左右手不对齐
- 长音和短音同时存在
- 任意复音和和弦
- 同音快速重复
- 多轨道独立增益与声像

### 12.2 拍数到样本位置

用户在 YAML 中使用拍数，渲染器将拍数转换成秒，再转换成样本索引。

固定 BPM 下：

```text
seconds = beat × 60 / BPM
sample = seconds × sample_rate
```

有多个速度点时，时间引擎按速度区间分段积分，保证速度变化后的事件仍能落在正确样本位置。

### 12.3 直接采样渲染

每个 MIDI 音高都对应一条经过人工确认的真实钢琴录音。

渲染音符时，程序会：

1. 根据 `pitch` 查找对应采样；
2. 根据 `velocity` 和轨道增益计算振幅；
3. 根据 `start_beat` 计算起始样本；
4. 根据 `duration_beats` 计算音符结束位置；
5. 添加释放包络，避免突然截断；
6. 根据 `pan` 分配左右声道；
7. 将所有音符叠加到主输出缓冲区；
8. 应用主增益并写入 WAV。

由于使用 88 键完整采样，渲染器不需要对少量音源进行大跨度变调，可以减少明显的变调伪影。

---

## 13. 源码文件说明

### `src/piano_synth/__init__.py`

Python 包入口文件。

主要作用：

- 将目录声明为 `piano_synth` 包；
- 保存包级版本或公共接口；
- 支持其他模块通过 `import piano_synth` 导入项目。

该文件通常应保持简洁，复杂业务逻辑应放在独立模块中。

### `src/piano_synth/cli.py`

命令行入口和 Typer 命令注册模块。

负责提供：

```text
discover
analyze
report
validate-manifest
accept-detected
accept-expected
validate-project
render
```

它的主要职责是：

1. 接收命令行参数；
2. 加载 manifest 或乐谱；
3. 调用对应业务模块；
4. 输出表格、警告和错误；
5. 根据结果设置退出码；
6. 将处理结果保存到文件。

CLI 层主要负责流程编排，不应承载复杂的音频分析算法。

### `src/piano_synth/models.py`

项目的核心数据模型，使用 Pydantic 定义严格的数据结构。

主要模型包括：

- `RecordStatus`：录音处理状态
- `AnalysisMetadata`：分析算法及参数
- `AudioMetadata`：WAV 元数据
- `KeyRecord`：单个琴键录音
- `DatasetManifest`：完整 88 键采样库
- `NoteEvent`：音符事件
- `PedalEvent`：踏板事件
- `Track`：音轨
- `TempoPoint`：速度变化点
- `RenderProject`：完整渲染工程

Pydantic 会自动检查音域、力度、时长、声像和字段类型，并禁止 manifest 中出现未定义字段。

### `src/piano_synth/manifest.py`

负责 manifest 的读取、写入和路径处理。

主要职责：

- 从 YAML 加载 `DatasetManifest`
- 将模型保存为 YAML
- 处理源录音和解码 WAV 的相对路径
- 计算或检查文件 SHA-256
- 更新 manifest 时间
- 保证写回文件的数据结构稳定

manifest 是采样库的事实来源。渲染器不应根据文件名临时猜测 MIDI 音高，而应读取经过确认的 `midi_final`。

### `src/piano_synth/pitch.py`

负责音高和音乐理论相关换算。

主要功能通常包括：

- MIDI 编号转频率
- 频率转 MIDI
- MIDI 转科学音高名称
- 计算音分误差
- 根据 88 键序号计算预期 MIDI
- 检查检测结果是否落在钢琴音域内

十二平均律基频换算公式为：

```text
f = 440 × 2^((midi - 69) / 12)
```

其中 MIDI 69 对应 A4 = 440 Hz。

### `src/piano_synth/preprocess.py`

负责录音预处理和音高分析，是采样库建设流程的核心模块。

主要职责：

- 调用 FFmpeg 解码原始录音
- 统一转换为 WAV/PCM
- 读取音频元数据
- 检测峰值和削波
- 估计录音基频
- 计算检测 MIDI 和音分误差
- 生成置信度和审核备注
- 更新记录状态
- 接受自动检测映射
- 按已知 88 键顺序接受人工确认映射

该模块保留 `midi_detected` 和 `midi_final` 两套结果：

- `midi_detected` 是算法分析证据；
- `midi_final` 是经过审核后用于渲染的正式映射。

这种设计避免自动分析错误直接污染最终采样库。

### `src/piano_synth/validation.py`

负责采样库 manifest 的完整性校验。

主要检查：

- 是否恰好包含 88 条记录
- `record_id` 和序号是否重复
- MIDI 21～108 是否完整覆盖
- 源文件和解码文件是否存在
- SHA-256 是否匹配
- VERIFIED 记录是否包含最终 MIDI 和音名
- 自动检测结果是否超出钢琴范围
- 分析元数据是否完整

校验结果通常分为：

- `ERROR`：必须修复，阻止后续操作
- `WARNING`：需要关注，但不一定阻止渲染

### `src/piano_synth/project_validation.py`

负责乐谱工程的语义校验。

Pydantic 负责单字段范围，而该模块负责跨对象和业务规则，例如：

- 音符的 `track_id` 是否存在
- 轨道标识是否重复
- 速度点是否有效
- 乐谱是否包含可渲染音符
- 事件关系是否合理
- 时间轴是否存在异常

校验通过后才建议进入渲染阶段。

### `src/piano_synth/timing.py`

负责音乐拍数、秒和样本位置之间的转换。

它处理：

- 固定 BPM
- 多个速度变化点
- 任意浮点拍数
- 音符开始时间
- 音符持续时间
- 最终样本索引

这个模块将“乐谱时间”和“音频时间”隔离。YAML 使用拍数，音频渲染内部只处理秒和样本。

### `src/piano_synth/rendering.py`

负责把乐谱工程渲染成立体声音频。

主要功能包括：

- 从 manifest 建立 MIDI 到 WAV 的采样库
- 读取并缓存琴键采样
- 根据力度和增益缩放波形
- 根据音符持续时间截取或延长采样
- 生成释放包络
- 计算左右声道增益
- 将音符叠加到输出缓冲区
- 应用主输出增益
- 检查或处理削波
- 使用 SoundFile 写出 WAV

核心叠加过程可以概括为：

```text
buffer[start_sample:end_sample] += note_waveform
```

每个轨道拥有独立事件列表，但最终都会按照绝对样本位置叠加到同一立体声缓冲区。

### `configs/default.yaml`

项目默认配置文件。

通常用于保存：

- 解码格式
- 采样率
- 基频分析参数
- 置信度阈值
- 音分偏差阈值
- 默认渲染参数

修改配置前，应先查看 CLI 是否读取了对应字段。命令行参数通常会覆盖默认配置。

### `examples/simple_project.yaml`

可以直接校验和渲染的示例乐谱。

它也是编写新乐谱时最可靠的模板。建议复制后修改，不要直接覆盖原始示例。

### `data/manifests/88keys.yaml`

完整的 88 键采样库清单。

它保存：

- 每条录音的序号和路径
- 文件哈希
- 预期 MIDI
- 检测 MIDI
- 最终 MIDI
- 科学音高名称
- 基频和音分误差
- 处理状态
- 审核备注
- 分析算法元数据

这是重要数据文件。修改前建议备份，不建议手工批量改写其中的最终 MIDI 映射。

### `data/output/`

默认推荐的渲染输出目录。

例如：

```text
data/output/simple-project-baseline.wav
data/output/my_song.wav
data/output/smoke-test.wav
```

该目录中的 WAV 通常属于生成结果，可以加入 `.gitignore`。

### `tests/`

自动化测试目录。

测试用于防止以下功能在修改后发生回归：

- 音高换算
- 时间换算
- 数据模型校验
- manifest 读写
- 88 键映射
- 音频叠加
- WAV 渲染
- CLI 行为

修改核心逻辑后应运行：

```powershell
pytest
```

### `environment.yml`

Conda 环境定义文件。

它记录：

- Python 版本
- Python 依赖
- 音频处理依赖
- 测试工具

用于在其他机器上重建一致的开发环境。

### `pyproject.toml`

Python 项目配置文件。

通常包含：

- 项目名称和版本
- Python 版本要求
- 运行依赖
- 开发依赖
- `piano-synth` 命令行入口
- pytest 配置
- 构建系统配置

`piano-synth` 命令能在终端直接运行，是因为该文件将命令映射到了 CLI 模块。

---

## 14. 推荐工作流

日常编写和渲染乐谱：

```powershell
conda activate music
```

编辑：

```text
examples/my_song.yaml
```

校验：

```powershell
piano-synth validate-project `
    examples/my_song.yaml
```

渲染：

```powershell
piano-synth render `
    data/manifests/88keys.yaml `
    examples/my_song.yaml `
    data/output/my_song.wav `
    --subtype PCM_24 `
    --master-gain-db -12 `
    --release-seconds 0.35 `
    --tail-seconds 2.0
```

播放：

```powershell
Invoke-Item data/output/my_song.wav
```

运行测试：

```powershell
pytest
```

---

## 15. 常见问题

### 找不到 `piano-synth` 命令

确认环境已激活：

```powershell
conda activate music
```

然后重新安装：

```powershell
python -m pip install -e .
```

### 找不到乐谱文件

不要原样使用：

```text
path/to/project.yaml
```

这只是占位符。使用实际存在的文件，例如：

```powershell
piano-synth validate-project `
    examples/simple_project.yaml
```

### 找不到 `data/projects/smoke-test.yaml`

该文件不是自动生成的。可以使用现有示例：

```text
examples/simple_project.yaml
```

或者从示例复制：

```powershell
Copy-Item `
    examples/simple_project.yaml `
    examples/smoke-test.yaml
```

### 输出目录不存在

创建目录：

```powershell
New-Item -ItemType Directory -Force data/output | Out-Null
```

### 输出声音削波或失真

降低主增益：

```powershell
--master-gain-db -18
```

同时检查轨道的 `gain_db`，和弦较密集时应保留更多余量。

### 尾音突然被截断

增加：

```powershell
--release-seconds 0.6
--tail-seconds 3.0
```

### 乐曲速度不正确

检查乐谱中的：

```yaml
tempo:
  - beat: 0
    bpm: 120
```

### 音符音高不正确

检查 `pitch` 是否使用标准 MIDI 编号。中央 C 是 MIDI 60，而不是录音文件的序号。

### 最高音出现检测警告

高音区容易出现弱基频和泛音误判。自动检测值保留为分析证据，实际渲染使用人工确认后的 `midi_final`。

---

## 16. 当前限制

当前版本仍有以下限制：

- 主要使用单力度 88 键录音；
- 力度变化主要通过振幅映射实现；
- 不能完全重建真实钢琴不同力度下的频谱变化；
- `.m4a` 原始录音可能包含 AAC 压缩伪影；
- 高音区基频检测容易被泛音干扰；
- 踏板和同音重触发模型仍可继续完善；
- 尚未实现完整的频谱参数合成引擎；
- 尚未实现 Karplus-Strong 数字波导引擎；
- 尚未实现 Piano Roll 和 MIDI 导出；
- CLI 和端到端流程的测试覆盖率仍需提高。

---

## 17. 后续开发方向

计划中的后续能力包括：

1. 从代表性钢琴录音提取谐波、相位和衰减参数；
2. 对每个谐波使用独立衰减时间；
3. 提取琴槌击弦的 attack 瞬态；
4. 建立频谱参数合成引擎；
5. 建立带频率相关衰减的 Karplus-Strong 引擎；
6. 改进力度到音色的非线性映射；
7. 支持更自然的同音重触发和 Voice 管理；
8. 完善延音踏板行为；
9. 增加 Piano Roll 可视化；
10. 支持 MIDI 导入和导出；
11. 支持左右手分轨导出；
12. 增加完整端到端测试和性能测试。

---

## 18. 最小命令清单

```powershell
# 激活环境
conda activate music

# 安装项目
python -m pip install -e .

# 查看帮助
piano-synth --help

# 校验采样库
piano-synth validate-manifest `
    data/manifests/88keys.yaml `
    --require-verified `
    --verify-hashes

# 查看采样报告
piano-synth report `
    data/manifests/88keys.yaml

# 校验乐谱
piano-synth validate-project `
    examples/simple_project.yaml

# 创建输出目录
New-Item -ItemType Directory -Force data/output | Out-Null

# 渲染
piano-synth render `
    data/manifests/88keys.yaml `
    examples/simple_project.yaml `
    data/output/simple-project-baseline.wav `
    --subtype PCM_24 `
    --master-gain-db -12 `
    --release-seconds 0.35 `
    --tail-seconds 2.0

# 播放
Invoke-Item data/output/simple-project-baseline.wav

# 测试
pytest
```
