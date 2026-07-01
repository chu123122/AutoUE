from __future__ import annotations

import re
from typing import Any, Mapping

from core.workflow_validation import parse_node_json

RUNTIME_NODE = "PuerTSRuntimeMappingCompiler"
SLOT_NODE = "TypeScriptImplementationSlotProjector"
INTERACTIVE_TS_DIR = "TypeScript/content/generated/interactive"


def _pascal(value: str) -> str:
    parts = re.split(r"[^A-Za-z0-9]+", value)
    text = "".join(part[:1].upper() + part[1:] for part in parts if part)
    return text or "GeneratedBehavior"


def _mappings(mapping_node: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [m for m in mapping_node.get("mappings", []) if isinstance(m, Mapping)]


def run_typescript_interactive_plan(inputs: dict[str, str]) -> dict[str, Any]:
    mapping_node = parse_node_json(RUNTIME_NODE, inputs.get("runtime_mapping", ""))
    parse_node_json(SLOT_NODE, inputs.get("ts_slots", ""))
    template_inputs: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    runtime_mapping_path = mapping_node.get("runtime_mapping_path", "") if isinstance(mapping_node, Mapping) else ""

    for mapping in _mappings(mapping_node):
        behavior_id = str(mapping.get("behavior_id") or "")
        entity_id = str(mapping.get("entity_id") or "")
        flow_id = str(mapping.get("flow_id") or "")
        name = _pascal(f"{entity_id}.{behavior_id}" if entity_id else behavior_id)
        path = f"{INTERACTIVE_TS_DIR}/{name}Interactable.ts"
        export_name = f"run{name}Interaction"
        interface_name = f"{name}InteractionContext"
        item = {
            "template": "interactive_object",
            "path": path,
            "entity_id": entity_id,
            "behavior_id": behavior_id,
            "flow_id": flow_id,
            "runtime_mapping_path": runtime_mapping_path,
            "export_name": export_name,
            "interface_name": interface_name,
            "action_label": f"execute {behavior_id}",
            "target_label": entity_id or "Target",
            "result_label": f"{behavior_id} interaction trace recorded",
        }
        template_inputs.append(item)
        traces.append({
            "entity_id": entity_id,
            "behavior_id": behavior_id,
            "flow_id": flow_id,
            "runtime_mapping_path": runtime_mapping_path,
            "file_path": path,
            "export_name": export_name,
        })

    return {"template_inputs": template_inputs, "behavior_traces": traces, "validation_notes": ["deterministic interactive template plan"]}
