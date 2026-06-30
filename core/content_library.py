from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Mapping

from core.config import repo_path

LIBRARY_ROOT = repo_path("data/libraries/dead_cells")
MIN_COUNTS = {"entities": 50, "capabilities": 30, "behaviors": 10}
CORE_ENTITY_IDS = {"player", "zombie", "archer", "shield_bearer", "kamikaze_bat", "room_encounter", "health_bar_hud", "combat_damage_number_hud", "level_exit_door", "freeze_trap", "freeze_vfx", "side_camera", "gold_pickup"}
CORE_BEHAVIOR_IDS = {"enemy.behavior.chase_and_melee", "hud.behavior.refresh_value", "exit.behavior.unlock_and_transition"}
QUERY_SYNONYMS = {
    "玩家": ["player"], "僵尸": ["zombie", "enemy", "melee"], "弓箭": ["archer", "ranged", "projectile"], "射手": ["archer", "ranged"],
    "持盾": ["shield_bearer", "shield", "block"], "盾": ["shield", "block"], "自爆": ["kamikaze", "explosive", "self_destruct"], "蝙蝠": ["bat", "kamikaze"],
    "敌人": ["enemy"], "追击": ["chase"], "远程": ["ranged", "projectile"], "近战": ["melee"], "房间": ["room", "encounter"],
    "冰冻": ["freeze", "frozen"], "冰": ["freeze"], "陷阱": ["trap", "hazard"], "特效": ["vfx", "particle"], "粒子": ["vfx", "particle"],
    "镜头": ["camera"], "相机": ["camera"], "HUD": ["hud"], "界面": ["hud"], "血条": ["health_bar_hud", "health"], "伤害数字": ["combat_damage_number_hud", "damage"],
    "出口": ["exit", "door"], "门": ["door"], "拾取": ["pickup"], "金币": ["gold", "pickup"], "奖励": ["reward"], "全部": ["all"], "完整": ["all"], "全量": ["all"],
}
LEGACY_ID_RE = re.compile(r"(^|\.)(offense|pursuit)(\.|$)|selected_ability_ids|candidate_ability_ids")


def _validation_error(message: str):
    from core.validation.common import WorkflowValidationError
    return WorkflowValidationError(message)


def _read_json(name: str, key: str) -> list[dict[str, Any]]:
    data = json.loads((LIBRARY_ROOT / name).read_text(encoding="utf-8"))
    items = data.get(key)
    if not isinstance(items, list):
        raise RuntimeError(f"{name}: expected list at {key}")
    return items


@lru_cache(maxsize=1)
def load_dead_cells_library() -> dict[str, Any]:
    entities = _read_json("entities.json", "entities")
    capabilities = _read_json("abilities.json", "abilities")
    behaviors = _read_json("behaviors.json", "behaviors")
    library = {
        "entities": {item["entity_id"]: item for item in entities},
        "capabilities": {item["capability_id"]: item for item in capabilities},
        "abilities": {item["capability_id"]: item for item in capabilities},  # compatibility alias: entries are capabilities.
        "behaviors": {item["behavior_id"]: item for item in behaviors},
        "capability_bindings_by_entity": {},
        "behaviors_by_capability": {},
    }
    for entity in entities:
        library["capability_bindings_by_entity"][entity["entity_id"]] = {b.get("capability_id"): b for b in entity.get("capability_bindings", []) if isinstance(b, dict)}
    for behavior in behaviors:
        for capability_id in behavior.get("required_capability_ids", []) or []:
            library["behaviors_by_capability"].setdefault(capability_id, []).append(behavior["behavior_id"])
    for key, minimum in MIN_COUNTS.items():
        if len(library[key]) < minimum:
            raise RuntimeError(f"dead cells {key} library count below minimum: expected >= {minimum}, got {len(library[key])}")
    validate_library_self_consistency(library)
    return library


def _audio_marker(value: Any) -> bool:
    return any(marker in json.dumps(value, ensure_ascii=False).lower() for marker in ["audio", "sound", "sfx", "音效", "声音", "bgm"])


def _check_params(label: str, schema: Mapping[str, Any], params: Mapping[str, Any], defaults: Mapping[str, Any] | None = None) -> None:
    unknown = sorted(set((params or {}).keys()) - set(schema.keys()) - set((defaults or {}).keys()))
    if unknown:
        raise RuntimeError(f"{label} has params not declared by params_schema/default_params: {unknown}")
    merged = dict(defaults or {})
    merged.update(dict(params or {}))
    for key, rule in schema.items():
        if not isinstance(rule, Mapping):
            continue
        if rule.get("required") and key not in merged:
            raise RuntimeError(f"{label} missing required param {key}")
        if key not in merged:
            continue
        typ = rule.get("type")
        val = merged[key]
        ok = (typ == "number" and isinstance(val, (int, float)) and not isinstance(val, bool)) or (typ == "string" and isinstance(val, str) and bool(val)) or (typ == "bool" and isinstance(val, bool)) or typ not in {"number", "string", "bool"}
        if not ok:
            raise RuntimeError(f"{label} param {key} has wrong type {typ}: {val!r}")
        if typ == "number" and "min" in rule and val < rule["min"]:
            raise RuntimeError(f"{label} param {key} below min {rule['min']}: {val!r}")


def validate_library_self_consistency(library: dict[str, Any] | None = None) -> None:
    lib = library or load_dead_cells_library()
    if len(lib["entities"]) != len(set(lib["entities"])) or len(lib["capabilities"]) != len(set(lib["capabilities"])) or len(lib["behaviors"]) != len(set(lib["behaviors"])):
        raise RuntimeError("dead cells library contains duplicate IDs")
    for entity_id, entity in lib["entities"].items():
        if _audio_marker(entity):
            raise RuntimeError(f"audio/SFX entity is forbidden in dead cells library: {entity_id}")
        if "status" in entity_id and entity_id != "status_icon_hud":
            raise RuntimeError(f"runtime status/state must not be gameplay entity: {entity_id}")
        bindings = entity.get("capability_bindings", [])
        if bindings is not None and not isinstance(bindings, list):
            raise RuntimeError(f"entity capability_bindings must be list: {entity_id}")
        for binding in bindings or []:
            cid = binding.get("capability_id") if isinstance(binding, dict) else None
            if cid not in lib["capabilities"]:
                raise RuntimeError(f"entity {entity_id} binding references unknown capability: {cid}")
            cap = lib["capabilities"][cid]
            _check_params(f"entity {entity_id} binding {cid}", cap.get("params_schema", {}), binding.get("params", {}), cap.get("default_params", {}))
        if entity.get("spawnable") is True:
            if entity.get("runtime_profile") != "enemy_runtime":
                raise RuntimeError(f"spawnable enemy must declare runtime_profile=enemy_runtime: {entity_id}")
            required = {"enemy.spawn.spawn_actor", "enemy.health.receive_damage", "enemy.death.emit_death_event"}
            present = {b.get("capability_id") for b in bindings or [] if isinstance(b, dict)}
            missing = sorted(required - present)
            if missing:
                raise RuntimeError(f"spawnable enemy lacks capability bindings {missing}: {entity_id}")
    seen_kind_action: dict[tuple[str, str], str] = {}
    for cid, cap in lib["capabilities"].items():
        if _audio_marker(cap):
            raise RuntimeError(f"audio/SFX capability is forbidden in dead cells library: {cid}")
        if LEGACY_ID_RE.search(cid):
            raise RuntimeError(f"legacy entity-specific capability ID is forbidden: {cid}")
        for key in ("semantic_role", "capability_kind", "action_kind", "runtime_features", "params_schema"):
            if key not in cap or cap[key] in (None, "", []):
                raise RuntimeError(f"capability lacks {key}: {cid}")
        if cap["semantic_role"] != "capability":
            raise RuntimeError(f"capability semantic_role must be capability: {cid}")
        if any(feature in {"status", "interaction"} for feature in cap.get("runtime_features", [])):
            raise RuntimeError(f"capability uses forbidden runtime feature: {cid}")
        pair = (str(cap.get("capability_kind")), str(cap.get("action_kind")))
        if pair in seen_kind_action and cap.get("runtime_handler") == lib["capabilities"][seen_kind_action[pair]].get("runtime_handler"):
            raise RuntimeError(f"duplicate canonical capability for {pair}: {seen_kind_action[pair]} and {cid}")
        seen_kind_action[pair] = cid
    for behavior_id, behavior in lib["behaviors"].items():
        if _audio_marker(behavior):
            raise RuntimeError(f"audio/SFX behavior is forbidden in dead cells library: {behavior_id}")
        if LEGACY_ID_RE.search(behavior_id):
            raise RuntimeError(f"legacy entity-specific behavior ID is forbidden: {behavior_id}")
        if "ability_id" in behavior:
            raise RuntimeError(f"behavior must not use legacy ability_id: {behavior_id}")
        required = behavior.get("required_capability_ids")
        if not isinstance(required, list) or not required:
            raise RuntimeError(f"behavior lacks required_capability_ids: {behavior_id}")
        for cid in required:
            if cid not in lib["capabilities"]:
                raise RuntimeError(f"behavior {behavior_id} references unknown capability {cid}")
            if LEGACY_ID_RE.search(str(cid)):
                raise RuntimeError(f"behavior {behavior_id} references legacy capability {cid}")
        if any(feature in {"status", "interaction"} for feature in behavior.get("runtime_features", [])):
            raise RuntimeError(f"behavior uses forbidden runtime feature: {behavior_id}")


def _tokens(text: str) -> set[str]:
    lower = text.lower()
    pieces = set(re.findall(r"[a-z0-9_]+", lower))
    for zh, expanded in QUERY_SYNONYMS.items():
        if zh.lower() in lower or zh in text:
            pieces.update(x.lower() for x in expanded)
    for token in list(pieces):
        pieces.update(part for part in token.split("_") if part)
    return {p for p in pieces if len(p) > 1}


def _entry_text(item: dict[str, Any]) -> str:
    return json.dumps(item, ensure_ascii=False).lower()


def _score(item: dict[str, Any], terms: set[str], id_key: str) -> int:
    haystack = _entry_text(item)
    identifier = str(item.get(id_key) or "").lower()
    return sum((10 if term in identifier else 0) + (3 if term in haystack else 0) for term in terms)


def _top_ids(items: dict[str, dict[str, Any]], id_key: str, terms: set[str], limit: int | None) -> list[str]:
    scored = sorted(((_score(item, terms, id_key), item[id_key]) for item in items.values()), key=lambda x: (-x[0], x[1]))
    positives = [item_id for score, item_id in scored if score > 0]
    chosen = positives if positives else [item_id for _score, item_id in scored]
    return chosen if limit is None else chosen[:limit]


def _explicit_ids(query: str, items: dict[str, dict[str, Any]], id_key: str) -> set[str]:
    lower = query.lower()
    out: set[str] = set()
    for item_id, item in items.items():
        names = [str(item.get(k) or "") for k in (id_key, "display_name", "display_name_zh", "summary", "summary_zh")]
        if any(name and (name.lower() in lower if name.isascii() else name in query) for name in names):
            out.add(item[id_key])
    return out


def _entity_can_satisfy(entity: Mapping[str, Any], behavior: Mapping[str, Any]) -> bool:
    required = set(behavior.get("required_capability_ids", []))
    bound = {b.get("capability_id") for b in entity.get("capability_bindings", []) if isinstance(b, Mapping)}
    return required.issubset(bound)


def _binding_summary(entity: Mapping[str, Any]) -> dict[str, Any]:
    return {"entity_id": entity.get("entity_id"), "entity_kind": entity.get("entity_kind"), "capability_ids": [b.get("capability_id") for b in entity.get("capability_bindings", []) if isinstance(b, Mapping)], "tags": entity.get("content_tags", [])}


def _close_candidate_set(entity_ids: set[str], capability_ids: set[str], behavior_ids: set[str]) -> tuple[set[str], set[str], set[str]]:
    lib = load_dead_cells_library()
    for behavior_id in list(behavior_ids):
        behavior = lib["behaviors"].get(behavior_id)
        if behavior:
            capability_ids.update(behavior.get("required_capability_ids", []))
    for entity_id in list(entity_ids):
        entity = lib["entities"].get(entity_id)
        if entity:
            capability_ids.update(b.get("capability_id") for b in entity.get("capability_bindings", []) if isinstance(b, Mapping))
            for behavior_id, behavior in lib["behaviors"].items():
                if _entity_can_satisfy(entity, behavior):
                    behavior_ids.add(behavior_id)
                    capability_ids.update(behavior.get("required_capability_ids", []))
    return entity_ids, {cid for cid in capability_ids if cid in lib["capabilities"]}, behavior_ids


def build_candidate_set(query: str, *, entity_limit: int = 60, capability_limit: int = 80, behavior_limit: int = 60) -> dict[str, Any]:
    lib = load_dead_cells_library()
    terms = _tokens(query)
    broad = "all" in terms
    entity_ids = set(_top_ids(lib["entities"], "entity_id", terms, None if broad else entity_limit))
    capability_ids = set(_top_ids(lib["capabilities"], "capability_id", terms, None if broad else capability_limit))
    behavior_ids = set(_top_ids(lib["behaviors"], "behavior_id", terms, None if broad else behavior_limit))
    entity_ids.update(_explicit_ids(query, lib["entities"], "entity_id"))
    capability_ids.update(_explicit_ids(query, lib["capabilities"], "capability_id"))
    behavior_ids.update(_explicit_ids(query, lib["behaviors"], "behavior_id"))
    entity_ids.update(CORE_ENTITY_IDS)
    behavior_ids.update(CORE_BEHAVIOR_IDS)
    entity_ids, capability_ids, behavior_ids = _close_candidate_set(entity_ids, capability_ids, behavior_ids)
    entities = [lib["entities"][i] for i in sorted(entity_ids) if i in lib["entities"]]
    capabilities = [lib["capabilities"][i] for i in sorted(capability_ids) if i in lib["capabilities"]]
    behaviors = [lib["behaviors"][i] for i in sorted(behavior_ids) if i in lib["behaviors"]]
    return {
        "schema_version": "autoue-dead-cells-candidate-set/v4",
        "query": query,
        "selection_rule": "Select only listed canonical IDs. Output selected_entity_ids, selected_capability_ids, selected_behavior_ids. Legacy selected_ability_ids is invalid.",
        "candidate_entity_ids": [e["entity_id"] for e in entities],
        "candidate_capability_ids": [c["capability_id"] for c in capabilities],
        "candidate_behavior_ids": [b["behavior_id"] for b in behaviors],
        "candidate_entities": entities,
        "candidate_capability_prototypes": capabilities,
        "candidate_behaviors": behaviors,
        "entity_capability_bindings_summary": [_binding_summary(e) for e in entities],
        "entities": entities,
        "capabilities": capabilities,
        "behaviors": behaviors,
    }


def parse_selection_output(node: str, data: Any) -> dict[str, list[str]]:
    if not isinstance(data, dict):
        raise _validation_error(f"{node}: selection output must be a JSON object")
    if "selected_ability_ids" in data:
        raise _validation_error(f"{node}: selected_ability_ids is legacy and forbidden; use selected_capability_ids")
    result: dict[str, list[str]] = {}
    for key in ("selected_entity_ids", "selected_capability_ids", "selected_behavior_ids"):
        values = data.get(key, [])
        if not isinstance(values, list):
            raise _validation_error(f"{node}: {key} must be a list")
        cleaned: list[str] = []
        for item in values:
            if not isinstance(item, str) or not item.strip():
                raise _validation_error(f"{node}: {key} must contain non-empty strings")
            if LEGACY_ID_RE.search(item):
                raise _validation_error(f"{node}: legacy ID is forbidden: {item}")
            if item not in cleaned:
                cleaned.append(item)
        result[key] = cleaned
    if not result["selected_behavior_ids"] and not result["selected_capability_ids"]:
        raise _validation_error(f"{node}: select at least one behavior_id or capability_id")
    return result


def validate_selection_against_library_and_candidates(node: str, selection: dict[str, list[str]], candidate_set: dict[str, Any]) -> None:
    lib = load_dead_cells_library()
    candidate_entities = set(candidate_set.get("candidate_entity_ids", []))
    candidate_capabilities = set(candidate_set.get("candidate_capability_ids", []))
    candidate_behaviors = set(candidate_set.get("candidate_behavior_ids", []))
    for entity_id in selection.get("selected_entity_ids", []):
        if entity_id not in lib["entities"]:
            raise _validation_error(f"{node}: selected entity_id is not in library: {entity_id}")
        if entity_id not in candidate_entities:
            raise _validation_error(f"{node}: selected entity_id is not in this candidate set: {entity_id}")
    selected_caps = set(selection.get("selected_capability_ids", []))
    for capability_id in selected_caps:
        if capability_id not in lib["capabilities"]:
            raise _validation_error(f"{node}: selected capability_id is not in library: {capability_id}")
        if capability_id not in candidate_capabilities:
            raise _validation_error(f"{node}: selected capability_id is not in this candidate set: {capability_id}")
    for behavior_id in selection.get("selected_behavior_ids", []):
        behavior = lib["behaviors"].get(behavior_id)
        if not behavior:
            raise _validation_error(f"{node}: selected behavior_id is not in library: {behavior_id}")
        if behavior_id not in candidate_behaviors:
            raise _validation_error(f"{node}: selected behavior_id is not in this candidate set: {behavior_id}")
        missing = set(behavior.get("required_capability_ids", [])) - selected_caps
        if missing:
            raise _validation_error(f"{node}: selected_capability_ids do not cover behavior {behavior_id}: {sorted(missing)}")


def canonicalize_selection(selection: dict[str, list[str]]) -> dict[str, Any]:
    lib = load_dead_cells_library()
    entity_ids = set(selection.get("selected_entity_ids", []))
    capability_ids = set(selection.get("selected_capability_ids", []))
    behavior_ids = set(selection.get("selected_behavior_ids", []))
    for behavior_id in list(behavior_ids):
        behavior = lib["behaviors"][behavior_id]
        capability_ids.update(behavior.get("required_capability_ids", []))
    # Do not expand a generic behavior to every entity that can satisfy it.
    # The LLM-selected entity IDs decide the bound entities; selected capabilities
    # and behaviors only decide which canonical prototypes attach to those entities.
    entities: list[dict[str, Any]] = []
    for entity_id in sorted(e for e in entity_ids if e in lib["entities"]):
        source_entity = dict(lib["entities"][entity_id])
        bound_ids = {b.get("capability_id") for b in source_entity.get("capability_bindings", []) if isinstance(b, Mapping)}
        caps = []
        for capability_id in sorted(capability_ids & bound_ids):
            cap = dict(lib["capabilities"][capability_id])
            cap["behaviors"] = [
                dict(lib["behaviors"][bid])
                for bid in sorted(behavior_ids)
                if capability_id in lib["behaviors"][bid].get("required_capability_ids", []) and _entity_can_satisfy(source_entity, lib["behaviors"][bid])
            ]
            if cap["behaviors"]:
                caps.append(cap)
        source_entity["capabilities"] = caps
        entities.append(source_entity)
    return {"schema_version": "autoue-eab-canonical/v2", "entities": entities, "non_goals": []}


def validate_entity_ability_behavior_against_library(node: str, data: dict[str, Any]) -> None:
    lib = load_dead_cells_library()
    for entity in data.get("entities", []):
        if not isinstance(entity, dict):
            continue
        entity_id = entity.get("entity_id", "")
        if entity_id not in lib["entities"]:
            raise _validation_error(f"{node}: entity_id is not in dead_cells entity library: {entity_id}")
        for capability in entity.get("capabilities", []) or []:
            capability_id = capability.get("capability_id", "")
            if capability_id not in lib["capabilities"]:
                raise _validation_error(f"{node}: capability_id is not in dead_cells capability library: {capability_id}")
            bound_ids = {b.get("capability_id") for b in lib["entities"][entity_id].get("capability_bindings", []) if isinstance(b, Mapping)}
            if capability_id not in bound_ids:
                raise _validation_error(f"{node}: capability_id {capability_id} is not bound by entity {entity_id}")
            for behavior in capability.get("behaviors", []) or []:
                behavior_id = behavior.get("behavior_id", "")
                known = lib["behaviors"].get(behavior_id)
                if not known:
                    raise _validation_error(f"{node}: behavior_id is not in dead_cells behavior library: {behavior_id}")
                if capability_id not in known.get("required_capability_ids", []):
                    raise _validation_error(f"{node}: behavior_id {behavior_id} does not require capability {capability_id}")


def render_candidate_set_prompt(candidate_set: dict[str, Any]) -> str:
    compact = {
        "library_contract": "Only select listed canonical IDs. Do not output legacy ability IDs or object text.",
        "selected_output_shape": {"selected_entity_ids": [], "selected_capability_ids": [], "selected_behavior_ids": []},
        "entities": [{"entity_id": e["entity_id"], "name": e.get("display_name_zh") or e.get("display_name"), "kind": e.get("entity_kind"), "tags": e.get("content_tags", [])} for e in candidate_set.get("candidate_entities", [])],
        "capability_prototypes": [{"capability_id": c["capability_id"], "kind": c.get("capability_kind"), "action_kind": c.get("action_kind"), "runtime_features": c.get("runtime_features", []), "name": c.get("display_name_zh") or c.get("display_name")} for c in candidate_set.get("candidate_capability_prototypes", [])],
        "behaviors": [{"behavior_id": b["behavior_id"], "required_capability_ids": b.get("required_capability_ids", []), "runtime_features": b.get("runtime_features", []), "name": b.get("display_name_zh") or b.get("display_name")} for b in candidate_set.get("candidate_behaviors", [])],
        "entity_capability_bindings_summary": candidate_set.get("entity_capability_bindings_summary", []),
    }
    return json.dumps(compact, ensure_ascii=False, indent=2)
