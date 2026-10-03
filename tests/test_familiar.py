"""使い魔（ノアの小鳥ピピ）：主人が戦闘に出ていれば一緒に戦い、主人の Lv で強くなる。ペットとは別枠。"""
import random

import pytest

from test_play import Driver, _seed  # noqa: F401
from trpg.battle.core import Battle, Command
from trpg.data import Report, load_game_data
from trpg.game import load_game
from trpg.package import open_package
from trpg.term import Buffer
from trpg.world.growth import raise_to_level
from trpg.world.state import GameState, Member

from conftest import edit


@pytest.fixture
def game(sample_dir):
    g = load_game(sample_dir)
    yield g
    g.close()


def state_with_noa(game, lv=10, pet=""):
    st = GameState.new_game(game.data, game.manifest)
    noa = Member.from_data(game.data, "noa")
    raise_to_level(noa, game.data, lv)
    st.party.append(noa)
    st.pet = pet
    return st


def msgs(events):
    return [v for k, v in events if k == "msg"]


def test_pipi_joins_and_grows_with_noa(game):
    gd = game.data
    st = state_with_noa(game, lv=10)
    b = Battle(gd, st, "slime_2", rng=random.Random(0))
    [pipi] = b.familiars
    assert pipi.name == "ピピ" and pipi.owner.member.id == "noa" and pipi.side == "party"
    assert pipi.max_hp == 14 + 5 * 9 and pipi.stat("agi") == 14 + 2 * 9
    assert pipi in b.allies and pipi in b.helpers and pipi not in b.party
    assert "ピピがいっしょに戦う！" in msgs(b.intro())
    assert gd.enemies["pipi"].stats["hp"] == 14                   # 元のデータは変えない
    st20 = state_with_noa(game, lv=20)
    assert Battle(gd, st20, "slime_2").familiars[0].max_hp > pipi.max_hp


def test_pipi_and_pet_together(game):
    st = state_with_noa(game, pet="mole")
    b = Battle(game.data, st, "slime_2", rng=random.Random(0))
    assert [h.name for h in b.helpers] == ["ピピ", "ハタケモグラ"]
    assert b.familiars[0].owner is not None and b.pet.owner is None


def test_no_pipi_without_noa_in_battle(game):
    st = state_with_noa(game)
    assert Battle(game.data, st, "slime_2", members=["hero"]).familiars == []
    st.party = st.party[:1]
    assert Battle(game.data, st, "slime_2").familiars == []


def test_pipi_acts_on_its_own(game):
    st = state_with_noa(game, lv=10)
    b = Battle(game.data, st, "slime_2", rng=random.Random(3))
    hero = b.party[0]
    acted = []
    for _ in range(6):
        out = msgs(b.run_round({hero: Command("defend"), b.party[1]: Command("defend")}))
        acted += [m for m in out if m.startswith("ピピ")]
        if b.result:
            break
    assert acted                                                  # つつく（攻撃）か、癒やしのさえずり


def test_screens_show_familiar(game):
    d = Driver(game)
    for _ in range(4):
        d.key("ENTER")
    d.settle()
    f = d.field
    f.st.party.append(Member.from_data(game.data, "noa"))
    f.st.pet = "slime"
    assert "使い魔 ピピ" in d.screen() and "ペット スライム" in d.screen()
    sc = f.start_battle("slime_2")
    d.tick(1.0)
    buf = Buffer(100, 30)
    sc.draw(buf)
    text = "\n".join("".join(c[0] for c in r) for r in buf.rows)
    assert "使い魔" in text and "ペット" in text and "ピピ" in text


def test_unknown_familiar_is_error(sample_dir):
    edit(sample_dir / "Friends.data", 'familiar = "pipi"', 'familiar = "dragon"')
    rep = Report()
    with open_package(sample_dir, rep) as pkg:
        load_game_data(pkg, rep)
    assert "dragon" in rep.format() and "使い魔" in rep.format()
