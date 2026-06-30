"""Workflow-level validation entrypoints."""

from __future__ import annotations

from typing import Any, Mapping

from core.validation.common import WORKFLOW_NODE_ORDER
from core.validation.cross_trace import validate_cross_trace
from core.validation.registry import NODE_VALIDATORS, parse_validated_node_output, validate_node_output
from core.validation.common import WorkflowValidationError


def validate_workflow_output_set(outputs: Mapping[str, str]) -> dict[str, Any]:
    missing = [name for name in WORKFLOW_NODE_ORDER if not outputs.get(name, "").strip()]
    if missing:
        raise WorkflowValidationError(f"missing workflow LLM outputs: {missing}")
    data = {name: parse_validated_node_output(name, outputs[name]) for name in WORKFLOW_NODE_ORDER}
    return {"data_by_node": data, "evidence": validate_cross_trace(data, True)}


def validate_partial_workflow_outputs(outputs: Mapping[str, str]) -> dict[str, Any]:
    data = {
        name: parse_validated_node_output(name, text)
        for name, text in outputs.items()
        if name in NODE_VALIDATORS and isinstance(text, str) and text.strip()
    }
    return {"data_by_node": data, "evidence": validate_cross_trace(data, False)}


def validate_graph_node_output(node, state, output: str) -> str:
    validator_id = getattr(node, "validator_id", None)
    canonical = validate_node_output(node.name, output, validator_id=validator_id)
    prior = dict(getattr(state, "llm_outputs", {}) or {})
    prior[node.name] = canonical
    validate_partial_workflow_outputs(prior)
    return canonical
