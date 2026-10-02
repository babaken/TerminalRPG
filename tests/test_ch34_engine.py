"""5-1：3・4 章に必要なエンジン機能（仲間の一時離脱と復帰・一部の仲間だけの戦闘・ターン制限・
影の敵・装備の入れ替え・スキルと能力の追加・エンディング）。"""
import random

import pytest

from test_play import Driver, _seed  # noqa: F401
from trpg.battle.core import Battle, Command
from trpg.data import Report, load_game_data
from trpg.game import load_game
from trpg.package import open_package
from trpg.save import state_from_dict, state_to_dict
from trpg.scenes.ending import EndingScene
from trpg.scenes.field import FieldScene
from trpg.scenes.title import TitleScene
from trpg.script.lint import lint_script
from trpg.script.parser import parse_script
from trpg.world.growth import skills_of
from trpg.world.state import Member, format_text

SHADOW = '''
[[enemy]]
id = "shadow_hero"
name = "影の{hero}"
aa = "aa/slime.txt"
stats = { hp = 1 }
copy = "hero"

[[group]]
id = "shadow"
members = ["shadow_hero"]
'''

SCRIPT = '''
*leave_test
@party leave #2 keep=injured
{away.injured}は動けない。
@if away.injured == mia
@flag set mia_away
@endif
@end

*return_test
@party return injured
@end

*evolve_test
@item replace rusty_sword copper_sword
@skill add hero fire
@skill add all heal
@stat hero hp +20
@stat hero luk -2
@end

*solo_test
@battle group=slime_2 members=hero turns=2 lose=*solo_lost
@flag set solo_won
@end

*solo_lost
@flag set solo_timeout
@end

*end_test
@ending text="{hero}の旅は、まだ続く"
@end
'''


@pytest.fixture
def game(sample_dir):
    (sample_dir / "Enemy.data").write_text((sample_dir / "Enemy.data").read_text(encoding="utf-8") + SHADOW,
                                           encoding="utf-8")
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
    st = d.field.st
    st.party.append(Member.from_data(game.data, "mia"))
    st.hero.equip["weapon"] = "rusty_sword"
    st.items["rusty_sword"] = 1
    return d


def run(d, label):
    d.field.start_script(label)
    return d.settle()


# ---------------------------------------------------------------- 一時離脱と復帰
def test_party_leave_and_return_keeps_member(d, game):
    st = d.field.st
    mia = st.member("mia")
    mia.lv, mia.equip["accessory"] = 7, "cat_collar"
    talk = run(d, "leave_test")
    assert st.member("mia") is None and st.away["injured"] is mia
    assert "ミアは動けない。" in " ".join(talk) and "mia_away" in st.flags
    restored = state_from_dict(state_to_dict(st))                 # セーブしても覚えている
    assert restored.away["injured"].lv == 7 and restored.away["injured"].equip["accessory"] == "cat_collar"
    run(d, "return_test")
    assert st.member("mia") is mia and st.away == {} and [m.id for m in st.party] == ["hero", "mia"]
    assert format_text("{away.injured}", st) == "" and st.lookup(("away", "injured")) == ""


# ---------------------------------------------------------------- 装備の入れ替え・スキル・能力
def test_item_replace_skill_and_stat(d, game):
    st = d.field.st
    hero = st.hero
    hp0, luk0 = hero.max_hp, hero.base["luk"]
    run(d, "evolve_test")
    assert hero.equip["weapon"] == "copper_sword"                  # 装備中のものも
    assert st.items.get("copper_sword") == 1 and "rusty_sword" not in st.items   # 袋の中のものも
    assert "fire" in skills_of(hero, game.data) and "heal" in skills_of(hero, game.data)
    assert "heal" in skills_of(st.member("mia"), game.data)
    assert hero.max_hp == hp0 + 20 and hero.base["luk"] == luk0 - 2
    restored = state_from_dict(state_to_dict(st))
    assert restored.hero.extra_skills == ["fire", "heal"]


# ---------------------------------------------------------------- 戦闘
def test_battle_members_only(game):
    from trpg.world.state import GameState
    st = GameState.new_game(game.data, game.manifest)
    st.party.append(Member.from_data(game.data, "mia"))
    st.pet = "slime"
    b = Battle(game.data, st, "slime_2", members=["hero"], rng=random.Random(0))
    assert [x.member.id for x in b.party] == ["hero"] and b.pet is None
    b2 = Battle(game.data, st, "slime_2", members=["hero", "pet"], rng=random.Random(0))
    assert b2.pet is not None


def test_turn_limit_goes_to_lose_label(d, game):
    st = d.field.st
    st.hero.base["hp"] = 999
    st.hero.hp = 999
    for e in ("slime",):
        game.data.enemies[e].stats["hp"] = 999                    # 倒せない
    d.field.start_script("solo_test")
    d.tick(1.0)
    sc = d.scene
    assert sc.battle.party[0].member.id == "hero" and len(sc.battle.party) == 1
    for _ in range(400):
        if isinstance(d.scene, FieldScene):
            break
        b = d.scene
        if b.mode == "command":
            b.cmds = {a: Command("defend") for a in b.battle.actors()}
            b._run_round()
        d.key("ENTER")
    d.settle()
    assert sc.battle.result == "timeout" and sc.battle.turn == 2
    assert "solo_timeout" in st.flags and "solo_won" not in st.flags


def test_shadow_copies_hero(game):
    from trpg.world.state import GameState
    st = GameState.new_game(game.data, game.manifest)
    st.hero.equip["weapon"] = "copper_sword"
    b = Battle(game.data, st, "shadow", rng=random.Random(0))
    sh = b.enemies[0]
    assert sh.name == "影のユウ"
    assert sh.max_hp == st.hero.max_hp and sh.stat("atk") == st.hero.stat("atk", game.data)
    assert game.data.enemies["shadow_hero"].stats["hp"] == 1      # 元のデータは変えない


# ---------------------------------------------------------------- エンディング
def test_ending_screen_then_title(d):
    d.field.start_script("end_test")
    d.tick(0.3)
    sc = d.scene
    assert isinstance(sc, EndingScene)
    d.key("ENTER")                                                # すぐには閉じない
    assert d.scene is sc
    d.tick(2.0)
    screen = d.screen()
    assert "ユウの旅は、まだ続く" in screen and "FirstQuest" in screen and "ミア Lv" in screen
    d.key("ENTER")
    d.tick(0.3)
    assert isinstance(d.scene, TitleScene)


# ---------------------------------------------------------------- 検証
def test_parse_and_lint_errors(sample_dir):
    sco = sample_dir / "scenario.sco"
    sco.write_text(sco.read_text(encoding="utf-8") + '''
*bad_cmds
@party return nobody
@party leave 2
@stat hero power +3
@stat hero hp 3
@skill add hero no_skill
@item replace herb
@battle group=slime_2 turns=0
@battle group=slime_2 members=hero,ghost
@end
''', encoding="utf-8")
    rep = Report()
    with open_package(sample_dir, rep) as pkg:
        gd = load_game_data(pkg, rep)
        sc = parse_script(sco.read_text(encoding="utf-8"), rep, "scenario.sco", loader=pkg.read_text)
        lint_script(sc, gd, rep, pkg)
    text = rep.format()
    for want in ("keep=nobody", "#2 のような", "能力は", "+20 や -5", "no_skill", "旧ID 新ID",
                 "turns は 1 以上", "ghost"):
        assert want in text, want
