# Plain-English Style

The primer's prose follows a subset of ASD-STE100 (Simplified Technical English). The reader may be new to the code and may not be a native English speaker.

## Rules

1. **Max 20 words per sentence.** Max 6 sentences per paragraph. (Checked by `scripts/check_style.py`.)
2. **Active voice.** "The handler retries the call", not "The call is retried".
3. **One idea per sentence.** Split at "and", "which", "so that" when they join two ideas.
4. **One word, one meaning.** Pick one term per concept and keep it. Use the repo's own glossary terms when it has a `CONTEXT.md`.
5. **Literal words.** Write "fails" for "blows up", "first" for "up front", "check" for "sanity-check".
6. **Concrete over abstract.** Name the function, the field, the value. "Sets `timeout` to 30 s" beats "adjusts timing behaviour".
7. **Steps as numbered lists**, one action per step, verb first.
8. **Define each acronym** on first use, except common ones (API, HTTP, CLI, JSON, URL, CPU).

## Exemptions

Text inside `code`, code blocks, Mermaid blocks, tables of file paths, and quoted PR or commit text is exempt. Wrap every identifier, path, flag, and literal value in `code`.

## Labels

Mark uncertainty with a visible tag, never with hedging words like "probably" or "seems":

- `Stated` / `Inferred` on every reason.
- `inferred` on architecture facts not backed by docs.
- `Illustrative` on invented examples.
- `heuristic` on risk and review-time ratings.

## Example

> **Before:** The upload client is configured such that, in the event of a transient network failure, the operation will simply be abandoned without any further attempts being made, which obviously isn't ideal.
>
> **After:** The upload client stops after one failed call. This change adds retries. The client now tries up to 3 times. It waits 1 s, then 2 s, between tries.
