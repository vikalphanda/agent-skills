"""Check PR Primer prose against the Plain-English Style length rules.

Usage: python check_style.py <file.html|file.md> [...]
Exit 0 when clean, 1 when any sentence breaks a rule.
Text inside code, pre, script, style, svg, tables, and Mermaid fences is exempt.
"""
import re
import sys
from html.parser import HTMLParser

MAX_WORDS = 20
MAX_SENTENCES_PER_PARA = 6
EXEMPT_TAGS = {"code", "pre", "script", "style", "svg", "table", "summary", "dt"}
BLOCK_TAGS = {"p", "li", "dd", "div", "h1", "h2", "h3", "h4", "td", "th", "br", "section", "header", "footer"}
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9`\"(])")


class ProseExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.paras = []
        self.buf = []

    def flush(self):
        text = " ".join("".join(self.buf).split())
        if text:
            self.paras.append(text)
        self.buf = []

    def handle_starttag(self, tag, attrs):
        if tag in EXEMPT_TAGS:
            self.depth += 1
            self.buf.append(" CODE ")
        elif tag in BLOCK_TAGS and self.depth == 0:
            self.flush()

    def handle_endtag(self, tag):
        if tag in EXEMPT_TAGS:
            self.depth = max(0, self.depth - 1)
        elif tag in BLOCK_TAGS and self.depth == 0:
            self.flush()

    def handle_data(self, data):
        if self.depth == 0:
            self.buf.append(data)


def html_paras(text):
    p = ProseExtractor()
    p.feed(text)
    p.flush()
    return p.paras


def md_paras(text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`[^`]*`", "CODE", text)
    paras, buf = [], []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(("|", "#")) or re.match(r"^([-*]|\d+\.)\s", s):
            if buf:
                paras.append(" ".join(buf))
                buf = []
            if re.match(r"^([-*]|\d+\.)\s", s):
                paras.append(re.sub(r"^([-*]|\d+\.)\s+", "", s))
            continue
        buf.append(s)
    if buf:
        paras.append(" ".join(buf))
    return paras


def check(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    paras = html_paras(text) if path.lower().endswith((".html", ".htm")) else md_paras(text)
    problems = []
    for para in paras:
        sentences = [s for s in SENTENCE_SPLIT.split(para) if s.strip()]
        if len(sentences) > MAX_SENTENCES_PER_PARA:
            problems.append(f"paragraph has {len(sentences)} sentences (max {MAX_SENTENCES_PER_PARA}): {para[:80]}...")
        for s in sentences:
            words = re.findall(r"[A-Za-z0-9][\w'’/-]*", s)
            if len(words) > MAX_WORDS:
                problems.append(f"{len(words)} words (max {MAX_WORDS}): {s}")
    return problems


def main(paths):
    if not paths:
        print(__doc__)
        return 2
    failed = False
    for path in paths:
        problems = check(path)
        status = "OK" if not problems else f"{len(problems)} problem(s)"
        print(f"{path}: {status}")
        for p in problems:
            print(f"  - {p}")
        failed |= bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
