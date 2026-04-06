# pdfuse

Merge, split, and convert files to PDF — all from the terminal. No API keys, no cloud uploads.

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

## Supported formats

| Type   | Extensions                    |
|--------|-------------------------------|
| Image  | PNG, JPG, JPEG, BMP, TIFF     |
| Office | DOCX, PPTX                    |
| PDF    | PDF (merge / split / info)    |

## Platform notes

`docx2pdf` requires **Microsoft Word** on Windows/macOS or **LibreOffice** on Linux.
Install LibreOffice with `sudo apt install libreoffice` (Debian/Ubuntu).

## Dependencies

- [click](https://click.palletsprojects.com/) — CLI framework  
- [rich](https://github.com/Textualize/rich) — terminal formatting  
- [pypdf](https://github.com/py-pdf/pypdf) — PDF merge / split  
- [Pillow](https://pillow.readthedocs.io/) — image to PDF  
- [docx2pdf](https://github.com/AlJohri/docx2pdf) — Office to PDF  
- [python-docx](https://python-docx.readthedocs.io/) — Word metadata  

## License

MIT
