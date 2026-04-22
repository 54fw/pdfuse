
# pdfuse

[![CI](https://github.com/54fw/pdfuse/actions/workflows/ci.yml/badge.svg)](https://github.com/54fw/pdfuse/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Merge, split, compress, rotate, watermark, reorder, and batch-process PDFs — all from the terminal. No API keys, no cloud uploads.

---

## Table of contents

- [Installation](#installation)
- [Commands](#commands)
  - [merge](#merge)
  - [split](#split)
  - [convert](#convert)
  - [compress](#compress)
  - [rotate](#rotate)
  - [watermark](#watermark)
  - [reorder](#reorder)
  - [batch](#batch-workflow)
- [Platform notes](#platform-notes)
- [Dependencies](#dependencies)

---

## Installation

```bash
git clone https://github.com/54fw/pdfuse.git
cd pdfuse
pip install -e .
```

Verify the install:

```bash
pdfuse --version
```

---

## Commands

### merge

Combine multiple PDFs into one, in the order given.

```bash
pdfuse merge chapter1.pdf chapter2.pdf chapter3.pdf -o book.pdf
```

```
✓ Merged 3 file(s) → book.pdf (142 pages)
```

**Folder mode** — merge all PDFs in a directory into one file:

```bash
# Merge all PDFs sorted by name (default)
pdfuse merge --folder ./chapters/ -o book.pdf

# Sorted by last-modified date, newest first
pdfuse merge --folder ./reports/ --sort name --reverse -o combined.pdf

# Include subdirectories
pdfuse merge --folder ./chapters/ --recursive -o book.pdf
```

| Option | Default | Description |
|---|---|---|
| `--folder DIR` | — | Merge all PDFs in this directory |
| `--sort [name\|date]` | `name` | Sort order before merging |
| `--reverse` | off | Reverse sort order |
| `--recursive` | off | Recurse into subdirectories |
| `--pattern TEXT` | `*.pdf` | Glob filter |

---

### split

Extract a page range from a PDF.

```bash
# Extract pages 3–7
pdfuse split report.pdf --pages 3-7 -o excerpt.pdf

# Extract a single page
pdfuse split report.pdf --pages 5-5 -o page5.pdf
```

`--pages` uses the format `START-END` (1-indexed, inclusive).

**Folder mode** — split every PDF in a directory:

```bash
pdfuse split --folder ./inbox/ --pages 1-3 -o ./first_pages/

# Recursive with parallel workers
pdfuse split --folder ./docs/ --pages 1-1 -o ./covers/ --recursive --workers 4
```

| Option | Default | Description |
|---|---|---|
| `--folder DIR` | — | Process all PDFs in this directory |
| `--pages N-M` | required | Page range to extract (e.g. `1-3`) |
| `--recursive` | off | Recurse into subdirectories |
| `--pattern TEXT` | `*.pdf` | Glob filter |
| `--workers INT` | `1` | Parallel worker threads |

---

### convert

Convert images or Office documents to PDF.

```bash
# Single image
pdfuse convert photo.jpg -o photo.pdf

# Multiple images → one PDF (one page per image)
pdfuse convert scan1.png scan2.png scan3.png -o scans.pdf

# Word document (requires Microsoft Word on macOS/Windows or LibreOffice on Linux)
pdfuse convert report.docx -o report.pdf

# PowerPoint
pdfuse convert slides.pptx -o slides.pdf
```

Supported image formats: PNG, JPG, JPEG, BMP, TIFF.

**Folder mode** — batch-convert a directory (output extension is changed to `.pdf`):

```bash
# Convert all JPGs in a folder
pdfuse convert --folder ./scans/ --pattern "*.jpg" -o ./pdfs/

# Convert everything (all supported formats)
pdfuse convert --folder ./assets/ -o ./pdfs/ --recursive
```

| Option | Default | Description |
|---|---|---|
| `--folder DIR` | — | Convert all matching files in this directory |
| `--recursive` | off | Recurse into subdirectories |
| `--pattern TEXT` | `*` | Glob filter (e.g. `*.png`, `*.docx`) |
| `--workers INT` | `1` | Parallel worker threads |

---

### compress

Losslessly compress a PDF by deflating its content streams.

```bash
pdfuse compress report.pdf -o report_small.pdf
```

```
✓ Compressed report.pdf → report_small.pdf (1204 KB → 876 KB, 27.2% reduction)
```

**Folder mode:**

```bash
pdfuse compress --folder ./drafts/ -o ./compressed/

# Recursive with 4 parallel workers
pdfuse compress --folder ./archive/ -o ./out/ --recursive --workers 4
```

| Option | Default | Description |
|---|---|---|
| `--folder DIR` | — | Compress all PDFs in this directory |
| `--recursive` | off | Recurse into subdirectories |
| `--pattern TEXT` | `*.pdf` | Glob filter |
| `--workers INT` | `1` | Parallel worker threads |

---

### rotate

Rotate pages 90°, 180°, or 270° clockwise.

```bash
# Rotate all pages 90°
pdfuse rotate scan.pdf --angle 90 -o scan_fixed.pdf

# Rotate only page 2 upside-down
pdfuse rotate doc.pdf --angle 180 --pages 2 -o doc_fixed.pdf

# Rotate pages 1 and 3 by 270°
pdfuse rotate doc.pdf --angle 270 --pages 1,3 -o doc_rotated.pdf
```

`--pages` accepts a comma-separated list of 1-indexed page numbers. Omit to rotate all pages.

**Folder mode:**

```bash
pdfuse rotate --folder ./inbox/ --angle 90 -o ./fixed/

# Rotate only the first page of every file
pdfuse rotate --folder ./scans/ --angle 90 --pages 1 -o ./out/ --recursive
```

| Option | Default | Description |
|---|---|---|
| `--folder DIR` | — | Rotate all PDFs in this directory |
| `--angle [90\|180\|270]` | required | Rotation angle in degrees (clockwise) |
| `--pages N[,N...]` | all pages | Comma-separated 1-indexed page numbers to rotate |
| `--recursive` | off | Recurse into subdirectories |
| `--pattern TEXT` | `*.pdf` | Glob filter |
| `--workers INT` | `1` | Parallel worker threads |

---

### watermark

Stamp every page with a diagonal text watermark or a PDF overlay.

```bash
# Generated diagonal text watermark
pdfuse watermark contract.pdf --text "CONFIDENTIAL" -o contract_wm.pdf

# First page of another PDF used as a transparent stamp
pdfuse watermark report.pdf --stamp company_logo.pdf -o report_branded.pdf
```

**Folder mode:**

```bash
pdfuse watermark --folder ./contracts/ --text "DRAFT" -o ./watermarked/

pdfuse watermark --folder ./reports/ --stamp logo.pdf -o ./branded/ --workers 2
```

| Option | Default | Description |
|---|---|---|
| `--folder DIR` | — | Watermark all PDFs in this directory |
| `--recursive` | off | Recurse into subdirectories |
| `--pattern TEXT` | `*.pdf` | Glob filter |
| `--workers INT` | `1` | Parallel worker threads |

---

### reorder

Rearrange, duplicate, or omit pages using a comma-separated 1-indexed list.

```bash
# Reverse a 3-page document
pdfuse reorder doc.pdf --order 3,2,1 -o reversed.pdf

# Move the cover page to the end
pdfuse reorder doc.pdf --order 2,3,4,5,1 -o cover_last.pdf

# Duplicate the first page
pdfuse reorder doc.pdf --order 1,1,2,3 -o with_dup.pdf
```

**Folder mode:**

```bash
pdfuse reorder --folder ./docs/ --order 3,1,2 -o ./reordered/

pdfuse reorder --folder ./archive/ --order 2,1 -o ./out/ --recursive --workers 4
```

| Option | Default | Description |
|---|---|---|
| `--folder DIR` | — | Reorder pages in all PDFs in this directory |
| `--recursive` | off | Recurse into subdirectories |
| `--pattern TEXT` | `*.pdf` | Glob filter |
| `--workers INT` | `1` | Parallel worker threads |

A summary is printed after each folder run:

```
Summary: 12 succeeded, 0 failed
```

Failed files print a warning but do not stop the run. The exit code is 1 if any file failed.

---

## Batch workflow

Execute a sequence of operations defined in a YAML file.

```bash
pdfuse batch workflow.yaml

# Override the file pattern from the command line (folder modes only)
pdfuse batch workflow.yaml --pattern "report*.pdf"
```

### Single-file workflow

```yaml
# workflow.yaml
input: report.pdf
steps:
  - compress
  - watermark:
      text: "CONFIDENTIAL"
  - split:
      pages: "1-10"
  - rotate:
      angle: 90
      pages: "2,4"
output: final.pdf
```

Intermediate files are written to a temporary directory and cleaned up automatically. The original input file is never modified.

```
✓ Workflow complete → final.pdf
```

### Folder workflow — per-file output

Each file in the folder is independently run through the pipeline and written to `output_folder`.

```yaml
# bulk.yaml
input_folder: ./contracts/
pattern: "*.pdf"
steps:
  - compress
  - watermark:
      text: "DRAFT"
output_folder: ./processed/
```

```bash
pdfuse batch bulk.yaml
```

Failed files print a warning and processing continues; the exit code is 1 if any file failed.

### Folder workflow — merge all into one file

Add a `merge` step anywhere in the pipeline. Steps **before** `merge` are applied to each file
individually; `merge` collects all results and combines them into one PDF; steps **after** `merge`
are applied to that single merged file.

The result is written to `{output_folder}/{output_name}` (default `output_name: merged.pdf`),
or to an exact path via `output`.

```yaml
# assemble.yaml
input_folder: ./chapters/
steps:
  - merge:
      sort: name          # "name" (alphabetical, default) or "date" (last modified)
      reverse: false      # true to reverse sort order
      pattern: "*.pdf"    # glob filter (default: *.pdf)
  - compress
  - watermark:
      text: "DRAFT"
output_folder: ./processed/
output_name: book.pdf     # optional; default: merged.pdf
```

```bash
pdfuse batch assemble.yaml

# Override pattern at runtime
pdfuse batch assemble.yaml --pattern "ch*.pdf"
```

```
Summary: 5 succeeded, 0 failed
✓ Merged 5 file(s) → ./processed/book.pdf
```

### Supported step types

| Step | In single-file workflow | In folder workflow |
|---|---|---|
| `compress` | — | — |
| `merge` | `with` (comma-separated paths or YAML list) | `sort`, `reverse`, `pattern` (all optional) |
| `watermark` | `text` **or** `stamp` | same |
| `split` | `pages` (e.g. `"1-5"`) | same |
| `rotate` | `angle` (90 / 180 / 270); optional `pages` | same |
| `reorder` | `order` (e.g. `"3,1,2"`) | same |

---

## Platform notes

| Feature | Requirement |
|---|---|
| `convert` with DOCX/PPTX | Microsoft Word (macOS/Windows) **or** LibreOffice (Linux) |
| `watermark --text` | [reportlab](https://www.reportlab.com/) (installed automatically) |

Install LibreOffice on Debian/Ubuntu:

```bash
sudo apt install libreoffice
```

---

## Dependencies

| Package | Purpose |
|---|---|
| [click](https://click.palletsprojects.com/) | CLI framework |
| [rich](https://github.com/Textualize/rich) | Terminal output and progress bars |
| [pypdf](https://github.com/py-pdf/pypdf) | PDF read / write / transform |
| [Pillow](https://pillow.readthedocs.io/) | Image to PDF conversion |
| [reportlab](https://www.reportlab.com/) | Text watermark rendering |
| [docx2pdf](https://github.com/AlJohri/docx2pdf) | Office document to PDF |
| [python-docx](https://python-docx.readthedocs.io/) | Word document metadata |
| [PyYAML](https://pyyaml.org/) | Batch workflow parsing |

---

## License

MIT
