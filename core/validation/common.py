"""Shared workflow validation helpers."""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Iterable

WORKFLOW_NODE_ORDER = [
    "SceneAndGameplaySplitter",
    "EntityAbilityBehaviorPlanner",
    "ThinGameplayFlowPlanner",
    "EncounterSpecPlanner",
    "UEApiMCPFeasibilitySearcher",
    "PuerTSRuntimeMappingPlanner",
    "TypeScriptScriptAnalyzer",
    "TypeScriptInteractiveObjectGenerator",
    "TypeScriptCodeGenerator",
    "EvaluateInstructionGenerator",
]
RUNTIME_MAPPING_PATH = "flow/05-puerts-runtime-mapping.json"
BANNED_FLOW_MARKERS = ("RetrieveModel", "PCGGraphComposer", "PCGPlanner", "LLMHttpServer")
BANNED_NATIVE_MARKERS = (
    "AInteractiveObjectBase", "CustomModules", "header_code", "source_code", "cpp_code",
    "ModuleCodeGenerator", "InteractiveObjectCodeGenerator",
)
BANNED_OUTPUT_MARKERS = BANNED_FLOW_MARKERS + BANNED_NATIVE_MARKERS
CXX_FILE_RE = re.compile(r"(?i)\.(?:h|cpp)\b")
TS_IDENT_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
ALLOWED_TEMPLATES = {
    "TypeScriptInteractiveObjectGenerator": {"interactive_object"},
    "TypeScriptCodeGenerator": {
        "ability_module",
        "runtime_bootstrap",
        "aid_runtime_orchestrator",
        "aid_character_adapter",
        "aid_gamemode_adapter",
        "aid_camera_setup",
        "scene_manifest_helper",
        "encounter_spec_data",
        "enemy_archetypes",
        "spawn_point_registry",
        "enemy_archetype_registry",
        "enemy_spawn_manager",
        "encounter_manager",
    },
}
ALLOWED_STAGES = {"Input", "Ability/Action", "SpatialQuery/HitQuery", "Damage/Resource", "Event/Result", "Feedback/HUD", "Cleanup", "Custom"}
ALLOWED_VERDICTS = {"hit", "miss"}
ALLOWED_HIT_TYPES = {"direct_hit", "indirect_hit", "none"}
ALLOWED_CARRIERS = {"template_rendered_ts", "existing_runtime_adapter", "generated_aidev_adapter", "generated_runtime_orchestrator", "blocked"}

class WorkflowValidationError(ValueError):
    pass

def strip_json_fence(text: str) -> str:
    s = text.strip()
    m = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", s, flags=re.I | re.S)
    return m.group(1).strip() if m else s

def parse_node_json(node_name: str, text: str) -> Any:
    try:
        return json.loads(strip_json_fence(text))
    except Exception as exc:
        raise WorkflowValidationError(f"{node_name}: output must be valid JSON: {exc}") from exc

def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)

def walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from walk_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk_strings(v)

def walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from walk_keys(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk_keys(v)

def validate_common_workflow_contract(node: str, data: Any) -> None:
    if not isinstance(data, dict):
        raise WorkflowValidationError(f"{node}: output JSON must be an object")
    for text in walk_strings(data):
        if CXX_FILE_RE.search(text):
            raise WorkflowValidationError(f"{node}: native code filename markers are forbidden: {text}")
        for marker in BANNED_OUTPUT_MARKERS:
            if marker in text:
                raise WorkflowValidationError(f"{node}: banned legacy workflow marker appears in output: {marker}")

def require_list(node: str, obj: dict[str, Any], key: str, *, non_empty: bool = False) -> list[Any]:
    value = obj.get(key)
    if not isinstance(value, list):
        raise WorkflowValidationError(f"{node}: expected list at {key}")
    if non_empty and not value:
        raise WorkflowValidationError(f"{node}: expected non-empty list at {key}")
    return value

def require_dict(node: str, obj: dict[str, Any], key: str) -> dict[str, Any]:
    value = obj.get(key)
    if not isinstance(value, dict):
        raise WorkflowValidationError(f"{node}: expected object at {key}")
    return value

def require_string(node: str, obj: dict[str, Any], key: str, *, non_empty: bool = False) -> str:
    value = obj.get(key)
    if not isinstance(value, str):
        raise WorkflowValidationError(f"{node}: expected string at {key}")
    if non_empty and not value.strip():
        raise WorkflowValidationError(f"{node}: expected non-empty string at {key}")
    return value

def require_identifier(node: str, obj: dict[str, Any], key: str) -> str:
    value = require_string(node, obj, key, non_empty=True)
    if not TS_IDENT_RE.fullmatch(value):
        raise WorkflowValidationError(f"{node}: {key} must be a TypeScript identifier: {value}")
    return value

def is_safe_relative_path(value: str) -> bool:
    if not value or "\x00" in value:
        return False
    posix = PurePosixPath(value.replace("\\", "/"))
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or windows.root:
        return False
    return ".." not in (set(posix.parts) | set(windows.parts))

def validate_rel_path(node: str, path: str, *, label: str, suffixes: tuple[str, ...]) -> None:
    if not is_safe_relative_path(path):
        raise WorkflowValidationError(f"{node}: {label} must be relative and stay inside output root: {path}")
    if not path.lower().endswith(suffixes):
        raise WorkflowValidationError(f"{node}: {label} must end with {suffixes}: {path}")

def validate_ts_path(node: str, path: str, *, label: str) -> None:
    validate_rel_path(node, path, label=label, suffixes=(".ts", ".tsx"))

def validate_json_path(node: str, path: str, *, label: str) -> None:
    validate_rel_path(node, path, label=label, suffixes=(".json",))
