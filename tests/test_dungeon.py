"""4-1：ダンジョン機能（dungeon マップの名前表示、map 条件式、ワープアイテム、@tile、暗いマップ）。"""
import pytest

from test_menu import choose, pick, read_msgs, top  # noqa: F401
from test_play import Driver, _seed  # noqa: F401
from trpg.data import Report, load_game_data
from trpg.game import load_game
from trpg.package import open_package
from trpg.save import state_from_dict, state_to_dict
from trpg.scenes.field import FieldScene
from trpg.scenes.menu import MenuScene
from trpg.script.lint import lint_script
from trpg.script.parser import parse_script

from conftest import edit

WING = '''
[[item]]
id = "wing"
name = "帰り羽"
type = "consumable"
use = { field = true, effect = "warp", to = "town_bern", x = 20, y = 12, dir = "down", when = "map.dungeon" }
'''

SCRIPT = '''
*tile_test
@tile 3 3 #
@tile 1 1 T map=village_lito
@end

*where_test
@if map == house_hero and !map.dungeon
@flag set in_house
@endif
@if map.dungeon
@flag set in_dungeon
@endif
@end
'''


@pytest.fixture
def game(sample_dir):
    (sample_dir / "Items.data").write_text((sample_dir / "Items.data").read_text(encoding="utf-8") + WING,
                                           encoding="utf-8")
    edit(sample_dir / "Map.data", 'id = "forest_1"\n', 'id = "forest_1"\ndungeon = true\n')
    sco = sample_dir / "scenario.sco"
    sco.write_text(sco.read_text(encoding="utf-8") + SCRIPT, encoding="utf-8")
    g = load_game(sample_dir)
    yield g
    g.close()


@pytest.fixture
def d(game):
    d = Driver(game)
    for _ in range(4):
        d.key("ENTER")
    d.settle()
    return d


def run(d, label):
    d.field.start_script(label)
    d.tick(0.3)
    while d.field.msg.active:
        d.key("ENTER")


def test_dungeon_banner(d):
    f = d.field
    assert f.map.id == "house_hero" and f.banner_left == 0
    f.change_map("forest_1", 15, 15)
    f.pending_auto = False
    d.tick(0.5)
    assert "囁きの森" in d.screen() and f.banner_left > 0
    assert d.screen().count("囁きの森") == 2                  # 枠の題名と名前の表示
    d.tick(2.0)
    assert d.screen().count("囁きの森") == 1
    f.change_map("forest_1", 15, 14)                          # 同じ階の中の移動では出さない
    assert f.banner_left == 0


def test_map_condition(d):
    run(d, "where_test")
    st = d.field.st
    assert "in_house" in st.flags and "in_dungeon" not in st.flags
    d.field.change_map("forest_1", 15, 15)
    d.field.pending_auto = False
    run(d, "where_test")
    assert "in_dungeon" in st.flags


def test_warp_item_only_in_dungeon(d):
    st = d.field.st
    st.add_item("wing", 2)
    top(d, "どうぐ")
    pick(d, "帰り羽")
    choose(d, 0)
    assert "ここでは使えない" in " ".join(read_msgs(d))
    assert st.items["wing"] == 2
    d.key("ESC")
    d.key("ESC")
    d.field.change_map("forest_1", 15, 15)
    d.field.pending_auto = False
    d.tick(2.5)
    top(d, "どうぐ")
    pick(d, "帰り羽")
    choose(d, 0)
    assert isinstance(d.scene, FieldScene)
    assert (st.map_id, st.x, st.y, st.dir) == ("town_bern", 20, 12, "down")
    assert st.items["wing"] == 1
    d.tick(0.5)
    assert "帰り羽を使った" in d.screen()


def test_tile_command_persists(d, game):
    f = d.field
    st = f.st
    run(d, "tile_test")
    assert st.tile_override("house_hero", 3, 3) == "#" and not f.passable(3, 3)
    assert st.tile_override("village_lito", 1, 1) == "T"
    restored = state_from_dict(state_to_dict(st))
    assert restored.tiles == st.tiles
    f.change_map("village_lito", 2, 1)
    f.pending_auto = False
    assert not f.passable(1, 1) and "木" in d.screen()


def test_tile_lint(sample_dir):
    sco = sample_dir / "scenario.sco"
    sco.write_text(sco.read_text(encoding="utf-8") + '''
*bad_tile
@tile 99 0 # map=house_hero
@tile 1 1 Q map=house_hero
@tile 1 1 . map=nowhere
@tile 1 1 %
@end
''', encoding="utf-8")
    rep = Report()
    with open_package(sample_dir, rep) as pkg:
        gd = load_game_data(pkg, rep)
        sc = parse_script(sco.read_text(encoding="utf-8"), rep, "scenario.sco", loader=pkg.read_text)
        lint_script(sc, gd, rep, pkg)
    text = rep.format()
    assert "マップ house_hero の外" in text and "「Q」はマップ house_hero" in text
    assert "nowhere" in text and "「%」はどのタイルセットにもありません" in text


def test_warp_item_data_checks(sample_dir):
    (sample_dir / "Items.data").write_text((sample_dir / "Items.data").read_text(encoding="utf-8") + '''
[[item]]
id = "bad_wing"
name = "壊れた羽"
type = "consumable"
use = { field = true, effect = "warp", to = "nowhere" }

[[item]]
id = "bad_wing2"
name = "壊れた羽2"
type = "consumable"
use = { field = true, effect = "warp", to = "house_hero", x = 99, when = "map ==" }

[[item]]
id = "bad_wing3"
name = "壊れた羽3"
type = "consumable"
use = { field = true, effect = "warp" }
''', encoding="utf-8")
    rep = Report()
    with open_package(sample_dir, rep) as pkg:
        load_game_data(pkg, rep)
    text = rep.format()
    assert "nowhere" in text and "house_hero の外" in text and "条件式の誤り" in text and "to" in text


def test_dark_dungeon_hides_far_npcs(d):
    f = d.field
    f.pending_auto = False
    npcs = [n for n in f.map.npcs if f.npc_visible(n)]
    assert npcs
    n = npcs[0]
    assert n.glyph in d.screen()
    f.map.dark = True
    try:
        far = [(x, y) for y in range(f.map.height) for x in range(f.map.width)
               if f.passable(x, y) and (abs(x - n.x) > 3 or abs(y - n.y) > 3) and not f.npc_at(x, y)]
        f.st.x, f.st.y = far[0]
        assert n.glyph not in d.screen()                          # 周囲 3 マスの外は見えない
        f.st.x, f.st.y = n.x, n.y + 1 if f.passable(n.x, n.y + 1) else n.y - 1
        assert n.glyph in d.screen()
    finally:
        f.map.dark = False
