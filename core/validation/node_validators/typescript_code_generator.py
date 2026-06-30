"""Node-specific workflow output validator."""

from __future__ import annotations

from typing import Any

from core.validation.common import WorkflowValidationError, require_list, validate_ts_path
from core.validation.node_validators.typescript_interactive_object_generator import _reject_raw_files, _template_inputs, _traces

ENEMY_TEMPLATES = {"enemy_archetypes", "spawn_point_registry", "enemy_archetype_registry", "enemy_spawn_manager", "encounter_manager", "encounter_spec_data"}


def validate_typescript_code_generator(node: str, data: dict[str, Any]) -> None:
    _reject_raw_files(node, data)
    runtime_features = require_list(node, data, "runtime_features", non_empty=True)
    if any(not isinstance(item, str) or not item.strip() for item in runtime_features):
        raise WorkflowValidationError(f"{node}: runtime_features must contain non-empty strings")
    if any(item in {"status", "interaction"} for item in runtime_features):
        raise WorkflowValidationError(f"{node}: runtime_features must not contain status/interaction")
    disabled_features = require_list(node, data, "disabled_features")
    if any(not isinstance(item, str) or not item.strip() for item in disabled_features):
        raise WorkflowValidationError(f"{node}: disabled_features must contain non-empty strings")
    if "enemy_encounter" in runtime_features and "enemy_encounter" in disabled_features:
        raise WorkflowValidationError(f"{node}: enemy_encounter cannot be both enabled and disabled")
    template_names = {item.get("template", "") for item in data.get("template_inputs", []) if isinstance(item, dict)}
    enemy_templates = sorted(template_names.intersection(ENEMY_TEMPLATES))
    if enemy_templates and "enemy_encounter" not in runtime_features:
        raise WorkflowValidationError(f"{node}: enemy templates require runtime_features to include enemy_encounter: {enemy_templates}")
    paths = _template_inputs(node, data)
    _traces(node, data, paths)
    for pi, path in enumerate(require_list(node, data, "consumed_interactive_files", non_empty=True)):
        if not isinstance(path, str):
            raise WorkflowValidationError(f"{node}: consumed_interactive_files[{pi}] must be string")
        validate_ts_path(node, path, label=f"consumed_interactive_files[{pi}]")
    require_list(node, data, "validation_notes")
