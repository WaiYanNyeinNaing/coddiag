# CodDiag

CodDiag is a Codex skill for creating concise, source-verified visual walkthroughs of one bounded codebase feature or Git diff. It produces Markdown reports with restricted Mermaid diagrams, exact source anchors, confidence labels, failure paths, data boundaries, and project essentials.

## What it does

- Traces a feature from entry point through validation, orchestration, side effects, and output.
- Separates verified claims from inferences and unresolved gaps.
- Compiles a structured JSON report into deterministic Markdown and Mermaid.
- Rejects unsafe evidence paths, secret-bearing environment files, and arbitrary Mermaid input.
- Uses local source inspection by default; remote model drafting requires explicit opt-in.

## Install

Copy or clone this repository into your Codex skills directory:

```bash
git clone https://github.com/WaiYanNyeinNaing/coddiag.git ~/.codex/skills/coddiag
```

Restart Codex if the skill is not discovered automatically.

## Use

Ask Codex to use `$coddiag` for a specific feature or diff. Keep the scope narrow—for example, “Explain the checkout submission flow” or “Walk through the current authentication diff.”

CodDiag first inspects the repository and builds a `report.json` following [the report contract](references/report-contract.md). Validate and compile it with:

```bash
python3 scripts/coddiag.py validate \
  --repo /path/to/repository \
  --input report.json \
  --out walkthrough.md
```

The validator uses only the Python standard library.

## Optional model drafting

Direct source inspection is the default. An optional local Ollama draft can be requested with:

```bash
python3 scripts/coddiag.py model \
  --provider ollama \
  --model <installed-model> \
  --prompt evidence-prompt.txt \
  --out candidate.txt
```

Remote OpenAI-compatible endpoints are supported only with explicit consent and an HTTPS base URL. See [provider choices](references/provider.md). Never place credentials in prompts or committed files.

## Repository layout

- `SKILL.md` — skill behavior and workflow.
- `scripts/coddiag.py` — validator, Markdown/Mermaid compiler, and optional model adapter.
- `references/report-contract.md` — structured report schema and validation rules.
- `references/provider.md` — local and explicitly opted-in remote drafting options.
- `agents/openai.yaml` — Codex skill metadata.
- `assets/icon.svg` — skill icon.

## License

[MIT](LICENSE)
