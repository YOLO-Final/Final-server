import argparse
import base64
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

try:
    import fitz  # PyMuPDF
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"PyMuPDF is required. Install with: py -m pip install pymupdf ({exc})")


def ocr_pdf_to_text(pdf_path: Path, out_path: Path, model: str, max_pages: int = 0) -> Path:
    load_dotenv()
    client = OpenAI()

    doc = fitz.open(str(pdf_path))
    page_count = len(doc)
    limit = page_count if max_pages <= 0 else min(page_count, max_pages)

    chunks = []
    for idx in range(limit):
        page = doc.load_page(idx)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image_bytes = pix.tobytes("png")
        b64 = base64.b64encode(image_bytes).decode("ascii")
        image_url = f"data:image/png;base64,{b64}"

        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Extract all visible text from this page exactly as written. "
                                "Keep original language (Korean/English), line breaks, and tables as plain text. "
                                "Do not summarize."
                            ),
                        },
                        {"type": "input_image", "image_url": image_url},
                    ],
                }
            ],
        )
        text = (response.output_text or "").strip()
        chunks.append(f"\n\n=== PAGE {idx + 1} ===\n{text}\n")
        print(f"[ocr] page {idx + 1}/{limit} done")

    out_path.write_text("".join(chunks).strip() + "\n", encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="OCR PDF to TXT with OpenAI Vision")
    parser.add_argument("pdf", type=str, help="Input PDF path")
    parser.add_argument("--out", type=str, default="", help="Output TXT path")
    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="Vision-capable model")
    parser.add_argument("--max-pages", type=int, default=0, help="Process only first N pages (0=all)")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
        raise SystemExit(f"Input PDF not found: {pdf_path}")

    if args.out:
        out_path = Path(args.out).resolve()
    else:
        out_path = pdf_path.with_suffix("")
        out_path = out_path.with_name(out_path.name + "_ocr.txt")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = ocr_pdf_to_text(pdf_path, out_path, model=args.model, max_pages=args.max_pages)
    print(f"[ocr] written: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
