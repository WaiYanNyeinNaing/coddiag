# Report contract

Use UTF-8 JSON for one bounded feature. Paths are repository-relative; lines are 1-based and inclusive. A `needle` is an exact one-line substring within a range of at most 15 lines. Never cite secrets, dependencies, build products, or files outside the repository.

## Shape

```json
{
  "feature": "Run the complete job hunt",
  "audience": "A first-time user and junior Python developer",
  "summary": "One action finds jobs, tailors application material, and returns ranked results.",
  "revision": "abc1234 + uncommitted files named in scope",
  "scope_notes": ["Includes POST /api/run_all through its final stream event.", "Excludes browser-extension internals."],
  "stages": ["Check prerequisites", "Find and save jobs", "Tailor the resume", "Show results"],
  "nodes": [
    {"id": "request", "label": "Start the full run", "group": "server", "description": "The request handler checks the resume path.", "evidence": [{"path": "app.py", "start": 335, "end": 345, "needle": "async def run_all("}]},
    {"id": "search", "label": "Find and save jobs", "group": "storage", "description": "The search stage stores each job locally.", "evidence": [{"path": "app.py", "start": 141, "end": 160, "needle": "db.upsert_job("}]}
  ],
  "edges": [
    {"id": "checks_to_search", "from": "request", "to": "search", "label": "checks pass", "explanation": "The handler starts searching after validation.", "evidence": [{"path": "app.py", "start": 349, "end": 361, "needle": "yield from _do_search("}]}
  ],
  "views": {
    "overview": {"title": "The whole journey", "purpose": "Feature from start to result.", "node_ids": ["request", "search"], "edge_ids": ["checks_to_search"]},
    "stages": [
      {"stage": "Check prerequisites", "title": "Start gate", "purpose": "Validation before work.", "node_ids": ["request", "search"], "edge_ids": ["checks_to_search"]},
      {"stage": "Find and save jobs", "title": "Search", "purpose": "Collection and storage.", "node_ids": ["request", "search"], "edge_ids": ["checks_to_search"]},
      {"stage": "Tailor the resume", "title": "Tailoring", "purpose": "Input becomes output.", "node_ids": ["request", "search"], "edge_ids": ["checks_to_search"]},
      {"stage": "Show results", "title": "Delivery", "purpose": "Result reaches the user.", "node_ids": ["request", "search"], "edge_ids": ["checks_to_search"]}
    ],
    "data_external": {"title": "Boundaries", "purpose": "Saved or externally sent data.", "node_ids": ["request", "search"], "edge_ids": ["checks_to_search"]},
    "failure_decisions": {"title": "Stopping points", "purpose": "Decision and visible consequence.", "node_ids": ["request", "search"], "edge_ids": ["checks_to_search"]},
    "project_essentials": {"title": "Feature components", "purpose": "Important implementation pieces and their dependency.", "node_ids": ["request", "search"], "edge_ids": ["checks_to_search"]}
  },
  "claims": [
    {"status": "verified", "topic": "happy path", "text": "Search happens before tailoring.", "evidence": [{"path": "app.py", "start": 357, "end": 365, "needle": "yield from _do_optimize("}]},
    {"status": "inferred", "topic": "timing", "text": "A long search may feel slow.", "basis": "No timing trace was run."},
    {"status": "gap", "topic": "tests", "text": "No endpoint test was found.", "resolution": "Test POST /api/run_all and inspect streamed events."}
  ],
  "technical_details": {
    "data": ["SQLite stores jobs locally."],
    "external_calls": ["The browser bridge reads LinkedIn."],
    "failures": ["A missing resume returns HTTP 400 before search."],
    "configuration": ["Supabase mirroring is optional."],
    "tests": ["No feature-level test was found; recorded as a gap."]
  },
  "project_essentials": {
    "important_files": [
      {"role": "Owns the full-run request and orchestration.", "evidence": [{"path": "app.py", "start": 335, "end": 345, "needle": "async def run_all("}]}
    ],
    "environment": [
      {"name": "SUPABASE_URL", "purpose": "Enables optional remote mirroring.", "evidence": [{"path": ".env.example", "start": 1, "end": 8, "needle": "SUPABASE_URL="}]}
    ],
    "git": {
      "branch": "main",
      "revision": "abc1234",
      "working_tree": "Modified: app.py; untracked: none.",
      "feature_changed_files": ["app.py"]
    }
  }
}
```

## Rules

- `summary` is 1–3 plain sentences. `scope_notes` has 1–12 items; `stages` has 3–5 items.
- `nodes` has 2–12 connected nodes. Every node and edge has exact evidence. Edge evidence must support the relationship.
- Required views are `overview`, one `stages` view per stage, `data_external`, `failure_decisions`, and `project_essentials`. A view has 2–8 nodes, at least one edge, stays within the inventory, and is connected.
- Optional node `group` is `ui`, `server`, `browser`, `llm`, `storage`, or `output`.
- Claim status is `verified`, `inferred`, or `gap`. Verified requires evidence; inferred requires `basis`; gap requires `resolution`.
- Every `technical_details` category exists and is nonempty. Use a brief truthful “none found/applies” when needed.
- `project_essentials.important_files` is nonempty. Each item has a concise `role` and exact source evidence; the renderer derives the path from that evidence.
- `project_essentials.environment` is nonempty. Each item names a variable or configuration setting, explains its purpose, and cites safe documentation or code. `.env.example` may be cited; `.env`, secret-bearing variants, and secret values must never be read or included. Use a truthful “none found” item anchored to a manifest or config source when environment variables do not apply.
- `project_essentials.git` records `branch`, `revision`, `working_tree`, and zero or more `feature_changed_files`. These are Git command results, not source anchors. Never cite `.git` internals.
- Coaching fields such as predictions, questions, exercises, and glossary are not part of the default contract.

## Output

The deterministic compiler emits only standard Markdown plus restricted Mermaid. It emits no raw HTML. The report contains a short summary, required diagrams, minimal boundary and failure notes, compact confidence labels, one technical evidence trail, and project essentials. It does not repeat arrow explanations below stage diagrams.

Arbitrary Mermaid input is rejected. Structured IDs compile to `flowchart TD`, quoted one-line nodes, basic edge labels, fixed `classDef` styles, and class assignments.
