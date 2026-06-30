SCHEMA: StaticEvaluationPlanBuilder

Create evaluation instructions from generated workflow artifacts. This is a validation plan, not runtime proof.

Rules:
- Output JSON only.
- Use runtime_features from PuerTSRuntimeMappingCompiler.
- If enemy_encounter is disabled, do not expect EnemySpawned, AliveEnemyRegistered, EnemyDied, or EncounterCompleted.
- For trap/status/VFX gameplay, verify HarnessReady, MoveInput, IceTrapTriggered, FrozenStatusApplied, AUTOUE_GENERATED_PLAYER_FROZEN, FreezeVFXVisible, CameraShakeTriggered, and IceTrapRearmed when applicable.
- This is not a PIE gameplay test; do not claim UE Editor launch, PIE launch, player input injection, or real runtime pass/fail.
