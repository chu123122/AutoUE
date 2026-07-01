from __future__ import annotations

import json
from pathlib import Path

from core.BaseLLMNode import BaseLLMNode, GraphState
from core.content_library import (
    build_candidate_set,
    canonicalize_selection,
    parse_selection_output,
    render_candidate_set_prompt,
    validate_selection_against_library_and_candidates,
)
from core.scripted_enemy_cases import candidate_query_for_case
from core.workflow_validation import parse_node_json, validate_node_output

ENTITY_ABILITY_BEHAVIOR_PLANNER_PROMPT = """SCHEMA: EntityAbilityBehaviorPlanner
Select Dead Cells library IDs only. The second library is semantic Capability; selected_capability_ids is canonical and selected_ability_ids is forbidden. Python validates selected IDs and expands them into the canonical entities -> capabilities -> behaviors tree. Do not invent entity, capability, or behavior text. Return JSON only.
"""


def _output_root(state: GraphState) -> Path:
    save_dir = getattr(state, "save_dir", "")
    if not save_dir:
        raise RuntimeError("state.save_dir is required for 02 structure emission")
    root = Path(save_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_planner_context(node: BaseLLMNode, state: GraphState, full_input: str) -> None:
    candidate_query = full_input
    case = getattr(node.model, "scripted_enemy_case", "")
    if isinstance(case, str) and case:
        candidate_query += "\n" + candidate_query_for_case(case)
    candidate_set = build_candidate_set(candidate_query)
    state._eab_candidate_set = candidate_set
    node.full_input = (
        "User/scene/gameplay input:\n"
        + full_input
        + "\n\nTask: choose only the relevant Dead Cells library IDs for this request. "
        "The LLM output is an ID selection, not the final entity tree. "
        "Python will expand selected IDs into entities[] -> capabilities[] -> behaviors[] for downstream nodes.\n\n"
        "Output JSON shape exactly:\n"
        "{\n"
        "  \"selected_entity_ids\": [\"optional entity ids that must appear even without selected behaviors\"],\n"
        "  \"selected_capability_ids\": [\"optional capability ids; selecting one expands all its child behaviors\"],\n"
        "  \"selected_behavior_ids\": [\"behavior ids relevant to the user request\"]\n"
        "}\n\n"
        "Rules:\n"
        "- Select IDs only from the candidate set below.\n"
        "- Do not output entity/capability/behavior objects, summaries, trigger/execution/result text, engine_ports, files, templates, runtime owners, or code fields.\n"
        "- Include HUD, particles, VFX, traps, status, camera, pickups, exit, enemies, and gameplay objects only when relevant.\n"
        "- Audio/SFX is intentionally excluded.\n\n"
        "Candidate Dead Cells library subset:\n"
        + render_candidate_set_prompt(candidate_set)
    )


def validate_selection_and_expand_output(node: BaseLLMNode, state: GraphState, output: str) -> str:
    raw = parse_node_json("EntityAbilityBehaviorPlanner", output)
    selection = parse_selection_output("EntityAbilityBehaviorPlanner", raw)
    candidate_set = getattr(state, "_eab_candidate_set", None)
    if not isinstance(candidate_set, dict):
        candidate_set = build_candidate_set(getattr(node, "full_input", ""))
    validate_selection_against_library_and_candidates("EntityAbilityBehaviorPlanner", selection, candidate_set)
    canonical = canonicalize_selection(selection)
    canonical_text = json.dumps(canonical, ensure_ascii=False, indent=2)
    validated = validate_node_output("EntityAbilityBehaviorPlanner", canonical_text)
    state._eab_selection = selection
    state._eab_candidate_set = candidate_set
    return validated


def _canonical_selection_view(selection: dict) -> dict:
    return {
        "selected_entity_ids": selection.get("selected_entity_ids", []),
        "selected_capability_ids": selection.get("selected_capability_ids", []),
        "selected_behavior_ids": selection.get("selected_behavior_ids", []),
    }


def write_02_structure(state: GraphState, output: str) -> None:
    data = parse_node_json("EntityAbilityBehaviorPlanner", validate_node_output("EntityAbilityBehaviorPlanner", output))
    root = _output_root(state)
    flow_dir = root / "flow"
    flow_dir.mkdir(parents=True, exist_ok=True)
    selection = getattr(state, "_eab_selection", None)
    candidate_set = getattr(state, "_eab_candidate_set", None)
    if isinstance(candidate_set, dict):
        (flow_dir / "02-entity-behavior-candidates.json").write_text(json.dumps(candidate_set, ensure_ascii=False, indent=2), encoding="utf-8")
    selection_view = _canonical_selection_view(selection) if isinstance(selection, dict) else None
    if isinstance(selection_view, dict):
        (flow_dir / "02-entity-behavior-selection.json").write_text(json.dumps(selection_view, ensure_ascii=False, indent=2), encoding="utf-8")
    structure = {
        "schema_version": "autoue-02-structure/v1",
        "analysis_order": "library candidate retrieval -> ID selection -> Python canonical expansion",
        "machine_tree": "entities -> capabilities -> behaviors",
        "entities": data.get("entities", []),
        "non_goals": data.get("non_goals", []),
    }
    (flow_dir / "02-structure.json").write_text(json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 02 结构化拆解：死亡细胞库 ID 选择 → 行为-能力-实体", "", "流程：检索候选库项 → LLM 只选择 ID → Python 从三库展开 canonical tree。", ""]
    if isinstance(selection_view, dict):
        lines.extend(["## LLM 原始 ID 选择", "", "```json", json.dumps(selection_view, ensure_ascii=False, indent=2), "```", ""])
    for entity in data.get("entities", []):
        lines.append(f"## Entity: `{entity.get('entity_id','')}` · {entity.get('display_name_zh') or entity.get('display_name','')}")
        lines.append(entity.get("summary_zh") or entity.get("summary", ""))
        lines.append("")
        for capability in entity.get("capabilities", []):
            lines.append(f"### Capability: `{capability.get('capability_id','')}` · {capability.get('display_name_zh') or capability.get('display_name','')}")
            lines.append(capability.get("summary_zh") or capability.get("summary", ""))
            for behavior in capability.get("behaviors", []):
                lines.append(f"- Behavior `{behavior.get('behavior_id','')}` · {behavior.get('display_name_zh') or behavior.get('display_name','')}: {behavior.get('trigger','')} → {behavior.get('execution','')} → {behavior.get('result','')}")
            lines.append("")
    (flow_dir / "02-结构化拆解-行为能力实体.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"[SUCCESS] 02 structure saved under: {flow_dir}")


def create_entity_ability_behavior_planner() -> BaseLLMNode:
    return BaseLLMNode(
        name="EntityAbilityBehaviorPlanner",
        prompt=ENTITY_ABILITY_BEHAVIOR_PLANNER_PROMPT,
        pre_action=build_planner_context,
        output_validator=validate_selection_and_expand_output,
        post_action=write_02_structure,
        enable_feedback=False,
    )
