import pytest

from trpg.data import Report, load_game_data
from trpg.package import open_package
from trpg.script.expr import ExprError, evaluate, parse_expr
from trpg.script.lint import lint_script
from trpg.script.parser import parse_script, split_args
from trpg.script.vm import VM, ChoiceReq, MessageReq, ScriptError, WaitReq
from trpg.world.state import GameState, format_text


def parse(text, loader=None):
    rep = Report()
    sc = parse_script(text, rep, "t.sco", loader=loader)
    return sc, rep


class FakeHost:
    def __init__(self):
        self.cmds = []

    def exec_cmd(self, ins):
        self.cmds.append((ins.args["name"], ins.args["pos"], ins.args["kw"]))
        return None


def run(text, state=None, gd=None, label="start", choices=()):
    sc, rep = parse(text)
    assert rep.ok, rep.format()
    st = state or GameState()
    host = FakeHost()
    vm = VM(sc, st, gd, host)
    vm.start(label)
    out, choices = [], list(choices)
    while True:
        req = vm.step()
        if req is None:
            break
        if isinstance(req, MessageReq):
            out.append(" ".join(t for _, t in req.lines))
        elif isinstance(req, ChoiceReq):
            vm.choose(choices.pop(0))
        else:
            out.append(req)
    return out, st, host


# ---------------------------------------------------------------- 式
def test_expr_eval():
    st = GameState(gold=120, flags={"a"}, vars={"n": 3}, items={"herb": 2}, quests={"q": "done"})
    ok = lambda s: evaluate(parse_expr(s), st)
    assert ok("flag.a and !flag.b")
    assert ok("gold >= 100 and var.n == 3")
    assert ok("item.herb > 1 or false")
    assert ok("quest.q == done")
    assert ok("not (var.n < 3)")
    assert ok("var.missing == 0")
    assert not ok("party.has(hero)")


@pytest.mark.parametrize("src", ["", "flag.a and", "gold >>= 1", "foo.bar", "(flag.a", "flag.a flag.b"])
def test_expr_errors(src):
    with pytest.raises(ExprError):
        parse_expr(src)


def test_split_args():
    assert split_args('a "b c" k=v k2="x y"') == (["a", "b c"], {"k": "v", "k2": "x y"})
    assert split_args('"第1章　出会い"') == (["第1章　出会い"], {})


# ---------------------------------------------------------------- 構文解析
def test_messages_and_pages():
    sc, rep = parse("*start\nカイ「やあ」\n地の文\n\n次のページ\n")
    assert rep.ok
    msgs = [i for i in sc.instrs if i.op == "msg"]
    assert len(msgs) == 2
    assert msgs[0].args["lines"] == [("カイ", "カイ「やあ」"), ("", "地の文")]


def test_parse_errors_have_lines():
    text = "*start\n@unknown 1\n@flag toggle x\n@map village 1\n@if flag.a\n*start\n@goto\n"
    _, rep = parse(text)
    lines = {e.line: e.message for e in rep.errors}
    assert "@unknown という命令はありません" in lines[2]
    assert "toggle" in lines[3]
    assert "3 番目の引数がありません" in lines[4]
    assert "重複" in lines[6]
    assert "1 番目の引数がありません" in lines[7]
    assert "@endif がありません" in lines[5]


def test_specific_arg_checks():
    _, rep = parse('*s\n@npc kai move 1\n@hero face north\n@battle escape=true\n@effect sparkle\n@map m 1 2 dir=north\n')
    text = rep.format()
    for frag in ("dx dy", "向き", "group=", "sparkle", "dir は"):
        assert frag in text


def test_if_elif_else():
    text = """*start
@if var.n == 1
  one
@elif var.n == 2
  two
@else
  other
@endif
done
"""
    for n, want in ((1, "one"), (2, "two"), (5, "other")):
        out, _, _ = run(text, GameState(vars={"n": n}))
        assert out == [want, "done"]


def test_choice_jump_and_fallthrough():
    text = """*start
@choice
  - はい → *yes
  - いいえ
@if choice == 2
  no
@endif
@end
*yes
yes
"""
    assert run(text, choices=[0])[0] == ["yes"]
    assert run(text, choices=[1])[0] == ["no"]


def test_state_commands_and_call():
    text = """*start
@flag set a
@var n = 2
@var n += 3
@gold add 50
@gold remove 80
@call *sub
@chapter 2 "承"
@wait 500
@end
*sub
@flag clear a
@return
"""
    out, st, _ = run(text, GameState(gold=10))
    assert st.vars["n"] == 5 and st.gold == 0 and "a" not in st.flags
    assert st.chapter == 2 and st.chapter_title == "承"
    assert isinstance(out[0], WaitReq) and out[0].seconds == 0.5


def test_host_commands_and_include():
    files = {"sub.sco": "*sub\n@effect flash white count=2\n@return\n"}
    sc, rep = parse('@include "sub.sco"\n*start\n@call *sub\n@map village 1 2\n', loader=files.get)
    assert rep.ok, rep.format()
    st = GameState()
    host = FakeHost()
    vm = VM(sc, st, None, host)
    vm.start("start")
    assert vm.step() is None
    assert host.cmds == [("effect", ["flash", "white"], {"count": "2"}), ("map", ["village", "1", "2"], {})]


def test_include_cycle_and_missing():
    files = {"a.sco": '@include "b.sco"\n', "b.sco": '@include "a.sco"\n'}
    _, rep = parse('@include "a.sco"\n@include "zzz.sco"\n', loader=files.get)
    text = rep.format()
    assert "循環" in text and "zzz.sco" in text


def test_infinite_loop_detected():
    sc, _ = parse("*start\n@goto *start\n")
    vm = VM(sc, GameState(), None, FakeHost())
    vm.start("start")
    with pytest.raises(ScriptError, match="無限ループ"):
        vm.step()


def test_format_text():
    from trpg.world.state import Member
    st = GameState(gold=7, vars={"x": 3})
    st.party = [Member("hero", "ユウ", "hero", 1, {"hp": 10}), Member("rina", "リナ", "priest", 1, {"hp": 10})]
    assert format_text("{hero}と{party.2}、{gold}G、{var.x}、{unknown}", st) == "ユウとリナ、7G、3、{unknown}"


# ---------------------------------------------------------------- 検証
def test_lint(sample_dir):
    sco = sample_dir / "scenario.sco"
    sco.write_text(sco.read_text(encoding="utf-8") + """
*extra_unused
@goto *nowhere
@map forest_1 99 99
@map forest_1 0 0
@item add potion
@battle group=nogroup
@npc ghost hide
@if flag.never_set
@endif
""", encoding="utf-8")
    rep = Report()
    with open_package(sample_dir, rep) as pkg:
        gd = load_game_data(pkg, rep)
        sc = parse_script(sco.read_text(encoding="utf-8"), rep, "scenario.sco", loader=pkg.read_text)
        lint_script(sc, gd, rep, pkg)
    text = rep.format()
    for frag in ("*nowhere", "(99, 99) がマップ外", "(0, 0) は通行できない", "アイテム「potion」",
                 "敵グループ「nogroup」", "NPC「ghost」", "*extra_unused はどこからも使われていません",
                 "フラグ never_set"):
        assert frag in text, frag


def test_lint_missing_label_from_data(sample_dir):
    sco = sample_dir / "scenario.sco"
    sco.write_text(sco.read_text(encoding="utf-8").replace("*ch1_chief_talk", "*ch1_chief_talk_x"), encoding="utf-8")
    rep = Report()
    with open_package(sample_dir, rep) as pkg:
        gd = load_game_data(pkg, rep)
        sc = parse_script(sco.read_text(encoding="utf-8"), rep, "scenario.sco", loader=pkg.read_text)
        lint_script(sc, gd, rep, pkg)
    [err] = rep.errors
    assert err.file == "Map.data" and "*ch1_chief_talk" in err.message
