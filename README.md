# AutoUE PuerTS Workflow

This checkout is the cleaned AutoUE adaptation for the PuerTS / TypeScript workflow.

The old AutoUE C++ / PCG / model-retrieval path has been removed from the active codebase. The single supported workflow is:

```text
SceneAndGameplaySplitter
→ EntityAbilityBehaviorPlanner
→ ThinGameplayFlowPlanner
→ EncounterSpecPlanner
→ UEApiMCPFeasibilitySearcher
→ PuerTSRuntimeMappingPlanner
→ TypeScriptScriptAnalyzer
→ TypeScriptInteractiveObjectGenerator
→ TypeScriptCodeGenerator
→ EvaluateInstructionGenerator
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Machine-specific settings belong in `config/local.json` or `.env`; neither should be committed.

## Configuration

- Runtime defaults: `config/local.example.json`
- LLM profiles: `config/llm-profiles.example.json`
- Active workflow: `config/workflows/puerts_ts.json`
- TypeScript templates: `templates/typescript/`

`UEApiMCPFeasibilitySearcher` reads MCP settings from `config/local.json`, environment overrides, or `[mcp_servers.ue-api-search]` in the Codex config.

## Validate wiring

```bash
python autogenerate_qwen.py --dry-run-config
python tools/validate_config_contract.py --workflow config/workflows/puerts_ts.json --phase phase2
pytest -q
```

## Run

```bash
python autogenerate_qwen.py --workflow config/workflows/puerts_ts.json
```

Generated outputs are written under `data/output*` and are ignored by git.
