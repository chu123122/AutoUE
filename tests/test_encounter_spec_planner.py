from __future__ import annotations

import json
from pathlib import Path

from core.encounter_validation import EncounterValidationError, validate_encounter_spec_data

ROOT = Path(__file__).resolve().parents[1]


def structure():
    return {
        'entities': [
            {'entity_id': 'player', 'entity_kind': 'player', 'display_name': 'Player', 'summary': 'Player', 'content_tags': ['player'], 'spawnable': False, 'abilities': []},
            {'entity_id': 'goblin_melee', 'entity_kind': 'enemy', 'display_name': 'Goblin', 'summary': 'Melee enemy', 'content_tags': ['enemy', 'ground', 'melee'], 'spawnable': True, 'enemy_profile': {'cost': 2, 'allowed_spawn_tags': ['ground', 'melee'], 'default_health': 2}, 'abilities': []},
        ],
        'non_goals': [],
    }


def load_fixture(name: str):
    return json.loads((ROOT / 'tests' / 'fixtures' / name).read_text(encoding='utf-8'))


def test_encounter_spec_fixture_is_valid_against_structure_and_manifest():
    validate_encounter_spec_data(load_fixture('encounter-spec.valid.json'), structure=structure(), manifest=load_fixture('scene-spawn-manifest.valid.json'))


def test_encounter_spec_rejects_coordinates():
    spec = load_fixture('encounter-spec.valid.json')
    spec['encounters'][0]['location'] = {'x': 1}
    try:
        validate_encounter_spec_data(spec, structure=structure(), manifest=load_fixture('scene-spawn-manifest.valid.json'))
    except EncounterValidationError as exc:
        assert 'coordinate/transform keys are forbidden' in str(exc)
    else:
        raise AssertionError('validator accepted coordinates in EncounterSpec')


def test_encounter_spec_rejects_unknown_spawn_group():
    spec = load_fixture('encounter-spec.valid.json')
    spec['encounters'][0]['spawn_group'] = 'missing_group'
    try:
        validate_encounter_spec_data(spec, structure=structure(), manifest=load_fixture('scene-spawn-manifest.valid.json'))
    except EncounterValidationError as exc:
        assert 'spawn_group not found' in str(exc)
    else:
        raise AssertionError('validator accepted unknown spawn_group')


def test_encounter_spec_rejects_budget_overrun():
    spec = load_fixture('encounter-spec.valid.json')
    spec['encounters'][0]['composition'][0]['count'] = 2
    try:
        validate_encounter_spec_data(spec, structure=structure(), manifest=load_fixture('scene-spawn-manifest.valid.json'))
    except EncounterValidationError as exc:
        assert 'exceeds enemy_budget' in str(exc)
    else:
        raise AssertionError('validator accepted budget overrun')
