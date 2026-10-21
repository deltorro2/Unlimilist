"""Importing outside files as Notes: each is converted to Markdown."""

import io

import pytest
from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from unlimilist.note_import import ImportRefused, import_file


def test_a_markdown_file_is_kept_as_is_and_titled_after_its_name(tmp_path):
    path = tmp_path / "Trip plan.md"
    path.write_text("# Lisbon\n\n- Alfama\n", encoding="utf-8")

    assert import_file(path) == ("Trip plan", "# Lisbon\n\n- Alfama")


def test_a_text_file_is_kept_as_text(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("line one\nline two", encoding="utf-8")

    assert import_file(path) == ("notes", "line one\nline two")


def test_a_text_file_that_is_not_utf8_still_imports(tmp_path):
    path = tmp_path / "old.txt"
    path.write_bytes("café".encode("cp1252"))

    assert import_file(path)[1] == "café"


def test_a_csv_file_becomes_a_table(tmp_path):
    path = tmp_path / "cities.csv"
    path.write_text("City,Days\nLisbon,3\nPorto,a|b\nFaro\n", encoding="utf-8")

    title, markdown = import_file(path)

    assert title == "cities"
    assert markdown == "| City | Days |\n| --- | --- |\n| Lisbon | 3 |\n| Porto | a\\|b |\n| Faro |  |"


def test_a_semicolon_csv_is_understood(tmp_path):
    path = tmp_path / "eu.csv"
    path.write_text("Name;Price\nTea;2,50\n", encoding="utf-8")

    assert import_file(path)[1] == "| Name | Price |\n| --- | --- |\n| Tea | 2,50 |"


def test_a_word_document_keeps_headings_formatting_lists_and_tables(qapp, tmp_path):
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_heading("Trip plan", 1)
    paragraph = document.add_paragraph("Some ")
    paragraph.add_run("bold").bold = True
    paragraph.add_run(" and ")
    paragraph.add_run("italic").italic = True
    document.add_paragraph("Alfama", style="List Bullet")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "City", "Days"
    table.cell(1, 0).text, table.cell(1, 1).text = "Lisbon", "3"
    path = tmp_path / "Trip.docx"
    document.save(path)

    title, markdown = import_file(path)

    assert title == "Trip"
    assert "# Trip plan" in markdown
    assert "**bold**" in markdown and "*italic*" in markdown
    assert "- Alfama" in markdown
    assert "|Lisbon|3" in markdown.replace(" ", "")


def _pdf(path, pages):
    writer = QPdfWriter(str(path))
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait, QMarginsF()))
    painter = QPainter(writer)
    for number, text in enumerate(pages):
        if number:
            writer.newPage()
        if text:
            painter.drawText(QRectF(200, 200, 8000, 2000), text)
        else:
            painter.fillRect(QRectF(200, 200, 2000, 2000), 0x888888)  # a "scan": no text at all
    painter.end()


def test_a_pdf_gives_its_text_page_by_page(qapp, tmp_path):
    path = tmp_path / "Report.pdf"
    _pdf(path, ["First page", "Second page"])

    title, markdown = import_file(path)

    assert title == "Report"
    assert markdown.index("First page") < markdown.index("Second page")


def test_a_pdf_without_text_is_refused(qapp, tmp_path):
    path = tmp_path / "scan.pdf"
    _pdf(path, [""])

    with pytest.raises(ImportRefused, match="no text"):
        import_file(path)


@pytest.mark.parametrize("name, reason", [("old.doc", "docx"), ("photo.png", "can't be imported")])
def test_other_files_are_refused(tmp_path, name, reason):
    path = tmp_path / name
    path.write_bytes(b"\x00\x01")

    with pytest.raises(ImportRefused, match=reason):
        import_file(path)


def test_a_broken_word_file_is_refused(qapp, tmp_path):
    path = tmp_path / "broken.docx"
    path.write_bytes(b"not a zip")

    with pytest.raises(ImportRefused):
        import_file(path)
