# PrimitiveRecipeRuntime 验收记录

## 环境

- AutoUE branch: `codex/phase3-complete-artifacts-20260629`
- AIDev project: `D:\UE5.7.4\AIDev`
- AIDev TS backup: `C:\tmp\autoue-aidev-ts-backup-20260630-211922`
- Bundle: `test_tmp\dead_cells_full_current_20260630-202057\output\demo_1`
- L4 PIE: 未运行

## 命令与结果

| 层级 | 命令 | 结果 | 证据 |
|---|---|---|---|
| L1 pytest | `python -m pytest tests/test_runtime_primitives.py tests/test_behavior_recipes.py tests/test_player_pickup_runtime_support.py -q` | PASS | `8 passed` |
| L2 node 6 | `python autoue.py node run --config config/local.json --workflow config/workflows/puerts_ts.json --node PuerTSRuntimeMappingCompiler --input-bundle test_tmp\dead_cells_full_current_20260630-202057\output\demo_1 --output-bundle test_tmp\dead_cells_full_current_20260630-202057\output\demo_1` | PASS | `flow/05-puerts-runtime-mapping.json`, `flow/06-behavior-spec.json`, `flow/06-runtime-support-check.json` |
| L2 node 7 | `python autoue.py node run ... --node TypeScriptImplementationSlotProjector ...` | PASS | `ports/ts_analyzer.json` |
| L2 node 8 | `python autoue.py node run ... --node TypeScriptInteractiveTemplatePlanner ...` | PASS | `ports/interactive_ts_plan.json`, 20 个 entity-scoped interactive TS |
| L2 node 9 | `python autoue.py node run ... --node TypeScriptRuntimeTemplatePlanner ...` | PASS | `ports/typescript_codegen.json`, primitive runtime TS 模板已生成 |
| L2 node 10 | `python autoue.py node run ... --node StaticEvaluationPlanBuilder ...` | PASS | `MyPCG/eval/instructions.json`, `instruction_count=20` |
| L2 validate-output | `python autoue.py validate-output --root test_tmp\dead_cells_full_current_20260630-202057\output\demo_1` | PASS | `result=pass`, 10 个节点均 pass |
| L3 AIDev sync | 备份 `D:\UE5.7.4\AIDev\TypeScript\content\generated` 后同步 bundle TS | PASS | backup: `C:\tmp\autoue-aidev-ts-backup-20260630-211922` |
| L3 AIDev tsc | `D:\UE5.7.4\AIDev\node_modules\.bin\tsc.cmd -p D:\UE5.7.4\AIDev\tsconfig.json` | PASS | exit code 0 |
| 回归最小集 | `python -m pytest tests/test_config_contract.py tests/test_dead_cells_content_library.py tests/test_runtime_primitives.py tests/test_behavior_recipes.py tests/test_player_pickup_runtime_support.py -q` | PASS | `63 passed` |
| 回归全量 | `python -m pytest tests -q` | PASS | `81 passed` |
| L4 PIE proof | 未运行 | NOT_RUN | `runtime_proof=not_run` |

## 关键产物检查

- `flow/06-runtime-support-check.json`
  - `schema_version=autoue-runtime-support-check/v2`
  - `static_support=supported`
  - `runtime_proof=not_run`
  - `unsupported_capabilities=[]`
  - `unsupported_primitives=[]`
- `flow/06-behavior-spec.json`
  - `player.behavior.move_and_attack`: `primitive_plan` 6 步
  - `pickup.behavior.collect_reward`: 每个 pickup 实例 `primitive_plan` 6 步
- `ports/typescript_codegen.json`
  - 已选择 `player_movement_runtime`, `player_combat_runtime`, `hit_query_runtime`, `damage_runtime`, `pickup_runtime`, `reward_runtime`, `feedback_runtime`
- `MyPCG/eval/instructions.json`
  - 多实体同 behavior 使用 entity-scoped interactive adapter，例如 `runArcherEncounterBehaviorCompleteWhenAllDeadInteraction`

## 失败项

- 无 L1/L2/L3 失败项。
- L4 未执行，不声明 runtime pass。

## 结论

- static_support: `supported`
- runtime_proof: `not_run`
- 是否完成: 达成本轮最小完成标准 L1/L2/L3；未完成 L4 PIE runtime proof。
