from __future__ import annotations

import json
from pathlib import Path

from core.BaseLLMNode import BaseLLMNode, GraphState
from core.behavior_spec import write_behavior_artifacts
from core.workflow_validation import RUNTIME_MAPPING_PATH, parse_node_json, validate_graph_node_output, validate_node_output
from tools.workflow_steps.puerts_runtime_mapping import run_puerts_runtime_mapping

NODE_NAME = "PuerTSRuntimeMappingCompiler"
PROMPT = """SCHEMA: PuerTSRuntimeMappingCompiler
确定性 Python 节点。把实体/能力/行为、thin flow 和 MCP evidence 编译为 BehaviorSpec、support check 与 PuerTS runtime mapping。返回 JSON only。
"""


def _output_root(state: GraphState) -> Path:
    save_dir = getattr(state, "save_dir", "")
    if not save_dir:
        raise RuntimeError("state.save_dir is required for runtime mapping emission")
    root = Path(save_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_runtime_mapping_output(state: GraphState) -> dict:
    return run_puerts_runtime_mapping({
        "entity_behavior": state.llm_outputs.get("EntityAbilityBehaviorPlanner", ""),
        "thin_flow": state.llm_outputs.get("ThinGameplayFlowPlanner", ""),
        "ue_api_feasibility": state.llm_outputs.get("UEApiMCPFeasibilitySearcher", ""),
    }, save_dir=getattr(state, "save_dir", ""))


def build_runtime_mapping_context(node: BaseLLMNode, state: GraphState, full_input: str) -> None:
    required = {
        "EntityAbilityBehaviorPlanner": state.llm_outputs.get("EntityAbilityBehaviorPlanner", ""),
        "ThinGameplayFlowPlanner": state.llm_outputs.get("ThinGameplayFlowPlanner", ""),
        "UEApiMCPFeasibilitySearcher": state.llm_outputs.get("UEApiMCPFeasibilitySearcher", ""),
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing:
        raise RuntimeError(f"{NODE_NAME} missing upstream outputs: {missing}")
    node.full_input = "Deterministic runtime mapping compilation."


class DeterministicPuerTSRuntimeMappingCompiler(BaseLLMNode):
    deterministic = True

    def call_model(self, full_input: str, state: GraphState):
        if self.name not in state.node_token_usage:
            state.node_token_usage[self.name] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return json.dumps(build_runtime_mapping_output(state), ensure_ascii=False, indent=2)


def write_runtime_mapping(state: GraphState, output: str) -> None:
    data = parse_node_json(NODE_NAME, validate_node_output(NODE_NAME, output, validator_id="puerts_runtime_mapping_planner"))
    target = _output_root(state) / RUNTIME_MAPPING_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if isinstance(data.get("behavior_spec"), dict) and isinstance(data.get("support_check"), dict):
        write_behavior_artifacts(state.save_dir, data["behavior_spec"], data["support_check"])
    print(f"[SUCCESS] PuerTS runtime mapping saved to: {target}")


def create_puerts_runtime_mapping_planner() -> BaseLLMNode:
    return DeterministicPuerTSRuntimeMappingCompiler(
        name=NODE_NAME,
        prompt=PROMPT,
        pre_action=build_runtime_mapping_context,
        output_validator=validate_graph_node_output,
        post_action=write_runtime_mapping,
        enable_feedback=False,
    )
