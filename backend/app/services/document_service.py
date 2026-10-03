"""Document parsing service for PDF, DOCX, and TXT files."""

from __future__ import annotations

import io
import logging
import re
import zipfile
from pathlib import PurePosixPath

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from lxml import etree

from app.config import get_settings
from app.core.exceptions import FileValidationException

logger = logging.getLogger(__name__)

# Supported extensions mapped to canonical type strings
_EXTENSION_MAP: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
}

# Magic-byte signatures for binary formats
_MAGIC_BYTES: dict[str, bytes] = {
    "pdf": b"%PDF",
    "docx": b"PK\x03\x04",  # ZIP (Office Open XML)
}

# Bound expansion before python-docx loads the package into memory.
_MAX_DOCX_MEMBERS = 2048
_MAX_DOCX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
_MAX_DOCX_XML_BYTES = 8 * 1024 * 1024


def _checked_xml(archive: zipfile.ZipFile, name: str):
    with archive.open(name) as member:
        data = member.read(_MAX_DOCX_XML_BYTES + 1)
    if len(data) > _MAX_DOCX_XML_BYTES:
        raise FileValidationException("DOCX XML part exceeds the parsing size limit")
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    root = etree.fromstring(data, parser=parser)
    if root.getroottree().docinfo.doctype:
        raise FileValidationException("DOCX XML must not contain a DTD or entity declarations")
    return root


def _validate_docx(content: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > _MAX_DOCX_MEMBERS:
                raise FileValidationException("DOCX contains too many archive entries")
            names: set[str] = set()
            expanded_size = 0
            for member in members:
                path = PurePosixPath(member.filename)
                if (
                    member.filename in names
                    or path.is_absolute()
                    or ".." in path.parts
                    or "\\" in member.filename
                    or member.flag_bits & 1
                ):
                    raise FileValidationException(
                        "DOCX contains unsafe or duplicate archive entries"
                    )
                names.add(member.filename)
                expanded_size += member.file_size
            if expanded_size > _MAX_DOCX_UNCOMPRESSED_BYTES:
                raise FileValidationException("DOCX expanded size exceeds the parsing size limit")
            required = {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}
            if not required.issubset(names):
                raise FileValidationException("DOCX is missing required document parts")

            types = _checked_xml(archive, "[Content_Types].xml")
            namespace = "{http://schemas.openxmlformats.org/package/2006/content-types}"
            defaults = {
                node.get("Extension"): node.get("ContentType", "")
                for node in types.findall(f"{namespace}Default")
            }
            overrides = {
                node.get("PartName", "").lstrip("/"): node.get("ContentType", "")
                for node in types.findall(f"{namespace}Override")
            }
            for member in members:
                if member.is_dir() or member.filename == "[Content_Types].xml":
                    continue
                suffix = PurePosixPath(member.filename).suffix.lower().lstrip(".")
                content_type = overrides.get(member.filename, defaults.get(suffix, ""))
                if suffix in {"xml", "rels"} or content_type.lower().endswith(("+xml", "/xml")):
                    _checked_xml(archive, member.filename)
    except FileValidationException:
        raise
    except (zipfile.BadZipFile, etree.LxmlError, OSError, ValueError, RuntimeError) as exc:
        raise FileValidationException("Invalid or unsupported DOCX ZIP/XML package") from exc


def _with_sources(result: dict, file_type: str) -> dict:
    for index, section in enumerate(result["sections"]):
        section["index"] = index
        section["source_ref"] = f"section:{index}"
        section["source"] = {
            **section.get("source", {}),
            "file_type": file_type,
            "section_index": index,
            "page_start": section.get("page_start"),
            "page_end": section.get("page_end"),
        }
    result["metadata"] = {"extraction": "text", "ocr_performed": False}
    result["warnings"] = (
        ["No extractable text was found. OCR is not performed."]
        if not result["full_text"].strip()
        else []
    )
    return result


def _docx_blocks(element, parent):
    for child in element:
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)
        elif child.tag in {qn("w:sdt"), qn("w:sdtContent"), qn("w:customXml")}:
            yield from _docx_blocks(child, parent)


def _table_rows(table: Table) -> list[list[str]]:
    rows = []
    for row in table.rows:
        cells = []
        # Physical cells avoid duplicating horizontally/vertically merged text.
        for cell_element in row._tr.tc_lst:
            cell = _Cell(cell_element, table)
            parts = []
            for block in _docx_blocks(cell_element, cell):
                if isinstance(block, Paragraph):
                    parts.append(block.text.strip())
                else:
                    parts.append("\n".join("\t".join(values) for values in _table_rows(block)))
            cells.append("\n".join(part for part in parts if part))
        rows.append(cells)
    return rows


class DocumentService:
    """Parse documents with stable, zero-based section indices and source metadata.

    Existing result fields are retained. ``metadata`` and ``warnings`` describe
    text extraction limitations; this service does not perform OCR.
    """

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_file(self, filename: str, content: bytes, file_size: int) -> str:
        """Validate a file and return its detected type string.

        Checks:
        1. File extension is among the supported types.
        2. File size does not exceed the configured maximum.
        3. Magic bytes match the claimed extension (for binary types).
        4. DOCX ZIP/XML parts are bounded and contain no DTDs or unsafe entries.

        Returns
        -------
        str
            One of ``"pdf"``, ``"docx"``, ``"txt"``.

        Raises
        ------
        FileValidationException
            When any validation check fails.
        """
        settings = get_settings()
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

        # --- extension check ---
        suffix = PurePosixPath(filename).suffix.lower()
        file_type = _EXTENSION_MAP.get(suffix)
        if file_type is None:
            allowed = ", ".join(sorted(_EXTENSION_MAP.keys()))
            raise FileValidationException(
                f"Unsupported file extension '{suffix}'. Allowed: {allowed}"
            )

        # --- size check ---
        actual_size = max(file_size, len(content))
        if actual_size > max_bytes:
            raise FileValidationException(
                f"File size ({actual_size / 1024 / 1024:.1f} MB) exceeds the "
                f"maximum allowed ({settings.MAX_UPLOAD_SIZE_MB} MB)"
            )
        if file_size != len(content):
            raise FileValidationException("Declared file size does not match the supplied content")
        if not content:
            raise FileValidationException("The uploaded file is empty")

        # --- magic bytes check (binary formats only) ---
        expected_magic = _MAGIC_BYTES.get(file_type)
        if expected_magic is not None:
            if not content[: len(expected_magic)] == expected_magic:
                raise FileValidationException(
                    f"File content does not match the expected format for "
                    f"'{suffix}' (magic bytes mismatch)"
                )

        if file_type == "docx":
            _validate_docx(content)
        return file_type

    # ------------------------------------------------------------------
    # PDF parsing
    # ------------------------------------------------------------------

    def parse_pdf(self, content: bytes) -> dict:
        """Parse a PDF using PyMuPDF.

        Extracts text per page, identifies headings by font-size heuristic,
        and groups text into hierarchical sections.

        Returns
        -------
        dict
            ``{"full_text": str, "sections": list[dict], "page_count": int}``
            Each section dict has keys: ``title``, ``level``, ``content``,
            ``page_start``, ``page_end``.
        """
        doc = fitz.open(stream=content, filetype="pdf")
        page_count = len(doc)

        # First pass: collect all text spans with font size info to determine
        # the heading threshold.
        all_spans: list[dict] = []
        for page_num in range(page_count):
            page = doc[page_num]
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
            for block in blocks:
                if block.get("type") != 0:  # skip image blocks
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text:
                            all_spans.append(
                                {
                                    "text": text,
                                    "size": round(span.get("size", 12), 1),
                                    "flags": span.get("flags", 0),
                                    "page": page_num,
                                }
                            )

        if not all_spans:
            doc.close()
            return _with_sources({"full_text": "", "sections": [], "page_count": page_count}, "pdf")

        # Determine body font size (the most common size)
        size_counts: dict[float, int] = {}
        for sp in all_spans:
            size_counts[sp["size"]] = size_counts.get(sp["size"], 0) + len(sp["text"])
        body_size = max(size_counts, key=size_counts.get)

        # Heading threshold: anything > body_size + 1pt or bold with > body_size
        heading_threshold = body_size + 1.0

        # Second pass: build sections
        sections: list[dict] = []
        current_section: dict | None = None
        full_text_parts: list[str] = []

        for sp in all_spans:
            text = sp["text"]
            full_text_parts.append(text)

            is_heading = False
            heading_level = 2  # default sub-heading

            if sp["size"] >= heading_threshold:
                is_heading = True
                # Larger font = higher heading level
                size_diff = sp["size"] - body_size
                if size_diff >= 6:
                    heading_level = 1
                elif size_diff >= 3:
                    heading_level = 2
                else:
                    heading_level = 3
            elif sp["size"] > body_size and (sp["flags"] & 2**4):
                # Bold text slightly larger than body
                is_heading = True
                heading_level = 3

            if is_heading and len(text) < 200:
                # Finish previous section
                if current_section is not None:
                    current_section["content"] = current_section["content"].strip()
                    sections.append(current_section)

                current_section = {
                    "title": text,
                    "level": heading_level,
                    "content": "",
                    "page_start": sp["page"],
                    "page_end": sp["page"],
                }
            else:
                if current_section is None:
                    # Text before the first heading -> untitled section
                    current_section = {
                        "title": "Introduction",
                        "level": 1,
                        "content": "",
                        "page_start": sp["page"],
                        "page_end": sp["page"],
                    }
                current_section["content"] += text + " "
                current_section["page_end"] = sp["page"]

        # Flush last section
        if current_section is not None:
            current_section["content"] = current_section["content"].strip()
            sections.append(current_section)

        doc.close()
        full_text = " ".join(full_text_parts)

        return _with_sources(
            {
                "full_text": full_text,
                "sections": sections,
                "page_count": page_count,
            },
            "pdf",
        )

    # ------------------------------------------------------------------
    # DOCX parsing
    # ------------------------------------------------------------------

    def parse_docx(self, content: bytes) -> dict:
        """Parse a DOCX file using python-docx.

        Uses Word heading styles (``Heading 1``, ``Heading 2``, etc.) to
        identify section structure. Paragraphs and tables remain in document
        order. Table text uses tabs between cells and newlines between rows;
        ``blocks`` retains structured cells and exact section-content offsets.

        Returns
        -------
        dict
            ``{"full_text": str, "sections": list[dict], "page_count": None}``
        """
        _validate_docx(content)
        doc = DocxDocument(io.BytesIO(content))

        sections: list[dict] = []
        current_section: dict | None = None
        full_text_parts: list[str] = []
        section_parts: list[str] = []
        section_length = 0

        for block_index, block in enumerate(_docx_blocks(doc.element.body, doc)):
            rows = _table_rows(block) if isinstance(block, Table) else None
            text = (
                "\n".join("\t".join(row) for row in rows)
                if rows is not None
                else block.text.strip()
            )
            if not text.strip():
                continue

            full_text_parts.append(text)
            style_name = block.style.name if isinstance(block, Paragraph) and block.style else ""

            # Detect heading paragraphs
            is_heading = False
            heading_level = 1

            if style_name.startswith("Heading"):
                is_heading = True
                # Extract level number: "Heading 1" -> 1, "Heading 2" -> 2, etc.
                level_str = style_name.replace("Heading", "").strip()
                try:
                    heading_level = int(level_str) if level_str else 1
                except ValueError:
                    heading_level = 1
            elif style_name == "Title":
                is_heading = True
                heading_level = 1

            if is_heading:
                # Close previous section
                if current_section is not None:
                    current_section["content"] = "\n".join(section_parts)
                    sections.append(current_section)

                section_parts = []
                section_length = 0

                current_section = {
                    "title": text,
                    "level": heading_level,
                    "content": "",
                    "page_start": None,
                    "page_end": None,
                    "blocks": [],
                    "source": {"heading_block_index": block_index},
                }
            else:
                if current_section is None:
                    current_section = {
                        "title": "Untitled Section",
                        "level": 1,
                        "content": "",
                        "page_start": None,
                        "page_end": None,
                        "blocks": [],
                    }
                start = section_length + bool(section_parts)
                section_parts.append(text)
                section_length = start + len(text)
                source_block = {
                    "type": "table" if rows is not None else "paragraph",
                    "block_index": block_index,
                    "source_ref": f"docx:block:{block_index}",
                    "start": start,
                    "end": start + len(text),
                }
                if rows is not None:
                    source_block["rows"] = rows
                    source_block["row_spans"] = []
                    row_start = start
                    for row_index, row in enumerate(rows):
                        row_end = row_start + len("\t".join(row))
                        source_block["row_spans"].append(
                            {
                                "row_index": row_index,
                                "start": row_start,
                                "end": row_end,
                            }
                        )
                        row_start = row_end + 1
                current_section["blocks"].append(source_block)

        # Flush last section
        if current_section is not None:
            current_section["content"] = "\n".join(section_parts)
            sections.append(current_section)

        full_text = "\n".join(full_text_parts)

        return _with_sources(
            {
                "full_text": full_text,
                "sections": sections,
                "page_count": None,
            },
            "docx",
        )

    # ------------------------------------------------------------------
    # TXT / Markdown parsing
    # ------------------------------------------------------------------

    def parse_txt(self, content: bytes) -> dict:
        """Parse a plain text or Markdown file.

        Splits by Markdown headings (``# Title``, ``## Sub``, etc.) or by
        double-newline-separated blocks when no headings are found.

        Returns
        -------
        dict
            ``{"full_text": str, "sections": list[dict], "page_count": None}``
        """
        text = content.decode("utf-8", errors="replace")

        # Try Markdown heading parsing first
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        headings = list(heading_pattern.finditer(text))

        sections: list[dict] = []

        if headings:
            # Parse using Markdown headings
            for i, match in enumerate(headings):
                level = len(match.group(1))
                title = match.group(2).strip()
                start = match.end()
                end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
                section_content = text[start:end].strip()

                # If there is text before the first heading, capture it
                if i == 0 and match.start() > 0:
                    preamble = text[: match.start()].strip()
                    if preamble:
                        sections.append(
                            {
                                "title": "Preamble",
                                "level": 1,
                                "content": preamble,
                                "page_start": None,
                                "page_end": None,
                            }
                        )

                sections.append(
                    {
                        "title": title,
                        "level": level,
                        "content": section_content,
                        "page_start": None,
                        "page_end": None,
                    }
                )
        else:
            # Fallback: split by double newlines into paragraph-based sections
            blocks = re.split(r"\n\s*\n", text)
            blocks = [b.strip() for b in blocks if b.strip()]

            if blocks:
                # Group blocks into sections of reasonable size
                # Use the first line of each block group as a pseudo-title
                chunk_size = max(1, len(blocks) // 10) if len(blocks) > 10 else 1
                for i in range(0, len(blocks), chunk_size):
                    chunk = blocks[i : i + chunk_size]
                    combined = "\n\n".join(chunk)
                    # Use first line (truncated) as title
                    first_line = chunk[0].split("\n")[0][:80]
                    sections.append(
                        {
                            "title": first_line if len(blocks) > 1 else "Full Text",
                            "level": 1,
                            "content": combined,
                            "page_start": None,
                            "page_end": None,
                        }
                    )

        return _with_sources(
            {
                "full_text": text,
                "sections": sections,
                "page_count": None,
            },
            "txt",
        )

    # ------------------------------------------------------------------
    # Unified parse entry point
    # ------------------------------------------------------------------

    def parse(self, content: bytes, file_type: str) -> dict:
        """Route to the appropriate parser based on file type.

        Parameters
        ----------
        content:
            Raw file bytes.
        file_type:
            One of ``"pdf"``, ``"docx"``, ``"txt"``.

        Returns
        -------
        dict
            ``{"full_text": str, "sections": list[dict], "page_count": int | None}``
        """
        parsers = {
            "pdf": self.parse_pdf,
            "docx": self.parse_docx,
            "txt": self.parse_txt,
        }

        parser = parsers.get(file_type)
        if parser is None:
            raise FileValidationException(f"No parser available for type '{file_type}'")

        try:
            result = parser(content)
        except FileValidationException:
            raise
        except Exception as exc:
            logger.exception("Failed to parse %s document", file_type)
            raise FileValidationException(f"Failed to parse {file_type} document: {exc}") from exc

        logger.info(
            "Parsed %s document: %d sections, %d chars",
            file_type,
            len(result.get("sections", [])),
            len(result.get("full_text", "")),
        )
        return result
