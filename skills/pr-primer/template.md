<!--
  Primer Summary template: short, pasteable into the PR description.
  Replace every {{PLACEHOLDER}}. Keep it under ~80 lines; the HTML primer holds the detail.
-->
## PR Primer: {{TITLE}}

<sub>Head `{{HEAD_SHA}}` · Generated {{DATE}} · Full primer: `docs/pr-primers/{{FILE}}.html`</sub>

> ⚠ No Stated Reason; all motives inferred. <!-- only when applicable -->

<sub>Built in {{single | split}} mode{{: N areas, R real links, K open questions}}.</sub>

**Summary.** {{3–5 short sentences}}

| Type | Size | Risk *(heuristic)* | Review time *(heuristic)* | Untested changes |
|---|---|---|---|---|
| {{type}} | +{{A}} / −{{D}}, {{N}} files | **{{Low/Medium/High}}**: {{reason}} | {{20–40 min}} | {{U}} of {{B}} |

### Why
- **Stated:** {{reason}} ({{source}})
- **Inferred:** {{reason}}

### Read these files first
1. `{{path}}`: {{why it matters}}

### Architecture
{{1–2 sentences}}

```mermaid
flowchart LR
  {{COMPONENT_DIAGRAM}}
```

### What changed
1. **{{Concept}}**: {{one or two short sentences}}

*Mechanical:* {{one line per kind}}

### Tests
| Behaviour change | Status | Tests |
|---|---|---|
| {{concept}} | {{Covered/Partly/Untested}} | `{{test}}` |

### Reviewer focus points
1. {{pointer}} (`{{path}}:{{line}}`)
