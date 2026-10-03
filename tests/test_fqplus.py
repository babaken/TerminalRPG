"""FirstQuest+（案C「主人公の正体」）のテスト。1・2 章は FirstQuest の通しプレイをそのまま流し、伏線の差分を確かめる。"""
import shutil
from pathlib import Path

import pytest

import test_chapter1
import test_chapter2
from test_chapter1 import Play
from test_play import _seed  # noqa: F401
from trpg.game import load_game
from trpg.package.check import check_package

PLUS = Path(__file__).resolve().parent.parent / "scenarios" / "FirstQuestPlus"


@pytest.fixture
def plus_dir(tmp_path) -> Path:
    d = tmp_path / "FirstQuestPlus"
    shutil.copytree(PLUS, d)
    return d


@pytest.fixture
def game(plus_dir):
    g = load_game(plus_dir)
    yield g
    g.close()


def test_package_is_valid():
    rep, m = check_package(PLUS, out=lambda s: None)
    assert rep.ok, rep.format()
    assert (m.id, m.title) == ("firstquest_plus", "FirstQuest+")


# ---------------------------------------------------------------- FirstQuest と同じ流れで遊べる
def test_chapter1_full_playthrough(game):
    test_chapter1.test_chapter1_full_playthrough(game)


@pytest.mark.parametrize("name", ["test_chapter2_kabura_to_blackrock_order", "test_chapter2_blackrock_cave",
                                  "test_chapter2_report_and_new_members"])
def test_chapter2_flow(game, name):
    getattr(test_chapter2, name)(game)


# ---------------------------------------------------------------- 1 章の伏線
def _new_game(game) -> Play:
    d = Play(game)
    d.key("ENTER")
    d.key("ENTER")
    return d


def test_chapter1_dream_and_tera(game):
    d = _new_game(game)
    talk = " ".join(d.settle())
    f = d.field
    assert "ゼノ" in talk and "p_dream_1" in f.st.flags
    d.walk_to(5, 7)                                  # 外へ → カイの誘い
    d.settle()
    d.walk_to(21, 8)                                 # 村の東の小屋
    assert f.st.map_id == "tera_hut"
    talk = " ".join(d.talk(5, 3, "up"))
    assert "大きくなったねぇ" in talk and "p_tera_1" in f.st.flags
    talk = " ".join(d.talk(5, 3, "up"))
    assert "年寄りの言うことは" in talk
    d.walk_to(4, 6)
    assert (f.st.map_id, f.st.x, f.st.y) == ("village_lito", 21, 9)


def test_chapter1_sword_voice_and_raid(game):
    d = _new_game(game)
    d.settle()
    f = d.field
    f.change_map("forest_1", 20, 3, "up")            # 祠の前
    f.pending_auto = False
    f.start_script("ch1_pull_sword")                 # 剣を抜く → 再会 → 夕食 → 夢 → 翌朝
    talk = " ".join(d.settle())
    assert "見つけた" in talk and "同じ顔をしていた" in talk
    assert "found_sword" in f.st.flags and f.st.effects.get("tint", "none") == "none"
    assert game.data.enemies["shadow_wolf"].stats["atk"] == 3      # 手加減している（FirstQuest は 7）
    f.start_script("ch1_raid")
    talk = " ".join(d.settle())
    assert "連れていこうとしてた" in talk and "魔物の仲間" in talk and "祟り" not in talk
    assert "ch1_raid_done" in f.st.flags


def test_chapter1_mother_secret(game):
    d = _new_game(game)
    d.settle()
    f = d.field
    f.start_script("ch1_farewell")
    talk = " ".join(d.settle())
    assert "話さなきゃいけないことがあるの" in talk and "p_mother_secret" in f.st.flags


# ---------------------------------------------------------------- 2 章の伏線
def _ch2(game) -> Play:
    d = test_chapter2.after_chapter1(game)            # 1 章でミアを選んだ状態
    d.field.st.chapter = 2
    for mid in game.data.maps:
        d.field.st.traps[mid] = []
    return d


def test_chapter2_rumor_and_grey(game):
    d = _ch2(game)
    f = d.field
    f.start_script("ch2_start")
    talk = " ".join(d.settle())
    assert "若い奴ばっかり" in talk and "グレイです" in talk and "興味深い" in talk
    assert "p_grey_met" in f.st.flags and f.st.quests["q_mole"] == "active"
    f.change_map("village_kabura", 14, 1, "down")
    assert f.npc_visible(f._find_npc("grey"))
    talk = " ".join(d.talk(16, 10, "up"))
    assert "届けよう" in talk
    f.start_script("ch2_mole_battle")
    talk = " ".join(d.settle())
    assert "お手並み拝見" in talk and "私にも読めません" in talk and "目をそらした" in talk
    assert not f.npc_visible(f._find_npc("grey"))    # 依頼が終わったら村からいなくなる


def test_chapter2_report_map_grey_leaves(game):
    d = _ch2(game)
    f = d.field
    f.st.flags |= {"p_grey_met", "mole_defeated"}
    f.st.items["old_map"] = 1
    f.start_script("ch2_report_map")
    talk = " ".join(d.settle())
    assert "器の帰る場所" in talk and "足早に協会を出ていった" in talk


def test_chapter2_cave_foreshadowing(game):
    d = _ch2(game)
    f = d.field
    st = f.st
    for m in st.party:
        m.hp = m.max_hp
    f.change_map("dungeon_b04", 11, 10, "down")
    talk = " ".join(d.talk(6, 13, "right"))          # 檻の残骸
    assert "小さな靴" in talk and "p_cage" in st.flags
    from trpg.world.growth import raise_to_level
    for m in st.party:
        raise_to_level(m, game.data, 8)
        m.hp, m.mp = m.max_hp, m.max_mp
    f.change_map("dungeon_b07", 12, 6, "down")
    d.walk_to(14, 7)                                 # なりそこない（踏むと戦闘）
    talk = " ".join(d.settle())
    assert "器……じゃ……ない" in talk and "p_b07_done" in st.flags
    d.walk_to(15, 7)
    d.walk_to(14, 7)                                 # 二度目は何も起きない
    assert not d.settle()
    f.change_map("dungeon_b10", 18, 2, "down")
    talk = " ".join(d.talk(5, 1, "up"))              # 壁画
    assert "赤子を抱いた魔物" in talk and "p_mural_1" in st.flags


def test_chapter2_report_grey_gone_and_chapter3_stub(game):
    d = _ch2(game)
    f = d.field
    f.st.flags |= {"p_b07_done"}
    f.start_script("ch2_report")
    talk = " ".join(d.settle())                     # 仲間選択の画面が開くところまで
    assert "人が魔物になっていた" in talk and "姿を消した" in talk and "p_grey_gone" in f.st.flags
    f2 = load_game(PLUS)
    try:
        assert "p3_start" in f2.script.labels
    finally:
        f2.close()
