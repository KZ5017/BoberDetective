from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "samples" / "pdf"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = {
        "native_text_hu.pdf": native_text_pdf(
            [
                "Jegyzokonyv minta: a tanut 2026. majus 13-an hallgattak meg.",
                "A mellekletkent hivatkozott kamera felvetel atadasa ellenorzesre var.",
            ]
        ),
        "scanned_text_hu.pdf": image_only_pdf(
            "Jegyzokonyv minta\nA kamera felvetel mellekletkent hivatkozott.\nOCR teszt 2026.",
            quality="good",
        ),
        "weak_scanned_text_hu.pdf": image_only_pdf(
            "Gyenge minosegu scan\nA szoveg nehezebben olvashato.\nOCR figyelmeztetes teszt.",
            quality="weak",
        ),
        "mixed_empty_page_hu.pdf": native_text_pdf(
            [
                "Elso oldal: van nativ PDF szoveg.",
                "",
            ]
        ),
    }
    for filename, content in samples.items():
        (OUTPUT_DIR / filename).write_bytes(content)
    print(f"Generated {len(samples)} PDF samples in {OUTPUT_DIR}")


def native_text_pdf(page_texts: list[str]) -> bytes:
    kids = " ".join(f"{4 + index * 2} 0 R" for index in range(len(page_texts))).encode()
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [" + kids + b"] /Count " + str(len(page_texts)).encode() + b" >> endobj\n",
        b"3 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]

    for index, text in enumerate(page_texts):
        page_object_number = 4 + index * 2
        content_object_number = page_object_number + 1
        escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content = f"BT /F1 18 Tf 72 720 Td ({escaped_text}) Tj ET".encode()
        objects.append(
            f"{page_object_number} 0 obj ".encode()
            + b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            + b"/Resources << /Font << /F1 3 0 R >> >> /Contents "
            + f"{content_object_number} 0 R >> endobj\n".encode()
        )
        objects.append(
            f"{content_object_number} 0 obj << /Length ".encode()
            + str(len(content)).encode()
            + b" >> stream\n"
            + content
            + b"\nendstream endobj\n"
        )

    output = bytearray(b"%PDF-1.4\n")
    offsets = []
    for obj in objects:
        offsets.append(len(output))
        output.extend(obj)
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(output)


def image_only_pdf(text: str, *, quality: str) -> bytes:
    background = (235, 235, 235) if quality == "weak" else "white"
    image = Image.new("RGB", (1600, 1000), background)
    draw = ImageDraw.Draw(image)
    font = _font(46 if quality == "weak" else 64)
    y = 260
    for line in text.splitlines():
        fill = (178, 178, 178) if quality == "weak" else "black"
        draw.text((130, y), line, fill=fill, font=font)
        y += 92

    if quality == "weak":
        image = image.rotate(7.5, expand=True, fillcolor=background)
        image = image.filter(ImageFilter.GaussianBlur(radius=2.4))
        image = image.resize((540, 380))

    output = BytesIO()
    image.save(output, format="PDF", resolution=150.0)
    return output.getvalue()


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


if __name__ == "__main__":
    main()
