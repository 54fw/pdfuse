"""Batch workflow execution: parse a YAML workflow file and run steps in sequence."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

from pdfuse.operations import compress_pdf, merge_pdfs, reorder_pdf, rotate_pdf, split_pdf, watermark_pdf
from pdfuse.utils import parse_page_range

console = Console()
err_console = Console(stderr=True)

VALID_STEPS = {"compress", "merge", "watermark", "split", "rotate", "reorder"}

_ALLOWED_PARAMS: dict[str, set[str]] = {
    "compress":  set(),
    "merge":     {"with", "sort", "reverse", "pattern"},
    "watermark": {"text", "stamp", "pages"},
    "split":     {"pages"},
    "rotate":    {"angle", "pages"},
    "reorder":   {"order"},
}


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
    output_folder: Path | None = None  # per-file output dir OR folder-merge output dir
    output_name: str = "merged.pdf"    # filename when merge step writes into output_folder
    pattern: str = "*.pdf"             # used by per-file folder mode; CLI --pattern overrides


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
    """Raise ValueError if a step's parameters are missing, conflicting, or unrecognised."""
    p = step.params
    allowed = _ALLOWED_PARAMS.get(step.name, set())
    unknown = set(p.keys()) - allowed
    if unknown:
        raise ValueError(
            f"Step '{step.name}': unknown parameter(s): {', '.join(sorted(unknown))}"
        )
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
    elif step.name == "merge":
        # 'with' (single-file context) and 'sort/reverse/pattern' (folder context)
        # are both optional here; context-specific validation happens in load_workflow.
        if "sort" in p and p["sort"] not in ("name", "date"):
            raise ValueError("Step 'merge': sort must be 'name' or 'date'")


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

    has_merge_step = any(s.name == "merge" for s in steps)

    # ---- single-file mode ----
    if has_input:
        src = yaml_path.parent / str(raw["input"])
        if not src.exists():
            err_console.print(f"[bold red]Error:[/bold red] Input file not found: {src}")
            raise SystemExit(1)
        out = raw.get("output")
        if not out:
            err_console.print("[bold red]Error:[/bold red] 'output' is required with 'input'.")
            raise SystemExit(1)

        # In single-file mode: merge step requires 'with'
        for step in steps:
            if step.name == "merge" and "with" not in step.params:
                err_console.print(
                    "[bold red]Error:[/bold red] Step 'merge' in single-file workflow "
                    "requires 'with' (comma-separated paths or YAML list)."
                )
                raise SystemExit(1)

        # Resolve 'with' paths relative to yaml location
        for step in steps:
            if step.name == "merge":
                raw_with = step.params["with"]
                if isinstance(raw_with, list):
                    path_strs = [str(x).strip() for x in raw_with]
                else:
                    path_strs = [s.strip() for s in str(raw_with).split(",") if s.strip()]
                resolved = []
                for ps in path_strs:
                    fp = yaml_path.parent / ps
                    if not fp.exists():
                        err_console.print(
                            f"[bold red]Error:[/bold red] File not found in merge step: {fp}"
                        )
                        raise SystemExit(1)
                    resolved.append(str(fp))
                step.params["with"] = resolved

        return WorkflowConfig(
            steps=steps,
            yaml_path=yaml_path,
            input=src,
            output=yaml_path.parent / str(out),
        )

    # ---- folder mode ----
    folder = yaml_path.parent / str(raw["input_folder"])
    if not folder.is_dir():
        err_console.print(
            f"[bold red]Error:[/bold red] 'input_folder' not found or not a directory: {folder}"
        )
        raise SystemExit(1)

    has_output = "output" in raw
    has_output_folder = "output_folder" in raw

    if has_output and has_output_folder:
        err_console.print(
            "[bold red]Error:[/bold red] Use 'output' or 'output_folder', not both."
        )
        raise SystemExit(1)

    if has_merge_step:
        if not has_output and not has_output_folder:
            err_console.print(
                "[bold red]Error:[/bold red] Workflow with 'merge' step requires "
                "'output_folder' or 'output'."
            )
            raise SystemExit(1)
        # In folder mode: merge step must NOT have 'with'
        for step in steps:
            if step.name == "merge" and "with" in step.params:
                err_console.print(
                    "[bold red]Error:[/bold red] Step 'merge' in folder workflow must not use "
                    "'with'. Use 'sort', 'reverse', and 'pattern' instead."
                )
                raise SystemExit(1)
    else:
        if not has_output_folder:
            err_console.print(
                "[bold red]Error:[/bold red] 'output_folder' is required with 'input_folder' "
                "(use 'output' only when a 'merge' step is present)."
            )
            raise SystemExit(1)

    pattern = str(raw.get("pattern", "*.pdf"))
    output_name = str(raw.get("output_name", "merged.pdf"))

    if has_output_folder:
        return WorkflowConfig(
            steps=steps,
            yaml_path=yaml_path,
            input_folder=folder,
            output_folder=yaml_path.parent / str(raw["output_folder"]),
            output_name=output_name,
            pattern=pattern,
        )

    return WorkflowConfig(
        steps=steps,
        yaml_path=yaml_path,
        input_folder=folder,
        output=yaml_path.parent / str(raw["output"]),
        pattern=pattern,
        output_name=output_name,
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
    if step.name == "merge":
        if "with" in p:
            n = len(p["with"]) if isinstance(p["with"], list) else len(str(p["with"]).split(","))
            return f"merge: +{n} file(s)"
        pattern = p.get("pattern", "*.pdf")
        sort = p.get("sort", "name")
        rev = " \u2193" if p.get("reverse", False) else ""
        return f"merge: all '{pattern}' (sort={sort}{rev})"
    return step.name  # unreachable after validation


def _execute_step(step: StepConfig, src: Path, dst: Path) -> None:
    """Execute one step, reading from *src* and writing to *dst*.

    Only called for non-merge steps in folder context, and for merge with 'with' in single-file.
    """
    p = step.params
    if step.name == "compress":
        compress_pdf(src, dst)
    elif step.name == "watermark":
        stamp = Path(str(p["stamp"])) if "stamp" in p else None
        pages_str = str(p["pages"]) if "pages" in p else None
        page_list = [int(x.strip()) for x in pages_str.split(",")] if pages_str else None
        watermark_pdf(src, dst, watermark_text=p.get("text"), watermark_pdf=stamp, pages=page_list)
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
    elif step.name == "merge":
        # Only reached in single-file context (with 'with' param)
        extra = [Path(f) for f in p["with"]]
        merge_pdfs([src] + extra, dst)


def _print_plan(cfg: WorkflowConfig) -> None:
    n = len(cfg.steps)
    console.print(f"[bold]Running workflow:[/bold] [cyan]{cfg.yaml_path.name}[/cyan]")
    for i, step in enumerate(cfg.steps, 1):
        console.print(f"  [{i}/{n}] {_step_label(step)}")
    console.print()


def _run_file_pipeline(
    pdf: Path,
    steps: list[StepConfig],
    tmp: Path,
    prefix: str,
) -> Path | None:
    """Run all steps on *pdf*, writing intermediates under *tmp*.

    Returns the path of the final result, or None if any step failed.
    """
    current: Path = pdf
    for i, step in enumerate(steps):
        next_path = tmp / f"{prefix}_step_{i + 1}.pdf"
        try:
            _execute_step(step, current, next_path)
        except (SystemExit, Exception) as exc:
            msg = str(exc) if not isinstance(exc, SystemExit) else "operation failed"
            err_console.print(
                f"[bold yellow]Warning:[/bold yellow] {pdf.name}: "
                f"step '{step.name}' failed: {msg}"
            )
            return None
        current = next_path
    return current


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def run_workflow(cfg: WorkflowConfig) -> None:
    """Dispatch to single-file, per-file folder, or folder-merge execution."""
    if cfg.input_folder is not None:
        merge_idx = next((i for i, s in enumerate(cfg.steps) if s.name == "merge"), None)
        if merge_idx is not None:
            _run_folder_merge_pipeline(cfg, merge_idx)
        else:
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
    """Per-file folder mode: apply all steps to each file independently."""
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


def _run_folder_merge_pipeline(cfg: WorkflowConfig, merge_idx: int) -> None:
    """Folder-merge mode: pre-steps applied per-file, merge, then post-steps on merged file."""
    import datetime

    folder = cfg.input_folder
    assert folder is not None

    merge_step = cfg.steps[merge_idx]
    m_pattern = str(merge_step.params.get("pattern", "*.pdf"))
    m_sort = str(merge_step.params.get("sort", "name"))
    m_reverse = bool(merge_step.params.get("reverse", False))

    files = [f for f in folder.glob(m_pattern) if f.is_file()]
    if not files:
        console.print(
            f"[yellow]No files matching '{m_pattern}' found in {folder}[/yellow]"
        )
        return

    if m_sort == "name":
        files.sort(key=lambda p: p.name.lower(), reverse=m_reverse)
    else:
        files.sort(key=lambda p: p.stat().st_mtime, reverse=m_reverse)

    _print_plan(cfg)

    from rich.table import Table
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="dim")
    table.add_column("File")
    table.add_column("Modified", style="dim")
    for i, f in enumerate(files, 1):
        mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        table.add_row(str(i), f.name, mtime)
    console.print(table)
    console.print()

    pre_steps = cfg.steps[:merge_idx]
    post_steps = cfg.steps[merge_idx + 1:]

    # Determine output path
    if cfg.output is not None:
        out = cfg.output
    else:
        assert cfg.output_folder is not None
        out = cfg.output_folder / cfg.output_name
    out.parent.mkdir(parents=True, exist_ok=True)

    pre_succeeded = 0
    pre_failed = 0
    processed: list[Path] = []

    with tempfile.TemporaryDirectory(prefix="pdfuse_batch_") as tmp_dir:
        tmp = Path(tmp_dir)

        # --- pre-merge steps (per-file) ---
        for idx, pdf in enumerate(files):
            if pre_steps:
                console.rule(f"[cyan]{pdf.name}[/cyan]")
            result = _run_file_pipeline(pdf, pre_steps, tmp, prefix=f"pre{idx}")
            if result is not None:
                stable = tmp / f"ready_{idx}.pdf"
                shutil.copy2(str(result), str(stable))
                processed.append(stable)
                pre_succeeded += 1
            else:
                pre_failed += 1

        if not processed:
            err_console.print(
                "[bold red]Error:[/bold red] No files succeeded in pre-merge steps; "
                "nothing to merge."
            )
            raise SystemExit(1)

        # --- merge ---
        console.rule("[dim]merging[/dim]")
        merged_tmp = tmp / "merged.pdf"
        merge_pdfs(processed, merged_tmp)

        # --- post-merge steps (single file) ---
        final = _run_file_pipeline(merged_tmp, post_steps, tmp, prefix="post")
        if final is None:
            err_console.print(
                "[bold red]Batch failed[/bold red] in post-merge steps."
            )
            raise SystemExit(1)

        shutil.copy2(str(final), str(out))

    console.print(
        f"\n[bold]Summary:[/bold] "
        f"[green]{pre_succeeded} succeeded[/green], "
        + (f"[bold red]{pre_failed} failed[/bold red]" if pre_failed else "0 failed")
    )
    console.print(
        f"[bold green]✓[/bold green] Merged {len(processed)} file(s) → [cyan]{out}[/cyan]"
    )
    if pre_failed:
        raise SystemExit(1)
