
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ORDER = [
    'SceneAndGameplaySplitter',
    'EntityAbilityBehaviorPlanner',
    'ThinGameplayFlowPlanner',
    'EncounterSpecPlanner',
    'UEApiMCPFeasibilitySearcher',
    'PuerTSRuntimeMappingCompiler',
    'TypeScriptImplementationSlotProjector',
    'TypeScriptInteractiveTemplatePlanner',
    'TypeScriptRuntimeTemplatePlanner',
    'StaticEvaluationPlanBuilder',
]
RUNTIME_MAPPING_PATH = 'flow/05-puerts-runtime-mapping.json'
ADJ_INPUT = 'flow/04-ue-api-mcp/adjudication/input.action_binding.json'
ADJ_OVERLAP = 'flow/04-ue-api-mcp/adjudication/primitive.on_component_begin_overlap.json'
ADJ_VISIBILITY = 'flow/04-ue-api-mcp/adjudication/component.set_visibility.json'
ADJ_CAMERA = 'flow/04-ue-api-mcp/adjudication/camera.update_view_target.json'


def run(cmd):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=True)


def run_no_check(cmd):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)


def write_workflow_variant(tmp_path: Path, mutate):
    workflow = json.loads((ROOT / 'config' / 'workflows' / 'puerts_ts.json').read_text(encoding='utf-8'))
    mutate(workflow)
    path = tmp_path / 'workflow.json'
    path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding='utf-8')
    return path



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
    return {'runtime_mapping_path': RUNTIME_MAPPING_PATH, 'behavior_spec_path': 'flow/06-behavior-spec.json', 'support_check_path': 'flow/06-runtime-support-check.json', 'runtime_features': RUNTIME_FEATURES, 'disabled_features': DISABLED_FEATURES, 'behavior_spec': spec, 'support_check': support, 'mappings': [{'entity_id': 'freeze_trap', 'behavior_id': BEHAVIOR_ID, 'flow_id': FLOW_ID, 'runtime_owner': RUNTIME_OWNER, 'implementation_carrier': 'template_rendered_ts', 'selected_runtime_owner': 'AutoUEBehaviorSpec.generated', 'existing_framework_candidates': ['AutoUE behavior runtime framework'], 'why_not_existing_framework': 'shared behavior framework renders BehaviorSpec instead of gameplay-specific TS', 'temporary_or_canonical': 'canonical', 'migration_path': 'regenerate BehaviorSpec data only', 'engine_port_mappings': [{'engine_port_id': p, 'adjudication_path': a, 'adapter_or_helper': helpers[p], 'verdict': 'hit', 'evidence_symbols': [syms[p]]} for p, a in zip(ENGINE_PORTS, ADJUDICATIONS)], 'thin_contracts': ['read input', 'detect overlap', 'write player.effects.frozen', 'show vfx', 'shake camera'], 'ability_binding': 'behavior_spec:hazard.behavior.freeze_on_overlap', 'verification_evidence': ['StateWritten player.effects.frozen']}], 'blocked_mappings': []}

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
        'TypeScriptInteractiveTemplatePlanner': json.dumps(interactive()),
    })
    return build_codegen_output(state)

def eval_plan():
    trace = {'entity_id': 'freeze_trap', 'behavior_id': BEHAVIOR_ID, 'flow_id': FLOW_ID, 'engine_port_ids': ENGINE_PORTS, 'adjudication_paths': ADJUDICATIONS, 'runtime_mapping_path': RUNTIME_MAPPING_PATH, 'ts_files': [INTERACTIVE_TS, RUNTIME_OWNER]}
    return {'evaluation_instructions': [{'step_id': 1, 'action': 'trigger_freeze_trap', 'target': 'FreezeTrap', 'description': 'validate static adapter call trace', 'driver': 'adapter_call', 'executor_action': 'call_behavior', 'expected': [{'type': 'static_trace_present', 'key': 'ability_module_export', 'expected_value': 'getAutoUEBehaviorSpec'}, {'type': 'static_trace_present', 'key': 'interactive_adapter_export', 'expected_value': 'runFreezeTrapInteraction'}, {'type': 'static_trace_present', 'key': 'engine_ports_mapped', 'expected_value': ENGINE_PORTS}], 'trace': trace}], 'coverage': [trace]}


def good_outputs():
    return {
        'SceneAndGameplaySplitter': json.dumps({'scene_description': 'Room', 'gameplay_description': 'Trigger freeze trap'}),
        'EntityAbilityBehaviorPlanner': json.dumps(eab()),
        'ThinGameplayFlowPlanner': json.dumps(thin()),
        'EncounterSpecPlanner': json.dumps(encounter()),
        'UEApiMCPFeasibilitySearcher': json.dumps(mcp()),
        'PuerTSRuntimeMappingCompiler': json.dumps(mapping()),
        'TypeScriptImplementationSlotProjector': json.dumps(analyzer()),
        'TypeScriptInteractiveTemplatePlanner': json.dumps(interactive()),
        'TypeScriptRuntimeTemplatePlanner': json.dumps(codegen()),
        'StaticEvaluationPlanBuilder': json.dumps(eval_plan()),
    }


def test_workflow_contains_only_active_puerts_nodes():
    result = run([sys.executable, 'tools/validate_config_contract.py', '--workflow', 'config/workflows/puerts_ts.json', '--contract', 'puerts_ts'])
    data = json.loads(result.stdout)
    assert data['result'] == 'pass'
    assert data['enabled_nodes'] == ORDER
    workflow = json.loads((ROOT / 'config' / 'workflows' / 'puerts_ts.json').read_text(encoding='utf-8'))
    all_nodes = {node['name'] for node in workflow['nodes']}
    for name in [
        'SceneFormalizer',
        'KeyElementExtractor',
        'RetrieveModel',
        'ModuleAnalyzer',
        'ModuleCodeGenerator',
        'InteractiveObjectAnalyzer',
        'InteractiveObjectCodeGenerator',
        'PCGGraphComposer',
        'PCGPlanner',
    ]:
        assert name not in all_nodes


def test_dry_run_config_has_prompts():
    result = run([sys.executable, 'autoue.py', 'check-config'])
    data = json.loads(result.stdout)
    assert data['missing_prompts'] == []
    assert data['enabled_nodes'] == ORDER
    assert data['runtime_validation']['enabled'] is False
    assert data['runtime_validation']['supported_drivers'] == ['adapter_call']


def test_workflow_uses_task_specific_codex_profiles():
    workflow = json.loads((ROOT / 'config' / 'workflows' / 'puerts_ts.json').read_text(encoding='utf-8'))
    by_name = {node['name']: node for node in workflow['nodes']}
    assert by_name['UEApiMCPFeasibilitySearcher']['llm_profile'] == 'codex_cli_fast'
    assert by_name['PuerTSRuntimeMappingCompiler']['llm_profile'] == 'codex_cli_planning'
    assert by_name['TypeScriptRuntimeTemplatePlanner']['llm_profile'] == 'codex_cli_codegen'


def test_workflow_config_declares_validators_and_artifacts():
    workflow = json.loads((ROOT / 'config' / 'workflows' / 'puerts_ts.json').read_text(encoding='utf-8'))
    by_name = {node['name']: node for node in workflow['nodes']}
    assert by_name['ThinGameplayFlowPlanner']['validator'] == 'thin_gameplay_flow_planner'
    assert {'kind': 'json', 'path': 'flow/03-thin-gameplay-flow.json'} in by_name['ThinGameplayFlowPlanner']['output_artifacts']
    assert {'kind': 'json', 'path_from': 'queries[].adjudication_path'} in by_name['UEApiMCPFeasibilitySearcher']['output_artifacts']
    assert {'kind': 'typescript', 'path_from': 'template_inputs[].path'} in by_name['TypeScriptRuntimeTemplatePlanner']['output_artifacts']


def test_config_contract_rejects_unknown_validator(tmp_path):
    path = write_workflow_variant(tmp_path, lambda wf: wf['nodes'][0].update({'validator': 'no_such_validator'}))
    result = run_no_check([sys.executable, 'tools/validate_config_contract.py', '--workflow', str(path), '--contract', 'puerts_ts'])
    assert result.returncode == 1
    assert 'unknown or missing validator' in result.stdout


def test_config_contract_rejects_missing_llm_profile(tmp_path):
    def mutate(wf):
        del wf['nodes'][0]['llm_profile']
    path = write_workflow_variant(tmp_path, mutate)
    result = run_no_check([sys.executable, 'tools/validate_config_contract.py', '--workflow', str(path), '--contract', 'puerts_ts'])
    assert result.returncode == 1
    assert 'missing llm_profile' in result.stdout


def test_config_contract_rejects_unknown_llm_profile(tmp_path):
    path = write_workflow_variant(tmp_path, lambda wf: wf['nodes'][0].update({'llm_profile': 'missing_profile'}))
    result = run_no_check([sys.executable, 'tools/validate_config_contract.py', '--workflow', str(path), '--contract', 'puerts_ts'])
    assert result.returncode == 1
    assert 'llm_profile does not exist' in result.stdout


def test_config_contract_rejects_absolute_output_artifact_path(tmp_path):
    def mutate(wf):
        wf['nodes'][0]['output_artifacts'][0]['path'] = 'C:/outside/SceneAndGameplaySplitter.txt'
    path = write_workflow_variant(tmp_path, mutate)
    result = run_no_check([sys.executable, 'tools/validate_config_contract.py', '--workflow', str(path), '--contract', 'puerts_ts'])
    assert result.returncode == 1
    assert 'safe relative path' in result.stdout


def test_workflow_loader_attaches_configured_validator_profile_and_artifacts():
    from core.workflow_loader import create_node_from_spec

    workflow = json.loads((ROOT / 'config' / 'workflows' / 'puerts_ts.json').read_text(encoding='utf-8'))
    spec = next(node for node in workflow['nodes'] if node['name'] == 'ThinGameplayFlowPlanner')
    node = create_node_from_spec(spec)
    assert node.validator_id == 'thin_gameplay_flow_planner'
    assert node.llm_profile == 'codex_cli_planning'
    assert {'kind': 'json', 'path': 'flow/03-thin-gameplay-flow.json'} in node.output_artifacts


def test_old_workflow_validation_facade_imports_still_work():
    from core.workflow_validation import (
        NODE_VALIDATORS,
        WorkflowValidationError,
        validate_graph_node_output,
        validate_node_output,
        validate_workflow_output_set,
    )
    assert WorkflowValidationError
    assert callable(validate_graph_node_output)
    assert callable(validate_node_output)
    assert callable(validate_workflow_output_set)
    assert 'ThinGameplayFlowPlanner' in NODE_VALIDATORS


def test_ts_generators_reject_raw_content_output():
    from core.workflow_validation import WorkflowValidationError, validate_node_output
    bad = {'files': [{'path': 'TypeScript/content/generated/Bad.ts', 'content': 'export const raw = true;'}], 'behavior_traces': [], 'validation_notes': []}
    try:
        validate_node_output('TypeScriptRuntimeTemplatePlanner', json.dumps(bad))
    except WorkflowValidationError as exc:
        assert 'raw files/content' in str(exc)
    else:
        raise AssertionError('validator accepted raw content output')


def test_planner_rejects_implementation_decisions():
    from core.workflow_validation import WorkflowValidationError, validate_node_output
    bad = eab()
    behavior = next(
        behavior
        for entity in bad['entities']
        for capability in entity.get('capabilities', [])
        for behavior in capability.get('behaviors', [])
    )
    behavior['target_ts_file'] = 'TypeScript/content/generated/X.ts'
    try:
        validate_node_output('EntityAbilityBehaviorPlanner', json.dumps(bad))
    except WorkflowValidationError as exc:
        assert 'definition-only' in str(exc)
    else:
        raise AssertionError('planner accepted implementation fields')


def test_thin_flow_requires_engine_ports():
    from core.workflow_validation import WorkflowValidationError, validate_node_output
    bad = thin()
    for stage in bad['flows'][0]['stages']:
        stage['engine_ports'] = []
    try:
        validate_node_output('ThinGameplayFlowPlanner', json.dumps(bad))
    except WorkflowValidationError as exc:
        assert 'engine_port' in str(exc)
    else:
        raise AssertionError('thin flow accepted no engine ports')


def test_mcp_miss_blocks_workflow_completion():
    from core.workflow_validation import WorkflowValidationError, validate_workflow_output_set
    outputs = good_outputs()
    bad = mcp()
    bad['queries'][0]['verdict'] = 'miss'
    bad['queries'][0]['hit_type'] = 'none'
    outputs['UEApiMCPFeasibilitySearcher'] = json.dumps(bad)
    try:
        validate_workflow_output_set(outputs)
    except WorkflowValidationError as exc:
        assert 'must be hit' in str(exc)
    else:
        raise AssertionError('workflow accepted MCP miss')


def test_runtime_mapping_blocked_blocks_workflow_completion():
    from core.workflow_validation import WorkflowValidationError, validate_workflow_output_set
    outputs = good_outputs()
    bad = mapping()
    bad['blocked_mappings'] = [{'behavior_id': BEHAVIOR_ID}]
    outputs['PuerTSRuntimeMappingCompiler'] = json.dumps(bad)
    try:
        validate_workflow_output_set(outputs)
    except WorkflowValidationError as exc:
        assert 'blocked_mappings' in str(exc)
    else:
        raise AssertionError('workflow accepted blocked mapping')


def test_analyzer_requires_mapping_trace():
    from core.workflow_validation import WorkflowValidationError, validate_node_output
    bad = analyzer()
    del bad['implementation_slots'][0]['runtime_mapping_path']
    try:
        validate_node_output('TypeScriptImplementationSlotProjector', json.dumps(bad))
    except WorkflowValidationError as exc:
        assert 'runtime_mapping_path' in str(exc)
    else:
        raise AssertionError('analyzer accepted slot without runtime mapping')


def test_typescript_script_analyzer_projects_runtime_mappings_without_llm():
    from core.BaseLLMNode import GraphState
    from custom_nodes.typescript_script_analyzer import create_typescript_script_analyzer

    class ExplodingModel:
        def invoke(self, _messages):
            raise AssertionError('TypeScriptImplementationSlotProjector must not call an LLM model')

    state = GraphState(llm_outputs={
        'EntityAbilityBehaviorPlanner': json.dumps(eab()),
        'PuerTSRuntimeMappingCompiler': json.dumps(mapping()),
    })
    node = create_typescript_script_analyzer()
    node.set_model(ExplodingModel())
    node.execute(state)
    data = json.loads(state.llm_outputs['TypeScriptImplementationSlotProjector'])
    assert data['missing_slots'] == []
    assert len(data['implementation_slots']) == 1
    slot = data['implementation_slots'][0]
    assert slot['target_ts_file'] == mapping()['mappings'][0]['runtime_owner']
    assert slot['runtime_mapping_path'] == RUNTIME_MAPPING_PATH
    assert state.node_token_usage['TypeScriptImplementationSlotProjector']['total_tokens'] == 0


def test_typescript_script_analyzer_reports_missing_runtime_owner():
    from custom_nodes.typescript_script_analyzer import generate_typescript_script_analysis

    bad_mapping = mapping()
    del bad_mapping['mappings'][0]['runtime_owner']
    data = json.loads(generate_typescript_script_analysis(json.dumps(eab()), json.dumps(bad_mapping)))
    assert data['implementation_slots'] == []
    assert data['missing_slots']
    assert 'runtime_owner' in data['missing_slots'][0]['missing_fields']


def test_workflow_output_set_accepts_good_trace_chain():
    from core.workflow_validation import validate_workflow_output_set
    result = validate_workflow_output_set(good_outputs())
    assert BEHAVIOR_ID in result['evidence']['behavior_trace_coverage']
    assert 'primitive.on_component_begin_overlap' in result['evidence']['engine_port_ids']


def test_partial_cross_trace_allows_generic_hud_behavior_on_multiple_entities():
    from core.content_library import canonicalize_selection
    from core.workflow_validation import validate_partial_workflow_outputs

    entity_behavior = canonicalize_selection({
        'selected_entity_ids': ['health_bar_hud', 'combat_damage_number_hud'],
        'selected_capability_ids': ['hud.display.refresh_value'],
        'selected_behavior_ids': ['hud.behavior.refresh_value'],
    })
    thin_flow = {
        'flows': [
            {
                'flow_id': 'flow_health_bar_hud_refresh_value',
                'entity_id': 'health_bar_hud',
                'source_behavior_id': 'hud.behavior.refresh_value',
                'stages': [{'stage': 'Event/Result', 'contract': 'refresh health HUD', 'inputs': ['state'], 'outputs': ['hud'], 'engine_ports': ['manual.trigger']}],
                'verification': ['health hud refreshed'],
            },
            {
                'flow_id': 'flow_combat_damage_number_hud_refresh_value',
                'entity_id': 'combat_damage_number_hud',
                'source_behavior_id': 'hud.behavior.refresh_value',
                'stages': [{'stage': 'Event/Result', 'contract': 'refresh damage HUD', 'inputs': ['state'], 'outputs': ['hud'], 'engine_ports': ['manual.trigger']}],
                'verification': ['damage hud refreshed'],
            },
        ]
    }

    result = validate_partial_workflow_outputs({
        'EntityAbilityBehaviorPlanner': json.dumps(entity_behavior),
        'ThinGameplayFlowPlanner': json.dumps(thin_flow),
    })
    coverage = result['evidence']['behavior_trace_coverage'] if 'behavior_trace_coverage' in result['evidence'] else {}
    assert result['evidence']['behavior_ids'] == ['hud.behavior.refresh_value']
    assert 'health_bar_hud::hud.behavior.refresh_value' in coverage or not coverage


def test_workflow_output_set_rejects_unknown_behavior_trace():
    from core.workflow_validation import WorkflowValidationError, validate_workflow_output_set
    outputs = good_outputs()
    bad = analyzer()
    bad['implementation_slots'][0]['behavior_id'] = 'enemy.unknown.behavior'
    outputs['TypeScriptImplementationSlotProjector'] = json.dumps(bad)
    try:
        validate_workflow_output_set(outputs)
    except WorkflowValidationError as exc:
        assert 'unknown behavior_id' in str(exc)
    else:
        raise AssertionError('output set accepted unknown behavior')


def test_workflow_output_set_rejects_unrendered_analyzer_target():
    from core.workflow_validation import WorkflowValidationError, validate_workflow_output_set
    outputs = good_outputs()
    bad = analyzer()
    bad['implementation_slots'][0]['target_ts_file'] = 'TypeScript/content/generated/NotRendered.ts'
    outputs['TypeScriptImplementationSlotProjector'] = json.dumps(bad)
    try:
        validate_workflow_output_set(outputs)
    except WorkflowValidationError as exc:
        assert 'target_ts_file must equal runtime_owner' in str(exc) or 'must render every analyzer' in str(exc)
    else:
        raise AssertionError('output set accepted analyzer target that codegen did not render')


def test_workflow_output_set_rejects_eval_missing_adjudication_trace():
    from core.workflow_validation import WorkflowValidationError, validate_workflow_output_set
    outputs = good_outputs()
    bad = eval_plan()
    bad['coverage'][0]['adjudication_paths'] = [ADJ_INPUT]
    outputs['StaticEvaluationPlanBuilder'] = json.dumps(bad)
    try:
        validate_workflow_output_set(outputs)
    except WorkflowValidationError as exc:
        assert 'adjudication_paths' in str(exc)
    else:
        raise AssertionError('output set accepted eval trace missing adjudication')



def test_support_matrix_missing_entry_blocks_support_check():
    from core.runtime_support_matrix import CapabilitySupportMatrix, check_capability_support

    check = check_capability_support([CAPABILITY_IDS[0]], matrix=CapabilitySupportMatrix([]))
    assert check['status'] == 'unsupported'
    assert check['unsupported_capabilities'][0]['missing_matrix_entry'] is True


def test_typescript_codegen_refuses_unsupported_runtime_mapping():
    from core.BaseLLMNode import GraphState
    from custom_nodes.typescript_code_generator import build_codegen_output

    bad_mapping = mapping()
    bad_mapping['support_check'] = {
        'status': 'unsupported',
        'unsupported_capabilities': [{'capability_id': 'shop_room_vendor.transaction.purchase_item', 'reason': 'inventory/currency transaction runtime is not implemented'}],
        'unsupported_behaviors': ['shop_room_vendor.transaction.purchase_item'],
    }
    state = GraphState(llm_outputs={
        'PuerTSRuntimeMappingCompiler': json.dumps(bad_mapping),
        'TypeScriptImplementationSlotProjector': json.dumps(analyzer()),
        'TypeScriptInteractiveTemplatePlanner': json.dumps(interactive()),
    })
    try:
        build_codegen_output(state)
    except RuntimeError as exc:
        assert 'refuses unsupported BehaviorSpec' in str(exc)
    else:
        raise AssertionError('TypeScriptRuntimeTemplatePlanner generated TS for unsupported runtime mapping')

def test_template_renderer_writes_from_template_not_model_content(tmp_path):
    from core.BaseLLMNode import GraphState
    from custom_nodes.template_file_writer import write_files_from_output
    state = GraphState(save_dir=str(tmp_path))
    write_files_from_output(state, 'TypeScriptInteractiveTemplatePlanner', json.dumps(interactive()))
    out = tmp_path / 'TypeScript' / 'content' / 'generated' / 'interactive' / 'FreezeTrapInteractable.ts'
    text = out.read_text(encoding='utf-8')
    assert 'export function runFreezeTrapInteraction' in text
    assert 'FLOW_ID' in text
    assert 'RUNTIME_MAPPING_PATH' in text


def test_aidev_bridge_templates_expose_runtime_contract():
    runtime = (ROOT / 'templates' / 'typescript' / 'behavior_orchestrator.ts.tmpl').read_text(encoding='utf-8')
    trap_runtime = (ROOT / 'templates' / 'typescript' / 'trap_runtime.ts.tmpl').read_text(encoding='utf-8')
    vfx_runtime = (ROOT / 'templates' / 'typescript' / 'vfx_runtime.ts.tmpl').read_text(encoding='utf-8')
    scene = (ROOT / 'templates' / 'typescript' / 'scene_manifest_helper.ts.tmpl').read_text(encoding='utf-8')
    for token in [
        'AUTOUE_INPUT_RIGHT_1S',
        'AUTOUE_INPUT_ATTACK',
        'trapArmed',
        'CameraShakeTriggered=1',
        'latestAutoUEGeneratedSnapshot',
        'cameraShakeActive',
        'updateAutoUEGeneratedSideCamera',
        'AUTOUE_ENEMY_ENCOUNTER_DISABLED',
        'StateWritten player.effects.frozen',
    ]:
        assert token in runtime
    assert 'TRAP_REARM_RADIUS' in trap_runtime
    assert 'IceTrapTriggered' in trap_runtime
    assert 'AutoUEGenerated_FreezeVFX' in vfx_runtime
    assert "makeWorldMesh(actor, 'AutoUEGenerated_Enemy'" not in runtime
    assert 'createAutoUEEncounterManager' not in runtime
    assert 'EnemyDamageApplied' not in runtime
    assert 'BeginDeferredActorSpawnFromClass' not in runtime
    for token in [
        'autoue-generated-scene-manifest/v3',
        'harness_input_tags',
        'AUTOUE_INPUT_RIGHT_1S',
        'AutoUEGenerated_SideCamera',
    ]:
        assert token in scene
    camera = (ROOT / 'templates' / 'typescript' / 'aid_camera_setup.ts.tmpl').read_text(encoding='utf-8')
    for token in [
        'sideOffsetY',
        'SIDE_CAMERA_YAW = 90',
        'updateAutoUEGeneratedSideCamera',
        'K2_SetWorldLocation',
        'K2_SetWorldRotation',
    ]:
        assert token in camera


def _has_current_smoke(root: Path) -> bool:
    return all((root / 'llm_outputs' / f'{node}.txt').exists() for node in ORDER)


def test_existing_workflow_output_validator_passes_when_current_smoke_present():
    root = ROOT / 'data' / 'output-smoke' / 'demo_1'
    if not root.exists() or not _has_current_smoke(root):
        return
    result = run([sys.executable, 'tools/validate_workflow_outputs.py', '--root', str(root)])
    data = json.loads(result.stdout)
    assert data['result'] == 'pass'


def test_existing_smoke_output_validator_passes_when_current_smoke_present():
    root = ROOT / 'data' / 'output-smoke' / 'demo_1'
    if not root.exists() or not _has_current_smoke(root):
        return
    result = run([sys.executable, 'tools/validate_smoke_outputs.py', '--root', str(root)])
    data = json.loads(result.stdout)
    assert data['result'] == 'pass'


def test_mcp_config_can_fallback_to_codex_config_or_env(monkeypatch):
    from core.mcp_client import load_ue_api_mcp_config
    monkeypatch.setenv('AUTOUE_UE_API_MCP_COMMAND', 'python')
    monkeypatch.setenv('AUTOUE_UE_API_MCP_ARGS', '["-m", "ue_api_search_mcp.server"]')
    cfg = load_ue_api_mcp_config({})
    assert cfg.command == 'python'
    assert cfg.args == ['-m', 'ue_api_search_mcp.server']
