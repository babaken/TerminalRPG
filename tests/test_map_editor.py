"""3-3a：マップエディタ（表示・タイルを塗る・保存）のテスト。"""
import tomllib

import pytest

from trpg.app import App
from trpg.package import PackageError
from trpg.term import CONT, Buffer, Key, KeyEvent
from trpg.tools.map_editor import EditorScene, load, main
from trpg.tools.mapfile import MapFileError, format_rows, quote, replace_rows

from conftest import edit


class Ed:
    def __init__(self, folder, map_id="house_hero"):
        self.root, self.gd, rep = load(folder)
        self.s = EditorScene(self.root, self.gd, map_id, rep)
        self.app = App(self.s)
        self.app.running = True

    def key(self, *keys):
        for k in keys:
            ev = KeyEvent(Key[k]) if k in Key.__members__ and len(k) > 1 else KeyEvent(Key.CHAR, k)
            self.s.on_key(ev, self.app.keymap.actions(ev))

    def screen(self, w=100, h=30):
        buf = Buffer(w, h)
        self.s.draw(buf)
        return "\n".join("".join(c[0] for c in row if c[0] != CONT) for row in buf.rows)

    def rows(self, map_id=None):
        return self.s.rows[map_id or self.s.map_id]


def saved_rows(folder, map_id):
    data = tomllib.loads((folder / "Map.data").read_text(encoding="utf-8"))
    return [m["rows"] for m in data["map"] if m["id"] == map_id][0]


# ---------------------------------------------------------------- Map.data の書き換え
def test_replace_rows_keeps_everything_else():
    text = '''# 説明
[[map]]
id = "a"   # 最初
rows = [   # 行
  "#]#",   # 括弧を含む
  "#.#",
]
dark = true

[[map.warp]]
x = 1

[[map]]
id = "b"
rows = ["..", ".."]
'''
    out = replace_rows(text, "b", ["#\\", '"#'])
    assert out.startswith(text[: text.index('rows = ["..')])        # a はそのまま（コメントも）
    assert tomllib.loads(out)["map"][1]["rows"] == ["#\\", '"#']
    out = replace_rows(text, "a", ["...", "..."])
    assert "# 説明" in out and "dark = true" in out and "[[map.warp]]" in out
    assert tomllib.loads(out)["map"][0]["rows"] == ["...", "..."]
    with pytest.raises(MapFileError, match="見つかりません"):
        replace_rows(text, "zzz", ["."])


def test_replace_rows_crlf_and_format():
    text = '[[map]]\r\nid = "a"\r\nrows = [\r\n  "..",\r\n]\r\n'
    out = replace_rows(text, "a", ["##"])
    assert out == '[[map]]\r\nid = "a"\r\nrows = [\r\n  "##",\r\n]\r\n'
    assert format_rows(["a"], "  ") == '[\n    "a",\n  ]'
    assert quote('a"b\\') == '"a\\"b\\\\"'


def test_unchanged_save_is_identical(sample_dir):
    text = (sample_dir / "Map.data").read_text(encoding="utf-8")
    data = tomllib.loads(text)
    for m in data["map"]:
        assert replace_rows(text, m["id"], m["rows"]) == text


# ---------------------------------------------------------------- 編集
def test_screen_shows_map_palette_and_objects(sample_dir):
    e = Ed(sample_dir, "town_bern")
    sc = e.screen()
    assert "交易都市ベルン（town_bern） 40×24" in sc
    assert "1 # ＃ 壁" in sc and "地面" in sc
    assert "兵" in sc and "Ｗ" in sc                       # NPC とワープ
    e.key("o")
    assert "兵" not in e.screen()
    e.key("?")
    assert "操作説明" in e.screen()
    e.key("x")
    assert e.s.mode == "edit"


def test_paint_pick_undo(sample_dir):
    e = Ed(sample_dir)
    e.key("RIGHT", "DOWN")                                 # (1, 1) は地面
    assert e.rows()[1][1] == "."
    e.key("1", "ENTER")                                    # 壁で塗る
    assert e.rows()[1][1] == "#" and "house_hero" in e.s.dirty and " *" in e.screen()
    e.key("]", "]", " ")             # 3 番目（木）
    assert e.rows()[1][1] == "T"
    e.key("RIGHT", "RIGHT", "i")                           # スポイト
    assert e.gd.maps["house_hero"].rows[1][3] == e.s.tiles[e.s.brush_i].char
    e.key("u", "u")
    assert e.rows()[1][1] == "." and "house_hero" not in e.s.dirty
    e.key("u")
    assert "元に戻す操作はありません" in e.screen()


def test_pen_paints_while_moving(sample_dir):
    e = Ed(sample_dir)
    e.key("RIGHT", "DOWN", "1", "p", "RIGHT", "RIGHT", "p", "RIGHT")
    assert e.rows()[1][1:5] == "###."


def test_cursor_stays_in_map_and_scrolls(sample_dir):
    e = Ed(sample_dir, "town_bern")
    for _ in range(60):
        e.key("RIGHT")
    e.key("PGDN", "PGDN", "PGDN")
    assert (e.s.x, e.s.y) == (39, 23)
    e.screen()
    assert e.s.ox > 0                                      # 右へずれた
    e.key("HOME")
    e.screen()
    assert e.s.x == 0 and e.s.ox == 0


def test_switch_maps_keeps_edits(sample_dir):
    e = Ed(sample_dir)
    e.key("RIGHT", "DOWN", "1", "ENTER", "m")
    assert "a：新しいマップ" in e.screen()
    while list(e.gd.maps)[e.s.list_i] != "forest_1":
        e.key("DOWN")
    e.key("ENTER")
    assert e.s.map_id == "forest_1"
    e.key("m")
    assert "* house_hero" in e.screen()
    e.key("ESC")
    assert e.s.mode == "edit" and e.s.map_id == "forest_1"


# ---------------------------------------------------------------- 保存
def test_save_writes_only_rows(sample_dir):
    before = (sample_dir / "Map.data").read_text(encoding="utf-8")
    e = Ed(sample_dir)
    e.key("RIGHT", "DOWN", "1", "ENTER", "s")
    assert "保存しました（1 マップ）" in e.screen() and "エラー 0 件" in e.screen()
    assert not e.s.dirty
    assert saved_rows(sample_dir, "house_hero")[1][1] == "#"
    after = (sample_dir / "Map.data").read_text(encoding="utf-8")
    diff = [(a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b]
    assert len(diff) == 1 and len(before.splitlines()) == len(after.splitlines())
    assert (sample_dir / "Map.data.bak").read_text(encoding="utf-8") == before
    e.key("s")
    assert "変更はありません" in e.screen()


def test_save_reports_validation(sample_dir):
    e = Ed(sample_dir, "house_hero")
    npc = e.gd.maps["house_hero"].npcs[0]
    e.s.x, e.s.y = npc.x, npc.y
    e.key("1", "ENTER", "s")                               # NPC を壁の上にする → 警告
    assert "警告" in e.screen() and saved_rows(sample_dir, "house_hero")[npc.y][npc.x] == "#"


def test_quit_confirm(sample_dir):
    e = Ed(sample_dir)
    e.key("q")
    assert not e.app.running                               # 変更なし → すぐ終わる
    e = Ed(sample_dir)
    e.key("RIGHT", "DOWN", "1", "ENTER", "q")
    assert e.app.running and "保存していない変更" in e.screen()
    e.key("ESC")
    assert e.app.running and e.s.mode == "edit"
    e.key("ESC", "n")
    assert not e.app.running and saved_rows(sample_dir, "house_hero")[1][1] == "."
    e = Ed(sample_dir)
    e.key("RIGHT", "DOWN", "1", "ENTER", "q", "y")
    assert not e.app.running and saved_rows(sample_dir, "house_hero")[1][1] == "#"


def test_fullwidth_keys_from_ime(sample_dir):
    e = Ed(sample_dir)
    e.key("RIGHT", "DOWN", "１", "ENTER")                 # IME オンの「１」
    assert e.rows()[1][1] == "#"


def test_unknown_tile_shown(sample_dir):
    e = Ed(sample_dir)
    e.s.rows["house_hero"][1] = "#?" + e.s.rows["house_hero"][1][2:]
    e.s.x, e.s.y = 1, 1
    assert "？" in e.screen() and "（未定義）" in e.screen()


def test_load_errors(sample_dir, tmp_path, capsys):
    with pytest.raises(PackageError, match="zip は編集できません"):
        load(tmp_path / "x.zip")
    assert main([str(sample_dir), "--map", "nowhere"]) == 1
    assert "nowhere" in capsys.readouterr().err
    edit(sample_dir / "Map.data", "[[map]]", "[[map]")      # TOML の誤り
    with pytest.raises(PackageError, match="マップがありません"):
        load(sample_dir)
