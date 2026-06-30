from __future__ import annotations

import json
from typing import Any

from core.BaseLLMNode import BaseLLMNode, GraphState
from core.workflow_validation import parse_node_json, validate_graph_node_output

TYPESCRIPT_SCRIPT_ANALYZER_PROMPT = """SCHEMA: TypeScriptScriptAnalyzer
Deterministic Python node. Convert PuerTS runtime mappings into behavior-level TypeScript/PuerTS implementation slots. Support bridge files are generated later by TypeScriptCodeGenerator. Return JSON only.
"""

REQUIRED_MAPPING_FIELDS = ("entity_id", "behavior_id", "flow_id", "runtime_owner")


def _runtime_mappings(mapping_node: dict[str, Any]) -> list[Any]:
    raw = mapping_node.get("runtime_mappings")
    if raw is None:
        raw = mapping_node.get("mappings", [])
    return raw if isinstance(raw, list) else []


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def generate_typescript_script_analysis(entity_output: str, runtime_mapping_output: str) -> str:
    """Build TypeScriptScriptAnalyzer output without invoking an LLM.

    The node intentionally only performs a deterministic projection:
    each valid PuerTS runtime mapping becomes exactly one implementation slot,
    and target_ts_file is copied from mapping.runtime_owner.
    """
    # EntityAbilityBehaviorPlanner is still a required input.  Parse it so a
    # malformed/missing upstream artifact fails loudly instead of silently
    # allowing the deterministic projection to proceed without its context.
    parse_node_json("EntityAbilityBehaviorPlanner", entity_output)
    mapping_node = parse_node_json("PuerTSRuntimeMappingPlanner", runtime_mapping_output)
    if not isinstance(mapping_node, dict):
        raise RuntimeError("PuerTSRuntimeMappingPlanner output must be a JSON object")

    top_runtime_mapping_path = _string(mapping_node.get("runtime_mapping_path"))
    sources: list[dict[str, str]] = []
    seen_sources: set[str] = set()
    slots: list[dict[str, str]] = []
    missing_slots: list[dict[str, Any]] = []

    mappings = _runtime_mappings(mapping_node)
    if not mappings:
        missing_slots.append({"mapping_index": None, "missing_fields": ["mappings"], "reason": "no runtime mappings found"})

    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            missing_slots.append({"mapping_index": index, "missing_fields": ["mapping_object"], "reason": "mapping must be object"})
            continue

        runtime_mapping_path = _string(mapping.get("runtime_mapping_path")) or top_runtime_mapping_path
        values = {field: _string(mapping.get(field)) for field in REQUIRED_MAPPING_FIELDS}
        missing = [field for field, value in values.items() if not value]
        if not runtime_mapping_path:
            missing.append("runtime_mapping_path")
        if missing:
            missing_slots.append({
                "mapping_index": index,
                "behavior_id": _string(mapping.get("behavior_id")),
                "entity_id": _string(mapping.get("entity_id")),
                "missing_fields": missing,
                "reason": "runtime mapping lacks required analyzer fields",
            })
            continue

        target = values["runtime_owner"]
        if target not in seen_sources:
            sources.append({
                "path": target,
                "role": "runtime_owner",
                "notes": "deterministically projected from PuerTSRuntimeMappingPlanner.runtime_owner",
            })
            seen_sources.add(target)

        slots.append({
            "entity_id": values["entity_id"],
            "behavior_id": values["behavior_id"],
            "flow_id": values["flow_id"],
            "runtime_mapping_path": runtime_mapping_path,
            "target_ts_file": target,
            "reason": "deterministically projected from PuerTSRuntimeMappingPlanner runtime mapping",
        })

    return json.dumps({
        "typescript_sources": sources,
        "implementation_slots": slots,
        "missing_slots": missing_slots,
    }, ensure_ascii=False, indent=2)


def build_ts_context(node: BaseLLMNode, state: GraphState, full_input: str) -> None:
    required = {
        "EntityAbilityBehaviorPlanner": state.llm_outputs.get("EntityAbilityBehaviorPlanner", ""),
        "PuerTSRuntimeMappingPlanner": state.llm_outputs.get("PuerTSRuntimeMappingPlanner", ""),
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing:
        raise RuntimeError(f"TypeScriptScriptAnalyzer missing upstream outputs: {missing}")
    node.full_input = "\n\n".join(f"{name} JSON:\n{value}" for name, value in required.items()) + (
        "\n\nDeterministic Python projection: for every runtime mapping, emit exactly one implementation slot whose target_ts_file equals mapping.runtime_owner."
    )


class DeterministicTypeScriptScriptAnalyzer(BaseLLMNode):
    """A BaseLLMNode-compatible deterministic node.

    BaseLLMNode still handles validation, timing, state propagation, and graph
    wiring, but this override never invokes self.model, so token usage remains 0.
    """

    def call_model(self, full_input: str, state: GraphState):  # noqa: D401 - BaseLLMNode signature
        if self.name not in state.node_token_usage:
            state.node_token_usage[self.name] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return generate_typescript_script_analysis(
            state.llm_outputs.get("EntityAbilityBehaviorPlanner", ""),
            state.llm_outputs.get("PuerTSRuntimeMappingPlanner", ""),
        )


def create_typescript_script_analyzer() -> BaseLLMNode:
    return DeterministicTypeScriptScriptAnalyzer(
        name="TypeScriptScriptAnalyzer",
        prompt=TYPESCRIPT_SCRIPT_ANALYZER_PROMPT,
        pre_action=build_ts_context,
        output_validator=validate_graph_node_output,
        enable_feedback=False,
    )
