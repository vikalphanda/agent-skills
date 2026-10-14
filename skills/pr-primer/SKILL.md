---
name: pr-primer
description: Write a PR Primer, a plain-English pre-review explainer of a code change (why, architecture, workflows, walkthrough, examples, test coverage) as HTML + Markdown. Use when the user wants a PR, branch, or diff explained for reviewers, or says "primer".
---

A **PR Primer** explains one change to a reviewer with no prior context. It _explains_; it never gives an approve/reject verdict (that is the `code-review` skill's job). Terms in **bold** are defined in [CONTEXT.md](CONTEXT.md).

## Help: return before starting work

If the arguments contain `--help`, show the usage and examples below in chat, then stop.
This takes precedence over every other argument, including `--run-tests`.
Help requires no repository, PR, or authentication. Do not inspect a repository, fetch PR data, run commands or tests, create todos, or generate, edit, or copy files.

```text
/pr-primer <PR URL | PR number | branch>             Generate HTML primer and Markdown summary
/pr-primer                                         Use the current branch against its base
/pr-primer <PR URL> --poster                        Also generate a one-page HTML poster
/pr-primer <PR URL> --md-only                       Generate only the Markdown summary
/pr-primer <PR URL> --md-only --poster              Generate the summary and HTML poster
/pr-primer <PR URL> --run-tests                     Run the mapped tests and record their results
/pr-primer <PR URL> --poster-only "<primer.html>"   Generate only a poster from the existing HTML primer
/pr-primer --help                                  Show usage; do not generate files
```

Explain that normal outputs go in `docs\pr-primers\` (use the host's path separators).
Large PRs are split into areas automatically; no flag is needed.
Poster-only output goes beside the supplied primer and leaves the primer and summary unchanged.
It requires matching PR identity and base/head SHAs. Mention that generated HTML is also copied to the folder in the `PR_PRIMER_MIRROR_DIR` environment variable when it is set.

Usage:

- `/pr-primer [<PR URL | PR number | branch>] [--run-tests] [--md-only] [--poster]`
- `/pr-primer <PR URL | PR number> --poster-only "<path-to-existing-primer.html>"`

No source argument = current branch against its base.

`--poster` adds a one-page **PR Poster** alongside the normal outputs. With `--md-only --poster`, write the Markdown summary and HTML poster, but skip the full HTML primer.
`--poster-only` requires an existing HTML primer path after the flag. It reads that file as the evidence source and generates only the poster.
It leaves the existing primer and summary unchanged. The path may be absolute or relative to the repository root.

Track every step below as a todo. Each step ends on its **Done when** line; do not start the next step before it holds.

## 1. Resolve the Change Source

Pick the adapter from the argument:

- **GitHub PR** (github URL, or bare number in a GitHub repo): `gh pr view <n> --json number,title,body,url,author,baseRefName,headRefName,headRefOid,baseRefOid,files,commits,closingIssuesReferences`, then `gh pr diff <n>`.
- **Azure DevOps PR** (`dev.azure.com` / `visualstudio.com` URL): `az repos pr show --id <n>` and `az repos pr work-item list --id <n>`; `git fetch` the source and target refs, then diff `merge-base(target, source)..source`.
- **Local branch**: base = remote default branch (`git symbolic-ref refs/remotes/origin/HEAD`); diff `$(git merge-base origin/<base> HEAD)..HEAD`, plus uncommitted changes if any.

Record: id (PR number, or branch name), title, URL, base SHA, head SHA, author, commit list. From here on, **base SHA** means the merge-base the diff starts from.

For `--poster-only`, metadata is enough; skip diff retrieval and source-code inspection.
For all other modes, resolve the repository root with `git rev-parse --show-toplevel`; if it fails, stop and explain that generation must run in a repository session. Make sure both SHAs exist locally (`git fetch origin pull/<n>/head` for GitHub, the source and target refs for Azure DevOps). Read code from the local checkout. If it is not at the head SHA, read files with `git show <headSHA>:<path>`; leave the user's branch where it is.

**Done when** poster-only mode has the PR identity and both SHAs, or other modes have the repository root and both SHAs available locally.

### Poster-only path

When `--poster-only` is present, resolve the PR metadata, then open the exact HTML file path supplied after the flag.
Read its embedded title, PR id or URL, base SHA, head SHA, reasons, architecture, workflows, examples, Key Files, and Coverage Map.
Confirm its PR identity, base SHA, and head SHA match the requested PR.
If the file is missing or any identity or SHA differs, stop and report that the primer must be regenerated.
Do not silently use another primer or rebuild the existing primer.

Use the validated primer as the sole evidence source for [POSTER.md](POSTER.md).
Generate `<id>-<slug>-poster.html` beside the supplied primer.
Do not run the full-primer steps, change the primer or summary, or execute tests in this mode.
Run the style and poster completion checks, then follow Step 10's copy and hash-check rules for the poster.

**Done when** the supplied primer matches the PR identity and SHAs, and only its poster was generated.

## 2. Collect Stated Reasons

Read the PR body, every commit message, and every linked issue / work item (`gh issue view`, `az boards work-item show`). Each motive you extract is a **Stated Reason** with its source.

If none exist, ask the author once via `ask_user` ("Why was this change made?"). If they skip, continue and set the banner: _No Stated Reason; all motives inferred._

**Done when** every motive is tagged Stated (with source) or the banner is set.

## 3. Plan the split, then partition the diff

Run the deterministic planner. It decides the mode; you do not:

```
python <skill-dir>/scripts/plan_split.py --repo <repo-root> --base <base SHA> --head <head SHA> --work-dir <repo-root>/docs/pr-primers/.work/<id>
```

It sets aside generated, vendored, lock, snapshot, and binary files, and writes `plan.json`. Pass `--exclude <glob>` for other generated files you spot. Read only its printed summary and the plan's `excluded` list here.

- **`mode: split`** (over 40 files, 1,500 changed lines, or ~40K diff tokens): read [LARGE-PR.md](LARGE-PR.md) and follow it in place of Steps 3–7, then continue at Step 8.
- **`mode: single`**: read the diff, list the set-aside files in one line by glob, and continue below.

Assign every remaining hunk to exactly one bucket:

- a **Mechanical Change** group (rename, formatting, import order, code moved without edits), summarised in one line each;
- a **Behaviour Change** concept: one logical change, possibly across many files. Name it with a short verb phrase ("Retry failed uploads").

Build the file → concept index as you go.

**Done when** split mode has handed over to LARGE-PR.md, or every remaining hunk sits in exactly one bucket.

## 4. Map the component architecture

Read in this order, stopping when the picture is clear: `README*`, `CONTEXT.md` / `CONTEXT-MAP.md`, `docs/adr/`, `docs/`, `AGENTS.md`. Then follow the code 1–2 hops out from the changed files (callers and callees).

Produce: the component's purpose in 2–3 sentences, its main parts, and one Mermaid component diagram with changed parts highlighted (`classDef changed`). Label anything not backed by docs as _inferred_.

**Done when** every changed file appears in the diagram or is named as outside it.

## 5. Trace impacted workflows

A workflow is an end-to-end path a user, caller, or job triggers (request handling, CLI command, reconcile loop, pipeline stage). For each workflow a Behaviour Change touches, write numbered steps **Before** and **After**, and one Mermaid sequence diagram of the After path.

**Done when** every Behaviour Change belongs to at least one workflow, or is marked "internal only".

## 6. Build examples

For each Behaviour Change, give one concrete case: input → old behaviour → new behaviour. Take data from tests and fixtures first. Mark any invented case as an **Illustrative Example**.

**Done when** each Behaviour Change has an example.

## 7. Build the Coverage Map

For each Behaviour Change, find the tests that exercise it: added or changed tests in the diff first, then existing tests that call the changed code. Status per row: **Covered** (a test asserts the new behaviour), **Partly** (a test runs the code but does not assert the change), **Untested**.

Run tests only with `--run-tests`: use the narrowest command covering the mapped tests and record pass/fail. Otherwise the map is built by reading alone.

**Done when** every Behaviour Change has a row.

## 8. Rank Key Files and rate the change

Rank non-test files by: number of Behaviour Changes they carry, then centrality (caller count; in split mode, the number of `real` links of the file's area), then lines changed. Give each a one-line "why it matters" and a read order. Test files belong in the Tests section.

Rate **Risk** Low / Medium / High with a one-line reason drawn from size, centrality of touched code, and Coverage Map gaps. Estimate **review time** as a range. Label both _heuristic_.

Write **Reviewer Focus Points**: neutral pointers ("Check how X handles empty input"), each tied to a file and line. Every Untested Behaviour Change becomes a focus point.

**Done when** every non-test changed file is ranked and every Untested row has a focus point.

## 9. Write the primer

Read [STYLE.md](STYLE.md) and write every prose sentence to it.

Always generate HTML in light theme: set `<meta name="color-scheme" content="light">` and omit dark theme media queries (`@media (prefers-color-scheme: dark)`).

Fill [template.html](template.html) (skip with `--md-only`) and [template.md](template.md), keeping their section order. The Markdown is the **Primer Summary**: short, pasteable into the PR description.

With `--poster`, read [POSTER.md](POSTER.md) and fill [poster-template.html](poster-template.html) from the same evidence.

Diagrams:
- Quote node labels containing brackets, parentheses, colons, or slashes: `NodeID["Label (details)"]`.
- Never use semicolons `;` in sequence diagram messages (replace with comma `,` or hyphen `-`).
- Quote participant descriptions with slashes or spaces: `participant Route as "TraceRouteBase / ICMPTraceRoute"`.
- Close every `loop`, `alt`, `opt` block with `end`.
- If `mmdc` is on PATH, run `python <skill-dir>/scripts/render_diagrams.py <generated-html>` to compile every Mermaid diagram into self-contained `<svg>` and append a collapsible `<details><summary>Diagram source (Mermaid)</summary>` block containing the editable Mermaid source, and remove the external script. Otherwise keep `<pre class="mermaid">` blocks and the script. The Markdown keeps ```` ```mermaid ```` fences either way.

Run the style check and mermaid validation, and fix every issue they flag:

```
python <skill-dir>/scripts/check_style.py <generated-file> [...]
python <skill-dir>/scripts/validate_mermaid.py <generated-file> [...]
```

When `mmdc` is available, run `python <skill-dir>/scripts/render_diagrams.py <generated-html>` after validation passes.

Pass every generated HTML and Markdown file, including the poster when requested.

**Done when** all checks exit 0 and the poster meets the completion checks in POSTER.md, when requested.

## 10. Save and publish

Use the repository root from Step 1. Create `<repo-root>/docs/pr-primers/` if needed. Write the files there, not only to a shared-copy folder. Use absolute paths derived from the resolved repository root. After writing, confirm every requested repository output exists and is non-empty. If any check fails, report the failure; do not claim success.

Write `<repo-root>/docs/pr-primers/<id>-<slug>.html` and `.md` (slug = kebab-case title, ≤ 40 chars). Overwrite any earlier primer for the same id; the head SHA in the header shows staleness. Leave the files and the `.work/` folder uncommitted, and add `docs/pr-primers/` to `.git/info/exclude` unless already ignored. Keep `.work/<id>/` so a rerun at the same head SHA reuses valid ledgers.

With `--poster`, also write `<id>-<slug>-poster.html` in the same folder. Link it from the Markdown summary and full HTML primer when present. Link the poster back to the generated primer, or to the Markdown summary with `--md-only`.

In `--poster-only` mode, save the poster beside the supplied primer and link it back to that file. Leave all other generated files untouched.

Optional mirror: if the `PR_PRIMER_MIRROR_DIR` environment variable is set, copy every generated HTML file to that folder after the repository outputs pass verification. Create the folder if its drive or parent exists. Keep each filename unchanged, and confirm that the source and destination hashes match (`Get-FileHash` on Windows, `sha256sum` or `shasum -a 256` elsewhere). If the variable is not set, skip the mirror without comment. If it is set but the folder cannot be used, keep the verified repository files and report that the mirror was skipped.

Reply with the absolute repository file paths, the mirror path or skip reason, the risk rating, and the count of Untested Behaviour Changes.
