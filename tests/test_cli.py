"""CLI integration tests for pdfuse top-level commands."""

from __future__ import annotations

import pytest
from click.testing import CliRunner
from pypdf import PdfReader

from conftest import make_pdf_bytes, write_png, write_rgba_png
from pdfuse.cli import main


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------

class TestCliMerge:
    def test_success(self, runner, tmp_path):
        a = tmp_path / "a.pdf"
        b = tmp_path / "b.pdf"
        out = tmp_path / "out.pdf"
        a.write_bytes(make_pdf_bytes(2))
        b.write_bytes(make_pdf_bytes(3))
        result = runner.invoke(main, ["merge", str(a), str(b), "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 5

    def test_missing_file(self, runner, tmp_path):
        result = runner.invoke(main, ["merge", str(tmp_path / "nope.pdf"), "-o", str(tmp_path / "out.pdf")])
        assert result.exit_code == 1

    def test_no_inputs(self, runner, tmp_path):
        result = runner.invoke(main, ["merge"])
        assert result.exit_code != 0

    def test_default_output_name(self, runner, tmp_path):
        a = tmp_path / "a.pdf"
        a.write_bytes(make_pdf_bytes(1))
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["merge", str(a)], catch_exceptions=False)
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# split
# ---------------------------------------------------------------------------

class TestCliSplit:
    def test_success(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        out = tmp_path / "out.pdf"
        src.write_bytes(make_pdf_bytes(5))
        result = runner.invoke(main, ["split", str(src), "--pages", "2-4", "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 3

    def test_single_page(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        out = tmp_path / "out.pdf"
        src.write_bytes(make_pdf_bytes(5))
        result = runner.invoke(main, ["split", str(src), "--pages", "3-3", "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 1

    def test_range_exceeds_total(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(make_pdf_bytes(3))
        out = tmp_path / "out.pdf"
        result = runner.invoke(main, ["split", str(src), "--pages", "1-10", "-o", str(out)])
        assert result.exit_code == 1
        assert not out.exists()

    def test_missing_pages_option(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(make_pdf_bytes(3))
        result = runner.invoke(main, ["split", str(src)])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------

class TestCliConvert:
    def test_single_image(self, runner, tmp_path):
        from PIL import Image
        img = tmp_path / "img.png"
        Image.new("RGB", (64, 64), (100, 150, 200)).save(str(img))
        out = tmp_path / "out.pdf"
        result = runner.invoke(main, ["convert", str(img), "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 1

    def test_multiple_images(self, runner, tmp_path):
        from PIL import Image
        imgs = []
        for i in range(3):
            p = tmp_path / f"img{i}.png"
            Image.new("RGB", (64, 64), (i * 50, 100, 200)).save(str(p))
            imgs.append(str(p))
        out = tmp_path / "out.pdf"
        result = runner.invoke(main, ["convert"] + imgs + ["-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 3

    def test_rgba_image(self, runner, tmp_path):
        img = write_rgba_png(dir=str(tmp_path))
        out = tmp_path / "out.pdf"
        result = runner.invoke(main, ["convert", str(img), "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0

    def test_unsupported_format(self, runner, tmp_path):
        p = tmp_path / "file.xyz"
        p.write_text("not a real file")
        result = runner.invoke(main, ["convert", str(p)])
        assert result.exit_code == 1

    def test_missing_file(self, runner, tmp_path):
        result = runner.invoke(main, ["convert", str(tmp_path / "nope.png")])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------

class TestCliInfo:
    def test_success(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(make_pdf_bytes(3))
        result = runner.invoke(main, ["info", str(src)], catch_exceptions=False)
        assert result.exit_code == 0

    def test_missing_file(self, runner, tmp_path):
        result = runner.invoke(main, ["info", str(tmp_path / "nope.pdf")])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# compress
# ---------------------------------------------------------------------------

class TestCliCompress:
    def test_success(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        out = tmp_path / "out.pdf"
        src.write_bytes(make_pdf_bytes(2))
        result = runner.invoke(main, ["compress", str(src), "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert out.exists()
        assert len(PdfReader(str(out)).pages) == 2

    def test_missing_file(self, runner, tmp_path):
        result = runner.invoke(main, ["compress", str(tmp_path / "nope.pdf")])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# rotate
# ---------------------------------------------------------------------------

class TestCliRotate:
    def test_rotate_90(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        out = tmp_path / "out.pdf"
        src.write_bytes(make_pdf_bytes(3))
        result = runner.invoke(main, ["rotate", str(src), "--angle", "90", "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 3

    def test_rotate_specific_pages(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        out = tmp_path / "out.pdf"
        src.write_bytes(make_pdf_bytes(4))
        result = runner.invoke(main, ["rotate", str(src), "--angle", "180", "--pages", "1,3", "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 4

    def test_missing_angle(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["rotate", str(src), "-o", str(tmp_path / "out.pdf")])
        assert result.exit_code != 0

    def test_invalid_angle(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["rotate", str(src), "--angle", "45"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# watermark
# ---------------------------------------------------------------------------

class TestCliWatermark:
    def test_text_watermark(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        out = tmp_path / "out.pdf"
        src.write_bytes(make_pdf_bytes(2))
        result = runner.invoke(main, ["watermark", str(src), "--text", "DRAFT", "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 2

    def test_stamp_watermark(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        stamp = tmp_path / "stamp.pdf"
        out = tmp_path / "out.pdf"
        src.write_bytes(make_pdf_bytes(2))
        stamp.write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["watermark", str(src), "--stamp", str(stamp), "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 2

    def test_no_flag_raises(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["watermark", str(src), "-o", str(tmp_path / "out.pdf")])
        assert result.exit_code == 1

    def test_both_flags_raises(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        stamp = tmp_path / "stamp.pdf"
        src.write_bytes(make_pdf_bytes(1))
        stamp.write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["watermark", str(src), "--text", "X", "--stamp", str(stamp)])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# reorder
# ---------------------------------------------------------------------------

class TestCliReorder:
    def test_success(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        out = tmp_path / "out.pdf"
        src.write_bytes(make_pdf_bytes(3))
        result = runner.invoke(main, ["reorder", str(src), "--order", "3,1,2", "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 3

    def test_repeat_pages(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        out = tmp_path / "out.pdf"
        src.write_bytes(make_pdf_bytes(3))
        result = runner.invoke(main, ["reorder", str(src), "--order", "1,1,2,3", "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 4

    def test_out_of_range_page(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        out = tmp_path / "out.pdf"
        src.write_bytes(make_pdf_bytes(2))
        result = runner.invoke(main, ["reorder", str(src), "--order", "1,5", "-o", str(out)])
        assert result.exit_code == 1
        assert not out.exists()

    def test_missing_order(self, runner, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(make_pdf_bytes(2))
        result = runner.invoke(main, ["reorder", str(src)])
        assert result.exit_code != 0
