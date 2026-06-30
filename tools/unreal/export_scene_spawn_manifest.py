from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.encounter_validation import SCENE_SPAWN_SCHEMA, validate_scene_spawn_manifest_data


def _prop(actor: Any, names: list[str], default: Any = None) -> Any:
    for name in names:
        try:
            return actor.get_editor_property(name)
        except Exception:
            pass
        try:
            return getattr(actor, name)
        except Exception:
            pass
    return default


def _class_name(actor: Any) -> str:
    try:
        return actor.get_class().get_name()
    except Exception:
        return type(actor).__name__


def _tags(actor: Any) -> set[str]:
    out: set[str] = set()
    for source in (_prop(actor, ["Tags", "tags"], []) or [], _prop(actor, ["ActorTags", "actor_tags"], []) or []):
        try:
            out.update(str(x) for x in source)
        except Exception:
            pass
    return out


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    try:
        return [str(x) for x in value if str(x)]
    except Exception:
        return []


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return bool(value)


def _as_number(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _is_kind(actor: Any, kind: str) -> bool:
    cls = _class_name(actor).lower()
    tags = {t.lower() for t in _tags(actor)}
    return kind.lower() in cls or kind.lower() in tags


def _tag_value(actor: Any, prefixes: list[str]) -> str:
    for tag in _tags(actor):
        raw = str(tag)
        for prefix in prefixes:
            if raw.startswith(prefix):
                return raw[len(prefix):].strip()
    return ""


def _spawn_group(actor: Any) -> str:
    return str(_prop(actor, ["SpawnGroup", "spawn_group", "spawnGroup"], "") or "") or _tag_value(actor, ["SpawnGroup=", "SpawnGroup:", "spawn_group="])


def _spawn_bool(actor: Any, names: list[str], tags: list[str], default: bool = False) -> bool:
    value = _prop(actor, names, None)
    if value is not None:
        return _as_bool(value, default)
    lower_tags = {t.lower() for t in _tags(actor)}
    return any(tag.lower() in lower_tags for tag in tags) or default


def _allowed_enemy_tags(actor: Any) -> list[str]:
    values = _as_str_list(_prop(actor, ["AllowedEnemyTags", "allowed_enemy_tags"], []))
    values.extend(_tag_value(actor, ["AllowedEnemyTags=", "AllowedEnemyTags:", "allowed_enemy_tags="]).replace(",", ";").split(";"))
    return [v.strip() for v in values if v and v.strip()]


def _load_map(map_name: str | None) -> str:
    import unreal  # type: ignore
    if map_name:
        unreal.EditorLoadingAndSavingUtils.load_map(map_name)
        return map_name
    world = unreal.EditorLevelLibrary.get_editor_world()
    try:
        return world.get_name()
    except Exception:
        return "<current>"


def export_manifest(map_name: str | None) -> dict[str, Any]:
    import unreal  # type: ignore
    level_name = _load_map(map_name)
    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    groups: dict[str, dict[str, Any]] = {}
    zones: list[dict[str, Any]] = []

    for actor in actors:
        if _is_kind(actor, "EnemySpawnPoint") or _is_kind(actor, "BP_EnemySpawnPoint"):
            group = _spawn_group(actor)
            if not group:
                continue
            item = groups.setdefault(group, {
                "spawn_group": group,
                "source_types": set(),
                "point_count": 0,
                "area_count": 0,
                "allowed_enemy_tags": set(),
                "can_initial_spawn": False,
                "can_runtime_spawn": False,
            })
            item["source_types"].add("EnemySpawnPoint")
            item["point_count"] += 1
            item["allowed_enemy_tags"].update(_allowed_enemy_tags(actor))
            item["can_initial_spawn"] = item["can_initial_spawn"] or _spawn_bool(actor, ["CanInitialSpawn", "can_initial_spawn"], ["CanInitialSpawn", "AUTOUE_CAN_INITIAL_SPAWN"], False)
            item["can_runtime_spawn"] = item["can_runtime_spawn"] or _spawn_bool(actor, ["CanRuntimeSpawn", "can_runtime_spawn"], ["CanRuntimeSpawn", "AUTOUE_CAN_RUNTIME_SPAWN"], False)
        elif _is_kind(actor, "EnemySpawnArea") or _is_kind(actor, "BP_EnemySpawnArea"):
            group = _spawn_group(actor)
            if not group:
                continue
            item = groups.setdefault(group, {
                "spawn_group": group,
                "source_types": set(),
                "point_count": 0,
                "area_count": 0,
                "allowed_enemy_tags": set(),
                "can_initial_spawn": False,
                "can_runtime_spawn": False,
            })
            item["source_types"].add("EnemySpawnArea")
            item["area_count"] += max(1, _as_number(_prop(actor, ["MaxSpawnCount", "max_spawn_count"], 1), 1))
            item["allowed_enemy_tags"].update(_allowed_enemy_tags(actor))
            item["can_initial_spawn"] = True
            item["can_runtime_spawn"] = True
        elif _is_kind(actor, "EncounterZone") or _is_kind(actor, "BP_EncounterZone"):
            group = _spawn_group(actor)
            zone_id = str(_prop(actor, ["ZoneId", "zone_id", "ZoneID"], "") or "")
            trigger = str(_prop(actor, ["TriggerType", "trigger", "Trigger"], "on_player_enter_zone") or "on_player_enter_zone")
            if zone_id and group:
                zones.append({
                    "zone_id": zone_id,
                    "trigger": trigger,
                    "spawn_group": group,
                    "one_shot": _as_bool(_prop(actor, ["OneShot", "one_shot"], True), True),
                })

    manifest = {
        "schema_version": SCENE_SPAWN_SCHEMA,
        "level_name": level_name,
        "spawn_groups": [
            {
                **{k: v for k, v in item.items() if k not in {"source_types", "allowed_enemy_tags"}},
                "source_types": sorted(item["source_types"]),
                "allowed_enemy_tags": sorted(item["allowed_enemy_tags"]),
            }
            for item in sorted(groups.values(), key=lambda x: x["spawn_group"])
        ],
        "encounter_zones": sorted(zones, key=lambda x: x["zone_id"]),
    }
    validate_scene_spawn_manifest_data(manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", dest="map_name")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    out_arg = args.out or os.getenv("AUTOUE_SPAWN_MANIFEST_OUT") or os.getenv("AUTOUE_EXPORT_OUT")
    if not out_arg:
        parser.error("--out is required unless AUTOUE_SPAWN_MANIFEST_OUT or AUTOUE_EXPORT_OUT is set")
    out = Path(out_arg).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = export_manifest(args.map_name or os.getenv("AUTOUE_EXPORT_MAP") or os.getenv("AUTOUE_ENCOUNTER_MAP"))
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[SUCCESS] scene spawn manifest exported to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
