# PR Primer

A pre-review explanation of a code change, written for reviewers in simplified technical English.

## Language

**PR Primer**:
The full HTML document that explains one change to a reviewer who has no prior context. It explains; it does not judge.
_Avoid_: Review Brief, PR explainer, change dossier, PR description

**Primer Summary**:
The short Markdown extract of a PR Primer, made to paste into the PR description.
_Avoid_: TL;DR, PR description

**PR Poster**:
A one-page visual introduction to a change, derived from the same evidence as its PR Primer.
It complements the detailed explanation; it does not replace it.

**Change Source**:
The input that defines the change: a GitHub PR, an Azure DevOps PR, or a local branch diff against its base.

**Stated Reason**:
A motive for the change taken from the PR text, commits, or linked issues/work items.

**Inferred Reason**:
A motive deduced from the code only. Must always be labelled as inferred.

**Reviewer Focus Point**:
A neutral pointer to an area that deserves reviewer attention. Never a verdict.
_Avoid_: finding, issue, bug

**Plain-English Style**:
The STE-inspired writing rules: max 20 words per sentence, active voice, one idea per sentence, no idioms. Code identifiers in code formatting are exempt.
_Avoid_: full ASD-STE100

**Key File**:
A file that holds most of the change, or its most important logic. Listed so reviewers know where to spend time.
_Avoid_: hot file, main file

**Mechanical Change**:
A change with no behaviour effect (rename, formatting, import reorder, generated output). Summarised in one line, never walked through.
_Avoid_: noise, trivial change

**Behaviour Change**:
A change that alters what the software does for some input. Each one must appear in the Coverage Map.

**Coverage Map**:
The mapping from each Behaviour Change to the tests that exercise it; unmapped changes are marked untested.

**Illustrative Example**:
An example invented to explain a change, as opposed to one taken from tests or fixtures. Must be labelled.

**Area**:
A group of changed files that one agent explains alone in large-PR mode. A script picks areas from directory paths and size limits, not from judgement.
_Avoid_: chunk, shard, module (when meaning an Area)

**Area Ledger**:
The JSON facts one area agent records about its Area. Every fact carries a citation; it holds no prose.

**Citation**:
A path, revision, line range, and exact quote that proves one fact. A script checks it against git.

**Area Link**:
A place where one Area depends on another. Both sides must judge it real or incidental; only real links reach the primer's diagrams.

## Relationships

- A **PR Primer** is produced from exactly one **Change Source**
- A **PR Primer** yields one **Primer Summary**
- A **PR Primer** can have one companion **PR Poster**
- Each motive in a **PR Primer** is either a **Stated Reason** or an **Inferred Reason**
- In large-PR mode, each changed file belongs to exactly one **Area**, and each **Area** yields one **Area Ledger**
- Every fact in an **Area Ledger** rests on at least one **Citation**

## Flagged ambiguities

- "Review" meant both judging and explaining — resolved: the **PR Primer** only explains; judging belongs to the separate code-review skill.
