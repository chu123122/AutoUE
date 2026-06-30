"""AutoUE 稳定命令入口。

常用命令：
- python autoue.py check-config
- python autoue.py run --workflow config/workflows/puerts_ts.json
- python autoue.py validate-output --root data/output/demo_1
- python autoue.py node run --node TypeScriptImplementationSlotProjector --input-bundle <prev> --output-bundle <next>
- python autoue.py node validate --node TypeScriptImplementationSlotProjector --bundle <bundle>
- python autoue.py run-runtime-validation --root data/output/demo_1 --write-summary
- python autoue.py validate-runtime --root data/output/demo_1
"""

from __future__ import annotations

import sys

from core.workflow_runner import main as workflow_main


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(__doc__.strip())
        raise SystemExit(2)
    raise SystemExit(workflow_main(sys.argv[1:]))
