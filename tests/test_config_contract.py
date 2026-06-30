
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
    'PuerTSRuntimeMappingPlanner',
    'TypeScriptScriptAnalyzer',
    'TypeScriptInteractiveObjectGenerator',
    'TypeScriptCodeGenerator',
    'EvaluateInstructionGenerator',
]
RUNTIME_MAPPING_PATH = 'flow/05-puerts-runtime-mapping.json'
ADJ_INPUT = 'flow/04-ue-api-mcp/adjudication/input.action_binding.json'
ADJ_DAMAGE = 'flow/04-ue-api-mcp/adjudication/damage.apply.json'


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


def eab():
    return {
        'entities': [{
            'entity_id': 'player', 'display_name': 'Player', 'summary': 'Playable character', 'entity_kind': 'player', 'content_tags': ['player'], 'spawnable': False,
            'abilities': [{
                'ability_id': 'player.combat', 'display_name': 'Combat', 'summary': 'Attack enemy',
                'behaviors': [{
                    'behavior_id': 'player.combat.attack', 'display_name': 'Attack Enemy',
                    'trigger': 'attack input', 'execution': 'strike enemy', 'result': 'enemy defeated', 'source_refs': []
                }]
            }]
        }, {
            'entity_id': 'goblin_melee', 'entity_kind': 'enemy', 'display_name': 'Goblin Melee', 'summary': 'Ground melee enemy',
            'content_tags': ['enemy', 'ground', 'melee'], 'spawnable': True,
            'enemy_profile': {'cost': 2, 'allowed_spawn_tags': ['ground', 'melee'], 'default_health': 2},
            'abilities': []
        }],
        'non_goals': []
    }


def thin():
    return {'flows': [{
        'flow_id': 'flow_player_combat_attack', 'entity_id': 'player', 'ability_id': 'player.combat', 'source_behavior_id': 'player.combat.attack',
        'stages': [
            {'stage': 'Input', 'contract': 'bind player attack input', 'inputs': ['attack'], 'outputs': ['requested'], 'engine_ports': ['input.action_binding']},
            {'stage': 'Damage/Resource', 'contract': 'apply damage to enemy', 'inputs': ['enemy'], 'outputs': ['defeated'], 'engine_ports': ['damage.apply']},
        ],
        'verification': ['enemy defeated']
    }]}

def encounter():
    return {'schema_version': 'autoue-encounter-spec/v1', 'encounters': [{
        'encounter_id': 'room_01_initial_guard',
        'trigger': {'type': 'on_level_start'},
        'spawn_group': 'room_01_guard',
        'enemy_budget': 2,
        'composition': [{'enemy': 'goblin_melee', 'count': 1}],
        'spawn_policy': {'avoid_camera_view': False, 'min_distance_to_player': 400, 'consume_spawn_point': True, 'max_alive': 1},
        'completion': {'type': 'all_spawned_enemies_defeated', 'set_flags': ['exit_unlocked']},
        'verification_hooks': ['enemy_spawned', 'enemy_defeated', 'encounter_completed']
    }]}



def mcp():
    return {'queries': [
        {'engine_port_id': 'input.action_binding', 'flow_ids': ['flow_player_combat_attack'], 'behavior_ids': ['player.combat.attack'], 'query': 'q1', 'raw_path': 'flow/04-ue-api-mcp/raw/input.action_binding.raw.json', 'adjudication_path': ADJ_INPUT, 'verdict': 'hit', 'hit_type': 'direct_hit', 'evidence_symbols': ['UE.EnhancedInputComponent.BindAction'], 'notes': 'ok'},
        {'engine_port_id': 'damage.apply', 'flow_ids': ['flow_player_combat_attack'], 'behavior_ids': ['player.combat.attack'], 'query': 'q2', 'raw_path': 'flow/04-ue-api-mcp/raw/damage.apply.raw.json', 'adjudication_path': ADJ_DAMAGE, 'verdict': 'hit', 'hit_type': 'direct_hit', 'evidence_symbols': ['UE.GameplayStatics.ApplyDamage'], 'notes': 'ok'},
    ], 'summary': {'all_required_ports_hit': True, 'blocked_engine_ports': []}}


def mapping():
    return {'runtime_mapping_path': RUNTIME_MAPPING_PATH, 'mappings': [{
        'entity_id': 'player', 'ability_id': 'player.combat', 'behavior_id': 'player.combat.attack', 'flow_id': 'flow_player_combat_attack',
        'runtime_owner': 'TypeScript/content/generated/SmokeGame.ts', 'implementation_carrier': 'template_rendered_ts', 'selected_runtime_owner': 'SmokeGameAbility',
        'existing_framework_candidates': ['TypeScriptCodeGenerator templates', 'AIDev TypeScript Blueprint adapter'],
        'why_not_existing_framework': 'scripted smoke uses generated templates to prove the bridge contract',
        'temporary_or_canonical': 'temporary',
        'migration_path': 'replace smoke runtime with canonical generated AIDev bridge after runtime validation',
        'engine_port_mappings': [
            {'engine_port_id': 'input.action_binding', 'adjudication_path': ADJ_INPUT, 'adapter_or_helper': 'CharacterAdapter.bindInput', 'verdict': 'hit', 'evidence_symbols': ['UE.EnhancedInputComponent.BindAction']},
            {'engine_port_id': 'damage.apply', 'adjudication_path': ADJ_DAMAGE, 'adapter_or_helper': 'RuntimePorts.applyDamage', 'verdict': 'hit', 'evidence_symbols': ['UE.GameplayStatics.ApplyDamage']},
        ],
        'thin_contracts': ['bind player attack input', 'apply damage to enemy'], 'ability_binding': 'adapter_call:tickSmokeGame', 'verification_evidence': ['trace']
    }], 'blocked_mappings': []}


def analyzer():
    return {'typescript_sources': [{'path': 'TypeScript/content/generated/SmokeGame.ts', 'role': 'ability', 'notes': 'mapping'}], 'implementation_slots': [{
        'entity_id': 'player', 'behavior_id': 'player.combat.attack', 'flow_id': 'flow_player_combat_attack', 'runtime_mapping_path': RUNTIME_MAPPING_PATH,
        'target_ts_file': 'TypeScript/content/generated/SmokeGame.ts', 'reason': 'mapping'
    }], 'missing_slots': []}


def interactive():
    return {'template_inputs': [{
        'template': 'interactive_object', 'path': 'TypeScript/content/generated/interactive/SmokeInteractable.ts', 'entity_id': 'player', 'behavior_id': 'player.combat.attack', 'flow_id': 'flow_player_combat_attack', 'runtime_mapping_path': RUNTIME_MAPPING_PATH,
        'export_name': 'runSmokeInteraction', 'interface_name': 'SmokeInteractionContext', 'action_label': 'attacks', 'target_label': 'Enemy', 'result_label': 'enemy defeated'
    }], 'behavior_traces': [{
        'entity_id': 'player', 'behavior_id': 'player.combat.attack', 'flow_id': 'flow_player_combat_attack', 'runtime_mapping_path': RUNTIME_MAPPING_PATH, 'file_path': 'TypeScript/content/generated/interactive/SmokeInteractable.ts', 'export_name': 'runSmokeInteraction'
    }], 'validation_notes': []}


def codegen():
    base = {'entity_id': 'player', 'behavior_id': 'player.combat.attack', 'flow_id': 'flow_player_combat_attack', 'runtime_mapping_path': RUNTIME_MAPPING_PATH, 'action_label': 'attacks', 'target_label': 'Enemy', 'result_label': 'enemy defeated'}
    support = [
        {'template': 'aid_runtime_orchestrator', 'path': 'TypeScript/content/generated/AutoUEGeneratedRuntime.ts', 'export_name': 'runAutoUEGeneratedRuntime', 'interface_name': 'AutoUEGeneratedRuntimeContext'},
        {'template': 'aid_character_adapter', 'path': 'TypeScript/AutoUEGeneratedCharacterAdapter.ts', 'export_name': 'AutoUEGeneratedCharacterAdapter', 'interface_name': 'AutoUEGeneratedCharacterAdapterContext'},
        {'template': 'aid_gamemode_adapter', 'path': 'TypeScript/AutoUEGeneratedGameModeAdapter.ts', 'export_name': 'AutoUEGeneratedGameModeAdapter', 'interface_name': 'AutoUEGeneratedGameModeAdapterContext'},
        {'template': 'aid_camera_setup', 'path': 'TypeScript/content/generated/AutoUEGeneratedCameraHelper.ts', 'export_name': 'setupAutoUEGeneratedCamera', 'interface_name': 'AutoUEGeneratedCameraOptions'},
        {'template': 'scene_manifest_helper', 'path': 'TypeScript/content/generated/AutoUEGeneratedSceneManifest.ts', 'export_name': 'getAutoUEGeneratedSceneManifest', 'interface_name': 'AutoUEGeneratedSceneManifestContext'},
        {'template': 'encounter_spec_data', 'path': 'TypeScript/content/generated/AutoUEGeneratedEncounterSpec.ts', 'export_name': 'getAutoUEGeneratedEncounterSpec', 'interface_name': 'AutoUEGeneratedEncounterSpecContext'},
        {'template': 'enemy_archetypes', 'path': 'TypeScript/content/generated/AutoUEGeneratedEnemyArchetypes.ts', 'export_name': 'getAutoUEGeneratedEnemyArchetypes', 'interface_name': 'AutoUEGeneratedEnemyArchetypesContext'},
        {'template': 'spawn_point_registry', 'path': 'TypeScript/content/generated/AutoUESpawnPointRegistry.ts', 'export_name': 'createAutoUESpawnPointRegistry', 'interface_name': 'AutoUESpawnPointRegistryContext'},
        {'template': 'enemy_archetype_registry', 'path': 'TypeScript/content/generated/AutoUEEnemyArchetypeRegistry.ts', 'export_name': 'createAutoUEEnemyArchetypeRegistry', 'interface_name': 'AutoUEEnemyArchetypeRegistryContext'},
        {'template': 'enemy_spawn_manager', 'path': 'TypeScript/content/generated/AutoUEEnemySpawnManager.ts', 'export_name': 'createAutoUEEnemySpawnManager', 'interface_name': 'AutoUEEnemySpawnManagerContext'},
        {'template': 'encounter_manager', 'path': 'TypeScript/content/generated/AutoUEEncounterManager.ts', 'export_name': 'createAutoUEEncounterManager', 'interface_name': 'AutoUEEncounterManagerContext'},
    ]
    template_inputs = [{
        'template': 'ability_module', 'path': 'TypeScript/content/generated/SmokeGame.ts', **base,
        'export_name': 'tickSmokeGame', 'interface_name': 'SmokeGameContext'
    }]
    template_inputs.extend({**item, **base} for item in support)
    return {'template_inputs': template_inputs, 'behavior_traces': [{
        'entity_id': 'player', 'behavior_id': 'player.combat.attack', 'flow_id': 'flow_player_combat_attack', 'runtime_mapping_path': RUNTIME_MAPPING_PATH, 'file_path': 'TypeScript/content/generated/SmokeGame.ts', 'export_name': 'tickSmokeGame'
    }], 'consumed_interactive_files': ['TypeScript/content/generated/interactive/SmokeInteractable.ts'], 'validation_notes': []}

def eval_plan():
    trace = {'entity_id': 'player', 'ability_id': 'player.combat', 'behavior_id': 'player.combat.attack', 'flow_id': 'flow_player_combat_attack', 'engine_port_ids': ['input.action_binding', 'damage.apply'], 'adjudication_paths': [ADJ_INPUT, ADJ_DAMAGE], 'runtime_mapping_path': RUNTIME_MAPPING_PATH, 'ts_files': ['TypeScript/content/generated/interactive/SmokeInteractable.ts', 'TypeScript/content/generated/SmokeGame.ts']}
    return {'evaluation_instructions': [{'step_id': 1, 'action': 'attack', 'target': 'Enemy', 'description': 'validate static adapter call trace', 'driver': 'adapter_call', 'executor_action': 'call_behavior', 'expected': [
        {'type': 'static_trace_present', 'key': 'ability_module_export', 'expected_value': 'tickSmokeGame'},
        {'type': 'static_trace_present', 'key': 'interactive_adapter_export', 'expected_value': 'runSmokeInteraction'},
        {'type': 'static_trace_present', 'key': 'engine_ports_mapped', 'expected_value': ['input.action_binding', 'damage.apply']},
    ], 'trace': trace}], 'coverage': [trace]}


def good_outputs():
    return {
        'SceneAndGameplaySplitter': json.dumps({'scene_description': 'Room', 'gameplay_description': 'Attack enemy'}),
        'EntityAbilityBehaviorPlanner': json.dumps(eab()),
        'ThinGameplayFlowPlanner': json.dumps(thin()),
        'EncounterSpecPlanner': json.dumps(encounter()),
        'UEApiMCPFeasibilitySearcher': json.dumps(mcp()),
        'PuerTSRuntimeMappingPlanner': json.dumps(mapping()),
        'TypeScriptScriptAnalyzer': json.dumps(analyzer()),
        'TypeScriptInteractiveObjectGenerator': json.dumps(interactive()),
        'TypeScriptCodeGenerator': json.dumps(codegen()),
        'EvaluateInstructionGenerator': json.dumps(eval_plan()),
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
    assert by_name['PuerTSRuntimeMappingPlanner']['llm_profile'] == 'codex_cli_planning'
    assert by_name['TypeScriptCodeGenerator']['llm_profile'] == 'codex_cli_codegen'


def test_workflow_config_declares_validators_and_artifacts():
    workflow = json.loads((ROOT / 'config' / 'workflows' / 'puerts_ts.json').read_text(encoding='utf-8'))
    by_name = {node['name']: node for node in workflow['nodes']}
    assert by_name['ThinGameplayFlowPlanner']['validator'] == 'thin_gameplay_flow_planner'
    assert {'kind': 'json', 'path': 'flow/03-thin-gameplay-flow.json'} in by_name['ThinGameplayFlowPlanner']['output_artifacts']
    assert {'kind': 'json', 'path_from': 'queries[].adjudication_path'} in by_name['UEApiMCPFeasibilitySearcher']['output_artifacts']
    assert {'kind': 'typescript', 'path_from': 'template_inputs[].path'} in by_name['TypeScriptCodeGenerator']['output_artifacts']


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
        validate_node_output('TypeScriptCodeGenerator', json.dumps(bad))
    except WorkflowValidationError as exc:
        assert 'raw files/content' in str(exc)
    else:
        raise AssertionError('validator accepted raw content output')


def test_planner_rejects_implementation_decisions():
    from core.workflow_validation import WorkflowValidationError, validate_node_output
    bad = eab()
    bad['entities'][0]['abilities'][0]['behaviors'][0]['target_ts_file'] = 'TypeScript/content/generated/X.ts'
    try:
        validate_node_output('EntityAbilityBehaviorPlanner', json.dumps(bad))
    except WorkflowValidationError as exc:
        assert 'definition-only' in str(exc)
    else:
        raise AssertionError('planner accepted implementation fields')


def test_thin_flow_requires_engine_ports():
    from core.workflow_validation import WorkflowValidationError, validate_node_output
    bad = thin()
    bad['flows'][0]['stages'][0]['engine_ports'] = []
    bad['flows'][0]['stages'][1]['engine_ports'] = []
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
    bad['blocked_mappings'] = [{'behavior_id': 'player.combat.attack'}]
    outputs['PuerTSRuntimeMappingPlanner'] = json.dumps(bad)
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
        validate_node_output('TypeScriptScriptAnalyzer', json.dumps(bad))
    except WorkflowValidationError as exc:
        assert 'runtime_mapping_path' in str(exc)
    else:
        raise AssertionError('analyzer accepted slot without runtime mapping')


def test_typescript_script_analyzer_projects_runtime_mappings_without_llm():
    from core.BaseLLMNode import GraphState
    from custom_nodes.typescript_script_analyzer import create_typescript_script_analyzer

    class ExplodingModel:
        def invoke(self, _messages):
            raise AssertionError('TypeScriptScriptAnalyzer must not call an LLM model')

    state = GraphState(llm_outputs={
        'EntityAbilityBehaviorPlanner': json.dumps(eab()),
        'PuerTSRuntimeMappingPlanner': json.dumps(mapping()),
    })
    node = create_typescript_script_analyzer()
    node.set_model(ExplodingModel())
    node.execute(state)
    data = json.loads(state.llm_outputs['TypeScriptScriptAnalyzer'])
    assert data['missing_slots'] == []
    assert len(data['implementation_slots']) == 1
    slot = data['implementation_slots'][0]
    assert slot['target_ts_file'] == mapping()['mappings'][0]['runtime_owner']
    assert slot['runtime_mapping_path'] == RUNTIME_MAPPING_PATH
    assert state.node_token_usage['TypeScriptScriptAnalyzer']['total_tokens'] == 0


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
    assert 'player.combat.attack' in result['evidence']['behavior_trace_coverage']
    assert 'input.action_binding' in result['evidence']['engine_port_ids']


def test_workflow_output_set_rejects_unknown_behavior_trace():
    from core.workflow_validation import WorkflowValidationError, validate_workflow_output_set
    outputs = good_outputs()
    bad = analyzer()
    bad['implementation_slots'][0]['behavior_id'] = 'enemy.unknown.behavior'
    outputs['TypeScriptScriptAnalyzer'] = json.dumps(bad)
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
    outputs['TypeScriptScriptAnalyzer'] = json.dumps(bad)
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
    outputs['EvaluateInstructionGenerator'] = json.dumps(bad)
    try:
        validate_workflow_output_set(outputs)
    except WorkflowValidationError as exc:
        assert 'adjudication_paths' in str(exc)
    else:
        raise AssertionError('output set accepted eval trace missing adjudication')


def test_template_renderer_writes_from_template_not_model_content(tmp_path):
    from core.BaseLLMNode import GraphState
    from custom_nodes.template_file_writer import write_files_from_output
    state = GraphState(save_dir=str(tmp_path))
    write_files_from_output(state, 'TypeScriptInteractiveObjectGenerator', json.dumps(interactive()))
    out = tmp_path / 'TypeScript' / 'content' / 'generated' / 'interactive' / 'SmokeInteractable.ts'
    text = out.read_text(encoding='utf-8')
    assert 'export function runSmokeInteraction' in text
    assert 'FLOW_ID' in text
    assert 'RUNTIME_MAPPING_PATH' in text


def test_aidev_bridge_templates_expose_runtime_contract():
    runtime = (ROOT / 'templates' / 'typescript' / 'aid_runtime_orchestrator.ts.tmpl').read_text(encoding='utf-8')
    scene = (ROOT / 'templates' / 'typescript' / 'scene_manifest_helper.ts.tmpl').read_text(encoding='utf-8')
    for token in [
        'AUTOUE_INPUT_RIGHT_1S',
        'AUTOUE_INPUT_ATTACK',
        'trapArmed',
        'TRAP_REARM_RADIUS',
        'AutoUEGenerated_FreezeVFX',
        'CameraShakeTriggered=1',
        'latestAutoUEGeneratedSnapshot',
        'cameraShakeActive',
        'updateAutoUEGeneratedSideCamera',
        'createAutoUEEncounterManager',
        'EnemyDamageApplied',
    ]:
        assert token in runtime
    assert "makeWorldMesh(actor, 'AutoUEGenerated_Enemy'" not in runtime
    for token in [
        'autoue-generated-scene-manifest/v2',
        'harness_input_tags',
        'AUTOUE_INPUT_RIGHT_1S',
        'AutoUEGenerated_FreezeVFX',
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
