from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from core.validation.common import WORKFLOW_NODE_ORDER, is_safe_relative_path

# Port names are the explicit typed contracts between nodes.  A bundle carries
# the accumulated ports; a node may only render prompts from the ports declared
# by its workflow config entry.
NODE_OUTPUT_PORTS: dict[str, str] = {
    "SceneAndGameplaySplitter": "scene_gameplay_split",
    "EntityAbilityBehaviorPlanner": "entity_behavior",
    "ThinGameplayFlowPlanner": "thin_flow",
    "EncounterSpecPlanner": "encounter_spec",
    "UEApiMCPFeasibilitySearcher": "ue_api_feasibility",
    "PuerTSRuntimeMappingCompiler": "runtime_mapping",
    "TypeScriptImplementationSlotProjector": "ts_analyzer",
    "TypeScriptInteractiveTemplatePlanner": "interactive_ts_plan",
    "TypeScriptRuntimeTemplatePlanner": "typescript_codegen",
    "StaticEvaluationPlanBuilder": "evaluation_instructions",
}
PORT_TO_NODE: dict[str, str] = {port: node for node, port in NODE_OUTPUT_PORTS.items()}

# These defaults mirror the real implementation dependencies of the current
# nodes.  Workflow JSON is the public contract; these defaults keep old or
# test-created workflow variants usable and make missing declarations loud.
DEFAULT_NODE_INPUT_PORTS: dict[str, list[str]] = {
    "SceneAndGameplaySplitter": ["user_prompt"],
    "EntityAbilityBehaviorPlanner": ["user_prompt", "scene_gameplay_split"],
    "ThinGameplayFlowPlanner": ["user_prompt", "entity_behavior"],
    "EncounterSpecPlanner": ["entity_behavior", "thin_flow", "scene_spawn_manifest"],
    "UEApiMCPFeasibilitySearcher": ["thin_flow"],
    "PuerTSRuntimeMappingCompiler": ["entity_behavior", "thin_flow", "ue_api_feasibility"],
    "TypeScriptImplementationSlotProjector": ["entity_behavior", "runtime_mapping"],
    "TypeScriptInteractiveTemplatePlanner": ["entity_behavior", "runtime_mapping", "ts_analyzer"],
    "TypeScriptRuntimeTemplatePlanner": ["entity_behavior", "runtime_mapping", "ts_analyzer", "interactive_ts_plan"],
    "StaticEvaluationPlanBuilder": [
        "scene_gameplay_split",
        "entity_behavior",
        "thin_flow",
        "encounter_spec",
        "ue_api_feasibility",
        "runtime_mapping",
        "ts_analyzer",
        "interactive_ts_plan",
        "typescript_codegen",
    ],
}
DEFAULT_NODE_OUTPUT_PORTS: dict[str, list[str]] = {node: [port] for node, port in NODE_OUTPUT_PORTS.items()}

JSON_PORTS = set(NODE_OUTPUT_PORTS.values()) | {"scene_spawn_manifest"}
TEXT_PORTS = {"user_prompt"}


def port_kind(port: str) -> str:
    return "text" if port in TEXT_PORTS else "json"


def default_port_relpath(port: str) -> str:
    suffix = "txt" if port_kind(port) == "text" else "json"
    return f"ports/{port}.{suffix}"


def normalize_path(rel: str) -> str:
    if not is_safe_relative_path(rel):
        raise ValueError(f"unsafe bundle-relative path: {rel}")
    return rel.replace("\\", "/")


@dataclass
class RunBundle:
    root: Path
    manifest: dict[str, Any]

    @classmethod
    def create(cls, root: str | Path, *, workflow: str, user_prompt: str, demo_name: str = "") -> "RunBundle":
        bundle = cls(Path(root).resolve(), {
            "schema_version": "autoue-run-bundle/v1",
            "workflow": workflow,
            "current_node": None,
            "demo_name": demo_name,
            "ports": {},
            "artifacts": {},
            "node_outputs": {},
            "trace": {"completed_nodes": [], "node_runs": [], "token_usage": {}, "execution_time": {}, "validation": {}},
        })
        bundle.root.mkdir(parents=True, exist_ok=True)
        bundle.write_port_text("user_prompt", user_prompt, producer="initial")
        bundle.save()
        return bundle

    @classmethod
    def load(cls, root: str | Path) -> "RunBundle":
        root_path = Path(root).resolve()
        manifest_path = root_path / "manifest.json"
        if manifest_path.exists():
            return cls(root_path, json.loads(manifest_path.read_text(encoding="utf-8")))
        return cls._import_legacy(root_path)

    @classmethod
    def _import_legacy(cls, root: Path) -> "RunBundle":
        prompt_path = root / "ports" / "user_prompt.txt"
        if not prompt_path.exists():
            prompt_path = root / "MyPCG" / "eval" / "Prompt.txt"
        user_prompt = prompt_path.read_text(encoding="utf-8", errors="replace") if prompt_path.exists() else ""
        bundle = cls(root, {
            "schema_version": "autoue-run-bundle/v1",
            "workflow": "",
            "current_node": None,
            "demo_name": root.name,
            "ports": {},
            "artifacts": {},
            "node_outputs": {},
            "trace": {"completed_nodes": [], "node_runs": [], "token_usage": {}, "execution_time": {}, "validation": {}},
        })
        if user_prompt:
            bundle.write_port_text("user_prompt", user_prompt, producer="legacy_import")
        llm_dir = root / "llm_outputs"
        if llm_dir.exists():
            for node in WORKFLOW_NODE_ORDER:
                path = llm_dir / f"{node}.txt"
                if not path.exists():
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                port = NODE_OUTPUT_PORTS.get(node)
                if port:
                    bundle.write_port_text(port, text, producer=node, kind="json")
                    bundle.manifest.setdefault("node_outputs", {})[node] = {
                        "port": port,
                        "path": default_port_relpath(port),
                        "raw_path": f"llm_outputs/{node}.txt",
                    }
                    bundle._write_legacy_llm_output(node, text)
                    if node not in bundle.manifest["trace"].setdefault("completed_nodes", []):
                        bundle.manifest["trace"]["completed_nodes"].append(node)
        return bundle

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def port_relpath(self, port: str) -> str:
        entry = self.manifest.get("ports", {}).get(port)
        if isinstance(entry, Mapping) and isinstance(entry.get("path"), str):
            return normalize_path(entry["path"])
        return default_port_relpath(port)

    def port_path(self, port: str) -> Path:
        return self.root / self.port_relpath(port)

    def has_port(self, port: str) -> bool:
        return self.port_path(port).exists()

    def require_ports(self, ports: list[str], *, node_name: str) -> None:
        missing = [port for port in ports if not self.has_port(port)]
        if missing:
            raise RuntimeError(f"{node_name} missing input ports: {missing}")

    def read_port_text(self, port: str) -> str:
        path = self.port_path(port)
        if not path.exists():
            raise FileNotFoundError(f"bundle port does not exist: {port} at {path}")
        return path.read_text(encoding="utf-8", errors="replace")

    def read_port_json(self, port: str) -> Any:
        return json.loads(self.read_port_text(port))

    def write_port_text(self, port: str, text: str, *, producer: str, kind: str | None = None) -> None:
        kind = kind or port_kind(port)
        rel = default_port_relpath(port)
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.manifest.setdefault("ports", {})[port] = {"path": rel, "kind": kind, "producer": producer}

    def write_port_json(self, port: str, data: Any, *, producer: str) -> None:
        self.write_port_text(port, json.dumps(data, ensure_ascii=False, indent=2), producer=producer, kind="json")

    def node_outputs_text(self) -> dict[str, str]:
        outputs: dict[str, str] = {}
        for node, port in NODE_OUTPUT_PORTS.items():
            raw = self.root / "llm_outputs" / f"{node}.txt"
            if raw.exists():
                outputs[node] = raw.read_text(encoding="utf-8", errors="replace")
                continue
            if self.has_port(port):
                outputs[node] = self.read_port_text(port)
        return outputs

    def _write_legacy_llm_output(self, node_name: str, output_text: str) -> str:
        rel = f"llm_outputs/{node_name}.txt"
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output_text, encoding="utf-8")
        return rel

    def record_node_output(
        self,
        *,
        node_name: str,
        output_port: str,
        output_text: str,
        token_usage: Mapping[str, Any] | None = None,
        execution_time: float | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        validation: Mapping[str, Any] | None = None,
    ) -> None:
        self.write_port_text(output_port, output_text, producer=node_name, kind="json")
        raw_rel = self._write_legacy_llm_output(node_name, output_text)
        self.manifest.setdefault("node_outputs", {})[node_name] = {
            "port": output_port,
            "path": self.port_relpath(output_port),
            "raw_path": raw_rel,
        }
        trace = self.manifest.setdefault("trace", {})
        completed = trace.setdefault("completed_nodes", [])
        if node_name not in completed:
            completed.append(node_name)
        trace.setdefault("node_runs", []).append({"node": node_name, "output_port": output_port})
        if token_usage is not None:
            trace.setdefault("token_usage", {})[node_name] = dict(token_usage)
        if execution_time is not None:
            trace.setdefault("execution_time", {})[node_name] = execution_time
        if validation is not None:
            trace.setdefault("validation", {})[node_name] = dict(validation)
        self.manifest["current_node"] = node_name
        for artifact in artifacts or []:
            self.add_artifact(node_name, artifact)

    def add_artifact(self, node_name: str, artifact: Mapping[str, Any]) -> None:
        rel = artifact.get("path")
        if not isinstance(rel, str):
            return
        rel = normalize_path(rel)
        self.manifest.setdefault("artifacts", {})[rel] = {
            "producer": node_name,
            "kind": artifact.get("kind", "artifact"),
            "exists": (self.root / rel).exists(),
        }

    def write_trace_file(self) -> None:
        trace_dir = self.root / "trace"
        trace_dir.mkdir(parents=True, exist_ok=True)
        trace_dir.joinpath("node_runs.json").write_text(
            json.dumps(self.manifest.get("trace", {}), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save_checkpoint(self, index: int, node_name: str) -> Path:
        dest = self.root / "bundles" / f"{index:02d}-{node_name}"
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        for name in ["manifest.json", "ports", "trace", "llm_outputs"]:
            src = self.root / name
            if not src.exists():
                continue
            target = dest / name
            if src.is_dir():
                shutil.copytree(src, target)
            else:
                shutil.copy2(src, target)
        return dest

    def copy_to(self, dest: str | Path) -> "RunBundle":
        dest_path = Path(dest).resolve()
        if dest_path == self.root:
            return self
        try:
            dest_path.relative_to(self.root)
            raise RuntimeError(f"output bundle must not be inside input bundle: {dest_path}")
        except ValueError:
            pass
        if dest_path.exists():
            shutil.rmtree(dest_path)
        shutil.copytree(self.root, dest_path, ignore=shutil.ignore_patterns("bundles", "__pycache__", ".pytest_cache"))
        copied = RunBundle.load(dest_path)
        copied.save()
        return copied
