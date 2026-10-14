#!/usr/bin/env python3
"""Check and merge Area Ledgers for a split PR Primer.

Usage:
  python check_ledgers.py --work-dir <dir> [--repo <path>] [--drop-invalid]

Reads <work-dir>/plan.json, <work-dir>/reasons.json and <work-dir>/ledgers/<id>.json.
Writes <work-dir>/merged.json and prints errors and warnings.

Checks:
  - every area has a ledger with the required shape;
  - every planned file is owned by exactly one ledger entry, and no ledger claims another area's file;
  - every citation exists at its revision, its lines are in range, and its quote appears in those lines;
  - every Stated reason points at a reason id in reasons.json;
  - every Behaviour Change has evidence, a test row, an example, and a workflow (or internal_only);
  - every planned Area Link is answered by both its consumer and provider ledgers;
  - glossary terms with different definitions are reported for the writer to reconcile.

--drop-invalid removes claims whose citations fail, records them under "dropped",
and turns the resulting gaps into warnings. Use it only after one repair attempt.

Exit codes: 0 = merged with no errors, 1 = errors remain, 2 = missing inputs.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

REQUIRED = ["area", "head_sha", "files", "behaviour_changes", "mechanical", "workflows",
            "examples", "tests", "links", "terms", "unknowns"]
STATUSES = {"Covered", "Partly", "Untested"}
MAX_LEDGER_CHARS = 16000
_blob_cache = {}


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def blob(repo, rev, path):
    key = (rev, path)
    if key not in _blob_cache:
        proc = subprocess.run(["git", "-C", repo, "show", f"{rev}:{path}"], capture_output=True)
        _blob_cache[key] = proc.stdout.decode("utf-8", "replace").splitlines() if proc.returncode == 0 else None
    return _blob_cache[key]


def norm(text):
    return re.sub(r"\s+", " ", text).strip()


def parse_lines(spec):
    if isinstance(spec, int):
        return spec, spec
    m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", str(spec))
    if not m:
        return None
    a = int(m.group(1))
    b = int(m.group(2) or a)
    return (a, b) if a <= b else None


class Checker:
    def __init__(self, repo, plan, reasons, drop):
        self.repo, self.plan, self.drop = repo, plan, drop
        self.revs = {"head": plan["head"], "base": plan["base"]}
        self.reason_ids = {r["id"] for r in reasons}
        self.errors, self.warnings, self.dropped = [], [], []

    def err(self, msg):
        self.errors.append(msg)

    def cite_problem(self, ev):
        if not isinstance(ev, dict) or not ev.get("path") or not ev.get("quote"):
            return "citation needs path, lines and quote"
        rev = ev.get("rev", "head")
        if rev not in self.revs:
            return f"rev must be head or base, got {rev!r}"
        rng = parse_lines(ev.get("lines"))
        if not rng:
            return f"bad lines {ev.get('lines')!r}"
        content = blob(self.repo, self.revs[rev], ev["path"])
        if content is None:
            return f"{ev['path']} does not exist at {rev}"
        a, b = rng
        if a < 1 or b > len(content):
            return f"{ev['path']}:{a}-{b} outside 1-{len(content)} at {rev}"
        if b - a > 200:
            return f"{ev['path']}:{a}-{b} spans more than 200 lines"
        if norm(ev["quote"]) not in norm(" ".join(content[a - 1:b])):
            return f"quote not found in {ev['path']}:{a}-{b} at {rev}: {ev['quote'][:60]!r}"
        return None

    def filter_evidence(self, where, items):
        """Return valid citations; report or drop the rest."""
        good = []
        for ev in items or []:
            problem = self.cite_problem(ev)
            if problem is None:
                good.append(ev)
            elif self.drop:
                self.dropped.append({"where": where, "reason": problem})
            else:
                self.err(f"{where}: {problem}")
        return good

    def check_ledger(self, area, led):
        aid = area["id"]
        missing = [k for k in REQUIRED if k not in led]
        if missing:
            self.err(f"{aid}: ledger missing keys {missing}")
            return None
        if led["area"] != aid:
            self.err(f"{aid}: ledger area is {led['area']!r}")
        led_sha = str(led["head_sha"]).strip().lower()
        if len(led_sha) < 7 or not self.plan["head"].startswith(led_sha):
            self.err(f"{aid}: ledger head_sha {led['head_sha']!r} does not match plan head")

        behaviours = {}
        for b in led["behaviour_changes"]:
            bid = b.get("id", "")
            where = f"{aid}/{bid or '?'}"
            if not re.fullmatch(rf"{aid}-B\d+", bid):
                self.err(f"{where}: id must look like {aid}-B1")
                continue
            if bid in behaviours:
                self.err(f"{where}: duplicate id")
                continue
            for field in ("title", "what"):
                if not b.get(field):
                    self.err(f"{where}: missing {field}")
            why = b.get("why") or {}
            if why.get("kind") == "stated":
                if why.get("reason_id") not in self.reason_ids:
                    if self.drop:
                        self.dropped.append({"where": where, "reason": f"unknown reason_id {why.get('reason_id')!r}; downgraded to inferred"})
                        b["why"] = {"kind": "inferred", "basis": "no verified stated reason"}
                    else:
                        self.err(f"{where}: stated why must use a reason_id from reasons.json")
            elif why.get("kind") == "inferred":
                if not why.get("basis"):
                    self.err(f"{where}: inferred why needs a basis")
            else:
                self.err(f"{where}: why.kind must be stated or inferred")
            b["evidence"] = self.filter_evidence(where, b.get("evidence"))
            if not b["evidence"]:
                if self.drop:
                    self.dropped.append({"where": where, "reason": "behaviour change has no valid citation"})
                    continue
                self.err(f"{where}: needs at least one citation")
            behaviours[bid] = b
        led["behaviour_changes"] = list(behaviours.values())

        planned = {f["path"] for f in area["files"]}
        owned = {}
        for entry in led["files"]:
            path = entry.get("path")
            changes = entry.get("changes")
            if path not in planned:
                self.err(f"{aid}: claims {path!r}, which is not in this area")
                continue
            if path in owned:
                self.err(f"{aid}: {path} listed twice")
            if changes == "mechanical":
                pass
            elif isinstance(changes, list) and changes:
                known = [c for c in changes if c in behaviours]
                if len(known) != len(changes):
                    unknown = sorted(set(changes) - set(known))
                    if self.drop:
                        self.warnings.append(f"{aid}: {path} refers to dropped or unknown {unknown}")
                    else:
                        self.err(f"{aid}: {path} refers to unknown behaviour ids {unknown}")
                if not known:
                    changes = "unexplained"
                    entry["changes"] = changes
            else:
                self.err(f"{aid}: {path} needs changes = list of behaviour ids or \"mechanical\"")
            owned[path] = changes
        for path in sorted(planned - set(owned)):
            self.err(f"{aid}: file not accounted for: {path}")
        for path, changes in owned.items():
            if changes == "unexplained":
                self.warnings.append(f"{aid}: {path} has no verified explanation after drops")

        for i, m in enumerate(led["mechanical"]):
            if not m.get("summary") or not m.get("paths"):
                self.err(f"{aid}/mechanical[{i}]: needs summary and paths")

        test_rows, example_rows = defaultdict(int), defaultdict(int)
        kept_tests = []
        for i, t in enumerate(led["tests"]):
            bid, where = t.get("behaviour_id"), f"{aid}/tests[{i}]"
            if bid not in behaviours:
                if not self.drop:
                    self.err(f"{where}: unknown behaviour_id {bid!r}")
                continue
            if t.get("status") not in STATUSES:
                self.err(f"{where}: status must be one of {sorted(STATUSES)}")
            if t.get("status") in ("Covered", "Partly"):
                t["evidence"] = self.filter_evidence(where, t.get("evidence"))
                if not t["evidence"]:
                    if self.drop:
                        t["status"] = "Untested"
                        t["note"] = "test citation failed verification"
                    else:
                        self.err(f"{where}: Covered/Partly needs a cited test")
            test_rows[bid] += 1
            kept_tests.append(t)
        led["tests"] = kept_tests

        kept_examples = []
        for i, e in enumerate(led["examples"]):
            bid, where = e.get("behaviour_id"), f"{aid}/examples[{i}]"
            if bid not in behaviours:
                if not self.drop:
                    self.err(f"{where}: unknown behaviour_id {bid!r}")
                continue
            if not all(e.get(k) for k in ("input", "before", "after")):
                self.err(f"{where}: needs input, before, after")
            if not e.get("illustrative"):
                e["evidence"] = self.filter_evidence(where, e.get("evidence"))
                if not e["evidence"]:
                    if self.drop:
                        e["illustrative"] = True
                    else:
                        self.err(f"{where}: cite a test or fixture, or set illustrative: true")
            example_rows[bid] += 1
            kept_examples.append(e)
        led["examples"] = kept_examples

        in_workflow = set()
        for w in led["workflows"]:
            if not w.get("name") or not w.get("steps_after"):
                self.err(f"{aid}/workflow {w.get('name')!r}: needs name and steps_after")
            in_workflow.update(w.get("behaviour_ids", []))
        for bid, b in behaviours.items():
            if not test_rows[bid]:
                self.err(f"{aid}/{bid}: needs a test row (Untested is allowed)")
            if not example_rows[bid]:
                self.err(f"{aid}/{bid}: needs an example")
            if bid not in in_workflow and not b.get("internal_only"):
                self.err(f"{aid}/{bid}: add it to a workflow or set internal_only: true")

        for i, link in enumerate(led["links"]):
            where = f"{aid}/links[{i}]"
            if link.get("direction") not in ("consumes", "provides"):
                self.err(f"{where}: direction must be consumes or provides")
            if link.get("verdict") not in ("real", "incidental"):
                self.err(f"{where}: verdict must be real or incidental")
            if link.get("verdict") == "real":
                if not link.get("contract"):
                    self.err(f"{where}: real link needs a contract")
                link["evidence"] = self.filter_evidence(where, link.get("evidence"))
                if not link["evidence"]:
                    if self.drop:
                        link["verdict"] = "unverified"
                    else:
                        self.err(f"{where}: real link needs a citation")

        for i, t in enumerate(led["terms"]):
            if not t.get("term") or not t.get("definition"):
                self.err(f"{aid}/terms[{i}]: needs term and definition")
        return led


def link_answer(led, link, side):
    """Find the ledger entry that answers a planned link from one side."""
    if not led:
        return None
    direction = "consumes" if side == "consumer" else "provides"
    other = link["provider"] if side == "consumer" else link["consumer"]
    for entry in led["links"]:
        if entry.get("link_id") == link["id"]:
            return entry
    for entry in led["links"]:
        if (entry.get("direction") == direction and entry.get("other_area") == other
                and link["name"].lower() in str(entry.get("name", "")).lower()):
            return entry
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--drop-invalid", action="store_true")
    ap.add_argument("--area", help="check one area's ledger only; does not write merged.json")
    args = ap.parse_args()

    plan_path = os.path.join(args.work_dir, "plan.json")
    reasons_path = os.path.join(args.work_dir, "reasons.json")
    for p in (plan_path, reasons_path):
        if not os.path.exists(p):
            print(f"missing {p}", file=sys.stderr)
            sys.exit(2)
    plan, reasons = load(plan_path), load(reasons_path)
    chk = Checker(args.repo, plan, reasons, args.drop_invalid)

    ledgers = {}
    areas = [a for a in plan["areas"] if not args.area or a["id"] == args.area]
    if args.area and not areas:
        print(f"unknown area {args.area}", file=sys.stderr)
        sys.exit(2)
    for area in areas:
        path = os.path.join(args.work_dir, "ledgers", f"{area['id']}.json")
        if not os.path.exists(path):
            chk.err(f"{area['id']}: ledger missing at {path}")
            continue
        if os.path.getsize(path) > MAX_LEDGER_CHARS:
            chk.warnings.append(f"{area['id']}: ledger is {os.path.getsize(path)} chars; keep it under {MAX_LEDGER_CHARS}")
        try:
            led = load(path)
        except json.JSONDecodeError as exc:
            chk.err(f"{area['id']}: invalid JSON: {exc}")
            continue
        led = chk.check_ledger(area, led)
        if led:
            ledgers[area["id"]] = led

    link_table = []
    for link in plan["links"]:
        if args.area and args.area not in (link["consumer"], link["provider"]):
            continue
        c = link_answer(ledgers.get(link["consumer"]), link, "consumer")
        p = link_answer(ledgers.get(link["provider"]), link, "provider")
        for side, ans, aid in (("consumer", c, link["consumer"]), ("provider", p, link["provider"])):
            if ans is None and aid in ledgers:
                chk.err(f"{aid}: planned link {link['id']} ({link['name']}) not answered as {side}")
        verdicts = {(c or {}).get("verdict"), (p or {}).get("verdict")} - {None}
        if verdicts == {"incidental"}:
            status = "incidental"
        elif "real" in verdicts and "incidental" in verdicts:
            status = "disputed"
            chk.warnings.append(f"{link['id']} {link['name']}: one side says real, the other incidental")
        elif verdicts == {"real"}:
            status = "real"
        else:
            status = "unverified"
        link_table.append({"id": link["id"], "name": link["name"], "consumer": link["consumer"],
                           "provider": link["provider"], "status": status,
                           "consumer_contract": (c or {}).get("contract"),
                           "provider_contract": (p or {}).get("contract")})

    glossary = defaultdict(list)
    for aid, led in ledgers.items():
        for t in led["terms"]:
            if t.get("term"):
                glossary[t["term"].strip().lower()].append({"area": aid, "term": t["term"], "definition": t["definition"]})
    term_conflicts = []
    for key, defs in sorted(glossary.items()):
        if len({norm(d["definition"]).lower() for d in defs}) > 1:
            term_conflicts.append(key)
            chk.warnings.append(f"term {defs[0]['term']!r} has {len(defs)} different definitions")

    unknowns = [{"area": aid, "text": u} for aid, led in ledgers.items() for u in led["unknowns"]]
    merged = {
        "base": plan["base"], "head": plan["head"], "reason": plan["reason"], "totals": plan["totals"],
        "excluded": plan["excluded"],
        "areas": [{"id": a["id"], "label": a["label"], "files": len(a["files"]), "added": a["added"],
                   "deleted": a["deleted"]} for a in plan["areas"]],
        "reasons": reasons, "ledgers": ledgers, "links": link_table,
        "glossary": [{"key": k, "entries": v} for k, v in sorted(glossary.items())],
        "term_conflicts": term_conflicts, "unknowns": unknowns, "dropped": chk.dropped,
        "errors": chk.errors, "warnings": chk.warnings,
    }
    for e in chk.errors:
        print(f"ERROR {e}")
    for w in chk.warnings:
        print(f"WARN  {w}")
    for d in chk.dropped:
        print(f"DROP  {d['where']}: {d['reason']}")
    if args.area:
        print(f"area {args.area}: errors: {len(chk.errors)}, warnings: {len(chk.warnings)}")
        sys.exit(1 if chk.errors else 0)

    out = os.path.join(args.work_dir, "merged.json")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(merged, fh, indent=1)
    real = sum(1 for l in link_table if l["status"] == "real")
    print(f"areas: {len(ledgers)}/{len(plan['areas'])}, behaviour changes: "
          f"{sum(len(l['behaviour_changes']) for l in ledgers.values())}, real links: {real}/{len(link_table)}, "
          f"errors: {len(chk.errors)}, warnings: {len(chk.warnings)}, dropped: {len(chk.dropped)}")
    print(f"merged: {os.path.abspath(out)}")
    sys.exit(1 if chk.errors else 0)


if __name__ == "__main__":
    main()
