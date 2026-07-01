from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.BaseLLMNode import GraphState
from custom_nodes.template_file_writer import write_files_from_output
from tools.generate_dead_cells_enemy_runtime_cases import codegen_for
from tools.unreal.stage_generated_ts_to_aidev import DEFAULT_REPORT, StageConfig, stage_generated_ts_bundle

NODE_NAME = "TypeScriptRuntimeTemplatePlanner"
DEFAULT_OUTPUT_ROOT = ROOT / "test_tmp" / "enemy_pie_fixture_bundles"
DEFAULT_CONFIG = ROOT / "config" / "local.json"
DEFAULT_AIDEV_ROOT = Path(r"D:\UE5.7.4\AIDev")
DEFAULT_UNREAL_EDITOR = Path(r"D:\UE-src-5.7\Engine\Binaries\Win64\UnrealEditor.exe")
DEFAULT_PROJECT = Path(r"D:\UE5.7.4\AIDev\AIDev.uproject")
DEFAULT_MAP = "/Game/Castlevania2D"
REQUIRED_SPAWN_GROUP = "room_01_guard"

CASE_FIXTURES: dict[str, str] = {
    "zombie": "01-zombie_melee",
    "archer": "02-archer_projectile",
    "kamikaze": "03-kamikaze_self_destruct",
    "shield": "04-shield_bearer_block",
}

CASE_EXPECTED_ATTACK: dict[str, str] = {
    "zombie": "melee_hitbox",
    "archer": "projectile_spawn",
    "kamikaze": "self_destruct",
    "shield": "melee_hitbox",
}

CASE_REQUIRED_MODULES: dict[str, set[str]] = {
    "zombie": {"enemy_combat", "enemy_presentation", "enemy_runtime", "encounter_manager"},
    "archer": {"enemy_combat", "enemy_presentation", "enemy_projectile_runtime", "enemy_runtime", "encounter_manager"},
    "kamikaze": {"enemy_combat", "enemy_presentation", "enemy_runtime", "encounter_manager"},
    "shield": {"enemy_combat", "enemy_presentation", "enemy_runtime", "encounter_manager"},
}

COMMON_LOG_MARKERS = [
    "EnemySpawnedByEncounter",
    "EnemyDetectPlayer",
    "in_range=1",
    "EnemyMoved",
    "EnemyAttackTelegraph",
    "EnemyAttackActive",
    "EnemyAttackResolved",
    "EncounterCompleted=1",
]


@dataclass
class CaseBundle:
    case: str
    fixture: Path
    bundle: Path
    behavior_spec: dict[str, Any]
    support_check: dict[str, Any]
    typescript_codegen: dict[str, Any]
    rendered_files: list[Path]
    static_report: dict[str, Any]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _load_local_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _config_path(config: dict[str, Any], dotted: str, default: Path | str) -> Path | str:
    current: Any = config
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    if isinstance(default, Path):
        return Path(str(current)) if current else default
    return str(current) if current else default


def _fixture_root(case: str) -> Path:
    if case not in CASE_FIXTURES:
        raise RuntimeError(f"unknown enemy PIE case: {case}")
    root = ROOT / "tests" / "fixtures" / "dead_cells_enemy_runtime_cases" / CASE_FIXTURES[case]
    if not root.exists():
        raise FileNotFoundError(f"enemy fixture does not exist: {root}")
    return root


def _render_current_templates(bundle: Path, codegen: dict[str, Any]) -> list[Path]:
    state = GraphState(save_dir=str(bundle))
    output = json.dumps(codegen, ensure_ascii=False, indent=2)
    return write_files_from_output(state, NODE_NAME, output)


def _spec_uses_attack(spec: dict[str, Any], attack_type: str) -> bool:
    for behavior in spec.get("behaviors", []):
        if not isinstance(behavior, dict):
            continue
        for action in behavior.get("actions", []):
            if isinstance(action, dict) and action.get("type") == f"enemy_{attack_type}".replace("enemy_projectile_spawn", "enemy_projectile_attack"):
                return True
            params = action.get("params", {}) if isinstance(action, dict) else {}
            if isinstance(params, dict) and attack_type in json.dumps(params, ensure_ascii=False):
                return True
            if isinstance(action, dict) and attack_type in str(action.get("type", "")):
                return True
    return False


def _validate_generated_bundle(bundle: Path, case: str, spec: dict[str, Any], support: dict[str, Any], codegen: dict[str, Any]) -> dict[str, Any]:
    if support.get("status") != "supported":
        raise RuntimeError(f"{case}: support.status must be supported, got {support.get('status')!r}")

    generated_root = bundle / "TypeScript" / "content" / "generated"
    required = [
        generated_root / "AutoUEGeneratedRuntime.ts",
        generated_root / "AutoUEGeneratedEncounterSpec.ts",
        generated_root / "AutoUESpawnPointRegistry.ts",
        generated_root / "AutoUEEnemySpawnManager.ts",
        generated_root / "AutoUEEnemyPresentationRuntime.ts",
    ]
    modules = list(codegen.get("runtime_features", []))
    if "enemy_projectile_runtime" in modules or _spec_uses_attack(spec, "projectile_spawn"):
        required.append(generated_root / "AutoUEEnemyProjectileRuntime.ts")

    missing = [str(path.relative_to(bundle)).replace("\\", "/") for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"{case}: generated bundle missing required TS files: {missing}")

    rendered_modules = set(codegen.get("rendered_runtime_modules", []))
    expected_modules = {"enemy_presentation_runtime", "enemy_combat", "enemy_brain", "enemy_spawn_manager"}
    missing_modules = sorted(expected_modules - rendered_modules)
    if missing_modules:
        raise RuntimeError(f"{case}: rendered_runtime_modules missing {missing_modules}")

    missing_required_modules = sorted(CASE_REQUIRED_MODULES[case] - set(modules))
    if missing_required_modules:
        raise RuntimeError(f"{case}: required_runtime_modules missing {missing_required_modules}")

    report = {
        "schema_version": "autoue-enemy-pie-static-report/v1",
        "case": case,
        "status": "pass",
        "bundle": str(bundle),
        "required_runtime_modules": modules,
        "rendered_runtime_modules": list(codegen.get("rendered_runtime_modules", [])),
        "required_files": [str(path.relative_to(bundle)).replace("\\", "/") for path in required],
    }
    _write_json(bundle / "flow" / "enemy-pie-static-report.json", report)
    return report


def build_case_bundle(case: str, output_root: Path = DEFAULT_OUTPUT_ROOT) -> CaseBundle:
    fixture = _fixture_root(case)
    spec = _read_json(fixture / "behavior_spec.json")
    support = _read_json(fixture / "support_check.json")
    if support.get("status") != "supported":
        raise RuntimeError(f"{case}: fixture support.status must be supported, got {support.get('status')!r}")

    codegen = codegen_for(spec, support)
    bundle = (output_root / f"{_stamp()}-{case}").resolve()
    bundle.mkdir(parents=True, exist_ok=False)
    flow = bundle / "flow"
    _write_json(flow / "06-behavior-spec.json", spec)
    _write_json(flow / "06-runtime-support-check.json", support)
    _write_json(flow / "typescript_codegen.json", codegen)
    (flow / "fixture-source.txt").write_text(str(fixture) + "\n", encoding="utf-8")

    rendered = _render_current_templates(bundle, codegen)
    static_report = _validate_generated_bundle(bundle, case, spec, support, codegen)
    return CaseBundle(case, fixture, bundle, spec, support, codegen, rendered, static_report)


def stage_bundle(bundle: Path, aidev_root: Path, *, apply: bool, run_tsc: bool) -> dict[str, Any]:
    return stage_generated_ts_bundle(
        StageConfig(
            bundle=bundle,
            aidev_root=aidev_root,
            apply=apply,
            run_tsc=run_tsc,
            report_path=DEFAULT_REPORT,
        )
    )


def _logs_dir(aidev_root: Path) -> Path:
    return aidev_root / "Saved" / "Logs"


def _log_files(aidev_root: Path) -> list[Path]:
    root = _logs_dir(aidev_root)
    if not root.exists():
        return []
    return sorted(root.glob("*.log"), key=lambda path: path.stat().st_mtime)


def snapshot_logs(aidev_root: Path) -> dict[str, int]:
    return {str(path): path.stat().st_size for path in _log_files(aidev_root)}


def read_log_delta(aidev_root: Path, snapshot: dict[str, int]) -> str:
    chunks: list[str] = []
    for path in _log_files(aidev_root):
        start = snapshot.get(str(path), 0)
        size = path.stat().st_size
        if size <= start:
            continue
        with path.open("rb") as f:
            f.seek(start)
            data = f.read()
        chunks.append(data.decode("utf-8", errors="ignore"))
    return "\n".join(chunks)


def _run_command(command: list[str], *, cwd: Path | None = None, timeout: int = 1800) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=str(cwd) if cwd else None, text=True, capture_output=True, timeout=timeout)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _map_for_editor_load(map_path: str) -> str:
    text = str(map_path or DEFAULT_MAP)
    if "." in text.rsplit("/", 1)[-1]:
        return text.rsplit(".", 1)[0]
    return text


def _write_spawn_precheck_script(bundle: Path, map_path: str, required_group: str) -> tuple[Path, Path]:
    report = (bundle / "flow" / "spawn-point-precheck.json").resolve()
    script = (bundle / "flow" / "spawn-point-precheck.py").resolve()
    source = f'''
from __future__ import annotations

import json
import traceback
from pathlib import Path

import unreal

MAP_PATH = {json.dumps(_map_for_editor_load(map_path), ensure_ascii=False)}
OUTPUT_PATH = Path(r{str(report)!r})
REQUIRED_GROUP = {json.dumps(required_group, ensure_ascii=False)}
SPAWN_TAGS = ["AUTOUE_ENEMY_SPAWN_POINT", "BP_EnemySpawnPoint", "EnemySpawnPoint"]


def _name(value):
    try:
        return str(value.get_name())
    except Exception:
        return str(value)


def _tags(actor):
    try:
        return [str(item) for item in list(actor.tags)]
    except Exception:
        return []


def _class_path(actor):
    try:
        return actor.get_class().get_path_name()
    except Exception:
        return ""


def _tag_value(tags, prefixes):
    for tag in tags:
        for prefix in prefixes:
            if tag.startswith(prefix):
                return tag[len(prefix):]
    return ""


def _prop_string(actor, names):
    for name in names:
        try:
            if hasattr(actor, name):
                value = getattr(actor, name)
                if value:
                    return str(value)
        except Exception:
            pass
        try:
            value = actor.get_editor_property(name)
            if value:
                return str(value)
        except Exception:
            pass
    return ""


def _spawn_group(actor, tags):
    return _prop_string(actor, ["SpawnGroup", "spawn_group", "spawnGroup"]) or _tag_value(tags, ["SpawnGroup=", "SpawnGroup:", "spawn_group="]) or "room_01_guard"


def _is_spawn_point(actor, tags):
    name = _name(actor)
    cls = _class_path(actor)
    return any(tag in tags for tag in SPAWN_TAGS) or "BP_EnemySpawnPoint" in name or "EnemySpawnPoint" in name or "BP_EnemySpawnPoint" in cls or "EnemySpawnPoint" in cls


def main():
    result = {{"schema_version": "autoue-spawn-point-precheck/v1", "result": "fail", "map": MAP_PATH, "required_group": REQUIRED_GROUP, "points": [], "errors": []}}
    try:
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
        actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
        for actor in actors:
            tags = _tags(actor)
            if not _is_spawn_point(actor, tags):
                continue
            group = _spawn_group(actor, tags)
            result["points"].append({{"name": _name(actor), "class": _class_path(actor), "tags": tags, "spawn_group": group}})
        result["result"] = "pass" if any(p.get("spawn_group") == REQUIRED_GROUP for p in result["points"]) else "fail"
    except Exception:
        result["errors"].append(traceback.format_exc())
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    unreal.log_warning(f"[AUTOUE_SPAWN_PRECHECK] ReportWritten path={{OUTPUT_PATH}} result={{result['result']}} points={{len(result['points'])}}")
    try:
        unreal.SystemLibrary.quit_editor()
    except Exception:
        pass


main()
'''
    script.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    return script, report


def run_spawn_precheck(bundle: Path, *, unreal_editor: Path, project: Path, map_path: str, required_group: str) -> dict[str, Any]:
    if not unreal_editor.exists():
        raise FileNotFoundError(f"UnrealEditor.exe does not exist: {unreal_editor}")
    if not project.exists():
        raise FileNotFoundError(f"AIDev project does not exist: {project}")
    script, report_path = _write_spawn_precheck_script(bundle, map_path, required_group)
    command = [
        str(unreal_editor),
        str(project),
        "-unattended",
        "-nop4",
        "-nosplash",
        f"-ExecutePythonScript={script}",
    ]
    run = _run_command(command, cwd=ROOT, timeout=1800)
    report = _read_json(report_path) if report_path.exists() else {"result": "fail", "errors": ["spawn precheck report missing"]}
    report["unreal_process"] = run
    _write_json(bundle / "flow" / "spawn-point-precheck-command.json", report)
    if run["returncode"] != 0 and report.get("result") != "pass":
        raise RuntimeError(f"spawn precheck Unreal process failed: {run}")
    if report.get("result") != "pass":
        raise RuntimeError(f"spawn precheck failed: required spawn_group={required_group}, report={report_path}")
    return report


def run_pie_validation(bundle: Path, *, aidev_root: Path, unreal_editor: Path, project: Path) -> dict[str, Any]:
    if not unreal_editor.exists():
        raise FileNotFoundError(f"UnrealEditor.exe does not exist: {unreal_editor}")
    if not project.exists():
        raise FileNotFoundError(f"AIDev project does not exist: {project}")
    validator = ROOT / "tools" / "unreal" / "run_autoue_pie_validation.py"
    before = snapshot_logs(aidev_root)
    command = [
        str(unreal_editor),
        str(project),
        "-unattended",
        "-nop4",
        "-nosplash",
        f"-ExecutePythonScript={validator}",
    ]
    run = _run_command(command, cwd=ROOT, timeout=2400)
    delta = read_log_delta(aidev_root, before)
    log_slice = bundle / "flow" / "pie-log-slice.txt"
    log_slice.write_text(delta, encoding="utf-8")
    validator_report_path = ROOT / "test_tmp" / "autoue-pie-validation-current.json"
    validator_report = _read_json(validator_report_path) if validator_report_path.exists() else None
    report = {
        "schema_version": "autoue-enemy-pie-run-report/v1",
        "status": "process_pass" if run["returncode"] == 0 else "process_failed",
        "log_slice": str(log_slice),
        "unreal_process": run,
        "validator_report": validator_report,
    }
    _write_json(bundle / "flow" / "pie-run-command.json", report)
    if run["returncode"] != 0 and not (isinstance(validator_report, dict) and validator_report.get("result") == "pass"):
        raise RuntimeError(f"PIE validation Unreal process failed: {run}")
    if isinstance(validator_report, dict) and validator_report.get("result") != "pass":
        raise RuntimeError(f"PIE validation report failed: {validator_report_path}")
    return report


def assert_case_log_slice(bundle: Path, case: str) -> dict[str, Any]:
    log_path = bundle / "flow" / "pie-log-slice.txt"
    text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
    missing = [marker for marker in COMMON_LOG_MARKERS if marker not in text]
    expected_type = CASE_EXPECTED_ATTACK[case]
    type_marker = f"EnemyAttackResolved enemy_id="
    if f"type={expected_type}" not in text or type_marker not in text:
        missing.append(f"EnemyAttackResolved type={expected_type}")
    if case == "kamikaze" and "EnemyDied" not in text:
        missing.append("EnemyDied")
    if case == "shield" and "EnemyDirectionalBlock" not in text and "EnemyBlocked" not in text:
        missing.append("EnemyDirectionalBlock or EnemyBlocked")
    report = {
        "schema_version": "autoue-enemy-pie-log-assertions/v1",
        "case": case,
        "result": "pass" if not missing else "fail",
        "missing": missing,
        "log_slice": str(log_path),
    }
    _write_json(bundle / "flow" / "pie-log-assertions.json", report)
    if missing:
        raise RuntimeError(f"{case}: PIE log assertions failed, missing={missing}, log_slice={log_path}")
    return report


def _run_one(case: str, args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    bundle = build_case_bundle(case, Path(args.output_root))
    aidev_root = Path(args.aidev_root or _config_path(config, "aidev_staging.aidev_root", DEFAULT_AIDEV_ROOT))
    unreal_editor = Path(args.unreal_editor or _config_path(config, "scene_spawn_manifest.unreal_editor", DEFAULT_UNREAL_EDITOR))
    project = Path(args.project or _config_path(config, "scene_spawn_manifest.project", DEFAULT_PROJECT))
    map_path = str(args.map or _config_path(config, "scene_spawn_manifest.map", DEFAULT_MAP))

    stage_report: dict[str, Any] | None = None
    precheck_report: dict[str, Any] | None = None
    pie_report: dict[str, Any] | None = None
    log_assertions: dict[str, Any] | None = None

    if not args.no_stage:
        stage_report = stage_bundle(bundle.bundle, aidev_root, apply=not args.dry_run_stage, run_tsc=not args.no_tsc)
    if args.pie:
        if args.no_stage or args.dry_run_stage:
            raise RuntimeError("--pie requires real staging; remove --no-stage/--dry-run-stage")
        if args.no_tsc:
            raise RuntimeError("--pie requires AIDev tsc; remove --no-tsc")
        if not args.skip_spawn_precheck:
            precheck_report = run_spawn_precheck(
                bundle.bundle,
                unreal_editor=unreal_editor,
                project=project,
                map_path=map_path,
                required_group=args.spawn_group,
            )
        pie_report = run_pie_validation(bundle.bundle, aidev_root=aidev_root, unreal_editor=unreal_editor, project=project)
        log_assertions = assert_case_log_slice(bundle.bundle, case)

    result = {
        "case": case,
        "fixture": str(bundle.fixture),
        "bundle": str(bundle.bundle),
        "static_report": bundle.static_report,
        "stage_report": stage_report,
        "spawn_precheck": precheck_report,
        "pie_report": pie_report,
        "log_assertions": log_assertions,
    }
    _write_json(bundle.bundle / "flow" / "regen-enemy-pie-result.json", result)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate fixed enemy runtime fixture bundles from current templates, optionally stage to AIDev and run PIE validation.")
    parser.add_argument("--case", required=True, choices=[*CASE_FIXTURES.keys(), "all"], help="Enemy fixture case to regenerate.")
    parser.add_argument("--pie", action="store_true", help="After render+stage+tsc, run spawn precheck, PIE validation, and log assertions.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Directory that receives generated fixture bundles.")
    parser.add_argument("--aidev-root", default="", help="AIDev project root. Defaults to config/local.json aidev_staging.aidev_root.")
    parser.add_argument("--unreal-editor", default="", help="UnrealEditor.exe. Defaults to config/local.json scene_spawn_manifest.unreal_editor.")
    parser.add_argument("--project", default="", help="AIDev .uproject. Defaults to config/local.json scene_spawn_manifest.project.")
    parser.add_argument("--map", default="", help="Map path for spawn precheck. Defaults to config/local.json scene_spawn_manifest.map.")
    parser.add_argument("--spawn-group", default=REQUIRED_SPAWN_GROUP, help="Required spawn_group for PIE enemy fixture cases.")
    parser.add_argument("--no-stage", action="store_true", help="Only render and statically validate the bundle; do not copy to AIDev.")
    parser.add_argument("--dry-run-stage", action="store_true", help="Run stage report without copying files. Incompatible with --pie.")
    parser.add_argument("--no-tsc", action="store_true", help="Stage without running AIDev tsc. Incompatible with --pie intent but allowed for diagnostics.")
    parser.add_argument("--skip-spawn-precheck", action="store_true", help="Skip the editor-only spawn point precheck before PIE.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = _load_local_config()
    cases = list(CASE_FIXTURES.keys()) if args.case == "all" else [args.case]
    results = []
    for case in cases:
        print(f"[AUTOUE_REGEN_ENEMY_PIE] case={case} start")
        result = _run_one(case, args, config)
        results.append(result)
        print(f"[AUTOUE_REGEN_ENEMY_PIE] case={case} pass bundle={result['bundle']}")
    print(json.dumps({"result": "pass", "cases": [item["case"] for item in results], "bundles": [item["bundle"] for item in results]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
