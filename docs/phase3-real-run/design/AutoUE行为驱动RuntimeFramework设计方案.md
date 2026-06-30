---
doc_type: design
subject: autoue_behavior_driven_runtime_framework
task: autoue-puerts-workflow-adaptation
status: draft
last_updated: 2026-06-30
---

# AutoUE 行为驱动 Runtime Framework 设计方案

## 1. 核心结论

本设计用于替代“每个玩法一套 TS 玩法模板”的方向。

目标不是自研一个大而全游戏引擎，也不是重写 UE 的事件系统，而是建立一层很薄的 AutoUE 行为翻译层：

```text
三库 Entity / Capability / Behavior
  → BehaviorSpec 数据
  → RuntimeSupportMatrix 硬门禁
  → UE 原生事件绑定
  → AutoUE ActionDispatcher 执行动作链
```

关键裁决：

- `status` 不作为 Entity，也不作为 runtime feature。
- `interaction` 不作为泛化 Capability。
- UE 原生事件、Delegate、Timer、Tick、Overlap、Damage 继续作为底层事件来源。
- AutoUE 只新增最小必要框架：实体绑定、状态黑板、触发路由、条件判断、动作派发、支持矩阵。
- Runtime 模板保留为“框架源码交付模板”，不再作为“玩法专用模板”。
- Unsupported capability 必须明确 fail，不允许生成看起来成功但实际无 runtime 行为的 TS。

## 2. 三库语义边界

### 2.1 Entity Library

Entity 是能被 runtime 找到、绑定、显示、生成或引用的对象。

可以是：

```text
player
zombie
freeze_trap
poison_pool
level_exit_door
combat_damage_number_hud
freeze_vfx
gold_pickup
cursed_chest
biome_teleporter
```

不应该是：

```text
freeze_status
poison_status
curse_status
burn_status
shock_status
```

这些不是世界对象，而是运行时状态值。

### 2.2 Capability Library

Capability 是某个 Entity 能执行或承载的具体动作能力。

禁止泛化能力：

```text
<entity>.state
<entity>.interaction
```

禁止泛化行为：

```text
*.state.initialize_state
*.state.update_state
*.interaction.accept_interaction
*.interaction.resolve_interaction
```

推荐能力命名：

```text
freeze_trap.sensor.detect_player_overlap
freeze_trap.effect.apply_freeze_to_player
poison_pool.hazard.apply_poison_dot
cursed_chest.chest.open_reward
cursed_chest.curse.add_curse_counter
biome_teleporter.teleport.activate_transition
forge_station.upgrade.apply_item_upgrade
shop_room_vendor.transaction.purchase_item
combo_mutation.counter.track_kill_combo
combo_mutation.modifier.apply_damage_bonus
blood_sword.attack.apply_bleed_on_hit
level_exit_door.lock.unlock_when_enemies_dead
```

Capability 可以声明它会写入哪些运行时状态，但状态本身不是库实体：

```json
{
  "capability_id": "poison_pool.hazard.apply_poison_dot",
  "entity_id": "poison_pool",
  "capability_kind": "apply_effect",
  "action_kind": "apply_dot",
  "state_writes": ["player.effects.poison_dot"],
  "runtime_primitives": ["effect_write", "timer"]
}
```

### 2.3 Behavior Library

Behavior 描述触发条件、能力组合、运行时状态写入、事件结果和验收日志。

示例：

```json
{
  "behavior_id": "poison_pool.poison_player_on_overlap",
  "primary_entity_id": "poison_pool",
  "trigger": {
    "type": "overlap_enter",
    "source_entity_id": "player",
    "target_entity_id": "poison_pool"
  },
  "required_capability_ids": [
    "poison_pool.sensor.detect_player_overlap",
    "poison_pool.hazard.apply_poison_dot",
    "poison_vfx.emit.spawn_particles",
    "health_bar_hud.display.refresh_value"
  ],
  "effects": [
    {
      "type": "write_state",
      "key": "player.effects.poison_dot",
      "value": {"duration": 3, "damage_per_second": 5}
    },
    {
      "type": "emit_event",
      "event": "hud.health.changed"
    }
  ]
}
```

## 3. 现有薄框架与缺口

当前已有一套薄 runtime 雏形：

```text
input_harness_runtime
movement_runtime
trap_runtime
status_runtime
vfx_runtime
aid_runtime_orchestrator
encounter_manager
enemy_spawn_manager
spawn_point_registry
```

它已经证明“模块拆分”可行，但还不是通用行为框架。主要缺口：

- 没有通用 `BehaviorSpec`。
- 没有 `CapabilitySupportMatrix`。
- 没有统一 `StateBlackboard`，当前 `status_runtime` 仍偏冰冻专用。
- 没有 `TriggerRouter` 把三库 trigger 稳定绑定到 UE 原生事件。
- 没有 `ActionDispatcher` 执行数据化动作链。
- 没有 unsupported hard fail，仍容易把未实现玩法套进已有模板。

## 4. 底层行为驱动 Runtime 框架

框架分两层：Python 编译层和 TypeScript runtime 执行层。

### 4.1 Python 编译层

Python 负责确定性变换和门禁，不负责“脑补实现”。

```text
EntityAbilityBehaviorPlanner output
  + ThinGameplayFlowPlanner output
  + PuerTSRuntimeMappingPlanner output
  → BehaviorSpecCompiler
  → RuntimeSupportChecker
  → TypeScriptCodeGenerator
```

#### BehaviorSpecCompiler

输入三库展开结果和 thin flow，输出可执行数据：

```json
{
  "schema_version": "autoue-behavior-spec/v1",
  "behaviors": [
    {
      "behavior_id": "hazard.behavior.freeze_on_overlap",
      "primary_entity_id": "freeze_trap",
      "trigger": {
        "type": "overlap_enter",
        "source_entity_id": "player",
        "target_entity_id": "freeze_trap"
      },
      "conditions": [
        {"type": "state_not_active", "key": "player.effects.frozen"}
      ],
      "actions": [
        {
          "type": "write_state",
          "key": "player.effects.frozen",
          "value": {"duration": 1.25}
        },
        {
          "type": "movement_gate",
          "target_entity_id": "player",
          "blocked_by": "player.effects.frozen"
        },
        {
          "type": "set_vfx_visible",
          "entity_id": "freeze_vfx",
          "visible_while": "player.effects.frozen"
        },
        {"type": "camera_impulse", "duration": 0.35}
      ],
      "required_capability_ids": [
        "freeze_trap.sensor.detect_player_overlap",
        "freeze_trap.effect.apply_freeze_to_player",
        "freeze_vfx.emit.show_freeze",
        "side_camera.camera.apply_impulse"
      ],
      "verification_logs": [
        "BehaviorTriggered hazard.behavior.freeze_on_overlap",
        "StateWritten player.effects.frozen",
        "VfxVisible freeze_vfx",
        "CameraImpulse"
      ]
    }
  ]
}
```

#### CapabilitySupportMatrix

支持矩阵是实现契约，不是第 4 个内容库。

它回答：某类 capability/action 现在能否由 runtime 框架实现。

```json
{
  "capability_kind": "sensor_overlap",
  "action_kind": "detect_overlap",
  "handler": "TriggerRouter.bindOverlapEnter",
  "required_runtime_modules": ["world_adapter", "entity_registry", "trigger_router"],
  "engine_ports": ["primitive.on_component_begin_overlap"],
  "supported": true
}
```

Unsupported 示例：

```json
{
  "capability_kind": "boss_phase_control",
  "action_kind": "switch_boss_phase",
  "handler": null,
  "required_runtime_modules": [],
  "engine_ports": [],
  "supported": false,
  "reason": "boss phase runtime is not implemented"
}
```

#### RuntimeSupportChecker

这是硬门禁。

支持时输出：

```json
{
  "status": "supported",
  "required_runtime_modules": [
    "world_adapter",
    "entity_registry",
    "state_blackboard",
    "trigger_router",
    "action_dispatcher",
    "movement_runtime",
    "vfx_runtime",
    "camera_runtime"
  ],
  "unsupported_capabilities": []
}
```

不支持时输出：

```json
{
  "status": "unsupported",
  "unsupported_capabilities": [
    {
      "capability_id": "concierge_boss.phase.switch_at_health_threshold",
      "capability_kind": "boss_phase_control",
      "reason": "boss phase runtime is not implemented"
    }
  ],
  "unsupported_behaviors": [
    "concierge_boss.phase_attack_sequence"
  ]
}
```

如果 `unsupported_capabilities` 非空，workflow 必须 fail，且不得生成伪 TS 实现。

### 4.2 TypeScript Runtime 执行层

TS 侧是一个轻量解释器，不是玩法模板集合。

```text
AutoUEWorldAdapter
AutoUEEntityRegistry
AutoUEStateBlackboard
AutoUETriggerRouter
AutoUEConditionChecker
AutoUEActionDispatcher
AutoUEBehaviorOrchestrator
Feature Action Handlers
```

#### AutoUEWorldAdapter

集中封装 UE / PuerTS API：

```text
find actor by tag/class
spawn actor
destroy actor
get/set location
set visibility
apply damage
bind overlap
bind destroyed
read input
set HUD value
attach VFX
```

上层行为不直接散落调用 UE API，而是调用 world adapter。

#### AutoUEEntityRegistry

把三库 `entity_id` 映射到运行时对象：

```json
{
  "player": {"binding": "player_controller_pawn"},
  "freeze_trap": {"binding": "actor_tag", "tag": "AUTOUE_FREEZE_TRAP"},
  "freeze_vfx": {"binding": "attached_component", "owner": "player"},
  "combat_damage_number_hud": {"binding": "hud_widget", "widget_id": "damage_number"}
}
```

#### AutoUEStateBlackboard

替代 `status` 实体/feature。

状态是 runtime 内部数据：

```text
player.effects.frozen
player.effects.poison_dot
run.curse_count
encounter.alive_enemy_count
exit.level_exit_door.unlocked
weapon.combo_stacks
```

示例：

```ts
state.set("player.effects.frozen", {
  active: true,
  expiresAt: now + 1.25
});
```

#### AutoUETriggerRouter

不重写 UE 事件系统，只绑定 UE 原生事件。

```text
UE Delegate / Input / Timer / Tick
  → TriggerRouter
  → behavior_id
  → BehaviorOrchestrator
```

例如 overlap：

```ts
freezeTrap.Collision.OnComponentBeginOverlap.Add((overlapped, otherActor) => {
  if (entityRegistry.is(otherActor, "player")) {
    orchestrator.runBehavior("hazard.behavior.freeze_on_overlap");
  }
});
```

#### AutoUEActionDispatcher

执行 BehaviorSpec 中的数据化动作：

```text
write_state
clear_state
apply_damage
grant_reward
spawn_vfx
set_vfx_visible
set_hud_value
unlock_exit
open_exit
spawn_enemy
destroy_entity
camera_impulse
movement_gate
start_timer
```

未知 action 必须在启动前 fail，不允许运行时忽略。

## 5. Runtime 模板的新边界

Runtime 框架完成后，不再需要玩法专用模板。

禁止方向：

```text
freeze_trap_runtime.ts.tmpl
poison_pool_runtime.ts.tmpl
boss_room_runtime.ts.tmpl
shop_forge_runtime.ts.tmpl
```

允许方向：框架源码交付模板。

```text
world_adapter.ts.tmpl
entity_registry.ts.tmpl
state_blackboard.ts.tmpl
trigger_router.ts.tmpl
condition_checker.ts.tmpl
action_dispatcher.ts.tmpl
behavior_orchestrator.ts.tmpl
behavior_spec.generated.ts.tmpl
runtime_bootstrap.ts.tmpl
```

长期更理想的形态是：AIDev 预装 AutoUE runtime framework，AutoUE 每次只生成 `BehaviorSpec.generated.ts` 和绑定数据。当前阶段可以继续用模板复制框架源码，但这些模板不承载具体玩法逻辑。

## 6. Boss 房为什么可能 unsupported

Boss 房不是“一个血很厚的普通敌人”。

例如：

```text
看守者 Boss 房：Boss 有血条，阶段化攻击，玩家翻滚躲避并攻击。
```

可拆成：

```text
player.combat.attack
player.movement.dodge_roll
concierge_boss.damage.receive_hit
boss_health_bar_hud.display.refresh_value
concierge_boss.phase.switch_at_health_threshold
concierge_boss.attack_pattern.ground_slam
concierge_boss.attack_pattern.fire_wave
```

普通战斗 runtime 可能能支持：

```text
player.combat.attack
concierge_boss.damage.receive_hit
boss_health_bar_hud.display.refresh_value
```

但 Boss 阶段机制需要额外系统：

```text
血量阈值监听
阶段状态
攻击模式表
攻击选择器
攻击冷却
Boss 专用范围伤害
Boss 专用视觉反馈
```

如果没有实现这些 handler，必须明确 unsupported：

```json
{
  "status": "unsupported",
  "unsupported_capabilities": [
    {
      "capability_id": "concierge_boss.phase.switch_at_health_threshold",
      "reason": "boss phase runtime is not implemented"
    },
    {
      "capability_id": "concierge_boss.attack_pattern.ground_slam",
      "reason": "boss attack pattern runtime is not implemented"
    }
  ]
}
```

允许说“支持 Boss 外观普通敌人 + Boss 血条”，但不能伪称支持“阶段化 Boss 战”。

## 7. 商店/锻造房为什么可能 unsupported

商店/锻造不是泛化 `interaction`。

原错误表达：

```text
shop_room_vendor.interaction.resolve_interaction
forge_station.interaction.resolve_interaction
```

正确拆解应是交易/装备系统：

```text
shop_room_vendor.transaction.purchase_item
wallet.currency.check_affordability
wallet.currency.spend_gold
inventory.item.add
status_icon_hud.display.refresh_value
forge_station.upgrade.apply_item_upgrade
equipment.modifier.upgrade_stat
```

这需要 runtime 支持：

```text
CurrencyRuntime
InventoryRuntime
EquipmentRuntime
TransactionRuntime
HudRuntime
```

如果当前框架只支持 overlap、damage、state write、vfx、hud refresh，就必须 fail：

```json
{
  "status": "unsupported",
  "unsupported_capabilities": [
    {
      "capability_id": "shop_room_vendor.transaction.purchase_item",
      "reason": "inventory/currency transaction runtime is not implemented"
    },
    {
      "capability_id": "forge_station.upgrade.apply_item_upgrade",
      "reason": "equipment upgrade runtime is not implemented"
    }
  ]
}
```

## 8. 20 个案例映射策略

20 个案例不要求全部成功，但每个都必须有明确映射结果。

流程：

```text
EAB selection
  → BehaviorSpecCompiler
  → RuntimeSupportChecker
  → supported?
      yes: 生成 framework + BehaviorSpec + TS 输出
      no: 写 unsupported report，workflow fail
```

每个案例输出一份映射表：

```text
behavior_id
required_capability_ids
capability_kind
action_kind
runtime handler
required runtime module
support status
unsupported reason
```

示例：冰冻控制房应支持：

```text
freeze_trap.sensor.detect_player_overlap → TriggerRouter.bindOverlapEnter
freeze_trap.effect.apply_freeze_to_player → StateBlackboard.write_state
freeze_vfx.emit.show_freeze → VfxRuntime.setVisible
side_camera.camera.apply_impulse → CameraRuntime.impulse
player.movement.block_while_effect_active → MovementRuntime.gateByState
```

示例：Boss 房可能部分不支持：

```text
concierge_boss.phase.switch_at_health_threshold → unsupported: boss phase runtime missing
concierge_boss.attack_pattern.ground_slam → unsupported: boss attack pattern runtime missing
```

示例：商店/锻造房可能不支持：

```text
shop_room_vendor.transaction.purchase_item → unsupported: inventory/currency runtime missing
forge_station.upgrade.apply_item_upgrade → unsupported: equipment upgrade runtime missing
```

## 9. 验收标准

设计落地后必须满足：

- 三库中无裸泛化 `*.state` / `*.interaction`。
- 三库中无 `*.state.initialize_state` / `*.state.update_state` / `*.interaction.accept_interaction` / `*.interaction.resolve_interaction`。
- `status` 不作为 Entity，不作为 runtime feature。
- 每个 selected capability 都能查到 support matrix 项。
- Unsupported capability 触发 hard fail。
- CodeGenerator 不再把 unsupported behavior 套进已有冰冻陷阱模板。
- 20 个案例全部重新生成，并给出 supported / unsupported 总表。
- Supported 案例必须 `validate-output pass`。
- Unsupported 案例必须有明确原因，不产生伪实现 TS。

## 10. 当前推荐落地口径

不引入完整 EventBus，不做 ECS。

采用：

```text
UE 原生事件
  + AutoUE TriggerRouter
  + StateBlackboard
  + ActionDispatcher
  + SupportMatrix
  + BehaviorSpec
```

这是一层最小行为驱动翻译框架，解决生成系统的确定性和防伪问题，同时最大限度复用 UE 原生生命周期和事件机制。
