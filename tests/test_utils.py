"""Tests for pdfuse.utils."""

from __future__ import annotations

import pytest

from conftest import make_pdf_bytes, write_pdf


# ---------------------------------------------------------------------------
# parse_page_range
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

    def test_negative_raises(self):
        from pdfuse.utils import parse_page_range
        with pytest.raises(SystemExit):
            parse_page_range("-1-3", 5)


# ---------------------------------------------------------------------------
# validate_input_files
# ---------------------------------------------------------------------------

class TestValidateInputFiles:
    def test_valid_file(self, tmp_path):
        from pdfuse.utils import validate_input_files
        p = tmp_path / "a.pdf"
        p.write_bytes(make_pdf_bytes(1))
        result = validate_input_files([str(p)])
        assert result == [p]

    def test_valid_with_extension_check(self, tmp_path):
        from pdfuse.utils import validate_input_files
        p = tmp_path / "a.pdf"
        p.write_bytes(make_pdf_bytes(1))
        result = validate_input_files([str(p)], allowed_exts={".pdf"})
        assert result == [p]

    def test_missing_file_raises(self, tmp_path):
        from pdfuse.utils import validate_input_files
        with pytest.raises(SystemExit):
            validate_input_files([str(tmp_path / "missing.pdf")])

    def test_wrong_extension_raises(self, tmp_path):
        from pdfuse.utils import validate_input_files
        p = tmp_path / "a.txt"
        p.write_text("hello")
        with pytest.raises(SystemExit):
            validate_input_files([str(p)], allowed_exts={".pdf"})

    def test_directory_raises(self, tmp_path):
        from pdfuse.utils import validate_input_files
        with pytest.raises(SystemExit):
            validate_input_files([str(tmp_path)])

    def test_multiple_valid_files(self, tmp_path):
        from pdfuse.utils import validate_input_files
        paths = [tmp_path / f"{i}.pdf" for i in range(3)]
        for p in paths:
            p.write_bytes(make_pdf_bytes(1))
        result = validate_input_files([str(p) for p in paths], allowed_exts={".pdf"})
        assert result == paths


# ---------------------------------------------------------------------------
# validate_output_path
# ---------------------------------------------------------------------------

class TestValidateOutputPath:
    def test_valid_path(self, tmp_path):
        from pdfuse.utils import validate_output_path
        out = validate_output_path(str(tmp_path / "out.pdf"))
        assert out == tmp_path / "out.pdf"

    def test_nonexistent_parent_raises(self, tmp_path):
        from pdfuse.utils import validate_output_path
        with pytest.raises(SystemExit):
            validate_output_path(str(tmp_path / "missing_dir" / "out.pdf"))


# ---------------------------------------------------------------------------
# default_output
# ---------------------------------------------------------------------------

class TestDefaultOutput:
    def test_replaces_suffix(self, tmp_path):
        from pdfuse.utils import default_output
        p = tmp_path / "file.docx"
        assert default_output(p) == tmp_path / "file.pdf"

    def test_already_pdf(self, tmp_path):
        from pdfuse.utils import default_output
        p = tmp_path / "file.pdf"
        assert default_output(p) == tmp_path / "file.pdf"

    def test_custom_suffix(self, tmp_path):
        from pdfuse.utils import default_output
        p = tmp_path / "file.png"
        assert default_output(p, suffix=".txt") == tmp_path / "file.txt"
