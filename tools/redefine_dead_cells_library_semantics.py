from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.content_library import load_dead_cells_library, validate_library_self_consistency

DOC = ROOT / "tests" / "fixtures" / "dead_cells_libraries"

CAPABILITY_KIND_ZH = {
    "apply_effect": "施加效果",
    "camera_feedback": "镜头反馈",
    "chain_lightning": "连锁闪电",
    "chest_reward": "宝箱奖励",
    "combat": "战斗",
    "curse_counter": "诅咒计数",
    "enemy_combat": "敌人战斗",
    "enemy_attack": "敌人攻击",
    "enemy_death": "敌人死亡",
    "enemy_defense": "敌人格挡",
    "enemy_health": "敌人生命值",
    "enemy_movement": "敌人移动",
    "enemy_pursuit": "敌人追击",
    "enemy_sensor": "敌人感知",
    "enemy_spawn": "敌人生成",
    "encounter": "遭遇战",
    "gate_lock": "门锁判定",
    "generic_capability": "通用能力",
    "hazard_arming": "危险机关预备",
    "hazard_resolution": "危险机关结算",
    "hud_binding": "界面绑定",
    "hud_feedback": "界面反馈",
    "level_transition": "关卡切换",
    "movement": "移动",
    "movement_gate": "移动门槛",
    "pickup_collection": "拾取收集",
    "platform_state": "平台状态",
    "reward_feedback": "奖励反馈",
    "sensor": "感应器",
    "sensor_overlap": "感应器重叠",
    "teleport_transition": "传送切换",
    "transaction": "交易",
    "upgrade": "升级",
    "vfx_binding": "特效绑定",
    "vfx_lifecycle": "特效生命周期",
    "weapon_effect": "武器效果",
}

ACTION_KIND_ZH = {
    "activate_transition": "激活切换",
    "add_curse_counter": "增加诅咒计数",
    "apply_bleed_on_hit": "命中施加流血",
    "apply_burn": "施加燃烧",
    "apply_damage": "施加伤害",
    "apply_effect": "施加效果",
    "apply_freeze": "施加冰冻",
    "apply_hazard_damage": "结算机关伤害",
    "apply_item_upgrade": "应用物品升级",
    "apply_poison_dot": "施加毒素持续伤害",
    "apply_shock_chain": "施加电击连锁",
    "arm_hazard": "预备危险机关",
    "block_by_state": "按状态阻挡",
    "camera_impulse": "镜头冲击",
    "chase_target": "追击目标",
    "collapse_when_touched": "接触后塌陷",
    "complete_when_all_dead": "全部死亡后完成",
    "detect_overlap": "检测重叠",
    "detect_player_by_distance": "按距离检测玩家",
    "directional_block": "方向格挡",
    "enemy_attack": "敌人攻击",
    "evaluate_unlock": "判定解锁",
    "flash_warning": "闪烁警示",
    "grant_reward": "授予奖励",
    "move_actor": "移动角色",
    "open_reward": "打开奖励",
    "purchase_item": "购买物品",
    "refresh_value": "刷新数值",
    "receive_damage": "接收伤害",
    "set_visible_while_state": "按状态显示",
    "self_destruct": "自爆",
    "spawn_particles": "生成粒子",
    "spawn_actor": "生成角色",
    "projectile_spawn": "生成投射物",
    "spawn_reward_visual": "生成奖励视觉反馈",
    "state_write": "写入状态",
    "tick_or_cleanup": "更新或清理",
}

TRIGGER_ZH = {
    "active hit frame overlaps target": "攻击有效帧与目标重叠",
    "actor approaches hazard zone": "角色靠近危险区域",
    "actor enters trigger bounds": "角色进入触发范围",
    "actor exits trigger bounds": "角色离开触发范围",
    "actor overlaps active hazard": "角色与已激活机关重叠",
    "active window ends": "激活窗口结束",
    "arming delay finishes": "预备延迟结束",
    "attack input": "收到攻击输入",
    "camera or viewport changes": "相机或视口发生变化",
    "collection is accepted": "拾取收集被接受",
    "completion condition changes": "完成条件发生变化",
    "condition becomes false or cooldown ends": "条件失效或冷却结束",
    "danger or threshold is reached": "进入危险状态或达到阈值",
    "danger state ends": "危险状态结束",
    "dodge input": "收到翻滚输入",
    "effect expires or owner dies": "效果到期或归属对象死亡",
    "effect has a tracked owner": "效果拥有可跟踪归属对象",
    "effect lifetime advances": "效果生命周期推进",
    "feedback begins": "反馈开始",
    "freeze trap applies frozen state": "冰冻陷阱施加冰冻状态",
    "frozen state changes": "冰冻状态发生变化",
    "gameplay event fires": "玩法事件触发",
    "handoff completes": "交接完成",
    "movement input": "收到移动输入",
    "player enters awareness range": "玩家进入感知范围",
    "player interacts while locked": "玩家在锁定状态下交互",
    "player interacts while unlocked": "玩家在解锁状态下交互",
    "player leaves trap rearm radius": "玩家离开陷阱重新预备半径",
    "player overlaps pickup": "玩家与拾取物重叠",
    "reward is granted": "奖励已授予",
    "target enters attack range": "目标进入攻击范围",
    "target is reachable": "目标可被追击到达",
    "tracked value changes": "被跟踪数值发生变化",
    "trigger condition becomes true": "触发条件成立",
    "valid cancel window": "进入有效取消窗口",
    "每帧检测玩家是否进入僵尸感知范围": "每帧检测玩家是否进入僵尸感知范围",
    "每帧检测玩家是否进入弓箭手感知范围": "每帧检测玩家是否进入弓箭手感知范围",
    "每帧检测玩家是否进入自爆蝙蝠感知范围": "每帧检测玩家是否进入自爆蝙蝠感知范围",
    "每帧检测玩家是否进入持盾兵感知范围": "每帧检测玩家是否进入持盾兵感知范围",
    "敌人死亡事件导致存活数量归零": "敌人死亡事件导致存活数量归零",
}

EXECUTION_ZH = {
    "accelerates, decelerates, and faces travel direction": "执行加速、减速并朝向移动方向",
    "adds stat, currency, cell, healing, or equipment value": "增加属性、货币、细胞、治疗或装备收益",
    "applies a short side-camera feedback impulse": "施加一次短促的侧视角镜头反馈冲击",
    "applies damage or status according to hazard type": "按机关类型施加伤害或状态",
    "applies the enemy attack result": "结算敌人攻击结果",
    "attaches the VFX to the player and toggles visibility while frozen": "把特效附着到玩家，并在冰冻期间切换可见性",
    "chains movement or another attack from recovery": "在收招阶段衔接移动或下一次攻击",
    "checks collection eligibility and run state": "检查拾取资格和本局状态",
    "cleans up current-room state": "清理当前房间状态",
    "clears pressure or occupancy state": "清除压力或占用状态",
    "executes the selected weapon strike against a target": "对目标执行所选武器打击",
    "fades warning visuals and restores normal color": "淡出警示视觉并恢复正常颜色",
    "follows the owner while the effect is active": "效果激活期间跟随归属对象",
    "hides or destroys collected pickup actor": "隐藏或销毁已收集的拾取物角色",
    "keeps the door closed and shows locked feedback": "保持门关闭并显示锁定反馈",
    "keeps the widget in readable screen position": "保持控件处于可读的屏幕位置",
    "marks the trap armed again after the player moves away": "玩家移开后将陷阱标记为可再次触发",
    "moves, jumps, flies, or teleports toward attack range": "通过移动、跳跃、飞行或传送接近攻击范围",
    "performs an invulnerable roll with recovery": "执行带收招阶段的无敌翻滚",
    "plays a visual flash or shake": "播放视觉闪烁或抖动",
    "records the triggering actor and pressure state": "记录触发角色和压力状态",
    "removes particles and detached components": "移除粒子和已分离组件",
    "returns hazard to cooldown or idle state": "让机关回到冷却或闲置状态",
    "reveals warning pose, light, or animation": "显示预警姿态、灯光或动画",
    "selects the player as target and turns toward them": "选择玩家为目标并转向玩家",
    "sends activation to connected door, trap, or reward": "向连接的门、机关或奖励发送激活信号",
    "sends reset or cooldown completion": "发送重置或冷却完成信号",
    "sets the locked or unlocked state": "设置锁定或解锁状态",
    "shows a visible windup before damage": "在造成伤害前显示可见前摇",
    "shows floating icon, sparkle, or number feedback": "显示漂浮图标、闪光或数字反馈",
    "spawns particles at the relevant actor or world position": "在相关角色或世界位置生成粒子",
    "starts transition, fade, or room completion": "开始切换、淡入淡出或房间完成流程",
    "switches the hazard to an active damage window": "把机关切换到有效伤害窗口",
    "updates alpha, scale, and simulation state": "更新透明度、缩放和模拟状态",
    "updates bars, icons, counters, or map tiles": "更新条形控件、图标、计数器或地图格",
}

RESULT_ZH = {
    "actor suffers hazard result": "角色承受机关结果",
    "collection is visible": "收集反馈可见",
    "combat remains responsive": "战斗保持响应性",
    "effect stays spatially coherent": "效果保持空间一致",
    "effect visibly progresses": "效果可见地推进",
    "enemy starts pursuing": "敌人开始追击",
    "enemy threatens the player": "敌人对玩家形成威胁",
    "event has visible feedback": "事件拥有可见反馈",
    "exit communicates availability": "出口清楚表达可用状态",
    "frozen state has visible feedback": "冰冻状态拥有可见反馈",
    "hazard becomes threatening": "机关进入威胁状态",
    "hazard can trigger again later": "机关之后可以再次触发",
    "HUD reflects current state": "界面反映当前状态",
    "HUD remains legible": "界面保持清晰可读",
    "HUD returns to baseline": "界面恢复基准状态",
    "linked object can react again": "连接对象可以再次响应",
    "linked object changes state": "连接对象改变状态",
    "next area can load": "下一区域可以加载",
    "pickup can transfer its reward": "拾取物可以转移奖励",
    "pickup cannot be collected twice": "拾取物不会被重复收集",
    "player avoids a hit window": "玩家避开命中窗口",
    "player can anticipate danger": "玩家可以预判危险",
    "player can react": "玩家可以反应",
    "player changes horizontal position": "玩家改变水平位置",
    "player or object is damaged": "玩家或对象受到伤害",
    "player progresses to next area": "玩家推进到下一区域",
    "player receives reward": "玩家获得奖励",
    "player remains in area": "玩家仍留在当前区域",
    "player sees urgent feedback": "玩家看到紧急反馈",
    "screen no longer shows stale effect": "屏幕不再显示过期效果",
    "target receives combat pressure": "目标承受战斗压力",
    "trap can trigger again later": "陷阱之后可以再次触发",
    "trap trigger is readable in camera feedback": "陷阱触发能通过镜头反馈被读懂",
    "trigger can reset": "触发器可以重置",
    "trigger is aware of activation": "触发器记录到激活信息",
}


def _zh(mapping: dict[str, str], value: str) -> str:
    if not value:
        return "未声明"
    return value if any("\u4e00" <= char <= "\u9fff" for char in value) else mapping.get(value, value)


TEXT_REPLACEMENTS = {
    "HUD": "界面",
    "Boss": "首领",
    "VFX": "特效",
    "target.effects.bleed_dot": "目标的流血持续效果",
    "player.effects.burn": "玩家的燃烧状态",
    "player.effects.frozen": "玩家的冰冻状态",
    "run.curse_count": "本局诅咒计数",
}
TEXT_REPLACEMENTS.update({
    "写入 目标": "写入目标",
    "写入 玩家": "写入玩家",
    "读取 本局": "读取本局",
    " 的 界面": "的界面",
    "计数 界面": "计数界面",
    "特效特效生命周期": "特效生命周期",
})


def _clean_zh_text(value: str | None, fallback: str = "暂无说明") -> str:
    text = value or fallback
    for before, after in TEXT_REPLACEMENTS.items():
        text = text.replace(before, after)
    while "。。" in text:
        text = text.replace("。。", "。")
    return text.strip()


def _clean_name(value: str | None, fallback: str) -> str:
    return _clean_zh_text(value, fallback).rstrip("。；，,.;")


def _clean_clause(value: str | None, fallback: str = "未声明") -> str:
    return _clean_zh_text(value, fallback).rstrip("。；，,.;")


def _item_description(name: str, summary: str | None) -> str:
    clean_summary = _clean_zh_text(summary)
    if clean_summary.rstrip("。") == name.rstrip("。"):
        return f"{name}。"
    return f"{name}。{clean_summary}"


def _capability_label(lib: dict, capability_id: str) -> str:
    cap = lib["capabilities"].get(capability_id, {})
    return f"`{capability_id}`（{_clean_name(cap.get('display_name_zh'), capability_id)}）"


def write_docs() -> None:
    lib = load_dead_cells_library()
    DOC.mkdir(parents=True, exist_ok=True)
    (DOC / "entities.zh.md").write_text(
        "# 死亡细胞实体库（不含音效）\n\n"
        "实体是可绑定、可显示、可生成或可引用的对象；运行时状态进入状态黑板，不在实体库里伪装成玩法对象。\n\n"
        + "\n".join(
            f"- `{entity_id}`："
            f"{_item_description(_clean_name(entity.get('display_name_zh'), entity_id), entity.get('summary_zh') or entity.get('summary'))}"
            for entity_id, entity in sorted(lib["entities"].items())
        ) + "\n",
        encoding="utf-8",
    )
    (DOC / "abilities.zh.md").write_text(
        "# 死亡细胞能力库（不含音效）\n\n"
        "能力表示运行时可以调用的具体玩法能力；禁止把泛化状态或泛化交互伪装成能力。每项都标明能力类型、动作类型和中文用途。\n\n"
        + "\n".join(
            f"- `{capability_id}`："
            f"{_item_description(_clean_name(cap.get('display_name_zh'), capability_id), cap.get('summary_zh') or cap.get('summary'))}"
            f"能力类型：{_zh(CAPABILITY_KIND_ZH, cap.get('capability_kind', ''))}；"
            f"动作类型：{_zh(ACTION_KIND_ZH, cap.get('action_kind', ''))}。"
            for capability_id, cap in sorted(lib["capabilities"].items())
        ) + "\n",
        encoding="utf-8",
    )
    (DOC / "behaviors.zh.md").write_text(
        "# 死亡细胞行为库（不含音效）\n\n"
        "行为由触发条件、执行动作、结果影响和所需能力组成；行为只描述玩法流程，运行时状态仍由状态黑板承载。\n\n"
        + "\n".join(
            f"- `{behavior_id}`：{_clean_name(behavior.get('display_name_zh'), behavior_id)}。"
            f"触发：{_clean_clause(_zh(TRIGGER_ZH, behavior.get('trigger', '')))}；"
            f"执行：{_clean_clause(_zh(EXECUTION_ZH, behavior.get('execution', '')))}；"
            f"结果：{_clean_clause(_zh(RESULT_ZH, behavior.get('result', '')))}；"
            f"所需能力：{', '.join(_capability_label(lib, cap_id) for cap_id in behavior.get('required_capability_ids', []))}。"
            for behavior_id, behavior in sorted(lib["behaviors"].items())
        ) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    lib = load_dead_cells_library()
    validate_library_self_consistency(lib)
    write_docs()
    print(json.dumps({
        "result": "pass",
        "entities": len(lib["entities"]),
        "capabilities": len(lib["capabilities"]),
        "behaviors": len(lib["behaviors"]),
        "contract": "Entity/Capability/Behavior only; runtime state belongs to StateBlackboard",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
