"""
pdf/parser.py

Extract CutContour vector paths from a PDF page.

Strategy:
  1. Walk the page content stream tracking the current transformation matrix (CTM).
  2. Identify the Separation colorspace named "CutContour" in page Resources.
  3. Collect all path construction operators executed while that colorspace is active
     for a stroke (S/s/B/b) operation.
  4. Apply the CTM to produce absolute page-space coordinates.
  5. Flatten Bézier curves to polylines with the requested geometric tolerance.

Returns a list of "subpaths", each being a closed polygon in PDF point coords.
"""

from __future__ import annotations
import math
from typing import Optional
import pikepdf
from ..geometry.bezier import cubic_to_polyline


class ParseError(Exception):
    pass


# ---------------------------------------------------------------------------
# Matrix helpers
# ---------------------------------------------------------------------------

def _concat(a: list[float], b: list[float]) -> list[float]:
    """PDF matrix multiply: result = a × b (column-major)."""
    a0, a1, a2, a3, a4, a5 = a
    b0, b1, b2, b3, b4, b5 = b
    return [
        a0 * b0 + a1 * b2,
        a0 * b1 + a1 * b3,
        a2 * b0 + a3 * b2,
        a2 * b1 + a3 * b3,
        a4 * b0 + a5 * b2 + b4,
        a4 * b1 + a5 * b3 + b5,
    ]


def _apply_ctm(ctm: list[float], x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = ctm
    return a * x + c * y + e, b * x + d * y + f


# ---------------------------------------------------------------------------
# Spot-color name discovery
# ---------------------------------------------------------------------------

def _find_cutcontour_cs_name(page: pikepdf.Page) -> Optional[str]:
    """Return the resource name (e.g. '/CS0') of the CutContour Separation color."""
    res = page.obj.get("/Resources") or page.Resources
    cs_dict = res.get("/ColorSpace")
    if cs_dict is None:
        return None
    for key in cs_dict.keys():
        entry = cs_dict[key]
        # entry should be [/Separation, name, altCS, tintTransform]
        if not isinstance(entry, pikepdf.Array) or len(entry) < 2:
            continue
        if str(entry[0]) == "/Separation" and str(entry[1]) == "/CutContour":
            return str(key)
    return None


# ---------------------------------------------------------------------------
# Path extraction
# ---------------------------------------------------------------------------

def extract_cutcontour_paths(
    page: pikepdf.Page,
    tol_mm: float = 0.03,
) -> list[list[tuple[float, float]]]:
    """
    Return a list of closed polygons (in absolute PDF-point coordinates)
    representing all stroked CutContour paths on the page.

    Raises ParseError if CutContour is not found or path is open.
    """
    cs_name = _find_cutcontour_cs_name(page)
    if cs_name is None:
        raise ParseError("CutContour spot color not found in page Resources.")

    content_ops = list(pikepdf.parse_content_stream(page))

    ctm_stack: list[list[float]] = [[1, 0, 0, 1, 0, 0]]
    current_cs_stroke: Optional[str] = None  # current stroke colorspace resource name
    path_buffer: list[tuple[str, list[float]]] = []  # (opname, args)
    current_pt: Optional[tuple[float, float]] = None  # current path point in user space
    subpath_start: Optional[tuple[float, float]] = None

    result_polygons: list[list[tuple[float, float]]] = []

    def flush_path_as_polygon() -> None:
        """Convert accumulated path ops to absolute polygon(s)."""
        nonlocal current_pt, subpath_start
        if not path_buffer:
            return

        ctm = ctm_stack[-1]
        subpaths: list[list[tuple[float, float]]] = []
        current_subpath: list[tuple[float, float]] = []
        cp: tuple[float, float] = (0.0, 0.0)
        sp: tuple[float, float] = (0.0, 0.0)

        for op, args in path_buffer:
            if op == "m":
                if current_subpath:
                    subpaths.append(current_subpath)
                p = _apply_ctm(ctm, args[0], args[1])
                current_subpath = [p]
                cp = (args[0], args[1])
                sp = cp
            elif op == "l":
                p = _apply_ctm(ctm, args[0], args[1])
                current_subpath.append(p)
                cp = (args[0], args[1])
            elif op == "c":
                # c x1 y1 x2 y2 x3 y3
                p0u = cp
                p1u = (args[0], args[1])
                p2u = (args[2], args[3])
                p3u = (args[4], args[5])
                # flatten in user space, then transform
                pts_u = cubic_to_polyline(p0u, p1u, p2u, p3u, tol_mm)
                for pu in pts_u:
                    current_subpath.append(_apply_ctm(ctm, pu[0], pu[1]))
                cp = p3u
            elif op == "v":
                # v x2 y2 x3 y3 — p1 = current point
                p0u = cp
                p1u = cp  # implicit
                p2u = (args[0], args[1])
                p3u = (args[2], args[3])
                pts_u = cubic_to_polyline(p0u, p1u, p2u, p3u, tol_mm)
                for pu in pts_u:
                    current_subpath.append(_apply_ctm(ctm, pu[0], pu[1]))
                cp = p3u
            elif op == "y":
                # y x1 y1 x3 y3 — p2 = p3
                p0u = cp
                p1u = (args[0], args[1])
                p3u = (args[2], args[3])
                p2u = p3u  # implicit
                pts_u = cubic_to_polyline(p0u, p1u, p2u, p3u, tol_mm)
                for pu in pts_u:
                    current_subpath.append(_apply_ctm(ctm, pu[0], pu[1]))
                cp = p3u
            elif op == "h":
                # close subpath
                if current_subpath:
                    current_subpath.append(current_subpath[0])  # close
                    subpaths.append(current_subpath)
                    current_subpath = []
                cp = sp
            elif op == "re":
                # rectangle: x y w h
                x, y, w, h = args[0], args[1], args[2], args[3]
                corners = [
                    _apply_ctm(ctm, x, y),
                    _apply_ctm(ctm, x + w, y),
                    _apply_ctm(ctm, x + w, y + h),
                    _apply_ctm(ctm, x, y + h),
                    _apply_ctm(ctm, x, y),
                ]
                subpaths.append(corners)
                cp = (x, y)
                sp = cp

        if current_subpath:
            subpaths.append(current_subpath)

        for sp_pts in subpaths:
            if len(sp_pts) < 3:
                continue
            # Verify closed (first ≈ last)
            first, last = sp_pts[0], sp_pts[-1]
            if abs(first[0] - last[0]) > 0.1 or abs(first[1] - last[1]) > 0.1:
                raise ParseError(
                    "CutContour contains an open (unclosed) subpath — cannot offset safely."
                )
            # Remove duplicate closing point for offset input
            pts = sp_pts[:-1] if (
                abs(sp_pts[0][0] - sp_pts[-1][0]) < 1e-6 and
                abs(sp_pts[0][1] - sp_pts[-1][1]) < 1e-6
            ) else sp_pts
            if len(pts) >= 3:
                result_polygons.append(pts)

        path_buffer.clear()

    for operands, op in content_ops:
        opname = str(op)

        if opname == "q":
            ctm_stack.append(ctm_stack[-1][:])
        elif opname == "Q":
            if len(ctm_stack) > 1:
                ctm_stack.pop()
        elif opname == "cm":
            args = [float(str(o)) for o in operands]
            ctm_stack[-1] = _concat(ctm_stack[-1], args)
        elif opname == "CS":
            current_cs_stroke = str(operands[0])
        elif opname == "cs":
            pass  # fill colorspace — we only care about stroke
        elif opname in ("m", "l", "c", "v", "y", "h", "re"):
            args = [float(str(o)) for o in operands]
            path_buffer.append((opname, args))
        elif opname in ("S", "s", "B", "b", "B*", "b*"):
            # stroke operation
            if current_cs_stroke == cs_name:
                flush_path_as_polygon()
            else:
                path_buffer.clear()
        elif opname in ("f", "F", "f*", "n", "W", "W*"):
            # fill or clip — clear without extracting
            path_buffer.clear()

    if not result_polygons:
        raise ParseError("CutContour spot color found but no stroked paths were extracted.")

    return result_polygons
