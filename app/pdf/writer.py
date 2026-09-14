"""
pdf/writer.py

Append a PerfCutContour spot-color stroke to an existing PDF page.

Strategy:
- Add a new Separation colorspace resource for PerfCutContour.
- Build a content-stream fragment that:
    1. Saves graphics state (q)
    2. Sets the stroke color to PerfCutContour at 100%
    3. Sets stroke width to match typical prepress hairline (0.25 pt)
    4. Draws each offset polygon as a closed path and strokes it
    5. Restores graphics state (Q)
- Append this stream to the page's content array (or wrap in a Form XObject
  to keep it self-contained and avoid interfering with existing clipping paths).

We wrap the new content in its own content stream appended *after* the existing
content, so the original PDF data is never modified.
"""

from __future__ import annotations
import pikepdf
from pikepdf import Name, Array, Dictionary, Stream, Pdf


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PERF_CUT_NAME = "PerfCutContour"

# Alternate CMYK: C1=[1,0,1,0] → 100C/0M/100Y/0K (green preview)
def _make_separation_cs(pdf: Pdf, ink_name: str, c: float, m: float, y: float, k: float) -> pikepdf.Array:
    """
    Build a Separation colorspace array with a linear DeviceCMYK alternate.
    C0 = 0,0,0,0 (paper white at tint=0)
    C1 = c,m,y,k (full ink at tint=1)
    """
    tint_fn = Dictionary(
        FunctionType=2,
        Domain=Array([0, 1]),
        C0=Array([0.0, 0.0, 0.0, 0.0]),
        C1=Array([c, m, y, k]),
        N=1.0,
        Range=Array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]),
    )
    return Array([Name("/Separation"), Name(f"/{ink_name}"), Name("/DeviceCMYK"), tint_fn])


def _fmt(v: float) -> str:
    """Format a float for PDF content streams — trim trailing zeros."""
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _polygon_to_pdf_path(polygon: list[tuple[float, float]]) -> str:
    """Emit PDF path operators for a closed polygon (no CTM; coords are absolute)."""
    if len(polygon) < 2:
        return ""
    ops = []
    first = polygon[0]
    ops.append(f"{_fmt(first[0])} {_fmt(first[1])} m")
    for x, y in polygon[1:]:
        ops.append(f"{_fmt(x)} {_fmt(y)} l")
    ops.append("h")
    return "\n".join(ops)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def append_perfcut_contour(
    pdf: Pdf,
    page_index: int,
    polygons: list[list[tuple[float, float]]],
    stroke_width_pt: float = 0.25,
) -> None:
    """
    Append PerfCutContour paths to the given page.

    *polygons* must be in absolute page-space PDF points (CTM already applied).
    We reset the CTM to identity (using the cm operator) so we can draw
    at absolute coordinates regardless of whatever transforms are in effect.
    """
    page = pdf.pages[page_index]
    res = page.obj["/Resources"]

    # ---- 1. Register colorspace resource ----
    cs_array = _make_separation_cs(pdf, PERF_CUT_NAME, 1.0, 0.0, 1.0, 0.0)
    if "/ColorSpace" not in res:
        res["/ColorSpace"] = Dictionary()
    cs_dict = res["/ColorSpace"]

    # Find a free CS name
    used = {str(k) for k in cs_dict.keys()}
    cs_key = "/CS_PCC"
    i = 0
    while cs_key in used:
        cs_key = f"/CS_PCC{i}"
        i += 1
    cs_dict[cs_key] = cs_array

    # ---- 2. Build content stream ----
    path_parts = [_polygon_to_pdf_path(poly) for poly in polygons if len(poly) >= 3]
    if not path_parts:
        return

    # We draw at absolute page coordinates by resetting to identity CTM.
    # Wrap in q/Q so we don't leak graphics state into existing content.
    stream_lines = [
        "q",                          # save graphics state
        "1 0 0 1 0 0 cm",            # reset CTM to identity (absolute coords)
        f"{cs_key} CS",               # set stroke colorspace
        "1 SCN",                      # tint = 1.0 (full ink)
        f"{_fmt(stroke_width_pt)} w", # stroke width
        "1 J",                        # round line caps
        "1 j",                        # round line joins
    ]
    for path_data in path_parts:
        stream_lines.append(path_data)
        stream_lines.append("S")      # stroke

    stream_lines.append("Q")         # restore graphics state

    stream_data = "\n".join(stream_lines).encode("latin-1")
    new_stream = Stream(pdf, stream_data)

    # ---- 3. Append to page Contents ----
    contents = page.obj.get("/Contents")
    if contents is None:
        page.obj["/Contents"] = new_stream
    elif isinstance(contents, pikepdf.Array):
        contents.append(new_stream)
    else:
        # Single stream ref → convert to array
        page.obj["/Contents"] = Array([contents, new_stream])
