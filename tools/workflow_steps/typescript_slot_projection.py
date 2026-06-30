from __future__ import annotations

import json
from typing import Any

from core.workflow_validation import parse_node_json

RUNTIME_NODE = "PuerTSRuntimeMappingCompiler"
ENTITY_NODE = "EntityAbilityBehaviorPlanner"
REQUIRED_MAPPING_FIELDS = ("entity_id", "behavior_id", "flow_id", "runtime_owner")


def _runtime_mappings(mapping_node: dict[str, Any]) -> list[Any]:
    raw = mapping_node.get("runtime_mappings")
    if raw is None:
        raw = mapping_node.get("mappings", [])
    return raw if isinstance(raw, list) else []


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def run_typescript_slot_projection(inputs: dict[str, str]) -> dict[str, Any]:
    parse_node_json(ENTITY_NODE, inputs.get("entity_behavior", ""))
    mapping_node = parse_node_json(RUNTIME_NODE, inputs.get("runtime_mapping", ""))
    if not isinstance(mapping_node, dict):
        raise RuntimeError(f"{RUNTIME_NODE} output must be a JSON object")

    top_runtime_mapping_path = _string(mapping_node.get("runtime_mapping_path"))
    sources: list[dict[str, str]] = []
    seen_sources: set[str] = set()
    slots: list[dict[str, str]] = []
    missing_slots: list[dict[str, Any]] = []

    mappings = _runtime_mappings(mapping_node)
    if not mappings:
        missing_slots.append({"mapping_index": None, "missing_fields": ["mappings"], "reason": "no runtime mappings found"})

    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            missing_slots.append({"mapping_index": index, "missing_fields": ["mapping_object"], "reason": "mapping must be object"})
            continue

        runtime_mapping_path = _string(mapping.get("runtime_mapping_path")) or top_runtime_mapping_path
        values = {field: _string(mapping.get(field)) for field in REQUIRED_MAPPING_FIELDS}
        missing = [field for field, value in values.items() if not value]
        if not runtime_mapping_path:
            missing.append("runtime_mapping_path")
        if missing:
            missing_slots.append({
                "mapping_index": index,
                "behavior_id": _string(mapping.get("behavior_id")),
                "entity_id": _string(mapping.get("entity_id")),
                "missing_fields": missing,
                "reason": "runtime mapping lacks required analyzer fields",
            })
            continue

        target = values["runtime_owner"]
        if target not in seen_sources:
            sources.append({
                "path": target,
                "role": "runtime_owner",
                "notes": "deterministically projected from runtime mapping runtime_owner",
            })
            seen_sources.add(target)

        slots.append({
            "entity_id": values["entity_id"],
            "behavior_id": values["behavior_id"],
            "flow_id": values["flow_id"],
            "runtime_mapping_path": runtime_mapping_path,
            "target_ts_file": target,
            "reason": "deterministically projected from runtime mapping",
        })

    return {
        "typescript_sources": sources,
        "implementation_slots": slots,
        "missing_slots": missing_slots,
    }


def generate_typescript_slot_projection(entity_output: str, runtime_mapping_output: str) -> str:
    return json.dumps(run_typescript_slot_projection({"entity_behavior": entity_output, "runtime_mapping": runtime_mapping_output}), ensure_ascii=False, indent=2)
