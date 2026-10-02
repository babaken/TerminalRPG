"""4-2：テイムした魔物（ペット）が戦闘に参加する。"""
import random

import pytest

from test_battle_core import game, msgs, new_state  # noqa: F401
from test_play import Driver, _seed  # noqa: F401
from trpg.battle.core import Battle, Command
from trpg.data import Report, load_game_data
from trpg.package import open_package
from trpg.script.lint import lint_script
from trpg.script.parser import parse_script
from trpg.term import Buffer


def battle(game, pet="mole", group="slime_2", seed=0):
    st = new_state(game)
    st.pet = pet
    return st, Battle(game.data, st, group, rng=random.Random(seed))


def test_pet_joins_with_full_hp(game):
    st, b = battle(game)
    assert b.pet is not None and b.pet.side == "party" and b.pet.pet
    assert b.pet.hp == b.pet.max_hp == 40 and b.pet.name == "ハタケモグラ"
    assert b.pet in b.allies and b.pet not in b.party
    assert "ハタケモグラがいっしょに戦う！" in msgs(b.intro())
    _, nob = battle(game, pet="")
    assert nob.pet is None and nob.allies == nob.party


def test_pet_attacks_enemies(game):
    st, b = battle(game)
    hero = b.party[0]
    acted = []
    for _ in range(10):
        out = msgs(b.run_round({hero: Command("defend")}))
        acted += [m for m in out if m.startswith("ハタケモグラの攻撃") or "ハタケモグラの" in m]
        if b.result:
            break
    assert acted                                               # ペットが自分で攻撃した
    assert b.result == "win" or any(e.hp < e.max_hp for e in b.enemies)


def test_pet_command_choices(game):
    st, b = battle(game)
    c = b.pet_command(b.pet)
    assert c.kind in ("attack", "skill") and c.target in b.enemies
    for e in b.enemies:
        e.hp = 0
    assert b.pet_command(b.pet).target is None


def test_enemies_can_target_pet(game):
    st, b = battle(game, seed=3)
    targets = {id(b._enemy_target(b.enemies[0], "random")) for _ in range(40)}
    assert id(b.pet) in targets and id(b.party[0]) in targets


def test_lose_when_party_down_even_if_pet_alive(game):
    st, b = battle(game)
    b.party[0].hp = 0
    assert b.pet.alive and b._check_end() and b.result == "lose"


def test_pet_gets_no_exp_and_hp_not_saved(game):
    st, b = battle(game)
    b.pet.hp = 5
    for e in b.enemies:
        e.hp = 0
        b.defeated.append(e.enemy.id)
    b._check_end()
    out = msgs(b.finish())
    assert not any("ハタケモグラ" in m for m in out)
    _, b2 = battle(game)
    assert b2.pet.hp == b2.pet.max_hp                          # 次の戦闘では満タン


def test_pet_status_ticks(game):
    st, b = battle(game)
    if "poison" in game.data.statuses:
        b.pet.status["poison"] = 2
        msgs(b._end_of_round())
        assert b.pet.hp < b.pet.max_hp


def test_tame_replaces_pet(game):
    st, b = battle(game)
    b.tame_rate = lambda t: 1.0
    out = msgs(b._tame(b.party[0], Command("tame", target=b.enemies[0])))
    assert st.pet == "slime"
    assert "いままでのハタケモグラは、野に帰っていった。" in out


def test_escape_failure_stops_pet(game):
    st, b = battle(game)
    b.escape_rate = lambda: 0.0
    out = msgs(b.run_round({b.party[0]: Command("escape")}))
    assert not any(m.startswith("ハタケモグラの") for m in out)


# ---------------------------------------------------------------- 画面・スクリプト
@pytest.fixture
def d(game):
    d = Driver(game)
    for _ in range(4):
        d.key("ENTER")
    d.settle()
    return d


def test_battle_screen_shows_pet(d):
    d.field.st.pet = "mole"
    sc = d.field.start_battle("slime_2")
    d.tick(0.5)
    buf = Buffer(100, 30)
    sc.draw(buf)
    text = "\n".join("".join(c[0] for c in r) for r in buf.rows)
    assert "ペット" in text and "ハタケモグラ" in text


def test_field_panel_shows_pet(d):
    d.field.st.pet = "slime"
    assert "ペット スライム" in d.screen()


def test_pet_command_and_expression(d):
    f = d.field
    f.vm.script = parse_script('''*p
@pet mole
@if pet == mole
@flag set has_mole
@endif
@pet release
@if pet == ""
@flag set no_pet
@endif
@end
''', Report())
    f.start_script("p")
    d.tick(0.3)
    assert {"has_mole", "no_pet"} <= f.st.flags and f.st.pet == ""


def test_pet_lint(sample_dir):
    sco = sample_dir / "scenario.sco"
    sco.write_text(sco.read_text(encoding="utf-8") + "\n*pet_bad\n@pet dragon\n@pet release\n@end\n", encoding="utf-8")
    rep = Report()
    with open_package(sample_dir, rep) as pkg:
        gd = load_game_data(pkg, rep)
        sc = parse_script(sco.read_text(encoding="utf-8"), rep, "scenario.sco", loader=pkg.read_text)
        lint_script(sc, gd, rep, pkg)
    text = rep.format()
    assert "dragon" in text and text.count("release") == 0
