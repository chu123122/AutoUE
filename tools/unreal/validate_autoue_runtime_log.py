from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_ORDERED_MARKERS = [
    "SpawnPointRegistryReady",
    "SpawnPointAcquired",
    "EnemyPhysicsReady",
    "AliveEnemyRegistered",
    "EnemySpawnedByEncounter",
    "EncounterStarted",
    "EnemyRuntimeReady managed_by=EncounterManager",
]

FORBIDDEN_MARKERS = [
    "RuntimeModuleUnavailable",
    "EnemySpawnManagerRejected",
    "SpawnPointMissing",
]
IGNORED_PUERTS_ERROR_SNIPPETS = [
    # PuerTS may log this during EndPIE / editor shutdown after the validation
    # report has already been written. It is not a generated runtime failure.
    "~FScriptArrayEx: Property is invalid",
]

SPAWN_ACQUIRED_RE = re.compile(
    r"SpawnPointAcquired\s+spawn_group=(?P<spawn_group>\S+)\s+actor=(?P<actor>\S+)"
)
SPAWNED_BY_ENCOUNTER_RE = re.compile(
    r"EnemySpawnedByEncounter\s+encounter=(?P<encounter>\S+)\s+enemy=(?P<enemy>\S+)\s+"
    r"enemy_id=(?P<enemy_id>\S+)\s+spawn_group=(?P<spawn_group>\S+)\s+"
    r"spawn_point=(?P<spawn_point>\S+)\s+loc=(?P<loc>-?\d+,-?\d+,-?\d+)"
)
DETECT_RE = re.compile(r"EnemyDetectPlayer\s+enemy_id=(?P<enemy_id>\S+)\s+distance=(?P<distance>\d+)\s+in_range=(?P<in_range>[01])")
MOVED_RE = re.compile(
    r"EnemyMoved\s+enemy_id=(?P<enemy_id>\S+)\s+from=(?P<from>-?\d+,-?\d+,-?\d+)\s+"
    r"to=(?P<to>-?\d+,-?\d+,-?\d+)\s+target_distance=(?P<target_distance>\d+)"
)


def _first_index(lines: list[str], marker: str, start: int = 0) -> int:
    for index in range(start, len(lines)):
        if marker in lines[index]:
            return index
    return -1


def validate_autoue_runtime_log(
    log_path: Path,
    *,
    require_in_range: bool = False,
    require_enemy_move: bool = False,
) -> dict:
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    errors: list[str] = []
    evidence: dict[str, object] = {
        "log_path": str(log_path),
        "line_count": len(lines),
        "required_markers": REQUIRED_ORDERED_MARKERS,
    }

    cursor = 0
    marker_lines: dict[str, int] = {}
    for marker in REQUIRED_ORDERED_MARKERS:
        index = _first_index(lines, marker, cursor)
        if index < 0:
            errors.append(f"missing required runtime marker: {marker}")
            continue
        marker_lines[marker] = index + 1
        cursor = index + 1
    evidence["marker_lines"] = marker_lines

    forbidden_hits: dict[str, list[int]] = {}
    for marker in FORBIDDEN_MARKERS:
        hits = [i + 1 for i, line in enumerate(lines) if marker in line]
        if hits:
            forbidden_hits[marker] = hits[:20]
            errors.append(f"forbidden runtime marker present: {marker}")
    evidence["forbidden_hits"] = forbidden_hits

    puerts_error_lines = []
    ignored_puerts_error_lines = []
    for i, line in enumerate(lines):
        if "Puerts: Error:" not in line and "Puerts: Error]" not in line:
            continue
        if any(snippet in line for snippet in IGNORED_PUERTS_ERROR_SNIPPETS):
            ignored_puerts_error_lines.append(i + 1)
        else:
            puerts_error_lines.append(i + 1)
    if puerts_error_lines:
        errors.append("Puerts error log present")
    evidence["puerts_error_lines"] = puerts_error_lines[:20]
    evidence["ignored_puerts_error_lines"] = ignored_puerts_error_lines[:20]

    acquired = []
    for line in lines:
        match = SPAWN_ACQUIRED_RE.search(line)
        if match:
            acquired.append(match.groupdict())
    spawned = []
    for line in lines:
        match = SPAWNED_BY_ENCOUNTER_RE.search(line)
        if match:
            spawned.append(match.groupdict())
    evidence["spawn_points_acquired"] = acquired
    evidence["enemies_spawned_by_encounter"] = spawned

    if not acquired:
        errors.append("no SpawnPointAcquired record parsed")
    if not spawned:
        errors.append("no EnemySpawnedByEncounter record parsed")
    if acquired and spawned:
        acquired_pairs = {(item["spawn_group"], item["actor"]) for item in acquired}
        for item in spawned:
            pair = (item["spawn_group"], item["spawn_point"])
            if pair not in acquired_pairs:
                errors.append(
                    "spawned enemy does not use an acquired spawn point: "
                    f"spawn_group={item['spawn_group']} spawn_point={item['spawn_point']}"
                )

    detections = []
    for line in lines:
        match = DETECT_RE.search(line)
        if match:
            data = match.groupdict()
            data["distance"] = int(data["distance"])
            data["in_range"] = data["in_range"] == "1"
            detections.append(data)
    evidence["enemy_detection_count"] = len(detections)
    evidence["enemy_detection_sample"] = detections[:5]
    evidence["enemy_detected_in_range"] = any(item["in_range"] for item in detections)
    if require_in_range and not evidence["enemy_detected_in_range"]:
        errors.append("no EnemyDetectPlayer in_range=1 record found")

    movements = []
    for line in lines:
        match = MOVED_RE.search(line)
        if match:
            data = match.groupdict()
            data["target_distance"] = int(data["target_distance"])
            movements.append(data)
    evidence["enemy_movement_count"] = len(movements)
    evidence["enemy_movement_sample"] = movements[:5]
    if require_enemy_move and not movements:
        errors.append("no EnemyMoved record found")

    return {
        "result": "fail" if errors else "pass",
        "errors": errors,
        "evidence": evidence,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", help="Unreal/PuerTS runtime log path")
    parser.add_argument("--require-in-range", action="store_true", help="also require enemy perception in_range=1")
    parser.add_argument("--require-enemy-move", action="store_true", help="also require generated enemy movement")
    parser.add_argument("--write-report", help="optional JSON report path")
    args = parser.parse_args(argv)

    report = validate_autoue_runtime_log(
        Path(args.log),
        require_in_range=args.require_in_range,
        require_enemy_move=args.require_enemy_move,
    )
    if args.write_report:
        Path(args.write_report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.write_report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["result"] != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())
