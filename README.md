# pdf-perfcut

A lightweight prepress automation tool that generates a **PerfCutContour** separation from an existing **CutContour** spot color in a PDF.

Given a print-ready PDF with a `CutContour` vector contour (a common prepress convention for die-cutting), pdf-perfcut computes an outward offset of exactly **2.5 mm** and appends the result as a new `PerfCutContour` PDF Separation spot color — ready for production finishing workflows.

---

## What problem it solves

In commercial print production, **CutContour** defines the die-cut edge. A **PerfCutContour** is the same shape expanded outward — typically used for perforation rules or kiss-cut positioning. Creating this contour manually is error-prone and slow. pdf-perfcut automates it precisely and verifiably.

---

## Workflow

```
input PDF (with CutContour)
  → identify CutContour Separation spot color
  → extract stroked vector paths, apply CTM
  → flatten Bézier curves to polyline (≤ 0.03 mm tolerance)
  → offset +2.5 mm outward (Clipper2)
  → add PerfCutContour as PDF Separation (CMYK 100/0/100/0, stroke overprint)
  → verify output integrity
  → return modified PDF
```

The original PDF content — artwork, images, fonts, transparency, page boxes, and spot colors — is **never modified**. Only the new contour stream is appended.

---

## Core features

- Identifies `CutContour` as a real **PDF Separation** spot color — not by visual appearance
- Generates `PerfCutContour` as a real **PDF Separation** spot color
  - Alternate preview: DeviceCMYK 100/0/100/0 (green)
  - Stroke only, no fill
  - **Stroke overprint enabled** (`/OP true`, `/OPM 1`)
- Fixed offset: **2.5 mm outward** — deterministic, no UI option to change
- Correctly applies PDF transformation matrices (CTM) before computing geometry
- Adaptive Bézier flattening via De Casteljau subdivision (≤ 0.03 mm geometric tolerance)
- Preserves original artwork, page boxes (MediaBox, TrimBox, BleedBox), and OutputIntent
- Fails loudly on unsupported structures rather than producing a silently incorrect result

---

## Technical approach

**Bézier flattening** — PDF paths use cubic Bézier curves. Before offsetting, curves are flattened to polylines using recursive De Casteljau subdivision, stopping when the maximum perpendicular deviation falls below the tolerance threshold.

**Polygon offsetting** — Uses [Clipper2](https://github.com/AngusJohnson/Clipper2) (via [pyclipr](https://github.com/drlukeparry/pyclipr)) for robust offset computation with round joins.

**PDF manipulation** — [pikepdf](https://pikepdf.readthedocs.io/) is used for low-level PDF access: parsing content streams, reading/writing colorspace resources, and appending content streams without touching the original data.

---

## Architecture

```
app/
  core.py          ← process_pdf(input, output) — shared pipeline entry point
  pdf/
    parser.py      ← extract CutContour paths from content stream
    writer.py      ← append PerfCutContour stream + resources
    verify.py      ← post-write integrity check
  geometry/
    bezier.py      ← adaptive Bézier → polyline flattener
    offset.py      ← Clipper2 polygon offset
  main.py          ← FastAPI: /api/convert, /api/convert-batch

frontend/
  index.html       ← single page, drag-and-drop
  app.js
  style.css

add_contour.py     ← CLI wrapper
tests/
  fixtures/        ← synthetic PDF fixtures (no customer artwork)
  test_pipeline.py ← regression tests
```

`app/core.process_pdf()` is the single entry point used by both the web API and the CLI. A future Google Drive worker will call the same function.

---

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| PDF I/O | pikepdf / qpdf |
| Polygon offset | Clipper2 via pyclipr |
| Web API | FastAPI + uvicorn |
| Frontend | Plain HTML / CSS / JS |
| Container | Docker |

No database, no message queue, no authentication, no persistent storage.

---

## Local installation

**Requirements:** Python 3.10+ and pip.

```bash
git clone https://github.com/your-username/pdf-perfcut.git
cd pdf-perfcut
pip install -r requirements.txt
```

### CLI

```bash
python add_contour.py input.pdf output.pdf
```

### Web server

```bash
uvicorn app.main:app --reload
# → http://localhost:8000
```

### macOS — double-click launcher

```bash
# In Finder, double-click:
run.command
# Opens http://localhost:8765 in your default browser.
```

---

## Docker

```bash
docker build -t pdf-perfcut .
docker run -p 8000:8000 pdf-perfcut
# → http://localhost:8000
```

---

## API endpoints

### `POST /api/convert`

Convert a single PDF.

| | |
|---|---|
| Content-Type | `multipart/form-data` |
| Field | `file` — PDF file |
| Response | `application/pdf` — modified PDF |
| Errors | `422` with JSON `{"detail": "..."}` |

```bash
curl -X POST http://localhost:8000/api/convert \
  -F "file=@input.pdf" \
  -o output.pdf
```

### `POST /api/convert-batch`

Convert multiple PDFs.

| | |
|---|---|
| Content-Type | `multipart/form-data` |
| Field | `files` — one or more PDF files |
| Response | `application/zip` — `results.zip` containing processed PDFs and, if any file failed, `errors.txt` |

```bash
curl -X POST http://localhost:8000/api/convert-batch \
  -F "files=@a.pdf" \
  -F "files=@b.pdf" \
  -F "files=@c.pdf" \
  -o results.zip
```

**`errors.txt` format (only present when errors occurred):**
```
bad-file.pdf — CutContour spot color not found in page Resources.
another.pdf — CutContour contains an open (unclosed) subpath.
```

---

## Limitations (v1)

- Processes **page 0 only** (single-page PDFs and first page of multi-page PDFs)
- Closed paths only — open CutContour paths are rejected with an error
- No UI for changing the offset distance (fixed at 2.5 mm by design)
- Sequential batch processing (no parallelism)
- Optimised for production PDFs using standard Separation spot color conventions

---

## Testing

```bash
python -m pytest tests/ -v
```

Test coverage:

- CutContour spot color extraction
- Bézier flattening and CTM application
- Offset distance (2.500 mm ± 0.05 mm at all four bbox edges)
- PerfCutContour is a real Separation spot color (DeviceCMYK 100/0/100/0)
- Stroke overprint (`/OP true`) present and applied in content stream
- Page boxes (MediaBox, TrimBox, BleedBox) unchanged
- Output reopens and passes pikepdf validation
- Missing CutContour → ParseError (not silent failure)

Fixtures are **synthetic** — small PDFs generated by `tests/make_fixtures.py` that reproduce the required PDF structure without customer artwork.

---

## Planned: Google Drive Hot Folder

A background worker that monitors a Google Drive folder, processes incoming PDFs automatically, and writes results back — using the same `process_pdf()` function as the web API.

No implementation yet. The processing pipeline is already structured to support it.

---

## Spot color reference

| Color | Ink name | Alternate | Preview CMYK |
|---|---|---|---|
| Input | `CutContour` | DeviceCMYK | 0/100/0/0 (magenta) |
| Output | `PerfCutContour` | DeviceCMYK | 100/0/100/0 (green) |

Both colors use overprint mode. The original CutContour is never modified.
