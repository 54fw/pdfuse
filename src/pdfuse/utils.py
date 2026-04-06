"""Utility helpers: file validation, path handling, page-range parsing."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

from rich.console import Console

console = Console(stderr=True)

SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}
SUPPORTED_OFFICE_EXTS = {".docx", ".pptx"}
SUPPORTED_CONVERT_EXTS = SUPPORTED_IMAGE_EXTS | SUPPORTED_OFFICE_EXTS


def validate_input_files(paths: List[str], allowed_exts: set[str] | None = None) -> List[Path]:
    """Validate that every path exists and (optionally) has an allowed extension.

    Raises SystemExit via *console.print* + raise so callers need not handle it.
    """
    validated: List[Path] = []
    for raw in paths:
        p = Path(raw)
        if not p.exists():
            console.print(f"[bold red]Error:[/bold red] File not found: {raw}")
            raise SystemExit(1)
        if not p.is_file():
            console.print(f"[bold red]Error:[/bold red] Not a file: {raw}")
            raise SystemExit(1)
        if allowed_exts is not None and p.suffix.lower() not in allowed_exts:
            console.print(
                f"[bold red]Error:[/bold red] Unsupported format '{p.suffix}'. "
                f"Allowed: {', '.join(sorted(allowed_exts))}"
            )
            raise SystemExit(1)
        validated.append(p)
    return validated


def validate_output_path(path: str) -> Path:
    """Ensure the output path's parent directory is writable."""
    p = Path(path)
    parent = p.parent
    if not parent.exists():
        console.print(f"[bold red]Error:[/bold red] Output directory does not exist: {parent}")
        raise SystemExit(1)
    if not os.access(parent, os.W_OK):
        console.print(f"[bold red]Error:[/bold red] Output directory is not writable: {parent}")
        raise SystemExit(1)
    return p


def parse_page_range(spec: str, total_pages: int) -> Tuple[int, int]:
    """Parse a page-range string like '2-5' into a (start, end) tuple (1-indexed, inclusive).

    Validates:
    - Format must be 'N-M' with N <= M
    - Both values must be within [1, total_pages]
    """
    try:
        parts = spec.split("-")
        if len(parts) != 2:
            raise ValueError
        start, end = int(parts[0]), int(parts[1])
    except ValueError:
        console.print(
            f"[bold red]Error:[/bold red] Invalid page range '{spec}'. "
            "Use format N-M, e.g. 1-3."
        )
        raise SystemExit(1)

    if start < 1 or end < 1:
        console.print(
            f"[bold red]Error:[/bold red] Page numbers must be positive (got {spec})."
        )
        raise SystemExit(1)

    if start > end:
        console.print(
            f"[bold red]Error:[/bold red] Start page {start} is greater than end page {end}."
        )
        raise SystemExit(1)

    if end > total_pages:
        console.print(
            f"[bold red]Error:[/bold red] Page range {spec} exceeds document length "
            f"({total_pages} page{'s' if total_pages != 1 else ''})."
        )
        raise SystemExit(1)

    return start, end


def default_output(input_path: Path, suffix: str = ".pdf") -> Path:
    """Return input path with extension replaced by *suffix*."""
    return input_path.with_suffix(suffix)
