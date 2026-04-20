"""Batch workflow execution: parse a YAML workflow file and run steps in sequence."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

from pdfuse.operations import compress_pdf, reorder_pdf, rotate_pdf, split_pdf, watermark_pdf
from pdfuse.utils import parse_page_range

console = Console()
err_console = Console(stderr=True)

VALID_STEPS = {"compress", "watermark", "split", "rotate", "reorder"}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class StepConfig:
    name: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowConfig:
    steps: list[StepConfig]
    yaml_path: Path
    # Single-file mode
    input: Path | None = None
    output: Path | None = None
    # Folder mode
    input_folder: Path | None = None
    output_folder: Path | None = None
    pattern: str = "*.pdf"


# ---------------------------------------------------------------------------
# Parsing and validation
# ---------------------------------------------------------------------------

def _parse_step(raw: Any) -> StepConfig:
    """Parse one YAML step entry into a StepConfig. Raises ValueError on bad input."""
    if isinstance(raw, str):
        name: str = raw.strip()
        params: dict[str, Any] = {}
    elif isinstance(raw, dict):
        if len(raw) != 1:
            raise ValueError(
                f"Each step must have exactly one key, got: {list(raw.keys())}"
            )
        name, raw_params = next(iter(raw.items()))
        if raw_params is None:
            params = {}
        elif not isinstance(raw_params, dict):
            raise ValueError(
                f"Params for '{name}' must be a mapping, got: {type(raw_params).__name__}"
            )
        else:
            params = dict(raw_params)
    else:
        raise ValueError(f"Step must be a string or mapping, got: {type(raw).__name__}")

    name = str(name).strip()
    if name not in VALID_STEPS:
        raise ValueError(
            f"Unknown step '{name}'. Valid steps: {', '.join(sorted(VALID_STEPS))}"
        )
    return StepConfig(name=name, params=params)


def _validate_step_params(step: StepConfig) -> None:
    """Raise ValueError if a step's parameters are missing or conflicting."""
    p = step.params
    if step.name == "watermark":
        has_text = "text" in p
        has_stamp = "stamp" in p
        if not has_text and not has_stamp:
            raise ValueError("Step 'watermark' requires 'text' or 'stamp'")
        if has_text and has_stamp:
            raise ValueError("Step 'watermark': use only one of 'text' or 'stamp'")
    elif step.name == "split":
        if "pages" not in p:
            raise ValueError("Step 'split' requires 'pages' (e.g. \"1-5\")")
    elif step.name == "rotate":
        if "angle" not in p:
            raise ValueError("Step 'rotate' requires 'angle'")
        try:
            angle = int(p["angle"])
        except (ValueError, TypeError):
            raise ValueError(f"Step 'rotate': angle must be an integer, got {p['angle']!r}")
        if angle not in (90, 180, 270):
            raise ValueError(f"Step 'rotate': angle must be 90, 180, or 270, got {angle}")
    elif step.name == "reorder":
        if "order" not in p:
            raise ValueError("Step 'reorder' requires 'order' (e.g. \"3,1,2\")")


def load_workflow(yaml_path: Path) -> WorkflowConfig:
    """Parse and validate *yaml_path*. Returns WorkflowConfig or raises SystemExit."""
    try:
        raw = yaml.safe_load(yaml_path.read_text())
    except yaml.YAMLError as exc:
        err_console.print(f"[bold red]Error:[/bold red] Invalid YAML: {exc}")
        raise SystemExit(1)

    if not isinstance(raw, dict):
        err_console.print("[bold red]Error:[/bold red] Workflow file must be a YAML mapping.")
        raise SystemExit(1)

    has_input = "input" in raw
    has_folder = "input_folder" in raw
    if has_input and has_folder:
        err_console.print(
            "[bold red]Error:[/bold red] Use 'input' or 'input_folder', not both."
        )
        raise SystemExit(1)
    if not has_input and not has_folder:
        err_console.print(
            "[bold red]Error:[/bold red] Workflow must specify 'input' or 'input_folder'."
        )
        raise SystemExit(1)

    raw_steps = raw.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        err_console.print("[bold red]Error:[/bold red] 'steps' must be a non-empty list.")
        raise SystemExit(1)

    try:
        steps = [_parse_step(s) for s in raw_steps]
        for step in steps:
            _validate_step_params(step)
    except ValueError as exc:
        err_console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    if has_input:
        src = yaml_path.parent / str(raw["input"])
        if not src.exists():
            err_console.print(f"[bold red]Error:[/bold red] Input file not found: {src}")
            raise SystemExit(1)
        out = raw.get("output")
        if not out:
            err_console.print("[bold red]Error:[/bold red] 'output' is required with 'input'.")
            raise SystemExit(1)
        return WorkflowConfig(
            steps=steps,
            yaml_path=yaml_path,
            input=src,
            output=yaml_path.parent / str(out),
        )

    folder = yaml_path.parent / str(raw["input_folder"])
    if not folder.is_dir():
        err_console.print(
            f"[bold red]Error:[/bold red] 'input_folder' not found or not a directory: {folder}"
        )
        raise SystemExit(1)
    out_folder = raw.get("output_folder")
    if not out_folder:
        err_console.print(
            "[bold red]Error:[/bold red] 'output_folder' is required with 'input_folder'."
        )
        raise SystemExit(1)
    return WorkflowConfig(
        steps=steps,
        yaml_path=yaml_path,
        input_folder=folder,
        output_folder=yaml_path.parent / str(out_folder),
        pattern=str(raw.get("pattern", "*.pdf")),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _step_label(step: StepConfig) -> str:
    """Return a short human-readable description of a step."""
    p = step.params
    if step.name == "compress":
        return "compress"
    if step.name == "watermark":
        if "text" in p:
            return f'watermark: "{p["text"]}"'
        return f"watermark: {p['stamp']}"
    if step.name == "split":
        return f"split: pages {p['pages']}"
    if step.name == "rotate":
        suffix = f" on pages {p['pages']}" if "pages" in p else ""
        return f"rotate: {p['angle']}°{suffix}"
    if step.name == "reorder":
        return f"reorder: [{p['order']}]"
    return step.name  # unreachable after validation


def _execute_step(step: StepConfig, src: Path, dst: Path) -> None:
    """Execute one step, reading from *src* and writing to *dst*."""
    p = step.params
    if step.name == "compress":
        compress_pdf(src, dst)
    elif step.name == "watermark":
        stamp = Path(str(p["stamp"])) if "stamp" in p else None
        watermark_pdf(src, dst, watermark_text=p.get("text"), watermark_pdf=stamp)
    elif step.name == "split":
        from pypdf import PdfReader
        total = len(PdfReader(str(src)).pages)
        page_range = parse_page_range(str(p["pages"]), total)
        split_pdf(src, page_range, dst)
    elif step.name == "rotate":
        pages_str = str(p["pages"]) if "pages" in p else None
        page_list = [int(x.strip()) for x in pages_str.split(",")] if pages_str else None
        rotate_pdf(src, dst, int(p["angle"]), page_list)
    elif step.name == "reorder":
        order = [int(x.strip()) for x in str(p["order"]).split(",")]
        reorder_pdf(src, dst, order)


def _print_plan(cfg: WorkflowConfig) -> None:
    n = len(cfg.steps)
    console.print(f"[bold]Running workflow:[/bold] [cyan]{cfg.yaml_path.name}[/cyan]")
    for i, step in enumerate(cfg.steps, 1):
        console.print(f"  [{i}/{n}] {_step_label(step)}")
    console.print()


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def run_workflow(cfg: WorkflowConfig) -> None:
    """Dispatch to single-file or folder-mode execution."""
    if cfg.input_folder is not None:
        _run_folder_workflow(cfg)
    else:
        _run_single_workflow(cfg)


def _run_single_workflow(cfg: WorkflowConfig) -> None:
    _print_plan(cfg)

    out = cfg.output
    assert out is not None
    out.parent.mkdir(parents=True, exist_ok=True)

    n = len(cfg.steps)
    with tempfile.TemporaryDirectory(prefix="pdfuse_batch_") as tmp_dir:
        tmp = Path(tmp_dir)
        current = cfg.input
        assert current is not None

        for i, step in enumerate(cfg.steps):
            next_path = tmp / f"step_{i + 1}.pdf"
            console.rule(f"[dim][{i + 1}/{n}] {_step_label(step)}[/dim]")
            try:
                _execute_step(step, current, next_path)
            except SystemExit:
                err_console.print(
                    f"[bold red]Batch failed[/bold red] at step [{i + 1}/{n}] '{step.name}'."
                )
                raise SystemExit(1)
            except Exception as exc:
                err_console.print(
                    f"[bold red]Batch failed[/bold red] at step [{i + 1}/{n}] "
                    f"'{step.name}': {exc}"
                )
                raise SystemExit(1)
            current = next_path

        shutil.copy2(str(current), str(out))

    console.print(
        f"\n[bold green]✓[/bold green] Workflow complete → [cyan]{out}[/cyan]"
    )


def _run_folder_workflow(cfg: WorkflowConfig) -> None:
    folder = cfg.input_folder
    assert folder is not None
    out_folder = cfg.output_folder
    assert out_folder is not None
    out_folder.mkdir(parents=True, exist_ok=True)

    files = sorted(f for f in folder.glob(cfg.pattern) if f.is_file())
    if not files:
        console.print(
            f"[yellow]No files matching '{cfg.pattern}' found in {folder}[/yellow]"
        )
        return

    _print_plan(cfg)
    console.print(f"Processing [bold]{len(files)}[/bold] file(s)…\n")

    n = len(cfg.steps)
    succeeded = 0
    failed = 0

    for pdf in files:
        console.rule(f"[cyan]{pdf.name}[/cyan]")
        out = out_folder / pdf.name
        file_ok = True

        with tempfile.TemporaryDirectory(prefix="pdfuse_batch_") as tmp_dir:
            tmp = Path(tmp_dir)
            current = pdf

            for i, step in enumerate(cfg.steps):
                next_path = tmp / f"step_{i + 1}.pdf"
                console.print(f"  [{i + 1}/{n}] {_step_label(step)}…")
                try:
                    _execute_step(step, current, next_path)
                except SystemExit:
                    err_console.print(
                        f"[bold yellow]Warning:[/bold yellow] {pdf.name}: "
                        f"step '{step.name}' failed."
                    )
                    file_ok = False
                    break
                except Exception as exc:
                    err_console.print(
                        f"[bold yellow]Warning:[/bold yellow] {pdf.name}: "
                        f"step '{step.name}' failed: {exc}"
                    )
                    file_ok = False
                    break
                current = next_path

            if file_ok:
                shutil.copy2(str(current), str(out))
                succeeded += 1
            else:
                failed += 1

    console.print(
        f"\n[bold]Summary:[/bold] "
        f"[green]{succeeded} succeeded[/green], "
        + (f"[bold red]{failed} failed[/bold red]" if failed else "0 failed")
    )
    if failed:
        raise SystemExit(1)
