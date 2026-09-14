"""
tests/test_pipeline.py

Regression tests against the supplied reference PDFs.
"""

from __future__ import annotations
import os
import sys
import math
import tempfile
import pytest
import pikepdf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.pdf.parser import extract_cutcontour_paths, ParseError
from app.pdf.writer import append_perfcut_contour
from app.pdf.verify import verify_output, collect_page_boxes, VerifyError
from app.geometry.offset import offset_polygons

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
INPUT_PDF = os.path.join(FIXTURES_DIR, "Notion_Sticker4_FC_48x50_upd.pdf")
REF_PDF = os.path.join(FIXTURES_DIR, "Notion_Sticker4_FC_48x50.pdf")

PT_TO_MM = 25.4 / 72.0
OFFSET_MM = 2.5


@pytest.fixture(scope="module")
def processed_pdf_path():
    """Run the full pipeline and return path to the output PDF."""
    pdf = pikepdf.open(INPUT_PDF)
    page = pdf.pages[0]
    original_boxes = collect_page_boxes(page)
    polys = extract_cutcontour_paths(page)
    offset_polys = offset_polygons(polys, OFFSET_MM)
    append_perfcut_contour(pdf, 0, offset_polys)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        tmp_path = f.name
    pdf.save(tmp_path)
    pdf.close()
    yield tmp_path
    os.unlink(tmp_path)


def _spot_names(page: pikepdf.Page) -> set[str]:
    res = page.obj.get("/Resources") or {}
    cs = res.get("/ColorSpace") if res else None
    if not cs:
        return set()
    names = set()
    for k in cs.keys():
        e = cs[k]
        if isinstance(e, pikepdf.Array) and len(e) >= 2 and str(e[0]) == "/Separation":
            names.add(str(e[1]).lstrip("/"))
    return names


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_input_has_cutcontour():
    pdf = pikepdf.open(INPUT_PDF)
    names = _spot_names(pdf.pages[0])
    pdf.close()
    assert "CutContour" in names, "Input PDF must have CutContour spot color"


def test_extract_returns_polygons():
    pdf = pikepdf.open(INPUT_PDF)
    polys = extract_cutcontour_paths(pdf.pages[0])
    pdf.close()
    assert len(polys) >= 1
    assert all(len(p) >= 3 for p in polys)


def test_cutcontour_bbox_matches_expected():
    """CutContour should be exactly 48x50 mm (TrimBox size)."""
    pdf = pikepdf.open(INPUT_PDF)
    polys = extract_cutcontour_paths(pdf.pages[0])
    pdf.close()
    xs = [p[0] for poly in polys for p in poly]
    ys = [p[1] for poly in polys for p in poly]
    w_mm = (max(xs) - min(xs)) * PT_TO_MM
    h_mm = (max(ys) - min(ys)) * PT_TO_MM
    assert abs(w_mm - 48.0) < 0.5, f"Width should be ~48 mm, got {w_mm:.3f}"
    assert abs(h_mm - 50.0) < 0.5, f"Height should be ~50 mm, got {h_mm:.3f}"


def test_offset_distance_is_2_5mm():
    pdf = pikepdf.open(INPUT_PDF)
    polys = extract_cutcontour_paths(pdf.pages[0])
    pdf.close()
    offset_polys = offset_polygons(polys, OFFSET_MM)

    xs_in = [p[0] for poly in polys for p in poly]
    ys_in = [p[1] for poly in polys for p in poly]
    xs_out = [p[0] for poly in offset_polys for p in poly]
    ys_out = [p[1] for poly in offset_polys for p in poly]

    expand_left  = (min(xs_in) - min(xs_out)) * PT_TO_MM
    expand_right = (max(xs_out) - max(xs_in)) * PT_TO_MM
    expand_down  = (min(ys_in) - min(ys_out)) * PT_TO_MM
    expand_up    = (max(ys_out) - max(ys_in)) * PT_TO_MM

    tol = 0.05  # 0.05 mm tolerance
    for label, val in [("left", expand_left), ("right", expand_right),
                       ("down", expand_down), ("up", expand_up)]:
        assert abs(val - OFFSET_MM) < tol, f"Offset {label}: expected {OFFSET_MM} mm, got {val:.4f} mm"


def test_output_has_both_spot_colors(processed_pdf_path):
    pdf = pikepdf.open(processed_pdf_path)
    names = _spot_names(pdf.pages[0])
    pdf.close()
    assert "CutContour" in names, "CutContour must remain in output"
    assert "PerfCutContour" in names, "PerfCutContour must be added to output"


def test_perfcutcontour_is_separation(processed_pdf_path):
    pdf = pikepdf.open(processed_pdf_path)
    page = pdf.pages[0]
    res = page.obj["/Resources"]
    cs_dict = res["/ColorSpace"]
    found = False
    for k in cs_dict.keys():
        e = cs_dict[k]
        if isinstance(e, pikepdf.Array) and len(e) >= 2:
            if str(e[0]) == "/Separation" and str(e[1]) == "/PerfCutContour":
                found = True
                # Check alternate colorspace is DeviceCMYK
                assert str(e[2]) == "/DeviceCMYK"
                # Check C1 preview is [1,0,1,0] (100C/0M/100Y/0K)
                fn = e[3]
                c1 = fn["/C1"]
                assert abs(float(str(c1[0])) - 1.0) < 0.01, "C(cyan) should be 1.0"
                assert abs(float(str(c1[1])) - 0.0) < 0.01, "M should be 0.0"
                assert abs(float(str(c1[2])) - 1.0) < 0.01, "Y should be 1.0"
                assert abs(float(str(c1[3])) - 0.0) < 0.01, "K should be 0.0"
    pdf.close()
    assert found, "PerfCutContour Separation not found in output"


def test_page_boxes_unchanged(processed_pdf_path):
    pdf_in = pikepdf.open(INPUT_PDF)
    orig_boxes = collect_page_boxes(pdf_in.pages[0])
    pdf_in.close()

    pdf_out = pikepdf.open(processed_pdf_path)
    out_boxes = collect_page_boxes(pdf_out.pages[0])
    pdf_out.close()

    for name in ("MediaBox", "TrimBox", "BleedBox"):
        if orig_boxes.get(name) is not None:
            assert str(orig_boxes[name]) == str(out_boxes[name]), \
                f"{name} changed: {orig_boxes[name]} → {out_boxes[name]}"


def test_output_can_be_reopened(processed_pdf_path):
    pdf = pikepdf.open(processed_pdf_path)
    assert len(pdf.pages) == 1
    pdf.close()


def test_verify_passes(processed_pdf_path):
    # Should not raise
    verify_output(processed_pdf_path)


def test_verify_fails_on_missing_perfcut():
    """Verification must catch a PDF without PerfCutContour."""
    with pytest.raises(VerifyError, match="PerfCutContour"):
        verify_output(INPUT_PDF)


def test_no_cutcontour_raises_parseerror():
    """A PDF without CutContour must raise ParseError."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        tmp = f.name
    try:
        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=(100, 100))
        pdf.save(tmp)
        pdf.close()
        pdf2 = pikepdf.open(tmp)
        with pytest.raises(ParseError, match="CutContour"):
            extract_cutcontour_paths(pdf2.pages[0])
        pdf2.close()
    finally:
        os.unlink(tmp)


def test_perfcutcontour_has_stroke_overprint(processed_pdf_path):
    """PerfCutContour content stream must apply an ExtGState with /OP true."""
    pdf = pikepdf.open(processed_pdf_path)
    page = pdf.pages[0]
    res = page.obj["/Resources"]

    # 1. Find the CS resource name for PerfCutContour
    cs_dict = res["/ColorSpace"]
    pcc_cs_key = None
    for k in cs_dict.keys():
        e = cs_dict[k]
        if isinstance(e, pikepdf.Array) and len(e) >= 2:
            if str(e[0]) == "/Separation" and str(e[1]) == "/PerfCutContour":
                pcc_cs_key = str(k)
                break
    assert pcc_cs_key is not None, "PerfCutContour colorspace not found"

    # 2. Find the ExtGState with /OP true
    egs_dict = res.get("/ExtGState")
    assert egs_dict is not None, "No ExtGState in page resources"
    op_gs_key = None
    for k in egs_dict.keys():
        entry = egs_dict[k]
        if entry.get("/OP") == True:  # noqa: E712
            op_gs_key = str(k)
            break
    assert op_gs_key is not None, "No ExtGState with /OP true found in resources"

    # 3. Verify the content stream applies that gs before stroking PerfCutContour
    content_ops = list(pikepdf.parse_content_stream(page))
    current_cs = None
    current_gs_applied = False
    gs_before_pcc_stroke = False

    for operands, op in content_ops:
        opname = str(op)
        if opname == "gs":
            applied = str(operands[0])
            if applied == op_gs_key:
                current_gs_applied = True
        elif opname == "CS":
            current_cs = str(operands[0])
            if current_cs != pcc_cs_key:
                current_gs_applied = False  # reset on different CS
        elif opname in ("S", "s", "B", "b") and current_cs == pcc_cs_key:
            if current_gs_applied:
                gs_before_pcc_stroke = True
        elif opname == "Q":
            current_gs_applied = False
            current_cs = None

    pdf.close()
    assert gs_before_pcc_stroke, (
        f"PerfCutContour stroke was not preceded by ExtGState {op_gs_key} "
        f"(with /OP true) in the content stream"
    )

