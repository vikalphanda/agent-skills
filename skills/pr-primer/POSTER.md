# PR Poster

Generate only with `--poster`. Use the primer's collected evidence and [STYLE.md](STYLE.md).
The poster explains the change; it gives no merge verdict.

## Content

Fill [poster-template.html](poster-template.html) in this order:

1. **Why:** the problem and intended outcome in two short sentences. Label each reason Stated or Inferred.
2. **Where:** a small component diagram, with changed parts highlighted and a text explanation.
3. **Before / After:** the main impacted workflow, in numbered steps. Name its trigger.
4. **Example:** one input, its old result, and its new result. Cite the fixture or label it Illustrative.
5. **Review map:** up to three Key Files in reading order, plus test coverage and execution status.

Header: title, PR link when available, head SHA, base SHA, generation date.
Footer: link to the generated primer or Markdown summary.

For large PRs, select the main concepts and name omitted concepts in a short scope note.
Keep complete details in the primer; the poster is a summary.
For a mechanical-only change, state that no behaviour change was identified.
Use a concrete transformation example and an unchanged workflow where appropriate.

## Evidence and presentation

- Reuse the primer's counts, test statuses, labels, and commit references exactly.
- Report Covered, Partly, and Untested counts for behaviour changes, not line-coverage percentages.
- Display test execution separately: Not run, Passed, Failed, or Blocked, with scope when tests ran.
- Include partial coverage, untested changes, and unavailable evidence in a visible test-gap note.
- Mark inferred architecture and invented examples. Use text labels as well as colours.
- Keep the poster self-contained: inline CSS and SVG, without scripts, fonts, images, or CDN requests.
- Use local Mermaid rendering if available. Otherwise draw a simple inline SVG from verified relationships.
- Preserve a text equivalent of the diagram. Escape untrusted text and use an SVG title and description.
- Use A4 landscape print styling. Keep body text at least 11 pt; shorten prose instead of shrinking text.

## Completion checks

Replace all placeholders. Confirm all five panels, evidence labels, SHA stamps, and the companion link are present.
Run the style checker on the poster. Inspect print preview when a browser is available.
Confirm one page with readable text and no clipping; simplify the diagram or shorten prose if needed.
If print preview is unavailable, report that the one-page layout remains unverified.
Check that the output contains no external asset references or scripts.
