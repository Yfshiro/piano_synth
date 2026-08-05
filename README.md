# Piano Synth

基于钢琴采样的 MIDI 乐谱渲染工具，可将乐谱工程渲染为立体声 WAV 音频。

## 功能

- 管理和校验钢琴采样库
- 分析采样音高与音分偏差
- 校验乐谱工程
- 根据力度、时值和释放时间渲染音符
- 输出 WAV 音频
- 提供命令行工具和自动化测试

## 环境要求

- Python 3.x
- Conda（推荐）
- SoundFile
- Typer
- PyYAML
- pytest

## 安装

```powershell
conda env create -f environment.yml
conda activate music

python -m pip install -e .
```

查看命令帮助：

```powershell
piano-synth --help
```

## 快速开始

### 校验采样库

```powershell
piano-synth validate-manifest `
    data/manifests/88keys.yaml `
    --require-verified `
    --verify-hashes
```

### 查看采样库报告

```powershell
piano-synth report `
    data/manifests/88keys.yaml
```

### 校验乐谱

```powershell
piano-synth validate-project `
    examples/simple_project.yaml
```

### 创建输出目录

渲染前先创建音频输出目录：

```powershell
New-Item -ItemType Directory -Force data/output | Out-Null
```


### 渲染 WAV

```powershell
piano-synth render `
    data/manifests/88keys.yaml `
    examples/simple_project.yaml `
    data/output/simple-project.wav `
    --subtype PCM_24 `
    --master-gain-db -12 `
    --release-seconds 0.35 `
    --tail-seconds 2.0
```

命令格式：

```text
piano-synth render <采样库清单> <乐谱文件> <输出文件> [选项]
```

#### 位置参数

| 参数 | 示例 | 说明 |
|---|---|---|
| 采样库清单 | `data/manifests/88keys.yaml` | 钢琴采样库的 Manifest 文件 |
| 乐谱文件 | `examples/simple_project.yaml` | 要渲染的 YAML 乐谱工程 |
| 输出文件 | `data/output/simple-project.wav` | 生成的 WAV 文件路径 |

#### 渲染选项

| 选项 | 示例 | 说明 |
|---|---|---|
| `--subtype` | `PCM_24` | 设置 WAV 编码格式。常用值为 `PCM_16`、`PCM_24` 和 `FLOAT` |
| `--master-gain-db` | `-12` | 设置整体输出增益，单位为 dB。数值越小，输出音量越低，可用于减少削波 |
| `--release-seconds` | `0.35` | 设置每个音符结束后的释放时间，单位为秒。过小可能导致声音突然截断，过大可能使快速乐段变浑浊 |
| `--tail-seconds` | `2.0` | 设置整首乐曲结束后额外保留的尾音时间，单位为秒，避免最后的音符或和弦被截断 |

推荐使用：

```powershell
--subtype PCM_24
--master-gain-db -12
--release-seconds 0.35
--tail-seconds 2.0
```

查看完整帮助：

```powershell
piano-synth render --help
```

播放生成的音频：

```powershell
Invoke-Item data/output/simple-project.wav
```

## 常用命令

```powershell
piano-synth discover --help
piano-synth analyze --help
piano-synth report data/manifests/88keys.yaml
piano-synth validate-manifest data/manifests/88keys.yaml
piano-synth validate-project examples/simple_project.yaml
```

## 测试

运行全部测试：

```powershell
pytest
```

运行覆盖率检查：

```powershell
pytest --cov=piano_synth --cov-report=term-missing
```

## 项目结构

```text
.
├── configs/
│   └── default.yaml
├── data/
│   ├── manifests/
│   │   └── 88keys.yaml
│   └── output/
├── examples/
│   └── simple_project.yaml
├── src/
│   └── piano_synth/
├── tests/
├── environment.yml
└── pyproject.toml
```

## 重要文件

- `configs/default.yaml`：默认配置
- `examples/simple_project.yaml`：示例乐谱
- `data/manifests/88keys.yaml`：88 键采样库清单
- `data/output/`：渲染结果目录

生成的 WAV 文件通常不需要提交到 Git，可以加入 `.gitignore`：

```gitignore
data/output/*
!data/output/.gitkeep
```

## License

请根据项目实际情况补充许可证信息。