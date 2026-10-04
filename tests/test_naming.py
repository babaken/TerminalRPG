"""追加要望 A-1：仲間とペットに名前を付ける（Friends.data の name_input、本文の {name.ID} {pet}）。"""
import random

import pytest

from conftest import edit
from test_chapter1 import Play
from test_play import _seed  # noqa: F401
from trpg.battle.core import Battle, Command
from trpg.data import Report
from trpg.game import load_game
from trpg.save import state_from_dict, state_to_dict
from trpg.scenes.battle import BattleScene
from trpg.scenes.facility import RecruitScene
from trpg.scenes.title import NameInputScene
from trpg.script.lint import lint_script
from trpg.script.parser import parse_script
from trpg.world.state import GameState, Member, format_text, pet_name


@pytest.fixture
def game(sample_dir):
    sco = sample_dir / "scenario.sco"
    sco.write_text(sco.read_text(encoding="utf-8") + """
*t_recruit
@recruit garo mia rina pick=1
{name.garo}「よろしく頼む」
@end

*t_add
@party add jack
{name.jack}「よろしく！」
@end
""", encoding="utf-8")
    g = load_game(sample_dir)
    yield g
    g.close()


def _start(game) -> Play:
    d = Play(game)
    for _ in range(4):
        d.key("ENTER")
    d.settle()
    return d


def _type(d, name):
    sc = d.scene
    assert isinstance(sc, NameInputScene)
    while sc.name:
        d.key("BACKSPACE")
    for ch in name:
        d.key(ch)
    d.key("ENTER")


def _recruit_garo(d):
    f = d.field
    f.start_script("t_recruit")
    d.tick(0.3)
    assert isinstance(d.scene, RecruitScene)
    d.ov_read()
    d.ov_pick("ガロ")
    d.ov_choose(0)                                   # 仲間にしますか？ → はい


def test_name_companion_on_recruit(game):
    d = _start(game)
    _recruit_garo(d)
    sc = d.scene
    assert isinstance(sc, NameInputScene) and sc.name == "ガロ"
    assert "ガロの名前を入力してください" in d.screen()
    _type(d, "ゴウ")
    msgs = d.ov_read()
    assert any("ゴウが仲間になった" in m for m in msgs)
    talk = " ".join(d.back_to_field())
    assert "ゴウ「よろしく頼む」" in talk
    st = d.field.st
    assert st.member("garo").name == "ゴウ" and "garo" in st.named
    assert format_text("{name.garo}と{name.mia}", st, game.data) == "ゴウとミア"   # ミアはまだいないので元の名前


def test_esc_keeps_default_name(game):
    d = _start(game)
    _recruit_garo(d)
    d.key("ESC")
    assert any("ガロが仲間になった" in m for m in d.ov_read())
    assert d.field.st.member("garo").name == "ガロ"


def test_party_add_asks_name_once(game):
    d = _start(game)
    f = d.field
    f.start_script("t_add")
    d.tick(0.3)
    _type(d, "ジョー")
    talk = " ".join(d.settle())
    assert "ジョー「よろしく！」" in talk
    st = f.st
    jack = st.member("jack")
    st.party.remove(jack)                             # 抜けて、もう一度加わる → もう聞かない
    f.start_script("t_add")
    d.tick(0.3)
    assert not isinstance(d.scene, NameInputScene)
    assert "jack" in st.named


def test_hero_is_not_asked_again(game):
    st = GameState.new_game(game.data, game.manifest, "アキ")
    assert "hero" in st.named


def test_names_are_saved(game):
    st = GameState.new_game(game.data, game.manifest, "アキ")
    st.party.append(Member.from_data(game.data, "garo"))
    st.party[-1].name = "ゴウ"
    st.named.add("garo")
    st.pet, st.pet_name = "slime", "ぷる"
    st2 = state_from_dict(state_to_dict(st))
    assert st2.member("garo").name == "ゴウ" and st2.named == {"hero", "garo"} and st2.pet_name == "ぷる"
    old = state_to_dict(st)
    del old["named"], old["pet_name"]
    st3 = state_from_dict(old)                         # 古いセーブ
    assert st3.named == set() and st3.pet_name == ""


# ---------------------------------------------------------------- ペット
def test_pet_name_in_battle_and_text(game):
    st = GameState.new_game(game.data, game.manifest, "アキ")
    st.pet, st.pet_name = "mole", "モグ太"
    b = Battle(game.data, st, "slime_2", rng=random.Random(0))
    assert b.pet.name == "モグ太"
    assert format_text("{pet}がいる", st, game.data) == "モグ太がいる"
    st.pet_name = ""
    assert pet_name(st, game.data) == "ハタケモグラ"
    b.tame_rate = lambda t: 1.0
    st.pet_name = "モグ太"
    out = [e[1] for e in b._tame(b.party[0], Command("tame", target=b.enemies[0])) if e[0] == "msg"]
    assert "いままでのモグ太は、野に帰っていった。" in out
    assert b.tamed and st.pet == "slime" and st.pet_name == ""


def test_name_pet_after_taming(game):
    """戦闘で手なずけたら、戦闘画面が閉じたあとに名前を付ける。"""
    d = _start(game)
    f = d.field
    st = f.st
    b = f.start_battle("slime_2")
    assert isinstance(d.scene, BattleScene)
    b.battle.tame_rate = lambda t: 1.0
    list(b.battle._tame(b.battle.party[0], Command("tame", target=b.battle.enemies[0])))
    assert b.battle.tamed and st.pet == "slime"
    b.battle.result = "win"
    d.app.pop()                                           # 戦闘画面を閉じる
    f._after_battle(b)
    assert isinstance(d.scene, NameInputScene) and d.scene.name == "スライム"
    _type(d, "ぷる")
    assert st.pet_name == "ぷる" and d.scene is f
    assert "ペット ぷる" in d.screen()


# ---------------------------------------------------------------- 検証
def test_lint_unknown_name_placeholder(game):
    rep = Report()
    sc = parse_script("*start\n{name.nobody}「やあ」\n- \n@end\n", rep)
    lint_script(sc, game.data, rep, game.package, "start")
    assert any("キャラクター「nobody」" in i.message for i in rep.errors)


@pytest.mark.parametrize("scenario", ["FirstQuest", "FirstQuestPlus"])
def test_sample_scenarios_use_name_placeholders(scenario):
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "scenarios" / scenario
    text = "\n".join(p.read_text(encoding="utf-8") for p in root.glob("*.sco"))
    body = "\n".join(l for l in text.split("\n") if not l.lstrip().startswith("#"))
    for name in ("ガロ", "ミア", "リナ", "ザラ", "ノア"):
        assert name not in body, name                     # 本文は {name.ID} で書く（名前を変えられるように）
    assert "ジャック「" not in body
