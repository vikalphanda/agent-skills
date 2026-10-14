# agent-skills

Reusable skills for coding agents (GitHub Copilot, Claude Code, Codex, Cursor, and others).
Each skill is a folder under [`skills/`](skills/) with a `SKILL.md` entry point.


## Skills

| Skill | What it does |
|-------|--------------|
| [pr-primer](skills/pr-primer/SKILL.md) | Explains a PR in plain English before review: why, architecture, workflows, key files, walkthrough with examples, and test coverage. Outputs HTML + Markdown. Supports GitHub and Azure DevOps. |

## Install

Copy the skill folder into your agent's skills directory:

| Agent | Personal | Per repo |
|-------|----------|----------|
| GitHub Copilot | `~/.copilot/skills/` | `.github/skills/` |
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex | `~/.codex/skills/` | `.agents/skills/` |

```bash
gh repo clone vikalphanda/agent-skills
cp -R agent-skills/skills/pr-primer ~/.copilot/skills/
```

Or use the installer: `npx skills@latest add vikalphanda/agent-skills --skill pr-primer`

For other agents, add an instruction such as: *"For PR primers, follow `<path>/skills/pr-primer/SKILL.md`."*

To update, copy the folder again.

> **Status: work in progress.**
> More skills are being added, are a versioned release package is coming soon.
> Skill names, options and file layouts may change before the first release.

## pr-primer

```text
/pr-primer <PR URL | number | branch>   HTML primer + Markdown summary
/pr-primer <PR URL> --poster            Also a one-page poster
/pr-primer <PR URL> --run-tests         Run mapped tests and record results
/pr-primer --help                       All options
```

- **Requires:** `git`, Python 3, and `gh` (GitHub) or `az` + azure-devops extension (Azure DevOps). Optional: `mmdc` for diagram validation.
- **Output:** `docs/pr-primers/` in the repo (not committed). Set `PR_PRIMER_MIRROR_DIR` to also copy HTML elsewhere.
- **Large PRs** are split into areas automatically, with every fact checked against the code. See [LARGE-PR.md](skills/pr-primer/LARGE-PR.md).

## Contributing

Add `skills/<name>/SKILL.md` with `name` and `description` front matter, use relative paths only, add a row to the table above, and open a PR.
