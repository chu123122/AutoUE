from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Iterable

from core.config import repo_path

LIBRARY_ROOT = repo_path("data/libraries/dead_cells")
MIN_COUNTS = {"entities": 50, "abilities": 100, "behaviors": 200}


def _validation_error(message: str):
    from core.validation.common import WorkflowValidationError
    return WorkflowValidationError(message)
CORE_ENTITY_IDS = {
    "player",
    "health_bar_hud",
    "status_icon_hud",
    "combat_damage_number_hud",
    "level_exit_door",
    "teleport_vfx",
    "bleed_vfx",
    "poison_vfx",
    "burn_vfx",
    "freeze_vfx",
    "gold_pickup",
    "cell_pickup",
    "zombie",
    "archer",
    "goblin_melee",
}
CORE_BEHAVIOR_IDS = {
    "player.combat.attack",
    "player.movement.run",
    "player.movement.dodge_roll",
    "level_exit_door.lock.evaluate_unlock",
    "level_exit_door.transition.accept_entry",
    "health_bar_hud.display.refresh_value",
    "combat_damage_number_hud.display.refresh_value",
    "status_icon_hud.display.refresh_value",
}
QUERY_SYNONYMS = {
    "玩家": ["player", "prisoner"], "囚徒": ["player", "prisoner"],
    "僵尸": ["zombie"], "哥布林": ["goblin", "goblin_melee"], "弓箭": ["archer", "bow", "ranged"], "射手": ["archer", "ranged"],
    "盾": ["shield", "shield_bearer", "parry"], "招架": ["parry", "shield"], "炸弹": ["grenadier", "explosive", "grenade"], "爆炸": ["explosive", "grenade"],
    "飞行": ["flying", "bat", "buzzcutter"], "蝙蝠": ["bat", "kamikaze"], "精英": ["elite", "slasher", "royal_guard"],
    "boss": ["boss", "concierge", "time_keeper", "giant"], "看守者": ["concierge"], "时守": ["time_keeper"], "国王之手": ["hand_of_the_king"],
    "宝箱": ["chest", "treasure_chest"], "诅咒": ["curse", "cursed", "cursed_chest", "curse_count"], "商店": ["shop", "vendor", "transaction"], "铸造": ["forge", "upgrade"],
    "毒": ["poison", "poison_pool", "poison_dot"], "火": ["fire", "burn", "flame"], "燃烧": ["burn", "fire"], "冰": ["freeze", "ice"], "冰冻": ["freeze", "ice"],
    "电": ["electric", "shock"], "电击": ["electric", "shock"], "流血": ["bleed", "blood"], "眩晕": ["stun"], "定身": ["root"],
    "陷阱": ["trap", "hazard"], "尖刺": ["spike"], "锯刃": ["saw", "blade"], "喷火": ["flame", "fire"], "毒池": ["poison_pool"],
    "出口": ["exit", "door", "level_exit_door"], "门": ["door", "gate"], "传送": ["teleport", "biome_teleporter"], "平台": ["platform"],
    "卷轴": ["scroll"], "金币": ["gold"], "细胞": ["cell"], "食物": ["food", "healing"], "血瓶": ["flask", "healing"], "图纸": ["blueprint"],
    "hud": ["hud"], "界面": ["hud", "display"], "血条": ["health_bar_hud", "health"], "小地图": ["minimap"], "伤害数字": ["damage_number"], "冷却": ["cooldown"],
    "粒子": ["vfx", "particle"], "特效": ["vfx", "particle"], "视觉": ["vfx", "hud", "display"],
    "侧视角": ["side_camera", "camera"], "镜头": ["side_camera", "camera"], "相机": ["side_camera", "camera"], "震动": ["camera", "feedback", "impulse"],
    "死亡": ["death", "corpse", "corpse_dust"], "消散": ["corpse_dust", "death"], "暴击": ["critical", "critical_hit"], "光环": ["aura", "elite_aura"],
    "近战": ["melee", "weapon"], "远程": ["ranged", "bow"], "武器": ["weapon"], "技能": ["skill"], "变异": ["mutation"],
    "完整": ["all"], "全部": ["all"], "全量": ["all"], "房间": ["room"], "奖励": ["reward"], "跳跃": ["movement", "platform"],
}


def _read_json(name: str, key: str) -> list[dict[str, Any]]:
    data = json.loads((LIBRARY_ROOT / name).read_text(encoding="utf-8"))
    items = data.get(key)
    if not isinstance(items, list):
        raise RuntimeError(f"{name}: expected list at {key}")
    return items


@lru_cache(maxsize=1)
def load_dead_cells_library() -> dict[str, Any]:
    entities = _read_json("entities.json", "entities")
    abilities = _read_json("abilities.json", "abilities")
    behaviors = _read_json("behaviors.json", "behaviors")
    library = {
        "entities": {item["entity_id"]: item for item in entities},
        # The physical file remains abilities.json for compatibility, but entries are semantic Capabilities.
        "abilities": {item["ability_id"]: item for item in abilities},
        "capabilities": {item.get("capability_id", item["ability_id"]): item for item in abilities},
        "behaviors": {item["behavior_id"]: item for item in behaviors},
        "abilities_by_entity": {},
        "capabilities_by_entity": {},
        "behaviors_by_ability": {},
        "behaviors_by_capability": {},
    }
    for key, minimum in MIN_COUNTS.items():
        actual = len(library[key])
        if actual < minimum:
            raise RuntimeError(f"dead cells {key} library count below minimum: expected >= {minimum}, got {actual}")
    for ability in abilities:
        library["abilities_by_entity"].setdefault(ability["entity_id"], []).append(ability["ability_id"])
        library["capabilities_by_entity"].setdefault(ability["entity_id"], []).append(ability.get("capability_id", ability["ability_id"]))
    for behavior in behaviors:
        library["behaviors_by_ability"].setdefault(behavior["ability_id"], []).append(behavior["behavior_id"])
        library["behaviors_by_capability"].setdefault(behavior["ability_id"], []).append(behavior["behavior_id"])
    validate_library_self_consistency(library)
    return library


def _audio_marker(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False).lower()
    return any(marker in text for marker in ["audio", "sound", "sfx", "音效", "声音", "bgm"])


def validate_library_self_consistency(library: dict[str, Any] | None = None) -> None:
    lib = library or load_dead_cells_library()
    if len(lib["entities"]) != len(set(lib["entities"])) or len(lib["abilities"]) != len(set(lib["abilities"])) or len(lib["behaviors"]) != len(set(lib["behaviors"])):
        raise RuntimeError("dead cells library contains duplicate IDs")
    for entity_id, entity in lib["entities"].items():
        if _audio_marker(entity):
            raise RuntimeError(f"audio/SFX entity is forbidden in dead cells library: {entity_id}")
        if "status" in entity_id and entity_id != "status_icon_hud":
            raise RuntimeError(f"runtime status/state must not be gameplay entity: {entity_id}")
        if entity.get("spawnable") is True:
            profile = entity.get("enemy_profile")
            if not isinstance(profile, dict) or not profile.get("allowed_spawn_tags") or not profile.get("default_health"):
                raise RuntimeError(f"spawnable enemy lacks enemy_profile: {entity_id}")
    for ability_id, ability in lib["abilities"].items():
        if _audio_marker(ability):
            raise RuntimeError(f"audio/SFX capability is forbidden in dead cells library: {ability_id}")
        entity_id = ability.get("entity_id", "")
        if entity_id not in lib["entities"]:
            raise RuntimeError(f"capability {ability_id} references unknown entity {entity_id}")
        if any(marker in ability_id for marker in (".state", ".interaction", "accept_interaction", "resolve_interaction")):
            raise RuntimeError(f"generic state/interaction capability is forbidden: {ability_id}")
        if "status" in ability_id and not ability_id.startswith("status_icon_hud"):
            raise RuntimeError(f"status must not be gameplay capability: {ability_id}")
        if ability.get("semantic_role") != "capability":
            raise RuntimeError(f"ability entry must be semantic capability: {ability_id}")
        if ability.get("capability_id") != ability_id:
            raise RuntimeError(f"capability_id must equal legacy ability_id for compatibility: {ability_id}")
        if not ability.get("capability_kind") or not ability.get("action_kind"):
            raise RuntimeError(f"capability lacks capability_kind/action_kind: {ability_id}")
        if not isinstance(ability.get("runtime_primitives"), list) or not ability.get("runtime_primitives"):
            raise RuntimeError(f"capability lacks runtime_primitives: {ability_id}")
        if not isinstance(ability.get("runtime_features"), list) or not ability.get("runtime_features"):
            raise RuntimeError(f"capability lacks runtime_features: {ability_id}")
        if any(feature in {"status", "interaction"} for feature in ability.get("runtime_features", [])):
            raise RuntimeError(f"capability uses forbidden runtime feature status/interaction: {ability_id}")
    for behavior_id, behavior in lib["behaviors"].items():
        if _audio_marker(behavior):
            raise RuntimeError(f"audio/SFX behavior is forbidden in dead cells library: {behavior_id}")
        ability_id = behavior.get("ability_id", "")
        entity_id = behavior.get("entity_id", "")
        ability = lib["abilities"].get(ability_id)
        if not ability:
            raise RuntimeError(f"behavior {behavior_id} references unknown ability {ability_id}")
        if ability.get("entity_id") != entity_id:
            raise RuntimeError(f"behavior {behavior_id} entity mismatch: {entity_id} vs {ability.get('entity_id')}")
        if any(marker in behavior_id for marker in (".state", ".interaction", "accept_interaction", "resolve_interaction")):
            raise RuntimeError(f"generic state/interaction behavior is forbidden: {behavior_id}")
        if "status" in behavior_id and not behavior_id.startswith("status_icon_hud"):
            raise RuntimeError(f"status must not be gameplay behavior: {behavior_id}")
        required = behavior.get("required_capability_ids")
        if not isinstance(required, list) or not required:
            raise RuntimeError(f"behavior lacks required_capability_ids: {behavior_id}")
        for capability_id in required:
            if capability_id not in lib["capabilities"]:
                raise RuntimeError(f"behavior {behavior_id} references unknown capability {capability_id}")
        if not isinstance(behavior.get("runtime_features"), list) or not behavior.get("runtime_features"):
            raise RuntimeError(f"behavior lacks runtime_features: {behavior_id}")
        if any(feature in {"status", "interaction"} for feature in behavior.get("runtime_features", [])):
            raise RuntimeError(f"behavior uses forbidden runtime feature status/interaction: {behavior_id}")
        trigger_text = json.dumps(behavior.get("trigger_model", {}), ensure_ascii=False)
        if "state_entity_id" in trigger_text or "freeze_status" in trigger_text:
            raise RuntimeError(f"behavior trigger_model must use state_key, not gameplay status entity: {behavior_id}")


def _tokens(text: str) -> set[str]:
    lower = text.lower()
    pieces = set(re.findall(r"[a-z0-9_]+", lower))
    for zh, expanded in QUERY_SYNONYMS.items():
        if zh in text:
            pieces.update(x.lower() for x in expanded)
    for token in list(pieces):
        pieces.update(p for p in token.split("_") if p)
    return {p for p in pieces if p and len(p) > 1}


def _entry_text(item: dict[str, Any]) -> str:
    return json.dumps(item, ensure_ascii=False).lower()


def _capability_id(item: dict[str, Any]) -> str:
    return str(item.get("capability_id") or item.get("ability_id") or "")


def _score(item: dict[str, Any], terms: set[str]) -> int:
    haystack = _entry_text(item)
    identifier = str(item.get("entity_id") or item.get("capability_id") or item.get("ability_id") or item.get("behavior_id") or "").lower()
    score = 0
    for term in terms:
        if term in identifier:
            score += 8
        if term in haystack:
            score += 3
    return score


def _top_ids(items: dict[str, dict[str, Any]], id_key: str, terms: set[str], limit: int | None) -> list[str]:
    scored = [(_score(item, terms), item[id_key]) for item in items.values()]
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    if limit is None:
        return [item_id for _score_value, item_id in scored]
    positives = [item_id for score, item_id in scored if score > 0]
    if positives:
        return positives[:limit]
    fallback = [item_id for score, item_id in scored if score == 0]
    return fallback[:limit]


def _explicit_ids(query: str, items: dict[str, dict[str, Any]], id_key: str) -> set[str]:
    lower = query.lower()
    mentioned: set[str] = set()
    name_keys = ("name", "display_name", "display_name_zh", "summary", "summary_zh")
    for item_id, item in items.items():
        names = [str(item.get(key) or "") for key in name_keys]
        if item_id.lower() in lower or any(name and (name.lower() in lower if name.isascii() else name in query) for name in names):
            mentioned.add(item[id_key])
    return mentioned


def _close_candidate_set(entity_ids: set[str], ability_ids: set[str], behavior_ids: set[str]) -> tuple[set[str], set[str], set[str]]:
    lib = load_dead_cells_library()
    for behavior_id in list(behavior_ids):
        behavior = lib["behaviors"].get(behavior_id)
        if not behavior:
            continue
        ability_ids.add(behavior["ability_id"])
        entity_ids.add(behavior["entity_id"])
    for ability_id in list(ability_ids):
        ability = lib["abilities"].get(ability_id)
        if not ability:
            continue
        entity_ids.add(ability["entity_id"])
        behavior_ids.update(lib["behaviors_by_ability"].get(ability_id, []))
    for entity_id in list(entity_ids):
        if entity_id not in lib["entities"]:
            continue
        for ability_id in lib["abilities_by_entity"].get(entity_id, []):
            ability_ids.add(ability_id)
            behavior_ids.update(lib["behaviors_by_ability"].get(ability_id, []))
    return entity_ids, ability_ids, behavior_ids


def build_candidate_set(query: str, *, entity_limit: int = 60, ability_limit: int = 120, behavior_limit: int = 180) -> dict[str, Any]:
    lib = load_dead_cells_library()
    terms = _tokens(query)
    broad = any(token in terms for token in {"all", "complete", "full", "全部", "完整", "全量"})
    e_limit = None if broad else entity_limit
    a_limit = None if broad else ability_limit
    b_limit = None if broad else behavior_limit
    gameplay_terms = terms - {"player", "prisoner"}
    entity_ids = set(_top_ids(lib["entities"], "entity_id", gameplay_terms or terms, e_limit))
    capability_terms = gameplay_terms
    ability_ids = set(_top_ids(lib["abilities"], "ability_id", capability_terms or terms, a_limit))
    behavior_ids = set(_top_ids(lib["behaviors"], "behavior_id", capability_terms or terms, b_limit))
    entity_ids.update(_explicit_ids(query, lib["entities"], "entity_id"))
    ability_ids.update(_explicit_ids(query, lib["abilities"], "ability_id"))
    behavior_ids.update(_explicit_ids(query, lib["behaviors"], "behavior_id"))
    entity_ids.update(CORE_ENTITY_IDS)
    behavior_ids.update(CORE_BEHAVIOR_IDS)
    entity_ids, ability_ids, behavior_ids = _close_candidate_set(entity_ids, ability_ids, behavior_ids)
    return {
        "schema_version": "autoue-dead-cells-candidate-set/v3",
        "query": query,
        "selection_rule": "EntityAbilityBehaviorPlanner may select only IDs listed here. The second library is Capability; selected_capability_ids is canonical. selected_ability_ids is accepted only as a legacy input alias and is never emitted canonically.",
        "candidate_entity_ids": sorted(entity_ids),
        "candidate_ability_ids": sorted(ability_ids),
        "candidate_capability_ids": sorted(ability_ids),
        "candidate_behavior_ids": sorted(behavior_ids),
        "entities": [lib["entities"][i] for i in sorted(entity_ids) if i in lib["entities"]],
        "abilities": [lib["abilities"][i] for i in sorted(ability_ids) if i in lib["abilities"]],
        "capabilities": [lib["abilities"][i] for i in sorted(ability_ids) if i in lib["abilities"]],
        "behaviors": [lib["behaviors"][i] for i in sorted(behavior_ids) if i in lib["behaviors"]],
    }


def parse_selection_output(node: str, data: Any) -> dict[str, list[str]]:
    if not isinstance(data, dict):
        raise _validation_error(f"{node}: selection output must be a JSON object")
    result: dict[str, list[str]] = {}
    for key in ("selected_entity_ids", "selected_ability_ids", "selected_capability_ids", "selected_behavior_ids"):
        values = data.get(key, [])
        if not isinstance(values, list):
            raise _validation_error(f"{node}: {key} must be a list")
        cleaned = []
        for item in values:
            if not isinstance(item, str) or not item.strip():
                raise _validation_error(f"{node}: {key} must contain non-empty strings")
            if item not in cleaned:
                cleaned.append(item)
        result[key] = cleaned
    merged_capabilities = []
    for item in result.get("selected_capability_ids", []) + result.get("selected_ability_ids", []):
        if item not in merged_capabilities:
            merged_capabilities.append(item)
    result["selected_capability_ids"] = merged_capabilities
    result.pop("selected_ability_ids", None)
    if not result["selected_behavior_ids"] and not result["selected_capability_ids"]:
        raise _validation_error(f"{node}: select at least one behavior_id or capability_id")
    return result


def validate_selection_against_library_and_candidates(node: str, selection: dict[str, list[str]], candidate_set: dict[str, Any]) -> None:
    lib = load_dead_cells_library()
    candidate_entities = set(candidate_set.get("candidate_entity_ids", []))
    candidate_abilities = set(candidate_set.get("candidate_capability_ids") or candidate_set.get("candidate_ability_ids", []))
    candidate_behaviors = set(candidate_set.get("candidate_behavior_ids", []))
    for entity_id in selection.get("selected_entity_ids", []):
        if entity_id not in lib["entities"]:
            raise _validation_error(f"{node}: selected entity_id is not in library: {entity_id}")
        if entity_id not in candidate_entities:
            raise _validation_error(f"{node}: selected entity_id is not in this candidate set: {entity_id}")
    for ability_id in selection.get("selected_capability_ids", selection.get("selected_ability_ids", [])):
        ability = lib["abilities"].get(ability_id)
        if not ability:
            raise _validation_error(f"{node}: selected capability_id is not in library: {ability_id}")
        if ability_id not in candidate_abilities:
            raise _validation_error(f"{node}: selected capability_id is not in this candidate set: {ability_id}")
        if ability["entity_id"] not in candidate_entities:
            raise _validation_error(f"{node}: selected capability parent entity is not in candidate set: {ability_id}")
    for behavior_id in selection.get("selected_behavior_ids", []):
        behavior = lib["behaviors"].get(behavior_id)
        if not behavior:
            raise _validation_error(f"{node}: selected behavior_id is not in library: {behavior_id}")
        if behavior_id not in candidate_behaviors:
            raise _validation_error(f"{node}: selected behavior_id is not in this candidate set: {behavior_id}")
        if behavior["ability_id"] not in candidate_abilities or behavior["entity_id"] not in candidate_entities:
            raise _validation_error(f"{node}: selected behavior parent closure is not in candidate set: {behavior_id}")


def canonicalize_selection(selection: dict[str, list[str]]) -> dict[str, Any]:
    lib = load_dead_cells_library()
    entity_ids = set(selection.get("selected_entity_ids", []))
    ability_ids = set(selection.get("selected_capability_ids", selection.get("selected_ability_ids", [])))
    behavior_ids = set(selection.get("selected_behavior_ids", []))
    for ability_id in list(ability_ids):
        ability = lib["abilities"][ability_id]
        entity_ids.add(ability["entity_id"])
        behavior_ids.update(lib["behaviors_by_ability"].get(ability_id, []))
    for behavior_id in list(behavior_ids):
        behavior = lib["behaviors"][behavior_id]
        ability_ids.add(behavior["ability_id"])
        entity_ids.add(behavior["entity_id"])
        for capability_id in behavior.get("required_capability_ids", []):
            capability = lib["capabilities"].get(capability_id)
            if capability:
                entity_ids.add(capability.get("entity_id", ""))
    entity_ids.discard("")
    entities = []
    for entity_id in sorted(entity_ids):
        source_entity = dict(lib["entities"][entity_id])
        entity_abilities = []
        for ability_id in sorted(a for a in ability_ids if lib["abilities"][a]["entity_id"] == entity_id):
            source_ability = dict(lib["abilities"][ability_id])
            source_ability["semantic_role"] = "capability"
            selected_behaviors = [b for b in sorted(behavior_ids) if lib["behaviors"][b]["ability_id"] == ability_id]
            if not selected_behaviors:
                continue
            source_ability["behaviors"] = [dict(lib["behaviors"][behavior_id]) for behavior_id in selected_behaviors]
            entity_abilities.append(source_ability)
        source_entity["abilities"] = entity_abilities
        entities.append(source_entity)
    return {"entities": entities, "non_goals": []}


def validate_entity_ability_behavior_against_library(node: str, data: dict[str, Any]) -> None:
    lib = load_dead_cells_library()
    for entity in data.get("entities", []):
        if not isinstance(entity, dict):
            continue
        entity_id = entity.get("entity_id", "")
        if entity_id not in lib["entities"]:
            raise _validation_error(f"{node}: entity_id is not in dead_cells entity library: {entity_id}")
        for ability in entity.get("abilities", []) or []:
            if not isinstance(ability, dict):
                continue
            ability_id = ability.get("ability_id", "")
            known_ability = lib["abilities"].get(ability_id)
            if not known_ability:
                raise _validation_error(f"{node}: capability/ability_id is not in dead_cells capability library: {ability_id}")
            if known_ability.get("entity_id") != entity_id:
                raise _validation_error(f"{node}: ability_id {ability_id} belongs to {known_ability.get('entity_id')}, not generated entity {entity_id}")
            for behavior in ability.get("behaviors", []) or []:
                if not isinstance(behavior, dict):
                    continue
                behavior_id = behavior.get("behavior_id", "")
                known_behavior = lib["behaviors"].get(behavior_id)
                if not known_behavior:
                    raise _validation_error(f"{node}: behavior_id is not in dead_cells behavior library: {behavior_id}")
                if known_behavior.get("ability_id") != ability_id:
                    raise _validation_error(f"{node}: behavior_id {behavior_id} belongs to {known_behavior.get('ability_id')}, not generated ability {ability_id}")
                if known_behavior.get("entity_id") != entity_id:
                    raise _validation_error(f"{node}: behavior_id {behavior_id} belongs to {known_behavior.get('entity_id')}, not generated entity {entity_id}")


def render_candidate_set_prompt(candidate_set: dict[str, Any]) -> str:
    compact = {
        "library_contract": "Only select IDs from this candidate set. Output ID selection only; do not write entity/ability/behavior text. Audio/SFX is intentionally excluded.",
        "selected_output_shape": {
            "selected_entity_ids": ["optional entity ids for entities that must appear even without selected behaviors"],
            "selected_capability_ids": ["optional capability ids; selecting one expands all child behaviors"],
            "selected_behavior_ids": ["required behavior ids relevant to the user request"],
        },
        "entities": [
            {"entity_id": e["entity_id"], "name": e.get("display_name_zh") or e.get("display_name"), "kind": e.get("entity_kind"), "tags": e.get("content_tags", [])}
            for e in candidate_set.get("entities", [])
        ],
        "capabilities": [
            {"capability_id": a.get("capability_id", a["ability_id"]), "legacy_ability_id": a["ability_id"], "entity_id": a["entity_id"], "kind": a.get("capability_kind"), "runtime_primitives": a.get("runtime_primitives", []), "engine_ports": a.get("engine_ports", []), "name": a.get("display_name_zh") or a.get("display_name")}
            for a in candidate_set.get("capabilities", candidate_set.get("abilities", []))
        ],
        "behaviors": [
            {"behavior_id": b["behavior_id"], "parent_capability_id": b["ability_id"], "entity_id": b["entity_id"], "required_capability_ids": b.get("required_capability_ids", []), "runtime_features": b.get("runtime_features", []), "name": b.get("display_name_zh") or b.get("display_name")}
            for b in candidate_set.get("behaviors", [])
        ],
    }
    return json.dumps(compact, ensure_ascii=False, indent=2)
