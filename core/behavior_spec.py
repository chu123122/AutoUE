from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from core.content_library import load_dead_cells_library
from core.runtime_support_matrix import SUPPORTED_ACTION_TYPES, check_capability_support

BEHAVIOR_SPEC_PATH = "flow/06-behavior-spec.json"
SUPPORT_CHECK_PATH = "flow/06-runtime-support-check.json"


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_") or "behavior"


def collect_selected_behaviors(entity_behavior: Mapping[str, Any]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for entity in entity_behavior.get("entities", []) if isinstance(entity_behavior, Mapping) else []:
        if not isinstance(entity, Mapping):
            continue
        for ability in entity.get("abilities", []) or []:
            if not isinstance(ability, Mapping):
                continue
            for behavior in ability.get("behaviors", []) or []:
                if isinstance(behavior, Mapping):
                    row = dict(behavior)
                    row.setdefault("entity_id", entity.get("entity_id", ""))
                    row.setdefault("ability_id", ability.get("ability_id", ""))
                    selected.append(row)
    return selected


def selected_capability_ids(entity_behavior: Mapping[str, Any]) -> list[str]:
    seen: list[str] = []
    for behavior in collect_selected_behaviors(entity_behavior):
        for capability_id in behavior.get("required_capability_ids", []) or []:
            if isinstance(capability_id, str) and capability_id and capability_id not in seen:
                seen.append(capability_id)
    return seen


def _flow_by_behavior(thin_flow: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for flow in (thin_flow or {}).get("flows", []) if isinstance(thin_flow, Mapping) else []:
        if isinstance(flow, Mapping) and flow.get("source_behavior_id"):
            result[str(flow["source_behavior_id"])] = dict(flow)
    return result


def _ports_for_flow(flow: Mapping[str, Any] | None) -> list[str]:
    ports: list[str] = []
    for stage in (flow or {}).get("stages", []) if isinstance(flow, Mapping) else []:
        if not isinstance(stage, Mapping):
            continue
        for port in stage.get("engine_ports", []) or []:
            if isinstance(port, str) and port and port not in ports:
                ports.append(port)
    return ports


def _action_from_capability(capability_id: str, capability: Mapping[str, Any]) -> list[dict[str, Any]]:
    kind = str(capability.get("capability_kind") or "")
    action = str(capability.get("action_kind") or "")
    entity_id = str(capability.get("entity_id") or "")
    if kind == "apply_effect" and action == "apply_freeze":
        return [{"type": "write_state", "key": "player.effects.frozen", "value": {"active": True, "duration": 1.25}, "capability_id": capability_id}]
    if kind == "movement_gate" and action == "block_by_state":
        return [{"type": "movement_gate", "target_entity_id": "player", "blocked_by": "player.effects.frozen", "capability_id": capability_id}]
    if kind == "vfx_binding" and action == "set_visible_while_state":
        return [{"type": "set_vfx_visible", "entity_id": entity_id, "visible_while": "player.effects.frozen", "capability_id": capability_id}]
    if kind == "camera_feedback" and action == "camera_impulse":
        return [{"type": "camera_impulse", "duration": 0.35, "capability_id": capability_id}]
    if kind == "hud_binding" and action == "refresh_value":
        return [{"type": "set_hud_value", "entity_id": entity_id, "source": "state_blackboard", "capability_id": capability_id}]
    if kind == "gate_lock" and action == "evaluate_unlock":
        return [{"type": "unlock_exit", "entity_id": entity_id, "state_key": f"exit.{entity_id}.unlocked", "capability_id": capability_id}]
    if kind == "level_transition" and action == "activate_transition":
        return [{"type": "open_exit", "entity_id": entity_id, "capability_id": capability_id}]
    if kind == "vfx_binding" and action == "spawn_particles":
        return [{"type": "spawn_vfx", "entity_id": entity_id, "capability_id": capability_id}]
    return []


def _actions_for_behavior(behavior: Mapping[str, Any]) -> list[dict[str, Any]]:
    explicit = behavior.get("effects")
    if isinstance(explicit, list) and explicit and all(isinstance(item, Mapping) and item.get("type") in SUPPORTED_ACTION_TYPES for item in explicit):
        return [dict(item) for item in explicit]
    lib = load_dead_cells_library()
    actions: list[dict[str, Any]] = []
    for capability_id in behavior.get("required_capability_ids", []) or []:
        capability = lib["capabilities"].get(capability_id)
        if isinstance(capability, Mapping):
            actions.extend(_action_from_capability(capability_id, capability))
    return actions


def _conditions_for_behavior(behavior: Mapping[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw = behavior.get("conditions")
    if isinstance(raw, list):
        conditions = [dict(item) for item in raw if isinstance(item, Mapping)]
    else:
        conditions = []
    for action in actions:
        if action.get("type") == "write_state" and action.get("key") == "player.effects.frozen":
            probe = {"type": "state_not_active", "key": "player.effects.frozen"}
            if probe not in conditions:
                conditions.append(probe)
    return conditions


def compile_behavior_spec(entity_behavior: Mapping[str, Any], thin_flow: Mapping[str, Any] | None = None, runtime_mapping: Mapping[str, Any] | None = None) -> dict[str, Any]:
    lib = load_dead_cells_library()
    flows = _flow_by_behavior(thin_flow)
    behaviors: list[dict[str, Any]] = []
    for behavior in collect_selected_behaviors(entity_behavior):
        behavior_id = str(behavior.get("behavior_id") or "")
        if behavior_id not in lib["behaviors"]:
            raise ValueError(f"BehaviorSpecCompiler: unknown behavior_id: {behavior_id}")
        canonical = dict(lib["behaviors"][behavior_id])
        canonical.update({k: v for k, v in behavior.items() if k not in {"effects"}})
        required = list(canonical.get("required_capability_ids") or [])
        missing = [capability_id for capability_id in required if capability_id not in lib["capabilities"]]
        if missing:
            raise ValueError(f"BehaviorSpecCompiler: behavior {behavior_id} references unknown capabilities: {missing}")
        actions = _actions_for_behavior(canonical)
        unknown_actions = sorted({str(action.get("type")) for action in actions if action.get("type") not in SUPPORTED_ACTION_TYPES})
        if unknown_actions:
            raise ValueError(f"BehaviorSpecCompiler: behavior {behavior_id} uses unknown action types: {unknown_actions}")
        flow = flows.get(behavior_id, {})
        trigger = canonical.get("trigger_model") if isinstance(canonical.get("trigger_model"), Mapping) else {"type": "manual", "description": canonical.get("trigger", "")}
        logs = canonical.get("verification_logs")
        if not isinstance(logs, list) or not logs:
            logs = [f"BehaviorTriggered {behavior_id}"]
            for action in actions:
                if action.get("type") == "write_state":
                    logs.append(f"StateWritten {action.get('key')}")
                elif action.get("type") == "set_vfx_visible":
                    logs.append(f"VfxVisible {action.get('entity_id')}")
                elif action.get("type") == "camera_impulse":
                    logs.append("CameraImpulse")
        behaviors.append({
            "behavior_id": behavior_id,
            "primary_entity_id": canonical.get("primary_entity_id") or canonical.get("entity_id"),
            "entity_id": canonical.get("entity_id"),
            "ability_id": canonical.get("ability_id"),
            "flow_id": flow.get("flow_id") or f"flow_{_safe_id(behavior_id)}",
            "trigger": dict(trigger),
            "conditions": _conditions_for_behavior(canonical, actions),
            "actions": actions,
            "required_capability_ids": required,
            "engine_port_ids": _ports_for_flow(flow),
            "verification_logs": [str(item) for item in logs],
        })
    return {
        "schema_version": "autoue-behavior-spec/v1",
        "source_nodes": ["EntityAbilityBehaviorPlanner", "ThinGameplayFlowPlanner", "PuerTSRuntimeMappingPlanner"],
        "behaviors": behaviors,
    }


def check_behavior_spec_support(behavior_spec: Mapping[str, Any]) -> dict[str, Any]:
    capability_ids: list[str] = []
    behavior_by_capability: dict[str, list[str]] = {}
    for behavior in behavior_spec.get("behaviors", []) if isinstance(behavior_spec, Mapping) else []:
        if not isinstance(behavior, Mapping):
            continue
        behavior_id = str(behavior.get("behavior_id") or "")
        for capability_id in behavior.get("required_capability_ids", []) or []:
            if isinstance(capability_id, str) and capability_id:
                if capability_id not in capability_ids:
                    capability_ids.append(capability_id)
                behavior_by_capability.setdefault(capability_id, []).append(behavior_id)
    check = check_capability_support(capability_ids)
    unsupported_behaviors = sorted({bid for item in check["unsupported_capabilities"] for bid in behavior_by_capability.get(item.get("capability_id", ""), [])})
    check["unsupported_behaviors"] = unsupported_behaviors
    check["behavior_by_capability"] = {key: sorted(set(value)) for key, value in sorted(behavior_by_capability.items())}
    return check


def write_behavior_artifacts(root: str | Path, behavior_spec: Mapping[str, Any], support_check: Mapping[str, Any]) -> None:
    root_path = Path(root).resolve()
    (root_path / BEHAVIOR_SPEC_PATH).parent.mkdir(parents=True, exist_ok=True)
    (root_path / BEHAVIOR_SPEC_PATH).write_text(json.dumps(behavior_spec, ensure_ascii=False, indent=2), encoding="utf-8")
    (root_path / SUPPORT_CHECK_PATH).write_text(json.dumps(support_check, ensure_ascii=False, indent=2), encoding="utf-8")


def compile_and_check(entity_behavior: Mapping[str, Any], thin_flow: Mapping[str, Any] | None = None, runtime_mapping: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = compile_behavior_spec(entity_behavior, thin_flow, runtime_mapping)
    return spec, check_behavior_spec_support(spec)
