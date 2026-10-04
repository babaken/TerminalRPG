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


# ---------------------------------------------------------------- 3 章「器」
import test_chapter3  # noqa: E402
from test_chapter2 import check_tile, descend, find  # noqa: E402
from trpg.world.growth import raise_to_level  # noqa: E402


def _after_ch2(game, lv=11) -> Play:
    """2 章を終えた直後（1 章でミア、2 章でガロとノア）。"""
    d = test_chapter3.after_chapter2(game, members=("mia", "garo", "noa"), lv=lv)
    st = d.field.st
    st.flags.add("ch2_had_mia")
    for mid in game.data.maps:
        st.traps[mid] = []
    return d


@pytest.mark.parametrize("spare", [False, True])
def test_chapter3_cave_reveal_and_split(game, spare):
    d = _after_ch2(game)
    f = d.field
    st = f.st
    talk = " ".join(d.talk(17, 2, "right", choose=0))           # ドルガン → 3 章
    assert "器計画" in talk and "p3_started" in st.flags and st.chapter == 3
    assert st.quests["q_blackrock_deep"] == "active" and st.tile_override("dungeon_b11", 26, 5) == ">"

    f.change_map("dungeon_b11", 25, 5)
    f.pending_auto = False
    d.walk_to(26, 5)
    d.settle()
    assert st.map_id == "dungeon_b12"
    talk = " ".join(check_tile(d, "W"))                          # グレイの研究ノート
    assert "王が選んだ器でなければ" in talk and "p3_note" in st.flags
    descend(d)
    child = f._find_npc("nari_child")
    talk = " ".join(d.talk(child.x, child.y + 1, "up", choose=1 if spare else 0))
    assert "うつわ" in talk and "p3_child_met" in st.flags and not f.npc_visible(child)
    assert ("p_child_spared" in st.flags) == spare
    assert ("おなじ……におい" in talk) == spare
    descend(d)
    talk = " ".join(check_tile(d, "G"))                          # 大扉が「目を開いて」開く
    assert "目を開いた" in talk and f.tile_char(20, 1) == ">"
    talk = " ".join(check_tile(d, "W"))                          # 壁画の全体
    assert "赤子に剣を握らせて" in talk and "p_mural_2" in st.flags
    descend(d)
    for m in st.party:
        m.hp, m.mp = m.max_hp, m.max_mp
    game.data.maps["dungeon_b15"].encounter = ""
    d.walk_to(*find(f, ">"))
    assert st.map_id == "dungeon_altar" and f.map.name == "玉座の間"

    # ---- 3-2：ネイヴの告白 → 洞穴の入口で仲間がひとり離れる（2 章で加わったガロかノアから選ぶ）
    talk = " ".join(d.settle())                                  # 選択肢はどれも 1 番目
    assert "我らが王の器よ" in talk and "手の甲に、剣と同じ紋章" in talk
    assert "ミアの" not in talk
    assert "p3_revealed" in st.flags and "p3_split" in st.flags and "p3_home_open" in st.flags
    assert "頭を冷やさせてくれ" in talk                         # ガロが離れる
    assert st.away["left"].id == "garo" and [m.id for m in st.party] == ["hero", "mia", "noa"]
    assert st.map_id == "guild_bern" and "家に帰ってこい" in talk
    assert st.effects.get("rain") == "off" and st.effects.get("tint") in (None, "none")


def test_chapter3_leave_choice_lists_only_chapter2_members(game):
    d = _after_ch2(game)
    f = d.field
    st = f.st
    st.flags |= {"p3_started", "p3_revealed"}
    f.start_script("p3_split")
    for _ in range(40):
        if f.choice is not None:
            break
        d.key("ENTER")
        d.tick(0.3)
    assert f.choice is not None
    assert [o for o in f.choice.options] == ["ガロ", "ノア"]       # 1 章からのミアは出ない
    d.key("DOWN")
    d.key("ENTER")
    talk = " ".join(d.settle())
    assert "怖いんだ" in talk and st.away["left"].id == "noa"


def _after_split(game, lv=24) -> Play:
    d = _after_ch2(game, lv=lv)
    f = d.field
    st = f.st
    st.chapter = 3
    st.flags |= {"p3_started", "p3_revealed", "p3_split", "p3_home_open", "p3_note", "p3_door_open", "ch1_farewell",
                 "ch1_left_village", "ch1_raid_done", "found_sword", "ch1_forest_done", "lost_friend",
                 "ch1_invited", "ch1_raid", "ch1_family_done", "ch1_meeting_done", "got_herbs", "p_tera_1"}
    st.quests["q_blackrock_deep"] = "active"
    garo = st.member("garo")
    st.party.remove(garo)
    st.away["left"] = garo
    return d


def _until_won(d, flag, start, tries=8) -> str:
    """一人の戦い：負けたら出直して、flag が立つまで挑む。読んだ会話を返す。"""
    talk = []
    st = d.field.st
    for _ in range(tries):
        try:
            talk += start()
        except AssertionError as e:                            # Play.settle は負けると止まる
            assert "戦闘に負けた" in str(e)
            talk += d.settle()
            assert any("もう一度来よう" in t for t in talk)
        if flag in st.flags:
            return " ".join(talk)
    raise AssertionError(f"{flag} が立たない")


def test_chapter3_home_tera_memories_and_return(game):
    d = _after_split(game)
    f = d.field
    st = f.st
    # ---- 街道を北へ → 村 → 母の告白
    f.change_map("field_road", 15, 2, "up")
    f.pending_auto = False
    d.walk_to(15, 0)
    talk = " ".join(d.settle())
    assert "戸を閉めていく" in talk and "テラおばあさんが、森で赤ちゃんを拾ってきた" in talk
    assert "p_family_accept" in st.flags and st.map_id == "house_hero"
    talk = " ".join(d.talk(8, 3, "up"))                          # 母
    assert "帰る場所は、ここよ" in talk

    # ---- テラ：心の鍵剣
    d.walk_to(5, 7)
    d.walk_to(21, 8)
    assert st.map_id == "tera_hut"
    talk = " ".join(d.talk(5, 3, "up"))
    assert "入れ物がいっぱいなら" in talk and "p3_tera_done" in st.flags
    assert st.hero.equip["weapon"] == "heart_key_sword" and "kokoro_tozashi" in st.hero.extra_skills
    assert "心の鍵剣" in talk

    # ---- 記憶の場所：森の祠（影の自分）
    d.walk_to(4, 6)
    d.walk_to(15, 0)
    assert st.map_id == "forest_1"
    d.settle()
    hp0 = st.hero.max_hp
    talk = _until_won(d, "p3_mem1", lambda: d.talk(20, 2, "up"))  # 影の自分（同じ強さ。負けたら出直す）
    assert "秘密基地" in talk and st.hero.max_hp == hp0 + 20

    # ---- 村の丘（父と星）
    d.walk_to(15, 15)
    assert st.map_id == "village_lito"
    def hill():
        d.walk_to(27, 2)
        return d.walk_to(28, 2) or d.settle()
    talk = _until_won(d, "p3_mem2", hill)
    assert "北の星" in talk and "hoshiyomi" in st.hero.extra_skills

    # ---- ベルンの協会（最後に回ると、そのまま仲間が戻ってくる → 3 章の完）
    f.change_map("guild_bern", 3, 5, "down")
    f.pending_auto = False

    def guild():
        f.st.dir = "down"
        d.key("ENTER")
        return d.settle()
    talk = _until_won(d, "p3_mem3", guild)
    from trpg.scenes.saveload import SaveLoadScene
    assert isinstance(d.scene, SaveLoadScene)                  # 3 章の完のセーブ
    d.key("ESC")
    talk += " ".join(d.back_to_field())
    assert "p3_returned" in st.flags
    assert "お前の前に立つと決めたのは俺だ" in talk
    assert [m.id for m in st.party] == ["hero", "mia", "noa", "garo"] and not st.away
    assert "whirlwind" in st.member("garo").extra_skills and "flame_storm" in st.member("mia").extra_skills
    assert "虚ろの王ゼノ" in talk and "p3_done" in st.flags


def test_chapter3_memory_lost_can_retry(game):
    d = _after_split(game, lv=12)
    f = d.field
    st = f.st
    st.flags |= {"p_family_accept", "p3_tera_done"}
    f.start_script("p3_mem_lost")
    talk = " ".join(d.settle())
    assert "もう一度来よう" in talk and "p3_mem1" not in st.flags
    f.change_map("forest_1", 20, 2, "up")
    f.pending_auto = False
    ev = [e for e in f.map.events if e.label == "p3_mem_forest"]
    assert ev and f._cond(ev[0].when)                             # まだ挑める


def test_return_to_guild_after_other_order(game):
    """協会を先に回ったときは、残りを巡ってから協会に入ると仲間が戻る。"""
    d = _after_split(game)
    f = d.field
    st = f.st
    st.flags |= {"p_family_accept", "p3_tera_done", "p3_mem1", "p3_mem2", "p3_mem3"}
    f.change_map("town_bern", 7, 8, "up")
    f.pending_auto = False
    d.walk_to(7, 7)
    assert st.map_id == "guild_bern"
    talk = " ".join(d.settle())
    assert "協会の入口に立っていた" in talk and "p3_done" in st.flags


# ---------------------------------------------------------------- 4 章「終わりの始まり」
from trpg.scenes.ending import EndingScene  # noqa: E402
from trpg.scenes.title import TitleScene  # noqa: E402


def _after_ch3(game, spared=False, lv=24) -> Play:
    d = _after_split(game, lv=lv)
    f = d.field
    st = f.st
    st.party.append(st.away.pop("left"))
    st.flags |= {"p_family_accept", "p3_tera_done", "p3_mem1", "p3_mem2", "p3_mem3", "p3_returned", "p3_done",
                 "p3_child_met"} | ({"p_child_spared"} if spared else set())
    st.hero.equip["weapon"] = "heart_key_sword"
    st.hero.extra_skills += ["kokoro_tozashi", "hoshiyomi"]
    st.items.pop("rusty_sword", None)
    st.set_tile("dungeon_b14", 20, 1, ">")
    st.set_tile("dungeon_b11", 26, 5, ">")
    for m in st.party:
        m.hp, m.mp = m.max_hp, m.max_mp
        m.fill_sp(game.data)
    st.items.update(potion=10)
    f.change_map("guild_bern", 15, 2, "left")
    f.pending_auto = False
    return d


@pytest.mark.parametrize("spared", [False, True])
def test_chapter4_to_ending(game, spared):
    d = _after_ch3(game, spared)
    f = d.field
    st = f.st
    talk = " ".join(d.talk(17, 2, "right", choose=0))           # ドルガン → 4 章
    assert st.chapter == 4 and "p4_started" in st.flags and st.items.get("elixir") == 3
    talk = " ".join(d.talk(17, 2, "right"))
    assert "一番奥" in talk

    # ---- 玉座の間 → グレイとネイヴ → 虚ろの殻 → 精神世界 → 剣 → ゼノ 2 形態 → 黒い羽根 → 協会
    f.change_map("dungeon_altar", 14, 14, "up")
    talk = " ".join(d.settle())
    assert "余計なものを連れて" in talk
    assert ("おにいちゃんを……いじめるな" in talk) == spared
    assert "余は、虚ろの王ゼノ" in talk and "小さな村だ" in talk
    assert "すげー冒険者になって帰ってこい" in talk and "ピピも、僕も" in talk and "ガロ「お前の前に立つのは俺だ" in talk
    assert "ユウの剣を手に入れた" in talk and st.hero.equip["weapon"] == "own_sword"
    assert "michiru_hikari" in st.hero.extra_skills
    assert "すべて道連れに" in talk and "器は、お前だけでは" in talk
    assert st.items.get("black_feather") == 1 and "p4_done" in st.flags
    assert st.map_id == "guild_bern" and "おかえり、ユウ" in talk
    assert st.effects.get("tint") in (None, "none")
    assert game.data.items["own_sword"].name == "ユウの剣"

    # ---- リト村へ → 出迎え → 丘 → エンディング
    f.change_map("field_road", 15, 2, "up")
    f.pending_auto = False
    d.walk_to(15, 0)
    talk = " ".join(d.settle())
    assert "この村の子じゃ" in talk and "p4_home" in st.flags
    assert "紋章は、もう消えていた" in talk and "別の「器」" in talk
    for _ in range(200):
        if isinstance(d.scene, EndingScene):
            break
        d.key("ENTER")
        d.tick(0.2)
    assert isinstance(d.scene, EndingScene)
    d.tick(2.0)
    assert "ユウのまま、明日を生きていく" in d.screen()
    d.key("ENTER")
    d.tick(0.3)
    assert isinstance(d.scene, TitleScene)


def test_michiru_hikari_cures_forget(game):
    import random
    from trpg.battle.core import Battle, Command
    d = _after_ch3(game)
    st = d.field.st
    st.hero.extra_skills.append("michiru_hikari")
    b = Battle(game.data, st, "zeno_2", escape=False, rng=random.Random(0))
    list(b.intro())
    mia = next(x for x in b.party if x.member.id == "mia")
    mia.status["forget"] = 3
    hero = b.party[0]
    events = list(b._act(hero, Command("skill", skill="michiru_hikari", target="all")))
    assert "forget" not in mia.status
    assert any(e[0] == "msg" and "記憶喪失が治った" in e[1] for e in events)


def test_ending_villagers_appear_after_return(game):
    d = _after_ch3(game)
    f = d.field
    st = f.st
    st.flags |= {"p4_started", "p4_naive_done", "p4_done", "p4_home"}
    f.change_map("village_lito", 15, 15, "up")
    f.pending_auto = False
    assert f.npc_visible(f._find_npc("home_mother"))
    talk = " ".join(d.talk(14, 15, "up"))
    assert "うれしそう" in talk


# ---------------------------------------------------------------- 森のカイ（1 章のあとに森へ戻っても出ない）
@pytest.mark.parametrize("scenario", ["FirstQuest", "FirstQuestPlus"])
def test_forest_kai_gone_after_chapter1(tmp_path, scenario):
    src = PLUS.parent / scenario
    shutil.copytree(src, tmp_path / scenario)
    g = load_game(tmp_path / scenario)
    try:
        d = _new_game(g)
        d.settle()
        f = d.field
        f.change_map("forest_1", 20, 2, "up")
        f.pending_auto = False
        f.start_script("ch1_pull_sword")              # 剣 → 再会（カイが現れる）→ 夕食
        d.settle()
        st = f.st
        assert st.npc("forest_1", "kai_forest").get("hidden") is True
        st.npc("forest_1", "kai").update(hidden=False)   # 古い版のセーブに残っている「表示」の命令
        f.change_map("forest_1", 15, 14, "up")
        f.pending_auto = False
        assert not f.npc_visible(f._find_npc("kai_forest"))
        assert all(n.id != "kai" for n in f.map.npcs)
    finally:
        g.close()


def test_kai_greets_on_homecoming_and_waits_in_village(game):
    d = _after_split(game)
    f = d.field
    st = f.st
    f.change_map("field_road", 15, 2, "up")
    f.pending_auto = False
    d.walk_to(15, 0)
    talk = " ".join(d.settle())
    assert "お前はお前だ" in talk and talk.index("お前はお前だ") < talk.index("家の前で、母が待っていた")
    d.walk_to(5, 7)
    assert st.map_id == "village_lito"
    assert f.npc_visible(f._find_npc("kai_p3"))
    talk = " ".join(d.talk(8, 14, "up"))
    assert "テラばあちゃん" in talk
    st.flags.add("p3_tera_done")
    talk = " ".join(d.talk(8, 14, "up"))
    assert "秘密基地" in talk
