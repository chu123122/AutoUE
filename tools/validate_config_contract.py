from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.validation.common import WORKFLOW_NODE_ORDER, is_safe_relative_path
from core.validation.registry import VALIDATOR_REGISTRY

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


def profile_names(llm_profiles: dict) -> set[str]:
    profiles = llm_profiles.get("profiles", {})
    return set(profiles) if isinstance(profiles, dict) else set()


def validate_artifact_schema(node_name: str, artifacts, errors: list[str]) -> None:
    if not isinstance(artifacts, list) or not artifacts:
        errors.append(f"{node_name}: output_artifacts must be a non-empty list")
        return
    for index, artifact in enumerate(artifacts):
        label = f"{node_name}: output_artifacts[{index}]"
        if not isinstance(artifact, dict):
            errors.append(f"{label} must be object")
            continue
        kind = artifact.get("kind")
        if kind not in {"llm_output", "json", "markdown", "typescript"}:
            errors.append(f"{label}.kind is invalid: {kind}")
        has_path = "path" in artifact
        has_path_from = "path_from" in artifact
        if has_path == has_path_from:
            errors.append(f"{label} must set exactly one of path or path_from")
            continue
        if has_path:
            path = artifact.get("path")
            if not isinstance(path, str) or not is_safe_relative_path(path):
                errors.append(f"{label}.path must be a safe relative path: {path}")
        if has_path_from:
            path_from = artifact.get("path_from")
            if not isinstance(path_from, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\[\])?(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[\])?)*", path_from):
                errors.append(f"{label}.path_from has unsupported selector syntax: {path_from}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", default="config/workflows/puerts_ts.json")
    parser.add_argument("--contract", choices=["puerts_ts"], default="puerts_ts")
    args = parser.parse_args(argv)
    errors: list[str] = []

    for rel in ["config/local.example.json", "config/llm-profiles.example.json", args.workflow]:
        data = load_json(rel)
        for text in walk_strings(data):
            if ABS_WIN.search(text):
                errors.append(f"{rel}: hard-coded absolute Windows path: {text}")

    workflow = load_json(args.workflow)
    llm_profiles = load_json("config/llm-profiles.example.json")
    known_profiles = profile_names(llm_profiles)
    nodes = workflow.get("nodes", [])
    node_names = [node.get("name") for node in nodes]
    enabled = [node.get("name") for node in nodes if node.get("enabled", True)]

    if len(enabled) != len(set(enabled)):
        errors.append(f"duplicate enabled nodes: {enabled}")

    legacy_present = sorted(name for name in node_names if name in LEGACY_NODE_NAMES)
    if legacy_present:
        errors.append(f"legacy C++/PCG nodes must not be present in active workflow file: {legacy_present}")

    for node in nodes:
        name = node.get("name")
        prompt = node.get("prompt_file")
        if node.get("enabled", True) and prompt and not (ROOT / prompt).exists():
            errors.append(f"missing prompt file for {name}: {prompt}")
        if node.get("enabled", True):
            validator = node.get("validator")
            if not isinstance(validator, str) or validator not in VALIDATOR_REGISTRY:
                errors.append(f"{name}: unknown or missing validator: {validator}")
            llm_profile = node.get("llm_profile")
            if not isinstance(llm_profile, str) or not llm_profile:
                errors.append(f"{name}: missing llm_profile")
            elif llm_profile not in known_profiles:
                errors.append(f"{name}: llm_profile does not exist: {llm_profile}")
            validate_artifact_schema(str(name), node.get("output_artifacts"), errors)

    if enabled != WORKFLOW_NODE_ORDER:
        errors.append(f"workflow enabled node order mismatch: expected {WORKFLOW_NODE_ORDER}, got {enabled}")

    if errors:
        print(json.dumps({"result": "fail", "errors": errors}, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps({"result": "pass", "workflow": workflow.get("name"), "enabled_nodes": enabled}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
