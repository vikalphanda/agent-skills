"""Render Mermaid diagrams in HTML files to inline SVG using mmdc,
while preserving the Mermaid source in a collapsible details block.

Usage: python render_diagrams.py <file.html> [...]
If mmdc is not installed or fails on a diagram, keeps the fallback and exits 1.
"""
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile


def get_mmdc_path():
    cmd = shutil.which("mmdc")
    if not cmd:
        for candidate in ["mmdc.cmd", "mmdc.exe", "mmdc.ps1", "mmdc"]:
            c = shutil.which(candidate)
            if c:
                return c
    return cmd


def render_mermaid_to_svg(mmdc_bin, mermaid_text, diag_id):
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = os.path.join(tmpdir, f"diag_{diag_id}.mmd")
        out_path = os.path.join(tmpdir, f"diag_{diag_id}.svg")

        with open(in_path, "w", encoding="utf-8") as f:
            f.write(mermaid_text)

        cmd = [mmdc_bin, "-i", in_path, "-o", out_path, "-b", "white"]
        res = subprocess.run(cmd, capture_output=True, text=True, shell=True)

        if res.returncode != 0 or not os.path.exists(out_path):
            print(f"  [Error] mmdc failed on diagram {diag_id}:", file=sys.stderr)
            print(res.stderr or res.stdout, file=sys.stderr)
            return None

        with open(out_path, "r", encoding="utf-8") as f:
            svg_content = f.read()

        # Strip XML declaration or doctype if present
        svg_content = re.sub(r"<\?xml.*?\?>", "", svg_content)
        svg_content = re.sub(r"<!DOCTYPE.*?>", "", svg_content)
        return svg_content.strip()


def process_html_file(path, mmdc_bin):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(r'<pre\s+class=["\']mermaid["\']\s*>(.*?)</pre>', re.DOTALL | re.IGNORECASE)
    matches = list(pattern.finditer(content))

    if not matches:
        print(f"{path}: No Mermaid diagrams found.")
        return True

    print(f"{path}: Found {len(matches)} Mermaid diagram(s). Rendering with mmdc...")

    replacements = []
    for idx, match in enumerate(matches, start=1):
        mermaid_src = match.group(1).strip()
        # Unescape HTML entities if any were escaped
        raw_mermaid = html.unescape(mermaid_src)

        svg = render_mermaid_to_svg(mmdc_bin, raw_mermaid, idx)
        if not svg:
            return False

        escaped_src = html.escape(raw_mermaid)
        replacement = (
            f'{svg}\n'
            f'<details class="diagram-src">\n'
            f'  <summary>Diagram source (Mermaid)</summary>\n'
            f'  <pre><code>{escaped_src}</code></pre>\n'
            f'</details>'
        )
        replacements.append((match.start(), match.end(), replacement))

    # Apply replacements from back to front to keep offsets valid
    new_content = content
    for start, end, rep in reversed(replacements):
        new_content = new_content[:start] + rep + new_content[end:]

    # Remove the client-side Mermaid <script> tags since diagrams are inlined
    new_content = re.sub(
        r'<script\b[^>]*>.*?import\s+mermaid\s+from.*?mermaid\.initialize.*?</script>',
        '<!-- Mermaid diagrams pre-rendered to inline SVG by pr-primer -->',
        new_content,
        flags=re.DOTALL | re.IGNORECASE
    )

    # Ensure diagram-src CSS is present in <style>
    if '.diagram-src' not in new_content:
        extra_css = (
            '\n  .diagram svg{max-width:100%;height:auto;display:block;margin:auto}\n'
            '  .diagram-src{margin-top:8px;font-size:0.85em}\n'
            '  .diagram-src summary{cursor:pointer;color:var(--muted);font-weight:500}\n'
            '  .diagram-src pre{margin:6px 0 0;padding:8px;background:var(--card)}\n'
        )
        new_content = new_content.replace('</style>', f'{extra_css}</style>', 1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"{path}: Successfully replaced {len(matches)} diagram(s) with inline SVG + editable source.")
    return True


def main(paths):
    if not paths:
        print(__doc__)
        return 2

    mmdc_bin = get_mmdc_path()
    if not mmdc_bin:
        print("Error: mmdc (@mermaid-js/mermaid-cli) is not installed or not on PATH.", file=sys.stderr)
        return 1

    success = True
    for p in paths:
        if not os.path.exists(p):
            print(f"File not found: {p}", file=sys.stderr)
            success = False
            continue
        if not process_html_file(p, mmdc_bin):
            success = False

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
