from __future__ import annotations

import json
from types import SimpleNamespace


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def good_runtime_root(tmp_path, *, omit: set[str] | None = None):
    root = tmp_path / "demo_1"
    omit = omit or set()
    adj_input = "flow/04-ue-api-mcp/adjudication/input.action_binding.json"
    adj_damage = "flow/04-ue-api-mcp/adjudication/damage.apply.json"
    runtime_mapping_path = "flow/05-puerts-runtime-mapping.json"
    ability_ts = "TypeScript/content/generated/SmokeGame.ts"
    interactive_ts = "TypeScript/content/generated/interactive/SmokeInteractable.ts"
    trace = {
        "entity_id": "player",
        "behavior_id": "player.combat.attack",
        "flow_id": "flow_player_combat_attack",
        "engine_port_ids": ["input.action_binding", "damage.apply"],
        "adjudication_paths": [adj_input, adj_damage],
        "runtime_mapping_path": runtime_mapping_path,
        "ts_files": [interactive_ts, ability_ts],
    }
    instructions = {
        "evaluation_instructions": [
            {
                "step_id": 1,
                "action": "attack",
                "target": "Enemy",
                "description": "validate static adapter call trace",
                "driver": "adapter_call",
                "executor_action": "call_behavior",
                "expected": [
                    {"type": "static_trace_present", "key": "ability_module_export", "expected_value": "tickSmokeGame"},
                    {"type": "static_trace_present", "key": "interactive_adapter_export", "expected_value": "runSmokeInteraction"},
                    {"type": "static_trace_present", "key": "engine_ports_mapped", "expected_value": ["input.action_binding", "damage.apply"]},
                ],
                "trace": trace,
            }
        ],
        "coverage": [trace],
    }
    mapping = {
        "runtime_mapping_path": runtime_mapping_path,
        "mappings": [
            {
                "entity_id": "player",
                        "behavior_id": "player.combat.attack",
                "flow_id": "flow_player_combat_attack",
                "runtime_owner": ability_ts,
                "implementation_carrier": "template_rendered_ts",
                "selected_runtime_owner": "SmokeGameAbility",
                "engine_port_mappings": [
                    {"engine_port_id": "input.action_binding", "adjudication_path": adj_input, "verdict": "hit"},
                    {"engine_port_id": "damage.apply", "adjudication_path": adj_damage, "verdict": "hit"},
                ],
                "thin_contracts": ["bind input", "apply damage"],
                "ability_binding": "adapter_call:tickSmokeGame",
                "verification_evidence": ["static trace"],
            }
        ],
        "blocked_mappings": [],
    }
    if "instructions" not in omit:
        write_json(root / "MyPCG/eval/instructions.json", instructions)
    if "runtime_mapping" not in omit:
        write_json(root / runtime_mapping_path, mapping)
    if "adj_input" not in omit:
        write_json(root / adj_input, {"verdict": "hit"})
    if "adj_damage" not in omit:
        write_json(root / adj_damage, {"verdict": "hit"})
    if "ability_ts" not in omit:
        (root / ability_ts).parent.mkdir(parents=True, exist_ok=True)
        (root / ability_ts).write_text("export function tickSmokeGame() { return 'ok'; }\n", encoding="utf-8")
    if "interactive_ts" not in omit:
        (root / interactive_ts).parent.mkdir(parents=True, exist_ok=True)
        (root / interactive_ts).write_text("export function runSmokeInteraction() { return 'ok'; }\n", encoding="utf-8")
    return root


def load_instructions(root):
    return json.loads((root / "MyPCG/eval/instructions.json").read_text(encoding="utf-8"))


def save_instructions(root, data):
    write_json(root / "MyPCG/eval/instructions.json", data)


def test_runtime_validation_accepts_good_adapter_call(tmp_path):
    from core.runtime_validation import run_runtime_validation, validate_runtime_summary

    root = good_runtime_root(tmp_path)
    summary = run_runtime_validation(root, write_outputs=True)

    assert summary["result"] == "pass"
    assert (root / "runtime/runtime-summary.json").is_file()
    assert (root / "runtime/runtime-log.jsonl").is_file()
    assert validate_runtime_summary(root)["result"] == "pass"


def test_runtime_validation_fails_missing_instructions(tmp_path):
    from core.runtime_validation import run_runtime_validation

    root = tmp_path / "demo_1"
    root.mkdir()
    summary = run_runtime_validation(root)

    assert summary["result"] == "fail"
    assert any("missing instructions.json" in err for err in summary["errors"])


def test_runtime_validation_fails_missing_ts_file(tmp_path):
    from core.runtime_validation import run_runtime_validation

    root = good_runtime_root(tmp_path, omit={"ability_ts"})
    summary = run_runtime_validation(root)

    assert summary["result"] == "fail"
    assert any("ts_files missing file" in err or "ability_module_export missing file" in err for err in summary["errors"])


def test_runtime_validation_fails_missing_mcp_adjudication(tmp_path):
    from core.runtime_validation import run_runtime_validation

    root = good_runtime_root(tmp_path, omit={"adj_damage"})
    summary = run_runtime_validation(root)

    assert summary["result"] == "fail"
    assert any("adjudication" in err and "missing file" in err for err in summary["errors"])


def test_runtime_validation_fails_missing_runtime_mapping(tmp_path):
    from core.runtime_validation import run_runtime_validation

    root = good_runtime_root(tmp_path, omit={"runtime_mapping"})
    summary = run_runtime_validation(root)

    assert summary["result"] == "fail"
    assert any("runtime_mapping_path missing file" in err for err in summary["errors"])


def test_runtime_validation_fails_unknown_driver(tmp_path):
    from core.runtime_validation import run_runtime_validation

    root = good_runtime_root(tmp_path)
    data = load_instructions(root)
    data["evaluation_instructions"][0]["driver"] = "static_trace_only"
    save_instructions(root, data)
    summary = run_runtime_validation(root)

    assert summary["result"] == "fail"
    assert any("unknown runtime validation driver" in err for err in summary["errors"])


def test_runtime_validation_fails_unknown_expected_type(tmp_path):
    from core.runtime_validation import run_runtime_validation

    root = good_runtime_root(tmp_path)
    data = load_instructions(root)
    data["evaluation_instructions"][0]["expected"][0]["type"] = "state_changed"
    save_instructions(root, data)
    summary = run_runtime_validation(root)

    assert summary["result"] == "fail"
    assert any("unknown runtime expected type" in err for err in summary["errors"])


def test_run_workflow_runtime_validation_failure_returns_nonzero(tmp_path, monkeypatch):
    from core import workflow_runner

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "1.txt").write_text("smoke prompt", encoding="utf-8")
    output_dir = tmp_path / "output"

    from core import bundle_runner

    runtime_config = tmp_path / "runtime.json"
    runtime_config.write_text(json.dumps({
        "scene_spawn_manifest": {
            "allow_fixture": True,
            "fixture_path": "tests/fixtures/scene-spawn-manifest.valid.json"
        }
    }), encoding="utf-8")

    monkeypatch.setattr(bundle_runner, "run_runtime_validation", lambda demo_output_dir, write_outputs=True: {"result": "fail", "errors": ["boom"]})
    monkeypatch.setattr(workflow_runner, "WORKFLOW_FINISH_LOG_PATH", tmp_path / "demo_finish_log.txt")

    args = SimpleNamespace(
        config=str(runtime_config),
        workflow="config/workflows/puerts_ts.json",
        llm_profile="scripted_smoke",
        input_dir=str(input_dir),
        output_dir=str(output_dir),
        run_runtime_validation=True,
    )

    assert workflow_runner.run_workflow(args) == 1
