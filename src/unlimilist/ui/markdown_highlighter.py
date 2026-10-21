"""Colours raw Markdown as it is typed: headings, emphasis, code, links, lists, quotes and tables. The colours
are only drawn; the text itself stays plain Markdown."""

import re

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

_IN_FENCE = 1  # block state: inside a ``` fenced code block
# Named monospaced fonts: the system's own (".AppleSystemUIFontMonospaced") spaces out digits in a text editor.
MONOSPACE = ["Menlo", "Consolas", "DejaVu Sans Mono", "monospace"]


def _format(colour: str, bold: bool = False, italic: bool = False, fixed: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(colour))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    if italic:
        fmt.setFontItalic(True)
    if fixed:
        fmt.setFontFamilies(MONOSPACE)
    return fmt


HEADING = _format("#1A3D8F", bold=True)
MARKER = _format("#8A8F99")  # list bullets, quote marks, table pipes, rules
CODE = _format("#B4235A", fixed=True)
LINK = _format("#2F6FED")
QUOTE = _format("#5A5F6B", italic=True)
BOLD = _format("#1B1B1F", bold=True)
ITALIC = _format("#1B1B1F", italic=True)
STRIKE = _format("#8A8F99")
STRIKE.setFontStrikeOut(True)

_INLINE = [
    (re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1"), BOLD),
    (re.compile(r"(?<![*\w])([*_])(?=\S)(.+?)(?<=\S)\1(?![*\w])"), ITALIC),
    (re.compile(r"~~(?=\S)(.+?)(?<=\S)~~"), STRIKE),
    (re.compile(r"!?\[[^\]\n]*\]\([^)\n]*\)|<https?://[^>\s]+>"), LINK),
    (re.compile(r"`[^`\n]+`"), CODE),  # last, so code wins over what looks like emphasis inside it
]
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s.*$")
_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s)?")
_QUOTE = re.compile(r"^\s{0,3}>.*$")
_RULE = re.compile(r"^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")
_TABLE_PIPE = re.compile(r"\|")
_FENCE = re.compile(r"^\s{0,3}```")


class MarkdownHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text: str) -> None:
        fenced = self.previousBlockState() == _IN_FENCE
        if _FENCE.match(text):
            self.setFormat(0, len(text), CODE)
            self.setCurrentBlockState(-1 if fenced else _IN_FENCE)
            return
        if fenced:
            self.setFormat(0, len(text), CODE)
            self.setCurrentBlockState(_IN_FENCE)
            return
        self.setCurrentBlockState(-1)
        if _HEADING.match(text):
            self.setFormat(0, len(text), HEADING)
            return
        if _RULE.match(text):
            self.setFormat(0, len(text), MARKER)
            return
        if _QUOTE.match(text):
            self.setFormat(0, len(text), QUOTE)
        if match := _LIST.match(text):
            self.setFormat(0, match.end(), MARKER)
        if text.lstrip().startswith("|"):
            for match in _TABLE_PIPE.finditer(text):
                self.setFormat(match.start(), 1, MARKER)
        for pattern, fmt in _INLINE:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)
