#!/usr/bin/env python3
"""Generate README.md and index.html with emoji listings."""

import html
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

PER_ROW = 10
EMOJI_DIR = Path("emoji")
EXTENSIONS = (".png", ".gif", ".jpg", ".jpeg")


def generate_readme(files: list[Path]) -> None:
    """Generate README.md with HTML tables of all emoji images."""
    listing = defaultdict(list)
    for file in files:
        first_char = file.name[0].lower()
        if not re.match(r"[a-z]", first_char):
            first_char = r"\[^a-zA-Z:\]"
        listing[first_char].append(file)

    per_row_width = f"{100 // PER_ROW}%"
    contents = "# Emotes\n\n"

    for header in sorted(listing.keys(), key=lambda x: (not x.startswith("\\"), x)):
        icons = listing[header]
        contents += f"## {header}\n\n"
        contents += '<table style="text-align: center;width: 100%">\n'

        for i in range(0, len(icons), PER_ROW):
            chunk = icons[i:i + PER_ROW]
            contents += "<tr>\n"

            for icon in chunk:
                name = icon.stem
                encoded_path = f"emoji/{quote(icon.name)}"
                display_path = f"emoji/{icon.name}"

                contents += (
                    f"<td style='width: {per_row_width}'>"
                    f"<img width='30' src=\"{encoded_path}\" "
                    f"alt=\"{display_path}\" title=\":{name}:\"></td>\n"
                )

            contents += "</tr>\n"

        contents += "</table>\n\n"

    contents += f"\n\n Generated: {datetime.now(timezone.utc).isoformat()}"

    Path("README.md").write_text(contents, encoding="utf-8")
    print(f"Generated README.md with {len(files)} emojis")


def generate_html(files: list[Path]) -> None:
    """Generate index.html with searchable emoji grid grouped alphabetically."""
    # Group files by first character
    listing = defaultdict(list)
    for file in files:
        first_char = file.name[0].lower()
        if not re.match(r"[a-z]", first_char):
            first_char = "#"
        listing[first_char].append(file)

    # Build grouped HTML
    sections = []
    for header in sorted(listing.keys(), key=lambda x: (x != "#", x)):
        display_header = "0-9 / Special" if header == "#" else header.upper()
        emoji_items = []
        for file in listing[header]:
            name = file.stem
            encoded_path = f"emoji/{quote(file.name)}"
            escaped_name = html.escape(name)
            emoji_items.append(
                f'      <div class="emoji" data-keyword="{escaped_name}">'
                f'<img src="{encoded_path}" alt="{escaped_name}" title=":{escaped_name}:"></div>'
            )
        sections.append(
            f'    <section data-group="{html.escape(header)}">\n'
            f'      <h2>{display_header}</h2>\n'
            f'      <div class="grid">\n{chr(10).join(emoji_items)}\n      </div>\n'
            f'    </section>'
        )

    contents = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Emotes</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      margin: 0;
      padding: 20px;
      background: #1a1a1a;
      color: #fff;
    }}
    #search {{
      width: 100%;
      max-width: 400px;
      padding: 12px 16px;
      font-size: 16px;
      border: 2px solid #333;
      border-radius: 8px;
      background: #2a2a2a;
      color: #fff;
      margin-bottom: 20px;
    }}
    #search:focus {{
      outline: none;
      border-color: #666;
    }}
    #search::placeholder {{
      color: #888;
    }}
    section {{
      margin-bottom: 24px;
    }}
    section.hidden {{
      display: none;
    }}
    h2 {{
      font-size: 18px;
      font-weight: 600;
      margin: 0 0 12px 0;
      color: #ccc;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(50px, 1fr));
      gap: 8px;
    }}
    .emoji {{
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 8px;
      background: #2a2a2a;
      border-radius: 6px;
      transition: background 0.15s;
    }}
    .emoji:hover {{
      background: #3a3a3a;
    }}
    .emoji img {{
      width: 32px;
      height: 32px;
      object-fit: contain;
    }}
    .emoji.hidden {{
      display: none;
    }}
    #count {{
      color: #888;
      font-size: 14px;
      margin-bottom: 12px;
    }}
    h1 {{
      margin: 0 0 20px 0;
      font-size: 24px;
    }}
    h1 a {{
      color: #fff;
      text-decoration: none;
    }}
    h1 a:hover {{
      text-decoration: underline;
    }}
  </style>
</head>
<body>
  <h1><a href="https://github.com/ivuorinen/emoji">ivuorinen/emoji</a></h1>
  <input type="text" id="search" placeholder="Search emojis..." autofocus>
  <div id="count">{len(files)} emojis</div>
  <div id="content">
{chr(10).join(sections)}
  </div>
  <script>
    let timeout;
    const search = document.getElementById('search');
    const emojis = document.querySelectorAll('.emoji');
    const sections = document.querySelectorAll('section');
    const count = document.getElementById('count');
    const total = emojis.length;

    search.addEventListener('input', function(e) {{
      clearTimeout(timeout);
      timeout = setTimeout(() => {{
        const query = e.target.value.toLowerCase();
        let visible = 0;
        emojis.forEach(el => {{
          const match = el.dataset.keyword.toLowerCase().includes(query);
          el.classList.toggle('hidden', !match);
          if (match) visible++;
        }});
        sections.forEach(sec => {{
          const hasVisible = sec.querySelector('.emoji:not(.hidden)');
          sec.classList.toggle('hidden', !hasVisible);
        }});
        count.textContent = query ? visible + ' of ' + total + ' emojis' : total + ' emojis';
      }}, 150);
    }});
  </script>
</body>
</html>
'''

    Path("index.html").write_text(contents, encoding="utf-8")
    print(f"Generated index.html with {len(files)} emojis")


def main():
    files = sorted(
        f for f in EMOJI_DIR.iterdir()
        if f.suffix.lower() in EXTENSIONS
    )

    if not files:
        raise SystemExit("No images to continue with.")

    generate_readme(files)
    generate_html(files)


if __name__ == "__main__":
    main()
