"""
app/main.py — FastAPI application

Endpoints:
  POST /api/convert        — single PDF → processed PDF
  POST /api/convert-batch  — multiple PDFs → ZIP archive
"""

from __future__ import annotations
import io
import os
import tempfile
import traceback
import zipfile

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .core import process_pdf
from .pdf.parser import ParseError
from .pdf.verify import VerifyError

app = FastAPI(title="pdf-perfcut")


# ---------------------------------------------------------------------------
# Single-file endpoint
# ---------------------------------------------------------------------------

@app.post("/api/convert")
async def convert(file: UploadFile = File(...)):
    _require_pdf(file.filename)

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path  = os.path.join(tmpdir, "input.pdf")
        output_path = os.path.join(tmpdir, "output.pdf")

        with open(input_path, "wb") as f:
            f.write(await file.read())

        try:
            process_pdf(input_path, output_path)
        except (ParseError, VerifyError) as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Internal error: {e}")

        out_bytes = open(output_path, "rb").read()

    return Response(
        content=out_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )


# ---------------------------------------------------------------------------
# Batch endpoint
# ---------------------------------------------------------------------------

@app.post("/api/convert-batch")
async def convert_batch(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    errors: list[str] = []
    zip_buffer = io.BytesIO()

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for upload in files:
                fname = upload.filename or "unknown.pdf"
                if not fname.lower().endswith(".pdf"):
                    errors.append(f"{fname} — Not a PDF file.")
                    continue

                input_path  = os.path.join(tmpdir, f"in_{fname}")
                output_path = os.path.join(tmpdir, f"out_{fname}")

                with open(input_path, "wb") as f:
                    f.write(await upload.read())

                try:
                    process_pdf(input_path, output_path)
                    zf.write(output_path, arcname=fname)
                except (ParseError, VerifyError) as e:
                    errors.append(f"{fname} — {e}")
                except Exception as e:
                    errors.append(f"{fname} — Internal error: {e}")

            if errors:
                zf.writestr("errors.txt", "\n".join(errors) + "\n")

    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.read(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="results.zip"'},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_pdf(filename: str | None) -> None:
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------

_frontend = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_frontend):
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")
