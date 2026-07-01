# Primitive + Recipe Runtime 实现方案

> 目标：把当前 `PuerTSRuntimeMappingCompiler` 卡住的 `player.behavior.move_and_attack` 与 `pickup.behavior.collect_reward` 从“仅被能力库选中”推进到“有可组合 runtime 实现、可生成 TS、可静态验收、可进入 AIDev/PIE 验证”。

## 1. 当前问题

当前链路已经能完成：

```text
用户需求
→ SceneAndGameplaySplitter
→ EntityAbilityBehaviorPlanner
→ ThinGameplayFlowPlanner
→ EncounterSpecPlanner
→ UEApiMCPFeasibilitySearcher
```

但到第 6 节点：

```text
PuerTSRuntimeMappingCompiler
```

会被 support matrix 拦住：

```text
pickup.collect.grant_reward
pickup.feedback.spawn_reward_visual
player.movement.move_actor
player.attack.apply_damage
```

对应行为：

```text
pickup.behavior.collect_reward
player.behavior.move_and_attack
```

根因不是 LLM 没拆出来，也不是 UE API 不存在，而是当前 runtime 合同里这些能力没有正式 handler、模板和验证闭环。

## 2. 重要判断：support matrix 不是 runtime proof

当前 `core/runtime_support_matrix.py` 只回答：

```text
这个 capability 是否登记为“静态可生成”
```

它不等于：

```text
TS 已生成
TS 已编译
AIDev 已接入
PIE 里真实触发
日志证明玩法发生
```

因此，之前敌人 runtime 虽然比 player/pickup 走得更远，已经有：

```text
EnemySpawnRuntime
EnemyMovement
EnemyCombat
EnemyHealth
EnemyDeathEvents
EncounterManager
```

但如果没有真实 runtime evidence，也仍然可能停留在“静态看起来成功”。  
后续必须把状态拆成：

```text
static_support = supported / unsupported
runtime_proof = not_run / pass / fail
```

不能把 support matrix 通过当作最终完成。

## 3. 现有可复用基础

当前已经有“参数跟随”的雏形：

```text
capability.default_params
entity.capability_bindings.params
behavior.capability_overrides
behavior.resolved_capabilities
behavior.runtime_params
TS runtime handler 读取 params
```

关键代码：

```text
core/behavior_spec.py
core/runtime_support_matrix.py
templates/typescript/enemy_movement.ts.tmpl
templates/typescript/enemy_combat.ts.tmpl
templates/typescript/enemy_spawn_runtime.ts.tmpl
```

例如敌人移动模板中同一个实现读取不同参数：

```text
params.move_speed || enemy.runtime_params?.move_speed
```

敌人攻击模板中读取：

```text
params.attack_damage || enemy.runtime_params?.attack_damage
params.cooldown_seconds || enemy.runtime_params?.cooldown
```

这个方向要保留，并扩展到 player、pickup、reward、feedback。

## 4. 三种实现方向

### 4.1 方向一：继续 Handler Registry，补齐 player/pickup handler

做法：

```text
player.movement.move_actor
  -> PlayerMovementRuntime.moveActor

player.attack.apply_damage
  -> PlayerCombatRuntime.applyDamage

pickup.collect.grant_reward
  -> PickupRuntime.grantReward

pickup.feedback.spawn_reward_visual
  -> RewardFeedbackRuntime.spawnRewardVisual
```

需要新增模板：

```text
templates/typescript/player_movement_runtime.ts.tmpl
templates/typescript/player_combat_runtime.ts.tmpl
templates/typescript/pickup_runtime.ts.tmpl
templates/typescript/reward_feedback_runtime.ts.tmpl
```

优点：

- 最快 unblock 当前 bundle。
- 和现有敌人 runtime 模式一致。
- 改造半径小。

缺点：

- 自由组合性一般。
- 每加新行为都容易新增一个专用 runtime。
- 容易从“能力库”退化成“handler 列表”。

适合：

- 快速补当前 4 个 unsupported capability。
- 作为短期 unblock 方案。

### 4.2 方向二：完全组件式 Ability Runtime

做法：把行为拆成可组合组件。

组件示例：

```text
InputTrigger
OverlapTrigger
CooldownGate
StateGate
MovementMotor
HitShape
TargetFilter
DamageApplier
RewardGrant
VisibilityFeedback
HudFeedback
DestroyOrHideEntity
CameraImpulse
```

`player.behavior.move_and_attack` 编译成：

```text
input_axis
→ movement_motor
→ input_action
→ cooldown_gate
→ hit_shape
→ target_filter
→ damage_applier
```

`pickup.behavior.collect_reward` 编译成：

```text
overlap_trigger
→ once_gate
→ reward_grant
→ hud_feedback
→ visibility_feedback
→ consume_entity
```

优点：

- 自由组合性最好。
- 同一个移动/攻击/反馈/奖励组件可被 player、enemy、trap、pickup、platform 复用。
- 适合长期能力库。

缺点：

- 改造量最大。
- 需要完整组件调度器。
- 需要定义组件输入输出协议。
- validator 复杂度高。

适合：

- 作为最终演进方向。
- 不适合直接一步到位改完当前链路。

### 4.3 方向三：Primitive + Behavior Recipe 混合方案

这是推荐方案。

核心分层：

```text
Primitive Runtime：稳定、可复用的小能力
Behavior Recipe：把行为展开为 primitive 组合
```

Primitive 示例：

```text
input.read_axis
input.read_action
movement.apply_intent
hit.resolve_melee
damage.apply
overlap.detect
reward.grant
feedback.set_visibility
feedback.hud_update
entity.consume
timer.cooldown_gate
timer.once_gate
```

Behavior Recipe 示例：

```text
player.behavior.move_and_attack
  = input.read_axis
  + movement.apply_intent
  + input.read_action
  + timer.cooldown_gate
  + hit.resolve_melee
  + damage.apply

pickup.behavior.collect_reward
  = overlap.detect
  + timer.once_gate
  + reward.grant
  + feedback.hud_update
  + feedback.set_visibility
  + entity.consume
```

优点：

- 比方向一更可扩展。
- 比方向二更容易落地。
- 复用当前 `support_matrix`、`behavior_spec`、`resolved_capabilities`、TS 模板体系。
- 可以逐步把敌人 runtime 从专用 handler 迁移到 primitive recipe。

缺点：

- 需要新增 recipe schema。
- `core/behavior_spec.py` 需要从硬编码 action 表过渡到 recipe 编译。
- 短期内会出现“旧 enemy handler + 新 primitive recipe”共存。

结论：采用方向三。

## 5. 推荐目标架构

```text
EntityAbilityBehaviorPlanner
  选择实体 / 能力 / 行为 ID

ThinGameplayFlowPlanner
  行为拆成薄 gameplay flow

PuerTSRuntimeMappingCompiler
  读取 behavior recipe
  展开 primitive_plan
  检查 primitive support
  生成 BehaviorSpec + RuntimeMapping

TypeScriptImplementationSlotProjector
  根据 primitive_plan 推导实现槽位

TypeScriptRuntimeTemplatePlanner
  根据 required_runtime_modules 选择 TS 模板

StaticEvaluationPlanBuilder
  生成静态与 runtime 验收说明
```

## 6. 新增 Primitive Registry

新增：

```text
core/runtime_primitives.py
```

定义：

```python
PrimitiveEntry(
    primitive_id="damage.apply",
    handler="DamageRuntime.apply",
    required_runtime_modules=["damage_runtime", "world_adapter"],
    engine_ports=["gameplay_statics.apply_damage"],
    params_schema={...},
    supported=True,
)
```

首批 primitive：

```text
input.read_axis
input.read_action
movement.apply_intent
hit.resolve_melee
damage.apply
overlap.detect
reward.grant
feedback.set_visibility
feedback.hud_update
entity.consume
timer.cooldown_gate
timer.once_gate
state.write
state.read
```

## 7. 新增 Behavior Recipe Registry

新增：

```text
core/behavior_recipes.py
```

### 7.1 player.behavior.move_and_attack recipe

```json
{
  "behavior_id": "player.behavior.move_and_attack",
  "recipe": [
    {
      "primitive_id": "input.read_axis",
      "outputs": ["move_intent"]
    },
    {
      "primitive_id": "movement.apply_intent",
      "inputs": ["move_intent"],
      "params": {
        "speed": "$entity.move_speed",
        "dash_speed": "$entity.dash_speed"
      }
    },
    {
      "primitive_id": "input.read_action",
      "params": {
        "action": "attack"
      },
      "outputs": ["attack_intent"]
    },
    {
      "primitive_id": "timer.cooldown_gate",
      "inputs": ["attack_intent"],
      "params": {
        "cooldown": "$entity.attack_cooldown"
      }
    },
    {
      "primitive_id": "hit.resolve_melee",
      "outputs": ["hit_targets"],
      "params": {
        "range": "$entity.attack_range",
        "radius": "$entity.hitbox_radius",
        "target_tags": ["enemy"]
      }
    },
    {
      "primitive_id": "damage.apply",
      "inputs": ["hit_targets"],
      "params": {
        "amount": "$entity.attack_damage"
      }
    }
  ]
}
```

### 7.2 pickup.behavior.collect_reward recipe

```json
{
  "behavior_id": "pickup.behavior.collect_reward",
  "recipe": [
    {
      "primitive_id": "overlap.detect",
      "outputs": ["pickup_overlap"],
      "params": {
        "target": "player"
      }
    },
    {
      "primitive_id": "timer.once_gate",
      "inputs": ["pickup_overlap"]
    },
    {
      "primitive_id": "reward.grant",
      "params": {
        "reward_type": "$entity.reward_type",
        "amount": "$entity.reward_amount"
      }
    },
    {
      "primitive_id": "feedback.hud_update"
    },
    {
      "primitive_id": "feedback.set_visibility",
      "params": {
        "visible": false
      }
    },
    {
      "primitive_id": "entity.consume"
    }
  ]
}
```

## 8. 参数解析规则

统一参数优先级：

```text
1. behavior capability_overrides
2. entity capability_bindings.params
3. entity runtime params
4. capability default_params
5. primitive default_params
```

新增或整理：

```text
core/behavior_spec.py
  resolve_recipe_params(...)
```

目标：

```text
同一个 primitive 实现不写死实体。
不同表现和不同数值通过 entity/capability/behavior 参数驱动。
```

## 9. BehaviorSpec 输出扩展

当前 `flow/06-behavior-spec.json` 需要扩展：

```json
{
  "behavior_id": "player.behavior.move_and_attack",
  "resolved_capabilities": [],
  "primitive_plan": [
    {
      "primitive_id": "movement.apply_intent",
      "handler": "MovementRuntime.applyIntent",
      "params": {
        "speed": 620
      },
      "required_runtime_modules": ["movement_runtime", "input_runtime"],
      "engine_ports": ["pawn.add_movement_input"]
    }
  ],
  "presentation_effects": []
}
```

区分：

```text
primitive_plan：玩法逻辑
presentation_effects：表现组合
```

表现组合不写死在奖励、攻击、移动里面。

## 10. TS Runtime 模板

新增或整理：

```text
templates/typescript/player_movement_runtime.ts.tmpl
templates/typescript/player_combat_runtime.ts.tmpl
templates/typescript/hit_query_runtime.ts.tmpl
templates/typescript/damage_runtime.ts.tmpl
templates/typescript/pickup_runtime.ts.tmpl
templates/typescript/reward_runtime.ts.tmpl
templates/typescript/feedback_runtime.ts.tmpl
```

首批 runtime 职责：

### 10.1 MovementRuntime

```text
读取 input axis
应用移动
支持 frozen / movement_gate
输出 MoveApplied / MoveBlocked 日志
```

### 10.2 PlayerCombatRuntime

```text
读取 attack action
判断 cooldown
调用 HitQueryRuntime.resolveMelee
调用 DamageRuntime.apply
输出 PlayerAttackResolved 日志
```

### 10.3 HitQueryRuntime

```text
按 range/radius/target_tags 查目标
输出 HitResolved 日志
```

### 10.4 DamageRuntime

```text
调用 WorldAdapter.applyDamage
输出 DamageApplied 日志
```

### 10.5 PickupRuntime

```text
绑定 overlap
once gate
调用 RewardRuntime.grant
调用 FeedbackRuntime
consume pickup
输出 PickupOverlap / PickupConsumed 日志
```

### 10.6 RewardRuntime

```text
写 currency / inventory / player_stats
输出 RewardGranted 日志
```

### 10.7 FeedbackRuntime

```text
HUD 更新
可见性切换
VFX 触发
输出 HudUpdated / VisibilityChanged 日志
```

## 11. TypeScript 模板选择逻辑

修改：

```text
tools/workflow_steps/typescript_runtime_template_plan.py
```

目标：

```text
根据 primitive_plan.required_runtime_modules 确定性选择模板
不要让 LLM 猜模板
```

示例映射：

```text
movement_runtime
  -> templates/typescript/player_movement_runtime.ts.tmpl

player_combat_runtime
  -> templates/typescript/player_combat_runtime.ts.tmpl

hit_query_runtime
  -> templates/typescript/hit_query_runtime.ts.tmpl

damage_runtime
  -> templates/typescript/damage_runtime.ts.tmpl

pickup_runtime
  -> templates/typescript/pickup_runtime.ts.tmpl

reward_runtime
  -> templates/typescript/reward_runtime.ts.tmpl

feedback_runtime
  -> templates/typescript/feedback_runtime.ts.tmpl
```

## 12. support gate 改造

当前：

```text
capability supported?
```

目标：

```text
capability has recipe?
recipe primitives all supported?
primitive has handler?
primitive has runtime module?
runtime module has template?
```

输出结构：

```json
{
  "schema_version": "autoue-runtime-support-check/v2",
  "static_support": "supported",
  "runtime_proof": "not_run",
  "unsupported_capabilities": [],
  "unsupported_primitives": [],
  "required_runtime_modules": []
}
```

## 13. validator 改造

修改：

```text
core/validation/node_validators/puerts_runtime_mapping_planner.py
core/validation/node_validators/typescript_code_generator.py
```

新增检查：

```text
primitive_plan 不为空
primitive_id 必须存在于 registry
handler 不为空
required_runtime_modules 必须有模板或已存在实现
params 满足 schema
unsupported_primitives 为空
blocked_mappings 为空
enemy_runtime 不能绕过 primitive proof
```

## 14. 敌人 runtime 的处理方式

短期：

```text
保留当前 EnemySpawnRuntime / EnemyMovement / EnemyCombat。
不要为了 player/pickup 改崩敌人链路。
```

中期：

```text
给敌人行为也生成 primitive_plan。
但 runtime 仍可先调用现有 enemy handler。
```

长期：

```text
enemy.behavior.chase_and_melee
  = enemy.spawn
  + target.detect
  + movement.toward
  + hit.resolve_melee
  + damage.apply
  + health.receive_damage
  + death.emit
  + encounter.update
```

这样 enemy、player、pickup、hazard 都会走同一套 primitive proof。

## 15. 实施顺序

### 批次 1：静态 unblock

```text
1. 新增 core/runtime_primitives.py
2. 新增 core/behavior_recipes.py
3. 改 core/behavior_spec.py 输出 primitive_plan
4. 改 core/runtime_support_matrix.py 或新增 recipe support check
5. 补 player/pickup/reward/feedback runtime 模板
6. 改 TypeScriptRuntimeTemplatePlanner 模板选择
7. 改 validator
8. 跑当前 bundle 第 6 节点
```

目标：

```text
PuerTSRuntimeMappingCompiler pass
```

### 批次 2：全链路生成

```text
9. 继续跑 TypeScriptImplementationSlotProjector
10. 继续跑 TypeScriptInteractiveTemplatePlanner
11. 继续跑 TypeScriptRuntimeTemplatePlanner
12. 继续跑 StaticEvaluationPlanBuilder
13. validate-output pass
```

目标：

```text
生成完整 TS 和 instructions.json
```

### 批次 3：AIDev 编译

```text
14. 同步生成 TS 到 D:\UE5.7.4\AIDev
15. tsc -p D:\UE5.7.4\AIDev\tsconfig.json
```

目标：

```text
AIDev TypeScript 编译 pass
```

### 批次 4：runtime proof

```text
16. 启动 UE/PIE
17. application-layer harness 触发移动、攻击、拾取、敌人
18. 收集 runtime log
19. validate runtime evidence
```

目标：

```text
runtime_proof = pass
```

## 16. 风险与防线

| 风险 | 防线 |
|---|---|
| 只改 `supported=True` 冒充完成 | validator 要求 handler/template/primitive_plan |
| TS 生成了但不可编译 | AIDev `tsc` 必跑 |
| support matrix 过了但 PIE 不触发 | `runtime_proof` 单独记录 |
| 表现和玩法耦死 | `primitive_plan` 与 `presentation_effects` 分离 |
| 组合爆炸 | primitive 输入输出 schema + recipe validator |
| 敌人旧逻辑继续假通过 | enemy 也逐步补 primitive_plan 和 runtime proof |

## 17. 完成定义

该方案完成不是指“第 6 节点不报错”，而是：

```text
当前 Dead Cells-like bundle 可以继续跑完全部节点；
player/pickup 不再被 support matrix 拦住；
生成 TS 可编译；
AIDev/PIE 有移动、攻击、拾取、奖励、反馈、敌人、encounter 的 runtime evidence；
support_check 明确区分 static_support 与 runtime_proof。
```

