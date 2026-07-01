from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from core.bundle import RunBundle
from core.bundle_runner import build_bundle_nodes, execute_node
from core.config import load_runtime_config, load_workflow_config

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MAPPING_PATH = 'flow/05-puerts-runtime-mapping.json'
ADJ_INPUT = 'flow/04-ue-api-mcp/adjudication/input.action_binding.json'
ADJ_OVERLAP = 'flow/04-ue-api-mcp/adjudication/primitive.on_component_begin_overlap.json'
ADJ_VISIBILITY = 'flow/04-ue-api-mcp/adjudication/component.set_visibility.json'
ADJ_CAMERA = 'flow/04-ue-api-mcp/adjudication/camera.update_view_target.json'



RUNTIME_FEATURES = ['action_dispatcher', 'behavior_orchestrator', 'condition_checker', 'entity_registry', 'movement_runtime', 'state_blackboard', 'trigger_router', 'world_adapter']
DISABLED_FEATURES = ['enemy_encounter']
BEHAVIOR_ID = 'hazard.behavior.freeze_on_overlap'
CAPABILITY_IDS = ['hazard.sensor.detect_overlap', 'hazard.effect.apply_freeze', 'vfx.visibility.set_visible_while_state', 'camera.feedback.camera_impulse']
FLOW_ID = 'flow_hazard_behavior_freeze_on_overlap'
RUNTIME_OWNER = 'TypeScript/content/generated/AutoUEBehaviorSpec.generated.ts'
INTERACTIVE_TS = 'TypeScript/content/generated/interactive/FreezeTrapInteractable.ts'
ENGINE_PORTS = ['input.action_binding', 'primitive.on_component_begin_overlap', 'component.set_visibility', 'camera.update_view_target']
ADJUDICATIONS = [ADJ_INPUT, ADJ_OVERLAP, ADJ_VISIBILITY, ADJ_CAMERA]

def eab():
    from core.content_library import canonicalize_selection
    return canonicalize_selection({'selected_entity_ids': ['freeze_trap', 'freeze_vfx', 'side_camera'], 'selected_capability_ids': CAPABILITY_IDS, 'selected_behavior_ids': [BEHAVIOR_ID]})

def thin():
    return {'flows': [{'flow_id': FLOW_ID, 'entity_id': 'freeze_trap', 'source_behavior_id': BEHAVIOR_ID, 'stages': [
        {'stage': 'Input', 'contract': 'read input', 'inputs': ['input'], 'outputs': ['intent'], 'engine_ports': ['input.action_binding']},
        {'stage': 'SpatialQuery/HitQuery', 'contract': 'detect trap overlap', 'inputs': ['location'], 'outputs': ['trigger'], 'engine_ports': ['primitive.on_component_begin_overlap']},
        {'stage': 'Event/Result', 'contract': 'write player.effects.frozen', 'inputs': ['trigger'], 'outputs': ['frozen'], 'engine_ports': ['primitive.on_component_begin_overlap']},
        {'stage': 'Feedback/HUD', 'contract': 'show vfx and shake camera', 'inputs': ['frozen'], 'outputs': ['feedback'], 'engine_ports': ['component.set_visibility', 'camera.update_view_target']},
    ], 'verification': ['player.effects.frozen written', 'enemy encounter disabled']}]} 

def encounter():
    return {'schema_version': 'autoue-encounter-spec/v1', 'encounters': []}

def mcp():
    rows = [
        ('input.action_binding', ADJ_INPUT, 'UE.PlayerController.IsInputKeyDown'),
        ('primitive.on_component_begin_overlap', ADJ_OVERLAP, 'UE.PrimitiveComponent.OnComponentBeginOverlap'),
        ('component.set_visibility', ADJ_VISIBILITY, 'UE.SceneComponent.SetVisibility'),
        ('camera.update_view_target', ADJ_CAMERA, 'UE.CameraComponent.K2_SetWorldLocation'),
    ]
    return {'queries': [{'engine_port_id': port, 'flow_ids': [FLOW_ID], 'behavior_ids': [BEHAVIOR_ID], 'query': port, 'raw_path': 'flow/04-ue-api-mcp/raw/' + port + '.raw.json', 'adjudication_path': adj, 'verdict': 'hit', 'hit_type': 'direct_hit', 'evidence_symbols': [sym], 'notes': 'ok'} for port, adj, sym in rows], 'summary': {'all_required_ports_hit': True, 'blocked_engine_ports': []}}

def behavior_spec_and_support():
    from core.behavior_spec import compile_and_check
    spec, support = compile_and_check(eab(), thin())
    assert support['status'] == 'supported'
    return spec, support

def mapping():
    spec, support = behavior_spec_and_support()
    helpers = {'input.action_binding': 'TriggerRouter.bindInputAction', 'primitive.on_component_begin_overlap': 'TriggerRouter.bindOverlapEnter', 'component.set_visibility': 'WorldAdapter.setVisibility', 'camera.update_view_target': 'WorldAdapter.cameraImpulse'}
    syms = {'input.action_binding': 'UE.PlayerController.IsInputKeyDown', 'primitive.on_component_begin_overlap': 'UE.PrimitiveComponent.OnComponentBeginOverlap', 'component.set_visibility': 'UE.SceneComponent.SetVisibility', 'camera.update_view_target': 'UE.CameraComponent.K2_SetWorldLocation'}
    return {'runtime_mapping_path': RUNTIME_MAPPING_PATH, 'behavior_spec_path': 'flow/06-behavior-spec.json', 'support_check_path': 'flow/06-runtime-support-check.json', 'encounter_spec_path': 'flow/03-encounter-spec.json', 'scene_spawn_manifest_path': 'flow/scene-spawn-manifest.json', 'runtime_features': RUNTIME_FEATURES, 'disabled_features': DISABLED_FEATURES, 'behavior_spec': spec, 'encounter_spec': encounter(), 'support_check': support, 'mappings': [{'entity_id': 'freeze_trap', 'behavior_id': BEHAVIOR_ID, 'flow_id': FLOW_ID, 'runtime_owner': RUNTIME_OWNER, 'implementation_carrier': 'template_rendered_ts', 'selected_runtime_owner': 'AutoUEBehaviorSpec.generated', 'existing_framework_candidates': ['AutoUE behavior runtime framework'], 'why_not_existing_framework': 'shared behavior framework renders BehaviorSpec instead of gameplay-specific TS', 'temporary_or_canonical': 'canonical', 'migration_path': 'regenerate BehaviorSpec data only', 'engine_port_mappings': [{'engine_port_id': p, 'adjudication_path': a, 'adapter_or_helper': helpers[p], 'verdict': 'hit', 'evidence_symbols': [syms[p]]} for p, a in zip(ENGINE_PORTS, ADJUDICATIONS)], 'thin_contracts': ['read input', 'detect overlap', 'write player.effects.frozen', 'show vfx', 'shake camera'], 'ability_binding': 'behavior_spec:hazard.behavior.freeze_on_overlap', 'verification_evidence': ['StateWritten player.effects.frozen']}], 'blocked_mappings': []}

def analyzer():
    return {'typescript_sources': [{'path': RUNTIME_OWNER, 'role': 'runtime_owner', 'notes': 'mapping'}], 'implementation_slots': [{'entity_id': 'freeze_trap', 'behavior_id': BEHAVIOR_ID, 'flow_id': FLOW_ID, 'runtime_mapping_path': RUNTIME_MAPPING_PATH, 'target_ts_file': RUNTIME_OWNER, 'reason': 'mapping'}], 'missing_slots': []}

def interactive():
    return {'template_inputs': [{'template': 'interactive_object', 'path': INTERACTIVE_TS, 'entity_id': 'freeze_trap', 'behavior_id': BEHAVIOR_ID, 'flow_id': FLOW_ID, 'runtime_mapping_path': RUNTIME_MAPPING_PATH, 'export_name': 'runFreezeTrapInteraction', 'interface_name': 'FreezeTrapInteractionContext', 'action_label': 'overlap triggers freeze', 'target_label': 'Player', 'result_label': 'player frozen with VFX and camera shake'}], 'behavior_traces': [{'entity_id': 'freeze_trap', 'behavior_id': BEHAVIOR_ID, 'flow_id': FLOW_ID, 'runtime_mapping_path': RUNTIME_MAPPING_PATH, 'file_path': INTERACTIVE_TS, 'export_name': 'runFreezeTrapInteraction'}], 'validation_notes': []}

def codegen():
    from core.BaseLLMNode import GraphState
    from custom_nodes.typescript_code_generator import build_codegen_output
    state = GraphState(llm_outputs={
        'PuerTSRuntimeMappingCompiler': json.dumps(mapping()),
        'TypeScriptImplementationSlotProjector': json.dumps(analyzer()),
        'EncounterSpecPlanner': json.dumps(encounter()),
        'TypeScriptInteractiveTemplatePlanner': json.dumps(interactive()),
    })
    return build_codegen_output(state)

def eval_plan():
    trace = {'entity_id': 'freeze_trap', 'behavior_id': BEHAVIOR_ID, 'flow_id': FLOW_ID, 'engine_port_ids': ENGINE_PORTS, 'adjudication_paths': ADJUDICATIONS, 'runtime_mapping_path': RUNTIME_MAPPING_PATH, 'ts_files': [INTERACTIVE_TS, RUNTIME_OWNER]}
    return {'evaluation_instructions': [{'step_id': 1, 'action': 'trigger_freeze_trap', 'target': 'FreezeTrap', 'description': 'validate static adapter call trace', 'driver': 'adapter_call', 'executor_action': 'call_behavior', 'expected': [{'type': 'static_trace_present', 'key': 'ability_module_export', 'expected_value': 'getAutoUEBehaviorSpec'}, {'type': 'static_trace_present', 'key': 'interactive_adapter_export', 'expected_value': 'runFreezeTrapInteraction'}, {'type': 'static_trace_present', 'key': 'engine_ports_mapped', 'expected_value': ENGINE_PORTS}], 'trace': trace}], 'coverage': [trace]}


def load_node(name: str, llm_profile='scripted_smoke'):
    runtime = load_runtime_config()
    runtime.setdefault("aidev_staging", {})["enabled"] = False
    workflow = load_workflow_config('config/workflows/puerts_ts.json', runtime)
    nodes, specs = build_bundle_nodes(runtime, workflow, llm_profile=llm_profile)
    by_name = {node.name: (node, spec) for node, spec in zip(nodes, specs)}
    return by_name[name], runtime, workflow


def write_json_port(bundle: RunBundle, port: str, data: dict, producer: str):
    bundle.write_port_text(port, json.dumps(data), producer=producer, kind='json')


def test_bundle_runner_executes_deterministic_analyzer_without_llm(tmp_path):
    bundle = RunBundle.create(tmp_path / 'bundle', workflow='puerts_ts_encounter_flow', user_prompt='trigger a freeze trap')
    write_json_port(bundle, 'entity_behavior', eab(), 'EntityAbilityBehaviorPlanner')
    write_json_port(bundle, 'runtime_mapping', mapping(), 'PuerTSRuntimeMappingCompiler')
    (node, spec), runtime, workflow = load_node('TypeScriptImplementationSlotProjector')
    execute_node(bundle, node, spec, runtime, workflow)
    assert bundle.has_port('ts_analyzer')
    data = bundle.read_port_json('ts_analyzer')
    assert data['missing_slots'] == []
    assert data['implementation_slots'][0]['target_ts_file'] == mapping()['mappings'][0]['runtime_owner']
    assert (bundle.root / 'llm_outputs' / 'TypeScriptImplementationSlotProjector.txt').exists()
    assert bundle.manifest['trace']['token_usage']['TypeScriptImplementationSlotProjector']['total_tokens'] == 0


def test_bundle_runner_encounter_spec_skips_scene_manifest_for_non_enemy_flow(tmp_path):
    bundle = RunBundle.create(tmp_path / 'bundle', workflow='puerts_ts_encounter_flow', user_prompt='trigger a freeze trap')
    write_json_port(bundle, 'entity_behavior', eab(), 'EntityAbilityBehaviorPlanner')
    write_json_port(bundle, 'thin_flow', thin(), 'ThinGameplayFlowPlanner')
    (node, spec), runtime, workflow = load_node('EncounterSpecPlanner')
    execute_node(bundle, node, spec, runtime, workflow)
    assert bundle.has_port('encounter_spec')
    assert not bundle.has_port('scene_spawn_manifest')
    assert bundle.read_port_json('encounter_spec')['encounters'] == []


def test_bundle_runner_codegen_materializes_declared_typescript(tmp_path):
    bundle = RunBundle.create(tmp_path / 'bundle', workflow='puerts_ts_encounter_flow', user_prompt='trigger a freeze trap')
    for port, data, producer in [
        ('entity_behavior', eab(), 'EntityAbilityBehaviorPlanner'),
        ('thin_flow', thin(), 'ThinGameplayFlowPlanner'),
        ('encounter_spec', encounter(), 'EncounterSpecPlanner'),
        ('ue_api_feasibility', mcp(), 'UEApiMCPFeasibilitySearcher'),
        ('runtime_mapping', mapping(), 'PuerTSRuntimeMappingCompiler'),
        ('ts_analyzer', analyzer(), 'TypeScriptImplementationSlotProjector'),
        ('interactive_ts_plan', interactive(), 'TypeScriptInteractiveTemplatePlanner'),
    ]:
        write_json_port(bundle, port, data, producer)
    (node, spec), runtime, workflow = load_node('TypeScriptRuntimeTemplatePlanner')
    execute_node(bundle, node, spec, runtime, workflow)
    assert bundle.has_port('typescript_codegen')
    assert (bundle.root / 'TypeScript' / 'content' / 'generated' / 'AutoUEBehaviorSpec.generated.ts').exists()
    assert (bundle.root / 'TypeScript' / 'content' / 'generated' / 'AutoUEGeneratedRuntime.ts').exists()
    assert not (bundle.root / 'TypeScript' / 'content' / 'generated' / 'AutoUETrapRuntime.ts').exists()
    assert not (bundle.root / 'TypeScript' / 'content' / 'generated' / 'AutoUEEncounterManager.ts').exists()
    assert not (bundle.root / 'TypeScript' / 'content' / 'generated' / 'AutoUEEnemySpawnManager.ts').exists()


def test_node_cli_run_and_validate_roundtrip(tmp_path):
    prev = tmp_path / 'prev'
    next_bundle = tmp_path / 'next'
    bundle = RunBundle.create(prev, workflow='puerts_ts_encounter_flow', user_prompt='trigger a freeze trap')
    write_json_port(bundle, 'entity_behavior', eab(), 'EntityAbilityBehaviorPlanner')
    write_json_port(bundle, 'runtime_mapping', mapping(), 'PuerTSRuntimeMappingCompiler')
    bundle.save()
    run = subprocess.run([
        sys.executable, 'autoue.py', 'node', 'run', '--llm-profile', 'scripted_smoke',
        '--node', 'TypeScriptImplementationSlotProjector', '--input-bundle', str(prev), '--output-bundle', str(next_bundle)
    ], cwd=ROOT, text=True, capture_output=True, check=True)
    assert 'TypeScriptImplementationSlotProjector' in run.stdout
    val = subprocess.run([
        sys.executable, 'autoue.py', 'node', 'validate', '--node', 'TypeScriptImplementationSlotProjector', '--bundle', str(next_bundle)
    ], cwd=ROOT, text=True, capture_output=True, check=True)
    assert json.loads(val.stdout)['result'] == 'pass'


def test_stage_generated_ts_to_aidev_plans_only_autoue_generated_files(tmp_path):
    from tools.unreal.stage_generated_ts_to_aidev import StageConfig, stage_generated_ts_bundle

    bundle = tmp_path / "bundle"
    source = bundle / "TypeScript" / "content" / "generated"
    source.mkdir(parents=True)
    (bundle / "TypeScript" / "AutoUEGeneratedCharacterAdapter.ts").write_text("export const fresh = 1;\n", encoding="utf-8")
    (source / "AutoUEGeneratedRuntime.ts").write_text("export const runtime = 1;\n", encoding="utf-8")
    aidev = tmp_path / "AIDev"
    old_generated = aidev / "TypeScript" / "content" / "generated"
    old_generated.mkdir(parents=True)
    (aidev / "TypeScript" / "KeepUserCode.ts").write_text("keep\n", encoding="utf-8")
    (old_generated / "AutoUEOldRuntime.ts").write_text("old\n", encoding="utf-8")

    report = stage_generated_ts_bundle(StageConfig(bundle=bundle, aidev_root=aidev, apply=False, run_tsc=False, report_path=Path("flow/stage.json")))

    assert report["status"] == "dry_run"
    assert (aidev / "TypeScript" / "KeepUserCode.ts").read_text(encoding="utf-8") == "keep\n"
    assert "content/generated/AutoUEOldRuntime.ts" in report["removed"]
    assert any(item["path"] == "content/generated/AutoUEGeneratedRuntime.ts" for item in report["copied"])
    assert (bundle / "flow" / "stage.json").exists()
