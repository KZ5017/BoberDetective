from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from uuid import UUID


class OcrError(ValueError):
    pass


class OcrToolUnavailableError(OcrError):
    pass


class PdfRenderError(OcrError):
    pass


@dataclass(frozen=True)
class OcrPageResult:
    page_number: int
    text: str
    confidence: float | None
    image_path: Path


@dataclass(frozen=True)
class TesseractOcrResult:
    text: str
    confidence: float | None


@dataclass(frozen=True)
class OcrDocumentResult:
    pages: list[OcrPageResult]
    tool_name: str
    tool_version: str | None
    language: str


def ocr_pdf_document(
    pdf_path: Path,
    output_dir: Path,
    *,
    tesseract_cmd: str,
    languages: str,
    run_id: UUID,
    scale: int = 3,
) -> OcrDocumentResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    tool_version = tesseract_version(tesseract_cmd)
    image_paths = render_pdf_pages_to_images(pdf_path, output_dir, run_id=run_id, scale=scale)
    pages: list[OcrPageResult] = []
    for index, image_path in enumerate(image_paths):
        page_result = run_tesseract_with_confidence(image_path, tesseract_cmd=tesseract_cmd, languages=languages)
        pages.append(
            OcrPageResult(
                page_number=index + 1,
                text=page_result.text,
                confidence=page_result.confidence,
                image_path=image_path,
            )
        )
    return OcrDocumentResult(
        pages=pages,
        tool_name="tesseract",
        tool_version=tool_version,
        language=languages,
    )


def render_pdf_pages_to_images(pdf_path: Path, output_dir: Path, *, run_id: UUID, scale: int = 3) -> list[Path]:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise PdfRenderError("pypdfium2 is required to render PDF pages for OCR") from exc

    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        image_paths: list[Path] = []
        for page_index in range(len(pdf)):
            page = pdf[page_index]
            try:
                image = page.render(scale=scale).to_pil()
                image_path = output_dir / f"{run_id}-page-{page_index + 1:04d}.png"
                image.save(image_path)
                image_paths.append(image_path)
            finally:
                page.close()
        pdf.close()
        return image_paths
    except Exception as exc:
        raise PdfRenderError("PDF page rendering for OCR failed") from exc


def run_tesseract(image_path: Path, *, tesseract_cmd: str, languages: str) -> str:
    return run_tesseract_with_confidence(image_path, tesseract_cmd=tesseract_cmd, languages=languages).text


def run_tesseract_with_confidence(image_path: Path, *, tesseract_cmd: str, languages: str) -> TesseractOcrResult:
    command = [tesseract_cmd, str(image_path), "stdout", "-l", languages, "--psm", "6", "tsv"]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise OcrToolUnavailableError("Tesseract command is not available") from exc
    except subprocess.TimeoutExpired as exc:
        raise OcrError("Tesseract OCR timed out") from exc

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise OcrError(f"Tesseract OCR failed: {stderr[:500]}")
    return _parse_tesseract_tsv(completed.stdout)


def _parse_tesseract_tsv(tsv_output: str) -> TesseractOcrResult:
    lines = [line for line in tsv_output.splitlines() if line.strip()]
    if not lines:
        return TesseractOcrResult(text="", confidence=None)

    header = lines[0].split("\t")
    try:
        conf_index = header.index("conf")
        text_index = header.index("text")
    except ValueError as exc:
        raise OcrError("Tesseract TSV output did not contain expected columns") from exc

    words: list[str] = []
    confidences: list[float] = []
    for line in lines[1:]:
        columns = line.split("\t")
        if len(columns) <= max(conf_index, text_index):
            continue

        text = columns[text_index].strip()
        if text:
            words.append(text)

        try:
            confidence = float(columns[conf_index])
        except ValueError:
            continue
        if confidence >= 0:
            confidences.append(confidence)

    average_confidence = (sum(confidences) / len(confidences) / 100) if confidences else None
    return TesseractOcrResult(text=" ".join(words).strip(), confidence=average_confidence)


def tesseract_version(tesseract_cmd: str) -> str | None:
    try:
        completed = subprocess.run(
            [tesseract_cmd, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    first_line = completed.stdout.splitlines()[0] if completed.stdout.splitlines() else ""
    return first_line.removeprefix("tesseract ").strip() or None
