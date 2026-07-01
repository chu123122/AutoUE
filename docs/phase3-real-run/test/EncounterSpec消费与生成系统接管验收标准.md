# EncounterSpec 消费与生成系统接管验收标准

## 目标

生成链路不能再绕过 `EncounterSpecPlanner`：

- 具体遭遇配置必须进入 runtime mapping 和 TypeScript codegen。
- 敌人单位必须由 `EncounterManager -> EnemySpawnManager -> SpawnPointRegistry -> EnemySpawnRuntime` 管理生成。
- 禁止主 runtime 直接硬编码生成敌人位置、数量、行为。

## 硬门禁

### 1. RuntimeMappingCompiler

当 `EncounterSpecPlanner` 输出包含 `encounters` 时，`PuerTSRuntimeMappingCompiler` 必须：

- 写出 `encounter_spec_path`。
- 写出 `scene_spawn_manifest_path`。
- 内嵌 `encounter_spec` 数据。
- 启用 runtime features：
  - `encounter_spec_data`
  - `spawn_point_registry`
  - `enemy_spawn_manager`
  - `encounter_manager`
  - `enemy_spawn_runtime`
- 禁止把 `enemy_runtime` 或 `encounter` 标为 disabled。

对应实现：

- `tools/workflow_steps/puerts_runtime_mapping.py`
- `core/validation/node_validators/puerts_runtime_mapping_planner.py`

### 2. TypeScriptCodeGenerator

当 `EncounterSpec` 含 encounters 时，codegen 必须生成以下文件：

- `TypeScript/content/generated/AutoUEGeneratedEncounterSpec.ts`
- `TypeScript/content/generated/AutoUESpawnPointRegistry.ts`
- `TypeScript/content/generated/AutoUEEnemySpawnManager.ts`
- `TypeScript/content/generated/AutoUEEncounterManager.ts`

对应实现：

- `tools/workflow_steps/typescript_runtime_template_plan.py`
- `core/validation/node_validators/typescript_code_generator.py`

### 3. 主 runtime 禁止绕过生成系统

`AutoUEGeneratedRuntime.ts` 必须包含：

- `getAutoUEGeneratedEncounterSpec`
- `startInitialEncounters`
- `AutoUEEnemySpawnManager`
- `AutoUESpawnPointRegistry`

并且不得包含：

- `spawnGeneratedEnemies`
- `enemySpawnBehaviors`
- `const x = 340`
- `FLOOR_Z + 40 }`
- `services.enemySpawn.spawnEnemy(behavior, transform)`

对应实现：

- `tools/validate_workflow_outputs.py::validate_encounter_runtime_consumption`

### 4. UE 项目落地验收

最后写代码节点执行后，`aidev-stage-report.json` 必须显示：

- `apply: true`
- 目标为真实 AIDev 根目录。
- `tsc.returncode == 0`

### 5. Runtime 验收日志

运行时必须按顺序看到以下关键日志，才算“生成系统接管单位生成”：

```text
SpawnPointRegistryReady
SpawnPointAcquired
EnemyPhysicsReady
AliveEnemyRegistered
EnemySpawnedByEncounter
EncounterStarted
EnemyRuntimeReady managed_by=EncounterManager
```

如果 `SpawnPointAcquired` 位置不对，优先检查场景里的 `BP_EnemySpawnPoint` / manifest 导出数据；这时 runtime 已经消费真实出生点，不再是主 runtime 硬编码位置。

可执行验收命令：

```powershell
python tools\unreal\validate_autoue_runtime_log.py <Unreal运行日志> --write-report <report.json>
```

判定规则：

- `result == pass` 才代表 EncounterSpec 已被 runtime 实际消费。
- `EnemySpawnedByEncounter.spawn_group + spawn_point` 必须能对应前面的 `SpawnPointAcquired.spawn_group + actor`。
- 不允许出现：
  - `RuntimeModuleUnavailable`
  - `EnemySpawnManagerRejected`
  - `SpawnPointMissing`
  - PuerTS runtime error 日志
- 已知 `EndPIE` 之后的 `~FScriptArrayEx: Property is invalid` 属于 PuerTS shutdown 噪声，验收脚本会记录到 `ignored_puerts_error_lines`，不作为生成 runtime 失败。
- 如果要额外验“敌人进入感知并开始战斗”，再加：

```powershell
python tools\unreal\validate_autoue_runtime_log.py <Unreal运行日志> --require-in-range --require-enemy-move
```

注意：`--require-in-range --require-enemy-move` 是战斗/移动验收，不是“生成系统接管”验收。它失败通常说明玩家和出生点距离超过敌人感知范围，或者出生点布置不适合该案例。

### 6. PIE 验收

PIE 必须证明：

- 真实 PIE world 存在。
- 当前 GameMode 是生成的 `AutoUEGeneratedGameModeAdapter`。
- 当前 Pawn 是生成的 `AutoUEGeneratedCharacterAdapter`。
- 生成敌人进入 PIE world。
- 自动输入/靠近敌人后，敌人进入感知范围并产生移动/攻击/死亡/遭遇完成证据。

可执行脚本：

```text
tools\unreal\run_autoue_pie_validation.py
```

该脚本由 Unreal Editor 的 `-ExecutePythonScript` 执行，不是在普通 Python 里直接跑。

当前验证使用的启动方式：

```powershell
D:\UE-src-5.7\Engine\Binaries\Win64\UnrealEditor.exe `
  D:\UE5.7.4\AIDev\AIDev.uproject `
  /Game/Castlevania2D `
  -nop4 -nosplash -unattended -NullRHI `
  -ExecutePythonScript=D:\ClaudeTasks\active\autoue-puerts-workflow-adaptation\repo\AutoUE\tools\unreal\run_autoue_pie_validation.py
```

PIE 报告：

```text
test_tmp\autoue-pie-validation-current.json
```

PIE 运行日志：

```text
test_tmp\autoue_pie_validation_20260630.log
```

## 当前已验证样例

样例 bundle：

```text
test_tmp\dead_cells_encounter_runtime_consumed_20260630\output\demo_1
```

验证命令：

```powershell
python tools\validate_workflow_outputs.py --bundle test_tmp\dead_cells_encounter_runtime_consumed_20260630\output\demo_1 --write-report
python tools\unreal\validate_autoue_runtime_log.py test_tmp\aidev_headless_game_20260630.log --write-report test_tmp\aidev_headless_game_20260630.runtime-report.json
python tools\validate_workflow_outputs.py --bundle test_tmp\dead_cells_pie_validation_20260630\output\demo_1 --write-report
python tools\unreal\validate_autoue_runtime_log.py test_tmp\autoue_pie_validation_20260630.log --require-in-range --require-enemy-move --write-report test_tmp\autoue_pie_validation_20260630.runtime-report.json
```

报告中必须有：

```json
"encounter_runtime_consumption": "checked"
```

运行日志报告必须有：

```json
{
  "result": "pass",
  "enemies_spawned_by_encounter": [
    {
      "encounter": "room_01_initial_guard",
      "spawn_group": "room_01_guard",
      "spawn_point": "BP_EnemySpawnPoint_C_2"
    }
  ]
}
```

当前 PIE 报告必须有：

```json
{
  "result": "pass",
  "moved_near_enemy": true,
  "enemy_count": 1
}
```

并且 PIE 日志报告必须有：

```json
{
  "result": "pass",
  "enemy_detected_in_range": true,
  "enemy_movement_count": 294
}
```
