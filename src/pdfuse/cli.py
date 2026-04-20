"""Click CLI entry point for pdfuse."""

from __future__ import annotations

import concurrent.futures
from pathlib import Path
from typing import Callable, Tuple

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from pdfuse import __version__
from pdfuse.utils import (
    SUPPORTED_IMAGE_EXTS,
    SUPPORTED_OFFICE_EXTS,
    SUPPORTED_CONVERT_EXTS,
    default_output,
    parse_page_range,
    validate_input_files,
    validate_output_path,
)
from pdfuse.operations import (
    compress_pdf,
    convert_images_to_pdf,
    convert_office_to_pdf,
    merge_pdfs,
    pdf_info,
    reorder_pdf,
    rotate_pdf,
    split_pdf,
    watermark_pdf,
)

console = Console()
err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(__version__, prog_name="pdfuse")
def main() -> None:
    """pdfuse — merge, split, and convert files to PDF from the terminal."""


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------

@main.command("merge")
@click.argument("inputs", nargs=-1, required=True, metavar="FILE [FILE ...]")
@click.option("-o", "--output", default=None, help="Output PDF path (default: merged.pdf)")
def cmd_merge(inputs: Tuple[str, ...], output: str | None) -> None:
    """Merge multiple PDFs into a single file in the given order."""
    if not inputs:
        err_console.print("[bold red]Error:[/bold red] No input files provided.")
        raise SystemExit(1)

    validated = validate_input_files(list(inputs), allowed_exts={".pdf"})

    out_path = validate_output_path(output or "merged.pdf")

    total_pages = merge_pdfs(validated, out_path)

    console.print(
        f"[bold green]✓[/bold green] Merged {len(validated)} file(s) → "
        f"[cyan]{out_path}[/cyan] ({total_pages} page{'s' if total_pages != 1 else ''})"
    )


# ---------------------------------------------------------------------------
# split
# ---------------------------------------------------------------------------

@main.command("split")
@click.argument("input", metavar="FILE")
@click.option(
    "--pages",
    required=True,
    metavar="N-M",
    help="Page range to extract, e.g. 1-3",
)
@click.option("-o", "--output", default=None, help="Output PDF path (default: split_output.pdf)")
def cmd_split(input: str, pages: str, output: str | None) -> None:
    """Extract a page range from a PDF."""
    validated = validate_input_files([input], allowed_exts={".pdf"})
    src = validated[0]

    # We need the total page count before validating the range.
    from pypdf import PdfReader
    reader = PdfReader(str(src))
    total = len(reader.pages)
    if total == 0:
        err_console.print("[bold red]Error:[/bold red] Input PDF has 0 pages.")
        raise SystemExit(1)

    page_range = parse_page_range(pages, total)
    out_path = validate_output_path(output or "split_output.pdf")

    extracted = split_pdf(src, page_range, out_path)

    console.print(
        f"[bold green]✓[/bold green] Extracted {extracted} page(s) "
        f"(range {pages}) → [cyan]{out_path}[/cyan]"
    )


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------

@main.command("convert")
@click.argument("inputs", nargs=-1, required=True, metavar="FILE [FILE ...]")
@click.option("-o", "--output", default=None, help="Output PDF path")
def cmd_convert(inputs: Tuple[str, ...], output: str | None) -> None:
    """Convert images or Office documents to PDF.

    \b
    Supported formats:
      Images : PNG, JPG, JPEG, BMP, TIFF
      Office : DOCX, PPTX (requires Microsoft Word or LibreOffice)

    When multiple images are given, they are merged into one PDF.
    """
    if not inputs:
        err_console.print("[bold red]Error:[/bold red] No input files provided.")
        raise SystemExit(1)

    validated = validate_input_files(list(inputs), allowed_exts=SUPPORTED_CONVERT_EXTS)

    # Determine conversion type from the first file's extension.
    first_ext = validated[0].suffix.lower()
    is_office = first_ext in SUPPORTED_OFFICE_EXTS

    # For office files, only one input is accepted.
    if is_office:
        if len(validated) > 1:
            err_console.print(
                "[bold red]Error:[/bold red] Only one Office document can be converted at a time."
            )
            raise SystemExit(1)
        out_path = validate_output_path(output or str(default_output(validated[0])))
        convert_office_to_pdf(validated[0], out_path)
        console.print(
            f"[bold green]✓[/bold green] Converted [cyan]{validated[0].name}[/cyan] → "
            f"[cyan]{out_path}[/cyan]"
        )
    else:
        # Image(s)
        for p in validated:
            if p.suffix.lower() not in SUPPORTED_IMAGE_EXTS:
                err_console.print(
                    f"[bold red]Error:[/bold red] Cannot mix image and Office files: {p.name}"
                )
                raise SystemExit(1)

        if output:
            out_path = validate_output_path(output)
        elif len(validated) == 1:
            out_path = validate_output_path(str(default_output(validated[0])))
        else:
            out_path = validate_output_path("merged.pdf")

        convert_images_to_pdf(validated, out_path)

        if len(validated) == 1:
            console.print(
                f"[bold green]✓[/bold green] Converted [cyan]{validated[0].name}[/cyan] → "
                f"[cyan]{out_path}[/cyan]"
            )
        else:
            console.print(
                f"[bold green]✓[/bold green] Converted {len(validated)} image(s) → "
                f"[cyan]{out_path}[/cyan]"
            )


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------

@main.command("info")
@click.argument("input", metavar="FILE")
def cmd_info(input: str) -> None:
    """Display metadata for a PDF file."""
    validated = validate_input_files([input], allowed_exts={".pdf"})
    src = validated[0]

    info = pdf_info(src)

    table = Table(title=f"PDF Info: {src.name}", show_header=True, header_style="bold cyan")
    table.add_column("Field", style="bold")
    table.add_column("Value")

    for key, value in info.items():
        table.add_row(key, str(value))

    console.print(table)


# ---------------------------------------------------------------------------
# compress
# ---------------------------------------------------------------------------

@main.command("compress")
@click.argument("input", metavar="FILE")
@click.option("-o", "--output", default=None, help="Output PDF path (default: compressed.pdf)")
def cmd_compress(input: str, output: str | None) -> None:
    """Compress a PDF by compressing its content streams."""
    validated = validate_input_files([input], allowed_exts={".pdf"})
    src = validated[0]
    out_path = validate_output_path(output or "compressed.pdf")

    original_kb, compressed_kb = compress_pdf(src, out_path)
    saved = original_kb - compressed_kb
    pct = (saved / original_kb * 100) if original_kb else 0

    console.print(
        f"[bold green]✓[/bold green] Compressed [cyan]{src.name}[/cyan] → "
        f"[cyan]{out_path}[/cyan] "
        f"({original_kb} KB → {compressed_kb} KB, "
        f"[bold]{pct:.1f}%[/bold] reduction)"
    )


# ---------------------------------------------------------------------------
# rotate
# ---------------------------------------------------------------------------

@main.command("rotate")
@click.argument("input", metavar="FILE")
@click.option(
    "--angle",
    required=True,
    type=click.Choice(["90", "180", "270"]),
    help="Rotation angle in degrees (clockwise).",
)
@click.option(
    "--pages",
    default=None,
    metavar="N[,N...]",
    help="Comma-separated 1-indexed page numbers to rotate (default: all pages).",
)
@click.option("-o", "--output", default=None, help="Output PDF path (default: rotated.pdf)")
def cmd_rotate(input: str, angle: str, pages: str | None, output: str | None) -> None:
    """Rotate pages in a PDF by 90, 180, or 270 degrees."""
    validated = validate_input_files([input], allowed_exts={".pdf"})
    src = validated[0]
    out_path = validate_output_path(output or "rotated.pdf")

    page_list = None
    if pages:
        try:
            page_list = [int(p.strip()) for p in pages.split(",")]
        except ValueError:
            err_console.print(
                "[bold red]Error:[/bold red] --pages must be comma-separated integers, e.g. 1,3,5"
            )
            raise SystemExit(1)

    rotated = rotate_pdf(src, out_path, int(angle), page_list)

    page_desc = f"page{'s' if rotated != 1 else ''} {pages}" if pages else "all pages"
    console.print(
        f"[bold green]✓[/bold green] Rotated {rotated} {page_desc} by {angle}° → "
        f"[cyan]{out_path}[/cyan]"
    )


# ---------------------------------------------------------------------------
# watermark
# ---------------------------------------------------------------------------

@main.command("watermark")
@click.argument("input", metavar="FILE")
@click.option("--text", default=None, metavar="TEXT", help="Watermark text to stamp on every page.")
@click.option(
    "--stamp",
    default=None,
    metavar="STAMP_PDF",
    help="Path to a single-page PDF used as the watermark stamp.",
)
@click.option("-o", "--output", default=None, help="Output PDF path (default: watermarked.pdf)")
def cmd_watermark(input: str, text: str | None, stamp: str | None, output: str | None) -> None:
    """Add a text or PDF stamp watermark to every page.

    \b
    Examples:
      pdfuse watermark doc.pdf --text "CONFIDENTIAL"
      pdfuse watermark doc.pdf --stamp logo.pdf
    """
    if text is None and stamp is None:
        err_console.print(
            "[bold red]Error:[/bold red] Provide either --text TEXT or --stamp STAMP_PDF."
        )
        raise SystemExit(1)
    if text is not None and stamp is not None:
        err_console.print(
            "[bold red]Error:[/bold red] Use only one of --text or --stamp, not both."
        )
        raise SystemExit(1)

    validated = validate_input_files([input], allowed_exts={".pdf"})
    src = validated[0]

    stamp_path = None
    if stamp:
        stamp_validated = validate_input_files([stamp], allowed_exts={".pdf"})
        stamp_path = stamp_validated[0]

    out_path = validate_output_path(output or "watermarked.pdf")

    pages = watermark_pdf(src, out_path, watermark_text=text, watermark_pdf=stamp_path)

    label = f'"{text}"' if text else stamp_path.name  # type: ignore[union-attr]
    console.print(
        f"[bold green]✓[/bold green] Watermarked {pages} page(s) with {label} → "
        f"[cyan]{out_path}[/cyan]"
    )


# ---------------------------------------------------------------------------
# reorder
# ---------------------------------------------------------------------------

@main.command("reorder")
@click.argument("input", metavar="FILE")
@click.option(
    "--order",
    required=True,
    metavar="N[,N...]",
    help="Comma-separated 1-indexed page order, e.g. 3,1,2 or 1,1,2,3.",
)
@click.option("-o", "--output", default=None, help="Output PDF path (default: reordered.pdf)")
def cmd_reorder(input: str, order: str, output: str | None) -> None:
    """Reorder (or duplicate/omit) pages in a PDF.

    \b
    Examples:
      pdfuse reorder doc.pdf --order 3,1,2
      pdfuse reorder doc.pdf --order 1,2,1,3   # page 1 appears twice
    """
    validated = validate_input_files([input], allowed_exts={".pdf"})
    src = validated[0]

    try:
        page_order = [int(p.strip()) for p in order.split(",")]
    except ValueError:
        err_console.print(
            "[bold red]Error:[/bold red] --order must be comma-separated integers, e.g. 3,1,2"
        )
        raise SystemExit(1)

    if not page_order:
        err_console.print("[bold red]Error:[/bold red] --order cannot be empty.")
        raise SystemExit(1)

    out_path = validate_output_path(output or "reordered.pdf")

    written = reorder_pdf(src, out_path, page_order)

    console.print(
        f"[bold green]✓[/bold green] Wrote {written} page(s) in order [{order}] → "
        f"[cyan]{out_path}[/cyan]"
    )


# ---------------------------------------------------------------------------
# folder
# ---------------------------------------------------------------------------

@main.group("folder")
def cmd_folder() -> None:
    """Apply a pdfuse operation to every PDF in a directory."""


def _folder_options(fn: Callable) -> Callable:
    fn = click.option("--workers", default=1, show_default=True, type=int, metavar="INT", help="Parallel workers.")(fn)
    fn = click.option("--pattern", default="*.pdf", show_default=True, metavar="TEXT", help="Glob pattern to filter files.")(fn)
    fn = click.option("--recursive", is_flag=True, default=False, help="Also process PDFs in subdirectories.")(fn)
    fn = click.option("-o", "--output", required=True, metavar="DIR", help="Output directory.")(fn)
    fn = click.argument("directory", metavar="DIR")(fn)
    return fn


def _collect_pdfs(directory: Path, recursive: bool, pattern: str) -> list[Path]:
    if recursive:
        return sorted(f for f in directory.rglob(pattern) if f.is_file())
    return sorted(f for f in directory.glob(pattern) if f.is_file())


def _run_folder(
    directory: str,
    output: str,
    recursive: bool,
    pattern: str,
    workers: int,
    process_one: Callable[[Path, Path], None],
    label: str,
) -> None:
    src_dir = Path(directory)
    if not src_dir.is_dir():
        err_console.print(f"[bold red]Error:[/bold red] Not a directory: {directory}")
        raise SystemExit(1)

    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = _collect_pdfs(src_dir, recursive, pattern)
    if not files:
        console.print(f"[yellow]No files matching '{pattern}' found in {src_dir}[/yellow]")
        return

    total = len(files)
    console.print(f"Found [bold]{total}[/bold] file(s) — {label}…\n")

    succeeded = 0
    failed = 0

    def _safe(pdf: Path) -> tuple[bool, str]:
        out_path = out_dir / pdf.relative_to(src_dir)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            process_one(pdf, out_path)
            return True, ""
        except SystemExit:
            return False, "operation failed"
        except Exception as exc:
            return False, str(exc)

    if workers == 1:
        for i, pdf in enumerate(files, 1):
            console.rule(f"[dim]{pdf.relative_to(src_dir)} ({i}/{total})[/dim]")
            ok, msg = _safe(pdf)
            if ok:
                succeeded += 1
            else:
                failed += 1
                err_console.print(f"[bold yellow]Warning:[/bold yellow] {pdf.name}: {msg}")
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"{label}…", total=total)
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                fmap = {executor.submit(_safe, pdf): pdf for pdf in files}
                for fut in concurrent.futures.as_completed(fmap):
                    pdf = fmap[fut]
                    ok, msg = fut.result()
                    if ok:
                        succeeded += 1
                    else:
                        failed += 1
                        err_console.print(
                            f"[bold yellow]Warning:[/bold yellow] {pdf.name}: {msg}"
                        )
                    progress.advance(task)

    console.print(
        f"\n[bold]Summary:[/bold] "
        f"[green]{succeeded} succeeded[/green], "
        + (f"[bold red]{failed} failed[/bold red]" if failed else "0 failed")
    )
    if failed:
        raise SystemExit(1)


@cmd_folder.command("compress")
@_folder_options
def folder_compress(
    directory: str, output: str, recursive: bool, pattern: str, workers: int
) -> None:
    """Compress all PDFs in a directory."""
    _run_folder(
        directory, output, recursive, pattern, workers,
        lambda src, dst: compress_pdf(src, dst),
        "Compressing",
    )


@cmd_folder.command("rotate")
@_folder_options
@click.option(
    "--angle",
    required=True,
    type=click.Choice(["90", "180", "270"]),
    help="Rotation angle in degrees (clockwise).",
)
@click.option(
    "--pages",
    default=None,
    metavar="N[,N...]",
    help="Comma-separated 1-indexed page numbers to rotate (default: all).",
)
def folder_rotate(
    directory: str, output: str, recursive: bool, pattern: str, workers: int,
    angle: str, pages: str | None,
) -> None:
    """Rotate pages in all PDFs in a directory."""
    page_list: list[int] | None = None
    if pages:
        try:
            page_list = [int(p.strip()) for p in pages.split(",")]
        except ValueError:
            err_console.print(
                "[bold red]Error:[/bold red] --pages must be comma-separated integers, e.g. 1,3,5"
            )
            raise SystemExit(1)

    _run_folder(
        directory, output, recursive, pattern, workers,
        lambda src, dst: rotate_pdf(src, dst, int(angle), page_list),
        f"Rotating by {angle}°",
    )


@cmd_folder.command("watermark")
@_folder_options
@click.option("--text", default=None, metavar="TEXT", help="Watermark text.")
@click.option(
    "--stamp",
    default=None,
    metavar="STAMP_PDF",
    help="Path to a single-page PDF stamp.",
)
def folder_watermark(
    directory: str, output: str, recursive: bool, pattern: str, workers: int,
    text: str | None, stamp: str | None,
) -> None:
    """Watermark all PDFs in a directory."""
    if text is None and stamp is None:
        err_console.print(
            "[bold red]Error:[/bold red] Provide either --text TEXT or --stamp STAMP_PDF."
        )
        raise SystemExit(1)
    if text is not None and stamp is not None:
        err_console.print(
            "[bold red]Error:[/bold red] Use only one of --text or --stamp, not both."
        )
        raise SystemExit(1)

    stamp_path: Path | None = None
    if stamp:
        stamp_validated = validate_input_files([stamp], allowed_exts={".pdf"})
        stamp_path = stamp_validated[0]

    label = f'Watermarking with "{text}"' if text else f"Watermarking with {stamp_path.name}"  # type: ignore[union-attr]
    _run_folder(
        directory, output, recursive, pattern, workers,
        lambda src, dst: watermark_pdf(src, dst, watermark_text=text, watermark_pdf=stamp_path),
        label,
    )


@cmd_folder.command("reorder")
@_folder_options
@click.option(
    "--order",
    required=True,
    metavar="N[,N...]",
    help="Comma-separated 1-indexed page order, e.g. 3,1,2.",
)
def folder_reorder(
    directory: str, output: str, recursive: bool, pattern: str, workers: int,
    order: str,
) -> None:
    """Reorder pages in all PDFs in a directory."""
    try:
        page_order = [int(p.strip()) for p in order.split(",")]
    except ValueError:
        err_console.print(
            "[bold red]Error:[/bold red] --order must be comma-separated integers, e.g. 3,1,2"
        )
        raise SystemExit(1)

    if not page_order:
        err_console.print("[bold red]Error:[/bold red] --order cannot be empty.")
        raise SystemExit(1)

    _run_folder(
        directory, output, recursive, pattern, workers,
        lambda src, dst: reorder_pdf(src, dst, page_order),
        f"Reordering [{order}]",
    )


@cmd_folder.command("merge")
@click.argument("directory", metavar="DIR")
@click.option("-o", "--output", required=True, metavar="FILE", help="Output PDF path.")
@click.option(
    "--sort",
    type=click.Choice(["name", "date"]),
    default="name",
    show_default=True,
    help="Sort order: name = alphabetical, date = last modified.",
)
@click.option("--reverse", is_flag=True, default=False, help="Reverse the sort order.")
@click.option("--recursive", is_flag=True, default=False, help="Include PDFs from subdirectories.")
@click.option("--pattern", default="*.pdf", show_default=True, metavar="TEXT", help="Glob pattern to filter files.")
def folder_merge(
    directory: str,
    output: str,
    sort: str,
    reverse: bool,
    recursive: bool,
    pattern: str,
) -> None:
    """Merge all PDFs in a directory into a single file."""
    import datetime

    src_dir = Path(directory)
    if not src_dir.is_dir():
        err_console.print(f"[bold red]Error:[/bold red] Not a directory: {directory}")
        raise SystemExit(1)

    files = _collect_pdfs(src_dir, recursive, pattern)
    if not files:
        console.print(f"[yellow]No files matching '{pattern}' found in {src_dir}[/yellow]")
        return

    if sort == "name":
        files.sort(key=lambda p: p.name.lower(), reverse=reverse)
    else:
        files.sort(key=lambda p: p.stat().st_mtime, reverse=reverse)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="dim")
    table.add_column("File")
    table.add_column("Modified", style="dim")
    for i, f in enumerate(files, 1):
        mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        table.add_row(str(i), str(f.relative_to(src_dir)), mtime)
    console.print(table)
    console.print()

    out_path = validate_output_path(output)
    total_pages = merge_pdfs(files, out_path)

    console.print(
        f"[bold green]✓[/bold green] Merged {len(files)} file(s) → "
        f"[cyan]{out_path}[/cyan] ({total_pages} page{'s' if total_pages != 1 else ''})"
    )
