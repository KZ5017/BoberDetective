# PDF Test Samples

This directory contains generated local-only PDF samples for parser/OCR hardening.

Regenerate them from the repository root:

```bash
.venv/bin/python scripts/generate_pdf_samples.py
```

Expected generated files:

- `pdf/native_text_hu.pdf`: native-text PDF for parser checks.
- `pdf/scanned_text_hu.pdf`: image-only PDF with readable Hungarian-like text for OCR checks.
- `pdf/weak_scanned_text_hu.pdf`: degraded image-only PDF for OCR quality warning checks.
- `pdf/mixed_empty_page_hu.pdf`: native-text PDF with one empty page for `review_required` parsing checks.

These are synthetic samples, not evidence and not source truth for the product domain.

Evaluate parser/OCR behavior on the generated files:

```bash
.venv/bin/python scripts/evaluate_pdf_samples.py
```
