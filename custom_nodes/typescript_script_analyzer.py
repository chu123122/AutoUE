from __future__ import annotations

import json

from core.BaseLLMNode import BaseLLMNode, GraphState
from core.workflow_validation import validate_graph_node_output
from tools.workflow_steps.typescript_slot_projection import generate_typescript_slot_projection, run_typescript_slot_projection

NODE_NAME = "TypeScriptImplementationSlotProjector"
UPSTREAM_RUNTIME_NODE = "PuerTSRuntimeMappingCompiler"
PROMPT = """SCHEMA: TypeScriptImplementationSlotProjector
确定性 Python 节点。把 PuerTS runtime mapping 投影为 TypeScript/PuerTS 实现槽位。返回 JSON only。
"""


def generate_typescript_script_analysis(entity_output: str, runtime_mapping_output: str) -> str:
    return generate_typescript_slot_projection(entity_output, runtime_mapping_output)


def build_ts_context(node: BaseLLMNode, state: GraphState, full_input: str) -> None:
    required = {
        "EntityAbilityBehaviorPlanner": state.llm_outputs.get("EntityAbilityBehaviorPlanner", ""),
        UPSTREAM_RUNTIME_NODE: state.llm_outputs.get(UPSTREAM_RUNTIME_NODE, ""),
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing:
        raise RuntimeError(f"{NODE_NAME} missing upstream outputs: {missing}")
    node.full_input = "Deterministic TypeScript implementation slot projection."


class DeterministicTypeScriptImplementationSlotProjector(BaseLLMNode):
    deterministic = True

    def call_model(self, full_input: str, state: GraphState):
        if self.name not in state.node_token_usage:
            state.node_token_usage[self.name] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        output = run_typescript_slot_projection({
            "entity_behavior": state.llm_outputs.get("EntityAbilityBehaviorPlanner", ""),
            "runtime_mapping": state.llm_outputs.get(UPSTREAM_RUNTIME_NODE, ""),
        })
        return json.dumps(output, ensure_ascii=False, indent=2)


def create_typescript_script_analyzer() -> BaseLLMNode:
    return DeterministicTypeScriptImplementationSlotProjector(
        name=NODE_NAME,
        prompt=PROMPT,
        pre_action=build_ts_context,
        output_validator=validate_graph_node_output,
        enable_feedback=False,
    )
