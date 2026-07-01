# 敌人 PIE 方案 B：fixture bundle → 当前模板重渲染 → AIDev/PIE 一键验证

解决"改 `templates/typescript/enemy_*.ts.tmpl` 后，PIE 里马上看到刚改逻辑"的迭代问题。方案 B 是一条**独立的确定性热路径**：不经过 LLM、不跑节点 1-5，直接把固定敌人 fixture 的编译结果喂给确定性 codegen，只验证 **当前模板、生成装配、部署、tsc、PIE runtime** 这一段。它不依赖真实主链路先修好——两者共用节点 6-10 与 stage/PIE，但入口互不阻塞、可并行推进。

---

## 一、命令形态

新增一个预制脚本 `tools/regen_enemy_pie.py`：

```powershell
python tools/regen_enemy_pie.py --case zombie --pie
python tools/regen_enemy_pie.py --case archer --pie
python tools/regen_enemy_pie.py --case kamikaze --pie
python tools/regen_enemy_pie.py --case shield --pie
python tools/regen_enemy_pie.py --case all --pie
```

`--case` 映射到现有 fixture：

| case | fixture | 重点验证 |
|---|---|---|
| `zombie` | `tests/fixtures/dead_cells_enemy_runtime_cases/01-zombie_melee` | `melee_hitbox` 前摇、active 命中、hit=0/1 |
| `archer` | `tests/fixtures/dead_cells_enemy_runtime_cases/02-archer_projectile` | `projectile_spawn` 发射、方向/速度、表现钩子 |
| `kamikaze` | `tests/fixtures/dead_cells_enemy_runtime_cases/03-kamikaze_self_destruct` | 自爆前摇、范围伤害、自毁 |
| `shield` | `tests/fixtures/dead_cells_enemy_runtime_cases/04-shield_bearer_block` | `directional_block`、格挡减伤/免伤、反击 |

---

## 二、脚本阶段

方案 B 直接复用 `tools/generate_dead_cells_enemy_runtime_cases.py` 的确定性逻辑，不重造：

1. 选 case → 复用该脚本的 `build_candidate_set` → `canonicalize_selection` → `compile_and_check` 得到 `behavior_spec` / `support_check`（或直接读 fixture 里已存的 `behavior_spec.json` / `support_check.json`）。`support.status` 必须为 `supported`。
2. encounter 由 `codegen_for` 内部合成（`room_01_initial_guard`，`spawn_group=room_01_guard`，非空）——**不从 fixture 读**，fixture 里没有 `encounter_spec.json`。多敌人用 `max_alive=count`。
3. 调 `build_codegen_output` 得到 `template_inputs` 计划，**紧接着调 `write_files_from_output(state, "TypeScriptRuntimeTemplatePlanner", output)` 把当前 `templates/typescript/*.ts.tmpl` 渲染进 output demo 的 `TypeScript/`**。这一步不能省：`build_codegen_output` 只产计划、不落 `.ts`；漏了它 stage 的就是旧/空文件，"看到刚改逻辑"直接失效。
4. 静态检查生成物：必含 `AutoUEEnemyPresentationRuntime.ts`；archer/shield 需要投射物时含 `AutoUEEnemyProjectileRuntime.ts`；`typescript_codegen.json` 的 `required_runtime_modules` 含本 case 所需模块。
5. 走 `stage_generated_ts_to_aidev.py`：清旧 `AutoUEGenerated*.ts` + 复制新 TS + 运行 AIDev `tsc`。
6. PIE 前置检查（硬前提）：确认 AIDev 地图里有 tag=`AUTOUE_ENEMY_SPAWN_POINT` 的 spawn 点 actor，且其 `spawn_group` 覆盖 `room_01_guard`；缺失直接 fail-loud，不进 PIE。否则 `spawn_point_registry` 找不到点位、`enemy_count=0`，看起来"没刷怪"实为场景缺点。
7. 启 PIE：复用 `tools/unreal/run_autoue_pie_validation.py`。
8. 对本次日志切片做强断言（见三）。

因为走确定性 codegen、不经 `EncounterSpecPlanner`，**生成期不需要 `scene-spawn-manifest.json`**；manifest 只有真实主链路（`autoue.py run`）才需要。

---

## 三、当前日志切片与断言

为避免旧日志假通过，脚本启动 PIE 前记录 AIDev 日志文件大小/时间戳，PIE 结束后只分析新增片段。

通用断言：

```text
EnemySpawnedByEncounter
EnemyDetectPlayer in_range=1
EnemyMoved
EnemyAttackTelegraph
EnemyAttackActive
EnemyAttackResolved
EncounterCompleted=1
```

case-specific 断言：

```text
zombie   -> EnemyAttackResolved type=melee_hitbox
archer   -> EnemyAttackResolved type=projectile_spawn
kamikaze -> EnemyAttackResolved type=self_destruct + EnemyDied
shield   -> EnemyDirectionalBlock 或 EnemyBlocked
```

表现层已接可见原语（`flashActorColor` / `spawnTempShape` / `cameraImpulse` 落地），因此除日志外，PIE 里可**肉眼**确认前摇变红球、命中黄球、自爆橙球、被击白闪——日志 gate 与视觉验证可同时进行。`run_autoue_pie_validation.py` 现有 pass 条件只证明有敌人生成，证明不了相位机/表现；因此 `regen_enemy_pie.py` 必须把相位日志链作为第二道 gate。

---

## 四、为什么它适合模板热迭代

- 节点 6-10 / codegen / template writer 是确定性路径，每次跑都读当前模板。
- `stage_generated_ts_to_aidev.py` 会清理旧 `AutoUEGenerated*.ts` 和 `content/generated/AutoUE*.ts`，降低旧 TS 残留风险。
- `run_tsc=true` 后会覆盖 JS 编译结果；若后续确认 PuerTS 另有缓存目录，再把缓存清理纳入脚本。
- 敌人差异固定在 fixture 的 entity/capability/behavior/spec 参数里，适合对比 zombie/archer/kamikaze/shield 四类行为。
- 表现层已接可见原语，改模板后能在 PIE 肉眼看差异，不用只靠读日志。

---

## 五、不能解决什么

方案 B 不验证 LLM 节点 1-5 的选择质量。它证明"当前模板 + 当前运行链路能让指定敌人在 PIE 打起来"，但不证明"任意自然语言 prompt 都会稳定选中正确敌人"。后者是真实主链路的职责（见主链路补全计划），与方案 B 相互独立、可并行推进。
