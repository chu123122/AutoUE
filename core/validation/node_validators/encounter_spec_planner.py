"""Node-specific workflow output validator."""

from __future__ import annotations

from typing import Any

from core.encounter_validation import EncounterValidationError, validate_encounter_spec_data
from core.validation.common import WorkflowValidationError

def validate_encounter_spec_planner(node: str, data: dict[str, Any]) -> None:
    try:
        validate_encounter_spec_data(data)
    except EncounterValidationError as exc:
        raise WorkflowValidationError(str(exc)) from exc
