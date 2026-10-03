"""UI の英語切り替え（7-1）：すべての UI 文に英語の訳があり、切り替えると画面が英語になる。"""
import ast
import random
import re
from pathlib import Path

import pytest

from test_play import Driver, _seed  # noqa: F401
from trpg.battle.core import Battle, Command
from trpg.game import load_game
from trpg.i18n import get_lang, load_lang, set_lang, tr
from trpg.i18n.en import EN
from trpg.scenes.title import TitleScene
from trpg.term import Buffer
from trpg.world.state import GameState, Member

SRC = Path(__file__).resolve().parent.parent / "src" / "trpg"
JP = re.compile(r"[぀-ヿ一-鿿]")


def ui_keys() -> set[str]:
    keys = set()
    for p in SRC.rglob("*.py"):
        if "i18n" in p.parts:
            continue
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "tr" and n.args
                    and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
                keys.add(n.args[0].value)
    from trpg.app import IME_NOTICE
    from trpg.scenes.facility import STAT_NAMES
    from trpg.scenes.menu import SLOT_NAMES, TOP
    from trpg.settings import TEXT_SPEED_NAMES
    return (keys | set(TOP) | set(SLOT_NAMES.values()) | set(STAT_NAMES.values()) | {IME_NOTICE}
            | set(TEXT_SPEED_NAMES.values()))


def test_every_ui_text_has_english():
    missing = sorted(k for k in ui_keys() if JP.search(k) and k not in EN)
    assert not missing, f"英語の訳がない UI 文: {missing}"


def test_placeholders_match():
    ph = re.compile(r"\{(\d*)[^}]*\}")
    bad = [k for k, v in EN.items() if sorted(ph.findall(k)) != sorted(ph.findall(v))]
    assert not bad, f"{{0}} などの数が合わない: {bad}"
    assert not [v for v in EN.values() if JP.search(v)], "英語の訳に日本語が残っている"


def test_tr_switches_language():
    assert tr("{0}の攻撃！", "ユウ") == "ユウの攻撃！"
    set_lang("en")
    assert get_lang() == "en" and tr("{0}の攻撃！", "ユウ") == "ユウ attacks!"
    assert tr("翻訳のない文") == "翻訳のない文"                     # 訳がなければ日本語のまま
    with pytest.raises(ValueError):
        set_lang("fr")


@pytest.fixture
def game(sample_dir):
    g = load_game(sample_dir)
    yield g
    g.close()


def test_battle_messages_in_english(game):
    set_lang("en")
    st = GameState.new_game(game.data, game.manifest)
    st.party.append(Member.from_data(game.data, "garo"))
    b = Battle(game.data, st, "slime_2", rng=random.Random(0))
    out = [v for k, v in b.intro() if k == "msg"]
    assert out == ["スライム x2 appeared!"]                          # 名前はシナリオのまま
    out = [v for k, v in b.run_round({x: Command("attack", target=b.enemies[0]) for x in b.party}) if k == "msg"]
    assert any(m.endswith("attacks!") for m in out) and not any("の攻撃" in m for m in out)


def screen(scene):
    buf = Buffer(100, 30)
    scene.draw(buf)
    return "\n".join("".join(c[0] for c in r) for r in buf.rows)


def test_title_toggle_is_saved(game):
    d = Driver(game)
    title = d.scene
    assert isinstance(title, TitleScene)
    assert "はじめから" in screen(title) and "言語 / Language：日本語" in screen(title)
    title.index = TitleScene.LANG_INDEX
    d.key("ENTER")
    assert get_lang() == "en" and "New Game" in screen(title) and "言語 / Language：English" in screen(title)
    assert load_lang() == "en"                                          # 次の起動でも英語
    d.key("ENTER")
    assert get_lang() == "ja" and load_lang() == "ja"


def test_menu_and_field_in_english(game):
    set_lang("en")
    d = Driver(game)
    for _ in range(4):
        d.key("ENTER")
    d.settle()
    text = d.screen()
    assert "Party" in text and "Move: Arrows/WASD" in text
    d.key("ESC")
    text = d.screen()
    assert "Menu" in text and "Item" in text and "Equip" in text and "どうぐ" not in text
    d.key("ENTER")                                                     # Item（メニューの判定は日本語の見出しのまま）
    assert "Item" in d.screen() or "nothing" in d.screen()


def test_lang_option(game, sample_dir, capsys):
    from trpg.__main__ import main
    assert main(["--lang", "en", "--check", str(sample_dir)]) == 0
    assert get_lang() == "en"
