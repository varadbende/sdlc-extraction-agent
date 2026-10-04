"""
REQ-3: Deterministic PDF text extraction.
Converts a supplier TDS PDF into plain text for the extraction agent to read.
No LLM call here — this is pure text extraction (ADR-0008: whole-document
context, not RAG chunking, since a TDS is short enough to pass in full).
"""

import sys
import pdfplumber


def extract_text(pdf_path: str) -> str:
    """Returns the full text of a PDF, pages joined with a page-break marker."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append(f"--- Page {i} ---\n{text}")
    return "\n\n".join(pages)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python pdf_reader.py <path_to_pdf>")
        sys.exit(1)

    path = sys.argv[1]
    full_text = extract_text(path)
    print(full_text)
    print(f"\n\n[Extracted {len(full_text)} characters from {path}]")