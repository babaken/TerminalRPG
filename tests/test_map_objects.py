"""3-3b：マップエディタで NPC・ワープ・イベントを置く・編集する・動かす・消す。"""
import tomllib

import pytest

from trpg.tools import mapfile
from trpg.tools.mapfile import MapFileError

from test_map_editor import Ed


def saved(folder, map_id):
    data = tomllib.loads((folder / "Map.data").read_text(encoding="utf-8"))
    return [m for m in data["map"] if m["id"] == map_id][0]


def typ(e, text):
    for ch in text:
        e.key(ch)


def goto(e, x, y):
    e.s.x, e.s.y = x, y


# ---------------------------------------------------------------- Map.data の書き換え
TEXT = '''[[map]]
id = "a"
rows = ["....", "...."]

[[map.npc]]            # 番兵
id = "g"
glyph = "兵"
x = 1   # 横
y = 1
talk = "t"

[[map.warp]]
x = 0
y = 0
to = "b"
tx = 0
ty = 0

# ===== 次 =====
[[map]]
id = "b"
rows = [".."]
'''


def test_set_object_keeps_comments():
    out = mapfile.set_object(TEXT, "a", "npc", 0, {"x": 3, "talk": None, "color": "red"})
    assert "[[map.npc]]            # 番兵" in out and "x = 3   # 横" in out
    assert "talk" not in out and 'color = "red"' in out
    assert mapfile.read_objects(out)["a"]["npc"][0] == {"id": "g", "glyph": "兵", "x": 3, "y": 1, "color": "red"}


def test_add_and_delete_object():
    out = mapfile.add_object(TEXT, "a", "event", {"x": 2, "y": 0, "label": "ev", "once": True})
    assert out.index("[[map.event]]") < out.index("# ===== 次 =====")      # 次のマップの説明より前
    assert mapfile.read_objects(out)["a"]["event"] == [{"x": 2, "y": 0, "label": "ev", "once": True}]
    out = mapfile.add_object(out, "b", "npc", {"id": "z", "glyph": "人", "x": 0, "y": 0, "route": ["up", "down"]})
    assert out.rstrip().endswith('route = ["up", "down"]')
    out = mapfile.delete_object(out, "a", "npc", 0)
    assert "番兵" not in out and "\n\n\n" not in out
    objs = mapfile.read_objects(out)
    assert objs["a"]["npc"] == [] and len(objs["a"]["warp"]) == 1 and objs["b"]["npc"][0]["id"] == "z"
    with pytest.raises(MapFileError):
        mapfile.delete_object(out, "a", "npc", 0)


def test_sample_objects_round_trip(sample_dir):
    text = (sample_dir / "Map.data").read_text(encoding="utf-8")
    for mid, kinds in mapfile.read_objects(text).items():
        for kind, objs in kinds.items():
            for i, o in enumerate(objs):
                assert mapfile.set_object(text, mid, kind, i, dict(o)) == text      # 同じ値なら何も変わらない


# ---------------------------------------------------------------- エディタ
def test_add_npc_with_form(sample_dir):
    e = Ed(sample_dir)
    goto(e, 3, 3)
    e.key("n")
    assert e.s.mode == "form" and "NPCを追加" in e.screen()
    f = e.s.form
    f.row = 0
    e.key("ENTER")
    for _ in range(4):
        e.key("BACKSPACE")
    typ(e, "guest")
    e.key("ENTER")
    e.key("DOWN", "ENTER", "BACKSPACE")
    typ(e, "客")
    e.key("ENTER", "DOWN", "RIGHT")                          # 色を選ぶ
    e.key("F2")
    assert e.s.mode == "edit" and "NPC guest を置きました" in e.screen()
    npc = e.s.objs["house_hero"]["npc"][-1]
    assert npc == {"id": "guest", "glyph": "客", "color": "black", "x": 3, "y": 3}
    assert "house_hero" in e.s.dirty and "客" in e.screen()
    e.key("s")
    assert "エラー 0 件" in e.screen()
    assert saved(sample_dir, "house_hero")["npc"][-1]["id"] == "guest"


def test_form_validation(sample_dir):
    e = Ed(sample_dir)
    mother = e.s.objs["house_hero"]["npc"][0]
    goto(e, 1, 1)
    e.key("n", "ENTER", "BACKSPACE", "BACKSPACE", "BACKSPACE", "BACKSPACE")
    typ(e, mother["id"])
    e.key("ENTER", "F2")
    assert "使われています" in e.screen() and e.s.mode == "form"
    e.key("ENTER", "BACKSPACE")                                # ID の欄
    typ(e, "Bad")
    e.key("ENTER", "F2")
    assert "英小文字" in e.screen()
    e.key("ESC")
    assert e.s.mode == "edit" and len(e.s.objs["house_hero"]["npc"]) == len(saved(sample_dir, "house_hero")["npc"])


def test_add_warp_checks_target(sample_dir):
    e = Ed(sample_dir)
    goto(e, 2, 2)
    e.key("w")
    f = e.s.form
    f.values["to"] = "house_hero"
    f.values["tx"] = 99
    e.key("F2")
    assert "外です" in e.screen()
    f.values["tx"] = 1
    e.key("F2")
    w = e.s.objs["house_hero"]["warp"][-1]
    assert w == {"x": 2, "y": 2, "to": "house_hero", "tx": 1, "ty": 0} and "Ｗ" in e.screen()


def test_add_event_and_edit(sample_dir):
    e = Ed(sample_dir)
    goto(e, 4, 4)
    e.key("e", "ENTER")
    typ(e, "my_event")
    e.key("ENTER", "DOWN", "RIGHT", "DOWN", "ENTER", "F2")   # きっかけ → auto、一度きり → はい
    ev = e.s.objs["house_hero"]["event"][-1]
    assert ev == {"x": 4, "y": 4, "trigger": "auto", "label": "my_event", "once": True}
    e.key("c")
    assert "イベントを編集" in e.screen()
    e.key("DOWN", "DOWN", "ENTER", "F2")                      # 一度きり → いいえ（もともと書いてあるので false と書く）
    assert e.s.objs["house_hero"]["event"][-1]["once"] is False


def test_move_object_and_undo(sample_dir):
    e = Ed(sample_dir)
    mother = e.s.objs["house_hero"]["npc"][0]
    goto(e, mother["x"], mother["y"])
    e.key("g", "RIGHT", "DOWN")
    assert e.s.mode == "move"
    e.key("ENTER")
    moved = e.s.objs["house_hero"]["npc"][0]
    assert (moved["x"], moved["y"]) == (mother["x"] + 1, mother["y"] + 1)
    assert "動かしました" in e.screen()
    e.key("u")
    assert e.s.objs["house_hero"]["npc"][0] == mother and "house_hero" not in e.s.dirty
    goto(e, mother["x"], mother["y"])
    e.key("g", "LEFT", "ESC")
    assert e.s.objs["house_hero"]["npc"][0] == mother and (e.s.x, e.s.y) == (mother["x"], mother["y"])


def test_delete_with_confirm_and_pick(sample_dir):
    e = Ed(sample_dir)
    mother = e.s.objs["house_hero"]["npc"][0]
    goto(e, mother["x"], mother["y"])
    e.key("x")
    assert "消しますか" in e.screen()
    e.key("n")
    assert len(e.s.objs["house_hero"]["npc"]) == 3
    e.key("e", "ENTER")                                       # 同じマスにイベントも置く
    typ(e, "here")
    e.key("ENTER", "F2", "x")
    assert e.s.mode == "pick" and "どれにしますか" in e.screen()
    e.key("DOWN", "ENTER", "y")
    assert e.s.objs["house_hero"]["event"] == [] or all(o["label"] != "here" for o in e.s.objs["house_hero"]["event"])
    assert e.s.objs["house_hero"]["npc"][0] == mother
    e.key("s")
    assert "here" not in (sample_dir / "Map.data").read_text(encoding="utf-8")


def test_nothing_here(sample_dir):
    e = Ed(sample_dir)
    goto(e, 1, 1)
    e.key("c")
    assert "ありません" in e.screen()
    e.key("o", "g")
    assert "表示していません" in e.screen()


def test_save_after_undo_of_object_keeps_rows(sample_dir):
    e = Ed(sample_dir)
    goto(e, 1, 1)
    e.key("1", "ENTER", "e", "ENTER")
    typ(e, "x1")
    e.key("ENTER", "F2", "s", "u", "s")                       # 塗る → イベント → 保存 → イベントを戻す → 保存
    m = saved(sample_dir, "house_hero")
    assert m["rows"][1][1] == "#" and not m.get("event")
