"""Tests for pdfuse.operations."""

from __future__ import annotations

import pytest
from pypdf import PdfReader

from conftest import make_pdf_bytes, write_pdf, write_png, write_rgba_png


# ---------------------------------------------------------------------------
# merge_pdfs
# ---------------------------------------------------------------------------

class TestMergePdfs:
    def test_merge_two_pdfs(self, tmp_path):
        from pdfuse.operations import merge_pdfs
        a = write_pdf(3, dir=str(tmp_path))
        b = write_pdf(2, dir=str(tmp_path))
        out = tmp_path / "merged.pdf"
        total = merge_pdfs([a, b], out)
        assert total == 5
        assert out.exists()

    def test_merge_single_pdf(self, tmp_path):
        from pdfuse.operations import merge_pdfs
        a = write_pdf(4, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        total = merge_pdfs([a], out)
        assert total == 4

    def test_page_count_matches_reader(self, tmp_path):
        from pdfuse.operations import merge_pdfs
        a = write_pdf(2, dir=str(tmp_path))
        b = write_pdf(3, dir=str(tmp_path))
        out = tmp_path / "merged.pdf"
        merge_pdfs([a, b], out)
        assert len(PdfReader(str(out)).pages) == 5

    def test_order_preserved(self, tmp_path):
        from pdfuse.operations import merge_pdfs
        a = write_pdf(2, dir=str(tmp_path))
        b = write_pdf(3, dir=str(tmp_path))
        out = tmp_path / "merged.pdf"
        total = merge_pdfs([a, b], out)
        assert total == 5


# ---------------------------------------------------------------------------
# split_pdf
# ---------------------------------------------------------------------------

class TestSplitPdf:
    def test_split_range(self, tmp_path):
        from pdfuse.operations import split_pdf
        src = write_pdf(5, dir=str(tmp_path))
        out = tmp_path / "split.pdf"
        extracted = split_pdf(src, (2, 4), out)
        assert extracted == 3
        assert len(PdfReader(str(out)).pages) == 3

    def test_split_single_page(self, tmp_path):
        from pdfuse.operations import split_pdf
        src = write_pdf(5, dir=str(tmp_path))
        out = tmp_path / "split.pdf"
        extracted = split_pdf(src, (3, 3), out)
        assert extracted == 1
        assert len(PdfReader(str(out)).pages) == 1

    def test_split_full_range(self, tmp_path):
        from pdfuse.operations import split_pdf
        src = write_pdf(4, dir=str(tmp_path))
        out = tmp_path / "split.pdf"
        extracted = split_pdf(src, (1, 4), out)
        assert extracted == 4


# ---------------------------------------------------------------------------
# convert_images_to_pdf
# ---------------------------------------------------------------------------

class TestConvertImages:
    def test_convert_single_png(self, tmp_path):
        from pdfuse.operations import convert_images_to_pdf
        img = write_png(dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        convert_images_to_pdf([img], out)
        assert out.exists()
        assert len(PdfReader(str(out)).pages) == 1

    def test_convert_multiple_images(self, tmp_path):
        from pdfuse.operations import convert_images_to_pdf
        imgs = [write_png(dir=str(tmp_path)) for _ in range(3)]
        out = tmp_path / "out.pdf"
        convert_images_to_pdf(imgs, out)
        assert len(PdfReader(str(out)).pages) == 3

    def test_convert_rgba_image(self, tmp_path):
        from pdfuse.operations import convert_images_to_pdf
        img = write_rgba_png(dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        convert_images_to_pdf([img], out)
        assert out.exists()
        assert len(PdfReader(str(out)).pages) == 1


# ---------------------------------------------------------------------------
# pdf_info
# ---------------------------------------------------------------------------

class TestPdfInfo:
    def test_page_count(self, tmp_path):
        from pdfuse.operations import pdf_info
        src = write_pdf(7, dir=str(tmp_path))
        info = pdf_info(src)
        assert info["Pages"] == 7

    def test_required_keys(self, tmp_path):
        from pdfuse.operations import pdf_info
        src = write_pdf(1, dir=str(tmp_path))
        info = pdf_info(src)
        for key in ("File", "Pages", "Size", "Title", "Author", "Creator", "Producer"):
            assert key in info

    def test_file_name(self, tmp_path):
        from pdfuse.operations import pdf_info
        src = write_pdf(1, dir=str(tmp_path))
        info = pdf_info(src)
        assert info["File"] == src.name


# ---------------------------------------------------------------------------
# compress_pdf
# ---------------------------------------------------------------------------

class TestCompressPdf:
    def test_returns_size_tuple(self, tmp_path):
        from pdfuse.operations import compress_pdf
        src = write_pdf(2, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        original_kb, compressed_kb = compress_pdf(src, out)
        assert isinstance(original_kb, int)
        assert isinstance(compressed_kb, int)

    def test_output_exists(self, tmp_path):
        from pdfuse.operations import compress_pdf
        src = write_pdf(2, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        compress_pdf(src, out)
        assert out.exists()

    def test_page_count_preserved(self, tmp_path):
        from pdfuse.operations import compress_pdf
        src = write_pdf(3, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        compress_pdf(src, out)
        assert len(PdfReader(str(out)).pages) == 3


# ---------------------------------------------------------------------------
# rotate_pdf
# ---------------------------------------------------------------------------

class TestRotatePdf:
    def test_rotate_all_pages(self, tmp_path):
        from pdfuse.operations import rotate_pdf
        src = write_pdf(3, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        rotated = rotate_pdf(src, out, 90)
        assert rotated == 3
        assert len(PdfReader(str(out)).pages) == 3

    def test_rotate_specific_pages(self, tmp_path):
        from pdfuse.operations import rotate_pdf
        src = write_pdf(4, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        rotated = rotate_pdf(src, out, 180, pages=[1, 3])
        assert rotated == 2
        assert len(PdfReader(str(out)).pages) == 4

    def test_rotate_270(self, tmp_path):
        from pdfuse.operations import rotate_pdf
        src = write_pdf(2, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        rotated = rotate_pdf(src, out, 270)
        assert rotated == 2

    def test_invalid_angle_raises(self, tmp_path):
        from pdfuse.operations import rotate_pdf
        src = write_pdf(1, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        with pytest.raises(ValueError):
            rotate_pdf(src, out, 45)


# ---------------------------------------------------------------------------
# watermark_pdf
# ---------------------------------------------------------------------------

class TestWatermarkPdf:
    def test_text_watermark(self, tmp_path):
        from pdfuse.operations import watermark_pdf
        src = write_pdf(2, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        pages = watermark_pdf(src, out, watermark_text="DRAFT")
        assert pages == 2
        assert out.exists()
        assert len(PdfReader(str(out)).pages) == 2

    def test_pdf_stamp_watermark(self, tmp_path):
        from pdfuse.operations import watermark_pdf
        src = write_pdf(2, dir=str(tmp_path))
        stamp = write_pdf(1, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        pages = watermark_pdf(src, out, watermark_pdf=stamp)
        assert pages == 2
        assert out.exists()

    def test_no_watermark_arg_raises(self, tmp_path):
        from pdfuse.operations import watermark_pdf
        src = write_pdf(1, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        with pytest.raises(SystemExit):
            watermark_pdf(src, out)

    def test_zero_page_pdf_raises(self, tmp_path):
        from pdfuse.operations import watermark_pdf
        from pypdf import PdfWriter

        writer = PdfWriter()
        empty = tmp_path / "empty.pdf"
        with open(empty, "wb") as f:
            writer.write(f)
        out = tmp_path / "out.pdf"
        with pytest.raises(SystemExit):
            watermark_pdf(empty, out, watermark_text="X")


# ---------------------------------------------------------------------------
# reorder_pdf
# ---------------------------------------------------------------------------

class TestReorderPdf:
    def test_reorder_pages(self, tmp_path):
        from pdfuse.operations import reorder_pdf
        src = write_pdf(3, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        written = reorder_pdf(src, out, [3, 1, 2])
        assert written == 3
        assert len(PdfReader(str(out)).pages) == 3

    def test_repeat_pages(self, tmp_path):
        from pdfuse.operations import reorder_pdf
        src = write_pdf(3, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        written = reorder_pdf(src, out, [1, 1, 2])
        assert written == 3
        assert len(PdfReader(str(out)).pages) == 3

    def test_subset_of_pages(self, tmp_path):
        from pdfuse.operations import reorder_pdf
        src = write_pdf(5, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        written = reorder_pdf(src, out, [2, 4])
        assert written == 2
        assert len(PdfReader(str(out)).pages) == 2

    def test_out_of_range_raises(self, tmp_path):
        from pdfuse.operations import reorder_pdf
        src = write_pdf(3, dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        with pytest.raises(SystemExit):
            reorder_pdf(src, out, [1, 10])
