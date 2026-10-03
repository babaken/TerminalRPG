"""FirstQuest+ のために足したエンジン機能（M8 8-1）：条件つきの選択肢、アイテム名の {hero}。"""
import pytest

from test_menu import d, game, menu, top  # noqa: F401
from test_play import Driver, _seed  # noqa: F401
from test_script import FakeHost, parse
from trpg.game import load_game
from trpg.script.vm import VM, ChoiceReq, MessageReq, ScriptError
from trpg.world.items import personalize
from trpg.world.state import GameState

SCRIPT = """
*start
@choice
  - いつも出る → *a
  - 金持ちだけ → *b @if gold >= 100
  - フラグがあれば @if flag.f
@if choice == 3
  三番目
@endif
@end
*a
A
@end
*b
B
@end
"""


def _first_choice(st):
    sc, rep = parse(SCRIPT)
    assert rep.ok, rep.format()
    vm = VM(sc, st, None, FakeHost())
    vm.start("start")
    req = vm.step()
    assert isinstance(req, ChoiceReq)
    return vm, req


def test_hidden_options_are_not_shown():
    vm, req = _first_choice(GameState(gold=10))
    assert req.options == ["いつも出る"]


def test_choice_number_keeps_written_order():
    st = GameState(gold=10, flags={"f"})
    vm, req = _first_choice(st)
    assert req.options == ["いつも出る", "フラグがあれば"]
    vm.choose(1)                                  # 2 番目に出た = 書いた順で 3 番目
    assert st.last_choice == 3
    assert vm.step().lines[0][1] == "三番目"


def test_choice_jumps_with_condition():
    st = GameState(gold=500)
    vm, req = _first_choice(st)
    assert req.options == ["いつも出る", "金持ちだけ"]
    vm.choose(1)
    assert vm.step().lines[0][1] == "B"


def test_no_option_left_is_an_error():
    sc, rep = parse("*start\n@choice\n  - だれも → *x @if flag.none\n@end\n*x\n@end\n")
    assert rep.ok
    vm = VM(sc, GameState(), None, FakeHost())
    vm.start("start")
    with pytest.raises(ScriptError, match="選択肢がひとつも"):
        vm.step()


@pytest.mark.parametrize("line", ["  - あ @if ", "  - あ @if gold >>> 3"])
def test_bad_option_condition(line):
    _, rep = parse(f"*start\n@choice\n{line}\n@end\n")
    assert not rep.ok


def test_party_choice_in_game(sample_dir):
    """パーティにいる仲間だけを並べる（離脱する仲間を選ぶ場面）。"""
    sco = sample_dir / "scenario.sco"
    sco.write_text(sco.read_text(encoding="utf-8") + """
*who
@choice
  - ガロ → *w_garo @if party.has(garo)
  - ミア → *w_mia @if party.has(mia)
  - ユウ自身 → *w_hero @if party.has(hero)
@end
*w_garo
@end
*w_mia
@end
*w_hero
@end
""", encoding="utf-8")
    g = load_game(sample_dir)
    try:
        d = Driver(g)
        for _ in range(4):
            d.key("ENTER")
        d.settle()
        d.field.start_script("who")
        d.tick(0.2)
        assert d.field.choice is not None
        assert "ガロ" not in d.screen() and "ユウ自身" in d.screen()
    finally:
        g.close()


# ---------------------------------------------------------------- アイテム名の {hero}
def test_item_name_uses_hero_name(sample_dir):
    items = sample_dir / "Items.data"
    items.write_text(items.read_text(encoding="utf-8") + """
[[item]]
id = "own_sword"
name = "{hero}の剣"
type = "equipment"
slot = "weapon"
desc = "{hero}自身の剣。"
stats = { atk = 45 }
""", encoding="utf-8")
    g = load_game(sample_dir)
    try:
        it = g.data.items["own_sword"]
        personalize(g.data, "アキ")
        assert (it.name, it.desc) == ("アキの剣", "アキ自身の剣。")
        personalize(g.data, "ユウ")                 # 別のセーブを読んだら名前も変わる
        assert (it.name, it.desc) == ("ユウの剣", "ユウ自身の剣。")
        assert g.data.items["herb"].raw == ()       # {hero} のないアイテムはそのまま

        d = Driver(g)
        d.key("ENTER")                              # はじめから → 名前入力
        while d.scene.name:
            d.key("BACKSPACE")
        for ch in "ケン":
            d.key(ch)
        d.key("ENTER")
        d.settle()
        assert it.name == "ケンの剣"
    finally:
        g.close()
