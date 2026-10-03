"""戦闘ロジック（battle.core）のテスト。乱数は固定して結果を確かめる。"""
import random

import pytest

from trpg.battle.core import Battle, Command
from trpg.game import load_game
from trpg.world.state import GameState, Member


@pytest.fixture
def game(sample_dir):
    g = load_game(sample_dir)
    yield g
    g.close()


def new_state(game, *cids):
    st = GameState.new_game(game.data, game.manifest)
    for c in cids:
        st.party.append(Member.from_data(game.data, c))
    return st


def msgs(events):
    return [v for k, v in events if k == "msg"]


def fight(b, choose, max_rounds=30):
    """毎ラウンド choose(battle) のコマンドで戦い、全イベントのメッセージを返す。"""
    out = msgs(b.intro())
    for _ in range(max_rounds):
        out += msgs(b.run_round(choose(b)))
        if b.result:
            out += msgs(b.finish())
            return out
    raise AssertionError("終わらない")


def attack_first(b):
    return {p: Command("attack", target=b.alive("enemy")[0]) for p in b.actors()}


def test_intro_names_and_letters(game):
    b = Battle(game.data, new_state(game), "slime_bat")
    assert [e.name for e in b.enemies] == ["スライム", "コウモリ"]
    b2 = Battle(game.data, new_state(game), "slime_2")
    assert [e.name for e in b2.enemies] == ["スライムＡ", "スライムＢ"]
    assert msgs(b2.intro()) == ["スライムが 2 匹あらわれた！"]


def test_win_gives_rewards_and_counts_quest(game):
    st = new_state(game)
    st.hero.base["atk"] = 40           # 確実に勝てるように
    st.quests["q_slime"] = "active"
    st.quest_progress["q_slime"] = 0
    b = Battle(game.data, st, "slime_2", rng=random.Random(1))
    out = fight(b, attack_first)
    assert b.result == "win"
    assert "魔物たちをやっつけた！" in out
    assert st.gold == 2 * 2
    assert st.hero.exp == 6
    assert st.quest_progress["q_slime"] == 2


def test_level_up(game):
    st = new_state(game)
    st.hero.base["atk"] = 40
    b = Battle(game.data, st, "raid_wolves", rng=random.Random(3))
    out = fight(b, attack_first)
    assert b.result == "win" and st.hero.lv == 2
    assert "ユウはレベル 2 に上がった！" in out


def test_target_only_hero(game):
    st = new_state(game, "garo")
    b = Battle(game.data, st, "raid_wolves", target_only="hero", rng=random.Random(5))
    garo_hp = st.member("garo").hp
    for _ in range(3):
        list(b.run_round({p: Command("defend") for p in b.actors()}))
    assert st.member("garo").hp == garo_hp      # ガロは一度も狙われない
    assert st.hero.hp < st.hero.max_hp


def test_defend_halves_damage(game):
    st = new_state(game)
    b = Battle(game.data, st, "raid_wolves", rng=random.Random(0))
    w, h = b.enemies[0], b.party[0]
    normal = b.physical_damage(w, h)[0]
    h.defending = True
    b.rng = random.Random(0)
    assert b.physical_damage(w, h)[0] <= max(1, normal // 2 + 1)


def test_escape_blocked(game):
    st = new_state(game)
    b = Battle(game.data, st, "slime_2", escape=False, rng=random.Random(0))
    out = msgs(b.run_round({b.party[0]: Command("escape")}))
    assert "しかし、逃げられない！" in out and b.result is None


def test_escape_success(game):
    st = new_state(game)
    b = Battle(game.data, st, "slime_2", rng=random.Random(0))
    b.escape_rate = lambda: 1.0
    out = msgs(b.run_round({b.party[0]: Command("escape")}))
    assert b.result == "escape" and "うまく逃げ切れた！" in out


def test_lose(game):
    st = new_state(game)
    st.hero.hp = 1
    b = Battle(game.data, st, "raid_wolves", rng=random.Random(2))
    for _ in range(10):
        list(b.run_round({p: Command("defend") for p in b.actors()}))
        if b.result:
            break
    assert b.result == "lose" and st.hero.hp == 0


def test_fire_on_slime_is_super_effective(game):
    st = new_state(game, "mia")
    b = Battle(game.data, st, "slime_2", rng=random.Random(4))
    mia = next(p for p in b.party if p.member.id == "mia")
    out = msgs(b._skill(mia, Command("skill", skill="fire", target=b.enemies[0])))
    assert "ミアはファイアをとなえた！" in out and "効果はばつぐんだ！" in out
    assert mia.mp == mia.max_mp - 4


def test_heal_and_mp_shortage(game):
    st = new_state(game, "rina")
    b = Battle(game.data, st, "slime_2", rng=random.Random(4))
    rina = next(p for p in b.party if p.member.id == "rina")
    hero = b.party[0]
    hero.hp = 5
    out = msgs(b._skill(rina, Command("skill", skill="heal", target=hero)))
    assert hero.hp > 5 and any("回復した" in m for m in out)
    rina.mp = 0
    out = msgs(b._skill(rina, Command("skill", skill="heal", target=hero)))
    assert "しかし MP が足りない！" in out


def test_poison_ticks_and_antidote(game):
    st = new_state(game)
    st.add_item("antidote")
    b = Battle(game.data, st, "mushroom_slime", rng=random.Random(0))
    hero = b.party[0]
    out = msgs(b._inflict(hero, "poison", 1.0))
    assert out == ["ユウはどくになった！"]
    hp = hero.hp
    out = msgs(b._end_of_round())
    assert hero.hp < hp and "ユウはどくで苦しんでいる！" in out
    out = msgs(b._item(hero, Command("item", item="antidote", target=hero)))
    assert "ユウのどくが治った！" in out and "poison" not in hero.status
    assert "antidote" not in st.items


def test_poison_persists_after_battle(game):
    st = new_state(game)
    b = Battle(game.data, st, "slime_2", rng=random.Random(0))
    list(b._inflict(b.party[0], "poison", 1.0))
    b.result = "escape"
    list(b.finish())
    assert st.hero.status == ["poison"]          # field = true の状態異常は残る


def test_enemy_pattern_ai_condition(game):
    st = new_state(game)
    b = Battle(game.data, st, "mole_pack", rng=random.Random(0))
    mole = b.enemies[0]
    picks = {b.enemy_command(mole).kind for _ in range(40)}
    assert picks == {"attack"}                   # HP 満タンでは土かけを使わない
    mole.hp = 5
    picks = {b.enemy_command(mole).skill for _ in range(60)}
    assert "dig_attack" in picks


def test_tame(game):
    st = new_state(game)
    b = Battle(game.data, st, "slime_2", rng=random.Random(0))
    b.tame_rate = lambda t: 1.0
    out = msgs(b._tame(b.party[0], Command("tame", target=b.enemies[0])))
    assert st.pet == "slime" and b.enemies[0].gone
    assert "スライムＡはなついた！　仲間になった！" in out


def test_poison_kills_ally_at_end_of_round(game):
    """毒で味方が倒れても、ターンの終わりの処理が止まらない（以前は KeyError）。"""
    st = new_state(game)
    b = Battle(game.data, st, "slime_2", rng=random.Random(0))
    hero = b.party[0]
    hero.status["poison"] = 3
    hero.hp = 1
    out = msgs(b._end_of_round())
    assert not hero.alive and any("たおれてしまった" in m for m in out) and hero.status == {}
