"""見えない罠：初めて入った階にランダムに置き、踏むと作動して見えるようになる。"""
import random

import pytest

from test_play import Driver, _seed  # noqa: F401
from trpg.data import Report, load_game_data
from trpg.game import load_game
from trpg.package import open_package
from trpg.save import state_from_dict, state_to_dict
from trpg.world import traps as T
from trpg.world.state import GameState, Member

from conftest import edit


@pytest.fixture
def game(sample_dir):
    g = load_game(sample_dir)
    yield g
    g.close()


def new_state(game):
    st = GameState.new_game(game.data, game.manifest)
    st.party.append(Member.from_data(game.data, "mia"))
    return st


@pytest.mark.parametrize("seed", range(5))
def test_counts_and_places(game, seed):
    gd = game.data
    st = new_state(game)
    rng = random.Random(seed)
    for k in range(1, 16):
        mid = f"dungeon_b{k:02}" if k <= 11 else f"dungeon_b{k}"
        m = gd.maps[mid]
        traps = T.generate(st, gd, m, rng)
        lo, hi = (1, 1) if k <= 5 else ((2, 3) if k <= 11 else (4, 5))
        assert lo <= len(traps) <= hi, (mid, len(traps))
        blocked = T._blocked(gd, m)
        ts = gd.tilesets[m.tileset]
        for x, y, kind, shown in traps:
            assert kind in gd.traps and not shown
            assert ts.tiles[m.rows[y][x]].passable and (x, y) not in blocked
        assert len({(t[0], t[1]) for t in traps}) == len(traps)
    assert T.generate(st, gd, gd.maps["town_bern"], rng) == [] and "town_bern" not in st.traps


def test_generated_once_and_saved(game):
    gd = game.data
    st = new_state(game)
    first = [list(t) for t in T.generate(st, gd, gd.maps["dungeon_b07"], random.Random(1))]
    assert T.generate(st, gd, gd.maps["dungeon_b07"], random.Random(2)) == first     # 2 回目は置き直さない
    assert state_from_dict(state_to_dict(st)).traps == st.traps


def test_trigger_effects(game):
    gd = game.data
    st = new_state(game)
    rng = random.Random(0)
    hero, mia = st.party
    trap = [1, 1, "poison_needle", False]
    msgs = T.trigger(st, gd, trap, rng)
    assert trap[3] is True and "毒の針" in msgs[0]
    hit = hero if "poison" in hero.status else mia
    assert "poison" in hit.status and hit.hp < hit.max_hp
    for m in st.party:
        m.hp = m.max_hp
    msgs = T.trigger(st, gd, [1, 1, "bomb", False], rng)
    assert all(m.hp < m.max_hp for m in st.party) and "爆発" in msgs[0]
    for m in st.party:
        m.hp = 1
    T.trigger(st, gd, [1, 1, "arrow", False], rng)
    assert all(m.hp == 1 for m in st.party)                  # 罠では HP は 1 より下がらない


def test_step_on_trap_in_field(game):
    d = Driver(game)
    for _ in range(4):
        d.key("ENTER")
    d.settle()
    f = d.field
    st = f.st
    f.change_map("dungeon_b01", 4, 10)
    f.pending_auto = False
    st.traps["dungeon_b01"] = [[5, 10, "arrow", False]]       # 右隣に罠を置き直す
    f.enc_left = 999
    n0 = d.screen().count("矢")                               # 操作説明の「矢印」の分
    hp0 = st.hero.hp
    d.key("RIGHT")
    d.tick(0.3)
    assert (st.x, st.y) == (5, 10) and f.msg.active
    assert "壁から矢が飛んできた" in " ".join(f.msg.pages[0])
    assert st.hero.hp < hp0 and st.traps["dungeon_b01"][0][3] is True
    while f.msg.active:
        d.key("ENTER")
    d.key("LEFT")
    d.tick(0.5)
    assert d.screen().count("矢") == n0 + 1                   # 罠の「矢」が見えるようになった


def test_trap_data_checks(sample_dir):
    m = sample_dir / "Map.data"
    edit(m, 'status = "poison"\nmessage = "足元から毒の針', 'status = "sleep"\nmessage = "足元から毒の針')
    edit(m, 'glyph = "爆"', 'glyph = "B"')
    edit(m, 'id = "dungeon_b02"\ntraps = [1, 1]', 'id = "dungeon_b02"\ntraps = [3, 1]\ntrap_kinds = ["pitfall"]')
    rep = Report()
    with open_package(sample_dir, rep) as pkg:
        load_game_data(pkg, rep)
    text = rep.format()
    assert "sleep" in text and "表示幅が 1" in text and "[最小, 最大]" in text and "pitfall" in text
