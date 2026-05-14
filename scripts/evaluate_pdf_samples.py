from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.services.documents import _ocr_quality_issues
from app.services.ocr import ocr_pdf_document
from app.services.pdf_parsers import PdfParsingError, parse_pdf


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "samples" / "pdf"
OUTPUT_DIR = ROOT / ".run_logs" / "sample_ocr"


def main() -> None:
    if not SAMPLE_DIR.exists():
        raise SystemExit("No samples found. Run scripts/generate_pdf_samples.py first.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for pdf_path in sorted(SAMPLE_DIR.glob("*.pdf")):
        print(f"\n== {pdf_path.name} ==")
        evaluate_native_parse(pdf_path)
        evaluate_ocr(pdf_path)


def evaluate_native_parse(pdf_path: Path) -> None:
    try:
        result = parse_pdf(pdf_path.read_bytes(), "pypdf")
    except PdfParsingError as exc:
        print(f"native_parse: failed ({exc})")
        return

    page_lengths = [len(page.text) for page in result.pages]
    print(f"native_parse: ok parser={result.parser_name} pages={len(result.pages)} chars={sum(page_lengths)} page_chars={page_lengths}")


def evaluate_ocr(pdf_path: Path) -> None:
    try:
        result = ocr_pdf_document(
            pdf_path,
            OUTPUT_DIR / pdf_path.stem,
            tesseract_cmd="tesseract",
            languages="hun+eng",
            run_id=uuid4(),
        )
    except Exception as exc:
        print(f"ocr: failed ({exc})")
        return

    confidences = [page.confidence for page in result.pages]
    page_lengths = [len(page.text) for page in result.pages]
    issues = _ocr_quality_issues(result)
    print(f"ocr: ok pages={len(result.pages)} chars={sum(page_lengths)} page_chars={page_lengths} confidence={confidences}")
    print(f"ocr_issues: {issues}")


if __name__ == "__main__":
    main()
