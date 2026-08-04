"""
Plain-text parser.

Plain text has no native structural markup, so headings are recovered
heuristically rather than flattening the whole file into one blob:

  * Markdown-style ``#``, ``##``, ``###`` prefixes
  * Setext-style headings (a line followed by a line of ``===`` or ``---``)
  * Numbered headings, e.g. ``1.``, ``1.2``, ``Chapter 3``
  * Short ALL-CAPS lines (common in plain-text textbook exports)

Anything that doesn't match a heading heuristic becomes a paragraph or
list item under the most recently seen heading. URLs found anywhere in
the text are also extracted into ``UrlElement``s.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from app.core.constants import ElementType, SupportedFileType
from app.core.exceptions import ParsingError
from app.document_intelligence.models import (
    ContentBlock,
    DocumentMetadata,
    HeadingLevel,
    Section,
    StructuredDocument,
    UrlElement,
)
from app.parsers.base import BaseParser

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s)\]}'\"<>]+")
_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,4})\s+(.*\S)\s*$")
_NUMBERED_HEADING_RE = re.compile(
    r"^((?:chapter|unit|section)\s+)?(\d+(?:\.\d+){0,3})[\.\)]?\s+([A-Z].{2,80})$",
    re.IGNORECASE,
)
_LIST_ITEM_RE = re.compile(r"^\s*([-*•]|\d+[\.\)])\s+(.*\S)\s*$")


def _heading_level_for_numbering(numbering: str) -> HeadingLevel:
    depth = numbering.count(".") + 1
    return HeadingLevel(min(depth, HeadingLevel.H4.value))


def _looks_like_caps_heading(line: str) -> bool:
    stripped = line.strip()
    if not (3 <= len(stripped) <= 80):
        return False
    letters = [c for c in stripped if c.isalpha()]
    if len(letters) < 3:
        return False
    return all(c.isupper() for c in letters) and not stripped.endswith((".", ",", ";"))


class TxtParser(BaseParser):
    format_name = "txt"
    supports_ocr = False

    def parse(self, file_path: Path) -> StructuredDocument:
        self._base_check(file_path)
        try:
            raw = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ParsingError(f"Could not read TXT file: {exc}") from exc

        lines = raw.splitlines()
        root_sections: list[Section] = []
        # Stack of (level, Section) representing current heading nesting.
        stack: list[tuple[int, Section]] = []
        preamble = Section(heading=None, heading_level=HeadingLevel.TITLE)
        root_sections.append(preamble)
        current: Section = preamble

        def attach(level: int, heading_text: str) -> Section:
            nonlocal current
            new_section = Section(heading=heading_text, heading_level=HeadingLevel(level))
            while stack and stack[-1][0] >= level:
                stack.pop()
            if stack:
                stack[-1][1].subsections.append(new_section)
            else:
                root_sections.append(new_section)
            stack.append((level, new_section))
            current = new_section
            return new_section

        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                i += 1
                continue

            # Setext heading: text line followed by a line of === or ---
            if i + 1 < n and re.fullmatch(r"=+", lines[i + 1].strip()):
                attach(HeadingLevel.H1.value, stripped)
                i += 2
                continue
            if i + 1 < n and re.fullmatch(r"-{3,}", lines[i + 1].strip()):
                attach(HeadingLevel.H2.value, stripped)
                i += 2
                continue

            md_match = _MARKDOWN_HEADING_RE.match(stripped)
            if md_match:
                level = min(len(md_match.group(1)), HeadingLevel.H4.value)
                attach(level, md_match.group(2))
                i += 1
                continue

            num_match = _NUMBERED_HEADING_RE.match(stripped)
            if num_match:
                numbering = num_match.group(2)
                title = num_match.group(3)
                level = _heading_level_for_numbering(numbering).value
                attach(level, f"{numbering} {title}".strip())
                i += 1
                continue

            if _looks_like_caps_heading(stripped):
                attach(HeadingLevel.H1.value, stripped.title())
                i += 1
                continue

            list_match = _LIST_ITEM_RE.match(line)
            if list_match:
                current.blocks.append(
                    ContentBlock(
                        type=ElementType.LIST_ITEM,
                        text=list_match.group(2),
                        list_level=0,
                    )
                )
                i += 1
                continue

            # Regular paragraph: accumulate contiguous non-blank lines.
            para_lines = [stripped]
            i += 1
            while i < n and lines[i].strip() and not _MARKDOWN_HEADING_RE.match(lines[i].strip()):
                para_lines.append(lines[i].strip())
                i += 1
            para_text = " ".join(para_lines)
            current.blocks.append(ContentBlock(type=ElementType.PARAGRAPH, text=para_text))

        # Extract URLs across the whole document into their owning section.
        for section in [s for root in root_sections for s in root.iter_sections()]:
            for block in section.blocks:
                for url in _URL_RE.findall(block.text):
                    section.urls.append(UrlElement(url=url))

        if not preamble.blocks and not preamble.subsections:
            root_sections.remove(preamble)

        metadata = DocumentMetadata(
            source_filename=file_path.name,
            file_type=SupportedFileType.TXT,
            file_size_bytes=file_path.stat().st_size,
        )
        doc = StructuredDocument(metadata=metadata, sections=root_sections, raw_text_fallback=raw)
        logger.info(
            "Parsed TXT '%s': %d top-level sections", file_path.name, len(root_sections)
        )
        return doc
