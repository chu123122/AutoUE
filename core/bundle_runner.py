from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from langchain_core.messages import HumanMessage

from core.BaseLLMGraph import BaseLLMGraph
from core.BaseLLMNode import GraphState
from core.bundle import DEFAULT_NODE_INPUT_PORTS, DEFAULT_NODE_OUTPUT_PORTS, NODE_OUTPUT_PORTS, RunBundle
from core.bundle_validation import resolve_declared_artifacts, validate_bundle_node
from core.config import iter_enabled_nodes, load_llm_profiles, load_runtime_config, load_workflow_config, resolve_configured_path, resolve_copy_dirs, repo_path
from core.llm_factory import create_llm
from core.runtime_validation import run_runtime_validation, runtime_validation_config
from core.workflow_loader import create_node_from_spec, read_prompt_text

SCENE_SPAWN_MANIFEST_REL = Path("flow") / "scene-spawn-manifest.json"


def copy_all_dirs_to_output(demo_output_dir: Path, copy_dirs: list[Path]):
    for src_dir in copy_dirs:
        if not src_dir.exists():
            print(f"[WARN] Source directory does not exist, skipping: {src_dir}")
            continue
        dst_dir = demo_output_dir / src_dir.name
        print(f"[DEBUG] Copying {src_dir} -> {dst_dir}")
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)


def copy_prompt_to_eval(txt_path: Path, demo_output_dir: Path):
    eval_dir = demo_output_dir / "MyPCG" / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    target_path = eval_dir / "Prompt.txt"
    if target_path.exists():
        target_path.unlink()
    shutil.copy(txt_path, target_path)
    print(f"[DEBUG] Prompt copied to {target_path}")


def is_runtime_validation_enabled(args, runtime_config: dict) -> bool:
    runtime_section = runtime_config.get("runtime_validation", {})
    config_enabled = bool(runtime_section.get("enabled", False)) if isinstance(runtime_section, dict) else False
    return bool(getattr(args, "run_runtime_validation", False) or config_enabled)


def node_inputs(spec: Mapping[str, Any]) -> list[str]:
    name = str(spec.get('name'))
    return list(spec.get('inputs') or DEFAULT_NODE_INPUT_PORTS.get(name, []))


def node_outputs(spec: Mapping[str, Any]) -> list[str]:
    name = str(spec.get('name'))
    return list(spec.get('outputs') or DEFAULT_NODE_OUTPUT_PORTS.get(name, []))


def build_bundle_nodes(runtime_config: dict, workflow_config: dict, *, llm_profile: str | None = None):
    profiles = load_llm_profiles()
    selected_profile = llm_profile or runtime_config.get("llm_profile") or profiles.get("default_profile")
    base_model = create_llm(selected_profile, profiles)
    base_graph = BaseLLMGraph(model=base_model)
    nodes = []
    specs = []
    for spec in iter_enabled_nodes(workflow_config):
        node_profile = selected_profile if llm_profile else (spec.get("llm_profile") or selected_profile)
        node_model = create_llm(node_profile, profiles) if node_profile != selected_profile else base_model
        node = create_node_from_spec(spec)
        node.set_model(node_model)
        node.input_ports = node_inputs(spec)
        node.output_ports = node_outputs(spec)
        base_graph.AddNode(node)
        nodes.append(node)
        specs.append(spec)
    return nodes, specs


def _bundle_requires_enemy_encounter(bundle: RunBundle) -> bool:
    if not bundle.has_port("entity_behavior"):
        return True
    try:
        from custom_nodes.encounter_spec_planner import _requires_enemy_encounter
        return _requires_enemy_encounter(bundle.read_port_json("entity_behavior"))
    except Exception:
        return True


def _inject_scene_spawn_manifest(bundle: RunBundle, runtime_config: dict, workflow_config: dict) -> None:
    if bundle.has_port("scene_spawn_manifest"):
        return
    target = bundle.root / SCENE_SPAWN_MANIFEST_REL
    if not target.exists():
        # Reuse the existing deterministic manifest preparation logic without
        # making Bundle depend on workflow_runner at import time.
        from core.workflow_runner import ensure_scene_spawn_manifest_for_demo
        ensure_scene_spawn_manifest_for_demo(bundle.root, runtime_config, workflow_config)
    if target.exists():
        data = json.loads(target.read_text(encoding="utf-8"))
        bundle.write_port_json("scene_spawn_manifest", data, producer="scene_spawn_manifest")
        bundle.add_artifact("scene_spawn_manifest", {"kind": "json", "path": str(SCENE_SPAWN_MANIFEST_REL).replace('\\', '/')})
        bundle.save()


def _state_from_bundle(bundle: RunBundle) -> GraphState:
    llm_outputs = bundle.node_outputs_text()
    state = GraphState(
        messages=[HumanMessage(content=bundle.read_port_text("user_prompt") if bundle.has_port("user_prompt") else "")],
        save_dir=str(bundle.root),
        llm_outputs=llm_outputs,
    )
    if bundle.has_port("scene_gameplay_split"):
        try:
            split = bundle.read_port_json("scene_gameplay_split")
            state.scene_description = split.get("scene_description", "") if isinstance(split, dict) else ""
            state.gameplay_description = split.get("gameplay_description", "") if isinstance(split, dict) else ""
        except Exception:
            pass
    return state


def execute_node(bundle: RunBundle, node, spec: Mapping[str, Any], runtime_config: dict, workflow_config: dict) -> dict[str, Any]:
    name = node.name
    inputs = node_inputs(spec)
    outputs = node_outputs(spec)
    if "scene_spawn_manifest" in inputs:
        if name == "EncounterSpecPlanner" and not _bundle_requires_enemy_encounter(bundle):
            inputs = [port for port in inputs if port != "scene_spawn_manifest"]
        else:
            _inject_scene_spawn_manifest(bundle, runtime_config, workflow_config)
    bundle.require_ports(inputs, node_name=name)
    if len(outputs) != 1:
        raise RuntimeError(f"{name} must declare exactly one output port, got {outputs}")

    node.reset()
    old_next = node.next_node
    node.next_node = None
    state = _state_from_bundle(bundle)
    result = None
    try:
        result = node.execute(state)
    finally:
        node.next_node = old_next
    output_text = state.llm_outputs.get(name, "")
    if not output_text.strip():
        raise RuntimeError(f"{name} produced empty output")
    output_port = outputs[0]
    try:
        output_data = json.loads(output_text)
    except Exception:
        output_data = {}
    artifacts = resolve_declared_artifacts(spec, output_data if isinstance(output_data, dict) else {})
    token_usage = state.node_token_usage.get(name, {})
    execution_time = state.node_execution_time.get(name, 0.0)
    bundle.record_node_output(
        node_name=name,
        output_port=output_port,
        output_text=output_text,
        token_usage=token_usage,
        execution_time=execution_time,
        artifacts=artifacts,
        validation={"result": "pass", "validator": spec.get("validator")},
    )
    bundle.write_trace_file()
    bundle.save()
    validation = validate_bundle_node(bundle, {**dict(spec), "inputs": inputs, "outputs": outputs})
    print(json.dumps({"node": name, "output_port": output_port, "validation": validation["result"]}, ensure_ascii=False))
    return {"command": result, "validation": validation}


def run_bundle_workflow(args) -> int:
    runtime = load_runtime_config(args.config)
    workflow = load_workflow_config(args.workflow, runtime)
    input_dir = Path(args.input_dir).resolve() if args.input_dir else resolve_configured_path(runtime, "input_dir")
    output_dir = Path(args.output_dir).resolve() if args.output_dir else resolve_configured_path(runtime, "output_dir")
    post_actions = runtime.get("post_actions", {})
    copy_dirs = resolve_copy_dirs(runtime)
    run_runtime = is_runtime_validation_enabled(args, runtime)
    runtime_failures: list[dict] = []

    if not input_dir.exists():
        raise FileNotFoundError(f"input_dir does not exist: {input_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    txt_files = [p for p in input_dir.iterdir() if p.suffix == ".txt" and p.stem.isdigit()]
    txt_files.sort(key=lambda p: int(p.stem))
    if not txt_files:
        print(f"[WARN] No numeric .txt prompts found in {input_dir}")
        return 0

    for txt_path in txt_files:
        demo_id = txt_path.stem
        print(f"\n[DEBUG] ===== Processing demo_{demo_id} with BundlePipelineRunner =====")
        prompt = read_prompt_text(txt_path)
        if not prompt:
            print(f"[WARN] Empty prompt, skipping: {txt_path.name}")
            continue
        demo_output_dir = output_dir / f"demo_{demo_id}"
        bundle = RunBundle.create(demo_output_dir, workflow=workflow.get("name", ""), user_prompt=prompt, demo_name=f"demo_{demo_id}")
        nodes, specs = build_bundle_nodes(runtime, workflow, llm_profile=args.llm_profile)
        for index, (node, spec) in enumerate(zip(nodes, specs), start=1):
            execute_node(bundle, node, spec, runtime, workflow)
            bundle.save_checkpoint(index, node.name)
        if post_actions.get("copy_dirs", True):
            copy_all_dirs_to_output(demo_output_dir, copy_dirs)
        if post_actions.get("copy_prompt_to_eval", True):
            copy_prompt_to_eval(txt_path, demo_output_dir)
        bundle.write_trace_file()
        bundle.save()
        if run_runtime:
            runtime_summary = run_runtime_validation(demo_output_dir, write_outputs=True)
            print(f"[DEBUG] runtime validation result for demo_{demo_id}: {runtime_summary.get('result')}")
            if runtime_summary.get("result") != "pass":
                runtime_failures.append({"demo_id": demo_id, "errors": runtime_summary.get("errors", [])})
        finish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"demo_{demo_id} finished at {finish_time}\n"
        print(f"[DEBUG] {log_line.strip()}")
        from core.workflow_runner import WORKFLOW_FINISH_LOG_PATH
        WORKFLOW_FINISH_LOG_PATH.open("a", encoding="utf-8").write(log_line)
        print(f"[DEBUG] demo_{demo_id} output completed")
    if runtime_failures:
        print(json.dumps({"runtime_validation": "fail", "failures": runtime_failures}, ensure_ascii=False, indent=2))
        return 1
    return 0


def _node_spec(workflow: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    for spec in workflow.get('nodes', []):
        if spec.get('name') == name and spec.get('enabled', True):
            return spec
    raise RuntimeError(f"enabled node not found in workflow: {name}")


def node_run(args) -> int:
    runtime = load_runtime_config(args.config)
    workflow = load_workflow_config(args.workflow, runtime)
    input_bundle = RunBundle.load(args.input_bundle)
    bundle = input_bundle.copy_to(args.output_bundle)
    nodes, specs = build_bundle_nodes(runtime, workflow, llm_profile=args.llm_profile)
    by_name = {node.name: (node, spec) for node, spec in zip(nodes, specs)}
    if args.node not in by_name:
        raise RuntimeError(f"node not found in workflow: {args.node}")
    node, spec = by_name[args.node]
    execute_node(bundle, node, spec, runtime, workflow)
    print(json.dumps({"result": "pass", "bundle": str(bundle.root), "node": args.node}, ensure_ascii=False, indent=2))
    return 0


def node_validate(args) -> int:
    runtime = load_runtime_config(args.config)
    workflow = load_workflow_config(args.workflow, runtime)
    spec = dict(_node_spec(workflow, args.node))
    spec.setdefault('inputs', node_inputs(spec))
    spec.setdefault('outputs', node_outputs(spec))
    bundle = RunBundle.load(args.bundle)
    report = validate_bundle_node(bundle, spec)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report.get('result') != 'pass' else 0


def parse_node_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Run or validate one AutoUE workflow node against a typed bundle.")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", help="Runtime config JSON. Defaults to config/local.json if present, else local.example.json.")
    common.add_argument("--workflow", help="Workflow JSON. Defaults to config value or AUTOUE_WORKFLOW.")
    common.add_argument("--llm-profile", help="Override all node LLM profiles.")
    run_p = sub.add_parser("run", parents=[common])
    run_p.add_argument("--node", required=True)
    run_p.add_argument("--input-bundle", required=True)
    run_p.add_argument("--output-bundle", required=True)
    val_p = sub.add_parser("validate", parents=[common])
    val_p.add_argument("--node", required=True)
    val_p.add_argument("--bundle", required=True)
    return parser.parse_args(argv)


def node_main(argv: list[str] | None = None) -> int:
    args = parse_node_args(argv)
    if args.subcommand == "run":
        return node_run(args)
    if args.subcommand == "validate":
        return node_validate(args)
    raise RuntimeError(f"unknown node subcommand: {args.subcommand}")
