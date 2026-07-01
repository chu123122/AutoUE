from __future__ import annotations

import json

from tools.regen_enemy_pie import build_case_bundle


def test_regen_enemy_pie_renders_current_enemy_templates(tmp_path):
    bundle = build_case_bundle("zombie", tmp_path)

    generated = bundle.bundle / "TypeScript" / "content" / "generated"
    assert (generated / "AutoUEEnemyPresentationRuntime.ts").exists()
    assert (generated / "AutoUEEnemyCombat.ts").exists()
    assert (generated / "AutoUEGeneratedEncounterSpec.ts").exists()

    report = json.loads((bundle.bundle / "flow" / "enemy-pie-static-report.json").read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert "enemy_presentation" in report["required_runtime_modules"]


def test_regen_enemy_pie_archer_requires_projectile_runtime(tmp_path):
    bundle = build_case_bundle("archer", tmp_path)

    generated = bundle.bundle / "TypeScript" / "content" / "generated"
    assert (generated / "AutoUEEnemyProjectileRuntime.ts").exists()
    assert "enemy_projectile_runtime" in bundle.static_report["required_runtime_modules"]
