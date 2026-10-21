"""Turns an outside file into a Note's Title and Markdown Body. Images are left out, and the file is not kept.

Word documents go through HTML (mammoth) and Qt's Markdown writer, so a QGuiApplication must exist for them.
"""

import csv
import io
from pathlib import Path

SUPPORTED = (".md", ".markdown", ".txt", ".csv", ".docx", ".pdf")
FILE_FILTER = "Documents (*.md *.markdown *.txt *.csv *.docx *.pdf)"


class ImportRefused(Exception):
    """The file can't be imported; the message says why, for the user."""


def import_file(path: Path) -> tuple[str, str]:
    """(Title, Markdown) for the file at `path`. Raises ImportRefused if it can't be imported."""
    suffix = path.suffix.lower()
    if suffix in (".md", ".markdown", ".txt"):
        markdown = _read_text(path)
    elif suffix == ".csv":
        markdown = _csv_table(_read_text(path))
    elif suffix == ".docx":
        markdown = _word(path)
    elif suffix == ".pdf":
        markdown = _pdf(path)
    elif suffix == ".doc":
        raise ImportRefused(f"{path.name} is in the old Word format. Save it as .docx in Word, then import that.")
    else:
        raise ImportRefused(f"{path.name} can't be imported: only Markdown, text, CSV, Word (.docx) and PDF files.")
    return path.stem, markdown.strip()


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")  # most older text files on Windows
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _csv_table(text: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [row for row in csv.reader(io.StringIO(text), dialect) if any(cell.strip() for cell in row)]
    if not rows:
        raise ImportRefused("The CSV file is empty.")
    width = max(len(row) for row in rows)

    def line(row: list[str]) -> str:
        cells = [_cell(cell) for cell in row] + [""] * (width - len(row))
        return "| " + " | ".join(cells) + " |"

    return "\n".join([line(rows[0]), "| " + " | ".join(["---"] * width) + " |", *map(line, rows[1:])])


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def _word(path: Path) -> str:
    import mammoth
    from PySide6.QtGui import QTextDocument

    try:
        with path.open("rb") as file:
            # Images are dropped: an <img> with no source, which Qt then leaves out.
            html = mammoth.convert_to_html(file, convert_image=mammoth.images.img_element(lambda image: {})).value
    except Exception as error:  # not a zip, missing parts, ...
        raise ImportRefused(f"{path.name} could not be read as a Word document.") from error
    document = QTextDocument()
    document.setHtml(html)
    return document.toMarkdown(QTextDocument.MarkdownFeature.MarkdownDialectGitHub)


def _pdf(path: Path) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ImportRefused(f"{path.name} is protected by a password.")
        pages = [_tidy(page.extract_text() or "") for page in reader.pages]
    except ImportRefused:
        raise
    except Exception as error:
        raise ImportRefused(f"{path.name} could not be read as a PDF.") from error
    pages = [page for page in pages if page]
    if not pages:
        raise ImportRefused(f"{path.name} has no text to import (perhaps it is a scan).")
    return "\n\n".join(pages)


def _tidy(text: str) -> str:
    """A PDF page's text with each line's spacing evened out: PDFs often space words with tabs."""
    return "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()
