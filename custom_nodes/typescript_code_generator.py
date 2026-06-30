from __future__ import annotations

import json
from typing import Any, Mapping

from core.BaseLLMNode import BaseLLMNode, GraphState
from core.workflow_validation import parse_node_json, validate_graph_node_output
from custom_nodes.template_file_writer import write_files_from_output

TYPESCRIPT_CODE_GENERATOR_PROMPT = """SCHEMA: TypeScriptCodeGenerator
Deterministic Python node. Render shared behavior runtime framework templates plus BehaviorSpec.generated.ts. Never emit raw TypeScript source from LLM output.
"""

BEHAVIOR_SPEC_TS = "TypeScript/content/generated/AutoUEBehaviorSpec.generated.ts"
FRAMEWORK_TEMPLATES = [
    ("world_adapter", "TypeScript/content/generated/AutoUEWorldAdapter.ts", "createAutoUEWorldAdapter", "AutoUEWorldAdapterContext"),
    ("entity_registry", "TypeScript/content/generated/AutoUEEntityRegistry.ts", "createAutoUEEntityRegistry", "AutoUEEntityRegistryContext"),
    ("state_blackboard", "TypeScript/content/generated/AutoUEStateBlackboard.ts", "createAutoUEStateBlackboard", "AutoUEStateBlackboardContext"),
    ("trigger_router", "TypeScript/content/generated/AutoUETriggerRouter.ts", "createAutoUETriggerRouter", "AutoUETriggerRouterContext"),
    ("condition_checker", "TypeScript/content/generated/AutoUEConditionChecker.ts", "createAutoUEConditionChecker", "AutoUEConditionCheckerContext"),
    ("action_dispatcher", "TypeScript/content/generated/AutoUEActionDispatcher.ts", "createAutoUEActionDispatcher", "AutoUEActionDispatcherContext"),
    ("runtime_feature_manifest", "TypeScript/content/generated/AutoUERuntimeFeatureManifest.ts", "getAutoUERuntimeFeatureManifest", "AutoUERuntimeFeatureManifestContext"),
    ("input_harness_runtime", "TypeScript/content/generated/AutoUEInputHarnessRuntime.ts", "createAutoUEInputHarnessRuntime", "AutoUEInputHarnessRuntimeContext"),
    ("movement_runtime", "TypeScript/content/generated/AutoUEMovementRuntime.ts", "createAutoUEMovementRuntime", "AutoUEMovementRuntimeContext"),
    ("trap_runtime", "TypeScript/content/generated/AutoUETrapRuntime.ts", "createAutoUETrapRuntime", "AutoUETrapRuntimeContext"),
    ("vfx_runtime", "TypeScript/content/generated/AutoUEVfxRuntime.ts", "createAutoUEVfxRuntime", "AutoUEVfxRuntimeContext"),
    ("aid_camera_setup", "TypeScript/content/generated/AutoUEGeneratedCameraHelper.ts", "setupAutoUEGeneratedCamera", "AutoUEGeneratedCameraOptions"),
    ("scene_manifest_helper", "TypeScript/content/generated/AutoUEGeneratedSceneManifest.ts", "getAutoUEGeneratedSceneManifest", "AutoUEGeneratedSceneManifestContext"),
    ("behavior_orchestrator", "TypeScript/content/generated/AutoUEGeneratedRuntime.ts", "createAutoUEBehaviorOrchestrator", "AutoUEBehaviorOrchestratorContext"),
    ("runtime_bootstrap", "TypeScript/content/generated/AutoUERuntimeBootstrap.ts", "bootstrapAutoUEBehaviorRuntime", "AutoUERuntimeBootstrapContext"),
    ("aid_character_adapter", "TypeScript/AutoUEGeneratedCharacterAdapter.ts", "AutoUEGeneratedCharacterAdapter", "AutoUEGeneratedCharacterAdapterContext"),
    ("aid_gamemode_adapter", "TypeScript/AutoUEGeneratedGameModeAdapter.ts", "AutoUEGeneratedGameModeAdapter", "AutoUEGeneratedGameModeAdapterContext"),
]


def _first_behavior(spec: Mapping[str, Any]) -> dict[str, Any]:
    behaviors = spec.get("behaviors", []) if isinstance(spec, Mapping) else []
    if not behaviors or not isinstance(behaviors[0], Mapping):
        raise RuntimeError("TypeScriptCodeGenerator requires at least one BehaviorSpec behavior")
    return dict(behaviors[0])


def _behavior_ids(spec: Mapping[str, Any]) -> list[str]:
    return [str(item.get("behavior_id")) for item in spec.get("behaviors", []) if isinstance(item, Mapping) and item.get("behavior_id")]


def _interactive_files(interactive: Mapping[str, Any]) -> list[str]:
    files: list[str] = []
    for item in interactive.get("template_inputs", []) if isinstance(interactive, Mapping) else []:
        if isinstance(item, Mapping) and isinstance(item.get("path"), str):
            files.append(str(item["path"]))
    return files


def build_codegen_output(state: GraphState) -> dict[str, Any]:
    mapping = parse_node_json("PuerTSRuntimeMappingPlanner", state.llm_outputs.get("PuerTSRuntimeMappingPlanner", ""))
    analyzer = parse_node_json("TypeScriptScriptAnalyzer", state.llm_outputs.get("TypeScriptScriptAnalyzer", ""))
    interactive = parse_node_json("TypeScriptInteractiveObjectGenerator", state.llm_outputs.get("TypeScriptInteractiveObjectGenerator", ""))
    support = mapping.get("support_check", {})
    if support.get("status") != "supported":
        reasons = [item.get("reason", "") for item in support.get("unsupported_capabilities", []) if isinstance(item, Mapping)]
        raise RuntimeError(f"TypeScriptCodeGenerator refuses unsupported BehaviorSpec: {reasons}")
    spec = mapping.get("behavior_spec", {})
    first = _first_behavior(spec)
    runtime_features = list(mapping.get("runtime_features", []))
    disabled_features = list(mapping.get("disabled_features", []))
    base = {
        "entity_id": first.get("entity_id") or first.get("primary_entity_id"),
        "behavior_id": first.get("behavior_id"),
        "flow_id": first.get("flow_id"),
        "runtime_mapping_path": mapping.get("runtime_mapping_path"),
        "action_label": "execute BehaviorSpec action chain",
        "target_label": "BehaviorSpec",
        "result_label": "runtime framework dispatches data actions",
        "runtime_features": runtime_features,
        "disabled_features": disabled_features,
        "behavior_spec": spec,
        "support_check": support,
    }
    template_inputs = [{
        "template": "behavior_spec_generated",
        "path": BEHAVIOR_SPEC_TS,
        "export_name": "getAutoUEBehaviorSpec",
        "interface_name": "AutoUEBehaviorSpecContext",
        **base,
    }]
    for template, path, export, iface in FRAMEWORK_TEMPLATES:
        template_inputs.append({"template": template, "path": path, "export_name": export, "interface_name": iface, **base})

    rendered_paths = {item["path"] for item in template_inputs}
    for slot in analyzer.get("implementation_slots", []):
        target = slot.get("target_ts_file") if isinstance(slot, Mapping) else None
        if isinstance(target, str) and target and target not in rendered_paths:
            template_inputs.append({
                "template": "behavior_spec_generated",
                "path": target,
                "export_name": "getAutoUEBehaviorSpec",
                "interface_name": "AutoUEBehaviorSpecContext",
                **base,
            })
            rendered_paths.add(target)

    traces = []
    for behavior in spec.get("behaviors", []):
        if not isinstance(behavior, Mapping):
            continue
        traces.append({
            "entity_id": behavior.get("entity_id") or behavior.get("primary_entity_id"),
            "behavior_id": behavior.get("behavior_id"),
            "flow_id": behavior.get("flow_id"),
            "runtime_mapping_path": mapping.get("runtime_mapping_path"),
            "file_path": BEHAVIOR_SPEC_TS,
            "export_name": "getAutoUEBehaviorSpec",
        })
    return {
        "runtime_features": runtime_features,
        "disabled_features": disabled_features,
        "template_inputs": template_inputs,
        "behavior_traces": traces,
        "consumed_interactive_files": _interactive_files(interactive),
        "validation_notes": ["shared behavior runtime framework rendered", "raw TypeScript content is forbidden"],
    }


def build_generation_context(node: BaseLLMNode, state: GraphState, full_input: str) -> None:
    required = {
        "PuerTSRuntimeMappingPlanner": state.llm_outputs.get("PuerTSRuntimeMappingPlanner", ""),
        "TypeScriptScriptAnalyzer": state.llm_outputs.get("TypeScriptScriptAnalyzer", ""),
        "TypeScriptInteractiveObjectGenerator": state.llm_outputs.get("TypeScriptInteractiveObjectGenerator", ""),
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing:
        raise RuntimeError(f"TypeScriptCodeGenerator missing upstream outputs: {missing}")
    node.full_input = "Deterministic framework renderer; no gameplay-specific code generation."


class DeterministicTypeScriptCodeGenerator(BaseLLMNode):
    def call_model(self, full_input: str, state: GraphState):  # noqa: D401
        if self.name not in state.node_token_usage:
            state.node_token_usage[self.name] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return json.dumps(build_codegen_output(state), ensure_ascii=False, indent=2)


def write_generated_ts(state: GraphState, output: str) -> None:
    write_files_from_output(state, "TypeScriptCodeGenerator", output)


def create_typescript_code_generator() -> BaseLLMNode:
    return DeterministicTypeScriptCodeGenerator(
        name="TypeScriptCodeGenerator",
        prompt=TYPESCRIPT_CODE_GENERATOR_PROMPT,
        pre_action=build_generation_context,
        output_validator=validate_graph_node_output,
        post_action=write_generated_ts,
        enable_feedback=False,
    )
