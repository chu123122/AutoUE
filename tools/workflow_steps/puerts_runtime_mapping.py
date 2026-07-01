from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from core.behavior_spec import BEHAVIOR_SPEC_PATH, SUPPORT_CHECK_PATH, collect_selected_behaviors, compile_and_check, write_behavior_artifacts
from core.content_library import load_dead_cells_library
from core.encounter_validation import ENCOUNTER_SPEC_PATH, SCENE_SPAWN_MANIFEST_PATH
from core.workflow_validation import RUNTIME_MAPPING_PATH, parse_node_json

ENTITY_NODE = "EntityAbilityBehaviorPlanner"
THIN_NODE = "ThinGameplayFlowPlanner"
ENCOUNTER_NODE = "EncounterSpecPlanner"
MCP_NODE = "UEApiMCPFeasibilitySearcher"
ENCOUNTER_RUNTIME_MODULES = [
    "encounter_spec_data",
    "spawn_point_registry",
    "enemy_spawn_manager",
    "encounter_manager",
    "enemy_spawn_runtime",
]


def _queries_by_port(mcp_output: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for query in mcp_output.get("queries", []) if isinstance(mcp_output, Mapping) else []:
        if isinstance(query, Mapping) and query.get("engine_port_id"):
            out[str(query["engine_port_id"])] = dict(query)
    return out


def _ports_for_behavior(thin_flow: Mapping[str, Any], behavior_id: str, entity_id: str | None = None) -> list[str]:
    ports: list[str] = []
    for flow in thin_flow.get("flows", []) if isinstance(thin_flow, Mapping) else []:
        if not isinstance(flow, Mapping) or flow.get("source_behavior_id") != behavior_id:
            continue
        if entity_id and flow.get("entity_id") != entity_id:
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
        "actor.spawn": "WorldAdapter.spawnActor",
        "actor.destroy": "WorldAdapter.destroyActor",
        "actor.get_distance_to": "WorldAdapter.getDistanceBetweenActors",
        "actor.set_actor_location": "WorldAdapter.setActorLocation",
        "actor.on_destroyed": "WorldAdapter.bindOnDestroyed",
        "actor.on_take_any_damage": "WorldAdapter.bindOnTakeAnyDamage",
        "actor.get_forward_vector": "WorldAdapter.getForwardVector",
        "projectile.spawn": "WorldAdapter.spawnProjectile",
        "encounter.alive_count": "EncounterManager.completeWhenAllDead",
    }
    return helpers.get(port, "WorldAdapter.unsupportedPort")


def _requires_enemy_encounter(entity_behavior: Mapping[str, Any], behavior_spec: Mapping[str, Any], support_check: Mapping[str, Any]) -> bool:
    lib = load_dead_cells_library()
    for behavior in collect_selected_behaviors(entity_behavior):
        runtime_features = behavior.get("runtime_features", [])
        if isinstance(runtime_features, list) and ({"enemy_encounter", "enemy_runtime"} & set(runtime_features)):
            return True
        for capability_id in behavior.get("required_capability_ids", []) or []:
            capability = lib["capabilities"].get(capability_id)
            if isinstance(capability, Mapping) and ({"enemy_encounter", "enemy_runtime"} & set(capability.get("runtime_features", []) or [])):
                return True
    for behavior in behavior_spec.get("behaviors", []) if isinstance(behavior_spec, Mapping) else []:
        if not isinstance(behavior, Mapping):
            continue
        for capability_id in behavior.get("required_capability_ids", []) or []:
            capability = lib["capabilities"].get(capability_id)
            if isinstance(capability, Mapping) and ({"enemy_encounter", "enemy_runtime"} & set(capability.get("runtime_features", []) or [])):
                return True
    for row in support_check.get("unsupported_capabilities", []) if isinstance(support_check, Mapping) else []:
        if isinstance(row, Mapping):
            capability = lib["capabilities"].get(str(row.get("capability_id") or ""))
            if isinstance(capability, Mapping) and ({"enemy_encounter", "enemy_runtime"} & set(capability.get("runtime_features", []) or [])):
                return True
    return False


def _flow_key(entity_id: str, behavior_id: str) -> str:
    return f"{entity_id}::{behavior_id}" if entity_id else behavior_id


def _flow_id_by_behavior(thin_flow: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    counts: dict[str, int] = {}
    for flow in thin_flow.get("flows", []) if isinstance(thin_flow, Mapping) else []:
        if not isinstance(flow, Mapping) or not flow.get("source_behavior_id") or not flow.get("flow_id"):
            continue
        behavior_id = str(flow.get("source_behavior_id"))
        entity_id = str(flow.get("entity_id") or "")
        counts[behavior_id] = counts.get(behavior_id, 0) + 1
        out[_flow_key(entity_id, behavior_id)] = str(flow.get("flow_id"))
    for key, flow_id in list(out.items()):
        behavior_id = key.split("::", 1)[-1]
        if counts.get(behavior_id, 0) == 1:
            out[behavior_id] = flow_id
    return out


def _with_required_modules(modules: list[Any], required: list[str]) -> list[str]:
    out: list[str] = []
    for item in modules:
        if isinstance(item, str) and item and item not in out:
            out.append(item)
    for item in required:
        if item not in out:
            out.append(item)
    return out


def _has_runtime_encounters(encounter_spec: Mapping[str, Any]) -> bool:
    encounters = encounter_spec.get("encounters", []) if isinstance(encounter_spec, Mapping) else []
    return any(isinstance(item, Mapping) for item in encounters)


def run_puerts_runtime_mapping(inputs: dict[str, str], *, save_dir: str = "") -> dict[str, Any]:
    entity_behavior = parse_node_json(ENTITY_NODE, inputs.get("entity_behavior", ""))
    thin_flow = parse_node_json(THIN_NODE, inputs.get("thin_flow", ""))
    encounter_spec = parse_node_json(ENCOUNTER_NODE, inputs.get("encounter_spec", "{}")) if inputs.get("encounter_spec", "").strip() else {"schema_version": "autoue-encounter-spec/v1", "encounters": []}
    mcp_output = parse_node_json(MCP_NODE, inputs.get("ue_api_feasibility", ""))
    behavior_spec, support_check = compile_and_check(entity_behavior, thin_flow)
    if save_dir:
        Path(save_dir).resolve().mkdir(parents=True, exist_ok=True)
        write_behavior_artifacts(save_dir, behavior_spec, support_check)

    uses_runtime_encounter = _requires_enemy_encounter(entity_behavior, behavior_spec, support_check) or _has_runtime_encounters(encounter_spec)
    disabled_features = [] if uses_runtime_encounter else ["enemy_encounter", "enemy_runtime"]
    runtime_features = _with_required_modules(support_check.get("required_runtime_modules", []), ENCOUNTER_RUNTIME_MODULES if uses_runtime_encounter else [])
    if support_check["status"] != "supported":
        return {
            "runtime_mapping_path": RUNTIME_MAPPING_PATH,
            "behavior_spec_path": BEHAVIOR_SPEC_PATH,
            "support_check_path": SUPPORT_CHECK_PATH,
            "encounter_spec_path": ENCOUNTER_SPEC_PATH,
            "scene_spawn_manifest_path": SCENE_SPAWN_MANIFEST_PATH,
            "runtime_features": runtime_features,
            "disabled_features": disabled_features,
            "behavior_spec": behavior_spec,
            "encounter_spec": encounter_spec,
            "support_check": support_check,
            "mappings": [],
            "blocked_mappings": [{"behavior_id": behavior_id, "reason": "unsupported capability in RuntimeSupportMatrix"} for behavior_id in support_check.get("unsupported_behaviors", [])],
        }

    by_port = _queries_by_port(mcp_output)
    flow_ids = _flow_id_by_behavior(thin_flow)
    mappings: list[dict[str, Any]] = []
    runtime_owner = "TypeScript/content/generated/AutoUEBehaviorSpec.generated.ts"
    for behavior in behavior_spec.get("behaviors", []):
        behavior_id = behavior["behavior_id"]
        entity_id = str(behavior.get("entity_id") or behavior.get("primary_entity_id") or "")
        ports = _ports_for_behavior(thin_flow, behavior_id, entity_id)
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
            "entity_id": entity_id,
            "behavior_id": behavior_id,
            "flow_id": flow_ids.get(_flow_key(entity_id, behavior_id), flow_ids.get(behavior_id, behavior.get("flow_id"))),
            "runtime_owner": runtime_owner,
            "implementation_carrier": "template_rendered_ts",
            "selected_runtime_owner": "AutoUEBehaviorSpec.generated",
            "existing_framework_candidates": ["AutoUE behavior runtime framework", "AIDev TypeScript Blueprint adapter"],
            "why_not_existing_framework": "Use generated BehaviorSpec with shared runtime framework instead of gameplay-specific TypeScript templates.",
            "temporary_or_canonical": "canonical",
            "migration_path": "Keep framework templates stable; regenerate BehaviorSpec data only.",
            "engine_port_mappings": port_rows,
            "thin_contracts": [stage.get("contract", "") for flow in thin_flow.get("flows", []) if flow.get("source_behavior_id") == behavior_id and (not entity_id or flow.get("entity_id") == entity_id) for stage in flow.get("stages", []) if isinstance(stage, Mapping)],
            "ability_binding": f"behavior_spec:{behavior_id}",
            "verification_evidence": behavior.get("verification_logs", []),
        })

    return {
        "runtime_mapping_path": RUNTIME_MAPPING_PATH,
        "behavior_spec_path": BEHAVIOR_SPEC_PATH,
        "support_check_path": SUPPORT_CHECK_PATH,
        "encounter_spec_path": ENCOUNTER_SPEC_PATH,
        "scene_spawn_manifest_path": SCENE_SPAWN_MANIFEST_PATH,
        "runtime_features": runtime_features,
        "disabled_features": disabled_features,
        "behavior_spec": behavior_spec,
        "encounter_spec": encounter_spec,
        "support_check": support_check,
        "mappings": mappings,
        "blocked_mappings": [],
    }
