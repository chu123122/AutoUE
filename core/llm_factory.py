from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping

from core.scripted_enemy_cases import (
    SCRIPTED_ENEMY_CASES,
    candidate_query_for_case,
    encounter_for_case,
    get_scripted_enemy_case,
    thin_flow_for_case,
)


@dataclass
class SimpleChatResponse:
    content: str
    response_metadata: Dict[str, Any]


class OpenAICompatibleChatModel:
    """Tiny OpenAI-compatible chat wrapper used to avoid hard-wiring one vendor."""

    def __init__(self, *, api_key: str, base_url: str, model: str, temperature: float = 0.2, timeout: int = 120):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

    def _normalize_messages(self, messages: Iterable[Any]) -> list[dict[str, str]]:
        result = []
        for msg in messages:
            if isinstance(msg, Mapping):
                result.append({"role": str(msg.get("role", "user")), "content": str(msg.get("content", ""))})
            else:
                role = getattr(msg, "type", None) or getattr(msg, "role", None) or "user"
                if role == "human":
                    role = "user"
                if role == "ai":
                    role = "assistant"
                result.append({"role": str(role), "content": str(getattr(msg, "content", msg))})
        return result

    def invoke(self, messages: Iterable[Any]) -> SimpleChatResponse:
        payload = {"model": self.model, "messages": self._normalize_messages(messages), "temperature": self.temperature}
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return SimpleChatResponse(content=content, response_metadata={"token_usage": data.get("usage", {})})


class CodexCliChatModel:
    """LangChain-like wrapper around `codex exec`.

    This is the real LLM path for local AutoUE adaptation. It intentionally uses
    Codex CLI instead of a direct HTTP client so model/provider/auth routing stays
    in the user's current Codex runtime.
    """

    def __init__(self, *, command: str = "codex", model: str = "", cwd: str = ".", timeout: int = 900, reasoning_effort: str = ""):
        self.command = shutil.which(command) or command
        self.model = model
        self.cwd = cwd
        self.timeout = timeout
        self.reasoning_effort = reasoning_effort

    def _normalize_messages(self, messages: Iterable[Any]) -> tuple[str, str]:
        system_parts = []
        user_parts = []
        for msg in messages:
            if isinstance(msg, Mapping):
                role = str(msg.get("role", "user"))
                content = str(msg.get("content", ""))
            else:
                role = getattr(msg, "type", None) or getattr(msg, "role", None) or "user"
                if role == "human":
                    role = "user"
                if role == "ai":
                    role = "assistant"
                content = str(getattr(msg, "content", msg))
            if role == "system":
                system_parts.append(content)
            else:
                user_parts.append(f"[{role}]\n{content}")
        return "\n\n".join(system_parts), "\n\n".join(user_parts)

    def invoke(self, messages: Iterable[Any]) -> SimpleChatResponse:
        system_text, user_text = self._normalize_messages(messages)
        prompt = (
            "You are running as an LLM subcall inside the AutoUE Python workflow.\n"
            "Return only the requested final artifact. Do not run shell commands.\n"
            "Do not add explanations unless the task explicitly asks for them.\n\n"
            f"<system_prompt>\n{system_text}\n</system_prompt>\n\n"
            f"<workflow_input>\n{user_text}\n</workflow_input>\n"
        )
        with tempfile.TemporaryDirectory(prefix="autoue-codex-") as tmp:
            out_path = os.path.join(tmp, "last-message.txt")
            cmd = [
                self.command,
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--color",
                "never",
                "--output-last-message",
                out_path,
            ]
            if self.model:
                cmd.extend(["--model", self.model])
            if self.reasoning_effort:
                cmd.extend(["-c", f"model_reasoning_effort=\"{self.reasoning_effort}\""])
            if self.cwd:
                cmd.extend(["-C", self.cwd])
            cmd.append("-")
            proc = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=self.timeout,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    "codex exec failed with exit code "
                    f"{proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
                )
            if os.path.exists(out_path):
                content = open(out_path, "r", encoding="utf-8", errors="replace").read().strip()
            else:
                content = proc.stdout.strip()
            return SimpleChatResponse(
                content=content,
                response_metadata={"token_usage": {}, "provider": "codex_cli", "model": self.model or "codex-default"},
            )




class ScriptedSmokeChatModel:
    """Deterministic local model for workflow smoke tests; never calls network."""

    use_mcp_fixture = True

    def invoke(self, messages: Iterable[Any]) -> SimpleChatResponse:
        normalized = OpenAICompatibleChatModel(api_key="x", base_url="http://127.0.0.1", model="x")._normalize_messages(messages)
        system = "\n".join(m["content"] for m in normalized if m["role"] == "system")
        rf = ["action_dispatcher", "behavior_orchestrator", "condition_checker", "entity_registry", "movement_runtime", "state_blackboard", "trigger_router", "world_adapter"]
        df = ["enemy_encounter"]
        behavior_id = "hazard.behavior.freeze_on_overlap"
        capability_ids = ["hazard.sensor.detect_overlap", "hazard.effect.apply_freeze", "vfx.visibility.set_visible_while_state", "camera.feedback.camera_impulse"]
        flow_id = "flow_hazard_behavior_freeze_on_overlap"
        runtime_mapping_path = "flow/05-puerts-runtime-mapping.json"
        runtime_owner = "TypeScript/content/generated/AutoUEBehaviorSpec.generated.ts"
        interactive_path = "TypeScript/content/generated/interactive/FreezeTrapInteractable.ts"
        ports = ["input.action_binding", "primitive.on_component_begin_overlap", "component.set_visibility", "camera.update_view_target"]
        raw = {p: f"flow/04-ue-api-mcp/raw/{p}.raw.json" for p in ports}
        adj = {p: f"flow/04-ue-api-mcp/adjudication/{p}.json" for p in ports}
        trace = {"entity_id": "freeze_trap", "behavior_id": behavior_id, "flow_id": flow_id, "engine_port_ids": ports, "adjudication_paths": [adj[p] for p in ports], "runtime_mapping_path": runtime_mapping_path, "ts_files": [interactive_path, runtime_owner]}
        base = {"entity_id": "freeze_trap", "behavior_id": behavior_id, "flow_id": flow_id, "runtime_mapping_path": runtime_mapping_path, "action_label": "overlap triggers freeze", "target_label": "Player", "result_label": "player frozen with VFX and camera shake", "runtime_features": rf, "disabled_features": df}
        if "SCHEMA: StaticEvaluationPlanBuilder" in system:
            content = json.dumps({"evaluation_instructions": [{"step_id": 1, "action": "trigger_freeze_trap", "target": "FreezeTrap", "description": "Statically validate the behavior-driven freeze trap adapter_call trace without launching PIE.", "driver": "adapter_call", "executor_action": "call_behavior", "expected": [{"type": "static_trace_present", "key": "ability_module_export", "expected_value": "getAutoUEBehaviorSpec"}, {"type": "static_trace_present", "key": "interactive_adapter_export", "expected_value": "runFreezeTrapInteraction"}, {"type": "static_trace_present", "key": "engine_ports_mapped", "expected_value": ports}], "trace": trace}], "coverage": [trace]})
        elif "SCHEMA: TypeScriptRuntimeTemplatePlanner" in system:
            support = [
                ("runtime_feature_manifest", "TypeScript/content/generated/AutoUERuntimeFeatureManifest.ts", "getAutoUERuntimeFeatureManifest", "AutoUERuntimeFeatureManifestContext"),
                ("input_harness_runtime", "TypeScript/content/generated/AutoUEInputHarnessRuntime.ts", "createAutoUEInputHarnessRuntime", "AutoUEInputHarnessRuntimeContext"),
                ("movement_runtime", "TypeScript/content/generated/AutoUEMovementRuntime.ts", "createAutoUEMovementRuntime", "AutoUEMovementRuntimeContext"),
                ("trap_runtime", "TypeScript/content/generated/AutoUETrapRuntime.ts", "createAutoUETrapRuntime", "AutoUETrapRuntimeContext"),
                ("vfx_runtime", "TypeScript/content/generated/AutoUEVfxRuntime.ts", "createAutoUEVfxRuntime", "AutoUEVfxRuntimeContext"),
                ("aid_runtime_orchestrator", "TypeScript/content/generated/AutoUEGeneratedRuntime.ts", "runAutoUEGeneratedRuntime", "AutoUEGeneratedRuntimeContext"),
                ("aid_character_adapter", "TypeScript/AutoUEGeneratedCharacterAdapter.ts", "AutoUEGeneratedCharacterAdapter", "AutoUEGeneratedCharacterAdapterContext"),
                ("aid_gamemode_adapter", "TypeScript/AutoUEGeneratedGameModeAdapter.ts", "AutoUEGeneratedGameModeAdapter", "AutoUEGeneratedGameModeAdapterContext"),
                ("aid_camera_setup", "TypeScript/content/generated/AutoUEGeneratedCameraHelper.ts", "setupAutoUEGeneratedCamera", "AutoUEGeneratedCameraOptions"),
                ("scene_manifest_helper", "TypeScript/content/generated/AutoUEGeneratedSceneManifest.ts", "getAutoUEGeneratedSceneManifest", "AutoUEGeneratedSceneManifestContext"),
            ]
            template_inputs = [{"template": "ability_module", "path": runtime_owner, **base, "export_name": "getAutoUEBehaviorSpec", "interface_name": "AutoUEBehaviorSpecContext"}]
            template_inputs += [{"template": t, "path": path, "export_name": export, "interface_name": iface, **base} for t, path, export, iface in support]
            content = json.dumps({"runtime_features": rf, "disabled_features": df, "template_inputs": template_inputs, "behavior_traces": [{"entity_id": "freeze_trap", "behavior_id": behavior_id, "flow_id": flow_id, "runtime_mapping_path": runtime_mapping_path, "file_path": runtime_owner, "export_name": "getAutoUEBehaviorSpec"}], "consumed_interactive_files": [interactive_path], "validation_notes": ["behavior-driven runtime; enemy_encounter disabled"]})
        elif "SCHEMA: TypeScriptInteractiveTemplatePlanner" in system:
            content = json.dumps({"template_inputs": [{"template": "interactive_object", "path": interactive_path, "entity_id": "freeze_trap", "behavior_id": behavior_id, "flow_id": flow_id, "runtime_mapping_path": runtime_mapping_path, "export_name": "runFreezeTrapInteraction", "interface_name": "FreezeTrapInteractionContext", "action_label": "overlap triggers freeze", "target_label": "Player", "result_label": "player frozen with VFX and camera shake"}], "behavior_traces": [{"entity_id": "freeze_trap", "behavior_id": behavior_id, "flow_id": flow_id, "runtime_mapping_path": runtime_mapping_path, "file_path": interactive_path, "export_name": "runFreezeTrapInteraction"}], "validation_notes": ["scripted smoke interactive trap object template"]})
        elif "SCHEMA: TypeScriptImplementationSlotProjector" in system:
            content = json.dumps({"typescript_sources": [{"path": runtime_owner, "role": "runtime_owner", "notes": "runtime_owner from freeze trap mapping"}], "implementation_slots": [{"entity_id": "freeze_trap", "behavior_id": behavior_id, "flow_id": flow_id, "runtime_mapping_path": runtime_mapping_path, "target_ts_file": runtime_owner, "reason": "scripted smoke runtime mapping"}], "missing_slots": []})
        elif "SCHEMA: PuerTSRuntimeMappingCompiler" in system:
            port_rows = [("input.action_binding", "InputHarnessRuntime.read", "UE.PlayerController.IsInputKeyDown"), ("primitive.on_component_begin_overlap", "TrapRuntime.tickOverlapRadius", "UE.PrimitiveComponent.OnComponentBeginOverlap"), ("component.set_visibility", "VfxRuntime.setFrozenVisible", "UE.SceneComponent.SetVisibility"), ("camera.update_view_target", "CameraHelper.updateAutoUEGeneratedSideCamera", "UE.CameraComponent.K2_SetWorldLocation")]
            content = json.dumps({"runtime_mapping_path": runtime_mapping_path, "runtime_features": rf, "disabled_features": df, "mappings": [{"entity_id": "freeze_trap", "behavior_id": behavior_id, "flow_id": flow_id, "runtime_owner": runtime_owner, "implementation_carrier": "template_rendered_ts", "selected_runtime_owner": "FreezeTrapBehaviorRuntime", "existing_framework_candidates": ["TypeScriptRuntimeTemplatePlanner behavior feature modules", "AIDev TypeScript Blueprint adapter"], "why_not_existing_framework": "scripted smoke composes trap/state_blackboard/vfx/camera modules and disables enemy encounter", "temporary_or_canonical": "temporary", "migration_path": "replace scripted constants with behavior-derived module params after runtime validation", "engine_port_mappings": [{"engine_port_id": p, "adjudication_path": adj[p], "adapter_or_helper": h, "verdict": "hit", "evidence_symbols": [sym]} for p, h, sym in port_rows], "thin_contracts": ["read input", "detect trap overlap", "write player.effects.frozen", "show freeze VFX", "shake side camera"], "ability_binding": "behavior_spec:hazard.behavior.freeze_on_overlap", "verification_evidence": ["adapter_call can invoke freeze trap behavior", "enemy_encounter disabled"]}], "blocked_mappings": []})
        elif "SCHEMA: EncounterSpecPlanner" in system:
            content = json.dumps({"schema_version": "autoue-encounter-spec/v1", "encounters": []})
        elif "SCHEMA: UEApiMCPFeasibilitySearcher" in system:
            symbols = {"input.action_binding": "UE.PlayerController.IsInputKeyDown", "primitive.on_component_begin_overlap": "UE.PrimitiveComponent.OnComponentBeginOverlap", "component.set_visibility": "UE.SceneComponent.SetVisibility", "camera.update_view_target": "UE.CameraComponent.K2_SetWorldLocation"}
            content = json.dumps({"queries": [{"engine_port_id": p, "flow_ids": [flow_id], "behavior_ids": [behavior_id], "query": f"Unreal Engine PuerTS gameplay API for {p}", "raw_path": raw[p], "adjudication_path": adj[p], "verdict": "hit", "hit_type": "direct_hit", "evidence_symbols": [symbols[p]], "notes": "scripted smoke hit"} for p in ports], "summary": {"all_required_ports_hit": True, "blocked_engine_ports": []}})
        elif "SCHEMA: ThinGameplayFlowPlanner" in system:
            content = json.dumps({"flows": [{"flow_id": flow_id, "entity_id": "freeze_trap", "source_behavior_id": behavior_id, "stages": [{"stage": "Input", "contract": "read player movement/reset harness input", "inputs": ["input"], "outputs": ["intent"], "engine_ports": ["input.action_binding"]}, {"stage": "SpatialQuery/HitQuery", "contract": "detect player entering freeze trap radius", "inputs": ["player location", "trap radius"], "outputs": ["trap triggered"], "engine_ports": ["primitive.on_component_begin_overlap"]}, {"stage": "Event/Result", "contract": "write player.effects.frozen and block movement for a duration", "inputs": ["trap triggered"], "outputs": ["player.effects.frozen active"], "engine_ports": ["primitive.on_component_begin_overlap"]}, {"stage": "Feedback/HUD", "contract": "show freeze VFX and shake side camera while frozen", "inputs": ["player.effects.frozen active"], "outputs": ["visible VFX", "camera impulse"], "engine_ports": ["component.set_visibility", "camera.update_view_target"]}], "verification": ["IceTrapTriggered", "StateWritten player.effects.frozen", "enemy_encounter disabled"]}]})
        elif "SCHEMA: EntityAbilityBehaviorPlanner" in system:
            content = json.dumps({"selected_entity_ids": ["freeze_trap", "freeze_vfx", "side_camera"], "selected_capability_ids": capability_ids, "selected_behavior_ids": [behavior_id]})
        elif "SCHEMA: SceneAndGameplaySplitter" in system:
            content = json.dumps({"scene_description": "A tiny side-scroller test room with a freeze trap and exit.", "gameplay_description": "The player moves into a freeze trap, gets frozen, sees VFX/camera feedback, then exits after thawing."})
        else:
            content = json.dumps({"ok": True, "note": "scripted smoke output"})
        return SimpleChatResponse(content=content, response_metadata={"token_usage": {"input_tokens": 0, "output_tokens": 0}})


class ScriptedEnemyChatModel:
    """Deterministic enemy model for end-to-end enemy main-chain smoke tests."""

    use_mcp_fixture = True

    def __init__(self, case: str):
        self.case = case
        self.scripted_enemy_case = case
        self.spec = get_scripted_enemy_case(case)

    def _normalize(self, messages: Iterable[Any]) -> tuple[str, str]:
        normalized = OpenAICompatibleChatModel(api_key="x", base_url="http://127.0.0.1", model="x")._normalize_messages(messages)
        system = "\n".join(m["content"] for m in normalized if m["role"] == "system")
        user = "\n".join(m["content"] for m in normalized if m["role"] != "system")
        return system, user

    def _spawn_group_from_input(self, user: str) -> str:
        decoder = json.JSONDecoder()
        groups: list[str] = []
        for index, char in enumerate(user):
            if char != "{":
                continue
            try:
                data, _end = decoder.raw_decode(user[index:])
            except Exception:
                continue
            if not isinstance(data, dict) or data.get("schema_version") != "autoue-scene-spawn-manifest/v1":
                continue
            for group in data.get("spawn_groups", []):
                if isinstance(group, dict) and isinstance(group.get("spawn_group"), str) and group["spawn_group"]:
                    groups.append(group["spawn_group"])
        if "room_01_guard" in groups:
            return "room_01_guard"
        if groups:
            return groups[0]
        raise RuntimeError("ScriptedEnemyChatModel EncounterSpecPlanner requires a non-empty scene-spawn-manifest spawn_groups list")

    def _ue_api_output(self) -> dict[str, Any]:
        thin = thin_flow_for_case(self.case)
        seen: dict[str, dict[str, Any]] = {}
        for flow in thin.get("flows", []):
            for stage in flow.get("stages", []):
                for port in stage.get("engine_ports", []):
                    row = seen.setdefault(
                        port,
                        {
                            "engine_port_id": port,
                            "flow_ids": [],
                            "behavior_ids": [],
                            "query": f"Unreal Engine PuerTS gameplay API for {port}",
                            "raw_path": f"flow/04-ue-api-mcp/raw/{port}.raw.json",
                            "adjudication_path": f"flow/04-ue-api-mcp/adjudication/{port}.json",
                            "verdict": "hit",
                            "hit_type": "direct_hit",
                            "evidence_symbols": [],
                            "notes": "scripted enemy hit",
                        },
                    )
                    flow_id = flow.get("flow_id")
                    behavior_id = flow.get("source_behavior_id")
                    if flow_id and flow_id not in row["flow_ids"]:
                        row["flow_ids"].append(flow_id)
                    if behavior_id and behavior_id not in row["behavior_ids"]:
                        row["behavior_ids"].append(behavior_id)
                    symbol = {
                        "actor.spawn": "UE.World.SpawnActor",
                        "actor.get_distance_to": "UE.Actor.GetDistanceTo",
                        "actor.set_actor_location": "UE.Actor.K2_SetActorLocation",
                        "kismet.sphere_trace_single": "UE.KismetSystemLibrary.SphereTraceSingle",
                        "gameplay_statics.apply_damage": "UE.GameplayStatics.ApplyDamage",
                        "projectile.spawn": "UE.World.SpawnActor",
                        "actor.destroy": "UE.Actor.K2_DestroyActor",
                        "actor.get_forward_vector": "UE.Actor.GetActorForwardVector",
                        "actor.on_take_any_damage": "UE.Actor.OnTakeAnyDamage",
                        "actor.on_destroyed": "UE.Actor.OnDestroyed",
                        "encounter.alive_count": "AutoUE.EnemyRegistry.aliveCount",
                    }.get(port, "UE.Actor")
                    if symbol not in row["evidence_symbols"]:
                        row["evidence_symbols"].append(symbol)
        return {"queries": list(seen.values()), "summary": {"all_required_ports_hit": True, "blocked_engine_ports": []}}

    def invoke(self, messages: Iterable[Any]) -> SimpleChatResponse:
        system, user = self._normalize(messages)
        spec = self.spec
        if "SCHEMA: SceneAndGameplaySplitter" in system:
            content = {
                "scene_description": f"A deterministic side-scroller test room with a {spec.entity_ids[0]} enemy encounter.",
                "gameplay_description": f"Spawn one {spec.entity_ids[0]} on level start and validate visible enemy combat phases.",
            }
        elif "SCHEMA: EntityAbilityBehaviorPlanner" in system:
            content = spec.selection
        elif "SCHEMA: ThinGameplayFlowPlanner" in system:
            content = thin_flow_for_case(self.case)
        elif "SCHEMA: EncounterSpecPlanner" in system:
            content = encounter_for_case(self.case, self._spawn_group_from_input(user))
        elif "SCHEMA: UEApiMCPFeasibilitySearcher" in system:
            content = self._ue_api_output()
        else:
            content = {"ok": True, "note": f"scripted enemy output for {self.case}"}
        return SimpleChatResponse(
            content=json.dumps(content, ensure_ascii=False),
            response_metadata={"token_usage": {"input_tokens": 0, "output_tokens": 0}, "provider": "scripted_enemy", "case": self.case},
        )


def _env_or_default(profile: Mapping[str, Any], env_key: str, default_key: str = "", required: bool = False) -> str:
    env_name = profile.get(env_key)
    value = os.getenv(env_name, "") if env_name else ""
    if not value and default_key:
        value = str(profile.get(default_key, ""))
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {env_name}")
    return value


def create_llm(profile_name: str, profiles_config: Mapping[str, Any]):
    profiles = profiles_config.get("profiles", {})
    if profile_name not in profiles:
        raise KeyError(f"LLM profile not found: {profile_name}")
    profile = profiles[profile_name]
    provider = profile.get("provider")
    temperature = float(profile.get("temperature", 0.2))
    if provider == "scripted_smoke":
        return ScriptedSmokeChatModel()
    if provider == "scripted_enemy":
        case = str(profile.get("case") or "")
        if case not in SCRIPTED_ENEMY_CASES:
            raise ValueError(f"scripted_enemy profile requires case in {sorted(SCRIPTED_ENEMY_CASES)}; got {case!r}")
        return ScriptedEnemyChatModel(case)

    if provider == "codex_cli":
        command = os.getenv(profile.get("command_env", "CODEX_CLI_PATH"), "") or profile.get("command", "codex")
        model = os.getenv(profile.get("model_env", "CODEX_MODEL"), "") or profile.get("default_model", "")
        cwd = os.getenv(profile.get("cwd_env", "CODEX_WORKDIR"), "") or profile.get("cwd", ".")
        timeout = int(os.getenv(profile.get("timeout_env", "CODEX_AGENT_TIMEOUT_SEC"), "") or profile.get("timeout", 900))
        reasoning_effort = os.getenv(profile.get("reasoning_effort_env", "CODEX_REASONING_EFFORT"), "") or profile.get("reasoning_effort", "")
        return CodexCliChatModel(command=command, model=model, cwd=cwd, timeout=timeout, reasoning_effort=reasoning_effort)

    if provider == "openai_compatible":
        api_key = _env_or_default(profile, "api_key_env", required=True)
        base_url = _env_or_default(profile, "base_url_env", "default_base_url", required=True)
        model = _env_or_default(profile, "model_env", "default_model", required=True)
        return OpenAICompatibleChatModel(api_key=api_key, base_url=base_url, model=model, temperature=temperature)
    raise ValueError(f"Unsupported LLM provider: {provider}")
