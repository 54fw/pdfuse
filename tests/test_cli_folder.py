"""CLI integration tests for pdfuse --folder flag on each command."""

from __future__ import annotations

import os

import pytest
from click.testing import CliRunner
from pypdf import PdfReader

from conftest import make_pdf_bytes
from pdfuse.cli import main


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# compress --folder
# ---------------------------------------------------------------------------

class TestCompressFolder:
    def test_success(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "out"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(2))
        (src / "b.pdf").write_bytes(make_pdf_bytes(3))
        result = runner.invoke(main, ["compress", "--folder", str(src), "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert (out / "a.pdf").exists()
        assert (out / "b.pdf").exists()

    def test_creates_output_dir(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "new_out"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["compress", "--folder", str(src), "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert out.is_dir()

    def test_recursive(self, runner, tmp_path):
        src = tmp_path / "in"
        sub = src / "sub"
        out = tmp_path / "out"
        src.mkdir()
        sub.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(1))
        (sub / "b.pdf").write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["compress", "--folder", str(src), "-o", str(out), "--recursive"], catch_exceptions=False)
        assert result.exit_code == 0
        assert (out / "a.pdf").exists()
        assert (out / "sub" / "b.pdf").exists()

    def test_parallel_workers(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "out"
        src.mkdir()
        for i in range(4):
            (src / f"{i}.pdf").write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["compress", "--folder", str(src), "-o", str(out), "--workers", "2"], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(list(out.glob("*.pdf"))) == 4

    def test_empty_dir(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "out"
        src.mkdir()
        result = runner.invoke(main, ["compress", "--folder", str(src), "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0

    def test_missing_dir(self, runner, tmp_path):
        result = runner.invoke(main, ["compress", "--folder", str(tmp_path / "nope"), "-o", str(tmp_path / "out")])
        assert result.exit_code == 1

    def test_pattern_filter(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "out"
        src.mkdir()
        (src / "keep.pdf").write_bytes(make_pdf_bytes(1))
        (src / "skip.txt").write_text("not a pdf")
        result = runner.invoke(main, ["compress", "--folder", str(src), "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert (out / "keep.pdf").exists()
        assert not (out / "skip.txt").exists()

    def test_both_file_and_folder_raises(self, runner, tmp_path):
        src = tmp_path / "in"
        src.mkdir()
        f = tmp_path / "f.pdf"
        f.write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["compress", str(f), "--folder", str(src), "-o", str(tmp_path / "out")])
        assert result.exit_code == 1

    def test_neither_file_nor_folder_raises(self, runner, tmp_path):
        result = runner.invoke(main, ["compress"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# rotate --folder
# ---------------------------------------------------------------------------

class TestRotateFolder:
    def test_success(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "out"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(3))
        result = runner.invoke(main, ["rotate", "--folder", str(src), "-o", str(out), "--angle", "90"], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out / "a.pdf")).pages) == 3

    def test_all_angles(self, runner, tmp_path):
        for angle in ["90", "180", "270"]:
            src = tmp_path / f"in_{angle}"
            out = tmp_path / f"out_{angle}"
            src.mkdir()
            (src / "a.pdf").write_bytes(make_pdf_bytes(1))
            result = runner.invoke(main, ["rotate", "--folder", str(src), "-o", str(out), "--angle", angle], catch_exceptions=False)
            assert result.exit_code == 0

    def test_missing_angle(self, runner, tmp_path):
        src = tmp_path / "in"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["rotate", "--folder", str(src), "-o", str(tmp_path / "out")])
        assert result.exit_code != 0

    def test_specific_pages(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "out"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(4))
        result = runner.invoke(main, ["rotate", "--folder", str(src), "-o", str(out), "--angle", "90", "--pages", "1,3"], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out / "a.pdf")).pages) == 4

    def test_both_file_and_folder_raises(self, runner, tmp_path):
        src = tmp_path / "in"
        src.mkdir()
        f = tmp_path / "f.pdf"
        f.write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["rotate", str(f), "--folder", str(src), "--angle", "90", "-o", str(tmp_path / "out")])
        assert result.exit_code == 1

    def test_neither_file_nor_folder_raises(self, runner, tmp_path):
        result = runner.invoke(main, ["rotate", "--angle", "90"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# watermark --folder
# ---------------------------------------------------------------------------

class TestWatermarkFolder:
    def test_text_watermark(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "out"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(2))
        result = runner.invoke(main, ["watermark", "--folder", str(src), "-o", str(out), "--text", "DRAFT"], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out / "a.pdf")).pages) == 2

    def test_stamp_watermark(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "out"
        stamp = tmp_path / "stamp.pdf"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(2))
        stamp.write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["watermark", "--folder", str(src), "-o", str(out), "--stamp", str(stamp)], catch_exceptions=False)
        assert result.exit_code == 0

    def test_no_flag_raises(self, runner, tmp_path):
        src = tmp_path / "in"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["watermark", "--folder", str(src), "-o", str(tmp_path / "out")])
        assert result.exit_code == 1

    def test_both_flags_raises(self, runner, tmp_path):
        src = tmp_path / "in"
        stamp = tmp_path / "stamp.pdf"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(1))
        stamp.write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["watermark", "--folder", str(src), "-o", str(tmp_path / "out"), "--text", "X", "--stamp", str(stamp)])
        assert result.exit_code == 1

    def test_multiple_files(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "out"
        src.mkdir()
        for i in range(3):
            (src / f"{i}.pdf").write_bytes(make_pdf_bytes(2))
        result = runner.invoke(main, ["watermark", "--folder", str(src), "-o", str(out), "--text", "CONFIDENTIAL"], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(list(out.glob("*.pdf"))) == 3

    def test_both_file_and_folder_raises(self, runner, tmp_path):
        src = tmp_path / "in"
        src.mkdir()
        f = tmp_path / "f.pdf"
        f.write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["watermark", str(f), "--folder", str(src), "--text", "X", "-o", str(tmp_path / "out")])
        assert result.exit_code == 1

    def test_neither_file_nor_folder_raises(self, runner, tmp_path):
        result = runner.invoke(main, ["watermark", "--text", "X"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# reorder --folder
# ---------------------------------------------------------------------------

class TestReorderFolder:
    def test_success(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "out"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(3))
        result = runner.invoke(main, ["reorder", "--folder", str(src), "-o", str(out), "--order", "3,1,2"], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out / "a.pdf")).pages) == 3

    def test_repeat_pages(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "out"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(3))
        result = runner.invoke(main, ["reorder", "--folder", str(src), "-o", str(out), "--order", "1,1,2"], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out / "a.pdf")).pages) == 3

    def test_missing_order(self, runner, tmp_path):
        src = tmp_path / "in"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(2))
        result = runner.invoke(main, ["reorder", "--folder", str(src), "-o", str(tmp_path / "out")])
        assert result.exit_code != 0

    def test_failed_file_warns_but_continues(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "out"
        src.mkdir()
        (src / "good.pdf").write_bytes(make_pdf_bytes(3))
        (src / "bad.pdf").write_bytes(make_pdf_bytes(2))
        result = runner.invoke(main, ["reorder", "--folder", str(src), "-o", str(out), "--order", "1,2,3"])
        assert result.exit_code == 1
        assert (out / "good.pdf").exists()

    def test_both_file_and_folder_raises(self, runner, tmp_path):
        src = tmp_path / "in"
        src.mkdir()
        f = tmp_path / "f.pdf"
        f.write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["reorder", str(f), "--folder", str(src), "--order", "1", "-o", str(tmp_path / "out")])
        assert result.exit_code == 1

    def test_neither_file_nor_folder_raises(self, runner, tmp_path):
        result = runner.invoke(main, ["reorder", "--order", "1"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# merge --folder
# ---------------------------------------------------------------------------

class TestMergeFolder:
    def test_name_sort(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "merged.pdf"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(1))
        (src / "b.pdf").write_bytes(make_pdf_bytes(2))
        (src / "c.pdf").write_bytes(make_pdf_bytes(3))
        result = runner.invoke(main, ["merge", "--folder", str(src), "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 6

    def test_sort_date(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "merged.pdf"
        src.mkdir()
        a = src / "a.pdf"
        b = src / "b.pdf"
        a.write_bytes(make_pdf_bytes(2))
        b.write_bytes(make_pdf_bytes(3))
        os.utime(a, (1_000_000, 1_000_000))
        os.utime(b, (2_000_000, 2_000_000))
        result = runner.invoke(main, ["merge", "--folder", str(src), "-o", str(out), "--sort", "date"], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 5

    def test_reverse(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "merged.pdf"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(1))
        (src / "b.pdf").write_bytes(make_pdf_bytes(2))
        result = runner.invoke(main, ["merge", "--folder", str(src), "-o", str(out), "--reverse"], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 3

    def test_recursive(self, runner, tmp_path):
        src = tmp_path / "in"
        sub = src / "sub"
        out = tmp_path / "merged.pdf"
        src.mkdir()
        sub.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(1))
        (sub / "b.pdf").write_bytes(make_pdf_bytes(2))
        result = runner.invoke(main, ["merge", "--folder", str(src), "-o", str(out), "--recursive"], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 3

    def test_empty_dir(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "merged.pdf"
        src.mkdir()
        result = runner.invoke(main, ["merge", "--folder", str(src), "-o", str(out)], catch_exceptions=False)
        assert result.exit_code == 0
        assert not out.exists()

    def test_missing_dir(self, runner, tmp_path):
        result = runner.invoke(main, ["merge", "--folder", str(tmp_path / "nope"), "-o", str(tmp_path / "out.pdf")])
        assert result.exit_code == 1

    def test_pattern_filter(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "merged.pdf"
        src.mkdir()
        (src / "keep.pdf").write_bytes(make_pdf_bytes(2))
        (src / "other.pdf").write_bytes(make_pdf_bytes(3))
        result = runner.invoke(main, ["merge", "--folder", str(src), "-o", str(out), "--pattern", "keep*.pdf"], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 2

    def test_sort_date_reverse(self, runner, tmp_path):
        src = tmp_path / "in"
        out = tmp_path / "merged.pdf"
        src.mkdir()
        a = src / "a.pdf"
        b = src / "b.pdf"
        a.write_bytes(make_pdf_bytes(1))
        b.write_bytes(make_pdf_bytes(2))
        os.utime(a, (1_000_000, 1_000_000))
        os.utime(b, (2_000_000, 2_000_000))
        result = runner.invoke(main, ["merge", "--folder", str(src), "-o", str(out), "--sort", "date", "--reverse"], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(out)).pages) == 3

    def test_both_file_and_folder_raises(self, runner, tmp_path):
        src = tmp_path / "in"
        src.mkdir()
        f = tmp_path / "f.pdf"
        f.write_bytes(make_pdf_bytes(1))
        result = runner.invoke(main, ["merge", str(f), "--folder", str(src), "-o", str(tmp_path / "out.pdf")])
        assert result.exit_code == 1
