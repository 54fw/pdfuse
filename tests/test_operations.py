"""Unit tests for pdfuse.operations and pdfuse.utils."""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers to create minimal in-memory PDFs via pypdf
# ---------------------------------------------------------------------------

def _make_pdf(pages: int = 1) -> bytes:
    """Return raw bytes of a minimal valid PDF with *pages* blank pages."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _write_tmp_pdf(pages: int = 1, dir: str | None = None) -> Path:
    fd, name = tempfile.mkstemp(suffix=".pdf", dir=dir)
    os.write(fd, _make_pdf(pages))
    os.close(fd)
    return Path(name)


def _write_tmp_png(dir: str | None = None) -> Path:
    """Create a tiny solid-colour PNG."""
    from PIL import Image
    fd, name = tempfile.mkstemp(suffix=".png", dir=dir)
    os.close(fd)
    img = Image.new("RGB", (64, 64), color=(200, 100, 50))
    img.save(name)
    return Path(name)


def _write_tmp_rgba_png(dir: str | None = None) -> Path:
    """Create a tiny RGBA PNG (transparent channel)."""
    from PIL import Image
    fd, name = tempfile.mkstemp(suffix=".png", dir=dir)
    os.close(fd)
    img = Image.new("RGBA", (64, 64), color=(200, 100, 50, 128))
    img.save(name)
    return Path(name)


# ---------------------------------------------------------------------------
# Tests: utils.parse_page_range
# ---------------------------------------------------------------------------

class TestParsePageRange:
    def test_valid_range(self):
        from pdfuse.utils import parse_page_range
        assert parse_page_range("1-3", 5) == (1, 3)

    def test_single_page(self):
        from pdfuse.utils import parse_page_range
        assert parse_page_range("2-2", 5) == (2, 2)

    def test_full_range(self):
        from pdfuse.utils import parse_page_range
        assert parse_page_range("1-5", 5) == (1, 5)

    def test_start_greater_than_end_raises(self):
        from pdfuse.utils import parse_page_range
        with pytest.raises(SystemExit):
            parse_page_range("5-2", 10)

    def test_range_exceeds_total_raises(self):
        from pdfuse.utils import parse_page_range
        with pytest.raises(SystemExit):
            parse_page_range("10-20", 5)

    def test_invalid_format_raises(self):
        from pdfuse.utils import parse_page_range
        with pytest.raises(SystemExit):
            parse_page_range("abc", 5)

    def test_zero_start_raises(self):
        from pdfuse.utils import parse_page_range
        with pytest.raises(SystemExit):
            parse_page_range("0-3", 5)


# ---------------------------------------------------------------------------
# Tests: operations.merge_pdfs
# ---------------------------------------------------------------------------

class TestMergePdfs:
    def test_merge_two_pdfs(self, tmp_path):
        from pdfuse.operations import merge_pdfs
        a = _write_tmp_pdf(3, dir=str(tmp_path))
        b = _write_tmp_pdf(2, dir=str(tmp_path))
        out = tmp_path / "merged.pdf"
        total = merge_pdfs([a, b], out)
        assert total == 5
        assert out.exists()

    def test_merge_single_pdf(self, tmp_path):
        from pdfuse.operations import merge_pdfs
        a = _write_tmp_pdf(4, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        total = merge_pdfs([a], out)
        assert total == 4
        assert out.exists()

    def test_merged_page_count_correct(self, tmp_path):
        from pdfuse.operations import merge_pdfs
        from pypdf import PdfReader
        a = _write_tmp_pdf(2, dir=str(tmp_path))
        b = _write_tmp_pdf(3, dir=str(tmp_path))
        out = tmp_path / "merged.pdf"
        merge_pdfs([a, b], out)
        reader = PdfReader(str(out))
        assert len(reader.pages) == 5


# ---------------------------------------------------------------------------
# Tests: operations.split_pdf
# ---------------------------------------------------------------------------

class TestSplitPdf:
    def test_split_range(self, tmp_path):
        from pdfuse.operations import split_pdf
        from pypdf import PdfReader
        src = _write_tmp_pdf(5, dir=str(tmp_path))
        out = tmp_path / "split.pdf"
        extracted = split_pdf(src, (2, 4), out)
        assert extracted == 3
        reader = PdfReader(str(out))
        assert len(reader.pages) == 3

    def test_split_single_page(self, tmp_path):
        from pdfuse.operations import split_pdf
        from pypdf import PdfReader
        src = _write_tmp_pdf(5, dir=str(tmp_path))
        out = tmp_path / "split.pdf"
        extracted = split_pdf(src, (3, 3), out)
        assert extracted == 1
        reader = PdfReader(str(out))
        assert len(reader.pages) == 1


# ---------------------------------------------------------------------------
# Tests: operations.convert_images_to_pdf
# ---------------------------------------------------------------------------

class TestConvertImages:
    def test_convert_single_png(self, tmp_path):
        from pdfuse.operations import convert_images_to_pdf
        from pypdf import PdfReader
        img = _write_tmp_png(dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        convert_images_to_pdf([img], out)
        assert out.exists()
        reader = PdfReader(str(out))
        assert len(reader.pages) == 1

    def test_convert_multiple_images(self, tmp_path):
        from pdfuse.operations import convert_images_to_pdf
        from pypdf import PdfReader
        imgs = [_write_tmp_png(dir=str(tmp_path)) for _ in range(3)]
        out = tmp_path / "out.pdf"
        convert_images_to_pdf(imgs, out)
        reader = PdfReader(str(out))
        assert len(reader.pages) == 3

    def test_convert_rgba_image(self, tmp_path):
        """RGBA images must be converted to RGB before saving as PDF."""
        from pdfuse.operations import convert_images_to_pdf
        from pypdf import PdfReader
        img = _write_tmp_rgba_png(dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        # Should NOT raise; RGBA → RGB conversion happens inside the function.
        convert_images_to_pdf([img], out)
        assert out.exists()
        reader = PdfReader(str(out))
        assert len(reader.pages) == 1


# ---------------------------------------------------------------------------
# Tests: operations.pdf_info
# ---------------------------------------------------------------------------

class TestPdfInfo:
    def test_info_page_count(self, tmp_path):
        from pdfuse.operations import pdf_info
        src = _write_tmp_pdf(7, dir=str(tmp_path))
        info = pdf_info(src)
        assert info["Pages"] == 7

    def test_info_has_required_keys(self, tmp_path):
        from pdfuse.operations import pdf_info
        src = _write_tmp_pdf(1, dir=str(tmp_path))
        info = pdf_info(src)
        for key in ("File", "Pages", "Size", "Title", "Author"):
            assert key in info
