# Large-PR mode

Use this file only when `plan.json` says `"mode": "split"`. It replaces SKILL.md Steps 3–7. Then continue at Step 8.

The split controls four risks:

| Risk | Control |
|---|---|
| An area's context gets too large | `plan_split.py` caps each area by size. An area agent reads only its own diff, plus 12 ranges or fewer outside it. |
| Claims are invented | Every ledger fact is cited. `check_ledgers.py` verifies each quote against git. |
| Links between areas get lost | The plan detects links. Both sides must answer each one, and the writer draws only `real` links. |
| Terms drift or areas contradict | One glossary seed is shared. The checker reports conflicting terms and disputed links, and the writer turns each one into a focus point. |

You are the **writer**. You hold the plan summary, the reasons and `merged.json`. Area agents hold the diffs. Read area diffs or source only in two cases: Step 4 docs, or 5 line ranges or fewer to settle a disputed link.

## S1. Prepare the work directory

The work directory is `<repo-root>/docs/pr-primers/.work/<id>/`.
1. Write `reasons.json` from SKILL.md Step 2, as `[{"id": "R1", "text": "...", "source": "PR body"}]`. With the no-reason banner, write `[]`.
2. If a ledger exists from an earlier run, keep it only if `plan.json` has the same head SHA and the ledger passes `check_ledgers.py --area <id>`. Delete every other ledger.

**Done when** `plan.json` and `reasons.json` exist, and `ledgers/` holds only valid ledgers for this head SHA.

## S2. Dispatch the area agents

Start one sub-agent for each area that has no valid ledger. Use the general-purpose sub-agent type, and run up to 4 at a time. Give each agent this prompt, with the values filled in:

```text
Read <skill-dir>/AREA-AGENT.md and follow it exactly.
Area: <id>, "<label>". Area diff: <diff path>.
Work directory: <work-dir>. Repository: <repo-root>.
Base: <base SHA>. Head: <head SHA>.
Repo glossary: <path to the repo CONTEXT.md or glossary, or "none">.
Write the ledger to: <work-dir>/ledgers/<id>.json.
```

If no sub-agent tool exists, work through the areas one at a time with the same brief. Before starting the next area, write the current ledger and check it. Record "sequential" in the build notes.

**Done when** every area has a ledger file, or its agent reported failure.

## S3. Check and repair

Run `python <skill-dir>/scripts/check_ledgers.py --work-dir <work-dir> --repo <repo-root>`.

If it reports errors, send each area's errors to that area's agent once and ask for a fix. Use the same agent if it is still available; otherwise start a fresh one with the errors added to the prompt. Run the checker again. If errors remain, run it with `--drop-invalid`. Dropped claims and unexplained files move to the build notes.

**Done when** the checker exits 0.

## S4. Write from the merged ledgers

Read `merged.json`. Then fill SKILL.md Steps 4–7 from it:

- **Architecture (Step 4):** read the docs as in Step 4. Give each area a node, and draw an edge only for links with status `real`, labelled with the contract. Every changed file belongs to an area node, so the Step 4 completion check holds.
- **Workflows (Step 5):** join same-named workflows from different areas into one. Chain workflows across areas only through `real` links. Keep the `internal_only` behaviour changes as listed.
- **What changed (Step 6 section):** group behaviour changes under one `<h3>` per area, in area order. Number them in one sequence across the whole primer. The writer may reword area-agent sentences, but adds no facts that are missing from `merged.json`.
- **Examples and tests (Steps 6–7):** copy them from the ledgers. Cite file and line from the ledger evidence.
- **Glossary:** for each entry in `term_conflicts`, choose one definition, and use that term everywhere. When the areas really mean different things, rename one term.
- **Reviewer focus points (Step 8):** add one point for each `disputed` link, each contract mismatch between two sides of a `real` link, and each unknown that touches a behaviour change.

Fill the build notes in the template: the split reason, the areas, the link counts, the unknowns, the dropped claims, and whether agents ran in parallel or one at a time.

**Done when** every behaviour change, real link, unknown and dropped claim in `merged.json` appears in the primer.
