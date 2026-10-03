"""4章を通しでプレイするテスト（実際の画面にキーを送る）。3章の終わりの状態から、エンディングまで。"""
import pytest

from test_chapter2 import find
from test_chapter3 import after_chapter2
from test_play import _seed  # noqa: F401
from trpg.game import load_game
from trpg.scenes.ending import EndingScene
from trpg.scenes.field import FieldScene
from trpg.scenes.title import TitleScene
from trpg.world.growth import raise_to_level


@pytest.fixture
def game(sample_dir):
    g = load_game(sample_dir)
    yield g
    g.close()


def after_chapter3(game):
    d = after_chapter2(game, lv=25)
    st = d.field.st
    gd = game.data
    st.chapter = 3
    st.flags |= {"ch1_invited", "ch1_forest_done", "ch1_raid", "ch1_raid_done", "ch1_farewell",   # 1 章の村の出来事
                 "ch3_started", "ch3_lost", "ch3_temple_met", "trial1_done", "trial2_done", "trial3_done",
                 "ch3_done", "rod_rescued"}
    st.quests["q_blackrock_deep"] = "active"
    st.hero.equip["weapon"] = "awakening_sword"
    st.hero.extra_skills.append("fuukouzan")
    for m in st.party:
        raise_to_level(m, gd, 25)
        m.hp, m.mp = m.max_hp, m.max_mp
        m.fill_sp(gd)
    st.items["herb"] = 20
    for mid in gd.maps:
        st.traps[mid] = []
    return d


def test_chapter4_to_ending(game):
    d = after_chapter3(game)
    f = d.field
    st = f.st

    # ---- 4-1：ドルガン → 4 章
    talk = " ".join(d.talk(17, 2, "right", choose=0))
    assert st.chapter == 4 and "ch4_started" in st.flags and st.items.get("elixir") == 3
    assert "蝕王ヴェルム" in talk and "ランク B" in talk

    # ---- B14F の大扉はまた開く → 儀式の間
    from test_chapter2 import check_tile, find_in
    f.change_map("dungeon_b14", *find_in(game, "dungeon_b14", "<"))
    f.pending_auto = False
    st.set_tile("dungeon_b14", 20, 1, "G")
    talk = check_tile(d, "G")
    assert any("扉がひとりでに開いた" in t for t in talk)
    f.change_map("dungeon_altar", 14, 14, "up")
    talk = " ".join(d.settle())

    # ---- 4-2：ガルザ → ヴェルム不完全体 → 剣の覚醒 → 真体 → 4-3
    assert "懲りずに来たか" in talk and "長い眠りであった" in talk
    assert "封剣アストラが目覚めた" in talk and "嵐王と渇王" in talk
    assert st.hero.equip["weapon"] == "astra" and "seal_light" in st.hero.extra_skills
    assert "ch4_done" in st.flags and st.quests["q_blackrock_deep"] == "done"
    assert st.effects.get("tint") in (None, "none")

    # ---- 4-4：協会 → カイ
    assert st.map_id == "guild_bern" and "ch4_kai" in st.flags
    assert "封剣の勇者" in talk

    # ---- リト村へ（街道の北が開いている）
    f.change_map("field_road", 15, 1)
    f.pending_auto = False
    d.walk_to(15, 0)
    talk = " ".join(d.settle())
    assert "おにいちゃーーん" in talk and "ch4_home" in st.flags
    assert "流れ星" in talk and "始まったばかり" in talk
    for _ in range(200):                                     # スタッフロール・エンディング画面
        if isinstance(d.scene, EndingScene):
            break
        d.key("ENTER")
        d.tick(0.2)
    assert isinstance(d.scene, EndingScene)
    d.tick(2.0)
    assert "ユウの冒険は、まだ始まったばかり" in d.screen()
    d.key("ENTER")
    d.tick(0.3)
    assert isinstance(d.scene, TitleScene)


def test_road_to_village_still_closed_before_kai(game):
    d = after_chapter3(game)
    f = d.field
    f.change_map("field_road", 15, 1)
    f.pending_auto = False
    d.walk_to(15, 0)
    talk = d.settle()
    assert any("今は戻れない" in t for t in talk) and f.st.map_id == "field_road"
