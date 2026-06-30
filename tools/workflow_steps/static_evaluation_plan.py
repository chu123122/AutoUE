from __future__ import annotations

import re
from typing import Any, Mapping

from core.workflow_validation import parse_node_json

SCENE_NODE = "SceneAndGameplaySplitter"
ENTITY_NODE = "EntityAbilityBehaviorPlanner"
THIN_NODE = "ThinGameplayFlowPlanner"
ENCOUNTER_NODE = "EncounterSpecPlanner"
MCP_NODE = "UEApiMCPFeasibilitySearcher"
RUNTIME_NODE = "PuerTSRuntimeMappingCompiler"
SLOT_NODE = "TypeScriptImplementationSlotProjector"
INTERACTIVE_NODE = "TypeScriptInteractiveTemplatePlanner"
CODEGEN_NODE = "TypeScriptRuntimeTemplatePlanner"


def _safe_action(behavior_id: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", behavior_id).strip("_")
    return f"validate_{text or 'behavior'}"


def _interactive_by_behavior(interactive: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for trace in interactive.get("behavior_traces", []) if isinstance(interactive, Mapping) else []:
        if isinstance(trace, Mapping) and trace.get("behavior_id"):
            out[str(trace["behavior_id"])] = {"file_path": str(trace.get("file_path") or ""), "export_name": str(trace.get("export_name") or "")}
    return out


def _codegen_files(codegen: Mapping[str, Any]) -> list[str]:
    files: list[str] = []
    for item in codegen.get("template_inputs", []) if isinstance(codegen, Mapping) else []:
        if isinstance(item, Mapping) and isinstance(item.get("path"), str) and item["path"] not in files:
            files.append(str(item["path"]))
    return files


def run_static_evaluation_plan(inputs: dict[str, str]) -> dict[str, Any]:
    parse_node_json(SCENE_NODE, inputs.get("scene_gameplay_split", ""))
    parse_node_json(ENTITY_NODE, inputs.get("entity_behavior", ""))
    parse_node_json(THIN_NODE, inputs.get("thin_flow", ""))
    parse_node_json(ENCOUNTER_NODE, inputs.get("encounter_spec", ""))
    parse_node_json(MCP_NODE, inputs.get("ue_api_feasibility", ""))
    mapping = parse_node_json(RUNTIME_NODE, inputs.get("runtime_mapping", ""))
    parse_node_json(SLOT_NODE, inputs.get("ts_slots", ""))
    interactive = parse_node_json(INTERACTIVE_NODE, inputs.get("interactive_ts_plan", ""))
    codegen = parse_node_json(CODEGEN_NODE, inputs.get("typescript_codegen", ""))

    runtime_mapping_path = mapping.get("runtime_mapping_path", "")
    interactive_lookup = _interactive_by_behavior(interactive)
    codegen_files = _codegen_files(codegen)
    instructions: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []

    for index, runtime_mapping in enumerate(mapping.get("mappings", []), start=1):
        if not isinstance(runtime_mapping, Mapping):
            continue
        behavior_id = str(runtime_mapping.get("behavior_id") or "")
        entity_id = str(runtime_mapping.get("entity_id") or "")
        flow_id = str(runtime_mapping.get("flow_id") or "")
        ports = [str(p.get("engine_port_id")) for p in runtime_mapping.get("engine_port_mappings", []) if isinstance(p, Mapping) and p.get("engine_port_id")]
        adjudications = [str(p.get("adjudication_path")) for p in runtime_mapping.get("engine_port_mappings", []) if isinstance(p, Mapping) and p.get("adjudication_path")]
        interactive_trace = interactive_lookup.get(behavior_id, {})
        ts_files = [p for p in [interactive_trace.get("file_path")] if p] + codegen_files
        trace = {
            "entity_id": entity_id,
            "behavior_id": behavior_id,
            "flow_id": flow_id,
            "engine_port_ids": ports,
            "adjudication_paths": adjudications,
            "runtime_mapping_path": runtime_mapping_path,
            "ts_files": ts_files,
        }
        expected = [
            {"type": "static_trace_present", "key": "ability_module_export", "expected_value": "getAutoUEBehaviorSpec"},
            {"type": "static_trace_present", "key": "engine_ports_mapped", "expected_value": ports},
        ]
        if interactive_trace.get("export_name"):
            expected.insert(1, {"type": "static_trace_present", "key": "interactive_adapter_export", "expected_value": interactive_trace["export_name"]})
        instructions.append({
            "step_id": index,
            "action": _safe_action(behavior_id),
            "target": entity_id or behavior_id,
            "description": f"validate static adapter trace for {behavior_id}",
            "driver": "adapter_call",
            "executor_action": "call_behavior",
            "expected": expected,
            "trace": trace,
        })
        coverage.append(trace)

    return {"evaluation_instructions": instructions, "coverage": coverage}
