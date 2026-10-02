"""2章を通しでプレイするテスト（実際の画面にキーを送る）。1章の終わりの状態から始める。"""
import pytest

from test_chapter1 import Play
from test_play import _seed  # noqa: F401
from trpg.game import load_game
from trpg.scenes.field import FieldScene
from trpg.world.growth import raise_to_level
from trpg.world.state import Member


@pytest.fixture
def game(sample_dir):
    g = load_game(sample_dir)
    yield g
    g.close()


def after_chapter1(game) -> Play:
    """1章を終えた直後（協会で仲間を選んだところ）の状態を作る。"""
    d = Play(game)
    for _ in range(4):
        d.key("ENTER")
    d.settle()
    f = d.field
    st = f.st
    gd = game.data
    st.flags |= {"ch1_done", "guild_registered", "ch1_gate_talked", "ch1_know_guild", "ch1_left_village"}
    st.chapter = 1
    st.party.append(Member.from_data(gd, "mia"))
    for m in st.party:
        raise_to_level(m, gd, 4)
        m.hp, m.mp = m.max_hp, m.max_mp
    st.hero.equip.update(weapon="rusty_sword", armor="traveler_clothes")
    st.items["adventurer_card"] = 1
    st.items["herb"] = 3
    st.gold = 120
    f.change_map("guild_bern", 10, 4, "up")
    f.pending_auto = False
    return d


def test_chapter2_kabura_to_blackrock_order(game):
    d = after_chapter1(game)
    f = d.field
    st = f.st

    # ---- 2-1 噂 → カブラ村の依頼
    f.start_script("ch2_start")
    talk = " ".join(d.settle())
    assert st.chapter == 2 and "ch2_rumor" in st.flags
    assert "銀の牙" in talk and "ミア「……物騒な話ね」" in talk
    assert st.quests["q_mole"] == "active"

    talk = d.talk(10, 4, "up")                     # セラ：カブラ村は南門
    assert any("南門" in t for t in talk)
    d.ov_read()
    d.ov_choose(3)                                  # 協会画面：やめる
    d.ov_read()
    d.back_to_field()

    # ---- ベルンの南門 → カブラ村
    d.walk_to(10, 9)
    assert st.map_id == "town_bern"
    d.walk_to(20, 23)
    assert st.map_id == "village_kabura" and (st.x, st.y) == (14, 1)

    d.walk_to(19, 17)                               # 先に畑へ行っても、話を聞くまでは何も起きない
    assert st.map_id == "field_kabura"
    d.settle()
    assert "mole_defeated" not in st.flags
    d.walk_to(19, 0)
    assert st.map_id == "village_kabura"

    talk = d.talk(6, 5, "up")                       # 村長の妻
    assert "ch2_kabura_talked" in st.flags and any("南の畑" in t for t in talk)

    # ---- 畑：ドリルモール → 地図
    for m in st.party:
        m.hp, m.mp = m.max_hp, m.max_mp
    d.walk_to(19, 17)
    talk = " ".join(d.settle())
    assert "巨大なモグラ" in talk and "古びた地図" in talk
    assert "mole_defeated" in st.flags and st.items.get("old_map") == 1
    assert st.quests["q_mole"] == "active"          # 報告はまだ

    # ---- 協会に報告 → 指名依頼
    d.walk_to(19, 0)
    d.walk_to(14, 0)
    assert st.map_id == "town_bern"
    d.walk_to(7, 7)
    assert st.map_id == "guild_bern"
    gold0 = st.gold
    d.talk(10, 4, "up")
    d.ov_read()
    d.ov_choose(1)                                  # 依頼を報告する
    d.ov_pick("カブラ村の畑荒らし")
    d.ov_read()
    d.ov_choose(3)                                  # やめる
    d.ov_read()
    talk = " ".join(d.back_to_field())
    assert isinstance(d.scene, FieldScene)
    assert st.quests["q_mole"] == "done" and st.gold == gold0 + 200
    assert "黒岩の洞穴" in talk and "ランク D" in talk
    assert st.quests["q_blackrock"] == "active" and "ch2_map_reported" in st.flags
    assert "old_map" not in st.items and st.items.get("map_copy") == 1


def test_mole_battle_needs_quest(game):
    d = after_chapter1(game)
    f = d.field
    st = f.st
    st.flags.add("ch2_kabura_talked")
    f.change_map("field_kabura", 19, 1)
    d.settle()
    assert "mole_defeated" not in st.flags            # 依頼を受けていなければ出ない


def find(f, ch):
    return next((x, y) for y, r in enumerate(f.map.rows) for x, c in enumerate(r) if c == ch)


def check_tile(d, ch):
    """ch のタイル（宝箱など）の正面に立って調べ、会話を読む。"""
    f = d.field
    x, y = find(f, ch)
    for dx, dy, face in ((0, 1, "up"), (0, -1, "down"), (1, 0, "left"), (-1, 0, "right")):
        if f.passable(x + dx, y + dy):
            return d.talk(x + dx, y + dy, face)
    raise AssertionError("近づけない")


def descend(d):
    """下り階段まで歩く（ワープで次の階へ）。"""
    f = d.field
    before = f.st.map_id
    d.walk_to(*find(f, ">"))
    d.settle()
    assert f.st.map_id != before


def test_chapter2_blackrock_cave(game):
    d = after_chapter1(game)
    f = d.field
    st = f.st
    gd = game.data
    st.chapter = 2
    st.flags |= {"ch2_rumor", "mole_defeated", "ch2_map_reported", "ch2_kabura_talked"}
    st.quests.update(q_mole="done", q_blackrock="active")
    st.items["map_copy"] = 1
    st.items["herb"] = 8
    for m in st.party:
        raise_to_level(m, gd, 8)
        m.hp, m.mp = m.max_hp, m.max_mp

    # ---- 東門 → 洞穴前 → 見張り
    d.walk_to(10, 9)
    d.walk_to(39, 11)
    assert st.map_id == "field_blackrock"
    talk = " ".join(d.settle())
    assert "見張り" in talk
    d.walk_to(14, 4)                                          # 見張りの前で戦闘（会話は歩く途中で読み進める）
    d.settle()
    assert "ch2_guard_done" in st.flags
    assert not f.npc_visible(f._find_npc("goblin_cap"))
    d.walk_to(14, 1)
    assert st.map_id == "dungeon_b01"
    talk = " ".join(d.settle())
    assert "真っ暗" in talk and f.map.dark and f.banner == "黒岩の洞穴 B1F"

    # ---- B1F〜B11F
    check_tile(d, "P")                                         # 冒険者の荷物
    assert f.tile_char(*next((x, y) for y, r in enumerate(f.map.rows) for x, c in enumerate(r) if c == "P")) == "_"
    descend(d)                                                 # B2F
    descend(d)                                                 # B3F
    talk = check_tile(d, "B")
    assert st.items.get("steel_sword") == 1 and any("鋼の剣" in t for t in talk)
    descend(d)
    descend(d)                                                 # B5F
    st.party[0].hp = 1
    check_tile(d, "O")
    assert st.party[0].hp == st.party[0].max_hp
    descend(d)                                                 # B6F
    check_tile(d, "P")
    assert "found_silverfang" in st.flags and st.items.get("silverfang_emblem") == 1
    descend(d)
    descend(d)                                                 # B8F：オーガ
    assert st.map_id == "dungeon_b08"
    d.walk_to(*find(f, ">"))
    d.settle()
    assert "ch2_ogre_done" in st.flags
    if st.map_id == "dungeon_b08":                             # オーガに止められたら、もう一度階段へ
        descend(d)
    descend(d)                                                 # B10F
    talk = check_tile(d, "M")
    assert any("魔法陣" in t for t in talk)
    descend(d)                                                 # B11F
    assert st.map_id == "dungeon_b11" and ">" not in "".join(f.map.rows)

    # ---- 帰還の巻物 → 協会へ
    talk = check_tile(d, "B")
    j = " ".join(talk)
    assert "帰還の巻物" in j and "ch2_found_scroll" in st.flags
    assert st.map_id == "guild_bern" and st.items.get("return_scroll") == 1
    from trpg.world import quests as Q
    assert Q.goal_met(st, gd, gd.quests["q_blackrock"])      # 報告できる状態


def test_return_scroll_only_in_dungeon(game):
    d = after_chapter1(game)
    f = d.field
    st = f.st
    st.items["return_scroll"] = 1
    f.start_script("use_return_scroll")
    talk = " ".join(d.settle())
    assert "ここでは使えない" in talk and st.map_id == "guild_bern"
    f.change_map("dungeon_b03", *find_in(game, "dungeon_b03", "<"))
    f.pending_auto = False
    f.start_script("use_return_scroll")
    d.settle()
    assert (st.map_id, st.x, st.y) == ("town_bern", 7, 8) and st.items["return_scroll"] == 1


def find_in(game, mid, ch):
    rows = game.data.maps[mid].rows
    return next((x, y) for y, r in enumerate(rows) for x, c in enumerate(r) if c == ch)
