#!/usr/bin/env python3
"""
Create minimal synthetic PDF fixtures for testing.

Produces two files:
  tests/fixtures/input_cutcontour.pdf
    - 48x50 mm content, 3mm bleed on all sides → 54x56 mm page
    - CutContour Separation spot color (stroked rectangle)
    - ExtGState with OPM:1 (matches real-world structure)
    - No customer artwork

  tests/fixtures/no_cutcontour.pdf
    - Blank page, no spot colors
"""

import pikepdf
from pikepdf import Pdf, Page, Dictionary, Array, Name, Stream
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
os.makedirs(OUT_DIR, exist_ok=True)

MM = 72.0 / 25.4  # pt per mm

# ---------- input_cutcontour.pdf ----------
# Content area: 48x50 mm (TrimBox)
# Bleed: 3 mm → MediaBox/BleedBox: 54x56 mm
TRIM_W, TRIM_H = 48 * MM, 50 * MM
BLEED = 3 * MM
PAGE_W, PAGE_H = TRIM_W + 2 * BLEED, TRIM_H + 2 * BLEED

# CutContour path: rectangle following the TrimBox edges (in page units)
# TrimBox origin at (BLEED, BLEED)
X0, Y0 = BLEED, BLEED
X1, Y1 = BLEED + TRIM_W, BLEED + TRIM_H

# Round-cornered rectangle approximated as straight rect for simplicity
cut_path = (
    f"{X0:.4f} {Y0:.4f} m\n"
    f"{X1:.4f} {Y0:.4f} l\n"
    f"{X1:.4f} {Y1:.4f} l\n"
    f"{X0:.4f} {Y1:.4f} l\n"
    f"h\n"
)

tint_fn = Dictionary(
    FunctionType=2,
    Domain=Array([0, 1]),
    C0=Array([0.0, 0.0, 0.0, 0.0]),
    C1=Array([0.0, 1.0, 0.0, 0.0]),   # CutContour preview: 100M
    N=1.0,
    Range=Array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]),
)
cut_cs = Array([Name("/Separation"), Name("/CutContour"), Name("/DeviceCMYK"), tint_fn])

content_str = (
    "q\n"
    "/GS1 gs\n"
    "/CS0 CS\n"
    "1 SCN\n"
    "0.472 w\n"
    f"{cut_path}"
    "S\n"
    "Q\n"
)

pdf = Pdf.new()
page_obj = Dictionary(
    Type=Name("/Page"),
    MediaBox=Array([0, 0, PAGE_W, PAGE_H]),
    BleedBox=Array([0, 0, PAGE_W, PAGE_H]),
    TrimBox=Array([BLEED, BLEED, BLEED + TRIM_W, BLEED + TRIM_H]),
    Resources=Dictionary(
        ColorSpace=Dictionary(CS0=cut_cs),
        ExtGState=Dictionary(
            GS1=Dictionary(
                Type=Name("/ExtGState"),
                SA=True,
                OPM=1,
            )
        ),
    ),
    Contents=Stream(pdf, content_str.encode("latin-1")),
)
pdf.make_indirect(page_obj)
pdf.pages.append(Page(page_obj))
out_path = os.path.join(OUT_DIR, "input_cutcontour.pdf")
pdf.save(out_path)
print(f"Written: {out_path}")

# ---------- no_cutcontour.pdf ----------
pdf2 = Pdf.new()
page2 = Dictionary(
    Type=Name("/Page"),
    MediaBox=Array([0, 0, 200, 200]),
    Resources=Dictionary(),
    Contents=Stream(pdf2, b""),
)
pdf2.make_indirect(page2)
pdf2.pages.append(Page(page2))
out2 = os.path.join(OUT_DIR, "no_cutcontour.pdf")
pdf2.save(out2)
print(f"Written: {out2}")
print("Done.")
