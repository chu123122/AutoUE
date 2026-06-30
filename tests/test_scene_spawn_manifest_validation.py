from __future__ import annotations

import json
from pathlib import Path

from core.encounter_validation import EncounterValidationError, validate_scene_spawn_manifest_data

ROOT = Path(__file__).resolve().parents[1]


def test_scene_spawn_manifest_fixture_is_valid():
    data = json.loads((ROOT / 'tests' / 'fixtures' / 'scene-spawn-manifest.valid.json').read_text(encoding='utf-8'))
    validate_scene_spawn_manifest_data(data)


def test_scene_spawn_manifest_rejects_zone_unknown_group():
    data = json.loads((ROOT / 'tests' / 'fixtures' / 'scene-spawn-manifest.valid.json').read_text(encoding='utf-8'))
    data['encounter_zones'][0]['spawn_group'] = 'missing_group'
    try:
        validate_scene_spawn_manifest_data(data)
    except EncounterValidationError as exc:
        assert 'spawn_group does not exist' in str(exc)
    else:
        raise AssertionError('validator accepted unknown zone spawn_group')
