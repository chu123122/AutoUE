from __future__ import annotations

from core.runtime_primitives import all_primitives, check_primitive_support, runtime_module_templates


FIRST_BATCH = {
    "input.read_axis",
    "input.read_action",
    "movement.apply_intent",
    "hit.resolve_melee",
    "damage.apply",
    "overlap.detect",
    "reward.grant",
    "feedback.hud_update",
    "feedback.set_visibility",
    "entity.consume",
    "timer.cooldown_gate",
    "timer.once_gate",
}


def test_runtime_primitive_registry_is_unique_and_first_batch_complete():
    primitives = all_primitives()
    ids = [entry.primitive_id for entry in primitives]
    assert len(ids) == len(set(ids))
    assert FIRST_BATCH.issubset(set(ids))


def test_supported_primitives_have_handlers_modules_and_template_mapping():
    templates = runtime_module_templates()
    for entry in all_primitives():
        if not entry.supported:
            assert entry.reason
            continue
        assert entry.handler, entry.primitive_id
        assert entry.required_runtime_modules, entry.primitive_id
        assert isinstance(entry.params_schema or {}, dict)
        missing = [module for module in entry.required_runtime_modules if module not in templates]
        assert not missing, f"{entry.primitive_id} missing templates for {missing}"


def test_unknown_primitive_fails_loud():
    support = check_primitive_support(["missing.primitive"])
    assert support["unsupported_primitives"]
    assert "not registered" in support["unsupported_primitives"][0]["reason"]
