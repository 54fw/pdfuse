"""Core PDF operations: merge, split, convert."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()
err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def merge_pdfs(inputs: List[Path], output: Path) -> int:
    """Merge *inputs* into *output*. Returns total page count."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    total_pages = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Merging PDFs…", total=len(inputs))
        for pdf_path in inputs:
            from pypdf import PdfReader
            reader = PdfReader(str(pdf_path))
            if len(reader.pages) == 0:
                err_console.print(
                    f"[bold yellow]Warning:[/bold yellow] {pdf_path.name} has 0 pages — skipping."
                )
                progress.advance(task)
                continue
            for page in reader.pages:
                writer.add_page(page)
                total_pages += 1
            progress.advance(task)

    with open(output, "wb") as f:
        writer.write(f)

    return total_pages


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------

def split_pdf(input_path: Path, page_range: Tuple[int, int], output: Path) -> int:
    """Extract pages [start, end] (1-indexed, inclusive) from *input_path* into *output*."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(input_path))
    total = len(reader.pages)

    if total == 0:
        err_console.print("[bold red]Error:[/bold red] Input PDF has 0 pages.")
        raise SystemExit(1)

    start, end = page_range  # already validated by utils.parse_page_range

    writer = PdfWriter()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Extracting pages {start}–{end}…", total=end - start + 1)
        for i in range(start - 1, end):
            writer.add_page(reader.pages[i])
            progress.advance(task)

    with open(output, "wb") as f:
        writer.write(f)

    return end - start + 1


# ---------------------------------------------------------------------------
# Convert
# ---------------------------------------------------------------------------

def convert_images_to_pdf(images: List[Path], output: Path) -> None:
    """Convert one or more images to a single PDF using Pillow."""
    from PIL import Image

    pil_images: List[Image.Image] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Loading images…", total=len(images))
        for img_path in images:
            img = Image.open(img_path)
            # Pillow cannot save RGBA (or palette with transparency) directly as PDF;
            # must convert to RGB first.
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")
            pil_images.append(img)
            progress.advance(task)

    if not pil_images:
        err_console.print("[bold red]Error:[/bold red] No valid images to convert.")
        raise SystemExit(1)

    first, rest = pil_images[0], pil_images[1:]
    first.save(str(output), "PDF", save_all=True, append_images=rest)


def convert_office_to_pdf(input_path: Path, output: Path) -> None:
    """Convert a .docx or .pptx file to PDF using docx2pdf."""
    try:
        from docx2pdf import convert  # type: ignore
    except ImportError:
        err_console.print(
            "[bold red]Error:[/bold red] docx2pdf is not installed. "
            "Run: pip install docx2pdf"
        )
        raise SystemExit(1)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(f"Converting {input_path.name}…", total=None)
            convert(str(input_path), str(output))
    except Exception as exc:
        err_console.print(
            f"[bold red]Error:[/bold red] Conversion failed: {exc}\n"
            "[dim]docx2pdf requires Microsoft Word on Windows/macOS, "
            "or LibreOffice on Linux.[/dim]"
        )
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# Info
# ---------------------------------------------------------------------------

def pdf_info(input_path: Path) -> dict:
    """Return a dict of PDF metadata."""
    from pypdf import PdfReader

    reader = PdfReader(str(input_path))
    meta = reader.metadata or {}
    size_kb = input_path.stat().st_size / 1024

    return {
        "File": input_path.name,
        "Pages": len(reader.pages),
        "Size": f"{size_kb:.1f} KB",
        "Title": meta.get("/Title", "—"),
        "Author": meta.get("/Author", "—"),
        "Creator": meta.get("/Creator", "—"),
        "Producer": meta.get("/Producer", "—"),
    }
