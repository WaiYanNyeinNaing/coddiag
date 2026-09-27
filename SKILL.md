---
name: coddiag
description: Create a concise, source-verified visual walkthrough of one local codebase feature or Git diff for junior developers and non-technical readers. Uses local inspection by default; any remote model requires explicit opt-in.
---

# CodDiag

## Outcome

Show what one bounded feature does, how its stages connect, where it is implemented, and how to change it safely. Default to a concise visual report, not a repository wiki or teaching worksheet.

## Required report

- State the feature boundary, revision, working-tree state, audience, and exclusions.
- Start with a 1–3 sentence plain-language summary.
- Generate an overview, one compact Mermaid flow per stage, and focused data/external-system, failure/decision, and project-essentials flows.
- Reuse one validated node/edge inventory. Each node includes its role, action, and first source location.
- Cover relevant data writes, external calls, configuration, failures, and tests. End with project essentials: important feature files, safe configuration names and purposes, and Git context. Say briefly when none applies or was found.
- Label claims `VERIFIED`, `INFERRED`, or `GAP`. Verified claims require exact source evidence; inferences state their basis; gaps state how to resolve them.
- Keep prose minimal. Diagram edge labels carry the flow explanation; do not repeat every arrow in bullets. Cite each source/excerpt once in the technical evidence trail where possible.
- Emit standard Markdown and restricted Mermaid only. Never emit raw HTML such as `<details>` or `<summary>`.
- Do not add predictions, comprehension questions, exercises, or a glossary unless the user explicitly requests a coaching mode. The default contract and renderer omit them.

## Reader-friendly rules

Use everyday roles before code names: “the request handler (`run_all`)”. Prefer short labels, concrete verbs, and diagrams with 2–7 nodes (maximum 8 per view). Introduce implementation detail only in the concise evidence section. Color indicates component roles but labels must remain understandable without color.

Each visual answers one distinct concern. Stage diagrams zoom in rather than duplicating the overview. The data map shows boundaries, the failure map shows stopping points, and the essentials map connects the feature's important implementation components.

## Workflow

1. Read repository instructions, README or architecture notes, `git status`, revision, manifest, and a shallow tree. Do not edit application source.
2. Select one feature, journey, entry point, or diff. When ambiguous, choose the narrowest useful scope and disclose it.
3. Trace entry → validation → orchestration → side effects → output with `rg`, focused code windows, callers/imports, tests, configuration, async dispatch, and errors. Record short exact excerpts with 1-based lines. Inspect safe configuration documentation such as `.env.example`, manifests, or config modules; never read or cite `.env` or secret-bearing environment files.
4. When delegation is available and authorized, use separate read-only passes for the main flow, side effects/failures, and evidence audit.
5. Build `report.json` from [report-contract.md](references/report-contract.md). The agent owns anchors, claim status, view composition, and semantic review.
6. Run `python3 <skill>/scripts/coddiag.py validate --repo <repo> --input report.json --out walkthrough.md`. Fix all failures. If `mmdc` already exists, use it as an extra Mermaid parser check.
7. Confirm every diagram is useful, prose does not repeat diagram labels, source links are not duplicated unnecessarily, and every edge represents actual code.

For Git context, use Git commands to record the current branch, revision, a concise working-tree summary, and feature-relevant changed files. Do not inspect or cite `.git` internals. Project-essentials file and configuration entries require ordinary source anchors; Git metadata does not.

## Privacy and model boundary

Direct source inspection is sufficient. Optional drafting defaults to local Ollama at `http://127.0.0.1:11434/api/chat`. Never send private source remotely without explicit opt-in. Remote use requires `--provider openai-compatible`, a user-supplied HTTPS base URL and model, and `CODDIAG_API_KEY`. Exclude secrets, `.env`, credentials, generated dependencies, and unrelated files. See [provider.md](references/provider.md).

Do not use hosted GitHub diagram services for private repositories. Model output and Mermaid rendering are drafts, not evidence.

## Validation boundary

The validator confirms safe paths, exact excerpts, connected graphs/views, required visual coverage, and deterministic restricted Mermaid. It accepts no Mermaid source in input. It cannot prove runtime execution or edge meaning; review source and use tests or tracing where needed. Downgrade uncertainty to `INFERRED` or `GAP`.
