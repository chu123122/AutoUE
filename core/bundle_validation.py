from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from core.bundle import NODE_OUTPUT_PORTS, RunBundle
from core.validation.common import WorkflowValidationError, is_safe_relative_path
from core.validation.workflow import validate_partial_workflow_outputs
from core.validation.registry import validate_node_output


def values_from_selector(data: dict, selector: str) -> list[str]:
    current: list[object] = [data]
    for part in selector.split('.'):
        wants_list = part.endswith('[]')
        key = part[:-2] if wants_list else part
        next_values: list[object] = []
        for value in current:
            if not isinstance(value, dict) or key not in value:
                continue
            child = value[key]
            if wants_list:
                if isinstance(child, list):
                    next_values.extend(child)
            else:
                next_values.append(child)
        current = next_values
    return [value for value in current if isinstance(value, str) and value]


def _ensure_rel_file(root: Path, rel: str, errors: list[str], label: str) -> None:
    if not isinstance(rel, str) or not is_safe_relative_path(rel):
        errors.append(f"{label} unsafe path: {rel}")
        return
    target = (root / rel.replace('\\', '/')).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        errors.append(f"{label} path outside bundle: {rel}")
        return
    if not target.exists():
        errors.append(f"{label} missing file: {rel}")


def resolve_declared_artifacts(node_spec: Mapping[str, Any], node_data: dict[str, Any]) -> list[dict[str, Any]]:
    node_name = str(node_spec.get('name', ''))
    resolved: list[dict[str, Any]] = []
    for artifact in node_spec.get('output_artifacts', []) or []:
        if not isinstance(artifact, dict):
            continue
        kind = artifact.get('kind', 'artifact')
        if kind == 'llm_output':
            resolved.append({'kind': kind, 'path': f'llm_outputs/{node_name}.txt'})
            continue
        if isinstance(artifact.get('path'), str):
            resolved.append({'kind': kind, 'path': artifact['path'].format(node=node_name)})
            continue
        if isinstance(artifact.get('path_from'), str):
            for rel in values_from_selector(node_data, artifact['path_from']):
                resolved.append({'kind': kind, 'path': rel})
    return resolved


def _requires_scene_spawn_manifest_input(bundle: RunBundle, node_name: str) -> bool:
    if node_name != "EncounterSpecPlanner":
        return True
    if not bundle.has_port("entity_behavior"):
        return True
    try:
        from custom_nodes.encounter_spec_planner import _requires_enemy_encounter
        return _requires_enemy_encounter(bundle.read_port_json("entity_behavior"))
    except Exception:
        return True


def validate_bundle_node(bundle: RunBundle, node_spec: Mapping[str, Any]) -> dict[str, Any]:
    node_name = str(node_spec.get('name'))
    input_ports = list(node_spec.get('inputs') or [])
    if "scene_spawn_manifest" in input_ports and not _requires_scene_spawn_manifest_input(bundle, node_name):
        input_ports = [port for port in input_ports if port != "scene_spawn_manifest"]
    output_ports = list(node_spec.get('outputs') or [])
    errors: list[str] = []
    for port in input_ports:
        if not bundle.has_port(port):
            errors.append(f"missing input port: {port}")
    if len(output_ports) != 1:
        errors.append(f"{node_name}: expected exactly one output port, got {output_ports}")
        output_port = ""
    else:
        output_port = output_ports[0]
        if not bundle.has_port(output_port):
            errors.append(f"missing output port: {output_port}")
    node_output = bundle.node_outputs_text().get(node_name, "")
    data: dict[str, Any] = {}
    if not node_output.strip():
        errors.append(f"missing node output: {node_name}")
    else:
        try:
            canonical = validate_node_output(node_name, node_output, validator_id=node_spec.get('validator'))
            parsed = json.loads(canonical)
            if isinstance(parsed, dict):
                data = parsed
        except Exception as exc:
            errors.append(str(exc))
    if node_output.strip():
        try:
            validate_partial_workflow_outputs(bundle.node_outputs_text())
        except Exception as exc:
            errors.append(str(exc))
    for artifact in resolve_declared_artifacts(node_spec, data):
        _ensure_rel_file(bundle.root, str(artifact.get('path', '')), errors, f"{node_name} {artifact.get('kind', 'artifact')} artifact")
    result = {'result': 'fail' if errors else 'pass', 'node': node_name, 'errors': errors, 'output_port': output_ports[:1]}
    bundle.manifest.setdefault('trace', {}).setdefault('validation', {})[node_name] = result
    bundle.write_trace_file()
    bundle.save()
    return result


def validate_bundle(bundle: RunBundle, workflow_config: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    reports = []
    by_name = {n.get('name'): n for n in workflow_config.get('nodes', []) if isinstance(n, dict) and n.get('enabled', True)}
    for node_name in NODE_OUTPUT_PORTS:
        spec = by_name.get(node_name)
        if not spec:
            continue
        report = validate_bundle_node(bundle, spec)
        reports.append(report)
        errors.extend(f"{node_name}: {e}" for e in report.get('errors', []))
    return {'result': 'fail' if errors else 'pass', 'errors': errors, 'nodes': reports, 'bundle': str(bundle.root)}
