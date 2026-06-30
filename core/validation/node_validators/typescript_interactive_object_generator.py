"""Node-specific workflow output validator."""

from __future__ import annotations

from typing import Any

from core.validation.common import ALLOWED_TEMPLATES, WorkflowValidationError, require_identifier, require_list, require_string, validate_json_path, validate_ts_path, walk_keys

def _reject_raw_files(node: str, data: dict[str, Any]) -> None:
    if {"files", "content"}.intersection(walk_keys(data)):
        raise WorkflowValidationError(f"{node}: raw files/content are forbidden; use template_inputs rendered by Python templates")

def _template_inputs(node: str, data: dict[str, Any]) -> set[str]:
    _reject_raw_files(node, data)
    paths = set()
    for ii, item in enumerate(require_list(node, data, "template_inputs", non_empty=True)):
        if not isinstance(item, dict):
            raise WorkflowValidationError(f"{node}: template_inputs[{ii}] must be object")
        template = require_string(node, item, "template", non_empty=True)
        if template not in ALLOWED_TEMPLATES[node]:
            raise WorkflowValidationError(f"{node}: invalid template {template}")
        path = require_string(node, item, "path", non_empty=True)
        validate_ts_path(node, path, label=f"template_inputs[{ii}].path")
        if path in paths:
            raise WorkflowValidationError(f"{node}: duplicate template output path would overwrite a rendered file: {path}")
        paths.add(path)
        for key in ("entity_id", "behavior_id", "flow_id"):
            require_string(node, item, key, non_empty=True)
        validate_json_path(node, require_string(node, item, "runtime_mapping_path", non_empty=True), label=f"template_inputs[{ii}].runtime_mapping_path")
        require_identifier(node, item, "export_name")
        require_identifier(node, item, "interface_name")
        for key in ("action_label", "target_label", "result_label"):
            require_string(node, item, key, non_empty=True)
    return paths

def _traces(node: str, data: dict[str, Any], paths: set[str]) -> None:
    for ti, trace in enumerate(require_list(node, data, "behavior_traces", non_empty=True)):
        if not isinstance(trace, dict):
            raise WorkflowValidationError(f"{node}: behavior_traces[{ti}] must be object")
        for key in ("entity_id", "behavior_id", "flow_id"):
            require_string(node, trace, key, non_empty=True)
        validate_json_path(node, require_string(node, trace, "runtime_mapping_path", non_empty=True), label=f"behavior_traces[{ti}].runtime_mapping_path")
        file_path = require_string(node, trace, "file_path", non_empty=True)
        validate_ts_path(node, file_path, label=f"behavior_traces[{ti}].file_path")
        if file_path not in paths:
            raise WorkflowValidationError(f"{node}: behavior trace references non-rendered template path: {file_path}")

def validate_typescript_interactive_object_generator(node: str, data: dict[str, Any]) -> None:
    paths = _template_inputs(node, data)
    _traces(node, data, paths)
    require_list(node, data, "validation_notes")
