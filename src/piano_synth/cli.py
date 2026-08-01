from __future__ import annotations

import json
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from .manifest import (
    discover_dataset,
    load_manifest,
    save_manifest,
)
from .models import RenderProject
from .preprocess import (
    accept_detected_mapping,
    accept_expected_mapping,
    decode_and_analyze_manifest,
)
from .project_validation import validate_project
from .rendering import SampleLibrary, render_project, write_wav
from .validation import validate_manifest

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command("discover")
def discover(
    raw_directory: Path = typer.Argument(..., exists=True, file_okay=False),
    decoded_directory: Path = typer.Argument(..., file_okay=False),
    manifest_path: Path = typer.Argument(..., dir_okay=False),
) -> None:
    """扫描录音并创建初始manifest。"""
    manifest = discover_dataset(raw_directory, decoded_directory)
    save_manifest(manifest, manifest_path)
    console.print(
        f"已发现[bold]{len(manifest.records)}[/bold]个文件：{manifest_path}"
    )


@app.command("analyze")
def analyze(
    manifest_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
    ),
    cents_threshold: float = typer.Option(
        35.0,
        min=0.0,
        help="进入人工复核的最大音分偏差阈值",
    ),
    fmin_hz: float = typer.Option(
        25.0,
        min=1.0,
        help="基频检测下限",
    ),
    fmax_hz: float = typer.Option(
        5000.0,
        min=10.0,
        help="基频检测上限",
    ),
    overwrite: bool = typer.Option(
        False,
        help="是否覆盖已经存在的解码WAV",
    ),
) -> None:
    """解码录音并估计每个录音的基频。"""
    if fmax_hz <= fmin_hz:
        console.print("[red]fmax_hz必须大于fmin_hz[/red]")
        raise typer.Exit(code=2)

    manifest = load_manifest(manifest_path)

    decode_and_analyze_manifest(
        manifest,
        cents_review_threshold=cents_threshold,
        fmin_hz=fmin_hz,
        fmax_hz=fmax_hz,
        overwrite=overwrite,
    )

    save_manifest(manifest, manifest_path)

    console.print(
        "解码与分析完成。请运行report和validate-manifest，"
        "不要在检查结果前直接确认。"
    )


@app.command("report")
def report(
    manifest_path: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    """显示预期、检测和最终映射。"""
    manifest = load_manifest(manifest_path)
    table = Table(title=f"{manifest.dataset_id} / {manifest.dataset_version}")
    table.add_column("序号", justify="right")
    table.add_column("记录")
    table.add_column("源标签")
    table.add_column("预期MIDI")
    table.add_column("检测MIDI")
    table.add_column("最终MIDI")
    table.add_column("最终音名")
    table.add_column("f0/Hz")
    table.add_column("音分")
    table.add_column("状态")
    table.add_column("审核备注")

    for record in sorted(
        manifest.records,
        key=lambda item: item.sequence_index,
    ):
        table.add_row(
        str(record.sequence_index),
        record.record_id,
        record.source_label or "",
        str(record.midi_expected),
        (
            str(record.midi_detected)
            if record.midi_detected is not None
            else ""
        ),
        (
            str(record.midi_final)
            if record.midi_final is not None
            else ""
        ),
        record.scientific_name or "",
        (
            f"{record.detected_f0_hz:.3f}"
            if record.detected_f0_hz is not None
            else ""
        ),
        (
            f"{record.pitch_error_cents:+.2f}"
            if record.pitch_error_cents is not None
            else ""
        ),
        record.status.value,
        "; ".join(record.review_notes),
    )

    console.print(table)


@app.command("validate-manifest")
def validate_manifest_command(
    manifest_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    require_verified: bool = typer.Option(False),
    verify_hashes: bool = typer.Option(False),
) -> None:
    """严格校验manifest结构、文件和88键覆盖。"""
    manifest = load_manifest(manifest_path)
    issues = validate_manifest(
        manifest,
        require_verified=require_verified,
        verify_hashes=verify_hashes,
    )

    if not issues:
        console.print("[green]Manifest校验通过[/green]")
        return

    for issue in issues:
        console.print(
            f"[{issue.severity}] {issue.code}: {issue.message}"
            + (f" ({issue.record_id})" if issue.record_id else "")
        )

    if any(issue.severity == "ERROR" for issue in issues):
        raise typer.Exit(code=1)


@app.command("accept-detected")
def accept_detected(
    manifest_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    confirmation: str = typer.Option(
        ...,
        prompt="确认已人工检查全部88键？输入 ACCEPT_DETECTED",
    ),
) -> None:
    """人工检查后，将自动检测结果提升为正式映射。"""
    if confirmation != "ACCEPT_DETECTED":
        console.print("[red]确认字符串不匹配，未修改manifest[/red]")
        raise typer.Exit(code=2)

    manifest = load_manifest(manifest_path)

    incomplete = [
        record.record_id
        for record in manifest.records
        if record.midi_detected is None
    ]
    if incomplete:
        console.print(f"[red]以下记录没有检测结果：{incomplete}[/red]")
        raise typer.Exit(code=1)

    detected = [record.midi_detected for record in manifest.records]
    if sorted(detected) != list(range(21, 109)):
        console.print(
            "[red]检测结果没有严格覆盖MIDI 21至108，禁止批量确认。"
            "请手工修改midi_final。[/red]"
        )
        raise typer.Exit(code=1)

    accept_detected_mapping(manifest)

    issues = validate_manifest(
        manifest,
        require_verified=True,
    )
    errors = [
        issue
        for issue in issues
        if issue.severity == "ERROR"
    ]

    if errors:
        ...
        raise typer.Exit(code=1)

    save_manifest(manifest, manifest_path)

    issues = validate_manifest(
        manifest,
        require_verified=True,
    )

    errors = [
        issue
        for issue in issues
        if issue.severity == "ERROR"
    ]

    if errors:
        console.print(
            "[red]确认后的manifest仍未通过校验[/red]"
        )
        for issue in errors:
            console.print(
                f"[ERROR] {issue.code}: {issue.message}"
                + (
                    f" ({issue.record_id})"
                    if issue.record_id
                    else ""
                )
            )
        raise typer.Exit(code=1)

    save_manifest(manifest, manifest_path)

    console.print(
        "[green]88键映射已锁定并通过完整性校验[/green]"
    )

    console.print("[green]88键映射已锁定并通过完整性校验[/green]")


@app.command("accept-expected")
def accept_expected(
    manifest_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
    ),
    confirmation: str = typer.Option(
        ...,
        prompt=(
            "确认已人工核对88键顺序及review记录？"
            "输入 ACCEPT_EXPECTED"
        ),
    ),
    verify_hashes: bool = typer.Option(
        False,
        help="同时校验源文件和解码文件哈希",
    ),
) -> None:
    """
    人工审核后，按已知88键顺序确认最终MIDI 21至108。
    """
    if confirmation != "ACCEPT_EXPECTED":
        console.print(
            "[red]确认字符串不匹配，未修改manifest[/red]"
        )
        raise typer.Exit(code=2)

    manifest = load_manifest(manifest_path)

    preflight_issues = validate_manifest(
        manifest,
        verify_hashes=verify_hashes,
    )
    preflight_errors = [
        issue
        for issue in preflight_issues
        if issue.severity == "ERROR"
    ]

    if preflight_errors:
        console.print("[red]Manifest存在错误，禁止确认：[/red]")
        for issue in preflight_errors:
            console.print(
                f"[ERROR] {issue.code}: {issue.message}"
                + (
                    f" ({issue.record_id})"
                    if issue.record_id
                    else ""
                )
            )
        raise typer.Exit(code=1)

    incomplete = [
        record.record_id
        for record in manifest.records
        if (
            record.decoded_path is None
            or record.detected_f0_hz is None
            or record.analysis is None
        )
    ]

    if incomplete:
        console.print(
            "[red]以下记录未完成解码或分析，禁止确认：[/red]"
        )
        for record_id in incomplete:
            console.print(f"  - {record_id}")
        raise typer.Exit(code=1)

    review_records = [
        record
        for record in manifest.records
        if record.status.value == "review"
    ]

    if review_records:
        console.print(
            f"[yellow]将按已知序号人工确认 "
            f"{len(review_records)} 条 review 记录：[/yellow]"
        )
        for record in review_records:
            console.print(
                f"  {record.record_id}: "
                f"expected={record.midi_expected}, "
                f"detected={record.midi_detected}, "
                f"f0={record.detected_f0_hz:.3f} Hz"
            )

    accept_expected_mapping(manifest)

    postflight_issues = validate_manifest(
        manifest,
        require_verified=True,
        verify_hashes=verify_hashes,
    )
    postflight_errors = [
        issue
        for issue in postflight_issues
        if issue.severity == "ERROR"
    ]

    if postflight_errors:
        console.print(
            "[red]确认结果未通过严格校验，未写入manifest：[/red]"
        )
        for issue in postflight_errors:
            console.print(
                f"[ERROR] {issue.code}: {issue.message}"
                + (
                    f" ({issue.record_id})"
                    if issue.record_id
                    else ""
                )
            )
        raise typer.Exit(code=1)

    save_manifest(manifest, manifest_path)

    console.print(
        "[green]88键映射已按序号确认，"
        "midi_final完整覆盖MIDI 21至108[/green]"
    )

    warnings = [
        issue
        for issue in postflight_issues
        if issue.severity == "WARNING"
    ]
    for issue in warnings:
        console.print(
            f"[WARNING] {issue.code}: {issue.message}"
            + (
                f" ({issue.record_id})"
                if issue.record_id
                else ""
            )
        )


def _load_project(path: Path) -> RenderProject:
    with path.open("r", encoding="utf-8") as handle:
        if path.suffix.lower() == ".json":
            data = json.load(handle)
        else:
            data = yaml.safe_load(handle)
    return RenderProject.model_validate(data)


@app.command("validate-project")
def validate_project_command(
    project_path: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    """校验乐曲事件、轨道和时序。"""
    project = _load_project(project_path)
    issues = validate_project(project)

    if not issues:
        console.print("[green]工程校验通过[/green]")
        return

    for issue in issues:
        console.print(f"[{issue.severity}] {issue.code}: {issue.message}")

    if any(issue.severity == "ERROR" for issue in issues):
        raise typer.Exit(code=1)


@app.command("render")
def render(
    manifest_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    project_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    output_path: Path = typer.Argument(Path("data/output/render.wav"), dir_okay=False, help="输出WAV路径"),
    subtype: str = typer.Option("FLOAT"),
    master_gain_db: float = typer.Option(-12.0),
    release_seconds: float = typer.Option(0.35, min=0.001),
    tail_seconds: float = typer.Option(2.0, min=0.0),
) -> None:
    """使用88键直接采样基线渲染乐曲。"""
    manifest = load_manifest(manifest_path)
    manifest_issues = validate_manifest(
        manifest,
        require_verified=True,
    )
    manifest_errors = [
        issue for issue in manifest_issues if issue.severity == "ERROR"
    ]
    if manifest_errors:
        for issue in manifest_errors:
            console.print(f"[ERROR] {issue.code}: {issue.message}")
        raise typer.Exit(code=1)

    project = _load_project(project_path)
    project_issues = validate_project(project)
    project_errors = [
        issue for issue in project_issues if issue.severity == "ERROR"
    ]
    if project_errors:
        for issue in project_errors:
            console.print(f"[ERROR] {issue.code}: {issue.message}")
        raise typer.Exit(code=1)

    library = SampleLibrary(manifest, project.sample_rate)
    audio = render_project(
        project,
        library,
        master_gain_db=master_gain_db,
        release_seconds=release_seconds,
        tail_seconds=tail_seconds,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_wav(output_path, audio, project.sample_rate, subtype=subtype)

    peak = float(abs(audio).max()) if audio.size else 0.0
    console.print(
        f"渲染完成：{output_path}，"
        f"{len(audio) / project.sample_rate:.2f}秒，peak={peak:.6f}"
    )


if __name__ == "__main__":
    app()