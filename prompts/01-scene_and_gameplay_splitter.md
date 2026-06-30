SCHEMA: SceneAndGameplaySplitter

Split the user's request into scene_description and gameplay_description.

This node must make the request concrete enough for downstream entity / capability / behavior selection.
Do not merely restate genre labels such as "类死亡细胞", "roguelike", "横版动作", or "soulslike".
If the user gives a genre shorthand, expand the genre into concrete, representative scene and gameplay facts implied by that shorthand.

Required JSON shape:
{
  "scene_description": "Concrete environment, visible objects, spatial layout, actors, interactables, HUD/VFX objects, mood. Empty string only if truly absent.",
  "gameplay_description": "Player actions, enemy/hazard/reward interactions, mechanics, objectives, progression and feedback. Empty string only if truly absent."
}

Rules:
- Output JSON only. The first character must be { and the last character must be }.
- Do not invent implementation details, file paths, assets, APIs, code, plugins, or server dependencies.
- Do not output vague labels only. Each field should normally be 2-5 concrete clauses or sentences.
- For genre shorthand, infer common gameplay primitives from the genre, but keep them as generic gameplay facts rather than exact copyrighted level names.
- Separate "what is visible in the room/world" into scene_description and "what the player does / what systems react" into gameplay_description.
- Do not include implementation files, asset retrieval steps, procedural asset graphs, or server/plugin dependencies.

Example:
Input: "类死亡细胞"
Good:
{
  "scene_description": "A side-scrolling dungeon combat room with platforms, an exit door, several ground/ranged enemies, floor traps, pickups, HUD indicators, and hit/VFX feedback objects.",
  "gameplay_description": "The player moves and attacks through the room, enemies detect and attack the player, traps trigger on overlap, defeated enemies or pickups grant rewards, HUD values update, VFX communicate hits/status/rewards, and the exit unlocks after the encounter objective is complete."
}
Bad:
{
  "scene_description": "类死亡细胞风格的横版动作场景",
  "gameplay_description": "类死亡细胞风格的动作玩法"
}
