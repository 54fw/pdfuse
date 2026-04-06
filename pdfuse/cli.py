"""Click CLI entry point for pdfuse."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import click
from rich.console import Console
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
