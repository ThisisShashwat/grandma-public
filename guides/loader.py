"""Guides: Markdown files in content/guides/ become sanitized HTML, a table of contents and a reading time.

Pure Python, no Django. A page is found by looking its slug up in the dict of files that exist (slugs()), never by
joining the slug into a path, so nothing a visitor sends can reach a file outside content/guides/.
Widgets (the calculator, the demands list) are NOT handled here: the page keeps an empty `<div data-widget="name">`
and guides/widgets.py swaps in trusted markup after this module has sanitized the text.
"""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import frontmatter
import nh3
from markdown_it import MarkdownIt
from markdown_it.common.utils import escapeHtml
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.container import container_plugin
from pygments import highlight as pygments_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content" / "guides"
WORDS_PER_MINUTE = 200
CALLOUTS = ("tip", "warning", "note")

# What the sanitizer lets through. Everything else is stripped: scripts and styles with their content, event handlers,
# inline styles, unknown tags and attributes, and every URL scheme except these three.
TAGS = {"a", "b", "blockquote", "br", "code", "del", "details", "div", "em", "h1", "h2", "h3", "h4", "hr", "i", "img", "kbd", "li", "ol",
        "p", "pre", "s", "span", "strong", "sub", "summary", "table", "tbody", "td", "th", "thead", "tr", "ul"}
ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "div": {"data-widget"},
    "span": {"class", "data-slack"}, "pre": {"class"}, "code": {"class"},   # the Pygments highlighter writes the classes; data-slack is a channel placeholder (widgets.py)
    "h1": {"id"}, "h2": {"id"}, "h3": {"id"}, "h4": {"id"},      # the anchors plugin writes these
}
CLASSES = {"div": {"callout", *(f"callout--{name}" for name in CALLOUTS), "faq-answer"}, "p": {"callout-title"}, "details": {"faq-item"}}
SCHEMES = {"http", "https", "mailto"}


@dataclass(frozen=True)
class Heading:
    level: int
    id: str
    text: str


@dataclass(frozen=True)
class Guide:
    slug: str
    title: str
    order: int
    section: str
    summary: str
    widgets: tuple
    source: str       # only for text adapted from somewhere else (docs/guides.md has the licensing rules)
    license: str
    html: str         # sanitized; may still hold empty <div data-widget="..."> placeholders
    toc: tuple        # Headings, levels 2 and 3
    minutes: int


def _highlight(code, lang, attrs):
    """markdown-it calls this for fenced code. It must return a <pre ...> string, or "" to get the plain block."""
    try:
        lexer = get_lexer_by_name(lang)
    except ClassNotFound:
        return ""
    body = pygments_highlight(code, lexer, HtmlFormatter(nowrap=True))
    return f'<pre class="highlight"><code class="language-{lexer.aliases[0]}">{body}</code></pre>'


def _callout(name):
    def render(self, tokens, idx, options, env):
        if tokens[idx].nesting == -1:
            return "</div>\n"
        return f'<div class="callout callout--{name}"><p class="callout-title">{name.capitalize()}</p>\n'
    return render


def _faq(self, tokens, idx, options, env):
    """`::: faq Question text` ... `:::` is one expandable question (a <details>, closed, not exclusive: any number may be open).
    The question is plain text from the line itself, escaped here; the answer in between is ordinary Markdown."""
    if tokens[idx].nesting == -1:
        return "</div></details>\n"
    question = tokens[idx].info.strip().removeprefix("faq").strip()
    return f'<details class="faq-item"><summary>{escapeHtml(question)}</summary><div class="faq-answer">\n'


def _link_open(self, tokens, idx, options, env):
    """Links to other sites open in a new tab (nh3 adds rel="noopener noreferrer" to every link)."""
    if tokens[idx].attrGet("href").startswith("http"):
        tokens[idx].attrSet("target", "_blank")
    return self.renderToken(tokens, idx, options, env)


def _markdown():
    """GitHub-flavoured Markdown (tables, strikethrough), heading ids, ::: tip / warning / note callouts, ::: faq questions, highlighted code.
    Bare URLs are not turned into links (that needs linkify-it-py): write [text](url) or <url>."""
    md = MarkdownIt("gfm-like", {"linkify": False, "highlight": _highlight})
    md.use(anchors_plugin, min_level=2, max_level=4)
    for name in CALLOUTS:
        md.use(container_plugin, name=name, render=_callout(name))
    md.use(container_plugin, name="faq", render=_faq)
    md.add_render_rule("link_open", _link_open)
    return md


MD = _markdown()


def sanitize(html):
    return nh3.clean(html, tags=TAGS, attributes=ATTRIBUTES, allowed_classes=CLASSES, url_schemes=SCHEMES)


def _text(inline):
    return "".join(child.content for child in inline.children if child.type in ("text", "code_inline"))


def toc(tokens):
    return tuple(
        Heading(int(token.tag[1]), token.attrs["id"], _text(tokens[i + 1]))
        for i, token in enumerate(tokens)
        if token.type == "heading_open" and token.tag in ("h2", "h3")
    )


def minutes(html):
    """Reading time: the words in the page at 200 a minute, at least one minute."""
    words = len(nh3.clean(html, tags=set()).split())
    return max(1, round(words / WORDS_PER_MINUTE))


def render(markdown):
    """Markdown text to (sanitized HTML, table of contents)."""
    tokens = MD.parse(markdown)
    return sanitize(MD.renderer.render(tokens, MD.options, {})), toc(tokens)


@lru_cache(maxsize=None)
def _load(slug, path, mtime):
    """Parse and render one file. `mtime` only keys the cache: an edited file is a new key, so dev edits show at once."""
    post = frontmatter.load(path)
    meta = post.metadata
    html, headings = render(post.content)
    return Guide(
        slug=slug, title=meta["title"], order=meta["order"], section=meta["section"], summary=meta["summary"],
        widgets=tuple(meta.get("widgets", ())), source=meta.get("source", ""), license=meta.get("license", ""),
        html=html, toc=headings, minutes=minutes(html),
    )


def slugs(directory=None):
    """The guides that exist, {slug: path}. A slug is a file name without .md. `directory` is for tests."""
    return {path.stem: path for path in sorted(Path(directory or CONTENT_DIR).glob("*.md"))}


def _guide(slug, path):
    return _load(slug, str(path), path.stat().st_mtime_ns)


def get(slug, directory=None):
    """One guide, or None when no such file exists. The slug is only ever a dict key."""
    path = slugs(directory).get(slug)
    return None if path is None else _guide(slug, path)


def all_guides(directory=None):
    """Every guide in reading order (the `order` front matter)."""
    return sorted((_guide(slug, path) for slug, path in slugs(directory).items()), key=lambda guide: guide.order)


def sections(guides):
    """[(section name, [guides])], sections in the order they first appear."""
    grouped = {}
    for guide in guides:
        grouped.setdefault(guide.section, []).append(guide)
    return list(grouped.items())


def neighbours(guides, slug):
    """(previous, next) of a guide in reading order, None at either end."""
    i = [guide.slug for guide in guides].index(slug)
    return (guides[i - 1] if i else None, guides[i + 1] if i + 1 < len(guides) else None)
