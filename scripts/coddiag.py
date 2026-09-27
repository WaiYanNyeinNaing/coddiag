#!/usr/bin/env python3
"""CodDiag model adapter and source-anchor/graph validator (stdlib only)."""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlparse


ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
NODE_GROUPS = ("ui", "server", "browser", "llm", "storage", "output")
GROUP_LABELS = {
    "ui": "UI — user-facing interface",
    "server": "Server — request or application logic",
    "browser": "Browser — browser or extension work",
    "llm": "LLM — model-assisted processing",
    "storage": "Storage — saved or retrieved data",
    "output": "Output — result delivered to the user",
}
# Restrained light fills, dark text, and distinct borders. Labels also include the
# category so a monochrome render remains understandable.
GROUP_STYLES = {
    "ui": "fill:#DCEBFA,stroke:#2B6CB0,color:#172554,stroke-width:2px",
    "server": "fill:#E8EAF6,stroke:#4C51BF,color:#1E1B4B,stroke-width:2px",
    "browser": "fill:#E0F2F1,stroke:#0F766E,color:#134E4A,stroke-width:2px",
    "llm": "fill:#F3E8FF,stroke:#7E22CE,color:#3B0764,stroke-width:2px",
    "storage": "fill:#FEF3C7,stroke:#B45309,color:#451A03,stroke-width:2px",
    "output": "fill:#DCFCE7,stroke:#15803D,color:#14532D,stroke-width:2px",
}
SENSITIVE = re.compile(
    r"(^|/)(\.git|node_modules|vendor|dist|build|\.venv|venv|"
    r"__pycache__|\.next|.*\.(?:pem|key|p12|pfx))($|/)",
    re.IGNORECASE,
)
SECRET_ENV = re.compile(r"(^|/)\.env(?:$|\.(?!example$)[^/]+$)", re.IGNORECASE)


def fail(message):
    raise ValueError(message)


def field(obj, name, kind, where):
    value = obj.get(name)
    if not isinstance(value, kind) or (kind is str and not value.strip()):
        fail(f"{where}.{name}: expected nonempty {kind.__name__}")
    return value


def safe_text(value, where, maximum=300):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        fail(f"{where}: expected nonempty text of at most {maximum} characters")
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        fail(f"{where}: control character")
    return value.strip()


def validate_evidence(items, root, where):
    if not isinstance(items, list) or not items:
        fail(f"{where}: at least one source anchor required")
    anchors = []
    for index, item in enumerate(items):
        loc = f"{where}[{index}]"
        if not isinstance(item, dict):
            fail(f"{loc}: expected object")
        raw_path = field(item, "path", str, loc).replace("\\", "/")
        relative = Path(raw_path)
        if relative.is_absolute() or ".." in relative.parts or SENSITIVE.search(raw_path) or SECRET_ENV.search(raw_path):
            fail(f"{loc}: unsafe source path {raw_path!r}")
        target = (root / relative).resolve()
        if not target.is_file() or not target.is_relative_to(root):
            fail(f"{loc}: source file absent or outside repository: {raw_path}")
        start, end = item.get("start"), item.get("end")
        if type(start) is not int or type(end) is not int or start < 1 or end < start or end - start > 14:
            fail(f"{loc}: invalid 1-based line range (maximum 15 lines)")
        needle = safe_text(item.get("needle"), f"{loc}.needle", 200)
        if "\n" in needle:
            fail(f"{loc}.needle: must be on one line")
        try:
            lines = target.read_text(encoding="utf-8").splitlines()
        except (UnicodeError, OSError) as error:
            fail(f"{loc}: cannot read source: {error}")
        if end > len(lines) or not any(needle in line for line in lines[start - 1:end]):
            fail(f"{loc}: exact excerpt missing at {raw_path}:{start}-{end}")
        anchors.append((relative.as_posix(), start, end, needle))
    return anchors


def validate_report(report, root):
    if not isinstance(report, dict):
        fail("report: expected JSON object")
    reject_mermaid_input(report)
    for key in ("feature", "audience", "summary", "revision"):
        safe_text(report.get(key), key, 1000)
    sentences = [part for part in re.split(r"(?<=[.!?])\s+", report["summary"].strip()) if part]
    if not 1 <= len(sentences) <= 3:
        fail("summary: expected 1–3 plain sentences")
    for key, low, high in (("scope_notes", 1, 12), ("stages", 3, 5)):
        values = report.get(key)
        if not isinstance(values, list) or not low <= len(values) <= high:
            fail(f"{key}: expected {low}–{high} items")
        for i, value in enumerate(values):
            safe_text(value, f"{key}[{i}]", 500)
    nodes, edges = report.get("nodes"), report.get("edges")
    if not isinstance(nodes, list) or not 2 <= len(nodes) <= 12:
        fail("nodes: expected 2–12 nodes")
    if not isinstance(edges, list) or not edges:
        fail("edges: at least one edge required")
    ids = set()
    for i, node in enumerate(nodes):
        where = f"nodes[{i}]"
        if not isinstance(node, dict):
            fail(f"{where}: expected object")
        node_id = field(node, "id", str, where)
        if not ID.fullmatch(node_id) or node_id in ids:
            fail(f"{where}.id: invalid or duplicate")
        ids.add(node_id)
        for key in ("label", "description"):
            safe_text(node.get(key), f"{where}.{key}")
        group = node.get("group")
        if group is not None and group not in NODE_GROUPS:
            fail(f"{where}.group: expected one of {', '.join(NODE_GROUPS)} when provided")
        validate_evidence(node.get("evidence"), root, f"{where}.evidence")
    seen = set()
    edge_ids = set()
    adjacency = {node_id: set() for node_id in ids}
    for i, edge in enumerate(edges):
        where = f"edges[{i}]"
        if not isinstance(edge, dict):
            fail(f"{where}: expected object")
        edge_id = field(edge, "id", str, where)
        if not ID.fullmatch(edge_id) or edge_id in edge_ids:
            fail(f"{where}.id: invalid or duplicate")
        edge_ids.add(edge_id)
        source, target = edge.get("from"), edge.get("to")
        if source not in ids or target not in ids or source == target:
            fail(f"{where}: unknown endpoint or self-loop")
        pair = (source, target)
        if pair in seen:
            fail(f"{where}: duplicate directed edge")
        seen.add(pair)
        adjacency[source].add(target)
        adjacency[target].add(source)
        safe_text(edge.get("label"), f"{where}.label", 80)
        safe_text(edge.get("explanation"), f"{where}.explanation", 500)
        validate_evidence(edge.get("evidence"), root, f"{where}.evidence")
    reached, queue = set(), [nodes[0]["id"]]
    while queue:
        current = queue.pop()
        if current not in reached:
            reached.add(current)
            queue.extend(adjacency[current] - reached)
    if reached != ids:
        fail(f"graph: disconnected nodes {sorted(ids - reached)}")
    views = report.get("views")
    if not isinstance(views, dict):
        fail("views: expected object")
    required_views = ("overview", "data_external", "failure_decisions", "project_essentials")
    for key in required_views:
        if not isinstance(views.get(key), dict):
            fail(f"views.{key}: expected object")
    stage_views = views.get("stages")
    if not isinstance(stage_views, list) or len(stage_views) != len(report["stages"]):
        fail("views.stages: expected exactly one view per stages item")
    all_views = [(f"views.{key}", views[key]) for key in required_views]
    all_views.extend((f"views.stages[{i}]", view) for i, view in enumerate(stage_views))
    for where, view in all_views:
        validate_view(view, where, ids, edge_ids, edges)
    for i, (stage, view) in enumerate(zip(report["stages"], stage_views)):
        if view["stage"] != stage:
            fail(f"views.stages[{i}].stage: must exactly match stages[{i}]")
    claims = report.get("claims")
    if not isinstance(claims, list) or not claims:
        fail("claims: expected a nonempty list")
    for i, claim in enumerate(claims):
        where = f"claims[{i}]"
        if not isinstance(claim, dict) or claim.get("status") not in ("verified", "inferred", "gap"):
            fail(f"{where}.status: expected verified, inferred, or gap")
        safe_text(claim.get("topic"), f"{where}.topic", 80)
        safe_text(claim.get("text"), f"{where}.text", 500)
        if claim["status"] == "verified":
            validate_evidence(claim.get("evidence"), root, f"{where}.evidence")
        elif claim["status"] == "inferred":
            safe_text(claim.get("basis"), f"{where}.basis", 500)
        else:
            safe_text(claim.get("resolution"), f"{where}.resolution", 500)
    details = report.get("technical_details")
    if not isinstance(details, dict):
        fail("technical_details: expected object")
    for key in ("data", "external_calls", "failures", "configuration", "tests"):
        values = details.get(key)
        if not isinstance(values, list) or not values:
            fail(f"technical_details.{key}: expected nonempty list")
        for i, value in enumerate(values):
            safe_text(value, f"technical_details.{key}[{i}]", 500)
    essentials = report.get("project_essentials")
    if not isinstance(essentials, dict):
        fail("project_essentials: expected object")
    for section in ("important_files", "environment"):
        items = essentials.get(section)
        if not isinstance(items, list) or not items:
            fail(f"project_essentials.{section}: expected nonempty list")
        for i, item in enumerate(items):
            where = f"project_essentials.{section}[{i}]"
            if not isinstance(item, dict):
                fail(f"{where}: expected object")
            if section == "important_files":
                if set(item) - {"role", "evidence"}:
                    fail(f"{where}: only role and evidence are accepted")
                safe_text(item.get("role"), f"{where}.role", 300)
            else:
                if set(item) - {"name", "purpose", "evidence"}:
                    fail(f"{where}: only name, purpose, and evidence are accepted; never include values")
                name = safe_text(item.get("name"), f"{where}.name", 120)
                if "=" in name:
                    fail(f"{where}.name: use setting names only, never values")
                safe_text(item.get("purpose"), f"{where}.purpose", 300)
            validate_evidence(item.get("evidence"), root, f"{where}.evidence")
    git = essentials.get("git")
    if not isinstance(git, dict):
        fail("project_essentials.git: expected object")
    if set(git) - {"branch", "revision", "working_tree", "feature_changed_files"}:
        fail("project_essentials.git: unexpected field")
    for key in ("branch", "revision", "working_tree"):
        safe_text(git.get(key), f"project_essentials.git.{key}", 1000)
    changed = git.get("feature_changed_files")
    if not isinstance(changed, list):
        fail("project_essentials.git.feature_changed_files: expected list")
    for i, path in enumerate(changed):
        safe_text(path, f"project_essentials.git.feature_changed_files[{i}]", 300)
        normalized = path.replace("\\", "/")
        if Path(normalized).is_absolute() or ".." in Path(normalized).parts or SENSITIVE.search(normalized) or SECRET_ENV.search(normalized):
            fail(f"project_essentials.git.feature_changed_files[{i}]: unsafe path")


def reject_mermaid_input(value, where="report"):
    """Reject embedded diagram source anywhere in input; only structured views compile."""
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if "mermaid" in normalized or normalized in ("diagram_source", "graph_source"):
                fail(f"{where}.{key}: arbitrary diagram source is not accepted")
            reject_mermaid_input(child, f"{where}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_mermaid_input(child, f"{where}[{index}]")


def mermaid_label(value):
    """Return a conservative, one-line Mermaid quoted label."""
    cleaned = re.sub(r"\s+", " ", value).strip()
    cleaned = cleaned.translate(str.maketrans({
        '"': "'", "[": "(", "]": ")", "{": "(", "}": ")",
        "|": "/", "<": "(", ">": ")", "&": "+", "`": "'",
    }))
    return f'"{cleaned}"'


def mermaid_edge_label(value):
    """Return a basic flowchart edge label without quote/pipe delimiters."""
    return mermaid_label(value)[1:-1].replace("'", "")


def mermaid_id(node_id):
    """Avoid Mermaid keywords while retaining the report's validated ID."""
    return f"n_{node_id}"


def validate_view(view, where, node_ids, edge_ids, edges):
    """Validate a compact diagram recipe that can only reuse verified graph items."""
    for key in ("title", "purpose"):
        safe_text(view.get(key), f"{where}.{key}", 240)
    if where.startswith("views.stages["):
        safe_text(view.get("stage"), f"{where}.stage", 200)
    selected_nodes = view.get("node_ids")
    selected_edges = view.get("edge_ids")
    if not isinstance(selected_nodes, list) or not 2 <= len(selected_nodes) <= 8:
        fail(f"{where}.node_ids: expected 2–8 node IDs")
    if len(set(selected_nodes)) != len(selected_nodes) or any(item not in node_ids for item in selected_nodes):
        fail(f"{where}.node_ids: unknown or duplicate node ID")
    if not isinstance(selected_edges, list) or not selected_edges:
        fail(f"{where}.edge_ids: expected at least one edge ID")
    if len(set(selected_edges)) != len(selected_edges) or any(item not in edge_ids for item in selected_edges):
        fail(f"{where}.edge_ids: unknown or duplicate edge ID")
    edge_by_id = {edge["id"]: edge for edge in edges}
    selected = set(selected_nodes)
    adjacency = {node_id: set() for node_id in selected_nodes}
    for edge_id in selected_edges:
        edge = edge_by_id[edge_id]
        if edge["from"] not in selected or edge["to"] not in selected:
            fail(f"{where}.edge_ids: edge {edge_id!r} leaves the selected nodes")
        adjacency[edge["from"]].add(edge["to"])
        adjacency[edge["to"]].add(edge["from"])
    reached, queue = set(), [selected_nodes[0]]
    while queue:
        current = queue.pop()
        if current not in reached:
            reached.add(current)
            queue.extend(adjacency[current] - reached)
    if reached != selected:
        fail(f"{where}: diagram is disconnected")


def node_mermaid_label(node, root):
    """Give every node a readable action plus its first, compact source anchor."""
    path, start, end, _ = validate_evidence(node["evidence"], root, "node label")[0]
    location = f"{path}:{start}" if start == end else f"{path}:{start}-{end}"
    role = node["group"].upper() if node.get("group") else "COMPONENT"
    return mermaid_label(f"{role}: {node['label']} - {location}")


def diagram_lines(view, report, root):
    """Compile a validated view; arbitrary Mermaid is never accepted as input."""
    node_by_id = {node["id"]: node for node in report["nodes"]}
    edge_by_id = {edge["id"]: edge for edge in report["edges"]}
    chosen_nodes = [node_by_id[node_id] for node_id in view["node_ids"]]
    chosen_edges = [edge_by_id[edge_id] for edge_id in view["edge_ids"]]
    rendered = ["```mermaid", "flowchart TD"]
    groups_used = []
    for node in chosen_nodes:
        rendered.append(f"    {mermaid_id(node['id'])}[{node_mermaid_label(node, root)}]")
        if node.get("group") and node["group"] not in groups_used:
            groups_used.append(node["group"])
    for edge in chosen_edges:
        rendered.append(
            f"    {mermaid_id(edge['from'])} -->|{mermaid_edge_label(edge['label'])}| {mermaid_id(edge['to'])}"
        )
    for group in groups_used:
        rendered.append(f"    classDef {group} {GROUP_STYLES[group]}")
    for node in chosen_nodes:
        if node.get("group"):
            rendered.append(f"    class {mermaid_id(node['id'])} {node['group']}")
    rendered.extend(["```", ""])
    return rendered


def source_links(items, root, output_dir):
    return ", ".join(
        f"[{path}:{start}-{end}](<{quote(os.path.relpath(root / path, output_dir), safe='/')}#L{start}-L{end}>)"
        for path, start, end, _ in items
    )


def evidence_block(items, root, output_dir):
    anchors = validate_evidence(items, root, "rendered evidence")
    lines = []
    for path, start, end, needle in anchors:
        links = source_links([(path, start, end, needle)], root, output_dir)
        lines.extend([f"- Source: {links}", f"  - Exact excerpt: `{needle.replace('`', "'")}`"])
    return lines


def build_markdown(report, root, output_dir):
    lines = [
        f"# {report['feature']}",
        "",
        report["summary"],
        "",
        f"**Audience:** {report['audience']}  ",
        f"**Revision:** {report['revision']}",
        "",
        *[f"- {item}" for item in report["scope_notes"]],
        "",
        "## Overview",
        "",
    ]
    overview = report["views"]["overview"]
    lines.extend([f"**{overview['title']}**", ""])
    lines.extend(diagram_lines(overview, report, root))
    groups_used = []
    for node in report["nodes"]:
        if node.get("group") and node["group"] not in groups_used:
            groups_used.append(node["group"])
    if groups_used:
        lines.extend(["**Role legend (color is optional):**", ""])
        lines.extend(f"- **{group.upper()}**: {GROUP_LABELS[group].split(' — ', 1)[1]}" for group in groups_used)
        lines.append("")
    lines.extend(["## Stages", ""])
    for i, view in enumerate(report["views"]["stages"], 1):
        lines.extend([f"### {i}. {view['stage']}", ""])
        lines.extend(diagram_lines(view, report, root))
    data_view = report["views"]["data_external"]
    lines.extend(["## Data and outside systems", ""])
    lines.extend(diagram_lines(data_view, report, root))
    for key in ("data", "external_calls", "configuration"):
        lines.extend(f"- **{key.replace('_', ' ').title()}:** {value}" for value in report["technical_details"][key])
    lines.append("")
    failure_view = report["views"]["failure_decisions"]
    lines.extend(["## Decisions and failure paths", ""])
    lines.extend(diagram_lines(failure_view, report, root))
    lines.extend(f"- {value}" for value in report["technical_details"]["failures"])
    lines.extend(["", "## Confidence", ""])
    for status in ("verified", "inferred", "gap"):
        lines.extend([f"### {status.upper()}", ""])
        selected = [claim for claim in report["claims"] if claim["status"] == status]
        if not selected:
            lines.append("- None identified in this category.")
        for claim in selected:
            lines.append(f"- **{claim['topic']}:** {claim['text']}")
            if status == "verified":
                refs = source_links(validate_evidence(claim["evidence"], root, "claim"), root, output_dir)
                lines.append(f"  - Evidence: {refs}")
            elif status == "inferred":
                lines.append(f"  - Basis: {claim['basis']}")
            else:
                lines.append(f"  - To resolve: {claim['resolution']}")
        lines.append("")
    lines.extend(["## Technical evidence", ""])
    for i, node in enumerate(report["nodes"], 1):
        refs = source_links(validate_evidence(node["evidence"], root, f"node {node['id']}"), root, output_dir)
        needle = validate_evidence(node["evidence"], root, f"node {node['id']}")[0][3].replace("`", "'")
        lines.append(f"{i}. **{node['label']}** — {node['description']} {refs} · `{needle}`")
    lines.extend(["", "**Tests:**", ""])
    lines.extend(f"- {value}" for value in report["technical_details"]["tests"])
    essentials_view = report["views"]["project_essentials"]
    essentials = report["project_essentials"]
    lines.extend(["", "## Project essentials", ""])
    lines.extend(diagram_lines(essentials_view, report, root))
    lines.extend(["### Important files", ""])
    for item in essentials["important_files"]:
        anchors = validate_evidence(item["evidence"], root, "important file")
        refs = source_links(anchors, root, output_dir)
        paths = ", ".join(dict.fromkeys(anchor[0] for anchor in anchors))
        lines.append(f"- **{paths}:** {item['role']} {refs}")
    lines.extend(["", "### Environment and configuration", ""])
    for item in essentials["environment"]:
        refs = source_links(validate_evidence(item["evidence"], root, "environment setting"), root, output_dir)
        lines.append(f"- **{item['name']}:** {item['purpose']} {refs}")
    git = essentials["git"]
    lines.extend(["", "### Git context", "", f"- **Branch:** {git['branch']}", f"- **Revision:** {git['revision']}", f"- **Working tree:** {git['working_tree']}"])
    changed = git["feature_changed_files"]
    lines.append(f"- **Feature-relevant changed files:** {', '.join(changed) if changed else 'None.'}")
    lines.extend(["", "---", "", "Evidence gate passed: paths and exact excerpts exist. Control-flow meaning still requires human source review and, where appropriate, runtime tests.", ""])
    return "\n".join(lines)


def command_validate(args):
    root = Path(args.repo).resolve()
    if not root.is_dir():
        fail("repository directory does not exist")
    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    validate_report(report, root)
    output_dir = Path(args.out).resolve().parent if args.out else root
    result = build_markdown(report, root, output_dir)
    if args.out:
        Path(args.out).write_text(result, encoding="utf-8")
        print(f"Validated {len(report['nodes'])} nodes, {len(report['edges'])} edges; wrote {args.out}")
    else:
        print(result)


def request_json(url, payload, headers):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json", **headers}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        fail(f"model endpoint returned HTTP {error.code}")
    except urllib.error.URLError as error:
        fail(f"model endpoint unavailable: {error.reason}")


def command_model(args):
    prompt = Path(args.prompt).read_text(encoding="utf-8")
    if not prompt.strip() or len(prompt) > 120000:
        fail("prompt must contain 1–120000 characters of reviewed evidence")
    model = safe_text(args.model, "model", 150)
    if args.provider == "ollama":
        result = request_json(
            "http://127.0.0.1:11434/api/chat",
            {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False},
            {},
        )
        content = result["message"]["content"]
    else:
        parsed = urlparse(args.base_url or "")
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            fail("remote base URL must be HTTPS without embedded credentials")
        key = os.getenv("CODDIAG_API_KEY")
        if not key:
            fail("CODDIAG_API_KEY is required for remote provider")
        url = args.base_url.rstrip("/") + "/chat/completions"
        result = request_json(
            url,
            {"model": model, "messages": [{"role": "user", "content": prompt}]},
            {"Authorization": f"Bearer {key}"},
        )
        content = result["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        fail("model returned no text")
    Path(args.out).write_text(content, encoding="utf-8")
    print(f"Wrote model draft to {args.out}; validate its claims against source")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("validate", help="validate report JSON and compile Markdown/Mermaid")
    check.add_argument("--repo", required=True)
    check.add_argument("--input", required=True)
    check.add_argument("--out")
    model = sub.add_parser("model", help="request a draft from local Ollama or selected API")
    model.add_argument("--provider", choices=["ollama", "openai-compatible"], default="ollama")
    model.add_argument("--model", required=True)
    model.add_argument("--base-url")
    model.add_argument("--prompt", required=True)
    model.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        (command_validate if args.command == "validate" else command_model)(args)
    except (ValueError, KeyError, IndexError, json.JSONDecodeError, OSError) as error:
        print(f"CodDiag: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
