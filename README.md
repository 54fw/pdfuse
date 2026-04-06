# pdfuse

Merge, split, convert, compress, rotate, watermark, and reorder PDFs — all from the terminal. No API keys, no cloud uploads.

## Installation

```bash
pip install pdfuse
```

Or install from source:

```bash
git clone https://github.com/yourname/pdfuse.git
cd pdfuse
pip install -e .
```

## Usage

### Merge PDFs

```bash
pdfuse merge a.pdf b.pdf c.pdf -o output.pdf
```

### Split / Extract pages

```bash
pdfuse split input.pdf --pages 1-3 -o part.pdf
```

### Convert to PDF

```bash
# Single image
pdfuse convert photo.jpg -o photo.pdf

# Multiple images → single PDF
pdfuse convert *.jpg -o merged.pdf

# Word document (requires Microsoft Word or LibreOffice)
pdfuse convert doc.docx -o doc.pdf

# PowerPoint (requires Microsoft Word or LibreOffice)
pdfuse convert slides.pptx -o slides.pdf
```

### PDF info

```bash
pdfuse info report.pdf
```

### Compress

```bash
pdfuse compress report.pdf -o report_small.pdf
```

Losslessly compresses content streams. Reports before/after size and % reduction.

### Rotate pages

```bash
# Rotate all pages 90° clockwise
pdfuse rotate scan.pdf --angle 90 -o scan_fixed.pdf

# Rotate only page 2 by 180°
pdfuse rotate doc.pdf --angle 180 --pages 2 -o doc_p2.pdf

# Rotate pages 1 and 3 by 270°
pdfuse rotate doc.pdf --angle 270 --pages 1,3 -o doc_rotated.pdf
```

`--angle` must be 90, 180, or 270. `--pages` accepts a comma-separated list of 1-indexed page numbers (default: all pages).

### Watermark

```bash
# Diagonal text watermark
pdfuse watermark contract.pdf --text "CONFIDENTIAL" -o contract_draft.pdf

# PDF stamp overlay (e.g. a logo page)
pdfuse watermark report.pdf --stamp logo.pdf -o report_branded.pdf
```

Use `--text` for a generated diagonal watermark or `--stamp` to overlay the first page of another PDF.

### Reorder pages

```bash
# Reverse a 3-page document
pdfuse reorder doc.pdf --order 3,2,1 -o doc_reversed.pdf

# Move cover page to the end
pdfuse reorder doc.pdf --order 2,3,4,5,1 -o doc_cover_last.pdf

# Duplicate a page
pdfuse reorder doc.pdf --order 1,1,2,3 -o doc_dup.pdf
```

Pages can be repeated, omitted, or rearranged freely.

## Supported formats

| Type   | Extensions                                              |
|--------|---------------------------------------------------------|
| Image  | PNG, JPG, JPEG, BMP, TIFF                               |
| Office | DOCX, PPTX                                              |
| PDF    | PDF (merge / split / info / compress / rotate / watermark / reorder) |

## Platform notes

`docx2pdf` requires **Microsoft Word** on Windows/macOS or **LibreOffice** on Linux.
Install LibreOffice with `sudo apt install libreoffice` (Debian/Ubuntu).

## Dependencies

- [click](https://click.palletsprojects.com/) — CLI framework  
- [rich](https://github.com/Textualize/rich) — terminal formatting  
- [pypdf](https://github.com/py-pdf/pypdf) — PDF read/write/transform  
- [Pillow](https://pillow.readthedocs.io/) — image to PDF  
- [reportlab](https://www.reportlab.com/) — text watermark generation  
- [docx2pdf](https://github.com/AlJohri/docx2pdf) — Office to PDF  
- [python-docx](https://python-docx.readthedocs.io/) — Word metadata  

## License

MIT
