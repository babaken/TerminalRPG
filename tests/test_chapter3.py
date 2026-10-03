"""3章を通しでプレイするテスト（実際の画面にキーを送る）。2章の終わりの状態から始める。"""
import pytest

from test_chapter1 import Play
from test_chapter2 import check_tile, descend, find, find_in
from test_play import _seed  # noqa: F401
from trpg.game import load_game
from trpg.world.growth import raise_to_level
from trpg.world.state import Member


@pytest.fixture
def game(sample_dir):
    g = load_game(sample_dir)
    yield g
    g.close()


def after_chapter2(game, members=("mia", "garo", "noa"), lv=11) -> Play:
    """2章を終えた直後（協会、仲間 4 人）の状態を作る。"""
    d = Play(game)
    for _ in range(4):
        d.key("ENTER")
    d.settle()
    f = d.field
    st = f.st
    gd = game.data
    st.flags |= {"ch1_done", "guild_registered", "ch2_rumor", "mole_defeated", "ch2_map_reported",
                 "ch2_found_scroll", "found_silverfang", "ch2_done", "ch2_guard_done", "ch2_ogre_done"}
    st.chapter = 2
    st.quests.update(q_mole="done", q_blackrock="done")
    for c in members:
        st.party.append(Member.from_data(gd, c))
    for m in st.party:
        raise_to_level(m, gd, lv)
        m.hp, m.mp = m.max_hp, m.max_mp
    st.hero.equip.update(weapon="rusty_sword", armor="leather_armor")
    st.items.update(adventurer_card=1, return_scroll=1, map_copy=1, herb=10, steel_sword=1)
    f.change_map("guild_bern", 15, 2, "left")
    f.pending_auto = False
    return d


def test_chapter3_deep_cave_and_defeat(game):
    d = after_chapter2(game)
    f = d.field
    st = f.st

    # ---- 3-1：ドルガンに話しかけると 3 章が始まる（「まだだ」を選ぶと始まらない）
    d.talk(17, 2, "right", choose=1)
    assert "ch3_started" not in st.flags
    talk = " ".join(d.talk(17, 2, "right", choose=0))
    assert st.chapter == 3 and "ch3_started" in st.flags and st.quests["q_blackrock_deep"] == "active"
    assert "東の壁が崩れて" in talk
    assert st.tile_override("dungeon_b11", 26, 5) == ">"

    # ---- B11F の崩れた壁 → B12F〜B15F
    f.change_map("dungeon_b11", 25, 5)
    f.pending_auto = False
    d.walk_to(26, 5)
    d.settle()
    assert st.map_id == "dungeon_b12"
    talk = check_tile(d, "W")
    assert any("……封……剣……贄……" in t for t in talk)
    descend(d)
    assert st.map_id == "dungeon_b13"
    rod = f._find_npc("rod")
    talk = d.talk(rod.x, rod.y + 1, "up")
    assert "rod_rescued" in st.flags and st.items["return_scroll"] == 1
    assert any("人を集めて" in t for t in talk) and not f.npc_visible(rod)
    descend(d)
    assert st.map_id == "dungeon_b14"
    talk = check_tile(d, "G")                                 # 大扉：剣に反応して開く
    assert any("剣と同じ紋章" in t for t in talk)
    descend(d)
    for m in st.party:                                        # 道中の戦闘で減った分を戻しておく
        m.hp, m.mp = m.max_hp, m.max_mp
    game.data.maps["dungeon_b15"].encounter = ""             # B15F は戦わずに通る（ガルザ戦を満タンで）
    d.walk_to(*find(f, ">"))                                  # 儀式の間へ（会話はこのあと読む）
    assert st.map_id == "dungeon_altar"

    # ---- 3-2：ガルザ（負けイベント）→ 医務室
    talk = " ".join(d.settle())
    assert "封剣を持つ者よ" in talk
    assert "ch3_lost" in st.flags and st.map_id == "guild_infirmary"
    assert [m.id for m in st.party] == ["hero", "garo", "noa"] and st.away["injured"].id == "mia"
    assert "ミアがユウをかばい、倒れた" in talk
    assert "ミアは……命は取り留めた" in talk
    assert "ガロ「……俺がもっと前に出ていれば」" in talk and "ノア「ピピがずっと震えてる……」" in talk
    assert "風見の神殿" in talk
    assert all(m.hp == m.max_hp for m in st.party)
    assert st.tile_override("dungeon_b14", 20, 1) == "G"     # 大扉はまた閉じた
    assert st.effects.get("tint") in (None, "none")


def test_door_stays_closed_after_defeat(game):
    d = after_chapter2(game)
    f = d.field
    st = f.st
    st.flags |= {"ch3_started", "ch3_lost"}
    f.change_map("dungeon_b14", *find_in(game, "dungeon_b14", "<"))
    f.pending_auto = False
    st.set_tile("dungeon_b14", 20, 1, "G")
    talk = check_tile(d, "G")
    assert any("固く閉ざされている" in t for t in talk) and f.tile_char(20, 1) == "G"


def after_defeat(game) -> Play:
    """ガルザに敗れて医務室で目覚めた直後の状態（ミアが一時離脱）。"""
    d = after_chapter2(game)
    f = d.field
    st = f.st
    st.chapter = 3
    st.flags |= {"ch3_started", "ch3_lost", "rod_rescued"}
    st.quests["q_blackrock_deep"] = "active"
    mia = st.member("mia")
    st.party.remove(mia)
    st.away["injured"] = mia
    st.set_tile("field_blackrock", 27, 8, ".")
    st.set_tile("field_blackrock", 29, 8, "=")
    for mid in game.data.maps:
        st.traps[mid] = []
    return d


def test_rockslide_until_defeat(game):
    d = after_chapter2(game)
    f = d.field
    f.change_map("field_blackrock", 26, 8)
    f.pending_auto = False
    assert not f.passable(27, 8)
    talk = d.talk(26, 8, "right")
    assert any("落石でふさがっている" in t for t in talk)


def test_chapter3_temple_trials_and_return(game):
    d = after_defeat(game)
    f = d.field
    st = f.st
    gd = game.data

    # ---- 洞穴前の東 → 山道（雪）→ 神殿
    f.change_map("field_blackrock", 26, 8)
    f.pending_auto = False
    d.walk_to(29, 8)
    talk = " ".join(d.settle())
    assert st.map_id == "field_mountain" and st.effects.get("snow") not in (None, "off")
    assert "古い神殿" in talk
    d.walk_to(23, 0)
    talk = " ".join(d.settle())
    assert st.map_id == "temple_kazami" and "封剣アストラ" in talk and "ch3_temple_met" in st.flags

    # ---- 勇気の間：影と一人で戦う（負けたら挑み直す）
    d.walk_to(5, 1)
    assert st.map_id == "trial_1"
    for _ in range(5):
        talk = " ".join(d.talk(9, 2, "up"))
        if "trial1_done" in st.flags:
            break
        assert "出直してこい" in talk
    assert "trial1_done" in st.flags
    assert st.hero.equip["weapon"] == "awakening_sword" and "fuukouzan" in st.hero.extra_skills
    assert "影のユウ" in talk and "封光斬" in talk
    d.walk_to(9, 7)
    assert st.map_id == "temple_kazami"

    # ---- 慈愛の間：手当てしてやる
    luk0, hp0 = st.hero.base["luk"], st.hero.max_hp
    d.walk_to(16, 1)
    d.walk_to(9, 2)
    d.settle(choose=0)
    assert "trial2_done" in st.flags and "helped_pup" in st.flags
    assert st.hero.base["luk"] == luk0 + 2 and st.hero.max_hp == hp0 + 20
    d.walk_to(9, 7)

    # ---- 絆の間：「それでも一緒に行きたい」を選ぶまで続く
    d.walk_to(27, 1)
    d.walk_to(9, 2)
    st.dir = "up"
    d.key("ENTER")
    answers = [0, 1, 2]                                       # ごめん → 一人で行く → それでも一緒に行きたい
    asked = 0
    for _ in range(100):
        d.tick(0.2)
        if f.choice is not None:
            for _ in range(answers[asked]):
                d.key("DOWN")
            d.key("ENTER")
            asked += 1
        elif f.msg.active or f.busy:
            d.key("ENTER")
        else:
            break
    assert asked == 3 and "trial3_done" in st.flags
    d.walk_to(9, 7)

    # ---- オルド → 仲間の復帰・上位スキル → 伝説 → 3 章 完
    talk = " ".join(d.talk(15, 5, "left"))                   # 司祭オルド（祭壇の上）
    assert "ミア「……待たせちゃったね」" in talk
    assert [m.id for m in st.party] == ["hero", "garo", "noa", "mia"] and st.away == {}
    assert "whirlwind" in st.member("garo").extra_skills and "flame_storm" in st.member("mia").extra_skills
    assert "beast_call" in st.member("noa").extra_skills
    assert "三柱の魔" in talk and "蝕王ヴェルム" in talk
    assert "ch3_done" in st.flags and st.effects.get("snow") in (None, "off")
    from trpg.scenes.saveload import SaveLoadScene
    assert isinstance(d.scene, SaveLoadScene)


def test_old_save_after_defeat_opens_rockslide(game):
    """医務室の場面を古い版で通ったセーブ（落石の @tile がない）でも、ロードすると東へ行ける。"""
    from trpg.scenes.title import start_field
    d = after_chapter2(game)
    st = d.field.st
    st.flags |= {"ch3_started", "ch3_lost"}
    st.tiles.pop("field_blackrock", None)
    game.saves().save(1, st)
    loaded = game.saves().load(1)
    start_field(d.app, game, loaded)
    d.settle()
    assert loaded.tile_override("field_blackrock", 27, 8) == "." and loaded.tile_override("field_blackrock", 29, 8) == "="
