from __future__ import annotations

import json
from pathlib import Path

from core.BaseLLMNode import BaseLLMNode, GraphState
from core.encounter_validation import (
    ENCOUNTER_SPEC_MD_PATH,
    ENCOUNTER_SPEC_PATH,
    SCENE_SPAWN_MANIFEST_PATH,
    STRUCTURE_PATH,
    EncounterValidationError,
    load_json_file,
    render_encounter_spec_markdown,
    validate_encounter_spec_data,
    validate_scene_spawn_manifest_data,
)
from core.workflow_validation import parse_node_json, validate_graph_node_output, validate_node_output

ENCOUNTER_SPEC_PLANNER_PROMPT = """SCHEMA: EncounterSpecPlanner
Generate EncounterSpec data from structure, thin gameplay flow, and scene spawn manifest. Return JSON only.
"""


def _output_root(state: GraphState) -> Path:
    save_dir = getattr(state, "save_dir", "")
    if not save_dir:
        raise RuntimeError("state.save_dir is required for EncounterSpecPlanner emission")
    root = Path(save_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _load_manifest(root: Path) -> dict:
    manifest_path = root / SCENE_SPAWN_MANIFEST_PATH
    if not manifest_path.exists():
        raise RuntimeError(
            f"EncounterSpecPlanner requires enemy spawn data, but missing deterministic scene spawn manifest: {manifest_path}. "
            "Run tools/unreal/export_scene_spawn_manifest.py against the target UE map, or configure "
            "runtime_config.scene_spawn_manifest.fixture_path with a checked-in fixture. "
            "Do not fabricate spawn_group data and do not silently emit an empty encounter."
        )
    manifest = load_json_file(manifest_path)
    validate_scene_spawn_manifest_data(manifest)
    return manifest


def _requires_enemy_encounter(structure: dict) -> bool:
    for entity in structure.get("entities", []):
        if entity.get("spawnable") is True:
            return True
        for ability in entity.get("abilities", []):
            for behavior in ability.get("behaviors", []):
                if "enemy_encounter" in behavior.get("runtime_features", []):
                    return True
    return False


def build_encounter_context(node: BaseLLMNode, state: GraphState, full_input: str) -> None:
    required = {
        "EntityAbilityBehaviorPlanner": state.llm_outputs.get("EntityAbilityBehaviorPlanner", ""),
        "ThinGameplayFlowPlanner": state.llm_outputs.get("ThinGameplayFlowPlanner", ""),
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing:
        raise RuntimeError(f"EncounterSpecPlanner missing upstream outputs: {missing}")
    root = _output_root(state)
    structure = parse_node_json("EntityAbilityBehaviorPlanner", required["EntityAbilityBehaviorPlanner"])
    thin = parse_node_json("ThinGameplayFlowPlanner", required["ThinGameplayFlowPlanner"])
    structure_path = root / STRUCTURE_PATH
    structure_path.parent.mkdir(parents=True, exist_ok=True)
    structure_path.write_text(json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8")
    if not _requires_enemy_encounter(structure):
        state._autoue_enemy_encounter_enabled = False
        node.full_input = (
            f"Scene Description:\n{getattr(state, 'scene_description', '')}\n\n"
            f"Gameplay Description:\n{getattr(state, 'gameplay_description', '')}\n\n"
            "EntityAbilityBehaviorPlanner JSON:\n" + json.dumps(structure, ensure_ascii=False, indent=2) + "\n\n"
            "ThinGameplayFlowPlanner JSON:\n" + json.dumps(thin, ensure_ascii=False, indent=2) + "\n\n"
            "No selected behavior requires runtime feature enemy_encounter. Return EncounterSpec JSON with an empty encounters array."
        )
        return
    state._autoue_enemy_encounter_enabled = True
    manifest = _load_manifest(root)
    node.full_input = (
        f"Scene Description:\n{getattr(state, 'scene_description', '')}\n\n"
        f"Gameplay Description:\n{getattr(state, 'gameplay_description', '')}\n\n"
        "EntityAbilityBehaviorPlanner JSON:\n" + json.dumps(structure, ensure_ascii=False, indent=2) + "\n\n"
        "ThinGameplayFlowPlanner JSON:\n" + json.dumps(thin, ensure_ascii=False, indent=2) + "\n\n"
        "scene-spawn-manifest.json:\n" + json.dumps(manifest, ensure_ascii=False, indent=2) + "\n\n"
        "Generate EncounterSpec JSON only. Use no coordinates and only known spawn_group/enemy ids."
    )


def validate_encounter_output(node: BaseLLMNode, state: GraphState, output: str) -> str:
    canonical = validate_graph_node_output(node, state, output)
    data = parse_node_json("EncounterSpecPlanner", canonical)
    root = _output_root(state)
    structure = parse_node_json("EntityAbilityBehaviorPlanner", state.llm_outputs.get("EntityAbilityBehaviorPlanner", ""))
    manifest = _load_manifest(root) if _requires_enemy_encounter(structure) else None
    try:
        validate_encounter_spec_data(data, structure=structure, manifest=manifest)
    except EncounterValidationError as exc:
        raise RuntimeError(str(exc)) from exc
    return json.dumps(data, ensure_ascii=False, indent=2)


def write_encounter_spec(state: GraphState, output: str) -> None:
    data = parse_node_json("EncounterSpecPlanner", validate_node_output("EncounterSpecPlanner", output))
    root = _output_root(state)
    json_path = root / ENCOUNTER_SPEC_PATH
    md_path = root / ENCOUNTER_SPEC_MD_PATH
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_encounter_spec_markdown(data), encoding="utf-8")
    print(f"[SUCCESS] EncounterSpec saved to: {json_path}")


def create_encounter_spec_planner() -> BaseLLMNode:
    return BaseLLMNode(
        name="EncounterSpecPlanner",
        prompt=ENCOUNTER_SPEC_PLANNER_PROMPT,
        pre_action=build_encounter_context,
        output_validator=validate_encounter_output,
        post_action=write_encounter_spec,
        enable_feedback=False,
    )
