"""Shared test helpers for the pdfuse test suite."""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path


def make_pdf_bytes(pages: int = 1) -> bytes:
    """Return bytes for a minimal valid PDF with *pages* blank pages."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def write_pdf(pages: int = 1, dir: str | None = None) -> Path:
    """Write a temporary PDF to *dir* and return its Path."""
    fd, name = tempfile.mkstemp(suffix=".pdf", dir=dir)
    os.write(fd, make_pdf_bytes(pages))
    os.close(fd)
    return Path(name)


def write_png(dir: str | None = None) -> Path:
    """Write a small RGB PNG to *dir* and return its Path."""
    from PIL import Image

    fd, name = tempfile.mkstemp(suffix=".png", dir=dir)
    os.close(fd)
    Image.new("RGB", (64, 64), color=(200, 100, 50)).save(name)
    return Path(name)


def write_rgba_png(dir: str | None = None) -> Path:
    """Write a small RGBA PNG (transparent channel) to *dir* and return its Path."""
    from PIL import Image

    fd, name = tempfile.mkstemp(suffix=".png", dir=dir)
    os.close(fd)
    Image.new("RGBA", (64, 64), color=(200, 100, 50, 128)).save(name)
    return Path(name)
