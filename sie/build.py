#!/usr/bin/env python3
"""Build SIE notes from Obsidian vault into static HTML pages."""

import os
import re
import html
import shutil
from pathlib import Path

VAULT_DIR = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/Vault/SIE"
OUTPUT_DIR = Path(__file__).parent
IMAGES_SRC = VAULT_DIR / "Images"
IMAGES_DST = OUTPUT_DIR / "images"

STYLE = """\
body { font-family: 'Nunito', system-ui, sans-serif; margin: 0; padding: 0; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; }
h1, h2, h3 { margin: 1.2em 0 0.4em; }
h1 { font-size: 1.6em; }
h2 { font-size: 1.3em; }
a { color: #1a73e8; text-decoration: none; }
a:hover { text-decoration: underline; }
img { max-width: 100%; border-radius: 6px; margin: 12px 0; }
ul, ol { padding-left: 1.5em; }
li { margin: 4px 0; }
.nav { margin-bottom: 24px; font-size: 0.9em; }
.nav a { margin-right: 12px; }
.chapter-list { list-style: none; padding: 0; }
.chapter-list li { margin: 8px 0; }
.chapter-list a { font-size: 1.05em; }
#toggle { position: absolute; top: 10px; right: 20px; cursor: pointer; z-index: 2; }
body.dark { background: #1a1a1a; color: #ddd; }
body.dark a { color: #8cb4ff; }
body.dark img { border: 1px solid #333; }
"""

TOGGLE_SCRIPT = """\
<a id="toggle" onclick="document.body.classList.toggle('dark'); this.textContent = document.body.classList.contains('dark') ? 'light mode' : 'dark mode';">dark mode</a>
"""


def get_chapters():
    """Get sorted list of (number, title, filename) for all .md files."""
    chapters = []
    for f in VAULT_DIR.glob("*.md"):
        name = f.stem
        # Extract number prefix if present
        m = re.match(r"^(\d+)\.\s*(.+)$", name)
        if m:
            num = int(m.group(1))
            title = m.group(2).strip()
        else:
            num = 999
            title = name
        chapters.append((num, title, f.name, f))
    chapters.sort(key=lambda x: x[0])
    return chapters


def slug(filename):
    """Convert filename to URL-friendly slug."""
    name = Path(filename).stem
    s = re.sub(r"[^\w\s-]", "", name.lower())
    s = re.sub(r"[\s]+", "-", s.strip())
    return s


def convert_markdown(text):
    """Convert Obsidian-flavored markdown to HTML."""
    lines = text.split("\n")
    out = []
    in_list = False
    list_stack = []  # stack of (indent_level, list_type)

    for line in lines:

        # Check if this is a list item
        list_match = re.match(r"^(\t*)([-*]|\d+[.)]) (.*)$", line)

        if list_match:
            indent = len(list_match.group(1))
            marker = list_match.group(2)
            content = list_match.group(3)
            is_ordered = bool(re.match(r"\d+[.)]", marker))
            tag = "ol" if is_ordered else "ul"

            if not list_stack:
                out.append(f"<{tag}>")
                list_stack.append((indent, tag))
            elif indent > list_stack[-1][0]:
                out.append(f"<{tag}>")
                list_stack.append((indent, tag))
            else:
                while list_stack and indent < list_stack[-1][0]:
                    closing = list_stack.pop()
                    out.append(f"</{closing[1]}>")
                if list_stack and list_stack[-1][1] != tag:
                    closing = list_stack.pop()
                    out.append(f"</{closing[1]}>")
                    out.append(f"<{tag}>")
                    list_stack.append((indent, tag))

            content = inline_format(content)
            out.append(f"<li>{content}</li>")
            continue

        # Close any open lists
        while list_stack:
            closing = list_stack.pop()
            out.append(f"</{closing[1]}>")

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            content = inline_format(heading_match.group(2))
            out.append(f"<h{level}>{content}</h{level}>")
            continue

        # Empty line
        if line.strip() == "":
            out.append("")
            continue

        # Regular paragraph
        out.append(f"<p>{inline_format(line)}</p>")

    # Close any remaining lists
    while list_stack:
        closing = list_stack.pop()
        out.append(f"</{closing[1]}>")

    # Clean up excessive empty lines
    result = "\n".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


def inline_format(text):
    """Handle inline formatting: bold, italic, code, images."""
    # Extract image embeds first, replace with placeholders
    images = []
    def save_image(m):
        idx = len(images)
        name = m.group(1)
        images.append(f'<img src="images/{html.escape(name)}" alt="{html.escape(name)}">')
        return f"\x00IMG{idx}\x00"
    text = re.sub(r"!\[\[([^\]]+)\]\]", save_image, text)

    text = html.escape(text)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic (underscore)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<em>\1</em>", text)
    # Italic (asterisk)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    # Inline code
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)

    # Restore image placeholders
    for i, img_tag in enumerate(images):
        text = text.replace(f"\x00IMG{i}\x00", img_tag)
    return text


def wrap_html(title, body, back_link=True):
    """Wrap content in full HTML page."""
    nav = ""
    if back_link:
        nav = '<div class="nav"><a href="/sie/">&larr; All Chapters</a> · <a href="/">Home</a></div>'
    else:
        nav = '<div class="nav"><a href="/">Home</a></div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" type="image/x-icon">
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;700&display=swap" rel="stylesheet">
<title>{html.escape(title)} - SIE Notes</title>
<style>
{STYLE}
</style>
</head>
<body>
{TOGGLE_SCRIPT}
{nav}
{body}
</body>
</html>
"""


def build():
    # Copy images
    if IMAGES_SRC.exists():
        IMAGES_DST.mkdir(exist_ok=True)
        for img in IMAGES_SRC.iterdir():
            shutil.copy2(img, IMAGES_DST / img.name)
        print(f"Copied {len(list(IMAGES_SRC.iterdir()))} images")

    chapters = get_chapters()

    # Build index page
    items = []
    for num, title, filename, path in chapters:
        s = slug(filename)
        display = f"{num}. {title}" if num != 999 else title
        items.append(f'<li><a href="/sie/{s}.html">{html.escape(display)}</a></li>')

    index_body = f"""<h1>SIE Exam Notes</h1>
<p>Securities Industry Essentials study notes.</p>
<ul class="chapter-list">
{"".join(items)}
</ul>
"""
    index_html = wrap_html("SIE Exam Notes", index_body, back_link=False)
    (OUTPUT_DIR / "index.html").write_text(index_html)
    print("Built index.html")

    # Build each chapter page
    for i, (num, title, filename, path) in enumerate(chapters):
        s = slug(filename)
        md_content = path.read_text()
        html_content = convert_markdown(md_content)

        display = f"{num}. {title}" if num != 999 else title

        # Prev/next navigation
        nav_links = []
        if i > 0:
            prev_slug = slug(chapters[i - 1][2])
            prev_title = chapters[i - 1][1]
            nav_links.append(f'<a href="/sie/{prev_slug}.html">&larr; {html.escape(prev_title)}</a>')
        if i < len(chapters) - 1:
            next_slug = slug(chapters[i + 1][2])
            next_title = chapters[i + 1][1]
            nav_links.append(f'<a href="/sie/{next_slug}.html">{html.escape(next_title)} &rarr;</a>')

        bottom_nav = ""
        if nav_links:
            bottom_nav = '<div class="nav" style="margin-top: 32px; border-top: 1px solid #ddd; padding-top: 16px;">' + " · ".join(nav_links) + "</div>"

        body = f"<h1>{html.escape(display)}</h1>\n{html_content}\n{bottom_nav}"
        page_html = wrap_html(display, body)
        (OUTPUT_DIR / f"{s}.html").write_text(page_html)
        print(f"Built {s}.html")

    print(f"\nDone! Built {len(chapters)} chapters + index.")


if __name__ == "__main__":
    build()
