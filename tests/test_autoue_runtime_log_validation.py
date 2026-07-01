from __future__ import annotations

from pathlib import Path


GOOD_LOG = """
[AUTOUE_GENERATED] SpawnPointRegistryReady count=1 groups=room_01_guard
[AUTOUE_GENERATED] SpawnPointAcquired spawn_group=room_01_guard actor=BP_EnemySpawnPoint_C_2 tags=ground,melee
[AUTOUE_GENERATED] EnemyPhysicsReady actor=valid gravity=1
[AUTOUE_GENERATED] AliveEnemyRegistered count=1 enemy_id=zombie_1
[AUTOUE_GENERATED] EnemySpawnedByEncounter encounter=room_01_initial_guard enemy=zombie enemy_id=zombie_1 spawn_group=room_01_guard spawn_point=BP_EnemySpawnPoint_C_2 loc=640,0,-1085
[AUTOUE_GENERATED] EncounterStarted id=room_01_initial_guard spawn_group=room_01_guard spawned=1 alive=1
[AUTOUE_GENERATED] EnemyRuntimeReady managed_by=EncounterManager encounters=1 alive=1
[AUTOUE_GENERATED] EnemyDetectPlayer enemy_id=zombie_1 distance=1334 in_range=0
[AUTOUE_GENERATED] EnemyMoved enemy_id=zombie_1 from=640,0,-1085 to=639,0,-1085 target_distance=80
""".strip()


def write_log(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "runtime.log"
    path.write_text(text, encoding="utf-8")
    return path


def test_autoue_runtime_log_passes_when_encounter_spawn_consumes_spawn_point(tmp_path):
    from tools.unreal.validate_autoue_runtime_log import validate_autoue_runtime_log

    report = validate_autoue_runtime_log(write_log(tmp_path, GOOD_LOG))

    assert report["result"] == "pass"
    assert report["evidence"]["enemies_spawned_by_encounter"][0]["spawn_point"] == "BP_EnemySpawnPoint_C_2"


def test_autoue_runtime_log_fails_when_main_runtime_did_not_start_encounter(tmp_path):
    from tools.unreal.validate_autoue_runtime_log import validate_autoue_runtime_log

    report = validate_autoue_runtime_log(write_log(tmp_path, GOOD_LOG.replace("EncounterStarted", "EncounterSkipped")))

    assert report["result"] == "fail"
    assert any("EncounterStarted" in err for err in report["errors"])


def test_autoue_runtime_log_fails_when_spawned_enemy_does_not_use_acquired_point(tmp_path):
    from tools.unreal.validate_autoue_runtime_log import validate_autoue_runtime_log

    bad = GOOD_LOG.replace("spawn_point=BP_EnemySpawnPoint_C_2", "spawn_point=HardcodedSpawn_C_0")
    report = validate_autoue_runtime_log(write_log(tmp_path, bad))

    assert report["result"] == "fail"
    assert any("does not use an acquired spawn point" in err for err in report["errors"])


def test_autoue_runtime_log_can_require_enemy_detection_range(tmp_path):
    from tools.unreal.validate_autoue_runtime_log import validate_autoue_runtime_log

    report = validate_autoue_runtime_log(write_log(tmp_path, GOOD_LOG), require_in_range=True)

    assert report["result"] == "fail"
    assert any("in_range=1" in err for err in report["errors"])


def test_autoue_runtime_log_can_require_enemy_move(tmp_path):
    from tools.unreal.validate_autoue_runtime_log import validate_autoue_runtime_log

    report = validate_autoue_runtime_log(write_log(tmp_path, GOOD_LOG), require_enemy_move=True)

    assert report["result"] == "pass"
    assert report["evidence"]["enemy_movement_count"] == 1


def test_autoue_runtime_log_ignores_known_endpie_puerts_shutdown_noise(tmp_path):
    from tools.unreal.validate_autoue_runtime_log import validate_autoue_runtime_log

    log = GOOD_LOG + "\nPuerts: Error: ~FScriptArrayEx: Property is invalid\n"
    report = validate_autoue_runtime_log(write_log(tmp_path, log), require_enemy_move=True)

    assert report["result"] == "pass"
    assert report["evidence"]["ignored_puerts_error_lines"]
