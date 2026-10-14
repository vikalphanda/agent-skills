#!/usr/bin/env python3
"""Build a deterministic Area Split plan for a PR Primer.

Usage:
  python plan_split.py --base <sha> --head <sha> --work-dir <dir> [--repo <path>]
                       [--exclude <glob> ...] [--force-split]

Writes <work-dir>/plan.json and one <work-dir>/areas/<id>.diff per area.
The same inputs always give the same plan. No model judgement is involved.

plan.json "mode" is "single" when the PR fits one context, else "split".
Exit codes: 0 = plan written, 2 = git or argument error.
"""
import argparse
import fnmatch
import json
import math
import os
import re
import subprocess
import sys
from collections import defaultdict

# Split when any limit is exceeded.
SPLIT_FILES = 40
SPLIT_LINES = 1500
SPLIT_TOKENS = 40000
# Each area must fit these limits (except a single oversized file).
AREA_TOKENS = 25000
AREA_FILES = 25
CHARS_PER_TOKEN = 3.5
MAX_LINK_NAMES_PER_PAIR = 10
MAX_LINK_EVIDENCE = 3

DEFAULT_EXCLUDES = [
    "*.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "go.sum", "Cargo.lock",
    "poetry.lock", "packages.lock.json", "Gemfile.lock", "composer.lock",
    "vendor/*", "*/vendor/*", "node_modules/*", "*/node_modules/*", "third_party/*", "*/third_party/*",
    "*.min.js", "*.min.css", "*.map", "*.pb.go", "*_pb2.py", "*_pb2_grpc.py", "*.g.cs", "*.g.i.cs",
    "*.Designer.cs", "*.generated.*", "*_generated.*", "zz_generated*", "*/zz_generated*",
    "*.snap", "__snapshots__/*", "*/__snapshots__/*", "docs/pr-primers/*",
]

TEST_SEGMENTS = {"test", "tests", "__tests__", "spec", "specs", "testing", "unittests",
                 "unittest", "integrationtests", "functionaltests", "e2e", "testdata"}
TEST_SEGMENT_SUFFIXES = (".tests", ".test", ".unittests", ".unittest", ".integrationtests",
                         ".functionaltests", "_test", "_tests")
TEST_FILE_RE = re.compile(
    r"(^test_.*\.py$|_test\.(go|py|rb|exs?)$|\.(test|spec)\.[jt]sx?$|_spec\.rb$|"
    r"tests?\.(cs|java|kt|scala|fs|vb)$|^test.*\.(java|kt)$)",
    re.IGNORECASE,
)
GENERIC_STEMS = {"index", "main", "utils", "util", "types", "type", "init", "__init__", "mod",
                 "common", "helpers", "helper", "constants", "const", "config", "readme",
                 "test", "tests", "base", "models", "model", "errors", "error", "app", "program",
                 "startup", "setup", "build", "makefile", "dockerfile", "license", "changelog"}
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def git(repo, *args):
    proc = subprocess.run(["git", "-C", repo, "-c", "core.quotepath=off", *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        sys.stderr.write(f"git {' '.join(args)} failed: {proc.stderr.strip()}\n")
        sys.exit(2)
    return proc.stdout


def tokens(text):
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def parse_diff(text):
    """Split a unified diff into per-file records."""
    files = []
    chunks = re.split(r"(?m)^(?=diff --git )", text)
    for chunk in chunks:
        if not chunk.startswith("diff --git "):
            continue
        lines = chunk.splitlines()
        rec = {"path": None, "old_path": None, "status": "modified", "binary": False,
               "added": 0, "deleted": 0, "text": chunk, "changed": []}
        new_ln = old_ln = 0
        in_hunk = False
        for line in lines:
            if not in_hunk:
                if line.startswith("new file mode"):
                    rec["status"] = "added"
                elif line.startswith("deleted file mode"):
                    rec["status"] = "deleted"
                elif line.startswith("rename from "):
                    rec["old_path"] = line[len("rename from "):]
                    rec["status"] = "renamed"
                elif line.startswith("rename to "):
                    rec["path"] = line[len("rename to "):]
                elif line.startswith("--- a/"):
                    rec["old_path"] = rec["old_path"] or line[6:]
                elif line.startswith("+++ "):
                    if line.startswith("+++ b/"):
                        rec["path"] = line[6:]
                elif line.startswith("Binary files") or line.startswith("GIT binary patch"):
                    rec["binary"] = True
            m = HUNK_RE.match(line)
            if m:
                in_hunk = True
                old_ln, new_ln = int(m.group(1)), int(m.group(3))
                continue
            if not in_hunk:
                continue
            if line.startswith("+"):
                rec["added"] += 1
                rec["changed"].append(("head", new_ln, line[1:]))
                new_ln += 1
            elif line.startswith("-"):
                rec["deleted"] += 1
                rec["changed"].append(("base", old_ln, line[1:]))
                old_ln += 1
            elif line.startswith("\\"):
                pass
            else:
                new_ln += 1
                old_ln += 1
        if rec["path"] is None:
            rec["path"] = rec["old_path"]
        if rec["path"] is None:
            m = re.match(r"diff --git a/(.+) b/(.+)$", lines[0])
            rec["path"] = m.group(2) if m else lines[0][11:]
        if rec["status"] == "deleted" and rec["old_path"] is None:
            rec["old_path"] = rec["path"]
        if rec["status"] == "modified":
            rec["old_path"] = None
        files.append(rec)
    return files


def excluded_reason(path, binary, globs):
    if binary:
        return "binary"
    base = os.path.basename(path)
    for g in globs:
        if fnmatch.fnmatch(path, g) or fnmatch.fnmatch(base, g):
            return f"matches {g}"
    return None


def is_test(path):
    segs = path.lower().split("/")
    if any(s in TEST_SEGMENTS or s.endswith(TEST_SEGMENT_SUFFIXES) for s in segs[:-1]):
        return True
    return bool(TEST_FILE_RE.search(segs[-1]))


def group_key(path):
    """Directory segments with test markers removed, so tests sit with their code."""
    segs = path.split("/")[:-1]
    key = []
    for s in segs:
        low = s.lower()
        if low in TEST_SEGMENTS:
            continue
        for suf in TEST_SEGMENT_SUFFIXES:
            if low.endswith(suf):
                s = s[: -len(suf)]
                break
        if s:
            key.append(s)
    return tuple(key)


def weight(files):
    return sum(f["tokens"] for f in files)


def fits(files):
    return weight(files) <= AREA_TOKENS and len(files) <= AREA_FILES


def pack(files):
    """Greedy pack in path order; an oversized single file gets its own area."""
    out, cur = [], []
    for f in sorted(files, key=lambda r: r["path"]):
        if cur and not fits(cur + [f]):
            out.append(cur)
            cur = []
        cur.append(f)
    if cur:
        out.append(cur)
    return out


def is_small(files):
    return weight(files) < AREA_TOKENS / 2 and len(files) < AREA_FILES / 2


def merge_small(chunks):
    """Join neighbouring chunks only when both are small, so a focused area keeps its own agent."""
    out = []
    for c in chunks:
        if out and is_small(out[-1]) and is_small(c) and fits(out[-1] + c):
            out[-1] = out[-1] + c
        else:
            out.append(c)
    return out


def test_stem(path):
    name = os.path.basename(path).split(".")[0]
    for pat in (r"^test_", r"_test$", r"_spec$", r"Tests?$", r"^Test"):
        stripped = re.sub(pat, "", name)
        if stripped and stripped != name:
            return stripped
    return name


def attach_tests(groups, tests):
    """Put each test in the area of the code it tests: same stem first, then the longest shared path."""
    stem_area, leftovers = {}, []
    for i, g in enumerate(groups):
        for f in g:
            stem_area.setdefault(os.path.basename(f["path"]).split(".")[0], i)
    for t in sorted(tests, key=lambda r: r["path"]):
        target = stem_area.get(test_stem(t["path"]))
        if target is None:
            tkey = [s.lower() for s in t["key"]]
            best, best_score = None, 0
            for i, g in enumerate(groups):
                for f in g:
                    fkey = [s.lower() for s in f["key"]]
                    score = sum(1 for s in tkey if s in fkey)
                    if score > best_score:
                        best, best_score = i, score
            target = best
        if target is not None and weight(groups[target] + [t]) <= AREA_TOKENS * 1.5:
            groups[target].append(t)
        else:
            leftovers.append(t)
    return groups + (build(leftovers, 0) if leftovers else [])


def build(files, depth):
    if fits(files):
        return [files]
    buckets, here = defaultdict(list), []
    for f in files:
        (buckets[f["key"][depth]] if len(f["key"]) > depth else here).append(f)
    if not buckets:
        return pack(here)
    if len(buckets) == 1 and not here:
        return build(files, depth + 1)
    chunks = pack(here) if here else []
    for name in sorted(buckets):
        chunks.extend(build(buckets[name], depth + 1))
    return merge_small(chunks)


def common_dir(paths):
    parts = [p.split("/")[:-1] for p in paths]
    prefix = []
    for segs in zip(*parts):
        if all(s == segs[0] for s in segs):
            prefix.append(segs[0])
        else:
            break
    return "/".join(prefix)


def area_label(files):
    dirs = sorted({os.path.dirname(f["path"]) or "(repo root)" for f in files})
    if len(dirs) <= 3:
        return " + ".join(dirs)
    root = common_dir([f["path"] for f in files])
    depth = len(root.split("/")) if root else 0
    subs = sorted({f["path"].split("/")[depth] for f in files if len(f["path"].split("/")) > depth + 1})
    shown = ",".join(subs[:3]) + (",…" if len(subs) > 3 else "")
    return f"{root or '(repo root)'}/{{{shown}}}"


def find_links(areas):
    stem_owner = defaultdict(set)
    for a in areas:
        for f in a["_files"]:
            if f["is_test"]:
                continue
            stem = os.path.basename(f["path"]).split(".")[0]
            if len(stem) >= 4 and stem.lower() not in GENERIC_STEMS:
                stem_owner[stem].add(a["id"])
    if not stem_owner:
        return []
    pattern = re.compile(r"\b(" + "|".join(sorted(map(re.escape, stem_owner), key=len, reverse=True)) + r")\b")
    hits = defaultdict(lambda: {"count": 0, "evidence": []})
    for a in areas:
        for f in a["_files"]:
            for rev, ln, text in f["changed"]:
                for name in set(pattern.findall(text)):
                    for owner in sorted(stem_owner[name]):
                        if owner == a["id"]:
                            continue
                        h = hits[(a["id"], owner, name)]
                        h["count"] += 1
                        if len(h["evidence"]) < MAX_LINK_EVIDENCE:
                            path = f["old_path"] if rev == "base" and f["old_path"] else f["path"]
                            h["evidence"].append({"path": path, "rev": rev, "line": ln})
    by_pair = defaultdict(list)
    for (consumer, provider, name), h in hits.items():
        by_pair[(consumer, provider)].append((name, h))
    links = []
    for (consumer, provider) in sorted(by_pair):
        ranked = sorted(by_pair[(consumer, provider)], key=lambda x: (-x[1]["count"], x[0]))
        for name, h in ranked[:MAX_LINK_NAMES_PER_PAIR]:
            links.append({"id": f"L{len(links) + 1:02d}", "consumer": consumer, "provider": provider,
                          "name": name, "hits": h["count"], "evidence": h["evidence"]})
    return links


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="merge-base SHA the diff starts from")
    ap.add_argument("--head", required=True)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--exclude", action="append", default=[], help="extra glob to set aside")
    ap.add_argument("--force-split", action="store_true", help="split even under the limits (testing)")
    args = ap.parse_args()

    base = git(args.repo, "rev-parse", args.base).strip()
    head = git(args.repo, "rev-parse", args.head).strip()
    diff = git(args.repo, "diff", "-M", "-U3", "--no-color", "--no-ext-diff", base, head)
    records = parse_diff(diff)

    globs = DEFAULT_EXCLUDES + args.exclude
    excluded, included = [], []
    for r in records:
        reason = excluded_reason(r["path"], r["binary"], globs)
        if reason:
            excluded.append({"path": r["path"], "reason": reason})
            continue
        r["tokens"] = tokens(r["text"])
        r["is_test"] = is_test(r["path"])
        r["key"] = group_key(r["path"])
        included.append(r)

    total_lines = sum(r["added"] + r["deleted"] for r in included)
    total_tokens = weight(included)
    reasons = []
    if len(included) > SPLIT_FILES:
        reasons.append(f"{len(included)} files > {SPLIT_FILES}")
    if total_lines > SPLIT_LINES:
        reasons.append(f"{total_lines} changed lines > {SPLIT_LINES}")
    if total_tokens > SPLIT_TOKENS:
        reasons.append(f"~{total_tokens} diff tokens > {SPLIT_TOKENS}")
    if args.force_split:
        reasons.append("forced")
    mode = "split" if reasons else "single"

    if mode == "split" and included:
        sources = [r for r in included if not r["is_test"]]
        tests = [r for r in included if r["is_test"]]
        groups = build(sources, 0) if sources else []
        groups = attach_tests(groups, tests) if groups else build(tests, 0)
    else:
        groups = [included] if included else []
    if mode == "split" and len(groups) < 2:
        mode, reasons = "single", reasons + ["only one area after grouping"]

    areas = []
    for i, g in enumerate(groups, 1):
        g = sorted(g, key=lambda r: r["path"])
        areas.append({"id": f"A{i:02d}", "label": area_label(g), "_files": g})
    links = find_links(areas) if mode == "split" else []

    areas_dir = os.path.join(args.work_dir, "areas")
    os.makedirs(areas_dir, exist_ok=True)
    for name in os.listdir(areas_dir):
        if name.endswith(".diff"):
            os.remove(os.path.join(areas_dir, name))

    out_areas = []
    for a in areas:
        files = a["_files"]
        diff_path = os.path.join(areas_dir, f"{a['id']}.diff")
        with open(diff_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("".join(f["text"] for f in files))
        out_areas.append({
            "id": a["id"], "label": a["label"], "diff": os.path.abspath(diff_path),
            "tokens": weight(files), "added": sum(f["added"] for f in files),
            "deleted": sum(f["deleted"] for f in files),
            "oversize": len(files) == 1 and not fits(files),
            "files": [{"path": f["path"], "old_path": f["old_path"], "status": f["status"],
                       "added": f["added"], "deleted": f["deleted"], "tokens": f["tokens"],
                       "is_test": f["is_test"]} for f in files],
        })

    plan = {
        "version": 1, "base": base, "head": head, "mode": mode, "reason": "; ".join(reasons) or "under all limits",
        "limits": {"split_files": SPLIT_FILES, "split_lines": SPLIT_LINES, "split_tokens": SPLIT_TOKENS,
                   "area_tokens": AREA_TOKENS, "area_files": AREA_FILES},
        "totals": {"files": len(included), "added": sum(r["added"] for r in included),
                   "deleted": sum(r["deleted"] for r in included), "diff_tokens": total_tokens,
                   "excluded": len(excluded)},
        "excluded": excluded, "areas": out_areas, "links": links,
    }
    plan_path = os.path.join(args.work_dir, "plan.json")
    with open(plan_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(plan, fh, indent=1)

    t = plan["totals"]
    print(f"mode: {mode} ({plan['reason']})")
    print(f"files: {t['files']} (+{t['added']}/-{t['deleted']}, ~{t['diff_tokens']} tokens), set aside: {t['excluded']}")
    for a in out_areas:
        flag = " OVERSIZE" if a["oversize"] else ""
        print(f"  {a['id']} {a['label']}: {len(a['files'])} files, ~{a['tokens']} tokens{flag}")
    print(f"links: {len(links)}")
    print(f"plan: {os.path.abspath(plan_path)}")


if __name__ == "__main__":
    main()
