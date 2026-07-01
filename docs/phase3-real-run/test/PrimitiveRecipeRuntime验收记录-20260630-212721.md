# PrimitiveRecipeRuntime 验收记录

## 环境

- AutoUE commit: `5ebb626`
- AutoUE branch: `codex/phase3-complete-artifacts-20260629`
- AIDev project: `D:\UE5.7.4\AIDev`
- UE editor: `D:\UE-src-5.7\Engine\Binaries\Win64\UnrealEditor.exe`
- Map: `/Game/Castlevania2D.Castlevania2D`
- Bundle: `test_tmp\dead_cells_full_current_20260630-202057\output\demo_1`
- AIDev TS backup: `test_tmp\dead_cells_full_current_20260630-202057\output\demo_1\aidev_ts_backup_20260630-212625`
- L4 PIE: 未运行

## 命令与结果

| 层级 | 命令 | 结果 | 证据 |
|---|---|---|---|
| L1 pytest primitives | `python -m pytest tests/test_runtime_primitives.py -q` | PASS | `3 passed` |
| L1 pytest recipes | `python -m pytest tests/test_behavior_recipes.py -q` | PASS | `3 passed` |
| L1 pytest player/pickup support | `python -m pytest tests/test_player_pickup_runtime_support.py -q` | PASS | `2 passed` |
| L2 node 6 | `python autoue.py node run --config config/local.json --workflow config/workflows/puerts_ts.json --node PuerTSRuntimeMappingCompiler --input-bundle test_tmp\dead_cells_full_current_20260630-202057\output\demo_1 --output-bundle test_tmp\dead_cells_full_current_20260630-202057\output\demo_1` | PASS | `flow/05-puerts-runtime-mapping.json`, `flow/06-behavior-spec.json`, `flow/06-runtime-support-check.json` |
| L2 node 7 | `python autoue.py node run ... --node TypeScriptImplementationSlotProjector ...` | PASS | `ports/ts_analyzer.json` |
| L2 node 8 | `python autoue.py node run ... --node TypeScriptInteractiveTemplatePlanner ...` | PASS | `ports/interactive_ts_plan.json` |
| L2 node 9 | `python autoue.py node run ... --node TypeScriptRuntimeTemplatePlanner ...` | PASS | `ports/typescript_codegen.json`, 56 个 `.ts` 文件 |
| L2 node 10 | `python autoue.py node run ... --node StaticEvaluationPlanBuilder ...` | PASS | `MyPCG/eval/instructions.json` |
| L2 validate-output | `python autoue.py validate-output --root test_tmp\dead_cells_full_current_20260630-202057\output\demo_1` | PASS | `result=pass`, 10 个节点均 pass |
| L3 AIDev sync | 备份目标 AutoUE generated TS 后同步 bundle `TypeScript` 到 `D:\UE5.7.4\AIDev\TypeScript` | PASS | backup: `test_tmp\dead_cells_full_current_20260630-202057\output\demo_1\aidev_ts_backup_20260630-212625` |
| L3 AIDev tsc | `D:\UE5.7.4\AIDev\node_modules\.bin\tsc.cmd -p D:\UE5.7.4\AIDev\tsconfig.json` | PASS | exit code 0 |
| 回归最小集 | `python -m pytest tests/test_config_contract.py tests/test_dead_cells_content_library.py tests/test_runtime_primitives.py tests/test_behavior_recipes.py tests/test_player_pickup_runtime_support.py -q` | PASS | `63 passed` |
| 回归全量 | `python -m pytest tests -q` | PASS | `81 passed` |
| L4 PIE proof | 未运行 | NOT_RUN | `runtime_proof=not_run` |

## 关键产物检查

- `flow/06-runtime-support-check.json`
  - `status=supported`
  - `static_support=supported`
  - `runtime_proof=not_run`
  - `unsupported_capabilities=[]`
  - `unsupported_primitives=[]`
- `flow/06-behavior-spec.json`
  - 总行为数：20
  - `player.behavior.move_and_attack`: 1 条，`primitive_plan` 6 步
  - `pickup.behavior.collect_reward`: 3 条，分别 `primitive_plan` 6 步
  - player/pickup primitive handler 非空，required_runtime_modules 非空
- `ports/typescript_codegen.json`
  - 已生成 runtime TS：`AutoUEPlayerMovementRuntime.ts`, `AutoUEPlayerCombatRuntime.ts`, `AutoUEPickupRuntime.ts`, `AutoUERewardRuntime.ts`, `AutoUEFeedbackRuntime.ts`, `AutoUEDamageRuntime.ts`, `AutoUEHitQueryRuntime.ts` 等
- `MyPCG/eval/instructions.json`
  - 存在，validate-output 已纳入 configured artifacts

## 失败项

- 无 L1/L2/L3 失败项。
- L4 PIE runtime proof 未执行，因此不声明 runtime pass。

## 结论

- static_support: `supported`
- runtime_proof: `not_run`
- 是否完成: 达成本轮最小完成标准 L1/L2/L3；未完成 L4 PIE runtime proof。
