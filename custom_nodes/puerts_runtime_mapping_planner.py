from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from core.BaseLLMNode import BaseLLMNode, GraphState
from core.behavior_spec import BEHAVIOR_SPEC_PATH, SUPPORT_CHECK_PATH, collect_selected_behaviors, compile_and_check, write_behavior_artifacts
from core.content_library import load_dead_cells_library
from core.workflow_validation import RUNTIME_MAPPING_PATH, parse_node_json, validate_graph_node_output, validate_node_output

PUERTS_RUNTIME_MAPPING_PLANNER_PROMPT = """SCHEMA: PuerTSRuntimeMappingPlanner
Deterministic Python node. Compile Entity/Capability/Behavior IDs plus thin flow/MCP evidence into BehaviorSpec and runtime support mapping. Unsupported support matrix entries must hard fail; do not invent TypeScript.
"""


def _output_root(state: GraphState) -> Path:
    save_dir = getattr(state, "save_dir", "")
    if not save_dir:
        raise RuntimeError("state.save_dir is required for runtime mapping emission")
    root = Path(save_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _queries_by_port(mcp_output: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for query in mcp_output.get("queries", []) if isinstance(mcp_output, Mapping) else []:
        if isinstance(query, Mapping) and query.get("engine_port_id"):
            out[str(query["engine_port_id"])] = dict(query)
    return out


def _ports_for_behavior(thin_flow: Mapping[str, Any], behavior_id: str) -> list[str]:
    ports: list[str] = []
    for flow in thin_flow.get("flows", []) if isinstance(thin_flow, Mapping) else []:
        if not isinstance(flow, Mapping) or flow.get("source_behavior_id") != behavior_id:
            continue
        for stage in flow.get("stages", []) or []:
            if not isinstance(stage, Mapping):
                continue
            for port in stage.get("engine_ports", []) or []:
                if isinstance(port, str) and port and port not in ports:
                    ports.append(port)
    return ports


def _helper_for_port(port: str) -> str:
    helpers = {
        "input.action_binding": "TriggerRouter.bindInputAction",
        "primitive.on_component_begin_overlap": "TriggerRouter.bindOverlapEnter",
        "component.set_visibility": "WorldAdapter.setVisibility",
        "camera.update_view_target": "WorldAdapter.cameraImpulse",
        "widget.set_text": "WorldAdapter.setHudText",
        "widget.set_percent": "WorldAdapter.setHudPercent",
        "widget.set_render_opacity": "WorldAdapter.setHudOpacity",
        "gameplay_statics.open_level": "WorldAdapter.openLevel",
    }
    return helpers.get(port, "WorldAdapter.unsupportedPort")




def _requires_enemy_encounter(entity_behavior: Mapping[str, Any], behavior_spec: Mapping[str, Any], support_check: Mapping[str, Any]) -> bool:
    lib = load_dead_cells_library()
    for behavior in collect_selected_behaviors(entity_behavior):
        runtime_features = behavior.get("runtime_features", [])
        if isinstance(runtime_features, list) and "enemy_encounter" in runtime_features:
            return True
        for capability_id in behavior.get("required_capability_ids", []) or []:
            capability = lib["capabilities"].get(capability_id)
            if isinstance(capability, Mapping) and "enemy_encounter" in (capability.get("runtime_features", []) or []):
                return True
    for behavior in behavior_spec.get("behaviors", []) if isinstance(behavior_spec, Mapping) else []:
        if not isinstance(behavior, Mapping):
            continue
        for capability_id in behavior.get("required_capability_ids", []) or []:
            capability = lib["capabilities"].get(capability_id)
            if isinstance(capability, Mapping) and "enemy_encounter" in (capability.get("runtime_features", []) or []):
                return True
    for row in support_check.get("unsupported_capabilities", []) if isinstance(support_check, Mapping) else []:
        if isinstance(row, Mapping):
            capability = lib["capabilities"].get(str(row.get("capability_id") or ""))
            if isinstance(capability, Mapping) and "enemy_encounter" in (capability.get("runtime_features", []) or []):
                return True
    return False


def _flow_id_by_behavior(thin_flow: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(flow.get("source_behavior_id")): str(flow.get("flow_id"))
        for flow in thin_flow.get("flows", []) if isinstance(flow, Mapping) and flow.get("source_behavior_id") and flow.get("flow_id")
    }


def build_runtime_mapping_output(state: GraphState) -> dict[str, Any]:
    entity_behavior = parse_node_json("EntityAbilityBehaviorPlanner", state.llm_outputs.get("EntityAbilityBehaviorPlanner", ""))
    thin_flow = parse_node_json("ThinGameplayFlowPlanner", state.llm_outputs.get("ThinGameplayFlowPlanner", ""))
    mcp_output = parse_node_json("UEApiMCPFeasibilitySearcher", state.llm_outputs.get("UEApiMCPFeasibilitySearcher", ""))
    behavior_spec, support_check = compile_and_check(entity_behavior, thin_flow)
    if getattr(state, "save_dir", ""):
        write_behavior_artifacts(state.save_dir, behavior_spec, support_check)

    disabled_features = [] if _requires_enemy_encounter(entity_behavior, behavior_spec, support_check) else ["enemy_encounter"]
    if support_check["status"] != "supported":
        return {
            "runtime_mapping_path": RUNTIME_MAPPING_PATH,
            "behavior_spec_path": BEHAVIOR_SPEC_PATH,
            "support_check_path": SUPPORT_CHECK_PATH,
            "runtime_features": support_check.get("required_runtime_modules", []),
            "disabled_features": disabled_features,
            "behavior_spec": behavior_spec,
            "support_check": support_check,
            "mappings": [],
            "blocked_mappings": [
                {
                    "behavior_id": behavior_id,
                    "reason": "unsupported capability in RuntimeSupportMatrix",
                }
                for behavior_id in support_check.get("unsupported_behaviors", [])
            ],
        }

    by_port = _queries_by_port(mcp_output)
    flow_ids = _flow_id_by_behavior(thin_flow)
    mappings: list[dict[str, Any]] = []
    runtime_owner = "TypeScript/content/generated/AutoUEBehaviorSpec.generated.ts"
    for behavior in behavior_spec.get("behaviors", []):
        behavior_id = behavior["behavior_id"]
        ports = _ports_for_behavior(thin_flow, behavior_id)
        port_rows: list[dict[str, Any]] = []
        for port in ports:
            query = by_port.get(port, {})
            port_rows.append({
                "engine_port_id": port,
                "adjudication_path": query.get("adjudication_path") or f"flow/04-ue-api-mcp/adjudication/{port}.json",
                "adapter_or_helper": _helper_for_port(port),
                "verdict": query.get("verdict", "hit"),
                "evidence_symbols": query.get("evidence_symbols", []),
            })
        mappings.append({
            "entity_id": behavior.get("entity_id") or behavior.get("primary_entity_id"),
            "ability_id": behavior.get("ability_id"),
            "behavior_id": behavior_id,
            "flow_id": flow_ids.get(behavior_id, behavior.get("flow_id")),
            "runtime_owner": runtime_owner,
            "implementation_carrier": "template_rendered_ts",
            "selected_runtime_owner": "AutoUEBehaviorSpec.generated",
            "existing_framework_candidates": ["AutoUE behavior runtime framework", "AIDev TypeScript Blueprint adapter"],
            "why_not_existing_framework": "Use generated BehaviorSpec with shared runtime framework instead of gameplay-specific TypeScript templates.",
            "temporary_or_canonical": "canonical",
            "migration_path": "Keep framework templates stable; regenerate BehaviorSpec data only.",
            "engine_port_mappings": port_rows,
            "thin_contracts": [stage.get("contract", "") for flow in thin_flow.get("flows", []) if flow.get("source_behavior_id") == behavior_id for stage in flow.get("stages", []) if isinstance(stage, Mapping)],
            "ability_binding": f"behavior_spec:{behavior_id}",
            "verification_evidence": behavior.get("verification_logs", []),
        })

    return {
        "runtime_mapping_path": RUNTIME_MAPPING_PATH,
        "behavior_spec_path": BEHAVIOR_SPEC_PATH,
        "support_check_path": SUPPORT_CHECK_PATH,
        "runtime_features": support_check.get("required_runtime_modules", []),
        "disabled_features": disabled_features,
        "behavior_spec": behavior_spec,
        "support_check": support_check,
        "mappings": mappings,
        "blocked_mappings": [],
    }


def build_runtime_mapping_context(node: BaseLLMNode, state: GraphState, full_input: str) -> None:
    required = {
        "EntityAbilityBehaviorPlanner": state.llm_outputs.get("EntityAbilityBehaviorPlanner", ""),
        "ThinGameplayFlowPlanner": state.llm_outputs.get("ThinGameplayFlowPlanner", ""),
        "UEApiMCPFeasibilitySearcher": state.llm_outputs.get("UEApiMCPFeasibilitySearcher", ""),
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing:
        raise RuntimeError(f"PuerTSRuntimeMappingPlanner missing upstream outputs: {missing}")
    node.full_input = "Deterministic runtime mapping; no LLM inference."


class DeterministicPuerTSRuntimeMappingPlanner(BaseLLMNode):
    def call_model(self, full_input: str, state: GraphState):  # noqa: D401
        if self.name not in state.node_token_usage:
            state.node_token_usage[self.name] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return json.dumps(build_runtime_mapping_output(state), ensure_ascii=False, indent=2)


def write_runtime_mapping(state: GraphState, output: str) -> None:
    data = parse_node_json("PuerTSRuntimeMappingPlanner", validate_node_output("PuerTSRuntimeMappingPlanner", output))
    target = _output_root(state) / RUNTIME_MAPPING_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if isinstance(data.get("behavior_spec"), dict) and isinstance(data.get("support_check"), dict):
        write_behavior_artifacts(state.save_dir, data["behavior_spec"], data["support_check"])
    print(f"[SUCCESS] PuerTS runtime mapping saved to: {target}")


def create_puerts_runtime_mapping_planner() -> BaseLLMNode:
    return DeterministicPuerTSRuntimeMappingPlanner(
        name="PuerTSRuntimeMappingPlanner",
        prompt=PUERTS_RUNTIME_MAPPING_PLANNER_PROMPT,
        pre_action=build_runtime_mapping_context,
        output_validator=validate_graph_node_output,
        post_action=write_runtime_mapping,
        enable_feedback=False,
    )
