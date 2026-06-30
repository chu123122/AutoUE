# EncounterSpecPlanner 节点与敌人生成系统计划

状态：计划文档，未实现。  
日期：2026-06-30。  
范围：只记录设计、修改点和验收规则；本文件不代表代码、prompt、workflow、UE 蓝图或 TS runtime 已经修改。

## 1. 本轮决策

本轮只新增一个 LLM 节点：`EncounterSpecPlanner`。

它负责把“敌人实体”和“场景刷怪点”组织成 `EncounterSpec` 遭遇配置。它不负责写代码、不负责摆场景、不负责生成坐标、不负责 SpawnActor、不负责定义敌人种类。

确定性工具单独处理场景扫描：`SceneSpawnManifestExporter`。它是 UE Editor Python 脚本，由 workflow runner 在 `EncounterSpecPlanner` 之前直接执行，不是 LLM 节点，也不由 AI 生成。

敌人生成运行时第一版用 TypeScript / PuerTS 写，不用 C++ 起步。C++ 只作为后续底层桥接候选。

## 2. 调整后的流程

当前 PuerTS 主链在计划后变成：

```text
SceneAndGameplaySplitter
→ EntityAbilityBehaviorPlanner
→ ThinGameplayFlowPlanner
→ SceneSpawnManifestExporter          # 确定性工具，不是 LLM 节点
→ EncounterSpecPlanner                # 唯一新增 LLM 节点
→ UEApiMCPFeasibilitySearcher
→ PuerTSRuntimeMappingPlanner
→ TypeScriptScriptAnalyzer
→ TypeScriptInteractiveObjectGenerator
→ TypeScriptCodeGenerator
→ EvaluateInstructionGenerator
```

说明：

- “只新增一个节点”指只新增一个 LLM 规划节点。
- `SceneSpawnManifestExporter` 是 runner 固定步骤，执行代码扫描真实 UE Level。
- 后续如果 workflow 配置里统计 active LLM 节点，预计从 9 个变成 10 个。
- 确定性工具失败时，流程必须失败，不能让 AI 编造 `spawn_group`。

## 3. EncounterSpecPlanner 的用途

`EncounterSpecPlanner` 的职责是生成遭遇计划：

```text
有哪些遭遇
什么时候触发
从哪个 spawn_group 刷怪
刷哪些 enemy entity
刷几个
预算是多少
刷怪策略是什么
遭遇如何完成
后续 runtime 应验证哪些状态
```

它只输出数据，不输出代码。

### 输入

计划输入：

```text
flow/02-structure.json
flow/03-thin-gameplay-flow.json
flow/scene-spawn-manifest.json
用户原始需求 / scene-gameplay split 上下文
```

其中：

- `02-structure.json` 提供游戏内容全集，特别是可刷敌人列表。
- `03-thin-gameplay-flow.json` 提供玩法流程和触发语义。
- `scene-spawn-manifest.json` 提供真实 UE 场景扫描出来的合法刷怪组。

### 输出

计划输出：

```text
flow/03-encounter-spec.json
flow/03-encounter-spec.md
```

`json` 给后续代码生成和 validator 消费；`md` 给人看，说明为什么这样刷怪。

## 4. EncounterSpec 数据规格

第一版 `EncounterSpec`：

```json
{
  "schema_version": "autoue-encounter-spec/v1",
  "encounters": [
    {
      "encounter_id": "room_01_initial_guard",
      "trigger": {
        "type": "on_level_start"
      },
      "spawn_group": "room_01_guard",
      "enemy_budget": 5,
      "composition": [
        {
          "enemy": "goblin_melee",
          "count": 2
        }
      ],
      "spawn_policy": {
        "avoid_camera_view": false,
        "min_distance_to_player": 400,
        "consume_spawn_point": true,
        "max_alive": 2
      },
      "completion": {
        "type": "all_spawned_enemies_defeated",
        "set_flags": ["enemy_defeated", "exit_unlocked"]
      },
      "verification_hooks": [
        "enemy_spawned",
        "enemy_health_changed",
        "enemy_defeated",
        "encounter_completed"
      ]
    }
  ]
}
```

禁止事项：

- 不允许出现 `location`、`transform`、`coordinate`、`x/y/z` 这类具体坐标。
- 不允许写 UE API 名称。
- 不允许写 TS / C++ / Blueprint 代码。
- 不允许新增 enemy id。
- 不允许引用 `scene-spawn-manifest.json` 中不存在的 `spawn_group`。
- 不允许引用 `02-structure.json` 中不存在、或不是 `spawnable enemy` 的实体。

第一版支持的 trigger：

```text
on_level_start
on_player_enter_zone
```

第一版支持的 completion：

```text
all_spawned_enemies_defeated
```

第一版支持的 spawn policy：

```text
avoid_camera_view
min_distance_to_player
consume_spawn_point
max_alive
```

## 5. SceneSpawnManifestExporter 工具计划

`SceneSpawnManifestExporter` 是确定性 UE Editor Python 脚本。它不由 AI 生成，不作为 LLM 节点运行，而是由 workflow runner 在 `EncounterSpecPlanner` 之前直接执行。

计划文件：

```text
tools/unreal/export_scene_spawn_manifest.py
tools/validate_scene_spawn_manifest.py
```

运行形态：

```text
UnrealEditor.exe <Project>.uproject -ExecutePythonScript=tools/unreal/export_scene_spawn_manifest.py -- <args>
```

计划参数：

```text
--map /Game/...
--out <demo_dir>/flow/scene-spawn-manifest.json
```

脚本行为：

```text
打开指定 Map
遍历当前 Level Actor
识别 BP_EnemySpawnPoint / BP_EnemySpawnArea / BP_EncounterZone
读取公开属性
按 spawn_group 聚合
输出 scene-spawn-manifest.json
调用规格检查
```

识别规则：

- 不靠 Actor 实例名，例如 `BP_EnemySpawnPoint_12`。
- 优先靠 Blueprint class、Actor tag、稳定公开属性。
- 需要的属性由蓝图规范固定。

### 蓝图字段规范

`BP_EnemySpawnPoint`：

```text
SpawnGroup: string
SpawnRole: string
AllowedEnemyTags: string[]
CanInitialSpawn: bool
CanRuntimeSpawn: bool
ConsumeOnUse: bool
MinPlayerDistance: number
AvoidCameraView: bool
```

`BP_EnemySpawnArea`：

```text
SpawnGroup: string
AllowedEnemyTags: string[]
MaxSpawnCount: number
GroundOnly: bool
AvoidCameraView: bool
MinPlayerDistance: number
```

`BP_EncounterZone`：

```text
ZoneId: string
TriggerType: string
SpawnGroup: string
OneShot: bool
```

### scene-spawn-manifest 输出规格

```json
{
  "schema_version": "autoue-scene-spawn-manifest/v1",
  "level_name": "Lvl_TestRoom",
  "spawn_groups": [
    {
      "spawn_group": "room_01_guard",
      "source_types": ["EnemySpawnPoint"],
      "point_count": 3,
      "area_count": 0,
      "allowed_enemy_tags": ["ground", "melee"],
      "can_initial_spawn": true,
      "can_runtime_spawn": false
    }
  ],
  "encounter_zones": [
    {
      "zone_id": "room_01_entry_zone",
      "trigger": "on_player_enter_zone",
      "spawn_group": "room_01_guard",
      "one_shot": true
    }
  ]
}
```

### manifest 校验规则

`tools/validate_scene_spawn_manifest.py` 计划检查：

- `schema_version` 正确。
- `spawn_group` 非空且唯一聚合。
- 每个 `spawn_group` 至少有一个 point 或 area。
- `allowed_enemy_tags` 是数组。
- `can_initial_spawn` / `can_runtime_spawn` 是 bool。
- `zone_id` 非空且唯一。
- `EncounterZone.spawn_group` 必须存在。
- `trigger` 必须属于允许值。

如果真实 UE 环境不可用：

- 真实流程必须失败，不能伪造 manifest。
- 单元测试可以使用 fixture manifest，但必须标明 fixture。

## 6. 敌人生成系统设计

第一版用 TypeScript / PuerTS 实现运行时系统。

原因：

- 当前 AutoUE 目标是 PuerTS / TypeScript 工作流。
- `EncounterSpec` 是数据配置，运行时主要是编排：读 JSON、查点位、过滤、Spawn、记录状态。
- TS 热迭代更快，能和当前 `TypeScriptCodeGenerator`、AIDev adapter、PIE harness 保持一条链。
- C++ 会引入 UE 模块编译和更重的环境依赖，不适合第一版验证节点闭环。

C++ 后续只在这些情况再考虑：

```text
PuerTS 无法稳定访问必要 UE API
需要复杂导航 / 碰撞查询
需要大量敌人对象池
需要多人同步
需要 Editor 原生组件或 Subsystem
```

长期形态可以是：C++ 做底层薄桥，TS 继续负责 Encounter 编排。

### TS runtime 模块

计划由 `TypeScriptCodeGenerator` 生成或接入以下稳定模块：

```text
AutoUEGeneratedEncounterSpec.ts
AutoUEGeneratedEnemyArchetypes.ts
AutoUESpawnPointRegistry.ts
AutoUEEnemyArchetypeRegistry.ts
AutoUEEnemySpawnManager.ts
AutoUEEncounterManager.ts
```

职责：

`SpawnPointRegistry`：

```text
运行时收集 BP_EnemySpawnPoint / BP_EnemySpawnArea
按 spawn_group 建索引
提供 getSpawnPoints / getSpawnAreas 查询
```

`EnemyArchetypeRegistry`：

```text
维护 enemy_id -> 敌人运行时创建方式
enemy_id 必须来自 02-structure
第一版可以映射到 Blueprint class path 或 TS mesh proxy
```

`EnemySpawnManager`：

```text
读取 EncounterSpec.composition
根据 spawn_group 找合法点
执行 min_distance / avoid_camera / consume_spawn_point / max_alive 过滤
生成敌人
返回 spawned enemy handles
```

`EncounterManager`：

```text
加载 EncounterSpec
监听 on_level_start / on_player_enter_zone
启动 encounter
记录 alive enemies
监听敌人死亡
判断 all_spawned_enemies_defeated
设置 encounter_completed / exit_unlocked 等状态
```

运行流程：

```text
BeginPlay
→ SpawnPointRegistry 扫描当前 Level
→ EnemyArchetypeRegistry 注册可刷敌人
→ EncounterManager 加载 EncounterSpec
→ 触发 on_level_start
→ EnemySpawnManager 根据 spawn_group 生成敌人
→ 敌人受击 / 死亡
→ EncounterManager 判断 completion
→ 后续状态变化，例如 exit_unlocked
```

硬规则：

- 只有 `EnemySpawnManager` 可以生成敌人。
- 普通 ability 代码不得到处直接 `SpawnActor` 生成敌人。
- 敌人死亡、alive 计数、encounter 完成由 `EncounterManager` 统一记录。
- `EncounterSpec` 不写坐标，坐标只来自运行时 registry 找到的真实点位。

## 7. EntityAbilityBehaviorPlanner 升级计划

`EntityAbilityBehaviorPlanner` 要升级为“游戏内容全集”的源头。

原则：

```text
游戏里会影响玩法状态、表现或验证的东西，都必须先成为实体。
```

包括：

```text
player
enemy
trap
exit
pickup
projectile
camera helper
VFX owner
HUD state owner
trigger zone
```

不包括：

```text
EnemySpawnManager
EncounterManager
Registry
validator
runner
```

这些是系统基础设施，不是游戏内容实体。

### 计划 schema 增量

实体新增字段：

```json
{
  "entity_id": "goblin_melee",
  "entity_kind": "enemy",
  "display_name": "Goblin Melee",
  "summary": "Ground melee enemy.",
  "content_tags": ["enemy", "ground", "melee"],
  "spawnable": true,
  "enemy_profile": {
    "cost": 2,
    "allowed_spawn_tags": ["ground", "melee"],
    "default_health": 2
  },
  "abilities": []
}
```

规则：

- 敌人必须 `entity_kind = enemy`。
- 可由 EncounterSpec 刷出的敌人必须 `spawnable = true`。
- 可刷敌人必须带 `enemy_profile.cost`。
- `content_tags` 用来和 SpawnPoint 的 `AllowedEnemyTags` 匹配。
- 陷阱、出口、摄像机、VFX 等也必须是明确实体，不能在代码生成阶段临时冒出来。
- `BP_EnemySpawnPoint` / `BP_EnemySpawnArea` 不进入实体树；它们是场景标记，归 `scene-spawn-manifest`。
- `BP_EncounterZone` 如果有玩家可触发行为，可以作为 `entity_kind = trigger` 的实体；如果只是扫描辅助，也可以只留在 manifest。

### 需要防止的问题

以前可能出现的问题：

```text
代码里临时创建 Enemy / Camera / Exit
但 02-structure 里没有对应实体
```

升级后要通过 validator 和 trace 防止：

```text
TypeScriptCodeGenerator 生成的 gameplay object / archetype / encounter 引用必须能追溯到 02-structure 的 entity_id
```

## 8. TypeScriptCodeGenerator 的消费方式

`TypeScriptCodeGenerator` 不再自己发明敌人生成规则。

它计划读取：

```text
flow/02-structure.json
flow/03-thin-gameplay-flow.json
flow/03-encounter-spec.json
flow/scene-spawn-manifest.json
flow/05-puerts-runtime-mapping.json
```

然后生成：

```text
EncounterSpec 数据文件
EnemyArchetype 映射
TS Encounter runtime glue
必要的 adapter 接入代码
```

它可以生成 glue，但稳定运行时系统应尽量来自模板，避免每次让 AI 临场写一套刷怪系统。

## 9. MCP 查询边界

`EncounterSpecPlanner` 不查 UE API。

MCP 查询仍由 `UEApiMCPFeasibilitySearcher` 做。新增 Encounter 后，需要 MCP / runtime mapping 覆盖的 engine ports 主要是：

```text
运行时获取 Level Actor / tag / class
SpawnActor 或等价生成 Actor
读取 Actor transform
距离玩家过滤
可见性 / camera 过滤，如果第一版启用
触发区 overlap / player enter zone
Actor destroy / hide / defeated state
```

这些 API 能力不在 `EncounterSpecPlanner` 里判断，而是在后续 MCP 和 runtime mapping 里证明。

## 10. Validator 与验收计划

需要新增或扩展校验：

```text
validate_scene_spawn_manifest.py
EncounterSpecPlanner output validator
phase2/phase3 cross validator
```

EncounterSpec 校验：

- `encounter_id` 唯一。
- `spawn_group` 存在于 `scene-spawn-manifest.json`。
- `enemy` 存在于 `02-structure.json`。
- `enemy.entity_kind == enemy`。
- `enemy.spawnable == true`。
- `composition.count > 0`。
- `sum(enemy_profile.cost * count) <= enemy_budget`。
- `trigger.type` 属于允许值。
- `completion.type` 属于允许值。
- 不允许坐标字段。

跨节点校验：

```text
02-structure enemy entity
→ 03-encounter-spec composition enemy
→ TypeScript generated enemy archetype
→ runtime summary enemy_spawned / enemy_defeated
```

最小 runtime 验收：

```text
UE 场景里手动摆 3 个 BP_EnemySpawnPoint
exporter 导出 scene-spawn-manifest.json
EncounterSpecPlanner 生成 1 个 on_level_start encounter
TypeScriptCodeGenerator 生成或接入 TS EnemySpawnManager / EncounterManager
PIE 中敌人成功生成
攻击后 enemy_defeated
Encounter completed
```

## 11. 计划修改文件清单

只列计划，不代表已经实现。

新增：

```text
prompts/encounter_spec_planner.md
custom_nodes/encounter_spec_planner.py
tools/unreal/export_scene_spawn_manifest.py
tools/validate_scene_spawn_manifest.py
docs/phase3-real-run/design/EncounterSpecPlanner节点与敌人生成系统计划.md
```

修改：

```text
config/workflows/puerts_ts.json
prompts/entity_ability_behavior_planner.md
custom_nodes/entity_ability_behavior_planner.py
core/phase2_validation.py
tools/validate_phase2_outputs.py
custom_nodes/typescript_code_generator.py
prompts/typescript_code_generator.md
```

可能新增测试：

```text
tests/test_encounter_spec_planner.py
tests/test_scene_spawn_manifest_validation.py
tests/fixtures/scene-spawn-manifest.valid.json
tests/fixtures/encounter-spec.valid.json
```

## 12. 实施顺序建议

后续真正实现时按这个顺序：

```text
1. 先升级 EntityAbilityBehaviorPlanner schema 和 validator
2. 加 scene-spawn-manifest schema 与 validate_scene_spawn_manifest.py
3. 写 UE Editor Python exporter，并用手摆测试场景导出真实 manifest
4. 加 EncounterSpecPlanner prompt / node / validator
5. 更新 puerts_ts.json，在 ThinGameplayFlowPlanner 后插入 EncounterSpecPlanner
6. 更新 UEApiMCPFeasibilitySearcher / RuntimeMapping 的上下文，让 encounter runtime 所需 engine ports 被查询
7. 更新 TypeScriptCodeGenerator，接入稳定 TS 敌人生成系统模板
8. 加 fixture 单测和真实 run 验证
```

## 13. 当前未完成项

本文件只完成设计落档。以下内容尚未实现：

```text
EncounterSpecPlanner 节点代码
EncounterSpecPlanner prompt
workflow 配置插入
UE Editor Python exporter
manifest validator
EntityAbilityBehaviorPlanner schema 升级
TS EnemySpawnManager / EncounterManager
TypeScriptCodeGenerator 消费 EncounterSpec
真实 UE/PIE 验证
```

不能把本计划文档当成节点已接入或敌人生成系统已完成。
