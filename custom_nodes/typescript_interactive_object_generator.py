from __future__ import annotations

import json

from core.BaseLLMNode import BaseLLMNode, GraphState
from core.workflow_validation import validate_graph_node_output
from custom_nodes.template_file_writer import write_files_from_output
from tools.workflow_steps.typescript_interactive_plan import run_typescript_interactive_plan

NODE_NAME = "TypeScriptInteractiveTemplatePlanner"
RUNTIME_NODE = "PuerTSRuntimeMappingCompiler"
SLOT_NODE = "TypeScriptImplementationSlotProjector"
PROMPT = """SCHEMA: TypeScriptInteractiveTemplatePlanner
确定性 Python 节点。为交互对象选择 TypeScript/PuerTS 模板并生成 template_inputs。返回 JSON only。
"""


def build_interactive_context(node: BaseLLMNode, state: GraphState, full_input: str) -> None:
    required = {
        "EntityAbilityBehaviorPlanner": state.llm_outputs.get("EntityAbilityBehaviorPlanner", ""),
        RUNTIME_NODE: state.llm_outputs.get(RUNTIME_NODE, ""),
        SLOT_NODE: state.llm_outputs.get(SLOT_NODE, ""),
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing:
        raise RuntimeError(f"{NODE_NAME} missing upstream outputs: {missing}")
    node.full_input = "Deterministic interactive template planning."


class DeterministicTypeScriptInteractiveTemplatePlanner(BaseLLMNode):
    deterministic = True

    def call_model(self, full_input: str, state: GraphState):
        if self.name not in state.node_token_usage:
            state.node_token_usage[self.name] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        output = run_typescript_interactive_plan({
            "runtime_mapping": state.llm_outputs.get(RUNTIME_NODE, ""),
            "ts_slots": state.llm_outputs.get(SLOT_NODE, ""),
        })
        return json.dumps(output, ensure_ascii=False, indent=2)


def write_interactive_files(state: GraphState, output: str) -> None:
    write_files_from_output(state, NODE_NAME, output)


def create_typescript_interactive_object_generator() -> BaseLLMNode:
    return DeterministicTypeScriptInteractiveTemplatePlanner(
        name=NODE_NAME,
        prompt=PROMPT,
        pre_action=build_interactive_context,
        output_validator=validate_graph_node_output,
        post_action=write_interactive_files,
        enable_feedback=False,
    )
