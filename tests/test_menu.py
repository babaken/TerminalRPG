"""フィールドメニュー（どうぐ・スキル・そうび・つよさ・いらい・システム）のテスト。"""
import pytest

from test_play import Driver, _seed  # noqa: F401
from trpg.game import load_game
from trpg.scenes.field import FieldScene
from trpg.scenes.menu import TOP, MenuScene
from trpg.world.state import Member


@pytest.fixture
def game(sample_dir):
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


def menu(d) -> MenuScene:
    if not isinstance(d.scene, MenuScene):
        d.key("ESC")
    assert isinstance(d.scene, MenuScene)
    return d.scene


def top(d, name):
    m = menu(d)
    while len(m.views) > 1:
        d.key("ESC")
    while TOP[m.views[0].list.index] != name:
        d.key("DOWN")
    d.key("ENTER")
    return m


def pick(d, text):
    m = d.scene
    v = m.views[-1]
    idx = next(i for i, r in enumerate(v.list.rows) if text in r[0])
    while v.list.index != idx:
        d.key("DOWN")
    d.key("ENTER")


def read_msgs(d):
    m = d.scene
    out = []
    while isinstance(m, MenuScene) and m.msg.active and m.choice is None:
        out.append(" ".join(m.msg.pages[m.msg.page]))
        d.key("ENTER")
    return out


def choose(d, i):
    for _ in range(i):
        d.key("DOWN")
    d.key("ENTER")


def test_open_and_close(d):
    assert isinstance(d.scene, FieldScene)
    d.key("ESC")
    assert isinstance(d.scene, MenuScene)
    assert "パーティ" in d.screen() and "ユウ" in d.screen()
    d.key("ESC")
    assert isinstance(d.scene, FieldScene)


def test_use_herb_on_hurt_member(d):
    st = d.field.st
    st.add_item("herb", 2)
    st.hero.hp = 5
    top(d, "どうぐ")
    pick(d, "やくそう")
    choose(d, 0)                         # つかう
    pick(d, "ユウ")
    msgs = read_msgs(d)
    assert any("回復した" in m for m in msgs)
    assert st.hero.hp == min(st.hero.max_hp, 35) and st.items["herb"] == 1


def test_herb_on_full_hp_is_not_consumed(d):
    st = d.field.st
    st.add_item("herb")
    top(d, "どうぐ")
    pick(d, "やくそう")
    choose(d, 0)
    pick(d, "ユウ")
    msgs = read_msgs(d)
    assert any("満タン" in m for m in msgs) and st.items["herb"] == 1


def test_antidote_cures_poison(d):
    st = d.field.st
    st.add_item("antidote")
    st.hero.status = ["poison"]
    top(d, "どうぐ")
    pick(d, "どくけしそう")
    choose(d, 0)
    pick(d, "ユウ")
    assert any("どくが治った" in m for m in read_msgs(d))
    assert st.hero.status == [] and "antidote" not in st.items


def test_discard_and_key_item(d):
    st = d.field.st
    st.add_item("bread")
    st.add_item("adventurer_card")
    top(d, "どうぐ")
    pick(d, "やきたてパン")
    choose(d, 1)                         # すてる
    choose(d, 0)                         # はい
    read_msgs(d)
    assert "bread" not in st.items
    pick(d, "冒険者証")
    choose(d, 1)
    assert any("とんでもない" in m for m in read_msgs(d))
    assert st.items["adventurer_card"] == 1


def test_script_item_closes_menu_and_runs_label(d):
    st = d.field.st
    st.add_item("return_scroll")
    top(d, "どうぐ")
    pick(d, "帰還の巻物")
    choose(d, 0)
    assert isinstance(d.scene, FieldScene)
    d.tick(0.2)
    assert d.field.pending_labels == [] and d.field.error is None   # ラベルが実行された
    assert st.items["return_scroll"] == 1                            # だいじなもの（消費しない）


def test_equip_change_and_unequip(d, game):
    st = d.field.st
    st.add_item("copper_sword")
    st.hero.equip["weapon"] = "rusty_sword"
    top(d, "そうび")
    pick(d, "ユウ")
    pick(d, "武器")
    assert "攻撃  13 →  18" in d.screen()
    pick(d, "どうのつるぎ")
    read_msgs(d)
    assert st.hero.equip["weapon"] == "copper_sword" and st.items["rusty_sword"] == 1
    pick(d, "武器")
    pick(d, "はずす")
    read_msgs(d)
    assert "weapon" not in st.hero.equip and st.items["copper_sword"] == 1


def test_cannot_equip_other_jobs_gear(d, game):
    st = d.field.st
    st.party.append(Member.from_data(game.data, "mia"))
    st.add_item("copper_sword")
    top(d, "そうび")
    pick(d, "ミア")
    pick(d, "武器")
    assert any("装備できるものを持っていない" in m for m in read_msgs(d))


def test_status_view(d):
    top(d, "つよさ")
    s = d.screen()
    assert "ユウのつよさ" in s and "経験値" in s and "攻撃" in s
    d.key("ENTER")
    assert d.scene.status_member is None


def test_heal_skill(d, game):
    st = d.field.st
    st.party.append(Member.from_data(game.data, "rina"))
    st.hero.hp = 3
    top(d, "スキル")
    pick(d, "リナ")
    pick(d, "ヒール")
    pick(d, "ユウ")
    assert any("回復した" in m for m in read_msgs(d))
    assert st.hero.hp > 3 and st.member("rina").mp == st.member("rina").max_mp - 3


def test_quest_list(d):
    st = d.field.st
    st.quests["q_herb"] = "active"
    st.add_item("herb", 3)
    top(d, "いらい")
    s = d.screen()
    assert "やくそう集め" in s and "達成！" in s and "協会に報告しよう" in s
