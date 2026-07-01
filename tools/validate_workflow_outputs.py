from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.workflow_validation import BANNED_OUTPUT_MARKERS, WORKFLOW_NODE_ORDER, WorkflowValidationError, is_safe_relative_path, validate_workflow_output_set
from core.encounter_validation import ENCOUNTER_SPEC_MD_PATH, ENCOUNTER_SPEC_PATH, SCENE_SPAWN_MANIFEST_PATH, STRUCTURE_PATH, EncounterValidationError, validate_encounter_spec_data, validate_scene_spawn_manifest_data

CXX_SUFFIXES = {'.h', '.cpp'}
CXX_FILE_RE = re.compile(r'(?i)\.(?:h|cpp)\b')


def load_workflow_config(rel: str) -> dict:
    with (ROOT / rel).open('r', encoding='utf-8') as f:
        return json.load(f)


def iter_enabled_nodes(workflow: dict) -> list[dict]:
    return [node for node in workflow.get('nodes', []) if isinstance(node, dict) and node.get('enabled', True)]


def banned(label: str, text: str, errors: list[str]) -> None:
    if CXX_FILE_RE.search(text):
        errors.append(f'{label} contains forbidden native filename marker')
    for marker in BANNED_OUTPUT_MARKERS:
        if marker in text:
            errors.append(f'{label} contains banned marker: {marker}')


def validate_ts(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding='utf-8', errors='replace')
    banned(f'generated TypeScript {path}', text, errors)
    if '```' in text:
        errors.append(f'generated TypeScript contains Markdown fences: {path}')
    if text.count('{') != text.count('}'):
        errors.append(f'generated TypeScript has unbalanced braces: {path}')
    if text.count('(') != text.count(')'):
        errors.append(f'generated TypeScript has unbalanced parentheses: {path}')
    if 'export ' not in text and 'class ' not in text and 'function ' not in text:
        errors.append(f'generated TypeScript lacks an obvious exported/function/class entry point: {path}')


def validate_encounter_runtime_consumption(root: Path, data: dict, errors: list[str], evidence: dict) -> None:
    encounter = data.get('EncounterSpecPlanner', {}) if isinstance(data, dict) else {}
    if not isinstance(encounter, dict) or not encounter.get('encounters'):
        return
    runtime = root / 'TypeScript' / 'content' / 'generated' / 'AutoUEGeneratedRuntime.ts'
    if not runtime.exists():
        errors.append('EncounterSpec runtime consumption missing AutoUEGeneratedRuntime.ts')
        return
    text = runtime.read_text(encoding='utf-8', errors='replace')
    banned_runtime_markers = ['spawnGeneratedEnemies', 'enemySpawnBehaviors', 'const x = 340', 'FLOOR_Z + 40 }', 'services.enemySpawn.spawnEnemy(behavior, transform)']
    for marker in banned_runtime_markers:
        if marker in text:
            errors.append(f'EncounterSpec runtime consumption bypassed by hardcoded spawn marker: {marker}')
    required_runtime_markers = ['getAutoUEGeneratedEncounterSpec', 'startInitialEncounters', 'AutoUEEnemySpawnManager', 'AutoUESpawnPointRegistry']
    for marker in required_runtime_markers:
        if marker not in text:
            errors.append(f'EncounterSpec runtime consumption missing marker in AutoUEGeneratedRuntime.ts: {marker}')
    for rel in [
        'TypeScript/content/generated/AutoUEGeneratedEncounterSpec.ts',
        'TypeScript/content/generated/AutoUESpawnPointRegistry.ts',
        'TypeScript/content/generated/AutoUEEnemySpawnManager.ts',
        'TypeScript/content/generated/AutoUEEncounterManager.ts',
    ]:
        if not (root / rel).exists():
            errors.append(f'EncounterSpec runtime consumption missing generated module: {rel}')
    evidence['encounter_runtime_consumption'] = 'checked'


def ensure_rel_file(root: Path, rel: str, label: str, errors: list[str]) -> Path | None:
    if not isinstance(rel, str) or not is_safe_relative_path(rel):
        errors.append(f'{label} unsafe path: {rel}')
        return None
    target = (root / rel.replace('\\', '/')).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        errors.append(f'{label} path outside output root: {rel}')
        return None
    if not target.exists():
        errors.append(f'{label} missing file: {rel}')
        return None
    return target


def values_from_selector(data: dict, selector: str) -> list[str]:
    """Resolve the small path_from selector subset used by workflow config.

    Supported examples:
    - queries[].adjudication_path
    - template_inputs[].path
    """
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


def validate_configured_artifacts(root: Path, workflow: dict, data: dict, errors: list[str]) -> list[str]:
    artifacts: list[str] = []
    for node in iter_enabled_nodes(workflow):
        node_name = node.get('name', '')
        node_data = data.get(node_name, {}) if isinstance(data, dict) else {}
        for artifact in node.get('output_artifacts', []):
            if not isinstance(artifact, dict):
                continue
            kind = artifact.get('kind', 'artifact')
            if kind == 'llm_output':
                # LLM outputs are checked before node JSON validation.
                continue
            rels: list[str] = []
            if isinstance(artifact.get('path'), str):
                rels = [artifact['path'].format(node=node_name)]
            elif isinstance(artifact.get('path_from'), str):
                if isinstance(node_data, dict):
                    rels = values_from_selector(node_data, artifact['path_from'])
                if not rels:
                    errors.append(f'{node_name} configured artifact selector produced no paths: {artifact["path_from"]}')
                    continue
            for rel in rels:
                target = ensure_rel_file(root, rel, f'{node_name} configured {kind} artifact', errors)
                if not target:
                    continue
                artifacts.append(rel)
                if kind == 'json':
                    try:
                        json.loads(target.read_text(encoding='utf-8'))
                    except Exception as exc:
                        errors.append(f'{node_name} configured JSON artifact is invalid: {rel}: {exc}')
                if kind == 'typescript':
                    validate_ts(target, errors)
    return artifacts


def validate_declared_files(root: Path, data: dict, errors: list[str]) -> list[str]:
    emitted: list[str] = []
    for node in ['TypeScriptInteractiveTemplatePlanner', 'TypeScriptRuntimeTemplatePlanner']:
        node_data = data.get(node, {}) if isinstance(data, dict) else {}
        for item in node_data.get('template_inputs', []) if isinstance(node_data, dict) else []:
            rel = item.get('path', '') if isinstance(item, dict) else ''
            target = ensure_rel_file(root, rel, f'{node} template output', errors)
            if target:
                emitted.append(rel)
    return emitted


def _enemy_encounter_enabled(data: dict) -> bool:
    for node_name in ("PuerTSRuntimeMappingCompiler", "TypeScriptRuntimeTemplatePlanner"):
        node = data.get(node_name, {}) if isinstance(data, dict) else {}
        if isinstance(node, dict) and "enemy_encounter" in node.get("runtime_features", []):
            return True
    encounter = data.get("EncounterSpecPlanner", {}) if isinstance(data, dict) else {}
    return bool(isinstance(encounter, dict) and encounter.get("encounters"))


def validate_encounter_artifacts(root: Path, data: dict, errors: list[str], evidence: dict) -> list[str]:
    artifacts: list[str] = []
    manifest_data = None
    if _enemy_encounter_enabled(data):
        manifest_path = ensure_rel_file(root, SCENE_SPAWN_MANIFEST_PATH, 'SceneSpawnManifest', errors)
        if manifest_path:
            artifacts.append(SCENE_SPAWN_MANIFEST_PATH)
            try:
                manifest_data = json.loads(manifest_path.read_text(encoding='utf-8'))
                validate_scene_spawn_manifest_data(manifest_data)
                evidence['scene_spawn_groups'] = [g.get('spawn_group') for g in manifest_data.get('spawn_groups', [])]
            except Exception as exc:
                errors.append(f'scene-spawn-manifest is invalid: {exc}')
    else:
        evidence['scene_spawn_groups'] = []
    for rel, label in [(STRUCTURE_PATH, 'EntityAbilityBehaviorPlanner structure artifact'), (ENCOUNTER_SPEC_PATH, 'EncounterSpecPlanner json artifact'), (ENCOUNTER_SPEC_MD_PATH, 'EncounterSpecPlanner md artifact')]:
        target = ensure_rel_file(root, rel, label, errors)
        if target:
            artifacts.append(rel)
    if data.get('EncounterSpecPlanner'):
        try:
            validate_encounter_spec_data(data['EncounterSpecPlanner'], structure=data.get('EntityAbilityBehaviorPlanner'), manifest=manifest_data)
            evidence['encounter_count'] = len(data['EncounterSpecPlanner'].get('encounters', []))
        except EncounterValidationError as exc:
            errors.append(str(exc))
    return artifacts


def validate_mcp_artifacts(root: Path, data: dict, errors: list[str]) -> list[str]:
    artifacts: list[str] = []
    mcp = data.get('UEApiMCPFeasibilitySearcher', {}) if isinstance(data, dict) else {}
    for query in mcp.get('queries', []) if isinstance(mcp, dict) else []:
        for key in ['raw_path', 'adjudication_path']:
            rel = query.get(key, '') if isinstance(query, dict) else ''
            target = ensure_rel_file(root, rel, f'UEApiMCPFeasibilitySearcher {key}', errors)
            if target:
                artifacts.append(rel)
                try:
                    obj = json.loads(target.read_text(encoding='utf-8'))
                    if key == 'adjudication_path' and obj.get('verdict') != 'hit':
                        errors.append(f'adjudication verdict must be hit for workflow completion: {rel}')
                except Exception as exc:
                    errors.append(f'{key} is not valid JSON: {rel}: {exc}')
    for rel in ['flow/03-thin-gameplay-flow.json', 'flow/04-ue-api-mcp/summary.json', 'flow/05-puerts-runtime-mapping.json']:
        target = ensure_rel_file(root, rel, 'workflow flow artifact', errors)
        if target:
            artifacts.append(rel)
    return artifacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root')
    parser.add_argument('--bundle')
    parser.add_argument('--workflow', default='config/workflows/puerts_ts.json')
    parser.add_argument('--write-report', action='store_true')
    args = parser.parse_args(argv)
    selected_root = args.bundle or args.root
    if not selected_root:
        parser.error('one of --root or --bundle is required')
    root = Path(selected_root).resolve()
    workflow = load_workflow_config(args.workflow)
    enabled_nodes = [node.get('name') for node in iter_enabled_nodes(workflow)]
    errors: list[str] = []
    evidence = {'root': str(root)}
    outputs: dict[str, str] = {}

    if not root.exists():
        errors.append(f'root does not exist: {root}')
    llm_dir = root / 'llm_outputs'
    if not llm_dir.exists():
        errors.append(f'missing llm_outputs directory: {llm_dir}')
    else:
        for node in enabled_nodes:
            path = llm_dir / f'{node}.txt'
            if not path.exists():
                errors.append(f'missing LLM output: {path}')
                continue
            text = path.read_text(encoding='utf-8', errors='replace')
            if not text.strip():
                errors.append(f'empty LLM output: {path}')
                continue
            outputs[node] = text
            banned(f'LLM output {node}', text, errors)
        evidence['validated_llm_nodes'] = list(outputs)

    data: dict = {}
    if len(outputs) == len(WORKFLOW_NODE_ORDER):
        try:
            result = validate_workflow_output_set(outputs)
            data = result['data_by_node']
            evidence.update(result['evidence'])
        except WorkflowValidationError as exc:
            errors.append(str(exc))

    def is_stage_backup(path: Path) -> bool:
        parts = set(path.relative_to(root).parts)
        return any(part.startswith('aidev_ts_backup_') for part in parts) or 'aidev-stage-backups' in parts

    ts_files = sorted(path for path in root.rglob('*.ts') if path.is_file() and not is_stage_backup(path)) if root.exists() else []
    if not ts_files:
        errors.append('no generated .ts files found under output root')
    for path in ts_files:
        validate_ts(path, errors)
    evidence['generated_ts_files'] = [str(path.relative_to(root)) for path in ts_files]
    if data:
        evidence['configured_artifacts'] = validate_configured_artifacts(root, workflow, data, errors)
        evidence['declared_ts_files'] = validate_declared_files(root, data, errors)
        evidence['encounter_artifacts'] = validate_encounter_artifacts(root, data, errors, evidence)
        validate_encounter_runtime_consumption(root, data, errors, evidence)
        evidence['mcp_artifacts'] = validate_mcp_artifacts(root, data, errors)

    native_files = sorted(path for path in root.rglob('*') if path.is_file() and path.suffix.lower() in CXX_SUFFIXES) if root.exists() else []
    if native_files:
        errors.append('workflow output must not contain native code files: ' + ', '.join(str(path.relative_to(root)) for path in native_files))

    instructions = root / 'MyPCG' / 'eval' / 'instructions.json'
    if not instructions.exists():
        errors.append(f'missing instructions.json: {instructions}')
    else:
        try:
            text = instructions.read_text(encoding='utf-8')
            banned('instructions.json', text, errors)
            obj = json.loads(text)
            if not obj.get('evaluation_instructions'):
                errors.append('instructions.json has no evaluation_instructions')
            else:
                evidence['instruction_count'] = len(obj['evaluation_instructions'])
        except Exception as exc:
            errors.append(f'instructions.json is not valid JSON: {exc}')

    if args.bundle or (root / 'manifest.json').exists():
        try:
            from core.bundle import RunBundle
            from core.bundle_validation import validate_bundle
            bundle_report = validate_bundle(RunBundle.load(root), workflow)
            evidence['bundle_validation'] = bundle_report
            if bundle_report.get('result') != 'pass':
                errors.extend('bundle: ' + err for err in bundle_report.get('errors', []))
        except Exception as exc:
            errors.append(f'bundle validation failed: {exc}')

    report = {'result': 'fail' if errors else 'pass', 'errors': errors, 'evidence': evidence}
    if args.write_report and root.exists():
        (root / 'workflow_validation_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0

if __name__ == '__main__':
    raise SystemExit(main())
