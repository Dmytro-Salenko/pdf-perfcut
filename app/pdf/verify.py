"""
pdf/verify.py

Post-write verification: reopen the output PDF and confirm:
- CutContour Separation colorspace exists.
- PerfCutContour Separation colorspace exists.
- Page boxes are unchanged.
"""

from __future__ import annotations
import pikepdf
from typing import Optional


class VerifyError(Exception):
    pass


def _spot_names_on_page(page: pikepdf.Page) -> set[str]:
    res = page.obj.get("/Resources") or {}
    cs_dict = res.get("/ColorSpace") if res else None
    if not cs_dict:
        return set()
    names = set()
    for key in cs_dict.keys():
        entry = cs_dict[key]
        if isinstance(entry, pikepdf.Array) and len(entry) >= 2:
            if str(entry[0]) == "/Separation":
                names.add(str(entry[1]).lstrip("/"))
    return names


def verify_output(
    output_path: str,
    original_boxes: Optional[dict] = None,
) -> None:
    """
    Reopen *output_path* and verify structural integrity.
    Raises VerifyError with a descriptive message on failure.
    """
    try:
        pdf = pikepdf.open(output_path)
    except Exception as e:
        raise VerifyError(f"Could not reopen output PDF: {e}")

    page = pdf.pages[0]
    spot_names = _spot_names_on_page(page)

    if "CutContour" not in spot_names:
        raise VerifyError("CutContour spot color is missing from the output PDF.")
    if "PerfCutContour" not in spot_names:
        raise VerifyError("PerfCutContour spot color was not written to the output PDF.")

    if original_boxes:
        def box_str(b) -> str:
            return str(b) if b is not None else "none"

        for box_name, orig_val in original_boxes.items():
            cur_val = page.obj.get(f"/{box_name}")
            if box_str(orig_val) != box_str(cur_val):
                raise VerifyError(
                    f"Page box {box_name} changed: was {orig_val}, now {cur_val}"
                )

    pdf.close()


def collect_page_boxes(page: pikepdf.Page) -> dict:
    boxes = {}
    for name in ("MediaBox", "BleedBox", "TrimBox", "ArtBox", "CropBox"):
        v = page.obj.get(f"/{name}")
        boxes[name] = v
    return boxes
