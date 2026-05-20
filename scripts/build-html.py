#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "markdown-it-py>=3.0.0",
#   "mdit-py-plugins>=0.4.0",
#   "PyYAML>=6.0",
# ]
# ///
"""Build HTML pages from knowledge/**/*.md.

Protocol (see knowledge/_template.md):
- Frontmatter: title, date, tags, status (draft|wip|complete)
- Body: standard markdown + GitHub admonitions (> [!NOTE] / [!TIP] / [!WARNING] / [!IMPORTANT] / [!CAUTION])
- The first H1 is dropped (rendered from frontmatter)
- The first blockquote right after H1, if it looks like "key：value" meta lines, is hoisted to a meta block
- The first paragraph after that becomes the lead
- Internal links: *.md → *.html ; trailing "/" → "/README.html"
"""

from __future__ import annotations

import argparse
import datetime as dt
import html as html_lib
import re
import string
import sys
import unicodedata
from pathlib import Path

import yaml
from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.anchors import anchors_plugin

REPO_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"
TEMPLATE_DIR = Path(__file__).resolve().parent / "html-template"

ADMONITION_KINDS = {"note", "tip", "warning", "important", "caution"}
META_KEY_RE = re.compile(r"^[一-龥A-Za-z][一-龥A-Za-z0-9 _·]*[：:]\s*")
DATE_KEY_RE = re.compile(r"^日期[：:]")


# --------------------------------------------------------------------------- #
# Frontmatter
# --------------------------------------------------------------------------- #

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def split_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"invalid frontmatter: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data, text[m.end():]


# --------------------------------------------------------------------------- #
# Slug
# --------------------------------------------------------------------------- #

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).strip().lower()
    out = []
    for ch in text:
        if ch.isalnum() or "一" <= ch <= "鿿":
            out.append(ch)
        elif ch in " -_":
            out.append("-")
    slug = "".join(out)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "section"


# --------------------------------------------------------------------------- #
# Token utilities
# --------------------------------------------------------------------------- #

def inline_plain_text(tok: Token) -> str:
    """Best-effort plain-text extraction from an inline token's children."""
    if not tok.children:
        return tok.content
    parts = []
    for c in tok.children:
        if c.type == "text" or c.type == "code_inline":
            parts.append(c.content)
        elif c.type == "softbreak":
            parts.append("\n")
        elif c.type == "hardbreak":
            parts.append("\n")
    return "".join(parts)


def find_close(tokens: list[Token], start: int, open_type: str, close_type: str) -> int:
    depth = 1
    i = start + 1
    while i < len(tokens):
        if tokens[i].type == open_type:
            depth += 1
        elif tokens[i].type == close_type:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"unmatched {open_type}")


# --------------------------------------------------------------------------- #
# Strip leading H1 (we render title from frontmatter)
# --------------------------------------------------------------------------- #

def strip_first_h1(tokens: list[Token]) -> list[Token]:
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.tag == "h1":
            close = find_close(tokens, i, "heading_open", "heading_close")
            return tokens[:i] + tokens[close + 1:]
        # Stop scanning once we leave the doc preamble.
        if tok.type == "heading_open":
            break
    return tokens


# --------------------------------------------------------------------------- #
# Extract meta blockquote (key:value lines, hoisted to header)
# --------------------------------------------------------------------------- #

def extract_meta_blockquote(tokens: list[Token]) -> tuple[list[tuple[str, str]] | None, list[Token]]:
    """If the first block (after optional hr) is a key:value blockquote, hoist it.

    Returns (entries, remaining_tokens). entries is a list of (key, value).
    The 日期 entry is filtered out (already in frontmatter date).
    """
    i = 0
    # Skip leading hr / blank
    while i < len(tokens) and tokens[i].type == "hr":
        i += 1
    if i >= len(tokens) or tokens[i].type != "blockquote_open":
        return None, tokens
    bq_start = i
    bq_end = find_close(tokens, i, "blockquote_open", "blockquote_close")

    # Reject if blockquote contains an admonition marker
    inner_text_parts = []
    for tok in tokens[bq_start + 1:bq_end]:
        if tok.type == "inline":
            inner_text_parts.append(inline_plain_text(tok))
    inner_text = "\n".join(inner_text_parts).strip()
    if not inner_text:
        return None, tokens
    if re.match(r"^\[!(NOTE|TIP|WARNING|IMPORTANT|CAUTION)\]", inner_text, re.IGNORECASE):
        return None, tokens

    lines = [ln.strip() for ln in inner_text.split("\n") if ln.strip()]
    if not lines:
        return None, tokens
    if not all(META_KEY_RE.match(ln) for ln in lines):
        return None, tokens

    entries: list[tuple[str, str]] = []
    for ln in lines:
        if DATE_KEY_RE.match(ln):
            continue
        key, _, val = ln.partition("：") if "：" in ln else ln.partition(":")
        entries.append((key.strip(), val.strip()))

    # Consume the blockquote, plus an immediately-following hr if present.
    after = bq_end + 1
    while after < len(tokens) and tokens[after].type == "hr":
        after += 1
    return entries, tokens[:bq_start] + tokens[after:]


# --------------------------------------------------------------------------- #
# Extract lead paragraph
# --------------------------------------------------------------------------- #

def extract_lead_paragraph(tokens: list[Token]) -> tuple[list[Token] | None, list[Token]]:
    i = 0
    while i < len(tokens) and tokens[i].type == "hr":
        i += 1
    if i + 2 < len(tokens) and tokens[i].type == "paragraph_open":
        # Only treat as lead if next is a heading, not another paragraph
        # (otherwise we'd strip arbitrary opening text). Require the paragraph
        # to be reasonably short (< 280 chars).
        close = find_close(tokens, i, "paragraph_open", "paragraph_close")
        inline = tokens[i + 1]
        if inline.type == "inline" and len(inline_plain_text(inline)) < 280:
            # check that there's a heading following soon
            j = close + 1
            saw_heading = False
            scan = 0
            while j < len(tokens) and scan < 4:
                if tokens[j].type == "heading_open":
                    saw_heading = True
                    break
                if tokens[j].type == "paragraph_open":
                    break
                j += 1
                scan += 1
            if saw_heading:
                lead_tokens = tokens[i:close + 1]
                return lead_tokens, tokens[:i] + tokens[close + 1:]
    return None, tokens


# --------------------------------------------------------------------------- #
# Transform admonitions: > [!NOTE] ... → <div class="admonition note">
# --------------------------------------------------------------------------- #

ADMONITION_OPEN_RE = re.compile(
    r"^\[!(NOTE|TIP|WARNING|IMPORTANT|CAUTION)\]\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)


def transform_admonitions(tokens: list[Token]) -> list[Token]:
    out = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "blockquote_open":
            close = find_close(tokens, i, "blockquote_open", "blockquote_close")
            # Inspect first inline child
            first_inline_idx = None
            for j in range(i + 1, close):
                if tokens[j].type == "inline":
                    first_inline_idx = j
                    break
            if first_inline_idx is not None:
                first_text = inline_plain_text(tokens[first_inline_idx]).lstrip()
                m = ADMONITION_OPEN_RE.match(first_text)
                if m:
                    kind = m.group(1).lower()
                    # Strip the [!KIND] marker from the first inline token's children.
                    inline_tok = tokens[first_inline_idx]
                    _strip_admonition_marker(inline_tok)

                    # Emit a synthetic html_block opening + inner blockquote body + closing.
                    open_html = Token("html_block", "", 0)
                    open_html.content = (
                        f'<div class="admonition {kind}">'
                        f'<div class="admonition-title">{kind.capitalize()}</div>\n'
                    )
                    close_html = Token("html_block", "", 0)
                    close_html.content = "</div>\n"
                    out.append(open_html)
                    # Recurse into the inner tokens (in case of nested admonitions, unlikely)
                    inner = transform_admonitions(tokens[i + 1:close])
                    out.extend(inner)
                    out.append(close_html)
                    i = close + 1
                    continue
        out.append(tok)
        i += 1
    return out


def _strip_admonition_marker(inline_tok: Token) -> None:
    """Remove the leading [!KIND] (and following whitespace/break) from inline children."""
    children = inline_tok.children or []
    # Find leading text child
    if not children:
        inline_tok.content = ADMONITION_OPEN_RE.sub(r"\2", inline_tok.content.lstrip())
        return
    # Strip marker from first text child
    first = children[0]
    if first.type == "text":
        new = ADMONITION_OPEN_RE.sub(r"\2", first.content.lstrip())
        first.content = new
        # Drop a leading softbreak/hardbreak if marker consumed entire first text
        if not first.content and len(children) > 1 and children[1].type in {"softbreak", "hardbreak"}:
            inline_tok.children = children[2:]
        elif not first.content:
            inline_tok.children = children[1:]


# --------------------------------------------------------------------------- #
# Link rewriting: .md → .html ; trailing / → /README.html
# --------------------------------------------------------------------------- #

LINK_REWRITE_RE = re.compile(r"^([^#?]*?)(\.md)(#[^?]*)?$", re.IGNORECASE)


def rewrite_href(href: str) -> str:
    if href.startswith(("http://", "https://", "mailto:", "#")):
        return href
    # Trailing slash → README.html
    if href.endswith("/"):
        return href + "README.html"
    m = LINK_REWRITE_RE.match(href)
    if m:
        return m.group(1) + ".html" + (m.group(3) or "")
    return href


def install_link_rewriter(md: MarkdownIt) -> None:
    renderer = md.renderer

    def link_open(tokens, idx, options, env):
        tok = tokens[idx]
        if "href" in tok.attrs:
            tok.attrs["href"] = rewrite_href(tok.attrs["href"])
        return renderer.renderToken(tokens, idx, options, env)

    md.renderer.rules["link_open"] = link_open


# --------------------------------------------------------------------------- #
# Build TOC from H2/H3
# --------------------------------------------------------------------------- #

def build_toc(tokens: list[Token]) -> list[dict]:
    toc = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open" and tok.tag in ("h2", "h3"):
            inline = tokens[i + 1]
            text = inline_plain_text(inline).strip()
            anchor = tok.attrs.get("id") or slugify(text)
            toc.append({"level": int(tok.tag[1]), "text": text, "id": anchor})
        i += 1
    return toc


def render_toc(toc: list[dict]) -> str:
    if len(toc) < 3:
        return ""
    items = []
    for entry in toc:
        cls = "toc-l2" if entry["level"] == 2 else "toc-l3"
        items.append(
            f'<li class="{cls}"><a href="#{html_lib.escape(entry["id"])}">{html_lib.escape(entry["text"])}</a></li>'
        )
    body = "\n".join(items)
    return (
        '<aside class="toc collapsible">'
        '<details open>'
        '<summary>目录</summary>'
        '<div class="toc-body">'
        '<div class="toc-title">目录</div>'
        f'<ol>{body}</ol>'
        '</div></details></aside>'
    )


# --------------------------------------------------------------------------- #
# Renderer
# --------------------------------------------------------------------------- #

def make_md() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": True, "linkify": False, "breaks": False})
    md.enable("table")
    md.enable("strikethrough")
    md.use(
        anchors_plugin,
        max_level=4,
        slug_func=slugify,
        permalink=True,
        permalinkSymbol="#",
        permalinkSpace=False,
    )
    install_link_rewriter(md)
    return md


# --------------------------------------------------------------------------- #
# Frontmatter rendering
# --------------------------------------------------------------------------- #

STATUS_LABELS = {
    "draft": "draft",
    "wip": "wip",
    "complete": "complete",
}


def render_meta_inline(date: str, tags: list[str], status: str) -> str:
    parts = []
    if date:
        parts.append(f'<span class="date">{html_lib.escape(str(date))}</span>')
    if tags:
        for tag in tags:
            parts.append(f'<span class="tag-chip">{html_lib.escape(str(tag))}</span>')
    if status:
        st = str(status).lower()
        label = STATUS_LABELS.get(st, st)
        parts.append(f'<span class="status status-{html_lib.escape(st)}">{html_lib.escape(label)}</span>')
    return "\n        ".join(parts)


def render_meta_extra(entries: list[tuple[str, str]] | None) -> str:
    if not entries:
        return ""
    rows = []
    for k, v in entries:
        rows.append(f"<dt>{html_lib.escape(k)}</dt><dd>{html_lib.escape(v)}</dd>")
    return f'    <div class="doc-meta-extra"><dl>{"".join(rows)}</dl></div>'


# --------------------------------------------------------------------------- #
# Main per-file
# --------------------------------------------------------------------------- #

def build_one(md_path: Path, template: string.Template, style_css: str) -> Path:
    raw = md_path.read_text(encoding="utf-8")
    front, body = split_frontmatter(raw)

    title = front.get("title") or md_path.stem
    date = front.get("date") or ""
    tags = front.get("tags") or []
    status = (front.get("status") or "draft").lower()

    md = make_md()
    tokens = md.parse(body)
    tokens = strip_first_h1(tokens)
    meta_entries, tokens = extract_meta_blockquote(tokens)
    lead_tokens, tokens = extract_lead_paragraph(tokens)
    tokens = transform_admonitions(tokens)

    toc = build_toc(tokens)
    toc_html = render_toc(toc)
    main_class = "" if toc_html else "no-toc"

    body_html = md.renderer.render(tokens, md.options, {})
    lead_html = ""
    if lead_tokens:
        lead_inner = md.renderer.render(lead_tokens, md.options, {})
        lead_inner = lead_inner.replace("<p>", "", 1)
        if lead_inner.endswith("</p>\n"):
            lead_inner = lead_inner[: -len("</p>\n")]
        elif lead_inner.endswith("</p>"):
            lead_inner = lead_inner[: -len("</p>")]
        lead_html = f'    <div class="lead">{lead_inner.strip()}</div>'

    source_rel = md_path.relative_to(REPO_ROOT).as_posix()
    built_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    out_html = template.safe_substitute(
        LANG="zh-CN",
        TITLE=html_lib.escape(str(title)),
        STYLE=style_css,
        MAIN_CLASS=main_class,
        META_INLINE=render_meta_inline(date, tags, status),
        META_EXTRA=render_meta_extra(meta_entries),
        LEAD=lead_html,
        BODY=body_html.rstrip(),
        TOC=toc_html,
        SOURCE_PATH=html_lib.escape(source_rel),
        BUILT_AT=built_at,
    )

    out_path = md_path.with_suffix(".html")
    out_path.write_text(out_html, encoding="utf-8")
    return out_path


# --------------------------------------------------------------------------- #
# Entry
# --------------------------------------------------------------------------- #

def iter_md_files(root: Path) -> list[Path]:
    files = []
    for p in sorted(root.rglob("*.md")):
        if p.name == "_template.md":
            continue
        files.append(p)
    return files


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Build HTML pages from knowledge markdown.")
    ap.add_argument("paths", nargs="*", help="Specific .md files (default: all under knowledge/)")
    ap.add_argument("--check", action="store_true", help="Verify each .md has up-to-date .html (no write).")
    args = ap.parse_args(argv)

    template_text = (TEMPLATE_DIR / "base.html").read_text(encoding="utf-8")
    style_css = (TEMPLATE_DIR / "style.css").read_text(encoding="utf-8")
    template = string.Template(template_text)

    if args.paths:
        targets = [Path(p).resolve() for p in args.paths]
    else:
        targets = iter_md_files(KNOWLEDGE_DIR)

    if not targets:
        print("[build-html] no markdown files found", file=sys.stderr)
        return 1

    failures = 0
    for md_path in targets:
        try:
            out = build_one(md_path, template, style_css)
            print(f"[build-html] {md_path.relative_to(REPO_ROOT)} -> {out.relative_to(REPO_ROOT)}")
        except Exception as e:
            failures += 1
            print(f"[build-html] FAIL {md_path}: {e}", file=sys.stderr)
    if failures:
        print(f"[build-html] {failures} file(s) failed", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
