"""Registry for workflow node output validators."""

from __future__ import annotations

from typing import Any, Callable

from core.validation.common import (
    WorkflowValidationError,
    canonical_json,
    parse_node_json,
    validate_common_workflow_contract,
)
from core.validation.node_validators.encounter_spec_planner import validate_encounter_spec_planner
from core.validation.node_validators.entity_ability_behavior_planner import validate_entity_ability_behavior_planner
from core.validation.node_validators.evaluate_instruction_generator import validate_evaluate_instruction_generator
from core.validation.node_validators.puerts_runtime_mapping_planner import validate_puerts_runtime_mapping_planner
from core.validation.node_validators.scene_and_gameplay_splitter import validate_scene_and_gameplay_splitter
from core.validation.node_validators.thin_gameplay_flow_planner import validate_thin_gameplay_flow_planner
from core.validation.node_validators.typescript_code_generator import validate_typescript_code_generator
from core.validation.node_validators.typescript_interactive_object_generator import validate_typescript_interactive_object_generator
from core.validation.node_validators.typescript_script_analyzer import validate_typescript_script_analyzer
from core.validation.node_validators.ue_api_mcp_feasibility_searcher import validate_ue_api_mcp_feasibility_searcher

NodeValidator = Callable[[str, dict[str, Any]], None]

VALIDATOR_REGISTRY: dict[str, NodeValidator] = {
    "scene_and_gameplay_splitter": validate_scene_and_gameplay_splitter,
    "entity_ability_behavior_planner": validate_entity_ability_behavior_planner,
    "thin_gameplay_flow_planner": validate_thin_gameplay_flow_planner,
    "encounter_spec_planner": validate_encounter_spec_planner,
    "ue_api_mcp_feasibility_searcher": validate_ue_api_mcp_feasibility_searcher,
    "puerts_runtime_mapping_planner": validate_puerts_runtime_mapping_planner,
    "typescript_script_analyzer": validate_typescript_script_analyzer,
    "typescript_interactive_object_generator": validate_typescript_interactive_object_generator,
    "typescript_code_generator": validate_typescript_code_generator,
    "evaluate_instruction_generator": validate_evaluate_instruction_generator,
}

NODE_VALIDATOR_IDS: dict[str, str] = {
    "SceneAndGameplaySplitter": "scene_and_gameplay_splitter",
    "EntityAbilityBehaviorPlanner": "entity_ability_behavior_planner",
    "ThinGameplayFlowPlanner": "thin_gameplay_flow_planner",
    "EncounterSpecPlanner": "encounter_spec_planner",
    "UEApiMCPFeasibilitySearcher": "ue_api_mcp_feasibility_searcher",
    "PuerTSRuntimeMappingCompiler": "puerts_runtime_mapping_planner",
    "TypeScriptImplementationSlotProjector": "typescript_script_analyzer",
    "TypeScriptInteractiveTemplatePlanner": "typescript_interactive_object_generator",
    "TypeScriptRuntimeTemplatePlanner": "typescript_code_generator",
    "StaticEvaluationPlanBuilder": "evaluate_instruction_generator",
}

NODE_VALIDATORS: dict[str, NodeValidator] = {
    node_name: VALIDATOR_REGISTRY[validator_id]
    for node_name, validator_id in NODE_VALIDATOR_IDS.items()
}


def resolve_validator(validator_id: str) -> NodeValidator:
    try:
        return VALIDATOR_REGISTRY[validator_id]
    except KeyError as exc:
        known = ", ".join(sorted(VALIDATOR_REGISTRY))
        raise WorkflowValidationError(f"Unknown workflow validator: {validator_id}. Known validators: {known}") from exc


def default_validator_id_for_node(node_name: str) -> str:
    try:
        return NODE_VALIDATOR_IDS[node_name]
    except KeyError as exc:
        raise WorkflowValidationError(f"Unknown workflow node: {node_name}") from exc


def validate_node_data(node_name: str, data: Any, *, validator_id: str | None = None) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise WorkflowValidationError(f"{node_name}: output JSON must be an object")
    selected = validator_id or default_validator_id_for_node(node_name)
    validate_common_workflow_contract(node_name, data)
    resolve_validator(selected)(node_name, data)
    return data


def validate_node_output(node_name: str, text: str, *, validator_id: str | None = None) -> str:
    data = parse_node_json(node_name, text)
    validate_node_data(node_name, data, validator_id=validator_id)
    return canonical_json(data)


def parse_validated_node_output(node_name: str, text: str, *, validator_id: str | None = None) -> dict[str, Any]:
    data = parse_node_json(node_name, validate_node_output(node_name, text, validator_id=validator_id))
    if not isinstance(data, dict):
        raise WorkflowValidationError(f"{node_name}: output JSON must be object")
    return data
