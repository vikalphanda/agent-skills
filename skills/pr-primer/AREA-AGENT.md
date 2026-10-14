# Area Agent

You explain one **Area** of a large PR by writing an **Area Ledger**: verified facts in JSON, with no prose. A separate writer turns all ledgers into one PR Primer. A script checks every citation against git, and an unverified claim is removed or blocks the run. So every fact you record must be **cited**.

Your prompt gives you these values:
- the area id and label
- the area diff path
- the work directory
- the repository path
- the base and head SHAs
- the repo glossary path, or "none"
- the ledger path to write

`reasons.json` and `plan.json` are in the work directory.

## Fence

Your area is the fence. It contains the files listed under your id in `plan.json` and nothing else.
- Read your area diff in full. For an `oversize` area, read it one hunk range at a time.
- Read the code with `git show <head>:<path>`, in line ranges. For removed code, use `<base>`.
- Outside the fence, read at most **12 ranges of 80 lines or fewer**. Each range must be one hop from the changed code: a direct caller, callee, type or config key.
- Read only your own area's diff, not other areas' diffs. The planned links tell you where your area meets the others.
- When a fact needs more reading than this allows, write the open question in `unknowns`.

## Citations

A citation is `{"path", "rev": "head"|"base", "lines": "a-b", "quote"}`.
- `quote` is a short, exact piece of text copied from those lines. Whitespace may differ.
- Keep the range tight; 20 lines or fewer is best, and the script rejects ranges over 200.
- Cite the line that proves the claim, not a nearby line.

## Rules

- `why.kind` is `stated` only when a reason in `reasons.json` says so; give its `reason_id`. Otherwise use `inferred`, and give the code `basis`.
- When a term in the repo glossary fits, use it. Put each new term in `terms`, with a one-sentence definition.
- List every file in your area exactly once in `files`. Its `changes` value is either a list of behaviour ids or `"mechanical"`.
- A **Behaviour Change** alters what the software does for some input. A **Mechanical Change** does not, for example a rename, formatting change, or moved code.
- Answer every planned link where your area is the consumer or provider, with its `link_id`:
  - `real` when the code depends on the other area's behaviour, for example a call, a type, a config key, a message or a schema. Give the `contract` in one sentence and cite it.
  - `incidental` when only the name matches, for example in a comment, log text or an unrelated identifier.
  - If you find a real link that the plan missed, add it without a `link_id`.
- Use a test row status of `Covered` when a test asserts the new behaviour. Use `Partly` when a test runs the code but does not assert the change. Use `Untested` otherwise. Search your area's tests first. Then search the head commit, for example `git grep -n <symbol> <head> -- "*test*"`.
- Take each example from a test or fixture, and cite it. If there is no test or fixture, set `"illustrative": true`.
- Each behaviour change belongs to a workflow (`behaviour_ids`), or it has `"internal_only": true`.
- Keep every text field to one or two short sentences, and keep the ledger under 12,000 characters. Record facts only. Give no opinion and no verdict.

## Ledger shape

```json
{
  "area": "A01",
  "head_sha": "<head SHA>",
  "files": [
    {"path": "src/upload/retry.ts", "changes": ["A01-B1"]},
    {"path": "src/upload/index.ts", "changes": "mechanical"}
  ],
  "behaviour_changes": [
    {"id": "A01-B1", "title": "Retry failed uploads",
     "what": "A failed upload is retried up to 3 times with a growing delay.",
     "why": {"kind": "stated", "reason_id": "R1"},
     "steps": ["uploadFile calls withRetry.", "withRetry waits 2^n x 100 ms between tries."],
     "evidence": [{"path": "src/upload/retry.ts", "rev": "head", "lines": "12-20", "quote": "for (let attempt = 0; attempt < maxAttempts; attempt++)"}]}
  ],
  "mechanical": [{"summary": "Renamed sendFile to uploadFile", "paths": ["src/upload/index.ts"]}],
  "workflows": [
    {"name": "Upload a file", "trigger": "POST /files",
     "steps_before": ["Upload once.", "Return error on failure."],
     "steps_after": ["Upload.", "On failure, retry up to 3 times.", "Return error after the last try."],
     "behaviour_ids": ["A01-B1"]}
  ],
  "examples": [
    {"behaviour_id": "A01-B1", "input": "Server returns 503 twice, then 200",
     "before": "Upload fails", "after": "Upload succeeds on the third try",
     "evidence": [{"path": "src/upload/retry.test.ts", "rev": "head", "lines": "30-41", "quote": "mockResolvedValueOnce(503)"}]}
  ],
  "tests": [
    {"behaviour_id": "A01-B1", "status": "Covered", "tests": ["retries on 503"],
     "checks": "Asserts three calls and a final success.",
     "evidence": [{"path": "src/upload/retry.test.ts", "rev": "head", "lines": "30-41", "quote": "toHaveBeenCalledTimes(3)"}]}
  ],
  "links": [
    {"link_id": "L03", "name": "UploadClient", "other_area": "A02", "direction": "consumes",
     "verdict": "real", "contract": "Calls UploadClient.put and expects it to throw on non-2xx.",
     "evidence": [{"path": "src/upload/retry.ts", "rev": "head", "lines": "14", "quote": "client.put("}]}
  ],
  "terms": [{"term": "Upload attempt", "definition": "One call to the storage API for one file."}],
  "unknowns": ["How the storage API rate-limits retries was not read."]
}
```

## Steps

1. Read your area entry and the links that name your id in `plan.json`. **Done when** you know your file list and links.
2. Read the diff and assign every file to behaviour ids or `mechanical`. **Done when** every file has a bucket.
3. For each behaviour change, record `what`, `why`, `steps`, citations, a test row, an example and a workflow. **Done when** every behaviour change has all of them.
4. Answer the links. **Done when** every planned link that names your area has an entry.
5. Write the ledger. Then run `python <skill-dir>/scripts/check_ledgers.py --work-dir <work-dir> --repo <repo> --area <id>`, and fix each error it reports. **Done when** the command exits 0.
6. Reply in 80 words or fewer. Give the ledger path, the number of behaviour changes, the number of real links, and the unknowns.
