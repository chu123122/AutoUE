from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

SCENE_SPAWN_MANIFEST_PATH = "flow/scene-spawn-manifest.json"
ENCOUNTER_SPEC_PATH = "flow/03-encounter-spec.json"
ENCOUNTER_SPEC_MD_PATH = "flow/03-encounter-spec.md"
STRUCTURE_PATH = "flow/02-structure.json"
SCENE_SPAWN_SCHEMA = "autoue-scene-spawn-manifest/v1"
ENCOUNTER_SPEC_SCHEMA = "autoue-encounter-spec/v1"
ALLOWED_TRIGGERS = {"on_level_start", "on_player_enter_zone"}
ALLOWED_COMPLETIONS = {"all_spawned_enemies_defeated"}
ALLOWED_POLICY_KEYS = {"avoid_camera_view", "min_distance_to_player", "consume_spawn_point", "max_alive"}
BANNED_COORDINATE_KEYS = {"location", "transform", "coordinate", "coordinates", "x", "y", "z"}


class EncounterValidationError(ValueError):
    pass


def load_json_file(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _err(label: str, msg: str) -> EncounterValidationError:
    return EncounterValidationError(f"{label}: {msg}")


def _require_dict(label: str, obj: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = obj.get(key)
    if not isinstance(value, dict):
        raise _err(label, f"{key} must be object")
    return value


def _require_list(label: str, obj: Mapping[str, Any], key: str, *, non_empty: bool = False) -> list[Any]:
    value = obj.get(key)
    if not isinstance(value, list):
        raise _err(label, f"{key} must be list")
    if non_empty and not value:
        raise _err(label, f"{key} must be non-empty")
    return value


def _require_string(label: str, obj: Mapping[str, Any], key: str, *, non_empty: bool = False) -> str:
    value = obj.get(key)
    if not isinstance(value, str):
        raise _err(label, f"{key} must be string")
    if non_empty and not value.strip():
        raise _err(label, f"{key} must be non-empty")
    return value


def _require_bool(label: str, obj: Mapping[str, Any], key: str) -> bool:
    value = obj.get(key)
    if not isinstance(value, bool):
        raise _err(label, f"{key} must be bool")
    return value


def _require_positive_int(label: str, obj: Mapping[str, Any], key: str) -> int:
    value = obj.get(key)
    if not isinstance(value, int) or value <= 0:
        raise _err(label, f"{key} must be positive integer")
    return value


def _ensure_string_list(label: str, values: list[Any], key: str) -> list[str]:
    out: list[str] = []
    for i, item in enumerate(values):
        if not isinstance(item, str):
            raise _err(label, f"{key}[{i}] must be string")
        out.append(item)
    return out


def _walk_keys(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def _reject_coordinates(label: str, data: Any) -> None:
    banned = sorted({key for key in _walk_keys(data) if key.lower() in BANNED_COORDINATE_KEYS})
    if banned:
        raise _err(label, f"coordinate/transform keys are forbidden in EncounterSpec: {banned}")


def validate_scene_spawn_manifest_data(data: Any) -> dict[str, Any]:
    label = "SceneSpawnManifest"
    if not isinstance(data, dict):
        raise _err(label, "manifest must be object")
    if data.get("schema_version") != SCENE_SPAWN_SCHEMA:
        raise _err(label, f"schema_version must be {SCENE_SPAWN_SCHEMA}")
    _require_string(label, data, "level_name", non_empty=True)
    groups = _require_list(label, data, "spawn_groups")
    zones = _require_list(label, data, "encounter_zones")
    seen_groups: set[str] = set()
    for i, group in enumerate(groups):
        glabel = f"SceneSpawnManifest.spawn_groups[{i}]"
        if not isinstance(group, dict):
            raise _err(glabel, "must be object")
        spawn_group = _require_string(glabel, group, "spawn_group", non_empty=True)
        if spawn_group in seen_groups:
            raise _err(glabel, f"duplicate spawn_group: {spawn_group}")
        seen_groups.add(spawn_group)
        point_count = group.get("point_count")
        area_count = group.get("area_count")
        if not isinstance(point_count, int) or point_count < 0:
            raise _err(glabel, "point_count must be non-negative integer")
        if not isinstance(area_count, int) or area_count < 0:
            raise _err(glabel, "area_count must be non-negative integer")
        if point_count + area_count <= 0:
            raise _err(glabel, "must contain at least one point or area")
        _ensure_string_list(glabel, _require_list(glabel, group, "allowed_enemy_tags"), "allowed_enemy_tags")
        _ensure_string_list(glabel, _require_list(glabel, group, "source_types"), "source_types")
        _require_bool(glabel, group, "can_initial_spawn")
        _require_bool(glabel, group, "can_runtime_spawn")
    seen_zones: set[str] = set()
    for i, zone in enumerate(zones):
        zlabel = f"SceneSpawnManifest.encounter_zones[{i}]"
        if not isinstance(zone, dict):
            raise _err(zlabel, "must be object")
        zone_id = _require_string(zlabel, zone, "zone_id", non_empty=True)
        if zone_id in seen_zones:
            raise _err(zlabel, f"duplicate zone_id: {zone_id}")
        seen_zones.add(zone_id)
        trigger = _require_string(zlabel, zone, "trigger", non_empty=True)
        if trigger not in ALLOWED_TRIGGERS:
            raise _err(zlabel, f"invalid trigger: {trigger}")
        spawn_group = _require_string(zlabel, zone, "spawn_group", non_empty=True)
        if spawn_group not in seen_groups:
            raise _err(zlabel, f"spawn_group does not exist: {spawn_group}")
        _require_bool(zlabel, zone, "one_shot")
    return data


def collect_spawnable_enemy_entities(structure: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not structure:
        return {}
    enemies: dict[str, dict[str, Any]] = {}
    for entity in structure.get("entities", []):
        if not isinstance(entity, dict):
            continue
        entity_id = entity.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id:
            continue
        if entity.get("entity_kind") == "enemy" and entity.get("spawnable") is True:
            enemies[entity_id] = entity
    return enemies


def validate_spawnable_enemy_entity(entity: Mapping[str, Any], *, label: str = "EntityAbilityBehaviorPlanner") -> None:
    entity_id = entity.get("entity_id", "<unknown>")
    if entity.get("entity_kind") != "enemy":
        raise _err(label, f"spawnable entity must use entity_kind=enemy: {entity_id}")
    if entity.get("spawnable") is not True:
        raise _err(label, f"spawnable enemy must set spawnable=true: {entity_id}")
    tags = entity.get("content_tags")
    if not isinstance(tags, list) or not tags or any(not isinstance(x, str) for x in tags):
        raise _err(label, f"spawnable enemy must define non-empty content_tags: {entity_id}")
    profile = entity.get("enemy_profile")
    if not isinstance(profile, dict):
        raise _err(label, f"spawnable enemy must define enemy_profile: {entity_id}")
    _require_positive_int(label, profile, "cost")
    _require_positive_int(label, profile, "default_health")
    allowed = profile.get("allowed_spawn_tags")
    if not isinstance(allowed, list) or not allowed or any(not isinstance(x, str) for x in allowed):
        raise _err(label, f"enemy_profile.allowed_spawn_tags must be non-empty string list: {entity_id}")


def validate_encounter_spec_data(data: Any, *, structure: Mapping[str, Any] | None = None, manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    label = "EncounterSpec"
    if not isinstance(data, dict):
        raise _err(label, "spec must be object")
    if data.get("schema_version") != ENCOUNTER_SPEC_SCHEMA:
        raise _err(label, f"schema_version must be {ENCOUNTER_SPEC_SCHEMA}")
    _reject_coordinates(label, data)
    encounters = _require_list(label, data, "encounters")
    groups = {g.get("spawn_group"): g for g in (manifest or {}).get("spawn_groups", []) if isinstance(g, dict)}
    enemies = collect_spawnable_enemy_entities(structure)
    seen: set[str] = set()
    for i, encounter in enumerate(encounters):
        elabel = f"EncounterSpec.encounters[{i}]"
        if not isinstance(encounter, dict):
            raise _err(elabel, "must be object")
        encounter_id = _require_string(elabel, encounter, "encounter_id", non_empty=True)
        if encounter_id in seen:
            raise _err(elabel, f"duplicate encounter_id: {encounter_id}")
        seen.add(encounter_id)
        trigger = _require_dict(elabel, encounter, "trigger")
        trigger_type = _require_string(elabel, trigger, "type", non_empty=True)
        if trigger_type not in ALLOWED_TRIGGERS:
            raise _err(elabel, f"invalid trigger.type: {trigger_type}")
        spawn_group = _require_string(elabel, encounter, "spawn_group", non_empty=True)
        if groups and spawn_group not in groups:
            raise _err(elabel, f"spawn_group not found in scene-spawn-manifest: {spawn_group}")
        budget = _require_positive_int(elabel, encounter, "enemy_budget")
        policy = _require_dict(elabel, encounter, "spawn_policy")
        bad_policy = sorted(set(policy) - ALLOWED_POLICY_KEYS)
        if bad_policy:
            raise _err(elabel, f"unsupported spawn_policy keys: {bad_policy}")
        if "avoid_camera_view" in policy and not isinstance(policy["avoid_camera_view"], bool):
            raise _err(elabel, "spawn_policy.avoid_camera_view must be bool")
        if "consume_spawn_point" in policy and not isinstance(policy["consume_spawn_point"], bool):
            raise _err(elabel, "spawn_policy.consume_spawn_point must be bool")
        for key in ("min_distance_to_player", "max_alive"):
            if key in policy and (not isinstance(policy[key], int) or policy[key] < 0):
                raise _err(elabel, f"spawn_policy.{key} must be non-negative integer")
        completion = _require_dict(elabel, encounter, "completion")
        completion_type = _require_string(elabel, completion, "type", non_empty=True)
        if completion_type not in ALLOWED_COMPLETIONS:
            raise _err(elabel, f"invalid completion.type: {completion_type}")
        if "set_flags" in completion:
            _ensure_string_list(elabel, _require_list(elabel, completion, "set_flags"), "completion.set_flags")
        _ensure_string_list(elabel, _require_list(elabel, encounter, "verification_hooks", non_empty=True), "verification_hooks")
        total_cost = 0
        composition = _require_list(elabel, encounter, "composition", non_empty=True)
        allowed_group_tags = set(groups.get(spawn_group, {}).get("allowed_enemy_tags", [])) if groups else set()
        for ci, item in enumerate(composition):
            clabel = f"{elabel}.composition[{ci}]"
            if not isinstance(item, dict):
                raise _err(clabel, "must be object")
            enemy_id = _require_string(clabel, item, "enemy", non_empty=True)
            count = _require_positive_int(clabel, item, "count")
            if enemies and enemy_id not in enemies:
                raise _err(clabel, f"enemy is not a spawnable enemy entity: {enemy_id}")
            if enemy_id in enemies:
                enemy = enemies[enemy_id]
                validate_spawnable_enemy_entity(enemy, label=clabel)
                profile = enemy["enemy_profile"]
                total_cost += int(profile["cost"]) * count
                enemy_tags = set(enemy.get("content_tags", [])) | set(profile.get("allowed_spawn_tags", []))
                if allowed_group_tags and not (enemy_tags & allowed_group_tags):
                    raise _err(clabel, f"enemy tags do not match spawn_group allowed_enemy_tags: {enemy_id}")
        if enemies and total_cost > budget:
            raise _err(elabel, f"composition cost {total_cost} exceeds enemy_budget {budget}")
    return data


def render_encounter_spec_markdown(spec: Mapping[str, Any]) -> str:
    lines = ["# EncounterSpec", ""]
    for encounter in spec.get("encounters", []):
        lines.append(f"## {encounter.get('encounter_id', '<unnamed>')}")
        lines.append("")
        lines.append(f"- trigger: {encounter.get('trigger', {}).get('type', '')}")
        lines.append(f"- spawn_group: {encounter.get('spawn_group', '')}")
        lines.append(f"- enemy_budget: {encounter.get('enemy_budget', '')}")
        lines.append("- composition:")
        for item in encounter.get("composition", []):
            lines.append(f"  - {item.get('enemy', '')} x {item.get('count', '')}")
        lines.append(f"- completion: {encounter.get('completion', {}).get('type', '')}")
        hooks = ", ".join(encounter.get("verification_hooks", []))
        lines.append(f"- verification_hooks: {hooks}")
        lines.append("")
    if not spec.get("encounters"):
        lines.append("No encounters planned.")
        lines.append("")
    return "\n".join(lines)
