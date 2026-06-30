"""Node-specific workflow output validator."""

from __future__ import annotations

from typing import Any

from core.validation.common import WorkflowValidationError, require_list, validate_ts_path
from core.validation.node_validators.typescript_interactive_object_generator import _template_inputs, _traces

def validate_typescript_code_generator(node: str, data: dict[str, Any]) -> None:
    paths = _template_inputs(node, data)
    _traces(node, data, paths)
    for pi, path in enumerate(require_list(node, data, "consumed_interactive_files", non_empty=True)):
        if not isinstance(path, str):
            raise WorkflowValidationError(f"{node}: consumed_interactive_files[{pi}] must be string")
        validate_ts_path(node, path, label=f"consumed_interactive_files[{pi}]")
    require_list(node, data, "validation_notes")
