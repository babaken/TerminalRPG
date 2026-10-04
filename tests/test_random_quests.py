"""冒険者協会のランダムの依頼（Quests.data の random = true、manifest の random_quests）。"""
import random
from pathlib import Path

import pytest

from trpg.game import load_game
from trpg.save import state_from_dict, state_to_dict
from trpg.script.expr import evaluate, parse_expr
from trpg.world import quests as Q
from trpg.world.state import GameState

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(params=["FirstQuest", "FirstQuestPlus"])
def game(request):
    g = load_game(ROOT / "scenarios" / request.param)
    yield g
    g.close()


def cond_of(st):
    return lambda src: not src or bool(evaluate(parse_expr(src), st))


def board(game, st, slots=3, seed=0):
    random.seed(seed)
    return [q for q in Q.available(st, game.data, cond_of(st), slots=slots) if q.random]


def test_three_random_quests_on_the_board(game):
    st = GameState(flags={"guild_registered"})
    qs = board(game, st)
    assert len(qs) == 3 and all(q.rank == "F" for q in qs)
    assert len({q.id for q in qs}) == 3
    fixed = [q for q in Q.available(st, game.data, cond_of(st)) if not q.random]
    assert {q.id for q in fixed} == {"q_herb", "q_slime", "q_lost_cat", "q_delivery"}


def test_board_is_refilled_after_accepting(game):
    """受けきっても、別の依頼が補充される（達成した依頼も、また出てくる）。"""
    st = GameState(flags={"guild_registered", "ch2_rumor"})
    first = board(game, st)
    assert len(first) == 3
    for q in first:
        Q.accept(st, q)
    second = board(game, st)                       # 受けた 3 つは外れ、残りの 2 つが貼られる
    assert len(second) == 2 and not {q.id for q in first} & {q.id for q in second}
    for q in second:
        Q.accept(st, q)
    assert board(game, st) == []                   # 候補が尽きたら空
    q = game.data.quests["qr_mole"]
    st.quests[q.id] = "done"                       # 達成すると、また貼られる
    assert [x.id for x in board(game, st)] == ["qr_mole"]


@pytest.mark.parametrize("flags,rank", [
    ({"guild_registered"}, "F"),
    ({"guild_registered", "ch2_rumor"}, "E"),                       # カブラ村
    ({"guild_registered", "ch2_rumor", "ch2_map_reported"}, "D"),   # 黒岩の洞穴
    ({"guild_registered", "ch2_rumor", "ch2_map_reported", "ch2_ogre_done"}, "C"),
])
def test_newest_area_quest_is_always_posted(game, flags, rank):
    for seed in range(20):
        st = GameState(flags=set(flags))
        assert any(q.rank == rank for q in board(game, st, seed=seed))


def test_newest_area_quest_is_added_to_an_existing_board(game):
    st = GameState(flags={"guild_registered"})
    board(game, st)
    st.board = st.board[:2]                        # 枠が空いていて、新しいエリアが開いた
    st.flags.add("ch2_rumor")
    qs = board(game, st)
    assert [q.rank for q in qs].count("E") == 1 and len(qs) == 3


def test_chapter3_area(game):
    flags = {"guild_registered", "ch2_rumor", "ch2_map_reported", "ch2_ogre_done",
             "p3_started" if game.manifest.id == "firstquest_plus" else "ch3_started"}
    st = GameState(flags=flags)
    assert any(q.rank == "B" for q in board(game, st))


def test_slots_zero_means_no_random_quests(game):
    st = GameState(flags={"guild_registered"})
    assert board(game, st, slots=0) == []


def test_board_is_saved(game):
    st = GameState(flags={"guild_registered"})
    ids = [q.id for q in board(game, st)]
    assert state_from_dict(state_to_dict(st)).board == ids
    assert state_from_dict({}).board == []          # 古いセーブ


def test_defeat_counts_for_random_quest(game):
    st = GameState(flags={"guild_registered", "ch2_rumor"})
    q = game.data.quests["qr_mole"]
    Q.accept(st, q)
    Q.on_defeat(st, game.data, ["mole", "mole", "drill_mole"])
    assert Q.progress(st, game.data, q) == (2, 4)
    Q.on_defeat(st, game.data, ["mole", "mole"])
    assert Q.goal_met(st, game.data, q)
    res = Q.complete(st, game.data, q)
    assert st.quests[q.id] == "done" and any("100 G" in m for m in res.messages)


def test_guild_screen_shows_random_quests(game):
    from test_play import Driver
    d = Driver(game)
    for _ in range(4):
        d.key("ENTER")
    f = d.app.scene
    f.st.flags |= {"guild_registered", "ch2_rumor"}
    from trpg.scenes.facility import GuildScene
    g = GuildScene(f)
    d.app.push(g)
    g._top_done(0)
    assert [q.random for q in g._quests][-3:] == [True] * 3  # いつもの依頼のあとにランダムの依頼 3 つ
    assert sum(1 for q in g._quests if q.random) == 3
    assert any(q.rank == "E" for q in g._quests if q.random)
