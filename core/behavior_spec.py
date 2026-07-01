from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from core.behavior_recipes import compile_behavior_recipe, has_behavior_recipe, primitive_support_summary
from core.content_library import load_dead_cells_library
from core.runtime_support_matrix import DEFAULT_SUPPORT_MATRIX, FRAMEWORK_RUNTIME_MODULES, SUPPORTED_ACTION_TYPES, check_capability_support

BEHAVIOR_SPEC_PATH = "flow/06-behavior-spec.json"
SUPPORT_CHECK_PATH = "flow/06-runtime-support-check.json"


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_") or "behavior"


def collect_selected_behaviors(entity_behavior: Mapping[str, Any]) -> list[dict[str, Any]]:
    lib = load_dead_cells_library()
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entity in entity_behavior.get("entities", []) if isinstance(entity_behavior, Mapping) else []:
        if not isinstance(entity, Mapping):
            continue
        entity_id = str(entity.get("entity_id") or "")
        for capability in entity.get("capabilities", []) or []:
            if not isinstance(capability, Mapping):
                continue
            for behavior in capability.get("behaviors", []) or []:
                if not isinstance(behavior, Mapping):
                    continue
                behavior_id = str(behavior.get("behavior_id") or "")
                key = (entity_id, behavior_id)
                if not behavior_id or key in seen:
                    continue
                seen.add(key)
                row = dict(lib["behaviors"].get(behavior_id, behavior))
                row["bound_entity_id"] = entity_id
                row["entity_id"] = entity_id
                selected.append(row)
    return selected


def selected_capability_ids(entity_behavior: Mapping[str, Any]) -> list[str]:
    seen: list[str] = []
    for behavior in collect_selected_behaviors(entity_behavior):
        for capability_id in behavior.get("required_capability_ids", []) or []:
            if isinstance(capability_id, str) and capability_id and capability_id not in seen:
                seen.append(capability_id)
    return seen


def _flow_key(entity_id: str, behavior_id: str) -> str:
    return f"{entity_id}::{behavior_id}" if entity_id else behavior_id


def _flow_by_behavior(thin_flow: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    flows: dict[str, dict[str, Any]] = {}
    counts: dict[str, int] = {}
    for flow in (thin_flow or {}).get("flows", []) if isinstance(thin_flow, Mapping) else []:
        if not isinstance(flow, Mapping) or not flow.get("source_behavior_id"):
            continue
        behavior_id = str(flow["source_behavior_id"])
        entity_id = str(flow.get("entity_id") or "")
        counts[behavior_id] = counts.get(behavior_id, 0) + 1
        flows[_flow_key(entity_id, behavior_id)] = dict(flow)
    for key, flow in list(flows.items()):
        behavior_id = str(flow.get("source_behavior_id") or "")
        if counts.get(behavior_id, 0) == 1:
            flows[behavior_id] = flow
    return flows


def _ports_for_flow(flow: Mapping[str, Any] | None) -> list[str]:
    ports: list[str] = []
    for stage in (flow or {}).get("stages", []) if isinstance(flow, Mapping) else []:
        if isinstance(stage, Mapping):
            for port in stage.get("engine_ports", []) or []:
                if isinstance(port, str) and port and port not in ports:
                    ports.append(port)
    return ports


def _action_from_capability(capability_id: str, capability: Mapping[str, Any], params: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    kind = str(capability.get("capability_kind") or "")
    action = str(capability.get("action_kind") or "")
    resolved_params = dict(params or {})
    entity_id = str(resolved_params.get("entity_id") or resolved_params.get("bound_entity_id") or "")
    base = {"capability_id": capability_id, "entity_id": entity_id, "params": resolved_params}
    table = {
        ("apply_effect", "apply_freeze"): [{"type": "write_state", "key": "player.effects.frozen", "value": {"active": True, "duration": 1.25}, "capability_id": capability_id}],
        ("movement_gate", "block_by_state"): [{"type": "movement_gate", "target_entity_id": "player", "blocked_by": "player.effects.frozen", "capability_id": capability_id}],
        ("vfx_binding", "set_visible_while_state"): [{"type": "set_vfx_visible", "entity_id": entity_id, "visible_while": "player.effects.frozen", "capability_id": capability_id}],
        ("camera_feedback", "camera_impulse"): [{"type": "camera_impulse", "duration": 0.35, "capability_id": capability_id}],
        ("hud_binding", "refresh_value"): [{"type": "set_hud_value", "entity_id": entity_id, "source": "state_blackboard", "capability_id": capability_id}],
        ("gate_lock", "evaluate_unlock"): [{"type": "unlock_exit", "entity_id": entity_id, "state_key": f"exit.{entity_id}.unlocked", "capability_id": capability_id}],
        ("level_transition", "activate_transition"): [{"type": "open_exit", "entity_id": entity_id, "capability_id": capability_id}],
        ("vfx_binding", "spawn_particles"): [{"type": "spawn_vfx", "entity_id": entity_id, "capability_id": capability_id}],
    }
    if (kind, action) in table:
        return table[(kind, action)]
    enemy_actions = {
        ("enemy_spawn", "spawn_actor"): "enemy_spawn_actor",
        ("enemy_sensor", "detect_player_by_distance"): "enemy_detect_player",
        ("enemy_movement", "chase_target"): "enemy_chase_target",
        ("enemy_movement", "keep_distance"): "enemy_keep_distance",
        ("enemy_attack", "melee_hitbox"): "enemy_melee_attack",
        ("enemy_attack", "projectile_spawn"): "enemy_projectile_attack",
        ("enemy_attack", "self_destruct"): "enemy_self_destruct",
        ("enemy_defense", "directional_block"): "enemy_directional_block",
        ("enemy_health", "receive_damage"): "enemy_receive_damage",
        ("enemy_death", "emit_death_event"): "enemy_emit_death_event",
        ("encounter", "complete_when_all_dead"): "encounter_complete_when_all_dead",
    }
    if (kind, action) in enemy_actions:
        row = {"type": enemy_actions[(kind, action)], **base}
        if action in {"chase_target", "keep_distance", "melee_hitbox", "projectile_spawn", "self_destruct"}:
            row["target_entity_id"] = resolved_params.get("target_entity_id", "player")
        if action == "directional_block":
            row["source_entity_id"] = resolved_params.get("source_entity_id", "player")
        return [row]
    return []


def _entity_binding(entity: Mapping[str, Any] | None, capability_id: str) -> Mapping[str, Any] | None:
    for binding in (entity or {}).get("capability_bindings", []) if isinstance(entity, Mapping) else []:
        if isinstance(binding, Mapping) and binding.get("capability_id") == capability_id:
            return binding
    return None


def _validate_params(label: str, schema: Mapping[str, Any], params: Mapping[str, Any]) -> None:
    for key, rule in schema.items():
        if not isinstance(rule, Mapping):
            continue
        if rule.get("required") and key not in params:
            raise ValueError(f"BehaviorSpecCompiler: {label} missing required param {key}")


def resolve_behavior_capabilities(canonical: Mapping[str, Any]) -> list[dict[str, Any]]:
    lib = load_dead_cells_library()
    bound_entity_id = str(canonical.get("bound_entity_id") or canonical.get("entity_id") or canonical.get("primary_entity_id") or "")
    bound_entity = lib["entities"].get(bound_entity_id)
    overrides = canonical.get("capability_overrides", {}) if isinstance(canonical.get("capability_overrides", {}), Mapping) else {}
    resolved: list[dict[str, Any]] = []
    for capability_id in canonical.get("required_capability_ids", []) or []:
        capability = lib["capabilities"].get(capability_id)
        if not isinstance(capability, Mapping):
            raise ValueError(f"BehaviorSpecCompiler: unknown capability {capability_id}")
        binding = _entity_binding(bound_entity, capability_id)
        params = dict(capability.get("default_params") or {})
        if binding and isinstance(binding.get("params"), Mapping):
            params.update(dict(binding["params"]))
        override = overrides.get(capability_id)
        if isinstance(override, Mapping):
            params.update(dict(override))
        params.setdefault("bound_entity_id", bound_entity_id)
        params.setdefault("entity_id", bound_entity_id)
        _validate_params(f"{bound_entity_id}:{capability_id}", capability.get("params_schema", {}), params)
        entry = DEFAULT_SUPPORT_MATRIX.lookup(str(capability.get("capability_kind") or ""), str(capability.get("action_kind") or ""))
        resolved.append({
            "capability_id": capability_id,
            "capability_kind": capability.get("capability_kind"),
            "action_kind": capability.get("action_kind"),
            "handler": entry.handler if entry else capability.get("runtime_handler"),
            "params": params,
            "source_entity_binding": {"entity_id": bound_entity_id if binding else None, "capability_id": capability_id},
        })
    return resolved


def _actions_for_behavior(behavior: Mapping[str, Any]) -> list[dict[str, Any]]:
    explicit = behavior.get("effects")
    if isinstance(explicit, list) and explicit and all(isinstance(item, Mapping) and item.get("type") in SUPPORTED_ACTION_TYPES for item in explicit):
        return [dict(item) for item in explicit]
    lib = load_dead_cells_library()
    resolved_by_id = {str(item.get("capability_id")): item for item in behavior.get("resolved_capabilities", []) or [] if isinstance(item, Mapping) and item.get("capability_id")}
    actions: list[dict[str, Any]] = []
    for capability_id in behavior.get("required_capability_ids", []) or []:
        cap = lib["capabilities"].get(capability_id)
        if isinstance(cap, Mapping):
            params = resolved_by_id.get(capability_id, {}).get("params", {})
            actions.extend(_action_from_capability(capability_id, cap, params if isinstance(params, Mapping) else {}))
    return actions


def _attach_recipe_handlers(canonical: dict[str, Any], primitive_plan: list[dict[str, Any]]) -> None:
    if not primitive_plan:
        return
    behavior_id = str(canonical.get("behavior_id") or "")
    covered_capabilities = {str(step.get("capability_id") or "") for step in primitive_plan if step.get("capability_id")}
    for capability in canonical.get("resolved_capabilities", []) or []:
        if isinstance(capability, dict) and capability.get("capability_id") in covered_capabilities and not capability.get("handler"):
            capability["handler"] = f"BehaviorRecipe.{behavior_id}"


def _primitive_runtime_modules(primitive_plan: list[dict[str, Any]]) -> list[str]:
    modules: list[str] = []
    for step in primitive_plan:
        for module in step.get("required_runtime_modules", []) or []:
            if isinstance(module, str) and module and module not in modules:
                modules.append(module)
    return modules


def _conditions_for_behavior(behavior: Mapping[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw = behavior.get("conditions")
    conditions = [dict(item) for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []
    for action in actions:
        if action.get("type") == "write_state" and action.get("key") == "player.effects.frozen":
            probe = {"type": "state_not_active", "key": "player.effects.frozen"}
            if probe not in conditions:
                conditions.append(probe)
    return conditions


def _runtime_domain_for_behavior(canonical: Mapping[str, Any], actions: list[dict[str, Any]]) -> str:
    features = canonical.get("runtime_features", [])
    if isinstance(features, list) and "enemy_runtime" in features:
        return "enemy_runtime"
    if any(str(a.get("type", "")).startswith("enemy_") or a.get("type") == "encounter_complete_when_all_dead" for a in actions):
        return "enemy_runtime"
    return "behavior_runtime"


def _runtime_params_for_behavior(canonical: Mapping[str, Any]) -> dict[str, Any]:
    lib = load_dead_cells_library()
    entity = lib["entities"].get(str(canonical.get("bound_entity_id") or canonical.get("entity_id") or ""))
    params = dict(entity.get("runtime") or {}) if isinstance(entity, Mapping) else {}
    if isinstance(canonical.get("runtime_params"), Mapping):
        params.update(dict(canonical["runtime_params"]))
    for resolved in canonical.get("resolved_capabilities", []) or []:
        if isinstance(resolved, Mapping) and resolved.get("capability_id") == "enemy.spawn.spawn_actor" and isinstance(resolved.get("params"), Mapping):
            params.update(dict(resolved["params"]))
    return params


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
        canonical.setdefault("bound_entity_id", canonical.get("entity_id") or canonical.get("primary_entity_id"))
        required = list(canonical.get("required_capability_ids") or [])
        missing = [cid for cid in required if cid not in lib["capabilities"]]
        if missing:
            raise ValueError(f"BehaviorSpecCompiler: behavior {behavior_id} references unknown capabilities: {missing}")
        canonical["resolved_capabilities"] = resolve_behavior_capabilities(canonical)
        primitive_plan = compile_behavior_recipe(canonical) if has_behavior_recipe(behavior_id) else []
        _attach_recipe_handlers(canonical, primitive_plan)
        actions = _actions_for_behavior(canonical)
        unknown = sorted({str(a.get("type")) for a in actions if a.get("type") not in SUPPORTED_ACTION_TYPES})
        if unknown:
            raise ValueError(f"BehaviorSpecCompiler: behavior {behavior_id} uses unknown action types: {unknown}")
        flow = flows.get(_flow_key(str(canonical.get("bound_entity_id") or canonical.get("entity_id") or ""), behavior_id), flows.get(behavior_id, {}))
        trigger = canonical.get("trigger_model") if isinstance(canonical.get("trigger_model"), Mapping) else {"type": "manual", "description": canonical.get("trigger", "")}
        logs = canonical.get("verification_logs") if isinstance(canonical.get("verification_logs"), list) else None
        if not logs:
            logs = [f"BehaviorTriggered {behavior_id}"] + [f"ActionDispatched {a.get('type')}" for a in actions]
            logs += [f"PrimitiveReady {step['primitive_id']}" for step in primitive_plan]
        runtime_features = list(canonical.get("runtime_features") or [])
        for module in _primitive_runtime_modules(primitive_plan):
            if module not in runtime_features:
                runtime_features.append(module)
        behaviors.append({
            "behavior_id": behavior_id,
            "bound_entity_id": canonical.get("bound_entity_id"),
            "primary_entity_id": canonical.get("primary_entity_id") or canonical.get("entity_id"),
            "entity_id": canonical.get("entity_id"),
            "runtime_domain": _runtime_domain_for_behavior(canonical, actions),
            "runtime_features": runtime_features,
            "runtime_params": _runtime_params_for_behavior(canonical),
            "resolved_capabilities": list(canonical.get("resolved_capabilities") or []),
            "primitive_plan": primitive_plan,
            "presentation_effects": [],
            "flow_id": flow.get("flow_id") or f"flow_{_safe_id(behavior_id)}",
            "trigger": dict(trigger),
            "conditions": _conditions_for_behavior(canonical, actions),
            "actions": actions,
            "required_capability_ids": required,
            "engine_port_ids": _ports_for_flow(flow),
            "verification_logs": [str(item) for item in logs],
        })
    return {"schema_version": "autoue-behavior-spec/v1", "source_nodes": ["EntityAbilityBehaviorPlanner", "ThinGameplayFlowPlanner", "PuerTSRuntimeMappingCompiler"], "behaviors": behaviors}


def check_behavior_spec_support(behavior_spec: Mapping[str, Any]) -> dict[str, Any]:
    capability_ids: list[str] = []
    behavior_by_capability: dict[str, list[str]] = {}
    recipe_covered_capabilities: set[str] = set()
    recipe_behavior_ids: set[str] = set()
    primitive_plan: list[Mapping[str, Any]] = []
    for behavior in behavior_spec.get("behaviors", []) if isinstance(behavior_spec, Mapping) else []:
        if isinstance(behavior, Mapping):
            behavior_id = str(behavior.get("behavior_id") or "")
            behavior_primitives = [step for step in behavior.get("primitive_plan", []) or [] if isinstance(step, Mapping)]
            if behavior_primitives:
                recipe_behavior_ids.add(behavior_id)
                primitive_plan.extend(behavior_primitives)
                for step in behavior_primitives:
                    capability_id = step.get("capability_id")
                    if isinstance(capability_id, str) and capability_id:
                        recipe_covered_capabilities.add(capability_id)
            for capability_id in behavior.get("required_capability_ids", []) or []:
                if isinstance(capability_id, str) and capability_id:
                    if capability_id not in capability_ids:
                        capability_ids.append(capability_id)
                    behavior_by_capability.setdefault(capability_id, []).append(behavior_id)
    base_check = check_capability_support(capability_ids)
    primitive_check = primitive_support_summary(list(primitive_plan))
    unsupported_primitives = list(primitive_check["unsupported_primitives"])
    can_cover_by_recipe = not unsupported_primitives
    unsupported_capabilities = [
        item for item in base_check["unsupported_capabilities"]
        if not (can_cover_by_recipe and item.get("capability_id") in recipe_covered_capabilities)
    ]
    supported_capabilities = list(base_check["supported_capabilities"])
    if can_cover_by_recipe:
        for item in base_check["unsupported_capabilities"]:
            capability_id = str(item.get("capability_id") or "")
            if capability_id in recipe_covered_capabilities:
                supported_capabilities.append({
                    **item,
                    "supported": True,
                    "handler": "BehaviorRecipe.primitive_plan",
                    "reason": "covered by supported Behavior Recipe primitives",
                })
    required_modules = set(FRAMEWORK_RUNTIME_MODULES)
    required_modules.update(base_check.get("required_runtime_modules", []))
    required_modules.update(primitive_check.get("required_runtime_modules", []))
    engine_ports = set(base_check.get("engine_ports", []))
    engine_ports.update(primitive_check.get("engine_ports", []))
    unsupported_behaviors = sorted({
        bid
        for item in unsupported_capabilities
        for bid in behavior_by_capability.get(item.get("capability_id", ""), [])
    })
    if unsupported_primitives:
        unsupported_behaviors = sorted(set(unsupported_behaviors) | recipe_behavior_ids)
    status = "unsupported" if unsupported_capabilities or unsupported_primitives else "supported"
    return {
        "schema_version": "autoue-runtime-support-check/v2",
        "status": status,
        "static_support": status,
        "runtime_proof": "not_run",
        "required_runtime_modules": sorted(required_modules),
        "engine_ports": sorted(engine_ports),
        "supported_capabilities": supported_capabilities,
        "unsupported_capabilities": unsupported_capabilities,
        "supported_primitives": primitive_check["supported_primitives"],
        "unsupported_primitives": unsupported_primitives,
        "unsupported_behaviors": unsupported_behaviors,
        "behavior_by_capability": {k: sorted(set(v)) for k, v in sorted(behavior_by_capability.items())},
    }


def write_behavior_artifacts(root: str | Path, behavior_spec: Mapping[str, Any], support_check: Mapping[str, Any]) -> None:
    root_path = Path(root).resolve()
    (root_path / BEHAVIOR_SPEC_PATH).parent.mkdir(parents=True, exist_ok=True)
    (root_path / BEHAVIOR_SPEC_PATH).write_text(json.dumps(behavior_spec, ensure_ascii=False, indent=2), encoding="utf-8")
    (root_path / SUPPORT_CHECK_PATH).write_text(json.dumps(support_check, ensure_ascii=False, indent=2), encoding="utf-8")


def compile_and_check(entity_behavior: Mapping[str, Any], thin_flow: Mapping[str, Any] | None = None, runtime_mapping: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = compile_behavior_spec(entity_behavior, thin_flow, runtime_mapping)
    return spec, check_behavior_spec_support(spec)
