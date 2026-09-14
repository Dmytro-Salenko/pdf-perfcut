#!/usr/bin/env python3
"""
add_contour.py — Phase 1 CLI

Usage:
    python add_contour.py input.pdf output.pdf

Takes a PDF with a CutContour spot color, generates a 2.5 mm outward offset,
and writes it back as PerfCutContour.  Fails loudly if anything is wrong.
"""

from __future__ import annotations
import sys
import os

# Allow running from project root without installing the package
sys.path.insert(0, os.path.dirname(__file__))

import pikepdf

from app.pdf.parser import extract_cutcontour_paths, ParseError
from app.pdf.writer import append_perfcut_contour
from app.pdf.verify import verify_output, collect_page_boxes, VerifyError
from app.geometry.offset import offset_polygons

OFFSET_MM = 2.5


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python add_contour.py input.pdf output.pdf", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    if not os.path.isfile(input_path):
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # ---- Step 1: Open ----
    print(f"Opening: {input_path}")
    try:
        pdf = pikepdf.open(input_path)
    except Exception as e:
        print(f"ERROR: cannot open PDF: {e}", file=sys.stderr)
        sys.exit(1)

    page = pdf.pages[0]
    original_boxes = collect_page_boxes(page)
    print(f"  Page size: {page.obj.get('/MediaBox')}")

    # ---- Step 2: Extract CutContour ----
    print("Extracting CutContour paths…")
    try:
        polygons = extract_cutcontour_paths(page)
    except ParseError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"  Found {len(polygons)} subpath(s), total {sum(len(p) for p in polygons)} vertices")

    # ---- Step 3: Offset ----
    print(f"Generating {OFFSET_MM} mm outward offset…")
    offset_polys = offset_polygons(polygons, OFFSET_MM)
    print(f"  Offset produced {len(offset_polys)} polygon(s), total {sum(len(p) for p in offset_polys)} vertices")

    if not offset_polys:
        print("ERROR: Clipper2 returned empty offset — check input geometry.", file=sys.stderr)
        sys.exit(1)

    # ---- Step 4: Append PerfCutContour ----
    print("Appending PerfCutContour to PDF…")
    append_perfcut_contour(pdf, 0, offset_polys)

    # ---- Step 5: Save ----
    print(f"Saving: {output_path}")
    pdf.save(output_path)
    pdf.close()

    # ---- Step 6: Verify ----
    print("Verifying output…")
    try:
        verify_output(output_path, original_boxes)
    except VerifyError as e:
        print(f"ERROR: verification failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("OK — output verified successfully.")
    print(f"  Output: {output_path}")


if __name__ == "__main__":
    main()
