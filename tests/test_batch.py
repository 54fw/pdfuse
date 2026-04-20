"""Tests for pdfuse.batch (load_workflow, run_workflow) and the batch CLI command."""

from __future__ import annotations

import textwrap

import pytest
import yaml
from click.testing import CliRunner
from pypdf import PdfReader

from conftest import make_pdf_bytes
from pdfuse.batch import (
    StepConfig,
    WorkflowConfig,
    _parse_step,
    _step_label,
    _validate_step_params,
    load_workflow,
    run_workflow,
)
from pdfuse.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_workflow(tmp_path, content: str):
    """Write YAML content to tmp_path/workflow.yaml and return its Path."""
    p = tmp_path / "workflow.yaml"
    p.write_text(textwrap.dedent(content))
    return p


# ---------------------------------------------------------------------------
# _parse_step
# ---------------------------------------------------------------------------

class TestParseStep:
    def test_bare_string(self):
        s = _parse_step("compress")
        assert s.name == "compress"
        assert s.params == {}

    def test_mapping_with_params(self):
        s = _parse_step({"watermark": {"text": "DRAFT"}})
        assert s.name == "watermark"
        assert s.params == {"text": "DRAFT"}

    def test_mapping_with_null_params(self):
        s = _parse_step({"compress": None})
        assert s.name == "compress"
        assert s.params == {}

    def test_unknown_step_raises(self):
        with pytest.raises(ValueError, match="Unknown step"):
            _parse_step("merge")

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            _parse_step(42)

    def test_dict_multiple_keys_raises(self):
        with pytest.raises(ValueError, match="exactly one key"):
            _parse_step({"compress": {}, "rotate": {}})

    def test_non_dict_params_raises(self):
        with pytest.raises(ValueError, match="mapping"):
            _parse_step({"watermark": "some string"})


# ---------------------------------------------------------------------------
# _validate_step_params
# ---------------------------------------------------------------------------

class TestValidateStepParams:
    def test_compress_no_params_ok(self):
        _validate_step_params(StepConfig("compress"))  # no exception

    def test_watermark_text_ok(self):
        _validate_step_params(StepConfig("watermark", {"text": "X"}))

    def test_watermark_stamp_ok(self):
        _validate_step_params(StepConfig("watermark", {"stamp": "s.pdf"}))

    def test_watermark_no_params_raises(self):
        with pytest.raises(ValueError, match="requires"):
            _validate_step_params(StepConfig("watermark", {}))

    def test_watermark_both_raises(self):
        with pytest.raises(ValueError, match="only one"):
            _validate_step_params(StepConfig("watermark", {"text": "X", "stamp": "s.pdf"}))

    def test_split_requires_pages(self):
        with pytest.raises(ValueError, match="pages"):
            _validate_step_params(StepConfig("split", {}))

    def test_rotate_requires_angle(self):
        with pytest.raises(ValueError, match="angle"):
            _validate_step_params(StepConfig("rotate", {}))

    def test_rotate_bad_angle_raises(self):
        with pytest.raises(ValueError, match="90, 180, or 270"):
            _validate_step_params(StepConfig("rotate", {"angle": 45}))

    def test_reorder_requires_order(self):
        with pytest.raises(ValueError, match="order"):
            _validate_step_params(StepConfig("reorder", {}))


# ---------------------------------------------------------------------------
# _step_label
# ---------------------------------------------------------------------------

class TestStepLabel:
    def test_compress(self):
        assert _step_label(StepConfig("compress")) == "compress"

    def test_watermark_text(self):
        assert _step_label(StepConfig("watermark", {"text": "DRAFT"})) == 'watermark: "DRAFT"'

    def test_watermark_stamp(self):
        assert _step_label(StepConfig("watermark", {"stamp": "logo.pdf"})) == "watermark: logo.pdf"

    def test_split(self):
        assert _step_label(StepConfig("split", {"pages": "1-5"})) == "split: pages 1-5"

    def test_rotate_no_pages(self):
        assert _step_label(StepConfig("rotate", {"angle": 90})) == "rotate: 90°"

    def test_rotate_with_pages(self):
        assert _step_label(StepConfig("rotate", {"angle": 180, "pages": "1,3"})) == "rotate: 180° on pages 1,3"

    def test_reorder(self):
        assert _step_label(StepConfig("reorder", {"order": "3,1,2"})) == "reorder: [3,1,2]"


# ---------------------------------------------------------------------------
# load_workflow — single-file mode
# ---------------------------------------------------------------------------

class TestLoadWorkflowSingleFile:
    def test_minimal_compress(self, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(2))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - compress
            output: out.pdf
        """)
        cfg = load_workflow(p)
        assert cfg.input == tmp_path / "src.pdf"
        assert cfg.output == tmp_path / "out.pdf"
        assert len(cfg.steps) == 1
        assert cfg.steps[0].name == "compress"

    def test_multiple_steps(self, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(3))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - compress
              - watermark:
                  text: "CONFIDENTIAL"
              - rotate:
                  angle: 90
            output: out.pdf
        """)
        cfg = load_workflow(p)
        assert len(cfg.steps) == 3
        assert cfg.steps[1].params["text"] == "CONFIDENTIAL"
        assert cfg.steps[2].params["angle"] == 90

    def test_missing_input_file_raises(self, tmp_path):
        p = _write_workflow(tmp_path, """
            input: nonexistent.pdf
            steps:
              - compress
            output: out.pdf
        """)
        with pytest.raises(SystemExit):
            load_workflow(p)

    def test_missing_output_raises(self, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(1))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - compress
        """)
        with pytest.raises(SystemExit):
            load_workflow(p)

    def test_both_input_and_folder_raises(self, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(1))
        (tmp_path / "folder").mkdir()
        p = _write_workflow(tmp_path, """
            input: src.pdf
            input_folder: folder
            steps:
              - compress
            output: out.pdf
        """)
        with pytest.raises(SystemExit):
            load_workflow(p)

    def test_neither_input_nor_folder_raises(self, tmp_path):
        p = _write_workflow(tmp_path, """
            steps:
              - compress
            output: out.pdf
        """)
        with pytest.raises(SystemExit):
            load_workflow(p)

    def test_unknown_step_raises(self, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(1))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - merge
            output: out.pdf
        """)
        with pytest.raises(SystemExit):
            load_workflow(p)

    def test_missing_step_params_raises(self, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(1))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - watermark: {}
            output: out.pdf
        """)
        with pytest.raises(SystemExit):
            load_workflow(p)

    def test_empty_steps_raises(self, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(1))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps: []
            output: out.pdf
        """)
        with pytest.raises(SystemExit):
            load_workflow(p)

    def test_invalid_yaml_raises(self, tmp_path):
        p = tmp_path / "workflow.yaml"
        p.write_text("key: [unclosed")
        with pytest.raises(SystemExit):
            load_workflow(p)

    def test_non_mapping_yaml_raises(self, tmp_path):
        p = tmp_path / "workflow.yaml"
        p.write_text("- just a list")
        with pytest.raises(SystemExit):
            load_workflow(p)


# ---------------------------------------------------------------------------
# load_workflow — folder mode
# ---------------------------------------------------------------------------

class TestLoadWorkflowFolder:
    def test_valid_folder_workflow(self, tmp_path):
        (tmp_path / "docs").mkdir()
        p = _write_workflow(tmp_path, """
            input_folder: docs
            steps:
              - compress
            output_folder: out
        """)
        cfg = load_workflow(p)
        assert cfg.input_folder == tmp_path / "docs"
        assert cfg.output_folder == tmp_path / "out"
        assert cfg.pattern == "*.pdf"

    def test_custom_pattern(self, tmp_path):
        (tmp_path / "docs").mkdir()
        p = _write_workflow(tmp_path, """
            input_folder: docs
            pattern: "report*.pdf"
            steps:
              - compress
            output_folder: out
        """)
        cfg = load_workflow(p)
        assert cfg.pattern == "report*.pdf"

    def test_missing_input_folder_raises(self, tmp_path):
        p = _write_workflow(tmp_path, """
            input_folder: does_not_exist
            steps:
              - compress
            output_folder: out
        """)
        with pytest.raises(SystemExit):
            load_workflow(p)

    def test_missing_output_folder_raises(self, tmp_path):
        (tmp_path / "docs").mkdir()
        p = _write_workflow(tmp_path, """
            input_folder: docs
            steps:
              - compress
        """)
        with pytest.raises(SystemExit):
            load_workflow(p)


# ---------------------------------------------------------------------------
# run_workflow — single-file mode
# ---------------------------------------------------------------------------

class TestRunWorkflowSingleFile:
    def _make_cfg(self, tmp_path, steps_yaml: str, pages: int = 3) -> WorkflowConfig:
        src = tmp_path / "src.pdf"
        out = tmp_path / "out.pdf"
        src.write_bytes(make_pdf_bytes(pages))
        content = f"input: src.pdf\nsteps:\n{steps_yaml}\noutput: out.pdf\n"
        p = _write_workflow(tmp_path, content)
        return load_workflow(p)

    def test_compress_step(self, tmp_path):
        cfg = self._make_cfg(tmp_path, "  - compress")
        run_workflow(cfg)
        assert cfg.output.exists()
        assert len(PdfReader(str(cfg.output)).pages) == 3

    def test_rotate_step(self, tmp_path):
        cfg = self._make_cfg(tmp_path, "  - rotate:\n      angle: 90")
        run_workflow(cfg)
        assert len(PdfReader(str(cfg.output)).pages) == 3

    def test_watermark_step(self, tmp_path):
        cfg = self._make_cfg(tmp_path, '  - watermark:\n      text: "TEST"')
        run_workflow(cfg)
        assert len(PdfReader(str(cfg.output)).pages) == 3

    def test_reorder_step(self, tmp_path):
        cfg = self._make_cfg(tmp_path, "  - reorder:\n      order: \"3,1,2\"", pages=3)
        run_workflow(cfg)
        assert len(PdfReader(str(cfg.output)).pages) == 3

    def test_split_step(self, tmp_path):
        cfg = self._make_cfg(tmp_path, "  - split:\n      pages: \"1-2\"", pages=5)
        run_workflow(cfg)
        assert len(PdfReader(str(cfg.output)).pages) == 2

    def test_pipeline_of_three_steps(self, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(make_pdf_bytes(4))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - compress
              - rotate:
                  angle: 180
              - watermark:
                  text: "DRAFT"
            output: out.pdf
        """)
        cfg = load_workflow(p)
        run_workflow(cfg)
        assert cfg.output.exists()
        assert len(PdfReader(str(cfg.output)).pages) == 4

    def test_input_file_preserved(self, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(make_pdf_bytes(2))
        original_bytes = src.read_bytes()
        p = _write_workflow(tmp_path, "input: src.pdf\nsteps:\n  - compress\noutput: out.pdf\n")
        cfg = load_workflow(p)
        run_workflow(cfg)
        assert src.read_bytes() == original_bytes

    def test_output_dir_created_automatically(self, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(make_pdf_bytes(1))
        p = _write_workflow(tmp_path, "input: src.pdf\nsteps:\n  - compress\noutput: subdir/out.pdf\n")
        cfg = load_workflow(p)
        run_workflow(cfg)
        assert cfg.output.exists()

    def test_failed_step_exits_with_1(self, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(make_pdf_bytes(2))
        # split pages out of range → fails at execution
        p = _write_workflow(tmp_path, "input: src.pdf\nsteps:\n  - split:\n      pages: \"10-20\"\noutput: out.pdf\n")
        cfg = load_workflow(p)
        with pytest.raises(SystemExit) as exc_info:
            run_workflow(cfg)
        assert exc_info.value.code == 1

    def test_no_partial_output_on_failure(self, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(make_pdf_bytes(2))
        out = tmp_path / "out.pdf"
        p = _write_workflow(tmp_path, "input: src.pdf\nsteps:\n  - split:\n      pages: \"10-20\"\noutput: out.pdf\n")
        cfg = load_workflow(p)
        with pytest.raises(SystemExit):
            run_workflow(cfg)
        assert not out.exists()

    def test_rotate_specific_pages(self, tmp_path):
        src = tmp_path / "src.pdf"
        src.write_bytes(make_pdf_bytes(4))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - rotate:
                  angle: 270
                  pages: "1,3"
            output: out.pdf
        """)
        cfg = load_workflow(p)
        run_workflow(cfg)
        assert len(PdfReader(str(cfg.output)).pages) == 4


# ---------------------------------------------------------------------------
# run_workflow — folder mode
# ---------------------------------------------------------------------------

class TestRunWorkflowFolder:
    def _make_folder_cfg(self, tmp_path, steps_yaml: str) -> WorkflowConfig:
        (tmp_path / "in").mkdir()
        content = f"input_folder: in\nsteps:\n{steps_yaml}\noutput_folder: out\n"
        p = _write_workflow(tmp_path, content)
        return load_workflow(p)

    def test_single_step_multiple_files(self, tmp_path):
        cfg = self._make_folder_cfg(tmp_path, "  - compress")
        (tmp_path / "in" / "a.pdf").write_bytes(make_pdf_bytes(2))
        (tmp_path / "in" / "b.pdf").write_bytes(make_pdf_bytes(3))
        run_workflow(cfg)
        assert (tmp_path / "out" / "a.pdf").exists()
        assert (tmp_path / "out" / "b.pdf").exists()

    def test_page_counts_preserved(self, tmp_path):
        cfg = self._make_folder_cfg(tmp_path, "  - compress")
        (tmp_path / "in" / "a.pdf").write_bytes(make_pdf_bytes(3))
        run_workflow(cfg)
        assert len(PdfReader(str(tmp_path / "out" / "a.pdf")).pages) == 3

    def test_multi_step_pipeline(self, tmp_path):
        steps = "  - compress\n  - rotate:\n      angle: 90"
        cfg = self._make_folder_cfg(tmp_path, steps)
        (tmp_path / "in" / "a.pdf").write_bytes(make_pdf_bytes(2))
        run_workflow(cfg)
        assert len(PdfReader(str(tmp_path / "out" / "a.pdf")).pages) == 2

    def test_empty_folder_returns_cleanly(self, tmp_path):
        cfg = self._make_folder_cfg(tmp_path, "  - compress")
        # no files added
        run_workflow(cfg)  # should not raise

    def test_failed_file_continues_and_exits_1(self, tmp_path):
        cfg = self._make_folder_cfg(tmp_path, "  - split:\n      pages: \"10-20\"")
        # good.pdf has 30 pages → split succeeds; bad.pdf has 2 pages → fails
        (tmp_path / "in" / "good.pdf").write_bytes(make_pdf_bytes(30))
        (tmp_path / "in" / "bad.pdf").write_bytes(make_pdf_bytes(2))
        with pytest.raises(SystemExit) as exc_info:
            run_workflow(cfg)
        assert exc_info.value.code == 1
        assert (tmp_path / "out" / "good.pdf").exists()
        assert not (tmp_path / "out" / "bad.pdf").exists()

    def test_output_folder_created(self, tmp_path):
        cfg = self._make_folder_cfg(tmp_path, "  - compress")
        (tmp_path / "in" / "a.pdf").write_bytes(make_pdf_bytes(1))
        run_workflow(cfg)
        assert (tmp_path / "out").is_dir()

    def test_pattern_filter(self, tmp_path):
        (tmp_path / "in").mkdir()
        p = _write_workflow(tmp_path, """
            input_folder: in
            pattern: "report*.pdf"
            steps:
              - compress
            output_folder: out
        """)
        cfg = load_workflow(p)
        (tmp_path / "in" / "report_a.pdf").write_bytes(make_pdf_bytes(1))
        (tmp_path / "in" / "other.pdf").write_bytes(make_pdf_bytes(1))
        run_workflow(cfg)
        assert (tmp_path / "out" / "report_a.pdf").exists()
        assert not (tmp_path / "out" / "other.pdf").exists()


# ---------------------------------------------------------------------------
# CLI: pdfuse batch
# ---------------------------------------------------------------------------

class TestCliBatch:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_single_file_success(self, runner, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(2))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - compress
            output: out.pdf
        """)
        result = runner.invoke(main, ["batch", str(p)], catch_exceptions=False)
        assert result.exit_code == 0
        assert (tmp_path / "out.pdf").exists()

    def test_multi_step_pipeline(self, runner, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(3))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - compress
              - rotate:
                  angle: 90
              - watermark:
                  text: "BATCH"
            output: out.pdf
        """)
        result = runner.invoke(main, ["batch", str(p)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(tmp_path / "out.pdf")).pages) == 3

    def test_missing_workflow_file(self, runner, tmp_path):
        result = runner.invoke(main, ["batch", str(tmp_path / "nope.yaml")])
        assert result.exit_code == 1

    def test_invalid_yaml(self, runner, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("key: [unclosed")
        result = runner.invoke(main, ["batch", str(p)])
        assert result.exit_code == 1

    def test_unknown_step(self, runner, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(1))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - merge
            output: out.pdf
        """)
        result = runner.invoke(main, ["batch", str(p)])
        assert result.exit_code == 1

    def test_folder_mode(self, runner, tmp_path):
        (tmp_path / "in").mkdir()
        (tmp_path / "in" / "a.pdf").write_bytes(make_pdf_bytes(2))
        (tmp_path / "in" / "b.pdf").write_bytes(make_pdf_bytes(3))
        p = _write_workflow(tmp_path, """
            input_folder: in
            steps:
              - compress
            output_folder: out
        """)
        result = runner.invoke(main, ["batch", str(p)], catch_exceptions=False)
        assert result.exit_code == 0
        assert (tmp_path / "out" / "a.pdf").exists()
        assert (tmp_path / "out" / "b.pdf").exists()

    def test_step_failure_exits_1(self, runner, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(2))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - split:
                  pages: "50-60"
            output: out.pdf
        """)
        result = runner.invoke(main, ["batch", str(p)])
        assert result.exit_code == 1
        assert not (tmp_path / "out.pdf").exists()
