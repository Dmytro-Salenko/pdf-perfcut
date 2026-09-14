"""
geometry/bezier.py

Adaptive cubic Bézier → polyline flattening.
Target tolerance: 0.02–0.05 mm (default 0.03 mm → ~0.085 pt).
"""

from __future__ import annotations
import math
from typing import Sequence

# 1 pt = 0.352778 mm  →  1 mm = 72/25.4 pt ≈ 2.8346 pt
MM_TO_PT: float = 72.0 / 25.4
PT_TO_MM: float = 25.4 / 72.0


def _dist_sq(ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    return dx * dx + dy * dy


def _point_on_bezier(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    mt = 1 - t
    x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
    y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
    return x, y


def _flatness_sq(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
) -> float:
    """Squared chord-distance flatness (Lembersky criterion)."""
    # Distance from control points to the chord p0→p3
    dx = p3[0] - p0[0]
    dy = p3[1] - p0[1]
    len_sq = dx * dx + dy * dy
    if len_sq < 1e-12:
        # Degenerate: all points near the same location
        d1 = _dist_sq(p0[0], p0[1], p1[0], p1[1])
        d2 = _dist_sq(p0[0], p0[1], p2[0], p2[1])
        return max(d1, d2)
    # Cross product / length for perpendicular distance
    d1 = abs(dx * (p0[1] - p1[1]) - dy * (p0[0] - p1[0])) / math.sqrt(len_sq)
    d2 = abs(dx * (p0[1] - p2[1]) - dy * (p0[0] - p2[0])) / math.sqrt(len_sq)
    return max(d1, d2) ** 2


def flatten_cubic(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    tol_sq: float,
    out: list[tuple[float, float]],
) -> None:
    """Recursively subdivide a cubic Bézier until flat enough.
    Appends intermediate points to *out*; caller must add p0 before and p3 after.
    """
    if _flatness_sq(p0, p1, p2, p3) <= tol_sq:
        return  # flat enough, nothing to add
    # De Casteljau midpoint split
    p01 = ((p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5)
    p12 = ((p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5)
    p23 = ((p2[0] + p3[0]) * 0.5, (p2[1] + p3[1]) * 0.5)
    p012 = ((p01[0] + p12[0]) * 0.5, (p01[1] + p12[1]) * 0.5)
    p123 = ((p12[0] + p23[0]) * 0.5, (p12[1] + p23[1]) * 0.5)
    pmid = ((p012[0] + p123[0]) * 0.5, (p012[1] + p123[1]) * 0.5)

    flatten_cubic(p0, p01, p012, pmid, tol_sq, out)
    out.append(pmid)
    flatten_cubic(pmid, p123, p23, p3, tol_sq, out)


def cubic_to_polyline(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    tol_mm: float = 0.03,
) -> list[tuple[float, float]]:
    """Return a polyline approximating the cubic Bézier (points in PDF points).
    p0 is NOT included (caller owns the current point); p3 IS included.
    """
    tol_pt = tol_mm * MM_TO_PT
    tol_sq = tol_pt * tol_pt
    mid_pts: list[tuple[float, float]] = []
    flatten_cubic(p0, p1, p2, p3, tol_sq, mid_pts)
    mid_pts.append(p3)
    return mid_pts
