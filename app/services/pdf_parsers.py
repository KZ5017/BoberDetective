from __future__ import annotations

from dataclasses import dataclass
import io
from importlib import metadata
from typing import Protocol


class PdfParsingError(ValueError):
    pass


class PdfParserUnavailableError(PdfParsingError):
    pass


class NoExtractedTextError(PdfParsingError):
    pass


@dataclass(frozen=True)
class ParsedPdfPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class PdfParseResult:
    pages: list[ParsedPdfPage]
    parser_name: str
    parser_version: str | None
    parser_profile: str


class PdfParser(Protocol):
    name: str
    version: str | None

    def parse(self, content: bytes) -> PdfParseResult:
        pass


class PypdfNativePdfParser:
    name = "pypdf"

    @property
    def version(self) -> str | None:
        return _package_version("pypdf")

    def parse(self, content: bytes) -> PdfParseResult:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise PdfParserUnavailableError("pypdf is required for fallback native PDF parsing") from exc

        try:
            reader = PdfReader(io.BytesIO(content))
            if getattr(reader, "is_encrypted", False):
                raise PdfParsingError("Encrypted PDF documents are not supported yet")

            pages = [
                ParsedPdfPage(page_number=index + 1, text=(page.extract_text() or "").strip())
                for index, page in enumerate(reader.pages)
            ]
        except PdfParsingError:
            raise
        except Exception as exc:
            raise PdfParsingError("pypdf native text extraction failed") from exc

        _ensure_pages_have_text(pages)
        return PdfParseResult(
            pages=pages,
            parser_name=self.name,
            parser_version=self.version,
            parser_profile="pypdf_native_v1",
        )


class DoclingNativePdfParser:
    name = "docling"

    @property
    def version(self) -> str | None:
        return _package_version("docling")

    def parse(self, content: bytes) -> PdfParseResult:
        try:
            from docling.datamodel.base_models import DocumentStream, InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter
            from docling.document_converter import PdfFormatOption
        except ImportError as exc:
            raise PdfParserUnavailableError("docling is required for the primary PDF parser profile") from exc

        try:
            stream = DocumentStream(name="document.pdf", stream=io.BytesIO(content))
            pipeline_options = PdfPipelineOptions(
                do_ocr=False,
                do_table_structure=False,
                enable_remote_services=False,
            )
            converter = DocumentConverter(
                allowed_formats=[InputFormat.PDF],
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
                },
            )
            result = converter.convert(stream)
            document = result.document
            page_numbers = _docling_page_numbers(document)
            pages = [
                ParsedPdfPage(
                    page_number=page_number,
                    text=document.export_to_text(page_no=page_number, traverse_pictures=True).strip(),
                )
                for page_number in page_numbers
            ]
        except Exception as exc:
            raise PdfParsingError("Docling native PDF text extraction failed") from exc

        _ensure_pages_have_text(pages)
        return PdfParseResult(
            pages=pages,
            parser_name=self.name,
            parser_version=self.version,
            parser_profile="docling_native_v1",
        )


def parse_pdf(content: bytes, parser_profile: str) -> PdfParseResult:
    profile = parser_profile.strip().casefold()
    if profile == "pypdf":
        return PypdfNativePdfParser().parse(content)
    if profile == "docling":
        return DoclingNativePdfParser().parse(content)
    if profile in {"docling_then_pypdf", "auto"}:
        try:
            return DoclingNativePdfParser().parse(content)
        except PdfParsingError:
            return PypdfNativePdfParser().parse(content)
    raise PdfParsingError("Unsupported PDF parser profile")


def _docling_page_numbers(document: object) -> list[int]:
    pages = getattr(document, "pages", None)
    if isinstance(pages, dict) and pages:
        return sorted(int(page_number) for page_number in pages)
    return [1]


def _ensure_pages_have_text(pages: list[ParsedPdfPage]) -> None:
    if not pages:
        raise NoExtractedTextError("PDF has no readable pages")
    if sum(len(page.text) for page in pages) == 0:
        raise NoExtractedTextError("PDF native text extraction produced no text")


def _package_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None
