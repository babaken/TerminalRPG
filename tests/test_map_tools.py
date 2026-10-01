"""3-3c：マップエディタの範囲の塗りつぶし・コピー・貼り付け、大きさの変更、新しいマップ。"""
import tomllib

from trpg.tools import mapfile

from test_map_editor import Ed
from test_map_objects import goto, saved, typ


def test_fill_rect_and_undo(sample_dir):
    e = Ed(sample_dir)
    before = list(e.rows())
    e.key("1")                                               # 壁
    goto(e, 1, 1)
    e.key("v", "RIGHT", "RIGHT", "DOWN")
    assert e.s.mode == "select" and "3×2" in e.screen()
    e.key("f")
    assert e.rows()[1][1:4] == "###" and e.rows()[2][1:4] == "###" and e.rows()[3][1:4] == before[3][1:4]
    assert "塗りつぶしました" in e.screen()
    e.key("u")
    assert e.rows() == before


def test_select_cancel(sample_dir):
    e = Ed(sample_dir)
    before = list(e.rows())
    goto(e, 1, 1)
    e.key("1", "v", "RIGHT", "ESC")
    assert e.s.mode == "edit" and e.rows() == before


def test_copy_paste_clipped(sample_dir):
    e = Ed(sample_dir, "village_lito")
    goto(e, 3, 2)                                           # 家（HHH / HDH）
    e.key("v", "RIGHT", "RIGHT", "DOWN", "c")
    assert e.s.clip == ["HHH", "HDH"] and "コピー 3×2" in e.screen()
    goto(e, 10, 14)
    e.key("b")
    assert e.rows()[14][10:13] == "HHH" and e.rows()[15][10:13] == "HDH"
    goto(e, e.s.width - 2, e.s.height - 1)                  # 右下の角：はみ出た分は切り捨て
    e.key("b")
    assert "切り捨て" in e.screen()
    assert e.rows()[-1][-2:] == "HH" and len(e.rows()[-1]) == e.s.width


def test_paste_without_copy(sample_dir):
    e = Ed(sample_dir)
    e.key("b")
    assert "コピーした範囲がありません" in e.screen()


def test_resize_grow_and_shrink(sample_dir):
    e = Ed(sample_dir, "house_hero")
    w, h = e.s.width, e.s.height
    e.key("r")
    assert "マップの大きさを変える" in e.screen()
    f = e.s.form
    f.values.update(width=w + 3, height=h + 2, fill=".")
    e.key("F2")
    assert (e.s.width, e.s.height) == (w + 3, h + 2)
    assert e.rows()[0].endswith("...") and e.rows()[-1] == "." * (w + 3)
    e.key("s")
    assert "エラー 0 件" in e.screen()
    assert len(saved(sample_dir, "house_hero")["rows"]) == h + 2
    e.key("u")
    assert (e.s.width, e.s.height) == (w, h)


def test_resize_blocked_by_objects(sample_dir):
    e = Ed(sample_dir, "house_hero")
    e.key("r")
    e.s.form.values.update(width=2, height=2)
    e.key("F2")
    assert e.s.mode == "form" and "外に出ます" in e.screen()
    e.s.form.values.update(width=0)
    e.key("F2")
    assert "1〜200" in e.screen()


def test_new_map(sample_dir):
    e = Ed(sample_dir)
    e.key("m", "a")
    assert e.s.mode == "form" and "マップを追加" in e.screen()
    f = e.s.form
    f.row = 0
    e.key("ENTER")
    for _ in range(10):
        e.key("BACKSPACE")
    typ(e, "cave_b1")
    e.key("ENTER", "DOWN", "ENTER")
    for _ in range(10):
        e.key("BACKSPACE")
    typ(e, "洞穴 B1")
    e.key("ENTER")
    f.values.update(width=12, height=8, fill="#", dark=True)
    e.key("F2")
    assert e.s.map_id == "cave_b1" and (e.s.width, e.s.height) == (12, 8)
    assert "洞穴 B1（cave_b1） 12×8 *" in e.screen()
    goto(e, 1, 1)
    e.key("2", "v", "RIGHT", "RIGHT", "DOWN", "f", "s")
    assert "エラー 0 件" in e.screen()
    m = saved(sample_dir, "cave_b1")
    assert m["name"] == "洞穴 B1" and m["dark"] is True and m["rows"][1] == "#...########"
    assert m["tileset"] == "default" and "indoor" not in m


def test_new_map_validation_and_undo(sample_dir):
    e = Ed(sample_dir)
    e.key("m", "a")
    e.s.form.values["id"] = "house_hero"
    e.key("F2")
    assert "すでにあります" in e.screen()
    e.s.form.values["id"] = "Bad"
    e.key("F2")
    assert "英小文字" in e.screen()
    e.s.form.values["id"] = "tmp_map"
    e.key("F2")
    assert e.s.map_id == "tmp_map" and "tmp_map" in e.s.dirty
    e.key("u")
    assert "tmp_map" not in e.gd.maps and e.s.map_id == "house_hero" and not e.s.dirty
    assert "tmp_map" not in e.s.text


def test_add_map_text():
    text = '[[map]]\nid = "a"\nrows = [".."]\n\n[[map.npc]]\nid = "n"\n'
    out = mapfile.add_map(text, {"id": "b", "name": "B", "dark": None}, ["##", "##"])
    data = tomllib.loads(out)
    assert data["map"][0]["npc"][0]["id"] == "n" and data["map"][1] == {"id": "b", "name": "B", "rows": ["##", "##"]}
    assert out.startswith(text)
