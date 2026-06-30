from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.content_library import load_dead_cells_library, validate_library_self_consistency

DOC = ROOT / "tests" / "fixtures" / "dead_cells_libraries"


def write_docs() -> None:
    lib = load_dead_cells_library()
    DOC.mkdir(parents=True, exist_ok=True)
    (DOC / "entities.zh.md").write_text(
        "# 死亡细胞实体库（Entity Library，不含音效）\n\n"
        "Entity 是可绑定/可显示/可生成/可引用对象；运行时状态进入 StateBlackboard。\n\n"
        + "\n".join(f"- `{entity_id}`" for entity_id in sorted(lib["entities"])) + "\n",
        encoding="utf-8",
    )
    (DOC / "abilities.zh.md").write_text(
        "# 死亡细胞能力库（Capability Library，不含音效）\n\n"
        "Capability 禁止泛化 state/interaction；每项含 capability_kind/action_kind。\n\n"
        + "\n".join(
            f"- `{capability_id}` {cap.get('capability_kind')}/{cap.get('action_kind')}"
            for capability_id, cap in sorted(lib["capabilities"].items())
        ) + "\n",
        encoding="utf-8",
    )
    (DOC / "behaviors.zh.md").write_text(
        "# 死亡细胞行为库（Behavior Library，不含音效）\n\n"
        "Behavior = trigger + conditions + actions + required_capability_ids。\n\n"
        + "\n".join(
            f"- `{behavior_id}` -> {', '.join(behavior.get('required_capability_ids', []))}"
            for behavior_id, behavior in sorted(lib["behaviors"].items())
        ) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    lib = load_dead_cells_library()
    validate_library_self_consistency(lib)
    write_docs()
    print(json.dumps({
        "result": "pass",
        "entities": len(lib["entities"]),
        "capabilities": len(lib["capabilities"]),
        "behaviors": len(lib["behaviors"]),
        "contract": "Entity/Capability/Behavior only; runtime state belongs to StateBlackboard",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
