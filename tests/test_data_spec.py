"""データ仕様書（docs/data_spec.md）が、エンジンの読み込み処理と食い違っていないこと。

読み込み処理（loader.py・manifest.py）が読む項目名と、選択肢の定数の値が、すべて仕様書に `項目名` の形で
載っているかを確かめる（項目を足したのに仕様書を書き忘れると失敗する）。
"""
import re
from pathlib import Path

from trpg.data import models

ROOT = Path(__file__).resolve().parent.parent
SPEC = (ROOT / "docs" / "data_spec.md").read_text(encoding="utf-8")
SOURCES = [ROOT / "src" / "trpg" / "data" / "loader.py", ROOT / "src" / "trpg" / "package" / "manifest.py"]

# t.str("name") / t.int("lv", …) / t.sub("use", …) / t.table_list("event") / f.entries("map") / _stats(t, "growth") など
_CALL = re.compile(r"\.(?:str|int|num|bool|strlist|intpair|sub|table_list|entries|raw|has|id)\(\s*\"([a-z_]+)\"")
_STATS = re.compile(r"_stats\(\s*\w+,\s*\"([a-z_]+)\"")
_GOAL_KEYS = re.compile(r"for k in \(([^)]*)\)")


def keys_in_sources() -> set[str]:
    keys = set()
    for src in SOURCES:
        text = src.read_text(encoding="utf-8")
        keys |= set(_CALL.findall(text)) | set(_STATS.findall(text))
        for group in _GOAL_KEYS.findall(text):
            keys |= set(re.findall(r"\"([a-z_]+)\"", group))
    return keys


def documented(key: str) -> bool:
    """`key` か、表の見出し [key] / [[key]] として載っているか。"""
    return f"`{key}`" in SPEC or f"[{key}]" in SPEC or f"[[{key}]]" in SPEC


def test_every_loaded_key_is_documented():
    missing = sorted(k for k in keys_in_sources() if not documented(k))
    assert not missing, f"データ仕様書に載っていない項目: {missing}"


def test_every_choice_is_documented():
    groups = {
        "STAT_KEYS": models.STAT_KEYS, "ELEMENTS": models.ELEMENTS, "EQUIP_SLOTS": models.EQUIP_SLOTS,
        "ITEM_TYPES": models.ITEM_TYPES, "TARGETS": models.TARGETS, "SKILL_KINDS": models.SKILL_KINDS,
        "AI_TYPES": models.AI_TYPES, "EVENT_TRIGGERS": models.EVENT_TRIGGERS, "NPC_MOVES": models.NPC_MOVES,
        "QUEST_GOALS": models.QUEST_GOALS, "SKILL_ANIMS": models.SKILL_ANIMS, "USE_EFFECTS": models.USE_EFFECTS,
        "ROUTE_STEPS": models.ROUTE_STEPS, "TRAP_TARGETS": models.TRAP_TARGETS,
    }
    missing = [f"{name}:{v}" for name, values in groups.items() for v in values if f"`{v}`" not in SPEC]
    assert not missing, f"データ仕様書に載っていない選択肢: {missing}"


def test_sample_keys_are_found():
    keys = keys_in_sources()
    for k in ("familiar", "traps", "sp", "regen", "copy", "growth", "trap_kinds", "dungeon", "sell_rate"):
        assert k in keys                                          # 抜き出し方そのものが壊れていないこと
