"""
geometry/offset.py

Outward polygon offset using pyclipr (Clipper2 bindings).
Input/output in PDF points; offset distance specified in mm.
"""

from __future__ import annotations
from typing import Sequence
import numpy as np
import pyclipr
from .bezier import MM_TO_PT


def offset_polygons(
    polygons: list[list[tuple[float, float]]],
    offset_mm: float,
) -> list[list[tuple[float, float]]]:
    """
    Offset one or more closed polygons outward by *offset_mm* millimetres.
    Coordinates are in PDF points.
    Returns a list of result polygons (may be more than input count for concave shapes).
    """
    offset_pt = offset_mm * MM_TO_PT  # mm → PDF points

    pc = pyclipr.ClipperOffset()
    for poly in polygons:
        arr = np.array(poly, dtype=np.float64)
        pc.addPath(arr, pyclipr.JoinType.Round, pyclipr.EndType.Polygon)

    result = pc.execute(offset_pt)

    out: list[list[tuple[float, float]]] = []
    for ring in result:
        if hasattr(ring, 'tolist'):
            pts = [tuple(p) for p in ring.tolist()]
        else:
            pts = [tuple(p) for p in ring]
        if len(pts) >= 3:
            out.append(pts)
    return out
