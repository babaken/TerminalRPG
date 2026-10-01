"""2-2：本文の制御コード・顔 AA・タイトル背景のテスト。"""
import pytest

from test_play import Driver, _seed  # noqa: F401
from trpg.data import DataError, Report, load_game_data
from trpg.game import load_game
from trpg.package import open_package
from trpg.scenes.title import TitleScene
from trpg.script.lint import lint_script
from trpg.script.parser import parse_script
from trpg.term import Buffer, Rect
from trpg.ui import markup
from trpg.ui.widgets import MessageWindow

from conftest import edit


# ---------------------------------------------------------------- 制御コード
def test_parse_codes():
    gs = markup.parse("あ\\w500い\\c[red]う\\c[]え\\s2お\\\\")
    assert "".join(g.ch for g in gs) == "あいうえお\\"
    assert gs[1].wait == 0.5 and gs[0].wait == 0
    assert gs[2].color == "red" and gs[3].color is None
    assert gs[4].speed == 2 and gs[3].speed == 1


def test_strip_and_check():
    assert markup.strip("\\c[yellow]剣\\c[]を得た\\w300！") == "剣を得た！"
    assert markup.check("\\c[yellow]剣\\c[]") == []
    errs = " ".join(markup.check("\\x \\c[purple]a\\c[] \\c[red]b"))
    assert "「\\x」は使えません" in errs and "purple" in errs and "閉じていません" in errs


def test_wait_and_speed_timing():
    w = MessageWindow()
    w.layout(40, 3)
    w.open([("", "あ\\w500い")])
    w.update(0.03)                      # 1 文字分（40 文字/秒）
    assert int(w.shown) == 1
    w.update(0.3)                       # 待ち 0.5 秒の途中
    assert int(w.shown) == 1
    w.update(0.25)
    assert w.page_done
    w.open([("", "ゆっくり\\s0一気に出る")])
    w.update(0.11)                      # 「ゆっくり」4 文字 → 以降は速さ 0 で一度に出る
    assert w.page_done
    assert w.pages[0] == ["ゆっくり一気に出る"]


def test_color_drawn():
    w = MessageWindow()
    w.open([("", "普通\\c[bright_red]赤\\c[]")])
    w.advance()
    buf = Buffer(40, 5)
    w.draw(buf, Rect(0, 0, 40, 5))
    row = buf.rows[1]
    red = [c for c in row if c[0] == "赤"][0]
    plain = [c for c in row if c[0] == "普"][0]
    assert red[1].fg == 9 and plain[1].fg != 9


# ---------------------------------------------------------------- 顔 AA
@pytest.fixture
def game(sample_dir):
    sco = sample_dir / "scenario.sco"
    sco.write_text(sco.read_text(encoding="utf-8") + """
*face_test
@face kai
カイ「顔が出る」
@choice
  - \\c[red]はい\\c[]
  - いいえ
@end
""", encoding="utf-8")
    g = load_game(sample_dir)
    yield g
    g.close()


def new_driver(game):
    d = Driver(game)
    for _ in range(4):
        d.key("ENTER")
    d.settle()
    return d


def test_face_shown_and_cleared(game):
    d = new_driver(game)
    f = d.field
    f.start_script("face_test")
    d.tick(0.5)
    screen = d.screen()
    assert "( ^  ^ )" in screen and "─ カイ ─" in screen
    d.key("ENTER")
    assert f.choice is not None and f.choice.options == ["はい", "いいえ"]   # 選択肢の制御コードは消える
    d.key("ENTER")
    d.tick(0.1)
    assert f.face is None and "( ^  ^ )" not in d.screen()


def test_face_path_priority(game):
    gd = game.data
    exists = game.package.exists
    assert gd.face_path("kai", exists) == "aa/face_kai.txt"
    assert gd.face_path("nobody", exists) is None
    assert gd.face_path("aa/slime.txt", exists) == "aa/slime.txt"


def test_lint_face_and_markup(sample_dir):
    sco = sample_dir / "scenario.sco"
    sco.write_text(sco.read_text(encoding="utf-8") + """
*lint_bad
@face ghost
母「\\c[pink]色\\c[]」
@choice
  - \\q変
@goto *lint_bad
""", encoding="utf-8")
    rep = Report()
    with open_package(sample_dir, rep) as pkg:
        gd = load_game_data(pkg, rep)
        sc = parse_script(sco.read_text(encoding="utf-8"), rep, "scenario.sco", loader=pkg.read_text)
        lint_script(sc, gd, rep, pkg)
    text = rep.format()
    assert "「ghost」の顔 AA がありません" in text
    assert "pink" in text and "「\\q」は使えません" in text


# ---------------------------------------------------------------- タイトル背景
def test_title_starfall(game):
    t = TitleScene(game)
    assert t.bg_kind == "starfall"
    first = t.bg
    for _ in range(150):                # 5 秒ほど
        t.update(1 / 30)
    assert t.bg is not first            # 降り終わったら次の流れ星
    saw_star = False
    for _ in range(120):                # 流れ星の頭（*）が見える瞬間がある。タイトル文字は常に見える
        t.update(1 / 30)
        buf = Buffer(100, 30)
        t.draw(buf)
        text = "\n".join("".join(c[0] for c in r) for r in buf.rows)
        assert "はじめから" in text
        saw_star = saw_star or "*" in text
    assert saw_star


def test_title_effect_validated(sample_dir):
    edit(sample_dir / "manifest.toml", 'effect = "starfall"', 'effect = "fireworks"')
    with pytest.raises(DataError) as ei:
        open_package(sample_dir)
    assert "fireworks" in ei.value.report.format()
