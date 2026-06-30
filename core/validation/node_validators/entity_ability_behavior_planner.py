"""Node-specific workflow output validator."""

from __future__ import annotations

from typing import Any

from core.encounter_validation import EncounterValidationError, validate_spawnable_enemy_entity
from core.validation.common import WorkflowValidationError, require_list, require_string, walk_keys

def validate_entity_ability_behavior_planner(node: str, data: dict[str, Any]) -> None:
    forbidden = {"files", "path", "file_path", "target_ts_file", "implementation_slots", "content", "ts_files", "template_inputs", "engine_ports", "flow_id", "runtime_mapping_path"}
    bad = sorted(forbidden.intersection(walk_keys(data)))
    if bad:
        raise WorkflowValidationError(f"{node}: planner is definition-only and must not decide files, templates, engine ports, flows, or implementation slots: {bad}")
    seen_entities: set[str] = set()
    for ei, entity in enumerate(require_list(node, data, "entities", non_empty=True)):
        if not isinstance(entity, dict):
            raise WorkflowValidationError(f"{node}: entities[{ei}] must be object")
        for key in ("entity_id", "display_name", "summary"):
            require_string(node, entity, key, non_empty=True)
        entity_id = entity["entity_id"]
        if entity_id in seen_entities:
            raise WorkflowValidationError(f"{node}: duplicate entity_id: {entity_id}")
        seen_entities.add(entity_id)
        if "entity_kind" in entity:
            require_string(node, entity, "entity_kind", non_empty=True)
        if "content_tags" in entity:
            tags = require_list(node, entity, "content_tags")
            if any(not isinstance(tag, str) or not tag.strip() for tag in tags):
                raise WorkflowValidationError(f"{node}: content_tags must contain non-empty strings")
        if "spawnable" in entity and not isinstance(entity["spawnable"], bool):
            raise WorkflowValidationError(f"{node}: spawnable must be bool when present")
        if entity.get("spawnable") is True:
            try:
                validate_spawnable_enemy_entity(entity, label=node)
            except EncounterValidationError as exc:
                raise WorkflowValidationError(str(exc)) from exc
        for ai, ability in enumerate(require_list(node, entity, "abilities")):
            if not isinstance(ability, dict):
                raise WorkflowValidationError(f"{node}: abilities[{ai}] must be object")
            for key in ("ability_id", "display_name", "summary"):
                require_string(node, ability, key, non_empty=True)
            for bi, behavior in enumerate(require_list(node, ability, "behaviors", non_empty=True)):
                if not isinstance(behavior, dict):
                    raise WorkflowValidationError(f"{node}: behaviors[{bi}] must be object")
                for key in ("behavior_id", "display_name", "trigger", "execution", "result"):
                    require_string(node, behavior, key, non_empty=True)
                if "source_refs" in behavior:
                    require_list(node, behavior, "source_refs")
