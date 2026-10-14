"""Validate Mermaid diagram syntax in HTML and Markdown files.

Usage: python validate_mermaid.py <file.html|file.md> [...]
Exit 0 when clean, 1 when any diagram fails validation.
"""
import re
import sys
from html.parser import HTMLParser

KNOWN_DIAGRAM_TYPES = (
    "flowchart", "graph", "sequenceDiagram", "classDiagram",
    "stateDiagram", "stateDiagram-v2", "erDiagram", "gantt",
    "pie", "gitGraph", "journey", "mindmap", "timeline", "quadrantChart"
)

BLOCK_START_KEYWORDS = {"loop", "alt", "opt", "par", "critical", "rect", "subgraph"}


class MermaidExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_mermaid = False
        self.diagrams = []
        self.buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            classes = dict(attrs).get("class", "").split()
            if "mermaid" in classes:
                self.in_mermaid = True
                self.buf = []

    def handle_endtag(self, tag):
        if tag == "pre" and self.in_mermaid:
            self.in_mermaid = False
            self.diagrams.append("".join(self.buf).strip())
            self.buf = []

    def handle_data(self, data):
        if self.in_mermaid:
            self.buf.append(data)


def extract_from_html(text):
    parser = MermaidExtractor()
    parser.feed(text)
    return parser.diagrams


def extract_from_md(text):
    return [m.strip() for m in re.findall(r"```mermaid\s*\n(.*?)\n```", text, re.DOTALL)]


def validate_diagram(diagram, diag_idx):
    errors = []
    lines = [ln.strip() for ln in diagram.splitlines() if ln.strip() and not ln.strip().startswith("%%")]

    if not lines:
        return [f"Diagram #{diag_idx}: Empty diagram"]

    header = lines[0].split()[0]
    if header not in KNOWN_DIAGRAM_TYPES:
        return [f"Diagram #{diag_idx}: Unknown diagram type '{header}'. Expected one of: {', '.join(KNOWN_DIAGRAM_TYPES)}"]

    diag_type = header

    if diag_type in ("flowchart", "graph"):
        if len(lines[0].split()) < 2:
            errors.append(f"Diagram #{diag_idx}: Flowchart missing direction (e.g. 'flowchart LR' or 'flowchart TD')")
        for line_no, line in enumerate(lines[1:], start=2):
            if line.startswith("classDef") or line.startswith("class ") or line.startswith("linkStyle"):
                continue
            # Check for unquoted dots or slashes in raw node IDs
            # E.g., 'TraceRoute.cpp --> Something' where TraceRoute.cpp is unquoted
            arrow_parts = re.split(r"\s*(?:-->|---|==>|-\.->)\s*", line)
            for part in arrow_parts:
                part = part.strip()
                # Check for raw node ID that contains a dot or slash outside quotes/brackets
                m_raw = re.match(r"^([A-Za-z0-9_\-\.\/]+)(?:\[|\(|\{|$)", part)
                if m_raw:
                    node_id = m_raw.group(1)
                    if ("." in node_id or "/" in node_id) and not (node_id.startswith('"') or node_id.startswith("'")):
                        errors.append(
                            f"Diagram #{diag_idx}, line {line_no}: Node ID '{node_id}' contains '.' or '/'. "
                            f"Node IDs must be alphanumeric; put filenames in labels: NodeID[\"{node_id}\"]"
                        )
            # Check for unquoted parentheses or brackets inside labels
            unquoted_labels = re.findall(r'\[([^"\'\[\]]+)\]', line)
            for lbl in unquoted_labels:
                if any(c in lbl for c in ("(", ")", "/", ":", ";")):
                    errors.append(
                        f"Diagram #{diag_idx}, line {line_no}: Label '[{lbl}]' contains special characters. "
                        f"Wrap label in double quotes: [\"{lbl}\"]"
                    )

    elif diag_type == "sequenceDiagram":
        block_stack = []
        for line_no, line in enumerate(lines[1:], start=2):
            tokens = line.split()
            first = tokens[0] if tokens else ""

            if first in BLOCK_START_KEYWORDS:
                block_stack.append((first, line_no))
            elif first == "else":
                if not block_stack or block_stack[-1][0] != "alt":
                    errors.append(f"Diagram #{diag_idx}, line {line_no}: 'else' without preceding 'alt'")
            elif first == "end":
                if not block_stack:
                    errors.append(f"Diagram #{diag_idx}, line {line_no}: 'end' without matching block start")
                else:
                    block_stack.pop()

            # Semicolon in sequence message acts as command delimiter and breaks parsing
            if ":" in line and not line.startswith("autonumber"):
                msg = line.split(":", 1)[1]
                if ";" in msg:
                    errors.append(
                        f"Diagram #{diag_idx}, line {line_no}: Semicolon ';' in sequence message '{msg.strip()}'. "
                        f"Semicolons act as statement separators in Mermaid. Replace with comma or hyphen."
                    )

            # Check participant alias for unquoted slashes or parentheses
            if first == "participant":
                if " as " in line:
                    alias = line.split(" as ", 1)[1].strip()
                    if any(c in alias for c in ("/", "(", ")", ";")) and not (alias.startswith('"') and alias.endswith('"')):
                        errors.append(
                            f"Diagram #{diag_idx}, line {line_no}: Participant alias '{alias}' contains special characters. "
                            f"Wrap in double quotes: participant {tokens[1]} as \"{alias}\""
                        )

        if block_stack:
            for unclosed, start_line in block_stack:
                errors.append(f"Diagram #{diag_idx}: Unclosed '{unclosed}' block started on line {start_line}")

    return errors


def check_file(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()

    if path.lower().endswith((".html", ".htm")):
        diagrams = extract_from_html(text)
    else:
        diagrams = extract_from_md(text)

    all_errors = []
    for idx, diag in enumerate(diagrams, start=1):
        errs = validate_diagram(diag, idx)
        all_errors.extend(errs)

    return diagrams, all_errors


def main(paths):
    if not paths:
        print(__doc__)
        return 2

    failed = False
    for path in paths:
        diagrams, errors = check_file(path)
        count = len(diagrams)
        if not errors:
            print(f"{path}: OK ({count} diagram{'s' if count != 1 else ''})")
        else:
            print(f"{path}: {len(errors)} error(s) in {count} diagram(s)")
            for err in errors:
                print(f"  - {err}")
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
