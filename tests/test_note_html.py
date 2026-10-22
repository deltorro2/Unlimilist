"""A Note's Body as the HTML page View mode shows: Markdown rendered, Mermaid blocks left for mermaid.js."""

from unlimilist.note_html import render_html


def body(html: str) -> str:
    return html[html.index("<body>") : html.index("</body>")]


def test_markdown_is_rendered_with_tables_strikethrough_checkboxes_and_links():
    html = body(
        render_html(
            "# Lisbon\n\n**bold** ~~gone~~\n\n- [x] Passports\n- [ ] Insurance\n\n"
            "| Day | Plan |\n| --- | --- |\n| Mon | Alfama |\n\nhttps://visitlisboa.com"
        )
    )

    assert "<h1>Lisbon</h1>" in html
    assert "<strong>bold</strong>" in html and "<s>gone</s>" in html
    assert html.count('type="checkbox"') == 2 and "checked" in html and "disabled" in html
    assert "<table>" in html and "<th>Day</th>" in html
    assert '<a href="https://visitlisboa.com">' in html


def test_a_mermaid_block_is_left_for_mermaid_js():
    html = body(render_html("```mermaid\ngraph TD; A-->B\n```"))

    assert '<pre class="mermaid">graph TD; A--&gt;B\n</pre>' in html


def test_other_code_blocks_stay_code():
    assert "<pre><code" in body(render_html("```python\nprint(1)\n```"))


def test_html_written_in_a_note_is_shown_as_text_never_run():
    html = body(render_html("<script>alert(1)</script> <img src=x onerror=alert(1)>"))

    assert "<script>" not in html and "<img" not in html
    assert "&lt;script&gt;" in html


def test_the_page_loads_mermaid_from_the_app_not_the_internet():
    html = render_html("text")

    assert '<script src="mermaid.min.js"></script>' in html
    assert "http" not in html[: html.index("<body>")]
