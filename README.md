# pdf-perfcut

Production prepress utility that adds a **2.5 mm outward PerfCutContour** spot-color contour to any PDF that contains a `CutContour` spot color.

## What it does

```
input PDF
→ locate vector CutContour (real PDF Separation color)
→ extract stroked paths + apply CTM
→ flatten Béziers (≤ 0.03 mm tolerance)
→ offset +2.5 mm outward (Clipper2 / pyclipr)
→ append PerfCutContour Separation (CMYK 100/0/100/0)
→ verify output
→ return modified PDF
```

Nothing is rasterized. Original content is untouched.

## Phase 1 – CLI

```bash
python add_contour.py input.pdf output.pdf
```

## Phase 2 – Web API

```bash
# Install
pip install -r requirements.txt

# Run
uvicorn app.main:app --reload

# Convert
curl -X POST http://localhost:8000/api/convert \
  -F "file=@input.pdf" \
  -o output.pdf
```

Open `http://localhost:8000` for the drag-and-drop UI.

## Docker

```bash
docker build -t pdf-perfcut .
docker run -p 8000:8000 pdf-perfcut
```

## Tests

```bash
python -m pytest tests/ -v
```

## Stack

- Python 3.12 / FastAPI / uvicorn
- pikepdf (PDF I/O)
- pyclipr / Clipper2 (polygon offset)
- Plain HTML + CSS + JS (no frameworks)

## Spot color spec

| Color | Name | Alternate | Preview CMYK |
|-------|------|-----------|-------------|
| Input | `CutContour` | DeviceCMYK | 0/100/0/0 (magenta) |
| Output | `PerfCutContour` | DeviceCMYK | 100/0/100/0 (green) |

Stroke only, no fill. Stroke width: 0.25 pt.

## Limitations (v1)

- Single-page PDFs only (processes page 0).
- Closed paths only; open paths raise an error.
- No UI for changing offset distance (fixed at 2.5 mm by design).
