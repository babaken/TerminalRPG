"""2-1 で追加したエフェクト（wipe / blink / scroll_text / tint invert / move / aa_show / aa_hide）のテスト。"""
import pytest

from test_play import Driver, _seed  # noqa: F401
from trpg.data import Report, load_game_data
from trpg.effects import Blink, EffectManager, ScrollText, Wipe
from trpg.game import load_game
from trpg.package import open_package
from trpg.script.lint import lint_script
from trpg.script.parser import parse_script
from trpg.term import REVERSE, Buffer

EXTRA = """
*fx_move_aa
@aa show aa/slime.txt 10 2 name=enemy
@effect move enemy -4 0 ms=20
動いた
@end

*fx_move_bg
@aa show aa/slime.txt 10 2 name=enemy
@effect move enemy 6 0 ms=50 wait=false
並行して話す
@end

*fx_slide
@effect aa_show aa/slime.txt 20 3 name=boss from=left ms=20
現れた
@effect aa_hide boss to=right ms=20
消えた
@end

*fx_blink
@effect blink mother count=2 interval=100
点滅した
@end

*fx_credits
@effect scroll_text file=credits.txt speed=20
おわり
@end

*fx_wipe
@effect wipe right 200
開いた
@end
"""


@pytest.fixture
def game(sample_dir):
    sco = sample_dir / "scenario.sco"
    sco.write_text(sco.read_text(encoding="utf-8") + EXTRA, encoding="utf-8")
    (sample_dir / "credits.txt").write_text("FirstQuest\n\nシナリオ　{hero}\n", encoding="utf-8")
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


def run_until_msg(d, max_secs=10.0):
    f = d.field
    t = 0.0
    while not f.msg.active and t < max_secs:
        d.tick(1 / 30)
        t += 1 / 30
    return f.msg.active


# ---------------------------------------------------------------- 画面効果（単体）
def test_wipe_in_reveals_from_left():
    w = Wipe("right", 400)
    buf = Buffer(100, 30)
    w.update(0.1)                          # 25% 開いた → 右 75% が覆われている
    r = w.covered(buf)
    assert (r.x, r.w) == (25, 75)
    w.update(0.3)
    assert w.covered(buf).w == 0 and w.done


def test_wipe_out_covers_and_stays_dark():
    em = EffectManager({})
    eff = em.start("wipe", ["down", "out", "200"], {})
    assert isinstance(eff, Wipe) and em.faded
    buf = Buffer(10, 10)
    eff.update(0.1)
    r = eff.covered(buf)
    assert (r.y, r.h) == (0, 5)            # 上から半分覆われた
    em.start("wipe", ["up"], {})
    assert not em.faded


def test_tint_invert():
    em = EffectManager({})
    em.start("tint", ["invert"], {})
    buf = Buffer(4, 1)
    buf.put(0, 0, "ab")
    em.apply_world(buf)
    assert all(c[1].attrs & REVERSE for c in buf.rows[0])


def test_blink_toggles():
    b = Blink("kai", count=2, interval=100)
    assert b.hidden()
    b.update(0.11)
    assert not b.hidden()
    b.update(0.3)
    assert b.done


def test_scroll_text_key_skips():
    s = ScrollText(["a", "b"], speed=1)
    assert s.needs_key and not s.done
    s.key()
    assert s.done


# ---------------------------------------------------------------- フィールドで
def test_move_aa_overlay(d):
    f = d.field
    f.start_script("fx_move_aa")
    seen = []
    for _ in range(100):
        seen.append(f.overlays["enemy"][1])
        if f.msg.active:
            break
        d.tick(0.01, step=0.01)                                   # 1 マスの時間（20ms）より短いフレームで観察
    assert f.overlays["enemy"][1:] == (6, 2)
    assert sorted(set(seen), reverse=True) == [10, 9, 8, 7, 6]   # 1 セルずつ動いた


def test_move_in_background(d):
    f = d.field
    f.start_script("fx_move_bg")
    assert f.msg.active and "並行して話す" in f.msg.pages[0][0]   # 待たずに次の行へ
    assert f.overlays["enemy"][1] == 10
    d.tick(0.5)
    assert f.overlays["enemy"][1] == 16 and not f.background_movers


def test_aa_slide_in_and_out(d):
    f = d.field
    f.start_script("fx_slide")
    assert f.overlays["boss"][1] < 0                              # 画面の左外から
    assert run_until_msg(d)
    assert f.overlays["boss"][1:] == (20, 3)
    assert "boss" in d.screen() or ".---." in d.screen()
    d.key("ENTER")
    d.key("ENTER")
    assert run_until_msg(d)
    assert "boss" not in f.overlays                               # 右へ消えて取り除かれた


def test_blink_hides_npc(d):
    f = d.field                                                   # 主人公の家：母がいる
    f.start_script("fx_blink")
    assert f.effects.hidden("mother")
    assert "母" not in d.screen()
    d.tick(0.12)
    assert "母" in d.screen()
    assert run_until_msg(d) and "点滅した" in f.msg.pages[0][0]


def test_scroll_text_from_file(d):
    f = d.field
    f.start_script("fx_credits")
    eff = f.req
    assert isinstance(eff, ScrollText) and eff.lines == ["FirstQuest", "", "シナリオ　ユウ"]
    d.tick(0.7)                                                   # 20 行/秒 → 下から数行上がる
    assert "FirstQuest" in d.screen()
    d.key("ENTER")                                                # 飛ばす
    assert run_until_msg(d) and "おわり" in f.msg.pages[0][0]


def test_wipe_in_field(d):
    f = d.field
    f.start_script("fx_wipe")
    d.tick(0.1)                                                   # 半分開いた
    rows = d.screen().split("\n")
    assert rows[0][:5].strip() and not rows[0][-5:].strip()      # 左は見えていて右はまだ黒
    assert run_until_msg(d) and not f.effects.faded


# ---------------------------------------------------------------- 検証
def test_lint_new_effects(sample_dir):
    sco = sample_dir / "scenario.sco"
    sco.write_text(sco.read_text(encoding="utf-8") + """
*fx_bad
@effect move ghost 1 0
@effect blink nobody
@effect aa_show aa/none.txt 1 2
@effect aa_show aa/slime.txt 1 2 from=middle
@effect scroll_text file=nofile.txt
@effect tint purple
@effect wipe diagonal
@effect move kai 1
@goto *fx_bad
""", encoding="utf-8")
    rep = Report()
    with open_package(sample_dir, rep) as pkg:
        gd = load_game_data(pkg, rep)
        sc = parse_script(sco.read_text(encoding="utf-8"), rep, "scenario.sco", loader=pkg.read_text)
        lint_script(sc, gd, rep, pkg)
    text = rep.format()
    for frag in ("対象「ghost」", "対象「nobody」", "aa/none.txt", "from は", "nofile.txt",
                 "tint は", "wipe の向き", "「対象 dx dy」"):
        assert frag in text, frag


def test_scroll_text_crlf_file(game, sample_dir):
    """Windows で保存した（改行が CRLF の）ファイルでも行末に \\r が残らない。"""
    (sample_dir / "credits.txt").write_bytes("A\r\nB\r\n".encode("utf-8"))
    g = load_game(sample_dir)
    d = Driver(g)
    for _ in range(4):
        d.key("ENTER")
    d.settle()
    d.field.start_script("fx_credits")
    assert d.field.req.lines == ["A", "B"]
