from __future__ import annotations

import json

from core.BaseLLMNode import BaseLLMNode, GraphState
from core.workflow_validation import validate_graph_node_output
from custom_nodes.template_file_writer import write_files_from_output
from tools.workflow_steps.typescript_runtime_template_plan import run_typescript_runtime_template_plan

NODE_NAME = "TypeScriptRuntimeTemplatePlanner"
RUNTIME_NODE = "PuerTSRuntimeMappingCompiler"
SLOT_NODE = "TypeScriptImplementationSlotProjector"
INTERACTIVE_NODE = "TypeScriptInteractiveTemplatePlanner"
PROMPT = """SCHEMA: TypeScriptRuntimeTemplatePlanner
确定性 Python 节点。生成共享 runtime framework 和 BehaviorSpec 的 TypeScript template_inputs。禁止输出原始 TypeScript 源码。
"""


def build_codegen_output(state: GraphState) -> dict:
    return run_typescript_runtime_template_plan({
        "runtime_mapping": state.llm_outputs.get(RUNTIME_NODE, ""),
        "ts_slots": state.llm_outputs.get(SLOT_NODE, ""),
        "interactive_ts_plan": state.llm_outputs.get(INTERACTIVE_NODE, ""),
    })


def build_generation_context(node: BaseLLMNode, state: GraphState, full_input: str) -> None:
    required = {
        RUNTIME_NODE: state.llm_outputs.get(RUNTIME_NODE, ""),
        SLOT_NODE: state.llm_outputs.get(SLOT_NODE, ""),
        INTERACTIVE_NODE: state.llm_outputs.get(INTERACTIVE_NODE, ""),
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing:
        raise RuntimeError(f"{NODE_NAME} missing upstream outputs: {missing}")
    node.full_input = "Deterministic TypeScript runtime template planning."


class DeterministicTypeScriptRuntimeTemplatePlanner(BaseLLMNode):
    deterministic = True

    def call_model(self, full_input: str, state: GraphState):
        if self.name not in state.node_token_usage:
            state.node_token_usage[self.name] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return json.dumps(build_codegen_output(state), ensure_ascii=False, indent=2)


def write_generated_ts(state: GraphState, output: str) -> None:
    write_files_from_output(state, NODE_NAME, output)


def create_typescript_code_generator() -> BaseLLMNode:
    return DeterministicTypeScriptRuntimeTemplatePlanner(
        name=NODE_NAME,
        prompt=PROMPT,
        pre_action=build_generation_context,
        output_validator=validate_graph_node_output,
        post_action=write_generated_ts,
        enable_feedback=False,
    )
