# Primitive + Recipe Runtime 具体验收方案

> 目标：验证 `Primitive + Behavior Recipe` 改造不是“登记通过”，而是真正能把 player movement/combat、pickup reward/feedback 从能力库一路落到 TS 生成、AIDev 编译与 runtime evidence。

## 1. 验收对象

首批验收行为：

```text
player.behavior.move_and_attack
pickup.behavior.collect_reward
```

首批验收能力：

```text
player.movement.move_actor
player.attack.apply_damage
pickup.collect.grant_reward
pickup.feedback.spawn_reward_visual
```

首批验收 primitive：

```text
input.read_axis
input.read_action
movement.apply_intent
hit.resolve_melee
damage.apply
overlap.detect
reward.grant
feedback.hud_update
feedback.set_visibility
entity.consume
timer.cooldown_gate
timer.once_gate
```

## 2. 验收分层

验收分四层，不能跳层声明完成。

```text
L1 静态编译层：Python schema / validator / pytest
L2 节点链路层：当前 bundle 从第 6 节点继续跑完
L3 AIDev 编译层：生成 TS 同步到 AIDev 后 tsc 通过
L4 Runtime proof 层：UE/PIE 中真实触发并产生日志证据
```

## 3. 当前复用 bundle

优先复用当前已经跑到第 5 节点的 bundle：

```text
test_tmp\dead_cells_full_current_20260630-202057\output\demo_1
```

当前已存在关键产物：

```text
flow\scene-spawn-manifest.json
flow\03-encounter-spec.json
flow\04-ue-api-mcp\summary.json
flow\06-behavior-spec.json
flow\06-runtime-support-check.json
```

当前已知失败点：

```text
PuerTSRuntimeMappingCompiler:
unsupported runtime capabilities:
- pickup.collect.grant_reward
- pickup.feedback.spawn_reward_visual
- player.movement.move_actor
- player.attack.apply_damage
```

验收目标是让这个 bundle 继续跑完，而不是重新编一个简单 fixture 冒充通过。

## 4. L1：单元测试验收

### 4.1 新增测试文件

```text
tests/test_runtime_primitives.py
tests/test_behavior_recipes.py
tests/test_player_pickup_runtime_support.py
```

### 4.2 runtime primitive registry 测试

命令：

```powershell
python -m pytest tests/test_runtime_primitives.py -q
```

必须验证：

```text
所有 primitive_id 唯一
所有 supported primitive 有 handler
所有 supported primitive 有 required_runtime_modules
所有 required_runtime_modules 有模板或既有实现
所有 params_schema 合法
unsupported primitive 会给出明确 reason
```

通过标准：

```text
pytest pass
```

### 4.3 behavior recipe 测试

命令：

```powershell
python -m pytest tests/test_behavior_recipes.py -q
```

必须验证：

```text
player.behavior.move_and_attack 能展开 primitive_plan
pickup.behavior.collect_reward 能展开 primitive_plan
recipe 引用的 primitive 全部存在
recipe inputs/outputs 能接上
recipe params 能从 entity/capability/default 中解析
缺参数时 fail loud
```

通过标准：

```text
pytest pass
```

### 4.4 player/pickup support 测试

命令：

```powershell
python -m pytest tests/test_player_pickup_runtime_support.py -q
```

必须验证：

```text
player.movement.move_actor 不再因为 missing handler 被 unsupported
player.attack.apply_damage 不再因为 missing handler 被 unsupported
pickup.collect.grant_reward 不再因为 missing handler 被 unsupported
pickup.feedback.spawn_reward_visual 不再因为 missing handler 被 unsupported
support_check.static_support == supported
support_check.runtime_proof == not_run
unsupported_capabilities == []
unsupported_primitives == []
```

通过标准：

```text
pytest pass
```

## 5. L2：当前 bundle 续跑验收

### 5.1 运行第 6 节点

命令：

```powershell
python autoue.py node run `
  --config config/local.json `
  --workflow config/workflows/puerts_ts.json `
  --node PuerTSRuntimeMappingCompiler `
  --input-bundle test_tmp\dead_cells_full_current_20260630-202057\output\demo_1 `
  --output-bundle test_tmp\dead_cells_full_current_20260630-202057\output\demo_1
```

必须生成：

```text
llm_outputs\PuerTSRuntimeMappingCompiler.txt
ports\runtime_mapping.json
flow\05-puerts-runtime-mapping.json
flow\06-behavior-spec.json
flow\06-runtime-support-check.json
```

必须满足：

```text
support_check.static_support == supported
support_check.runtime_proof == not_run
unsupported_capabilities == []
unsupported_primitives == []
behavior_spec 中 player/pickup 行为有 primitive_plan
primitive_plan 中 handler 非空
primitive_plan 中 required_runtime_modules 非空
```

失败即未完成。

### 5.2 继续跑第 7-10 节点

命令：

```powershell
python autoue.py node run --config config/local.json --workflow config/workflows/puerts_ts.json --node TypeScriptImplementationSlotProjector --input-bundle test_tmp\dead_cells_full_current_20260630-202057\output\demo_1 --output-bundle test_tmp\dead_cells_full_current_20260630-202057\output\demo_1

python autoue.py node run --config config/local.json --workflow config/workflows/puerts_ts.json --node TypeScriptInteractiveTemplatePlanner --input-bundle test_tmp\dead_cells_full_current_20260630-202057\output\demo_1 --output-bundle test_tmp\dead_cells_full_current_20260630-202057\output\demo_1

python autoue.py node run --config config/local.json --workflow config/workflows/puerts_ts.json --node TypeScriptRuntimeTemplatePlanner --input-bundle test_tmp\dead_cells_full_current_20260630-202057\output\demo_1 --output-bundle test_tmp\dead_cells_full_current_20260630-202057\output\demo_1

python autoue.py node run --config config/local.json --workflow config/workflows/puerts_ts.json --node StaticEvaluationPlanBuilder --input-bundle test_tmp\dead_cells_full_current_20260630-202057\output\demo_1 --output-bundle test_tmp\dead_cells_full_current_20260630-202057\output\demo_1
```

必须生成：

```text
ports\ts_analyzer.json
ports\interactive_ts_plan.json
ports\typescript_codegen.json
ports\evaluation_instructions.json
MyPCG\eval\instructions.json
TypeScript\*.ts
TypeScript\content\generated\*.ts
```

### 5.3 validate-output

命令：

```powershell
python autoue.py validate-output --root test_tmp\dead_cells_full_current_20260630-202057\output\demo_1
```

通过标准：

```text
result == pass
```

如果仍有：

```text
missing runtime_mapping
missing .ts files
missing instructions.json
unsupported runtime capabilities
```

则未完成。

## 6. L3：AIDev TypeScript 编译验收

### 6.1 同步生成 TS

把 bundle 生成的 TypeScript 产物同步到：

```text
D:\UE5.7.4\AIDev\TypeScript
```

同步前必须明确备份或清理旧 generated state，避免旧产物污染。

### 6.2 tsc 编译

命令：

```powershell
D:\UE5.7.4\AIDev\node_modules\.bin\tsc.cmd -p D:\UE5.7.4\AIDev\tsconfig.json
```

通过标准：

```text
exit code == 0
```

失败即未完成。不能把 Python validator pass 当成 AIDev 可用。

## 7. L4：Runtime proof 验收

### 7.1 UE/PIE 启动

目标工程：

```text
D:\UE5.7.4\AIDev\AIDev.uproject
```

当前 map：

```text
/Game/Castlevania2D.Castlevania2D
```

UE Editor：

```text
D:\UE-src-5.7\Engine\Binaries\Win64\UnrealEditor.exe
```

### 7.2 必须证明的 runtime 事件

#### Player movement

必须出现日志：

```text
InputAxisRead
MoveApplied
```

或者等价结构化 evidence：

```json
{
  "event": "MoveApplied",
  "entity_id": "player"
}
```

#### Player attack

必须出现日志：

```text
InputActionRead action=attack
HitResolved
DamageApplied
PlayerAttackResolved
```

并且能关联到敌人：

```text
target_entity_id = enemy
enemy hp changed
```

#### Pickup reward

必须出现日志：

```text
PickupOverlap
RewardGranted
PickupConsumed
```

并且能看到 reward state 变化：

```text
gold / cell / health / stat changed
```

#### Pickup feedback

必须出现日志：

```text
HudUpdated
VisibilityChanged
RewardFeedbackShown
```

#### Enemy runtime

不能只验 player/pickup。敌人原有链路也必须保留：

```text
EnemySpawned
EnemyDetectedPlayer
EnemyMoved
EnemyAttackResolved
EnemyDamageReceived
EnemyDied
EncounterCompleted
```

### 7.3 runtime_proof 更新

PIE 验证前：

```json
"runtime_proof": "not_run"
```

PIE 验证通过后：

```json
"runtime_proof": "pass"
```

PIE 验证失败：

```json
"runtime_proof": "fail"
```

不能把 `static_support=supported` 当成 `runtime_proof=pass`。

## 8. 回归测试

至少跑：

```powershell
python -m pytest tests/test_config_contract.py -q
python -m pytest tests/test_dead_cells_content_library.py -q
python -m pytest tests/test_runtime_primitives.py -q
python -m pytest tests/test_behavior_recipes.py -q
python -m pytest tests/test_player_pickup_runtime_support.py -q
```

如果时间允许：

```powershell
python -m pytest tests -q
```

## 9. 不接受的通过口径

以下都不能算完成：

```text
只把 supported=False 改成 supported=True
只让第 6 节点不报错
只生成 flow/06-behavior-spec.json
只生成 TS 但没有 tsc
只通过 validate-output 但没 AIDev 编译
只通过 AIDev 编译但没有 runtime log
只验证 player/pickup，没确认 enemy runtime 没退化
```

## 10. 最小完成标准

首批完成必须同时满足：

```text
1. pytest 新增测试通过
2. 当前 bundle 从第 6 节点继续跑完第 10 节点
3. validate-output pass
4. AIDev tsc pass
5. runtime_proof 仍明确标 not_run，不能冒充 pass
```

如果继续做 runtime 验收，则追加：

```text
6. PIE runtime evidence 覆盖 movement / attack / pickup / reward / enemy / encounter
7. runtime_proof 更新为 pass
```

## 11. 验收记录模板

每次验收写入：

```text
docs/phase3-real-run/test/PrimitiveRecipeRuntime验收记录-<timestamp>.md
```

记录格式：

```markdown
# PrimitiveRecipeRuntime 验收记录

## 环境

- AutoUE commit:
- AIDev project:
- UE editor:
- Map:
- Bundle:

## 命令与结果

| 层级 | 命令 | 结果 | 证据 |
|---|---|---|---|
| L1 pytest | ... | PASS/FAIL | ... |
| L2 node run | ... | PASS/FAIL | ... |
| L2 validate-output | ... | PASS/FAIL | ... |
| L3 AIDev tsc | ... | PASS/FAIL | ... |
| L4 PIE proof | ... | PASS/FAIL/NOT_RUN | ... |

## 失败项

- 

## 结论

- static_support:
- runtime_proof:
- 是否完成:
```

