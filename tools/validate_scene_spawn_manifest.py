from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.encounter_validation import EncounterValidationError, load_json_file, validate_scene_spawn_manifest_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AutoUE scene spawn manifest JSON.")
    parser.add_argument("manifest", nargs="?", help="Path to scene-spawn-manifest.json")
    parser.add_argument("--path", dest="path", help="Compatibility alias for manifest path")
    args = parser.parse_args()
    path_text = args.path or args.manifest
    if not path_text:
        parser.error("manifest path is required")
    path = Path(path_text).resolve()
    errors: list[str] = []
    if not path.exists():
        errors.append(f"manifest does not exist: {path}")
    else:
        try:
            data = load_json_file(path)
            validate_scene_spawn_manifest_data(data)
        except (OSError, json.JSONDecodeError, EncounterValidationError) as exc:
            errors.append(str(exc))
    report = {"result": "fail" if errors else "pass", "errors": errors, "path": str(path)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
