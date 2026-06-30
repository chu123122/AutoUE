from __future__ import annotations

import json
from pathlib import Path

from core.BaseLLMNode import BaseLLMNode, GraphState
from core.workflow_validation import parse_node_json, validate_graph_node_output, validate_node_output
from tools.workflow_steps.static_evaluation_plan import run_static_evaluation_plan

NODE_NAME = "StaticEvaluationPlanBuilder"
RUNTIME_NODE = "PuerTSRuntimeMappingCompiler"
SLOT_NODE = "TypeScriptImplementationSlotProjector"
INTERACTIVE_NODE = "TypeScriptInteractiveTemplatePlanner"
CODEGEN_NODE = "TypeScriptRuntimeTemplatePlanner"
PROMPT = """SCHEMA: StaticEvaluationPlanBuilder
确定性 Python 节点。生成完整 TypeScript/PuerTS 链路的静态验证计划。返回 JSON only。
"""


def GetInput(node: BaseLLMNode, state: GraphState, full_input: str) -> str:
    required = {
        "SceneAndGameplaySplitter": state.llm_outputs.get("SceneAndGameplaySplitter", ""),
        "EntityAbilityBehaviorPlanner": state.llm_outputs.get("EntityAbilityBehaviorPlanner", ""),
        "ThinGameplayFlowPlanner": state.llm_outputs.get("ThinGameplayFlowPlanner", ""),
        "EncounterSpecPlanner": state.llm_outputs.get("EncounterSpecPlanner", ""),
        "UEApiMCPFeasibilitySearcher": state.llm_outputs.get("UEApiMCPFeasibilitySearcher", ""),
        RUNTIME_NODE: state.llm_outputs.get(RUNTIME_NODE, ""),
        SLOT_NODE: state.llm_outputs.get(SLOT_NODE, ""),
        INTERACTIVE_NODE: state.llm_outputs.get(INTERACTIVE_NODE, ""),
        CODEGEN_NODE: state.llm_outputs.get(CODEGEN_NODE, ""),
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing:
        raise RuntimeError(f"{NODE_NAME} missing upstream outputs: {missing}")
    return "Deterministic static evaluation plan build."


class DeterministicStaticEvaluationPlanBuilder(BaseLLMNode):
    deterministic = True

    def call_model(self, full_input: str, state: GraphState):
        if self.name not in state.node_token_usage:
            state.node_token_usage[self.name] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        output = run_static_evaluation_plan({
            "scene_gameplay_split": state.llm_outputs.get("SceneAndGameplaySplitter", ""),
            "entity_behavior": state.llm_outputs.get("EntityAbilityBehaviorPlanner", ""),
            "thin_flow": state.llm_outputs.get("ThinGameplayFlowPlanner", ""),
            "encounter_spec": state.llm_outputs.get("EncounterSpecPlanner", ""),
            "ue_api_feasibility": state.llm_outputs.get("UEApiMCPFeasibilitySearcher", ""),
            "runtime_mapping": state.llm_outputs.get(RUNTIME_NODE, ""),
            "ts_slots": state.llm_outputs.get(SLOT_NODE, ""),
            "interactive_ts_plan": state.llm_outputs.get(INTERACTIVE_NODE, ""),
            "typescript_codegen": state.llm_outputs.get(CODEGEN_NODE, ""),
        })
        return json.dumps(output, ensure_ascii=False, indent=2)


def SaveInstructionjson(state: GraphState, output: str) -> None:
    data = parse_node_json(NODE_NAME, validate_node_output(NODE_NAME, output, validator_id="evaluate_instruction_generator"))
    save_dir = getattr(state, "save_dir", "")
    if not save_dir:
        raise RuntimeError("state.save_dir is required for instructions.json emission")
    target_dir = Path(save_dir).resolve() / "MyPCG" / "eval"
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / "instructions.json"
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
    print(f"[SUCCESS] instructions.json saved to: {file_path}")


def create_evaluate_instruction_generator() -> BaseLLMNode:
    return DeterministicStaticEvaluationPlanBuilder(
        name=NODE_NAME,
        prompt=PROMPT,
        enable_feedback=False,
        extra_prompt_action=GetInput,
        output_validator=validate_graph_node_output,
        post_action=SaveInstructionjson,
    )

evaluate_instruction_generator = create_evaluate_instruction_generator()
