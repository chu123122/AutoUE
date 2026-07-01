from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import load_runtime_config
from core.scripted_enemy_cases import SCRIPTED_ENEMY_CASES, get_scripted_enemy_case
from tools.regen_enemy_pie import (
    DEFAULT_AIDEV_ROOT,
    DEFAULT_MAP,
    DEFAULT_PROJECT,
    DEFAULT_UNREAL_EDITOR,
    REQUIRED_SPAWN_GROUP,
    _config_path,
    run_pie_validation,
    run_spawn_precheck,
)
from tools.unreal.validate_autoue_runtime_log import validate_autoue_runtime_log

DEFAULT_OUTPUT_ROOT = ROOT / "test_tmp" / "enemy_mainchain_bundles"
SCENE_FIXTURE = "tests/fixtures/scene-spawn-manifest.valid.json"


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _runtime_override(args: argparse.Namespace) -> dict[str, Any]:
    staging: dict[str, Any] = {"enabled": not args.no_stage}
    if args.aidev_root:
        staging["aidev_root"] = args.aidev_root
    if not args.no_stage:
        staging.update({"apply": not args.dry_run_stage, "run_tsc": not args.no_tsc})
    return {
        "scene_spawn_manifest": {
            "allow_fixture": True,
            "fixture_path": SCENE_FIXTURE,
        },
        "aidev_staging": staging,
        "post_actions": {"copy_dirs": False, "copy_prompt_to_eval": False},
        "runtime_validation": {"enabled": False},
    }


def _run_command(command: list[str], *, cwd: Path, timeout: int = 1800) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, timeout=timeout)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-6000:],
        "stderr_tail": proc.stderr[-6000:],
    }


def _find_first(container: Any, key: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(container, dict):
        for k, v in container.items():
            if k == key:
                found.append(v)
            found.extend(_find_first(v, key))
    elif isinstance(container, list):
        for item in container:
            found.extend(_find_first(item, key))
    return found


def _flatten_strings(values: list[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, list):
            out.extend(item for item in value if isinstance(item, str))
    return out


def _validate_mainchain_bundle(demo: Path, case: str, *, expect_stage: bool) -> dict[str, Any]:
    spec = get_scripted_enemy_case(case)
    selection_path = demo / "flow" / "02-entity-behavior-selection.json"
    encounter_path = demo / "flow" / "03-encounter-spec.json"
    support_path = demo / "flow" / "06-runtime-support-check.json"
    codegen_path = demo / "flow" / "typescript_codegen.json"
    if not codegen_path.exists():
        codegen_path = demo / "ports" / "typescript_codegen.json"
    required_paths = [selection_path, encounter_path, support_path, codegen_path]
    missing = [str(path.relative_to(demo)).replace("\\", "/") for path in required_paths if not path.exists()]
    if missing:
        raise RuntimeError(f"{case}: mainchain bundle missing required files: {missing}")

    selection = _read_json(selection_path)
    encounter = _read_json(encounter_path)
    support = _read_json(support_path)
    codegen = _read_json(codegen_path)
    generated = demo / "TypeScript" / "content" / "generated"

    errors: list[str] = []
    for entity_id in spec.entity_ids:
        if entity_id not in selection.get("selected_entity_ids", []):
            errors.append(f"selected_entity_ids missing {entity_id}")
    if not encounter.get("encounters"):
        errors.append("encounter_spec encounters is empty")
    if support.get("status") != "supported":
        errors.append(f"support.status is {support.get('status')!r}, expected supported")
    if not (generated / "AutoUEEnemyPresentationRuntime.ts").exists():
        errors.append("generated AutoUEEnemyPresentationRuntime.ts missing")
    modules = set(_flatten_strings(_find_first(codegen, "required_runtime_modules") + [codegen.get("runtime_features", [])]))
    if "enemy_presentation" not in modules and "enemy_presentation_runtime" not in modules:
        errors.append("typescript_codegen missing enemy presentation runtime module")
    if expect_stage and not (demo / "flow" / "aidev-stage-report.json").exists():
        errors.append("aidev-stage-report.json missing")
    if errors:
        raise RuntimeError(f"{case}: mainchain validation failed: {errors}")
    report = {
        "schema_version": "autoue-enemy-mainchain-static-report/v1",
        "case": case,
        "result": "pass",
        "demo": str(demo),
        "entity_ids": list(spec.entity_ids),
        "encounter_count": len(encounter.get("encounters", [])),
        "support_status": support.get("status"),
        "required_runtime_modules": sorted(str(x) for x in modules if isinstance(x, str)),
    }
    _write_json(demo / "flow" / "enemy-mainchain-static-report.json", report)
    return report


def _run_one(case: str, args: argparse.Namespace) -> dict[str, Any]:
    spec = get_scripted_enemy_case(case)
    output_root = Path(args.output_root).resolve() / f"{_stamp()}-{case}"
    input_dir = output_root / "input"
    result_dir = output_root / "output"
    input_dir.mkdir(parents=True, exist_ok=False)
    (input_dir / "001.txt").write_text(spec.prompt + "\n", encoding="utf-8")
    config_path = output_root / "runtime-config.enemy-mainchain.json"
    _write_json(config_path, _runtime_override(args))

    command = [
        sys.executable,
        "autoue.py",
        "run",
        "--config",
        str(config_path),
        "--input-dir",
        str(input_dir),
        "--output-dir",
        str(result_dir),
        "--llm-profile",
        f"scripted_enemy_{case}",
    ]
    run = _run_command(command, cwd=ROOT, timeout=args.timeout)
    _write_json(output_root / "autoue-run-command.json", run)
    if run["returncode"] != 0:
        raise RuntimeError(f"{case}: autoue.py run failed; report={output_root / 'autoue-run-command.json'}")

    demo = result_dir / "demo_001"
    static_report = _validate_mainchain_bundle(demo, case, expect_stage=not args.no_stage)

    pie_report: dict[str, Any] | None = None
    log_report: dict[str, Any] | None = None
    spawn_precheck: dict[str, Any] | None = None
    if args.pie:
        if args.no_stage or args.dry_run_stage:
            raise RuntimeError("--pie requires real staging; remove --no-stage/--dry-run-stage")
        runtime_config = load_runtime_config(str(config_path))
        aidev_root = Path(args.aidev_root or _config_path(runtime_config, "aidev_staging.aidev_root", DEFAULT_AIDEV_ROOT))
        unreal_editor = Path(args.unreal_editor or _config_path(runtime_config, "scene_spawn_manifest.unreal_editor", DEFAULT_UNREAL_EDITOR))
        project = Path(args.project or _config_path(runtime_config, "scene_spawn_manifest.project", DEFAULT_PROJECT))
        map_path = str(args.map or _config_path(runtime_config, "scene_spawn_manifest.map", DEFAULT_MAP))
        if not args.skip_spawn_precheck:
            spawn_precheck = run_spawn_precheck(
                demo,
                unreal_editor=unreal_editor,
                project=project,
                map_path=map_path,
                required_group=args.spawn_group,
            )
        pie_report = run_pie_validation(demo, aidev_root=aidev_root, unreal_editor=unreal_editor, project=project)
        log_path = demo / "flow" / "pie-log-slice.txt"
        log_report = validate_autoue_runtime_log(
            log_path,
            require_in_range=True,
            require_enemy_move=True,
            require_attack_phase=True,
            enemy_case=case,
            require_encounter_complete=True,
        )
        _write_json(demo / "flow" / "enemy-mainchain-pie-log-report.json", log_report)
        if log_report.get("result") != "pass":
            raise RuntimeError(f"{case}: PIE log validation failed; report={demo / 'flow' / 'enemy-mainchain-pie-log-report.json'}")

    result = {
        "case": case,
        "root": str(output_root),
        "demo": str(demo),
        "static_report": static_report,
        "spawn_precheck": spawn_precheck,
        "pie_report": pie_report,
        "pie_log_report": log_report,
    }
    _write_json(demo / "flow" / "enemy-mainchain-result.json", result)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full AutoUE main chain with deterministic scripted enemy profiles, optionally stage and validate in PIE.")
    parser.add_argument("--case", required=True, choices=[*SCRIPTED_ENEMY_CASES.keys(), "all"])
    parser.add_argument("--pie", action="store_true")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--aidev-root", default="")
    parser.add_argument("--unreal-editor", default="")
    parser.add_argument("--project", default="")
    parser.add_argument("--map", default="")
    parser.add_argument("--spawn-group", default=REQUIRED_SPAWN_GROUP)
    parser.add_argument("--no-stage", action="store_true")
    parser.add_argument("--dry-run-stage", action="store_true")
    parser.add_argument("--no-tsc", action="store_true")
    parser.add_argument("--skip-spawn-precheck", action="store_true")
    parser.add_argument("--timeout", type=int, default=1800)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cases = list(SCRIPTED_ENEMY_CASES) if args.case == "all" else [args.case]
    results = []
    for case in cases:
        print(f"[AUTOUE_ENEMY_MAINCHAIN] case={case} start")
        result = _run_one(case, args)
        results.append(result)
        print(f"[AUTOUE_ENEMY_MAINCHAIN] case={case} pass demo={result['demo']}")
    print(json.dumps({"result": "pass", "cases": cases, "demos": [item["demo"] for item in results]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
