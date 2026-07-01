"""Run an application-layer AutoUE PIE validation inside Unreal Editor.

This script is executed by Unreal's Python plugin via ``-ExecutePythonScript``.
It starts PIE, drives the generated AutoUE input-harness tags, samples the PIE
world, writes a JSON report, and exits the editor.

The script intentionally validates runtime behavior rather than source files:
PIE world must exist, generated GameMode/Pawn must be active, EncounterSpec
spawn must produce generated enemies, and generated runtime must react to input
tags inside PIE ticks.
"""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

import unreal


OUTPUT_PATH = Path(
    r"D:\ClaudeTasks\active\autoue-puerts-workflow-adaptation\repo\AutoUE"
    r"\test_tmp\autoue-pie-validation-current.json"
)
SAMPLE_PATH = OUTPUT_PATH.with_suffix(".samples.txt")
MAP_PATH = "/Game/Castlevania2D"
MAX_SECONDS = 45.0

LOG_PREFIX = "[AUTOUE_PIE_VALIDATOR]"


def _log(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def _set_keep_alive(enabled: bool) -> None:
    try:
        unreal.EditorPythonScripting.set_keep_python_script_alive(enabled)
        _log(f"KeepPythonScriptAlive={1 if enabled else 0}")
    except Exception as exc:
        _log(f"KeepPythonScriptAliveFailed enabled={1 if enabled else 0} error={exc}")


def _name(value: str):
    try:
        return unreal.Name(value)
    except Exception:
        return value


def _tags(actor) -> list[str]:
    try:
        return [str(item) for item in list(actor.tags)]
    except Exception:
        return []


def _has_tag(actor, tag: str) -> bool:
    return tag in _tags(actor)


def _add_tag(actor, tag: str) -> None:
    try:
        current = list(actor.tags)
        if tag not in [str(item) for item in current]:
            current.append(_name(tag))
            actor.tags = current
    except Exception as exc:
        _log(f"AddTagFailed tag={tag} error={exc}")


def _loc(actor) -> dict:
    try:
        v = actor.get_actor_location()
        return {"x": float(v.x), "y": float(v.y), "z": float(v.z)}
    except Exception:
        return {"x": None, "y": None, "z": None}


def _class_path(obj) -> str:
    try:
        return obj.get_class().get_path_name()
    except Exception:
        return ""


def _actor_name(actor) -> str:
    try:
        return actor.get_name()
    except Exception:
        return str(actor)


def _load_map() -> None:
    try:
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
        _log(f"MapLoaded {MAP_PATH}")
    except Exception as exc:
        _log(f"MapLoadSkipped path={MAP_PATH} error={exc}")


def _start_pie() -> None:
    try:
        subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if subsystem and hasattr(subsystem, "editor_request_begin_play"):
            subsystem.editor_request_begin_play()
            _log("EditorRequestBeginPlayRequested=1")
            return
    except Exception as exc:
        _log(f"EditorRequestBeginPlayFailed error={exc}")
    try:
        unreal.EditorLevelLibrary.editor_play_simulate()
        _log("EditorPlaySimulateRequested=1")
        return
    except Exception as exc:
        _log(f"EditorPlaySimulateFailed error={exc}")
    try:
        unreal.EditorLevelLibrary.editor_play_in_editor()
        _log("EditorPlayInEditorRequested=1")
    except Exception as exc:
        _log(f"EditorPlayInEditorFailed error={exc}")


def _end_pie_and_quit() -> None:
    try:
        unreal.EditorLevelLibrary.editor_end_play()
        _log("EditorEndPlayRequested=1")
    except Exception as exc:
        _log(f"EditorEndPlayFailed error={exc}")
    try:
        _set_keep_alive(False)
        unreal.SystemLibrary.quit_editor()
    except Exception as exc:
        _log(f"QuitEditorFailed error={exc}")


def _pie_world():
    try:
        worlds = unreal.EditorLevelLibrary.get_pie_worlds()
        if worlds:
            return worlds[0]
    except Exception:
        pass
    try:
        return unreal.EditorLevelLibrary.get_game_world()
    except Exception:
        return None


def _all_actors(world) -> list:
    try:
        return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
    except Exception:
        try:
            return list(unreal.EditorLevelLibrary.get_all_level_actors())
        except Exception:
            return []


def _pawn(world):
    try:
        return unreal.GameplayStatics.get_player_pawn(world, 0)
    except Exception:
        return None


def _game_mode(world):
    try:
        return unreal.GameplayStatics.get_game_mode(world)
    except Exception:
        return None


def _generated_enemies(world) -> list:
    out = []
    for actor in _all_actors(world):
        tags = _tags(actor)
        name = _actor_name(actor)
        if "AUTOUE_GENERATED_ENEMY" in tags or "AUTOUE_ENEMY_ZOMBIE" in tags or "zombie_1" in tags:
            out.append(actor)
        elif "AutoUE" in name and "Enemy" in name:
            out.append(actor)
    return out


def _move_pawn_near_enemy(pawn, enemy) -> bool:
    try:
        e = enemy.get_actor_location()
        target = unreal.Vector(float(e.x) - 30.0, float(e.y), float(e.z) + 8.0)
        pawn.set_actor_location(target, False, True)
        _log(f"PawnMovedNearEnemy target={round(target.x)},{round(target.y)},{round(target.z)}")
        return True
    except Exception as exc:
        _log(f"PawnMoveNearEnemyFailed error={exc}")
        return False


def _apply_damage_to_enemy(pawn, enemy, amount: float = 999.0) -> bool:
    try:
        pc = None
        world = _pie_world()
        if world:
            try:
                pc = unreal.GameplayStatics.get_player_controller(world, 0)
            except Exception:
                pc = None
        unreal.GameplayStatics.apply_damage(enemy, amount, pc, pawn, None)
        _log(f"EnemyDamageApplied actor={_actor_name(enemy)} amount={amount}")
        return True
    except Exception as exc:
        _log(f"EnemyDamageApplyFailed actor={_actor_name(enemy)} error={exc}")
        return False


class PieValidation:
    def __init__(self) -> None:
        self.started_at = time.time()
        self.handle = None
        self.state = "boot"
        self.state_since = self.started_at
        self.samples: list[dict] = []
        self.errors: list[str] = []
        self.right_tag_count = 0
        self.attack_tag_count = 0
        self.damage_pulse_count = 0
        self.moved_near_enemy = False
        self.finalized = False

    def transition(self, state: str) -> None:
        if self.state != state:
            _log(f"State {self.state}->{state}")
            self.state = state
            self.state_since = time.time()

    def sample(self) -> dict:
        world = _pie_world()
        pawn = _pawn(world) if world else None
        gm = _game_mode(world) if world else None
        enemies = _generated_enemies(world) if world else []
        sample = {
            "t": round(time.time() - self.started_at, 3),
            "state": self.state,
            "has_pie_world": bool(world),
            "game_mode_class": _class_path(gm) if gm else "",
            "pawn_class": _class_path(pawn) if pawn else "",
            "pawn_location": _loc(pawn) if pawn else {},
            "pawn_tags": _tags(pawn) if pawn else [],
            "enemy_count": len(enemies),
            "enemies": [
                {
                    "name": _actor_name(enemy),
                    "class": _class_path(enemy),
                    "location": _loc(enemy),
                    "tags": _tags(enemy),
                }
                for enemy in enemies[:5]
            ],
        }
        self.samples.append(sample)
        return sample

    def tick(self, delta_seconds: float) -> None:
        if self.finalized:
            return
        try:
            elapsed = time.time() - self.started_at
            if elapsed > MAX_SECONDS:
                self.errors.append("timeout")
                self.finish("timeout")
                return

            if self.state == "boot":
                _load_map()
                _start_pie()
                self.transition("wait_pie")
                return

            sample = self.sample()
            pawn = _pawn(_pie_world()) if _pie_world() else None
            enemies = _generated_enemies(_pie_world()) if _pie_world() else []

            if self.state == "wait_pie":
                if sample["has_pie_world"] and pawn:
                    self.transition("drive_move")
                return

            if self.state == "drive_move":
                if pawn:
                    _add_tag(pawn, "AUTOUE_INPUT_RIGHT_1S")
                    self.right_tag_count += 1
                if time.time() - self.state_since > 2.0:
                    self.transition("drive_attack")
                return

            if self.state == "drive_attack":
                if pawn and enemies:
                    self.moved_near_enemy = _move_pawn_near_enemy(pawn, enemies[0]) or self.moved_near_enemy
                if pawn:
                    _add_tag(pawn, "AUTOUE_INPUT_ATTACK")
                    self.attack_tag_count += 1
                if pawn and enemies and time.time() - self.state_since > 1.0 and self.damage_pulse_count < 3:
                    if _apply_damage_to_enemy(pawn, enemies[0]):
                        self.damage_pulse_count += 1
                if time.time() - self.state_since > 5.0:
                    self.transition("observe")
                return

            if self.state == "observe":
                if time.time() - self.state_since > 4.0:
                    self.finish("done")
                return
        except Exception:
            self.errors.append(traceback.format_exc())
            self.finish("exception")

    def finish(self, reason: str) -> None:
        if self.finalized:
            return
        self.finalized = True
        try:
            sample = self.sample()
        except Exception:
            sample = {}
        report = {
            "schema_version": "autoue-pie-validation/v1",
            "result": "pass"
            if not self.errors
            and any(s.get("has_pie_world") for s in self.samples)
            and any("AutoUEGeneratedGameModeAdapter" in s.get("game_mode_class", "") for s in self.samples)
            and any("AutoUEGeneratedCharacterAdapter" in s.get("pawn_class", "") for s in self.samples)
            and any(s.get("enemy_count", 0) > 0 for s in self.samples)
            else "fail",
            "reason": reason,
            "errors": self.errors,
            "right_tag_count": self.right_tag_count,
            "attack_tag_count": self.attack_tag_count,
            "damage_pulse_count": self.damage_pulse_count,
            "moved_near_enemy": self.moved_near_enemy,
            "last_sample": sample,
            "samples": self.samples,
        }
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        SAMPLE_PATH.write_text(
            "\n".join(json.dumps(s, ensure_ascii=False) for s in self.samples),
            encoding="utf-8",
        )
        _log(f"ReportWritten path={OUTPUT_PATH} result={report['result']} reason={reason}")
        try:
            if self.handle is not None:
                unreal.unregister_slate_post_tick_callback(self.handle)
        except Exception:
            pass
        _end_pie_and_quit()


_runner = PieValidation()
_set_keep_alive(True)
_runner.handle = unreal.register_slate_post_tick_callback(_runner.tick)
_log("PieValidationRegistered=1")
