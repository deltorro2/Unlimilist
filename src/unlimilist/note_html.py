"""A Note's Body as the HTML page View mode shows. The Markdown is rendered here (GitHub style: tables,
strikethrough, checkboxes, bare links); a ```mermaid block is left as text for mermaid.js, which the page loads from
the app's own files, so diagrams draw offline. HTML written in a Note is shown as text, never run.

The page sets `data-diagrams="done"` on its body once every diagram is drawn (or marked as broken).
"""

from markdown_it import MarkdownIt
from markdown_it.common.utils import escapeHtml
from mdit_py_plugins.tasklists import tasklists_plugin

_STYLE = """
body { margin: 0; padding: 10px 14px 24px; background: #FFFFFF; color: #1B1B1F;
       font: 14px/1.45 -apple-system, "Segoe UI", "Helvetica Neue", sans-serif; }
h1, h2, h3, h4, h5, h6 { margin: 14px 0 6px; line-height: 1.25; }
body > :first-child { margin-top: 0; }
h1 { font-size: 26px; } h2 { font-size: 20px; } h3 { font-size: 17px; }
p { margin: 0 0 10px; }
ul, ol { margin: 0 0 10px; padding-left: 28px; }
li { margin: 0 0 3px; }
li.task-list-item { list-style: none; margin-left: -20px; }
li.task-list-item input { margin: 0 6px 0 0; }
blockquote { margin: 0 0 10px; padding-left: 24px; color: #5A5F6B; font-style: italic; }
code, pre { font-family: Menlo, Consolas, "DejaVu Sans Mono", monospace; font-size: 13px; }
pre { margin: 0 0 10px; padding: 8px 10px; background: #F6F7FA; border-radius: 6px; overflow-x: auto; }
table { border-collapse: collapse; margin: 0 0 10px; }
th, td { border: 1px solid #D3D7E0; padding: 6px; text-align: left; vertical-align: top; }
th { font-weight: 700; }
a { color: #2F6FED; text-decoration: none; }
hr { border: none; border-top: 1px solid #D3D7E0; margin: 12px 0; }
.mermaid-block { margin: 0 0 10px; }
.mermaid-block pre.mermaid { visibility: hidden; height: 0; padding: 0; margin: 0; }
.mermaid-block.broken pre.mermaid { visibility: visible; height: auto; padding: 8px 10px; }
.mermaid-block svg { max-width: 100%; height: auto; }
.diagram-error { color: #D32F2F; font-size: 12px; margin: 0 0 4px; }
"""

# Draws each diagram in turn; a broken one keeps its code, under a short red error.
_DIAGRAMS = """
document.addEventListener("DOMContentLoaded", async () => {
  if (!window.mermaid) {  // never expected: the script ships with the app
    document.body.dataset.diagrams = "done";
    return;
  }
  mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "default" });
  let number = 0;
  for (const pre of document.querySelectorAll("pre.mermaid")) {
    const holder = pre.parentElement;
    const id = "diagram-" + number++;
    try {
      const { svg } = await mermaid.render(id, pre.textContent);
      holder.insertAdjacentHTML("beforeend", svg);
      holder.classList.add("rendered");
    } catch (error) {
      holder.classList.add("broken");
      const note = document.createElement("div");
      note.className = "diagram-error";
      note.textContent = "Diagram error: " + String(error && error.message ? error.message : error).split("\\n")[0];
      holder.insertBefore(note, pre);
      document.getElementById("d" + id)?.remove();  // what mermaid leaves behind when it fails
    }
  }
  document.body.dataset.diagrams = "done";
});
"""

_markdown = (
    MarkdownIt("commonmark", {"html": False, "linkify": True})
    .enable(["table", "strikethrough", "linkify"])
    .use(tasklists_plugin)
)
_default_fence = _markdown.renderer.rules["fence"]


def _fence(renderer, tokens, index, options, env):
    token = tokens[index]
    if token.info.strip().split()[:1] == ["mermaid"]:
        return f'<div class="mermaid-block"><pre class="mermaid">{escapeHtml(token.content)}</pre></div>\n'
    return _default_fence(tokens, index, options, env)


_markdown.add_render_rule("fence", _fence)


def render_html(markdown: str) -> str:
    """The whole page for `markdown`. mermaid.min.js is loaded relative to the page, from the app's assets."""
    return (
        '<!DOCTYPE html>\n<html><head><meta charset="utf-8">'
        f"<style>{_STYLE}</style>"
        '<script src="mermaid.min.js"></script>'
        f"<script>{_DIAGRAMS}</script>"
        f"</head>\n<body>{_markdown.render(markdown)}</body></html>"
    )
