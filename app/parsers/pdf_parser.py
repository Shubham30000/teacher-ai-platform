"""
PDF parser built on PyMuPDF (``fitz``).

PDF has no semantic heading tags, so structure is recovered with a
font-size/weight heuristic per PROJECT_ROADMAP.md item 6: the body-text
font size is taken as the statistical mode across the document, and any
line rendered meaningfully larger (or bold) than that is treated as a
heading, with heading depth derived from relative font size. Tables are
extracted with PyMuPDF's built-in table finder; images are extracted
via the page's image list and saved to disk.

Phase 1A explicitly does not implement OCR: pages that yield no
extractable text (i.e. scanned/image-only pages) are flagged in
``metadata.extra['ocr_required_pages']`` rather than silently dropped,
so the routing layer in Phase 1B can send them to an OCR-capable
parser.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Optional

from app.core.constants import ElementType, SupportedFileType
from app.core.exceptions import ParsingError
from app.document_intelligence.models import (
    ContentBlock,
    DocumentMetadata,
    HeadingLevel,
    ImageElement,
    Section,
    StructuredDocument,
    TableCell,
    TableElement,
    UrlElement,
)
from app.parsers.base import BaseParser

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s)\]}'\"<>]+")


class PdfParser(BaseParser):
    format_name = "pdf"
    #: OCR is prepared for (see module docstring) but not implemented in Phase 1A.
    supports_ocr = False

    def parse(self, file_path: Path) -> StructuredDocument:
        self._base_check(file_path)
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise ParsingError(
                "PyMuPDF is not installed. Install it with `pip install pymupdf`."
            ) from exc

        try:
            pdf = fitz.open(str(file_path))
        except Exception as exc:  # noqa: BLE001
            raise ParsingError(f"Failed to open PDF file: {exc}") from exc

        try:
            body_size = self._estimate_body_font_size(pdf)
            root_sections: list[Section] = []
            stack: list[tuple[int, Section]] = []
            preamble = Section(heading=None, heading_level=HeadingLevel.TITLE)
            root_sections.append(preamble)
            current = preamble
            ocr_required_pages: list[int] = []
            image_index = 0
            out_dir = file_path.parent / f"{file_path.stem}_assets"

            def attach(level: int, heading_text: str, page_number: int) -> Section:
                nonlocal current
                new_section = Section(
                    heading=heading_text,
                    heading_level=HeadingLevel(level),
                    page_number=page_number,
                )
                while stack and stack[-1][0] >= level:
                    stack.pop()
                if stack:
                    stack[-1][1].subsections.append(new_section)
                else:
                    root_sections.append(new_section)
                stack.append((level, new_section))
                current = new_section
                return new_section

            for page_index in range(pdf.page_count):
                page = pdf[page_index]
                page_number = page_index + 1
                page_dict = page.get_text("dict")
                page_has_text = False

                for block in page_dict.get("blocks", []):
                    if block.get("type") != 0:  # 0 = text block
                        continue
                    for line in block.get("lines", []):
                        spans = line.get("spans", [])
                        if not spans:
                            continue
                        line_text = "".join(span.get("text", "") for span in spans).strip()
                        if not line_text:
                            continue
                        page_has_text = True
                        max_size = max(span.get("size", body_size) for span in spans)
                        is_bold = any("bold" in (span.get("font", "").lower()) for span in spans)

                        level = self._classify_heading_level(max_size, body_size, is_bold)
                        if level is not None:
                            attach(level, line_text, page_number)
                        else:
                            current.blocks.append(
                                ContentBlock(
                                    type=ElementType.PARAGRAPH,
                                    text=line_text,
                                    page_number=page_number,
                                )
                            )
                            for url in _URL_RE.findall(line_text):
                                current.urls.append(
                                    UrlElement(url=url, page_number=page_number)
                                )

                if not page_has_text:
                    ocr_required_pages.append(page_number)

                # Tables (PyMuPDF >= 1.23 provides find_tables()).
                try:
                    table_finder = page.find_tables()
                    for table in table_finder.tables:
                        extracted = table.extract()
                        n_rows = len(extracted)
                        n_cols = max((len(r) for r in extracted), default=0)
                        cells = [
                            TableCell(
                                text=(extracted[r][c] or "") if c < len(extracted[r]) else "",
                                row=r,
                                col=c,
                                is_header=(r == 0),
                            )
                            for r in range(n_rows)
                            for c in range(n_cols)
                        ]
                        current.tables.append(
                            TableElement(
                                n_rows=n_rows,
                                n_cols=n_cols,
                                cells=cells,
                                page_number=page_number,
                            )
                        )
                except Exception:  # noqa: BLE001 - table extraction is best-effort
                    logger.debug("No extractable tables on page %d", page_number)

                # Images.
                for img in page.get_images(full=True):
                    xref = img[0]
                    image_index += 1
                    stored_path: Optional[str] = None
                    try:
                        pix = fitz.Pixmap(pdf, xref)
                        if pix.n - pix.alpha >= 4:  # CMYK -> RGB
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        out_dir.mkdir(parents=True, exist_ok=True)
                        out_path = out_dir / f"page{page_number}_image_{image_index}.png"
                        pix.save(str(out_path))
                        stored_path = str(out_path)
                    except Exception:  # noqa: BLE001
                        logger.warning(
                            "Could not extract image %d on page %d of '%s'",
                            image_index,
                            page_number,
                            file_path.name,
                        )
                    current.images.append(
                        ImageElement(
                            page_number=page_number,
                            stored_path=stored_path,
                            width=img[2] if len(img) > 2 else None,
                            height=img[3] if len(img) > 3 else None,
                        )
                    )

            if not preamble.blocks and not preamble.subsections and not preamble.tables:
                root_sections.remove(preamble)

            pdf_metadata = pdf.metadata or {}
            metadata = DocumentMetadata(
                source_filename=file_path.name,
                file_type=SupportedFileType.PDF,
                file_size_bytes=file_path.stat().st_size,
                page_count=pdf.page_count,
                author=pdf_metadata.get("author") or None,
                title=pdf_metadata.get("title") or None,
                extra={"ocr_required_pages": ocr_required_pages} if ocr_required_pages else {},
            )
            doc = StructuredDocument(metadata=metadata, sections=root_sections)
            logger.info(
                "Parsed PDF '%s': %d pages, %d sections, %d tables, %d images, %d pages need OCR",
                file_path.name,
                pdf.page_count,
                len(root_sections),
                doc.total_table_count(),
                doc.total_image_count(),
                len(ocr_required_pages),
            )
            return doc
        finally:
            pdf.close()

    @staticmethod
    def _estimate_body_font_size(pdf) -> float:
        """Body text font size = the most common span font size in the document."""
        sizes: list[float] = []
        # Sample up to the first 15 pages for performance on large textbooks.
        for page in pdf[: min(15, pdf.page_count)]:
            for block in page.get_text("dict").get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            sizes.append(round(span.get("size", 0), 1))
        if not sizes:
            return 11.0
        counts = Counter(sizes)
        # Counter.most_common() breaks ties by first-insertion order, which on
        # sparsely-sampled pages (or pages with few distinct spans) can select
        # a heading's font size as the "body" size purely because it happened
        # to be encountered first (e.g. a title rendered before any body
        # text). Body text is virtually never the *largest* font on a page,
        # so among sizes tied for the highest frequency, prefer the smallest
        # one as the more plausible body-text size.
        max_frequency = max(counts.values())
        most_frequent_sizes = [size for size, freq in counts.items() if freq == max_frequency]
        return min(most_frequent_sizes) if most_frequent_sizes else median(sizes)

    @staticmethod
    def _classify_heading_level(
        font_size: float, body_size: float, is_bold: bool
    ) -> Optional[int]:
        """Map a line's font size (relative to body size) to a heading level, or None for body text."""
        if body_size <= 0:
            return None
        ratio = font_size / body_size
        if ratio >= 1.8:
            return HeadingLevel.TITLE.value
        if ratio >= 1.5:
            return HeadingLevel.H1.value
        if ratio >= 1.25:
            return HeadingLevel.H2.value
        if ratio >= 1.1:
            return HeadingLevel.H3.value
        if is_bold and ratio >= 1.0:
            return HeadingLevel.H4.value
        return None
