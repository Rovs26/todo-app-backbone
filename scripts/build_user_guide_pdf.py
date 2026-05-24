#!/usr/bin/env python3
"""Build the user guide PDF from the screenshot manifest."""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

from fpdf import FPDF

WORKSPACE = Path(__file__).resolve().parent.parent
MANIFEST = WORKSPACE / "user-guide-assets" / "manifest.json"
OUTPUT = WORKSPACE / "user-guide.pdf"
APP_NAME = os.environ.get("APP_NAME", "Todo App")

PAGE_W, PAGE_H = 210, 297  # A4 in mm
MARGIN = 15
CONTENT_W = PAGE_W - 2 * MARGIN


# Helvetica is a latin-1 core font in fpdf2. Map common UTF-8 punctuation
# to ASCII equivalents so generation never fails on a stray dash or curly quote.
_REPLACEMENTS = {
    "\u2014": "-",   # em dash
    "\u2013": "-",   # en dash
    "\u2018": "'",   # left single quote
    "\u2019": "'",   # right single quote
    "\u201C": '"',   # left double quote
    "\u201D": '"',   # right double quote
    "\u2026": "...", # ellipsis
    "\u00A0": " ",   # non-breaking space
}


def _safe(text: str) -> str:
    for src, dst in _REPLACEMENTS.items():
        text = text.replace(src, dst)
    # Drop anything still outside latin-1 just in case.
    return text.encode("latin-1", "replace").decode("latin-1")


class GuidePDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, _safe(f"{APP_NAME} - User Guide"), align="R")
        self.ln(10)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")


def add_cover(pdf: FPDF, app_name: str) -> None:
    pdf.add_page()
    pdf.set_y(80)
    pdf.set_font("Helvetica", "B", 28)
    pdf.cell(0, 14, _safe(app_name), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 18)
    pdf.cell(0, 10, "User Guide", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 12)
    pdf.cell(0, 8, f"Generated {date.today().isoformat()}", align="C", new_x="LMARGIN", new_y="NEXT")


def add_toc(pdf: FPDF, manifest: list[dict], page_numbers: dict[str, int]) -> None:
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "Table of Contents", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 12)
    for entry in manifest:
        page = page_numbers.get(entry["route"], "-")
        line = f"{entry['label']}  ({entry['route']})"
        dots = "." * max(2, 80 - len(line))
        pdf.cell(0, 8, _safe(f"{line}{dots}{page}"), new_x="LMARGIN", new_y="NEXT")


def add_route_section(pdf: FPDF, entry: dict) -> None:
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, _safe(entry["label"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, _safe(f"Route: {entry['route']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    for img_path in entry.get("screenshots", []):
        if not os.path.exists(img_path):
            print(f"WARNING: missing screenshot, skipping: {img_path}", file=sys.stderr)
            continue
        # Reserve space; new page if not enough room.
        if pdf.get_y() > PAGE_H - 90:
            pdf.add_page()
        pdf.image(img_path, x=MARGIN, w=CONTENT_W)
        pdf.ln(2)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(110, 110, 110)
        caption = os.path.basename(img_path).replace(".png", "").replace("-", " ").title()
        pdf.cell(0, 5, _safe(caption), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

    steps = entry.get("steps") or []
    if steps:
        if pdf.get_y() > PAGE_H - 60:
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "How to use this page", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        for i, step in enumerate(steps, 1):
            pdf.multi_cell(0, 6, _safe(f"{i}. {step}"))
            pdf.ln(1)


def build(manifest: list[dict]) -> bytes:
    pdf = GuidePDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=MARGIN)

    add_cover(pdf, APP_NAME)

    # First pass: add a placeholder TOC, then sections, recording start pages.
    page_numbers: dict[str, int] = {}
    add_toc(pdf, manifest, page_numbers)
    for entry in manifest:
        page_numbers[entry["route"]] = pdf.page_no() + 1
        add_route_section(pdf, entry)

    # Second pass: rebuild with correct page numbers in the TOC.
    pdf2 = GuidePDF(format="A4", unit="mm")
    pdf2.set_auto_page_break(auto=True, margin=MARGIN)
    add_cover(pdf2, APP_NAME)
    add_toc(pdf2, manifest, page_numbers)
    for entry in manifest:
        add_route_section(pdf2, entry)

    return bytes(pdf2.output())


def main() -> int:
    if not MANIFEST.exists():
        print(f"ERROR: manifest not found at {MANIFEST}", file=sys.stderr)
        return 1
    manifest = json.loads(MANIFEST.read_text())
    if not manifest:
        print("ERROR: manifest is empty", file=sys.stderr)
        return 1

    pdf_bytes = build(manifest)
    OUTPUT.write_bytes(pdf_bytes)

    if not OUTPUT.exists() or OUTPUT.stat().st_size == 0:
        print(f"ERROR: PDF missing or empty at {OUTPUT}", file=sys.stderr)
        return 2

    print(str(OUTPUT.resolve()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
