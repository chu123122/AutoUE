from __future__ import annotations

import argparse
import os
from typing import Any

SPAWN_POINT_ASSET = "/Game/AutoUE/Encounter/BP_EnemySpawnPoint"
ENEMY_ASSET = "/Game/AutoUE/Enemies/BP_AutoUECombatEnemy"
ENEMY_CLASS_PATH = "/Game/AutoUE/Enemies/BP_AutoUECombatEnemy.BP_AutoUECombatEnemy_C"
LIFE_BAR_ASSET = "/Game/AutoUE/UI/WBP_AutoUECombatLifeBar"
LIFE_BAR_CLASS_PATH = "/Game/AutoUE/UI/WBP_AutoUECombatLifeBar.WBP_AutoUECombatLifeBar_C"
DEFAULT_SPAWN_GROUP = "room_01_guard"
SPAWN_POINT_TAGS = [
    "AUTOUE_ENEMY_SPAWN_POINT",
    "EnemySpawnPoint",
    "BP_EnemySpawnPoint",
    f"SpawnGroup={DEFAULT_SPAWN_GROUP}",
    "AllowedEnemyTags=ground;melee",
    "CanInitialSpawn",
    "CanRuntimeSpawn",
    "AUTOUE_CAN_INITIAL_SPAWN",
    "AUTOUE_CAN_RUNTIME_SPAWN",
]


def _name_list(unreal: Any, values: list[str]) -> list[Any]:
    return [unreal.Name(v) for v in values]


def _load_class(unreal: Any, path: str) -> Any:
    cls = unreal.load_class(None, path)
    if not cls:
        raise RuntimeError(f"required class not found: {path}")
    return cls


def _load_asset(unreal: Any, path: str) -> Any:
    try:
        return unreal.EditorAssetLibrary.load_asset(path)
    except Exception:
        return None


def _set_parent(factory: Any, parent_class: Any) -> None:
    for prop in ("ParentClass", "parent_class"):
        try:
            factory.set_editor_property(prop, parent_class)
            return
        except Exception:
            pass
    raise RuntimeError("BlueprintFactory does not expose ParentClass/parent_class")


def _class_candidate(value: Any) -> Any:
    if not value:
        return None
    # UE Python may expose generated_class as a method-like closure instead of
    # a property on some versions; call it only when it is a zero-arg getter.
    if callable(value):
        try:
            value = value()
        except TypeError:
            return None
        except Exception:
            return None
    if hasattr(value, "get_default_object") or hasattr(value, "get_super_class"):
        return value
    return None


def _generated_class(bp: Any) -> Any:
    for prop in ("GeneratedClass", "generated_class"):
        try:
            value = _class_candidate(bp.get_editor_property(prop))
            if value:
                return value
        except Exception:
            pass
    for attr in ("generated_class", "GeneratedClass"):
        try:
            value = _class_candidate(getattr(bp, attr))
            if value:
                return value
        except Exception:
            pass
    raise RuntimeError(f"blueprint has no generated class: {bp}")


def _compile_blueprint(unreal: Any, bp: Any) -> None:
    for owner, fn in ((getattr(unreal, "KismetEditorUtilities", None), "compile_blueprint"), (getattr(unreal, "BlueprintEditorLibrary", None), "compile_blueprint")):
        if owner and hasattr(owner, fn):
            try:
                getattr(owner, fn)(bp)
                return
            except Exception:
                pass


def _create_or_load_blueprint(unreal: Any, asset_path: str, parent_class: Any) -> Any:
    existing = _load_asset(unreal, asset_path)
    if existing:
        return existing
    package_path, asset_name = asset_path.rsplit("/", 1)
    unreal.EditorAssetLibrary.make_directory(package_path)
    factory = unreal.BlueprintFactory()
    _set_parent(factory, parent_class)
    created = unreal.AssetToolsHelpers.get_asset_tools().create_asset(asset_name, package_path, None, factory)
    if not created:
        raise RuntimeError(f"failed to create blueprint asset: {asset_path}")
    _compile_blueprint(unreal, created)
    unreal.EditorAssetLibrary.save_loaded_asset(created)
    return created


def _create_or_load_widget_blueprint(unreal: Any, asset_path: str, parent_class: Any) -> Any:
    existing = _load_asset(unreal, asset_path)
    if existing:
        return existing
    package_path, asset_name = asset_path.rsplit("/", 1)
    unreal.EditorAssetLibrary.make_directory(package_path)
    factory = None
    for factory_name in ("WidgetBlueprintFactory", "BlueprintFactory"):
        try:
            factory = getattr(unreal, factory_name)()
            _set_parent(factory, parent_class)
            break
        except Exception:
            factory = None
    if not factory:
        raise RuntimeError("failed to create WidgetBlueprintFactory/BlueprintFactory for CombatLifeBar")
    created = unreal.AssetToolsHelpers.get_asset_tools().create_asset(asset_name, package_path, None, factory)
    if not created:
        raise RuntimeError(f"failed to create combat life bar widget blueprint: {asset_path}")
    _compile_blueprint(unreal, created)
    unreal.EditorAssetLibrary.save_loaded_asset(created)
    return created


def _set_tags(obj: Any, unreal: Any, tags: list[str]) -> None:
    current: list[str] = []
    try:
        current = [str(x) for x in obj.get_editor_property("tags")]
    except Exception:
        try:
            current = [str(x) for x in obj.Tags]
        except Exception:
            current = []
    merged = []
    for tag in current + tags:
        if tag and tag not in merged:
            merged.append(tag)
    names = _name_list(unreal, merged)
    try:
        obj.set_editor_property("tags", names)
        return
    except Exception:
        pass
    try:
        obj.Tags = names
    except Exception as exc:
        raise RuntimeError(f"failed to set tags on {obj}: {exc}") from exc


def _set_optional_property(obj: Any, names: list[str], value: Any) -> bool:
    for name in names:
        try:
            obj.set_editor_property(name, value)
            return True
        except Exception:
            pass
    for name in names:
        try:
            setattr(obj, name, value)
            return True
        except Exception:
            pass
    return False


def _configure_spawn_point_blueprint(unreal: Any, bp: Any) -> None:
    cdo = unreal.get_default_object(_generated_class(bp))
    _set_tags(cdo, unreal, SPAWN_POINT_TAGS)
    _set_optional_property(cdo, ["SpawnGroup", "spawn_group", "spawnGroup"], DEFAULT_SPAWN_GROUP)
    _set_optional_property(cdo, ["AllowedEnemyTags", "allowed_enemy_tags"], ["ground", "melee"])
    _set_optional_property(cdo, ["CanInitialSpawn", "can_initial_spawn"], True)
    _set_optional_property(cdo, ["CanRuntimeSpawn", "can_runtime_spawn"], True)
    _compile_blueprint(unreal, bp)
    unreal.EditorAssetLibrary.save_loaded_asset(bp)


def _configure_life_bar_blueprint(unreal: Any, bp: Any) -> None:
    _compile_blueprint(unreal, bp)
    unreal.EditorAssetLibrary.save_loaded_asset(bp)


def _configure_enemy_blueprint(unreal: Any, bp: Any, life_bar_bp: Any) -> None:
    cdo = unreal.get_default_object(_generated_class(bp))
    _set_tags(cdo, unreal, ["AUTOUE_COMBAT_ENEMY", "AUTOUE_GENERATED_ENEMY_ARCHETYPE"])
    if not _set_optional_property(cdo, ["MaxHP", "max_hp"], 2.0):
        raise RuntimeError("BP_AutoUECombatEnemy: failed to set MaxHP")
    _set_optional_property(cdo, ["CurrentHP", "current_hp"], 2.0)

    mesh_asset = unreal.EditorAssetLibrary.load_asset("/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple")
    if not mesh_asset:
        raise RuntimeError("required visible enemy mesh not found: /Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple")
    mesh_comp = None
    for prop in ("Mesh", "mesh"):
        try:
            mesh_comp = cdo.get_editor_property(prop)
            break
        except Exception:
            pass
    if not mesh_comp:
        try:
            mesh_comp = cdo.Mesh
        except Exception:
            mesh_comp = None
    if not mesh_comp:
        raise RuntimeError("BP_AutoUECombatEnemy: missing inherited Mesh component")
    configured_mesh = False
    for method in ("set_skeletal_mesh_asset", "set_skeletal_mesh"):
        try:
            getattr(mesh_comp, method)(mesh_asset)
            configured_mesh = True
            break
        except Exception:
            pass
    if not configured_mesh:
        for prop in ("SkeletalMeshAsset", "skeletal_mesh_asset", "SkeletalMesh", "skeletal_mesh"):
            try:
                mesh_comp.set_editor_property(prop, mesh_asset)
                configured_mesh = True
                break
            except Exception:
                pass
    if not configured_mesh:
        raise RuntimeError("BP_AutoUECombatEnemy: failed to configure inherited Mesh component")
    try:
        mesh_comp.set_editor_property("relative_location", unreal.Vector(0, 0, -90))
    except Exception:
        pass
    try:
        mesh_comp.set_editor_property("relative_rotation", unreal.Rotator(0, -90, 0))
    except Exception:
        pass

    capsule = None
    for prop in ("CapsuleComponent", "capsule_component"):
        try:
            capsule = cdo.get_editor_property(prop)
            break
        except Exception:
            pass
    if capsule:
        try:
            capsule.set_capsule_size(42.0, 96.0, True)
        except Exception:
            pass

    life_bar_comp = None
    for prop in ("LifeBar", "life_bar"):
        try:
            life_bar_comp = cdo.get_editor_property(prop)
            break
        except Exception:
            pass
        try:
            life_bar_comp = getattr(cdo, prop)
            break
        except Exception:
            pass
    if not life_bar_comp:
        raise RuntimeError("BP_AutoUECombatEnemy: missing inherited LifeBar WidgetComponent")
    life_bar_class = _generated_class(life_bar_bp)
    configured_life_bar = False
    for method in ("set_widget_class", "SetWidgetClass"):
        try:
            getattr(life_bar_comp, method)(life_bar_class)
            configured_life_bar = True
            break
        except Exception:
            pass
    if not configured_life_bar:
        for prop in ("WidgetClass", "widget_class"):
            try:
                life_bar_comp.set_editor_property(prop, life_bar_class)
                configured_life_bar = True
                break
            except Exception:
                pass
    if not configured_life_bar:
        raise RuntimeError("BP_AutoUECombatEnemy: failed to configure LifeBar WidgetClass")
    try:
        life_bar_comp.set_editor_property("relative_location", unreal.Vector(0, 0, 130))
    except Exception:
        pass
    try:
        life_bar_comp.set_editor_property("draw_size", unreal.Vector2D(160, 24))
    except Exception:
        pass
    _compile_blueprint(unreal, bp)
    unreal.EditorAssetLibrary.save_loaded_asset(bp)


def _load_map(unreal: Any, map_name: str | None) -> str:
    if map_name:
        unreal.EditorLoadingAndSavingUtils.load_map(map_name)
        return map_name
    world = unreal.EditorLevelLibrary.get_editor_world()
    try:
        return world.get_name()
    except Exception:
        return "<current>"


def _actor_has_spawn_group(actor: Any) -> bool:
    tags: list[str] = []
    try:
        tags = [str(x) for x in actor.get_editor_property("tags")]
    except Exception:
        try:
            tags = [str(x) for x in actor.Tags]
        except Exception:
            tags = []
    return "AUTOUE_ENEMY_SPAWN_POINT" in tags and f"SpawnGroup={DEFAULT_SPAWN_GROUP}" in tags


def _place_spawn_point(unreal: Any, bp: Any) -> Any:
    bp_class = _generated_class(bp)
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if _actor_has_spawn_group(actor):
            _set_tags(actor, unreal, SPAWN_POINT_TAGS)
            _set_optional_property(actor, ["SpawnGroup", "spawn_group", "spawnGroup"], DEFAULT_SPAWN_GROUP)
            _set_optional_property(actor, ["AllowedEnemyTags", "allowed_enemy_tags"], ["ground", "melee"])
            _set_optional_property(actor, ["CanInitialSpawn", "can_initial_spawn"], True)
            _set_optional_property(actor, ["CanRuntimeSpawn", "can_runtime_spawn"], True)
            return actor
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(bp_class, unreal.Vector(360, 0, 120), unreal.Rotator(0, 0, 0))
    if not actor:
        raise RuntimeError("failed to place BP_EnemySpawnPoint instance in the current map")
    try:
        actor.set_actor_label("AUTOUE_room_01_guard_SpawnPoint")
    except Exception:
        pass
    _set_tags(actor, unreal, SPAWN_POINT_TAGS)
    _set_optional_property(actor, ["SpawnGroup", "spawn_group", "spawnGroup"], DEFAULT_SPAWN_GROUP)
    _set_optional_property(actor, ["AllowedEnemyTags", "allowed_enemy_tags"], ["ground", "melee"])
    _set_optional_property(actor, ["CanInitialSpawn", "can_initial_spawn"], True)
    _set_optional_property(actor, ["CanRuntimeSpawn", "can_runtime_spawn"], True)
    return actor


def prepare_assets(map_name: str | None = None) -> dict[str, Any]:
    import unreal  # type: ignore

    level = _load_map(unreal, map_name)
    actor_class = _load_class(unreal, "/Script/Engine.Actor")
    combat_enemy_class = _load_class(unreal, "/Script/AIDev.CombatEnemy")
    combat_life_bar_class = _load_class(unreal, "/Script/AIDev.CombatLifeBar")

    spawn_bp = _create_or_load_blueprint(unreal, SPAWN_POINT_ASSET, actor_class)
    life_bar_bp = _create_or_load_widget_blueprint(unreal, LIFE_BAR_ASSET, combat_life_bar_class)
    enemy_bp = _create_or_load_blueprint(unreal, ENEMY_ASSET, combat_enemy_class)
    # If the enemy blueprint cannot compile/generate from ACombatEnemy, fail here;
    # do not downgrade to a mesh placeholder.
    enemy_generated = _generated_class(enemy_bp)
    if not enemy_generated:
        raise RuntimeError("BP_AutoUECombatEnemy has no generated class")

    _configure_spawn_point_blueprint(unreal, spawn_bp)
    _configure_life_bar_blueprint(unreal, life_bar_bp)
    _configure_enemy_blueprint(unreal, enemy_bp, life_bar_bp)
    placed = _place_spawn_point(unreal, spawn_bp)

    save_ok = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    if save_ok is False:
        raise RuntimeError("failed to save dirty map/content packages after placing BP_EnemySpawnPoint")
    return {
        "level": level,
        "spawn_point_blueprint": SPAWN_POINT_ASSET,
        "enemy_blueprint": ENEMY_ASSET,
        "enemy_class_path": ENEMY_CLASS_PATH,
        "life_bar_blueprint": LIFE_BAR_ASSET,
        "life_bar_class_path": LIFE_BAR_CLASS_PATH,
        "placed_spawn_group": DEFAULT_SPAWN_GROUP,
        "placed_spawn_point": str(placed.get_name() if hasattr(placed, "get_name") else placed),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare AutoUE encounter assets in the currently opened UE project.")
    parser.add_argument("--map", dest="map_name", help="Optional map package path to load before asset placement.")
    args = parser.parse_args(argv)
    result = prepare_assets(args.map_name or os.getenv("AUTOUE_ENCOUNTER_MAP"))
    print("[SUCCESS] AutoUE encounter assets prepared")
    for key, value in result.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
