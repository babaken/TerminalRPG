"""2-3：色付き AA・スキルの演出・NPC の道順移動・加入レベル（lv=avg / lv=N）のテスト。"""
import random

import pytest

from test_play import Driver, _seed  # noqa: F401
from trpg.battle.core import Battle, Command
from trpg.data import Report, load_game_data
from trpg.data.models import parse_anim
from trpg.game import load_game
from trpg.package import open_package
from trpg.scenes.battle import BattleScene
from trpg.script.parser import parse_script
from trpg.term import Buffer, Style
from trpg.ui.aa import draw_aa
from trpg.world.state import GameState, Member

from conftest import edit


@pytest.fixture
def game(sample_dir):
    g = load_game(sample_dir)
    yield g
    g.close()


def new_driver(game):
    d = Driver(game)
    for _ in range(4):
        d.key("ENTER")
    d.settle()
    return d


def load_report(sample_dir) -> str:
    rep = Report()
    with open_package(sample_dir, rep) as pkg:
        load_game_data(pkg, rep)
    return rep.format()


# ---------------------------------------------------------------- 色付き AA
def test_draw_aa_colors():
    buf = Buffer(10, 2)
    draw_aa(buf, 0, 0, ["ab c", "de"], Style.of("white"), ["R.G", ""])
    row = buf.rows[0]
    assert row[0][1].fg == 9 and row[1][1].fg == 7 and row[3][1].fg == 7   # c は色指定なし → 既定
    assert row[2][0] == " "                                                 # 空白は透過
    assert buf.rows[1][0][1].fg == 7


def test_slime_color_loaded_and_drawn_in_battle(game):
    assert game.data.aa_color["aa/slime.txt"][0].strip() == "GGGGG"
    d = new_driver(game)
    b = d.field.start_battle("slime_2")
    d.tick(1.0)
    buf = Buffer(100, 30)
    b.draw(buf)
    greens = [c for row in buf.rows for c in row if c[0] == "-" and c[1].fg == 10]
    assert greens                                              # スライムの体が明るい緑で描かれている


def test_color_file_checks(sample_dir):
    (sample_dir / "aa" / "ghost.color").write_text("RR\n", encoding="utf-8")       # 対応する AA がない
    (sample_dir / "aa" / "bat.color").write_text("RZ\n" + "R" * 40 + "\n", encoding="utf-8")
    text = load_report(sample_dir)
    assert "aa/ghost.txt" in text and "'Z'" in text and "より長くなっています" in text


# ---------------------------------------------------------------- スキルの演出
def test_parse_anim():
    assert parse_anim("flash:red, shake:2") == [("flash", "red"), ("shake", "2")]
    assert parse_anim("") == []


def test_skill_anim_event_and_playback(game):
    st = GameState.new_game(game.data, game.manifest)
    st.party.append(Member.from_data(game.data, "mia"))
    b = Battle(game.data, st, "slime_2", rng=random.Random(0))
    mia = b.party[1]
    events = list(b._skill(mia, Command("skill", skill="fire", target=b.enemies[0])))
    anims = [v for k, v in events if k == "anim"]
    assert anims and anims[0][0] == "flash:red"

    d = new_driver(game)
    d.field.st.party.append(Member.from_data(game.data, "mia"))
    sc = d.field.start_battle("slime_2")
    sc._play_anim("flash:red,shake:2,blink", [sc.battle.enemies[0]])
    assert sc.anim_flash[0] == 1 and sc.shake >= 0.4 and id(sc.battle.enemies[0]) in sc.blink


def test_bad_anim_rejected(sample_dir):
    edit(sample_dir / "Items.data", 'anim = "flash:red"', 'anim = "explode"')
    edit(sample_dir / "Items.data", 'anim = "shake:2"', 'anim = "flash:rainbow"')
    text = load_report(sample_dir)
    assert "演出「explode」" in text and "rainbow" in text


# ---------------------------------------------------------------- 道順移動
def test_patrol_route(game):
    d = new_driver(game)
    f = d.field
    f.change_map("town_bern", 20, 1)
    f.pending_auto = False
    f.st.flags.add("ch1_gate_talked")
    patrol = f._find_npc("patrol")
    seen = []
    for _ in range(int(8 * 0.6 * 30) + 10):                    # 1 周（8 歩 × 0.6 秒）
        d.tick(1 / 30)
        p = f._npc_pos(patrol)
        if not seen or seen[-1] != p:
            seen.append(p)
    assert seen[:4] == [(22, 12), (23, 12), (24, 12), (25, 12)]
    assert seen[-1] == (22, 12)                                # 元の位置に戻った


def test_patrol_waits_when_blocked(game):
    d = new_driver(game)
    f = d.field
    f.change_map("town_bern", 23, 12)                          # 兵士の進む先に主人公が立つ
    f.pending_auto = False
    patrol = f._find_npc("patrol")
    d.tick(2.0)
    assert f._npc_pos(patrol) == (22, 12)
    assert f.st.npc("town_bern", "patrol").get("route_i", 0) == 0   # 進めなかった歩は数えない
    f.st.x = 30
    d.tick(0.7)
    assert f._npc_pos(patrol) == (23, 12)


def test_route_checks(sample_dir):
    m = sample_dir / "Map.data"
    edit(m, 'route = ["right", "right", "right", "wait", "left", "left", "left", "wait"]',
         'route = ["up", "up", "up", "up", "up", "up", "up", "up", "up", "up", "up", "up", "up"]')
    text = load_report(sample_dir)
    assert "NPC patrol の道順" in text and "通れないマス" in text

    edit(m, 'route = ["up", "up", "up", "up", "up", "up", "up", "up", "up", "up", "up", "up", "up"]',
         'route = ["right", "jump"]')
    assert "「jump」" in load_report(sample_dir)

    edit(m, 'route = ["right", "jump"]', 'route = ["right"]')
    assert "元の位置に戻りません" in load_report(sample_dir)


# ---------------------------------------------------------------- 加入レベル
def run(game, text, st):
    from trpg.script.vm import VM
    rep = Report()
    sc = parse_script("*t\n" + text + "\n", rep)
    assert rep.ok, rep.format()
    vm = VM(sc, st, game.data, None)
    vm.start("t")
    assert vm.step() is None


def test_party_add_lv_avg_and_number(game):
    random.seed(1)
    st = GameState.new_game(game.data, game.manifest)
    st.party[0].lv = 7
    run(game, "@party add garo lv=avg", st)
    garo = st.member("garo")
    assert garo.lv == 7 and garo.hp == garo.stat("hp", game.data) and garo.base["hp"] > 48
    run(game, "@party add mia lv=2", st)                      # もともと Lv3 → 下げない
    assert st.member("mia").lv == 3
    run(game, "@party add rina", st)
    assert st.member("rina").lv == 3


def test_recruit_lv_avg(game):
    from trpg.scenes.facility import RecruitScene
    d = new_driver(game)
    f = d.field
    f.st.party[0].lv = 6
    sc = RecruitScene(f, ["garo", "mia"], 1, lv="avg")
    d.app.push(sc)
    assert sc.list.rows[0][1] == "Lv 6"
    while sc.msg.active:
        d.key("ENTER")
    d.key("ENTER")                                             # ガロ
    d.key("ENTER")                                             # はい
    assert f.st.member("garo").lv == 6


def test_recruit_lv_validated():
    rep = Report()
    parse_script("*t\n@recruit garo lv=high\n", rep)
    assert "lv は整数か avg" in rep.format()
