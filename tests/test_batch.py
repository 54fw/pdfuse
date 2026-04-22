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
            _parse_step("foobar")

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

    def test_merge_no_params_ok(self):
        _validate_step_params(StepConfig("merge"))  # no params required at step level

    def test_merge_with_ok(self):
        _validate_step_params(StepConfig("merge", {"with": ["a.pdf", "b.pdf"]}))

    def test_merge_sort_name_ok(self):
        _validate_step_params(StepConfig("merge", {"sort": "name"}))

    def test_merge_sort_date_ok(self):
        _validate_step_params(StepConfig("merge", {"sort": "date"}))

    def test_merge_bad_sort_raises(self):
        with pytest.raises(ValueError, match="sort must be"):
            _validate_step_params(StepConfig("merge", {"sort": "size"}))

    def test_unknown_param_compress_raises(self):
        with pytest.raises(ValueError, match="unknown parameter"):
            _validate_step_params(StepConfig("compress", {"level": 9}))

    def test_unknown_param_rotate_raises(self):
        with pytest.raises(ValueError, match="unknown parameter"):
            _validate_step_params(StepConfig("rotate", {"angle": 90, "quality": "high"}))

    def test_unknown_param_watermark_raises(self):
        with pytest.raises(ValueError, match="unknown parameter"):
            _validate_step_params(StepConfig("watermark", {"text": "X", "opacity": 0.5}))

    def test_unknown_param_split_raises(self):
        with pytest.raises(ValueError, match="unknown parameter"):
            _validate_step_params(StepConfig("split", {"pages": "1-3", "extra": True}))

    def test_unknown_param_reorder_raises(self):
        with pytest.raises(ValueError, match="unknown parameter"):
            _validate_step_params(StepConfig("reorder", {"order": "1,2", "foo": "bar"}))

    def test_unknown_param_merge_raises(self):
        with pytest.raises(ValueError, match="unknown parameter"):
            _validate_step_params(StepConfig("merge", {"sort": "name", "blah": True}))

    def test_watermark_pages_allowed(self):
        _validate_step_params(StepConfig("watermark", {"text": "X", "pages": "1,3"}))


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

    def test_merge_single_file_mode(self):
        assert _step_label(StepConfig("merge", {"with": ["a.pdf", "b.pdf"]})) == "merge: +2 file(s)"

    def test_merge_folder_mode_defaults(self):
        assert _step_label(StepConfig("merge")) == "merge: all '*.pdf' (sort=name)"

    def test_merge_folder_mode_with_params(self):
        label = _step_label(StepConfig("merge", {"pattern": "*.pdf", "sort": "date", "reverse": True}))
        assert label == "merge: all '*.pdf' (sort=date ↓)"


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
              - foobar
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

    def test_both_output_and_output_folder_raises(self, tmp_path):
        (tmp_path / "docs").mkdir()
        p = _write_workflow(tmp_path, """
            input_folder: docs
            steps:
              - compress
            output: out.pdf
            output_folder: out/
        """)
        with pytest.raises(SystemExit):
            load_workflow(p)

    def test_folder_merge_mode_output_folder(self, tmp_path):
        (tmp_path / "docs").mkdir()
        p = _write_workflow(tmp_path, """
            input_folder: docs
            steps:
              - merge:
                  sort: name
                  pattern: "*.pdf"
              - compress
            output_folder: out
        """)
        cfg = load_workflow(p)
        assert cfg.input_folder == tmp_path / "docs"
        assert cfg.output_folder == tmp_path / "out"
        assert cfg.output is None
        assert cfg.output_name == "merged.pdf"  # default
        assert cfg.pattern == "*.pdf"

    def test_folder_merge_mode_output_name(self, tmp_path):
        (tmp_path / "docs").mkdir()
        p = _write_workflow(tmp_path, """
            input_folder: docs
            steps:
              - merge
            output_folder: out
            output_name: contracts_final.pdf
        """)
        cfg = load_workflow(p)
        assert cfg.output_name == "contracts_final.pdf"

    def test_folder_merge_mode_exact_output(self, tmp_path):
        (tmp_path / "docs").mkdir()
        p = _write_workflow(tmp_path, """
            input_folder: docs
            steps:
              - merge
            output: result.pdf
        """)
        cfg = load_workflow(p)
        assert cfg.output == tmp_path / "result.pdf"
        assert cfg.output_folder is None

    def test_folder_merge_invalid_sort_raises(self, tmp_path):
        (tmp_path / "docs").mkdir()
        p = _write_workflow(tmp_path, """
            input_folder: docs
            steps:
              - merge:
                  sort: size
            output_folder: out
        """)
        with pytest.raises(SystemExit):
            load_workflow(p)

    def test_folder_merge_with_param_raises(self, tmp_path):
        (tmp_path / "docs").mkdir()
        p = _write_workflow(tmp_path, """
            input_folder: docs
            steps:
              - merge:
                  with: "other.pdf"
            output_folder: out
        """)
        with pytest.raises(SystemExit):
            load_workflow(p)

    def test_single_file_merge_without_with_raises(self, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(1))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - merge
            output: out.pdf
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

    def test_watermark_with_pages(self, tmp_path):
        cfg = self._make_cfg(tmp_path, '  - watermark:\n      text: "X"\n      pages: "1,3"', pages=4)
        run_workflow(cfg)
        assert len(PdfReader(str(cfg.output)).pages) == 4

    def test_watermark_invalid_pages_exit_1(self, tmp_path):
        cfg = self._make_cfg(tmp_path, '  - watermark:\n      text: "X"\n      pages: "99"', pages=3)
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

    def test_merge_step(self, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(2))
        (tmp_path / "extra.pdf").write_bytes(make_pdf_bytes(3))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - merge:
                  with: "extra.pdf"
            output: out.pdf
        """)
        cfg = load_workflow(p)
        run_workflow(cfg)
        assert len(PdfReader(str(cfg.output)).pages) == 5

    def test_merge_step_yaml_list(self, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(1))
        (tmp_path / "b.pdf").write_bytes(make_pdf_bytes(2))
        (tmp_path / "c.pdf").write_bytes(make_pdf_bytes(3))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - merge:
                  with:
                    - b.pdf
                    - c.pdf
            output: out.pdf
        """)
        cfg = load_workflow(p)
        run_workflow(cfg)
        assert len(PdfReader(str(cfg.output)).pages) == 6

    def test_merge_missing_with_file_raises(self, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(1))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - merge:
                  with: "nonexistent.pdf"
            output: out.pdf
        """)
        with pytest.raises(SystemExit):
            load_workflow(p)


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
# run_workflow — folder-merge mode
# ---------------------------------------------------------------------------

class TestRunWorkflowFolderMerge:
    def _make_cfg(self, tmp_path, merge_params: str = "", post_steps: str = "") -> WorkflowConfig:
        """Build a folder-merge workflow where merge is the first step."""
        (tmp_path / "in").mkdir()
        merge_block = f"  - merge:\n{merge_params}" if merge_params else "  - merge"
        extra = post_steps or ""
        content = (
            f"input_folder: in\n"
            f"steps:\n{merge_block}\n{extra}"
            f"output_folder: out\n"
        )
        p = _write_workflow(tmp_path, content)
        return load_workflow(p)

    def test_merges_all_files(self, tmp_path):
        cfg = self._make_cfg(tmp_path)
        (tmp_path / "in" / "a.pdf").write_bytes(make_pdf_bytes(2))
        (tmp_path / "in" / "b.pdf").write_bytes(make_pdf_bytes(3))
        run_workflow(cfg)
        assert len(PdfReader(str(tmp_path / "out" / "merged.pdf")).pages) == 5

    def test_output_name_default(self, tmp_path):
        cfg = self._make_cfg(tmp_path)
        (tmp_path / "in" / "a.pdf").write_bytes(make_pdf_bytes(1))
        run_workflow(cfg)
        assert (tmp_path / "out" / "merged.pdf").exists()

    def test_output_name_custom(self, tmp_path):
        (tmp_path / "in").mkdir()
        p = _write_workflow(tmp_path, """
            input_folder: in
            steps:
              - merge
            output_folder: out
            output_name: contracts_final.pdf
        """)
        cfg = load_workflow(p)
        (tmp_path / "in" / "a.pdf").write_bytes(make_pdf_bytes(1))
        run_workflow(cfg)
        assert (tmp_path / "out" / "contracts_final.pdf").exists()
        assert not (tmp_path / "out" / "merged.pdf").exists()

    def test_pre_merge_steps(self, tmp_path):
        # steps BEFORE merge are applied per-file
        (tmp_path / "in").mkdir()
        p = _write_workflow(tmp_path, """
            input_folder: in
            steps:
              - compress
              - merge
            output_folder: out
        """)
        cfg = load_workflow(p)
        (tmp_path / "in" / "a.pdf").write_bytes(make_pdf_bytes(2))
        (tmp_path / "in" / "b.pdf").write_bytes(make_pdf_bytes(3))
        run_workflow(cfg)
        assert len(PdfReader(str(tmp_path / "out" / "merged.pdf")).pages) == 5

    def test_post_merge_steps(self, tmp_path):
        # steps AFTER merge are applied to the single merged file
        cfg = self._make_cfg(tmp_path, post_steps="  - compress\n")
        (tmp_path / "in" / "a.pdf").write_bytes(make_pdf_bytes(1))
        (tmp_path / "in" / "b.pdf").write_bytes(make_pdf_bytes(2))
        run_workflow(cfg)
        assert len(PdfReader(str(tmp_path / "out" / "merged.pdf")).pages) == 3

    def test_merge_step_pattern(self, tmp_path):
        cfg = self._make_cfg(tmp_path, merge_params="      pattern: \"keep*.pdf\"\n")
        (tmp_path / "in" / "keep.pdf").write_bytes(make_pdf_bytes(2))
        (tmp_path / "in" / "other.pdf").write_bytes(make_pdf_bytes(3))
        run_workflow(cfg)
        assert len(PdfReader(str(tmp_path / "out" / "merged.pdf")).pages) == 2

    def test_merge_step_sort_date_reverse(self, tmp_path):
        import os
        (tmp_path / "in").mkdir()
        p = _write_workflow(tmp_path, """
            input_folder: in
            steps:
              - merge:
                  sort: date
                  reverse: true
            output_folder: out
        """)
        cfg = load_workflow(p)
        a = tmp_path / "in" / "a.pdf"
        b = tmp_path / "in" / "b.pdf"
        a.write_bytes(make_pdf_bytes(1))
        b.write_bytes(make_pdf_bytes(2))
        os.utime(a, (1_000_000, 1_000_000))
        os.utime(b, (2_000_000, 2_000_000))
        run_workflow(cfg)
        assert len(PdfReader(str(tmp_path / "out" / "merged.pdf")).pages) == 3

    def test_empty_folder_returns_cleanly(self, tmp_path):
        cfg = self._make_cfg(tmp_path)
        run_workflow(cfg)
        assert not (tmp_path / "out" / "merged.pdf").exists()

    def test_output_dir_created(self, tmp_path):
        cfg = self._make_cfg(tmp_path)
        (tmp_path / "in" / "a.pdf").write_bytes(make_pdf_bytes(1))
        run_workflow(cfg)
        assert (tmp_path / "out").is_dir()

    def test_output_exact_path(self, tmp_path):
        (tmp_path / "in").mkdir()
        p = _write_workflow(tmp_path, """
            input_folder: in
            steps:
              - merge
            output: result/book.pdf
        """)
        cfg = load_workflow(p)
        (tmp_path / "in" / "a.pdf").write_bytes(make_pdf_bytes(2))
        run_workflow(cfg)
        assert (tmp_path / "result" / "book.pdf").exists()

    def test_failed_pre_merge_file_still_merges_rest_exits_1(self, tmp_path):
        (tmp_path / "in").mkdir()
        p = _write_workflow(tmp_path, """
            input_folder: in
            steps:
              - split:
                  pages: "10-20"
              - merge
            output_folder: out
        """)
        cfg = load_workflow(p)
        (tmp_path / "in" / "good.pdf").write_bytes(make_pdf_bytes(30))
        (tmp_path / "in" / "bad.pdf").write_bytes(make_pdf_bytes(2))
        with pytest.raises(SystemExit) as exc_info:
            run_workflow(cfg)
        assert exc_info.value.code == 1
        # good.pdf succeeded, so merged output should still exist
        assert (tmp_path / "out" / "merged.pdf").exists()


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
              - foobar
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

    def test_merge_step(self, runner, tmp_path):
        (tmp_path / "src.pdf").write_bytes(make_pdf_bytes(2))
        (tmp_path / "extra.pdf").write_bytes(make_pdf_bytes(3))
        p = _write_workflow(tmp_path, """
            input: src.pdf
            steps:
              - merge:
                  with: "extra.pdf"
            output: out.pdf
        """)
        result = runner.invoke(main, ["batch", str(p)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(tmp_path / "out.pdf")).pages) == 5

    def test_folder_merge_mode(self, runner, tmp_path):
        src = tmp_path / "in"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(2))
        (src / "b.pdf").write_bytes(make_pdf_bytes(3))
        p = _write_workflow(tmp_path, """
            input_folder: in
            steps:
              - merge
            output_folder: out
        """)
        result = runner.invoke(main, ["batch", str(p)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(tmp_path / "out" / "merged.pdf")).pages) == 5

    def test_folder_merge_output_name(self, runner, tmp_path):
        src = tmp_path / "in"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(2))
        p = _write_workflow(tmp_path, """
            input_folder: in
            steps:
              - merge
            output_folder: out
            output_name: final.pdf
        """)
        result = runner.invoke(main, ["batch", str(p)], catch_exceptions=False)
        assert result.exit_code == 0
        assert (tmp_path / "out" / "final.pdf").exists()

    def test_folder_merge_pattern_flag(self, runner, tmp_path):
        src = tmp_path / "in"
        src.mkdir()
        (src / "keep.pdf").write_bytes(make_pdf_bytes(2))
        (src / "skip.pdf").write_bytes(make_pdf_bytes(3))
        p = _write_workflow(tmp_path, """
            input_folder: in
            steps:
              - merge
            output_folder: out
        """)
        result = runner.invoke(
            main, ["batch", str(p), "--pattern", "keep*.pdf"], catch_exceptions=False
        )
        assert result.exit_code == 0
        assert len(PdfReader(str(tmp_path / "out" / "merged.pdf")).pages) == 2

    def test_folder_merge_post_steps(self, runner, tmp_path):
        src = tmp_path / "in"
        src.mkdir()
        (src / "a.pdf").write_bytes(make_pdf_bytes(2))
        (src / "b.pdf").write_bytes(make_pdf_bytes(3))
        p = _write_workflow(tmp_path, """
            input_folder: in
            steps:
              - merge
              - compress
              - watermark:
                  text: "DRAFT"
            output_folder: out
        """)
        result = runner.invoke(main, ["batch", str(p)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(tmp_path / "out" / "merged.pdf")).pages) == 5

    def test_folder_merge_sort_date(self, runner, tmp_path):
        import os
        src = tmp_path / "in"
        src.mkdir()
        a = src / "a.pdf"
        b = src / "b.pdf"
        a.write_bytes(make_pdf_bytes(1))
        b.write_bytes(make_pdf_bytes(2))
        os.utime(a, (1_000_000, 1_000_000))
        os.utime(b, (2_000_000, 2_000_000))
        p = _write_workflow(tmp_path, """
            input_folder: in
            steps:
              - merge:
                  sort: date
            output_folder: out
        """)
        result = runner.invoke(main, ["batch", str(p)], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(PdfReader(str(tmp_path / "out" / "merged.pdf")).pages) == 3
