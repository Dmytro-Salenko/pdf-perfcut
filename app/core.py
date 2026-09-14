"""
app/core.py

Single entry point for PDF processing, usable from:
  - CLI (add_contour.py)
  - FastAPI endpoints
  - Future Google Drive hot-folder worker

process_pdf(input_path, output_path) → None
Raises ParseError or VerifyError on failure.
"""

from __future__ import annotations
import pikepdf

from .pdf.parser import extract_cutcontour_paths, ParseError
from .pdf.writer import append_perfcut_contour
from .pdf.verify import verify_output, collect_page_boxes, VerifyError
from .geometry.offset import offset_polygons

OFFSET_MM = 2.5


def process_pdf(input_path: str, output_path: str) -> None:
    """
    Open *input_path*, add a 2.5 mm PerfCutContour offset contour,
    write the result to *output_path*, and verify the output.

    Raises:
        ParseError   — CutContour not found or geometry unsupported.
        VerifyError  — Output failed integrity check.
        Exception    — Any other pikepdf / IO error.
    """
    pdf = pikepdf.open(input_path)
    page = pdf.pages[0]
    original_boxes = collect_page_boxes(page)

    polygons = extract_cutcontour_paths(page)
    offset_polys = offset_polygons(polygons, OFFSET_MM)

    if not offset_polys:
        raise ParseError("Clipper2 returned an empty offset result — check input geometry.")

    append_perfcut_contour(pdf, 0, offset_polys)
    pdf.save(output_path)
    pdf.close()

    verify_output(output_path, original_boxes)
