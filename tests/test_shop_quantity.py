"""ショップの個数入力：道具は個数を選んで買う・売る（装備品を買うときは 1 つずつ）。"""
import pytest

from test_play import Driver, _seed  # noqa: F401
from trpg.game import load_game
from trpg.scenes.facility import ShopScene
from trpg.term import Buffer


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


def open_shop(d, shop="town_item", buy=True) -> ShopScene:
    sc = ShopScene(d.field, shop)
    d.app.push(sc)
    assert sc.choice is not None                              # 「かう / うる / やめる」
    if not buy:
        d.key("DOWN")
    d.key("ENTER")
    return sc


def pick(d, sc, name):
    rows = [r[0] for r in sc.list.rows]
    i = next(k for k, r in enumerate(rows) if name in r)
    while sc.list.index != i:
        d.key("DOWN")
    d.key("ENTER")


def screen(sc):
    buf = Buffer(100, 30)
    sc.draw(buf)
    return "\n".join("".join(c[0] for c in r) for r in buf.rows)


def answer_yes(d, sc):
    assert sc.choice is not None
    d.key("ENTER")
    for _ in range(10):                                       # 「まいどあり！」などを読む
        if not sc.msg.active or sc.choice is not None:
            break
        d.key("ENTER")


def test_buy_five_herbs(d):
    st = d.field.st
    st.gold, st.items["herb"] = 100, 1
    sc = open_shop(d)
    pick(d, sc, "やくそう")
    assert sc.mode == "qty_buy" and sc.qty == 1 and sc.qty_max == 12      # 100 G ÷ 8 G
    for _ in range(4):
        d.key("UP")
    text = screen(sc)
    assert "5 個" in text and "合計 40 G" in text and "持っている数 1" in text
    d.key("ENTER")
    assert "やくそうを 5 個、合計 40 G で買いますか" in " ".join(sc.msg.pages[sc.msg.page])
    answer_yes(d, sc)
    assert st.gold == 60 and st.items["herb"] == 6 and sc.mode == "buy"


def test_quantity_keys_and_limits(d):
    st = d.field.st
    st.gold = 1000
    st.items["herb"] = 90
    sc = open_shop(d)
    pick(d, sc, "やくそう")
    assert sc.qty_max == 9                                    # 99 個まで（持っている 90 個）
    d.key("RIGHT")
    assert sc.qty == 9                                        # ←→ は 10 ずつ（上限で止まる）
    d.key("UP")
    assert sc.qty == 1                                        # ↑で上限を超えると 1 に戻る
    d.key("DOWN")
    assert sc.qty == 9                                        # ↓で 1 より下は上限へ
    d.key("LEFT")
    assert sc.qty == 1
    d.key("ESC")                                              # やめる → 一覧に戻る
    assert sc.mode == "buy" and sc.choice is None and st.items["herb"] == 90
    st.items["herb"] = 99
    pick(d, sc, "やくそう")
    assert sc.mode == "buy" and "それ以上は持てない" in " ".join(sc.msg.pages[sc.msg.page])


def test_equipment_still_one_at_a_time(d):
    st = d.field.st
    st.gold = 500
    sc = open_shop(d, "town_weapon")
    pick(d, sc, "どうのつるぎ")
    assert sc.mode == "buy" and sc.choice is not None         # 個数は聞かず、すぐ「買いますか？」
    d.key("ENTER")
    for _ in range(10):
        if sc.choice is not None:
            break
        d.key("ENTER")
    assert sc.choice is not None                              # 「いま装備しますか？」
    assert st.items.get("copper_sword") == 1


def test_sell_several(d):
    st = d.field.st
    st.gold = 0
    st.items["herb"] = 7
    sc = open_shop(d, buy=False)
    pick(d, sc, "やくそう")
    assert sc.mode == "qty_sell" and sc.qty_max == 7
    d.key("UP")
    d.key("UP")
    d.key("ENTER")
    answer_yes(d, sc)
    price = int(8 * sc.shop.sell_rate)
    assert st.items["herb"] == 4 and st.gold == price * 3
    st.items["antidote"] = 1
    sc._open_sell()
    pick(d, sc, "どくけし")
    assert sc.mode == "sell" and sc.choice is not None        # 1 つしかなければ個数は聞かない


def test_mage_and_priest_gear(game):
    """魔法使い・僧侶向けの皮のローブとロッド（武具屋）。魔力が上がり、ほかの職業は装備できない。"""
    from trpg.world.state import Member
    gd = game.data
    assert {"rod", "leather_robe"} <= set(gd.shops["town_weapon"].goods)
    mia, rina, garo = (Member.from_data(gd, c) for c in ("mia", "rina", "garo"))
    for m in (mia, rina):
        assert m.can_equip("rod", gd) and m.can_equip("leather_robe", gd)
    assert not garo.can_equip("rod", gd) and not garo.can_equip("leather_robe", gd)
    mag0 = mia.stat("mag", gd)
    mia.equip.update(weapon="rod", armor="leather_robe")
    assert mia.stat("mag", gd) == mag0 - 2 + 10 + 4                  # ローブ（魔力 +2）から着替え


def test_upper_mage_gear_from_chapter4(game):
    """硬革のローブとマジックロッドは 4 章からの武具屋だけ。"""
    gd = game.data
    assert {"hard_leather_robe", "magic_rod"} <= set(gd.shops["town_weapon_4"].goods)
    assert not {"hard_leather_robe", "magic_rod"} & set(gd.shops["town_weapon"].goods)
    assert gd.items["magic_rod"].stats["mag"] > gd.items["rod"].stats["mag"]
    assert gd.items["hard_leather_robe"].stats["def"] > gd.items["leather_robe"].stats["def"]
