#!/usr/bin/env python3
"""
add_contour.py — CLI

Usage:
    python add_contour.py input.pdf output.pdf
"""

from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.core import process_pdf, OFFSET_MM
from app.pdf.parser import ParseError
from app.pdf.verify import VerifyError


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python add_contour.py input.pdf output.pdf", file=sys.stderr)
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]

    if not os.path.isfile(input_path):
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Opening:  {input_path}")
    print(f"Offset:   {OFFSET_MM} mm outward")

    try:
        process_pdf(input_path, output_path)
    except ParseError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except VerifyError as e:
        print(f"ERROR: verification failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Output:   {output_path}")
    print("OK.")


if __name__ == "__main__":
    main()
