"""Compatibility facade for workflow validation.

New code should import from core.validation.*.  This module remains so existing
callers/tests can keep using core.workflow_validation while the implementation
lives in the split validation package.
"""

from __future__ import annotations

from core.validation.common import (
    ALLOWED_CARRIERS,
    ALLOWED_HIT_TYPES,
    ALLOWED_STAGES,
    ALLOWED_TEMPLATES,
    ALLOWED_VERDICTS,
    BANNED_FLOW_MARKERS,
    BANNED_NATIVE_MARKERS,
    BANNED_OUTPUT_MARKERS,
    CXX_FILE_RE,
    RUNTIME_MAPPING_PATH,
    TS_IDENT_RE,
    WORKFLOW_NODE_ORDER,
    WorkflowValidationError,
    canonical_json,
    is_safe_relative_path,
    parse_node_json,
    require_dict,
    require_identifier,
    require_list,
    require_string,
    strip_json_fence,
    validate_common_workflow_contract,
    validate_json_path,
    validate_rel_path,
    validate_ts_path,
    walk_keys,
    walk_strings,
)
from core.validation.cross_trace import collect_behavior_index, validate_cross_trace
from core.validation.registry import (
    NODE_VALIDATORS,
    NODE_VALIDATOR_IDS,
    VALIDATOR_REGISTRY,
    default_validator_id_for_node,
    parse_validated_node_output,
    resolve_validator,
    validate_node_data,
    validate_node_output,
)
from core.validation.workflow import (
    validate_graph_node_output,
    validate_partial_workflow_outputs,
    validate_workflow_output_set,
)
from core.validation.node_validators.scene_and_gameplay_splitter import validate_scene_and_gameplay_splitter
from core.validation.node_validators.entity_ability_behavior_planner import validate_entity_ability_behavior_planner
from core.validation.node_validators.thin_gameplay_flow_planner import validate_thin_gameplay_flow_planner
from core.validation.node_validators.encounter_spec_planner import validate_encounter_spec_planner
from core.validation.node_validators.ue_api_mcp_feasibility_searcher import validate_ue_api_mcp_feasibility_searcher
from core.validation.node_validators.puerts_runtime_mapping_planner import validate_puerts_runtime_mapping_planner
from core.validation.node_validators.typescript_script_analyzer import validate_typescript_script_analyzer
from core.validation.node_validators.typescript_interactive_object_generator import validate_typescript_interactive_object_generator
from core.validation.node_validators.typescript_code_generator import validate_typescript_code_generator
from core.validation.node_validators.evaluate_instruction_generator import validate_evaluate_instruction_generator

_cross = validate_cross_trace
