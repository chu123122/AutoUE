# AutoUE 单节点调用使用说明

本文说明当前仓库里 `autoue.py node` 的真实能力边界、输入输出约定和常用命令。

## 结论

当前支持单节点调用，入口是：

```powershell
python autoue.py node run --node <NodeName> --input-bundle <prev-bundle> --output-bundle <next-bundle> [--llm-profile scripted_smoke]
python autoue.py node validate --node <NodeName> --bundle <bundle>
```

单节点调用不是裸 JSON 调用。它依赖 `RunBundle`：

- 输入来自 bundle 的 `ports/*`。
- 输出写回 bundle 的 `ports/*` 和 `llm_outputs/<NodeName>.txt`。
- 模板类节点还会在 bundle 目录下渲染声明的 artifact，例如 `TypeScript/**/*.ts`。
- `node run` 会先把 `--input-bundle` 复制成 `--output-bundle`，再只执行指定节点。

## 最小可用示例

先准备一个已有上游 bundle。最常见来源是完整 workflow 跑完后自动生成的 checkpoint：

```text
<demo-output>/bundles/01-SceneAndGameplaySplitter
<demo-output>/bundles/02-EntityAbilityBehaviorPlanner
...
<demo-output>/bundles/09-TypeScriptRuntimeTemplatePlanner
```

例如，重新执行 `TypeScriptRuntimeTemplatePlanner`：

```powershell
python autoue.py node run `
  --node TypeScriptRuntimeTemplatePlanner `
  --input-bundle test_tmp\capability_full_workflow_16_output\demo_1\bundles\08-TypeScriptInteractiveTemplatePlanner `
  --output-bundle test_tmp\single_node_probe\09-TypeScriptRuntimeTemplatePlanner `
  --llm-profile scripted_smoke
```

成功时会输出类似：

```json
{
  "result": "pass",
  "bundle": "...\\test_tmp\\single_node_probe\\09-TypeScriptRuntimeTemplatePlanner",
  "node": "TypeScriptRuntimeTemplatePlanner"
}
```

并在输出 bundle 下生成：

```text
manifest.json
ports/typescript_codegen.json
llm_outputs/TypeScriptRuntimeTemplatePlanner.txt
TypeScript/content/generated/*.ts
TypeScript/AutoUEGeneratedCharacterAdapter.ts
TypeScript/AutoUEGeneratedGameModeAdapter.ts
trace/node_runs.json
```

## 单节点校验

校验节点输出和声明 artifact：

```powershell
python autoue.py node validate `
  --node TypeScriptRuntimeTemplatePlanner `
  --bundle test_tmp\single_node_probe\09-TypeScriptRuntimeTemplatePlanner
```

注意：如果只拿 checkpoint 里的 JSON 输出去校验，但对应 TypeScript artifact 没有落在该 bundle 目录下，校验会失败，错误类似：

```text
TypeScriptRuntimeTemplatePlanner typescript artifact missing file: TypeScript/content/generated/AutoUEBehaviorSpec.generated.ts
```

这种情况不是“单节点不能跑”，而是该 bundle 不完整；用 `node run` 重新跑一次会把声明的模板 artifact 渲染出来。

## 节点输入输出端口

当前 `config/workflows/puerts_ts.json` 里的端口如下：

| 节点 | 输入 ports | 输出 port |
|---|---|---|
| SceneAndGameplaySplitter | `user_prompt` | `scene_gameplay_split` |
| EntityAbilityBehaviorPlanner | `user_prompt`, `scene_gameplay_split` | `entity_behavior` |
| ThinGameplayFlowPlanner | `user_prompt`, `entity_behavior` | `thin_flow` |
| EncounterSpecPlanner | `entity_behavior`, `thin_flow`, `scene_spawn_manifest` | `encounter_spec` |
| UEApiMCPFeasibilitySearcher | `thin_flow` | `ue_api_feasibility` |
| PuerTSRuntimeMappingCompiler | `entity_behavior`, `thin_flow`, `ue_api_feasibility` | `runtime_mapping` |
| TypeScriptImplementationSlotProjector | `entity_behavior`, `runtime_mapping` | `ts_analyzer` |
| TypeScriptInteractiveTemplatePlanner | `entity_behavior`, `runtime_mapping`, `ts_analyzer` | `interactive_ts_plan` |
| TypeScriptRuntimeTemplatePlanner | `entity_behavior`, `runtime_mapping`, `ts_analyzer`, `interactive_ts_plan` | `typescript_codegen` |
| StaticEvaluationPlanBuilder | `scene_gameplay_split`, `entity_behavior`, `thin_flow`, `encounter_spec`, `ue_api_feasibility`, `runtime_mapping`, `ts_analyzer`, `interactive_ts_plan`, `typescript_codegen` | `evaluation_instructions` |

执行某个节点前，输入 bundle 必须已经包含该节点需要的所有输入 port。

例如：

- 跑 `ThinGameplayFlowPlanner`，输入 bundle 至少要有 `user_prompt` 和 `entity_behavior`。
- 跑 `TypeScriptRuntimeTemplatePlanner`，输入 bundle 至少要有 `entity_behavior`、`runtime_mapping`、`ts_analyzer`、`interactive_ts_plan`。
- 跑 `StaticEvaluationPlanBuilder`，输入 bundle 必须已经走到 `TypeScriptRuntimeTemplatePlanner` 之后。

## 常见失败

### 1. 缺输入 port

错误形式：

```text
<NodeName> missing input ports: [...]
```

含义：输入 bundle 太早，缺少上游节点产物。换成更晚的 checkpoint，或先运行上游节点。

### 2. artifact 缺失

错误形式：

```text
typescript artifact missing file: ...
```

含义：JSON 声明了 TypeScript artifact，但文件没有在 bundle 目录下。通常需要用 `node run` 重新执行模板节点，而不是只拷贝 `llm_outputs`。

### 3. `scripted_smoke` 不是通用 20 案例模型

`--llm-profile scripted_smoke` 是本地确定性冒烟模型，目前固定输出 freeze trap 链路。它适合验证单节点机制，不代表任意 prompt 的真实 20 案例全流程。

## 适用边界

单节点调用适合：

- 重跑某个失败节点。
- 验证某个节点 validator。
- 检查模板节点是否实际落盘 artifact。
- 从某个 checkpoint 继续局部调试。

单节点调用不自动解决：

- 20 个案例逐一端到端批量执行。
- 不支持能力的 runtime 补齐。
- PIE/UE Editor 运行验证。
- 选中行为被静默丢弃的 gate 问题。

