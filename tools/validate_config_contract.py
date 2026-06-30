from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.phase2_validation import PHASE2_NODE_ORDER

ABS_WIN = re.compile(r"(?i)(?<![A-Z])[A-Z]:[\\/](?![\\/])")
LEGACY_NODE_NAMES = {
    "SceneFormalizer",
    "KeyElementExtractor",
    "RetrieveModel",
    "ModuleAnalyzer",
    "ModuleCodeGenerator",
    "InteractiveObjectAnalyzer",
    "InteractiveObjectCodeGenerator",
    "PCGGraphComposer",
    "PCGPlanner",
}


def load_json(rel: str) -> dict:
    with (ROOT / rel).open("r", encoding="utf-8") as f:
        return json.load(f)


def walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_strings(child)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", default="config/workflows/puerts_ts.json")
    parser.add_argument("--phase", choices=["phase2"], default="phase2")
    args = parser.parse_args()
    errors: list[str] = []

    for rel in ["config/local.example.json", "config/llm-profiles.example.json", args.workflow]:
        data = load_json(rel)
        for text in walk_strings(data):
            if ABS_WIN.search(text):
                errors.append(f"{rel}: hard-coded absolute Windows path: {text}")

    workflow = load_json(args.workflow)
    nodes = workflow.get("nodes", [])
    node_names = [node.get("name") for node in nodes]
    enabled = [node.get("name") for node in nodes if node.get("enabled", True)]

    if len(enabled) != len(set(enabled)):
        errors.append(f"duplicate enabled nodes: {enabled}")

    legacy_present = sorted(name for name in node_names if name in LEGACY_NODE_NAMES)
    if legacy_present:
        errors.append(f"legacy C++/PCG nodes must not be present in active workflow file: {legacy_present}")

    for node in nodes:
        prompt = node.get("prompt_file")
        if node.get("enabled", True) and prompt and not (ROOT / prompt).exists():
            errors.append(f"missing prompt file for {node.get('name')}: {prompt}")

    if enabled != PHASE2_NODE_ORDER:
        errors.append(f"phase2 enabled node order mismatch: expected {PHASE2_NODE_ORDER}, got {enabled}")

    if errors:
        print(json.dumps({"result": "fail", "errors": errors}, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps({"result": "pass", "workflow": workflow.get("name"), "enabled_nodes": enabled}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
