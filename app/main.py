"""
app/main.py — FastAPI endpoint

POST /api/convert
  Input:  multipart/form-data  field "file" — a PDF
  Output: application/pdf — modified PDF with PerfCutContour added

Uses a temporary directory per request; cleaned up after response is sent.
"""

from __future__ import annotations
import os
import sys
import tempfile
import traceback

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import pikepdf

from .pdf.parser import extract_cutcontour_paths, ParseError
from .pdf.writer import append_perfcut_contour
from .pdf.verify import verify_output, collect_page_boxes, VerifyError
from .geometry.offset import offset_polygons

OFFSET_MM = 2.5
app = FastAPI(title="pdf-perfcut")


@app.post("/api/convert")
async def convert(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.pdf")
        output_path = os.path.join(tmpdir, "output.pdf")

        # Save upload
        contents = await file.read()
        with open(input_path, "wb") as f:
            f.write(contents)

        # Process
        try:
            pdf = pikepdf.open(input_path)
            page = pdf.pages[0]
            original_boxes = collect_page_boxes(page)

            polys = extract_cutcontour_paths(page)
            offset_polys = offset_polygons(polys, OFFSET_MM)

            if not offset_polys:
                raise ParseError("Clipper2 returned empty offset result.")

            append_perfcut_contour(pdf, 0, offset_polys)
            pdf.save(output_path)
            pdf.close()

            verify_output(output_path, original_boxes)

        except ParseError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except VerifyError as e:
            raise HTTPException(status_code=500, detail=f"Output verification failed: {e}")
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Internal error: {e}")

        # Return file — must read before tmpdir is cleaned up
        out_bytes = open(output_path, "rb").read()

    from fastapi.responses import Response
    return Response(
        content=out_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )


# Serve frontend at root
_frontend = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_frontend):
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")
