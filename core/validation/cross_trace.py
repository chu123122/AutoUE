"""Cross-node workflow trace validation."""

from __future__ import annotations

from typing import Any, Mapping

from core.encounter_validation import EncounterValidationError, validate_encounter_spec_data
from core.validation.common import RUNTIME_MAPPING_PATH, WorkflowValidationError

def collect_behavior_index(planner: dict[str, Any]) -> dict[str, dict[str, str]]:
    out = {}
    for entity in planner.get("entities", []):
        for ability in entity.get("abilities", []):
            for behavior in ability.get("behaviors", []):
                behavior_id = behavior.get("behavior_id", "")
                if behavior_id:
                    out[behavior_id] = {"entity_id": entity.get("entity_id", ""), "ability_id": ability.get("ability_id", ""), "behavior_id": behavior_id}
    return out

def _known(node: str, index: Mapping[str, Mapping[str, str]], behavior_id: str, *, entity_id: str | None = None, ability_id: str | None = None) -> None:
    if behavior_id not in index:
        raise WorkflowValidationError(f"{node}: references unknown behavior_id: {behavior_id}")
    expected = index[behavior_id]
    if entity_id is not None and entity_id != expected.get("entity_id"):
        raise WorkflowValidationError(f"{node}: behavior {behavior_id} belongs to entity {expected.get('entity_id')}, got {entity_id}")
    if ability_id is not None and ability_id != expected.get("ability_id"):
        raise WorkflowValidationError(f"{node}: behavior {behavior_id} belongs to ability {expected.get('ability_id')}, got {ability_id}")

def _generated(data: Mapping[str, Any]) -> set[str]:
    return {item.get("path", "") for item in data.get("template_inputs", []) if isinstance(item, dict)}

def _flow_indexes(thin: Mapping[str, Any], behavior_index: Mapping[str, Mapping[str, str]], coverage: dict[str, set[str]]):
    flow_by_behavior, flow_by_id, ports_by_flow, behavior_by_port = {}, {}, {}, {}
    for flow in thin.get("flows", []):
        behavior_id = flow.get("source_behavior_id", "")
        _known("ThinGameplayFlowPlanner", behavior_index, behavior_id, entity_id=flow.get("entity_id", ""), ability_id=flow.get("ability_id", ""))
        flow_id = flow.get("flow_id", "")
        if behavior_id in flow_by_behavior:
            raise WorkflowValidationError(f"ThinGameplayFlowPlanner: duplicate flow for behavior_id: {behavior_id}")
        flow_by_behavior[behavior_id] = flow
        flow_by_id[flow_id] = flow
        coverage.setdefault(behavior_id, set()).add("ThinGameplayFlowPlanner")
        ports = set()
        for stage in flow.get("stages", []):
            for port in stage.get("engine_ports", []):
                ports.add(port)
                behavior_by_port.setdefault(port, set()).add(behavior_id)
        ports_by_flow[flow_id] = ports
    missing = sorted(set(behavior_index) - set(flow_by_behavior))
    if missing:
        raise WorkflowValidationError(f"ThinGameplayFlowPlanner: missing flow for behavior_id: {missing}")
    return flow_by_behavior, flow_by_id, ports_by_flow, behavior_by_port

def validate_cross_trace(data: Mapping[str, dict[str, Any]], require_all: bool) -> dict[str, Any]:
    behavior_index = collect_behavior_index(data.get("EntityAbilityBehaviorPlanner", {}))
    coverage = {behavior_id: set() for behavior_id in behavior_index}
    flow_by_behavior, flow_by_id, ports_by_flow, behavior_by_port = {}, {}, {}, {}
    if data.get("ThinGameplayFlowPlanner") and behavior_index:
        flow_by_behavior, flow_by_id, ports_by_flow, behavior_by_port = _flow_indexes(data["ThinGameplayFlowPlanner"], behavior_index, coverage)

    encounter_ids: list[str] = []
    if data.get("EncounterSpecPlanner"):
        try:
            validate_encounter_spec_data(data["EncounterSpecPlanner"], structure=data.get("EntityAbilityBehaviorPlanner"))
        except EncounterValidationError as exc:
            raise WorkflowValidationError(str(exc)) from exc
        encounter_ids = [item.get("encounter_id", "") for item in data["EncounterSpecPlanner"].get("encounters", []) if isinstance(item, dict)]

    mcp_by_port, adjudication_by_path = {}, {}
    if data.get("UEApiMCPFeasibilitySearcher"):
        for query in data["UEApiMCPFeasibilitySearcher"].get("queries", []):
            port = query.get("engine_port_id", "")
            if port in mcp_by_port:
                raise WorkflowValidationError(f"UEApiMCPFeasibilitySearcher: duplicate engine_port_id query: {port}")
            if query.get("verdict") != "hit":
                raise WorkflowValidationError(f"UEApiMCPFeasibilitySearcher: engine_port_id must be hit for workflow completion: {port}")
            mcp_by_port[port] = query
            adjudication_by_path[query.get("adjudication_path", "")] = query
            for behavior_id in query.get("behavior_ids", []):
                _known("UEApiMCPFeasibilitySearcher", behavior_index, behavior_id)
                coverage.setdefault(behavior_id, set()).add("UEApiMCPFeasibilitySearcher")
            expected = behavior_by_port.get(port, set())
            if expected and not expected.issubset(set(query.get("behavior_ids", []))):
                raise WorkflowValidationError(f"UEApiMCPFeasibilitySearcher: query {port} missing behavior references: {sorted(expected)}")
        if ports_by_flow:
            expected_ports = set().union(*ports_by_flow.values()) if ports_by_flow else set()
            missing = sorted(expected_ports - set(mcp_by_port))
            if missing:
                raise WorkflowValidationError(f"UEApiMCPFeasibilitySearcher: missing MCP query for engine_port_id: {missing}")

    mapping_by_behavior, runtime_mapping_path = {}, ""
    if data.get("PuerTSRuntimeMappingPlanner"):
        mapping_node = data["PuerTSRuntimeMappingPlanner"]
        runtime_mapping_path = mapping_node.get("runtime_mapping_path", "")
        if runtime_mapping_path != RUNTIME_MAPPING_PATH:
            raise WorkflowValidationError(f"PuerTSRuntimeMappingPlanner: runtime_mapping_path must be {RUNTIME_MAPPING_PATH}, got {runtime_mapping_path}")
        if mapping_node.get("blocked_mappings"):
            raise WorkflowValidationError("PuerTSRuntimeMappingPlanner: blocked_mappings must be empty for workflow completion")
        for mapping in mapping_node.get("mappings", []):
            behavior_id = mapping.get("behavior_id", "")
            _known("PuerTSRuntimeMappingPlanner", behavior_index, behavior_id, entity_id=mapping.get("entity_id", ""), ability_id=mapping.get("ability_id", ""))
            if mapping.get("implementation_carrier") == "blocked":
                raise WorkflowValidationError(f"PuerTSRuntimeMappingPlanner: mapping is blocked for behavior_id: {behavior_id}")
            if behavior_id in mapping_by_behavior:
                raise WorkflowValidationError(f"PuerTSRuntimeMappingPlanner: duplicate mapping for behavior_id: {behavior_id}")
            expected_flow = flow_by_behavior.get(behavior_id, {}).get("flow_id")
            if expected_flow and mapping.get("flow_id") != expected_flow:
                raise WorkflowValidationError(f"PuerTSRuntimeMappingPlanner: behavior {behavior_id} must map to its thin flow")
            mapping_by_behavior[behavior_id] = mapping
            coverage.setdefault(behavior_id, set()).add("PuerTSRuntimeMappingPlanner")
            mapped_ports = {p.get("engine_port_id", "") for p in mapping.get("engine_port_mappings", [])}
            missing_ports = sorted(ports_by_flow.get(mapping.get("flow_id", ""), set()) - mapped_ports)
            if missing_ports:
                raise WorkflowValidationError(f"PuerTSRuntimeMappingPlanner: behavior {behavior_id} missing runtime mappings for engine ports: {missing_ports}")
            for port in mapping.get("engine_port_mappings", []):
                if mcp_by_port and port.get("engine_port_id") not in mcp_by_port:
                    raise WorkflowValidationError(f"PuerTSRuntimeMappingPlanner: references engine_port without MCP query: {port.get('engine_port_id', '')}")
                if adjudication_by_path and port.get("adjudication_path") not in adjudication_by_path:
                    raise WorkflowValidationError(f"PuerTSRuntimeMappingPlanner: references unknown adjudication_path: {port.get('adjudication_path', '')}")
                if port.get("verdict") != "hit":
                    raise WorkflowValidationError(f"PuerTSRuntimeMappingPlanner: engine_port_mappings must be hit: {behavior_id}")
        missing = sorted(set(behavior_index) - set(mapping_by_behavior))
        if missing:
            raise WorkflowValidationError(f"PuerTSRuntimeMappingPlanner: missing mapping for behavior_id: {missing}")

    analyzer_targets, interactive_files, codegen_files = set(), set(), set()
    if data.get("TypeScriptScriptAnalyzer"):
        analyzer = data["TypeScriptScriptAnalyzer"]
        if analyzer.get("missing_slots"):
            raise WorkflowValidationError("TypeScriptScriptAnalyzer: missing_slots must be empty for workflow completion")
        for slot in analyzer.get("implementation_slots", []):
            behavior_id = slot.get("behavior_id", "")
            _known("TypeScriptScriptAnalyzer", behavior_index, behavior_id, entity_id=slot.get("entity_id", ""))
            mapped = mapping_by_behavior.get(behavior_id)
            if mapped:
                if slot.get("flow_id") != mapped.get("flow_id"):
                    raise WorkflowValidationError(f"TypeScriptScriptAnalyzer: slot flow_id must come from runtime mapping: {behavior_id}")
                if slot.get("runtime_mapping_path") != runtime_mapping_path:
                    raise WorkflowValidationError(f"TypeScriptScriptAnalyzer: slot runtime_mapping_path must be {runtime_mapping_path}")
                if slot.get("target_ts_file") != mapped.get("runtime_owner"):
                    raise WorkflowValidationError(f"TypeScriptScriptAnalyzer: target_ts_file must equal runtime_owner for behavior_id: {behavior_id}")
            analyzer_targets.add(slot.get("target_ts_file", ""))
            coverage.setdefault(behavior_id, set()).add("TypeScriptScriptAnalyzer")

    if data.get("TypeScriptInteractiveObjectGenerator"):
        interactive = data["TypeScriptInteractiveObjectGenerator"]
        interactive_files = _generated(interactive)
        for trace in interactive.get("behavior_traces", []):
            behavior_id = trace.get("behavior_id", "")
            _known("TypeScriptInteractiveObjectGenerator", behavior_index, behavior_id, entity_id=trace.get("entity_id", ""))
            mapped = mapping_by_behavior.get(behavior_id)
            if mapped and (trace.get("flow_id") != mapped.get("flow_id") or trace.get("runtime_mapping_path") != runtime_mapping_path):
                raise WorkflowValidationError(f"TypeScriptInteractiveObjectGenerator: trace must come from runtime mapping: {behavior_id}")
            coverage.setdefault(behavior_id, set()).add("TypeScriptInteractiveObjectGenerator")

    if data.get("TypeScriptCodeGenerator"):
        code = data["TypeScriptCodeGenerator"]
        codegen_files = _generated(code)
        consumed = set(code.get("consumed_interactive_files", []))
        if interactive_files and not consumed.issubset(interactive_files):
            raise WorkflowValidationError("TypeScriptCodeGenerator: consumed_interactive_files must reference TypeScriptInteractiveObjectGenerator files")
        missing_targets = sorted(analyzer_targets - codegen_files)
        if analyzer_targets and missing_targets:
            raise WorkflowValidationError(f"TypeScriptCodeGenerator: must render every analyzer implementation target: {missing_targets}")
        for trace in code.get("behavior_traces", []):
            behavior_id = trace.get("behavior_id", "")
            _known("TypeScriptCodeGenerator", behavior_index, behavior_id, entity_id=trace.get("entity_id", ""))
            mapped = mapping_by_behavior.get(behavior_id)
            if mapped and (trace.get("flow_id") != mapped.get("flow_id") or trace.get("runtime_mapping_path") != runtime_mapping_path):
                raise WorkflowValidationError(f"TypeScriptCodeGenerator: trace must come from runtime mapping: {behavior_id}")
            coverage.setdefault(behavior_id, set()).add("TypeScriptCodeGenerator")

    if data.get("EvaluateInstructionGenerator"):
        rendered = interactive_files | codegen_files
        for item in list(data["EvaluateInstructionGenerator"].get("evaluation_instructions", [])) + list(data["EvaluateInstructionGenerator"].get("coverage", [])):
            trace = item.get("trace") if isinstance(item, dict) and "trace" in item else item
            if not isinstance(trace, dict):
                continue
            behavior_id = trace.get("behavior_id", "")
            _known("EvaluateInstructionGenerator", behavior_index, behavior_id, entity_id=trace.get("entity_id", ""), ability_id=trace.get("ability_id", ""))
            mapped = mapping_by_behavior.get(behavior_id)
            if mapped:
                if trace.get("flow_id") != mapped.get("flow_id") or trace.get("runtime_mapping_path") != runtime_mapping_path:
                    raise WorkflowValidationError(f"EvaluateInstructionGenerator: trace must come from runtime mapping: {behavior_id}")
                expected_ports = {p.get("engine_port_id", "") for p in mapped.get("engine_port_mappings", [])}
                if not expected_ports.issubset(set(trace.get("engine_port_ids", []))):
                    raise WorkflowValidationError(f"EvaluateInstructionGenerator: trace missing engine_port_ids for {behavior_id}: {sorted(expected_ports - set(trace.get('engine_port_ids', [])))}")
                expected_adj = {p.get("adjudication_path", "") for p in mapped.get("engine_port_mappings", [])}
                if not expected_adj.issubset(set(trace.get("adjudication_paths", []))):
                    raise WorkflowValidationError(f"EvaluateInstructionGenerator: trace missing adjudication_paths for {behavior_id}: {sorted(expected_adj - set(trace.get('adjudication_paths', [])))}")
            missing_files = [p for p in trace.get("ts_files", []) if rendered and p not in rendered]
            if missing_files:
                raise WorkflowValidationError(f"EvaluateInstructionGenerator: ts_files were not rendered by TypeScriptInteractiveObjectGenerator or TypeScriptCodeGenerator: {missing_files}")
            coverage.setdefault(behavior_id, set()).add("EvaluateInstructionGenerator")

    evidence = {
        "behavior_ids": sorted(behavior_index),
        "flow_ids": sorted(flow_by_id),
        "encounter_ids": sorted(encounter_ids),
        "engine_port_ids": sorted(mcp_by_port or behavior_by_port),
        "mcp_adjudication_paths": sorted(adjudication_by_path),
        "runtime_mapping_path": runtime_mapping_path,
        "analyzer_targets": sorted(analyzer_targets),
        "interactive_files": sorted(interactive_files),
        "codegen_files": sorted(codegen_files),
    }
    if require_all and behavior_index:
        required = {"ThinGameplayFlowPlanner", "UEApiMCPFeasibilitySearcher", "PuerTSRuntimeMappingPlanner", "TypeScriptScriptAnalyzer", "TypeScriptInteractiveObjectGenerator", "TypeScriptCodeGenerator", "EvaluateInstructionGenerator"}
        missing = {bid: sorted(required - srcs) for bid, srcs in coverage.items() if required - srcs}
        if missing:
            raise WorkflowValidationError(f"workflow trace coverage missing for behavior_id: {missing}")
        evidence["behavior_trace_coverage"] = {bid: sorted(srcs) for bid, srcs in sorted(coverage.items())}
    return evidence
