"""SP（スキルポイント）：技は SP、魔法は MP。最大 SP は職業と Lv で決まり、戦闘中は毎ターン回復する。"""
import random

import pytest

from test_play import Driver, _seed  # noqa: F401
from trpg.battle.core import Battle, Command
from trpg.data import Report, load_game_data
from trpg.game import load_game
from trpg.package import open_package
from trpg.save import state_from_dict, state_to_dict
from trpg.term import Buffer
from trpg.world.growth import level_up, raise_to_level
from trpg.world.state import GameState, Member

from conftest import edit


@pytest.fixture
def game(sample_dir):
    g = load_game(sample_dir)
    yield g
    g.close()


def msgs(events):
    return [v for k, v in events if k == "msg"]


def test_max_sp_by_job_and_level(game):
    gd = game.data
    garo = Member.from_data(gd, "garo")                       # 戦士 Lv3：10 + 3 × 2
    assert garo.max_sp(gd) == 16 and garo.sp == 16 and garo.max_mp == 0
    mia = Member.from_data(gd, "mia")                         # 魔法使いは SP なし
    assert mia.max_sp(gd) == 0
    level_up(garo, gd, random.Random(0))
    assert garo.max_sp(gd) == 19 and garo.sp == 19
    raise_to_level(garo, gd, 10)
    assert garo.sp == garo.max_sp(gd) == 10 + 3 * 9


def test_garo_can_use_power_slash(game):
    gd = game.data
    st = GameState.new_game(gd, game.manifest)
    st.party.append(Member.from_data(gd, "garo"))
    b = Battle(gd, st, "slime_2", rng=random.Random(0))
    garo = b.party[1]
    assert garo.mp == 0
    out = msgs(b._skill(garo, Command("skill", skill="power_slash", target=b.enemies[0])))
    assert "強撃" in out[0] and "足りない" not in " ".join(out)
    assert garo.sp == 16 - 6 and garo.mp == 0
    garo.sp = 3
    out = msgs(b._skill(garo, Command("skill", skill="power_slash", target=b.enemies[0])))
    assert "SP が足りない" in " ".join(out) and garo.sp == 3


def test_sp_regen_each_turn_and_kept_after_battle(game):
    gd = game.data
    st = GameState.new_game(gd, game.manifest)
    st.party.append(Member.from_data(gd, "garo"))
    st.party[1].sp = 0
    b = Battle(gd, st, "slime_2", rng=random.Random(0))
    msgs(b._end_of_round())
    assert st.party[1].sp == 3                                # 毎ターン +3（戦闘後もそのまま）
    st.party[1].sp = 15
    msgs(b._end_of_round())
    assert st.party[1].sp == 16                               # 最大で止まる


def test_magic_still_uses_mp(game):
    gd = game.data
    st = GameState.new_game(gd, game.manifest)
    st.party.append(Member.from_data(gd, "mia"))
    b = Battle(gd, st, "slime_2", rng=random.Random(0))
    mia = b.party[1]
    mp0 = mia.mp
    msgs(b._skill(mia, Command("skill", skill="fire", target=b.enemies[0])))
    assert mia.mp == mp0 - 4


def test_heal_inn_and_old_save(game):
    gd = game.data
    st = GameState.new_game(gd, game.manifest)
    st.party.append(Member.from_data(gd, "garo"))
    st.party[1].sp = 2
    d = state_to_dict(st)
    assert state_from_dict(d).party[1].sp == 2
    del d["party"][1]["sp"]                                   # SP がない古いセーブ
    old = state_from_dict(d)
    assert old.party[1].sp == -1
    old.party[1].fix_sp(gd)
    assert old.party[1].sp == 16


def test_display_and_heal_command(game):
    d = Driver(game)
    for _ in range(4):
        d.key("ENTER")
    d.settle()
    f = d.field
    garo = Member.from_data(game.data, "garo")
    garo.sp = 5
    f.st.party.append(garo)
    assert "SP   5/16" in d.screen()                          # フィールドのパネル
    sc = f.start_battle("slime_2")
    d.tick(1.0)
    while sc.mode != "command":
        d.key("ENTER")
    def screen():
        buf = Buffer(100, 30)
        sc.draw(buf)
        return "\n".join("".join(c[0] for c in r) for r in buf.rows)
    assert "SP   5/16" in screen()                            # 戦闘画面の仲間の欄
    sc.actor_i = sc.actors.index(sc.battle.party[1])          # ガロの番にする
    sc.menu_i = [label for label, _ in sc._menu()].index("スキル")
    d.key("ENTER")
    assert "強撃" in screen() and "SP 6" in screen()          # スキルの一覧（消費は SP）


def test_sp_skill_on_job_without_sp_warns(sample_dir):
    edit(sample_dir / "Friends.data", 'skills = [ { lv = 1, skill = "fire" } ]',
         'skills = [ { lv = 1, skill = "fire" }, { lv = 2, skill = "power_slash" } ]')
    rep = Report()
    with open_package(sample_dir, rep) as pkg:
        load_game_data(pkg, rep)
    assert "最大 SP が 0" in rep.format()
