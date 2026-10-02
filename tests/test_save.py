"""セーブ／ロード（暗号化・改ざん検知・スロット・画面からの通し）のテスト。"""
import pytest

from test_play import Driver, _seed  # noqa: F401
from trpg.game import load_game
from trpg.save import SaveError, SaveStore, decode, encode, state_from_dict, state_to_dict
from trpg.scenes.field import FieldScene
from trpg.scenes.gameover import GameOverScene
from trpg.scenes.menu import TOP, MenuScene
from trpg.scenes.saveload import SaveLoadScene
from trpg.scenes.title import TitleScene
from trpg.world.state import GameState, Member


@pytest.fixture
def game(sample_dir, tmp_path):
    g = load_game(sample_dir)
    g.save_dir = tmp_path / "saves"
    yield g
    g.close()


def sample_state(game) -> GameState:
    st = GameState.new_game(game.data, game.manifest, "ケン")
    st.party.append(Member.from_data(game.data, "mia"))
    st.party[0].hp = 7
    st.party[0].status = ["poison"]
    st.party[0].equip["weapon"] = "rusty_sword"
    st.gold = 123
    st.items = {"herb": 4, "adventurer_card": 1}
    st.flags = {"found_sword", "ch1_raid"}
    st.vars = {"ch1_quests": 2}
    st.quests = {"q_herb": "done", "q_slime": "active"}
    st.quest_progress = {"q_slime": 3}
    st.chapter, st.chapter_title = 1, "出会いと旅立ち"
    st.map_id, st.x, st.y, st.dir = "town_bern", 20, 5, "left"
    st.once_events = {"forest_1:20:1:ch1_find_sword"}
    st.npc_state = {"forest_1:kai": {"hidden": True, "x": 19, "y": 2}}
    st.effects = {"tint": "night", "rain": "1", "fade": "in"}
    st.playtime = 3725.5
    st.pet = "slime"
    return st


# ---------------------------------------------------------------- 形式
def test_state_roundtrip(game):
    st = sample_state(game)
    st2 = state_from_dict(state_to_dict(st))
    assert state_to_dict(st2) == state_to_dict(st)
    assert st2.party[0].name == "ケン" and st2.party[0].status == ["poison"]
    assert st2.flags == {"found_sword", "ch1_raid"} and st2.npc_state["forest_1:kai"]["hidden"] is True


def test_old_save_missing_fields_uses_defaults():
    st = state_from_dict({"party": [], "gold": 5})
    assert st.gold == 5 and st.flags == set() and st.dir == "down" and st.pet == ""


def test_encrypted_and_not_readable(game):
    data = encode({"state": state_to_dict(sample_state(game))}, "firstquest")
    assert data.startswith(b"TRPGSAV")
    for plain in ("ケン".encode(), b"found_sword", b"town_bern", b"herb"):
        assert plain not in data
    assert decode(data, "firstquest")["state"]["gold"] == 123


def test_tamper_detected(game):
    data = bytearray(encode({"x": 1}, "firstquest"))
    data[-5] ^= 0x01
    with pytest.raises(SaveError, match="壊れている"):
        decode(bytes(data), "firstquest")


def test_other_scenario_rejected(game):
    data = encode({"x": 1}, "firstquest")
    with pytest.raises(SaveError, match="別のシナリオ"):
        decode(data, "otherquest")


def test_garbage_rejected():
    with pytest.raises(SaveError, match="セーブデータではありません"):
        decode(b"hello world, this is not a save file at all", "firstquest")


# ---------------------------------------------------------------- スロット
def test_slots(game, tmp_path):
    store = SaveStore("firstquest", "0.1.0", tmp_path)
    assert [i.exists for i in store.infos()] == [False] * 3 and not store.any_save()
    st = sample_state(game)
    store.save(2, st, "交易都市ベルン")
    info = store.info(2)
    assert info.ok and info.hero == "ケン" and info.chapter == 1 and info.map_name == "交易都市ベルン"
    assert "ケン Lv1" in info.label() and "01:02" in info.label()
    assert store.latest() == 2
    assert state_to_dict(store.load(2)) == state_to_dict(st)
    # 壊れたスロットは「読み込めません」と表示され、latest から外れる
    p = store.path(2)
    p.write_bytes(p.read_bytes()[:-3] + b"xyz")
    info = store.info(2)
    assert info.exists and not info.ok and "読み込めません" in info.label()
    assert store.latest() is None
    assert not list(tmp_path.rglob("*.tmp"))       # 一時ファイルは残らない


# ---------------------------------------------------------------- 画面から
def new_driver(game):
    d = Driver(game)
    for _ in range(4):
        d.key("ENTER")
    d.settle()
    return d


def open_system_save(d):
    d.key("ESC")
    m = d.scene
    assert isinstance(m, MenuScene)
    while TOP[m.views[0].list.index] != "システム":
        d.key("DOWN")
    d.key("ENTER")
    d.key("ENTER")                     # セーブ
    assert isinstance(d.scene, SaveLoadScene)
    return d.scene


def read_all(d, sc):
    out = []
    while d.scene is sc and sc.msg.active and sc.choice is None:
        out.append(" ".join(sc.msg.pages[sc.msg.page]))
        d.key("ENTER")
    return out


def test_save_from_menu_then_continue_from_title(game):
    d = new_driver(game)
    f = d.field
    f.st.gold = 77
    f.st.add_item("herb", 2)
    f.st.flags.add("test_flag")
    pos = (f.st.map_id, f.st.x, f.st.y)
    sc = open_system_save(d)
    assert "（空き）" in d.screen()
    d.key("ENTER")                     # スロット 1
    msgs = read_all(d, sc)
    assert any("スロット 1 にセーブしました" in m for m in msgs)
    assert isinstance(d.scene, MenuScene)

    # タイトルへ戻ると「つづきから」が選べ、カーソルもそこにある
    d.app.replace(TitleScene(game))
    t = d.scene
    assert t.items[1] == ("つづきから", True) and t.index == 1
    d.key("ENTER")
    assert isinstance(d.scene, SaveLoadScene) and "ユウ Lv1" in d.screen()
    d.key("ENTER")
    d.key("ENTER")                     # はい
    f2 = d.scene
    assert isinstance(f2, FieldScene) and f2 is not f
    assert (f2.st.map_id, f2.st.x, f2.st.y) == pos
    assert f2.st.gold == 77 and f2.st.items["herb"] == 2 and "test_flag" in f2.st.flags
    assert len(d.app._stack) == 1
    d.tick(0.5)
    assert not f2.busy                 # 自動イベントは起きない


def test_overwrite_asks(game):
    d = new_driver(game)
    sc = open_system_save(d)
    d.key("ENTER")                     # スロット 1 にセーブ
    read_all(d, sc)
    assert isinstance(d.scene, MenuScene)
    sc = d.app._stack[0].open_save()   # もう一度セーブ画面を開く（最後のスロットが選ばれている）
    assert sc.index == 0
    d.key("ENTER")
    assert sc.choice is not None and "上書きしますか" in " ".join(sc.msg.pages[0])
    d.key("DOWN")
    d.key("ENTER")                     # いいえ → 画面に残る
    assert d.scene is sc and not sc.closed


def test_save_point_only_blocks_menu_save(game):
    game.manifest.save = "save_point_only"
    d = new_driver(game)
    d.key("ESC")
    m = d.scene
    while TOP[m.views[0].list.index] != "システム":
        d.key("DOWN")
    d.key("ENTER")
    d.key("ENTER")
    assert isinstance(d.scene, MenuScene)
    assert "ここではセーブできない" in " ".join(m.msg.pages[0])


def test_save_point_command_resumes_script(game, sample_dir):
    sco = sample_dir / "scenario.sco"
    sco.write_text(sco.read_text(encoding="utf-8") + "\n*sp_test\n@save_point\nセーブのあと\n@end\n", encoding="utf-8")
    g = load_game(sample_dir)
    g.save_dir = game.save_dir
    d = new_driver(g)
    d.field.start_script("sp_test")
    sc = d.scene
    assert isinstance(sc, SaveLoadScene)
    d.key("ENTER")
    read_all(d, sc)
    d.tick(0.1)
    f = d.field
    assert f.msg.active and "セーブのあと" in " ".join(f.msg.pages[0])
    assert g.saves().info(1).ok


def test_on_load_label_runs(game, sample_dir):
    sco = sample_dir / "scenario.sco"
    text = sco.read_text(encoding="utf-8")
    assert "\n*on_load\n" in text                            # FirstQuest にもある → 先頭に一行足す
    sco.write_text(text.replace("\n*on_load\n", "\n*on_load\nおかえりなさい\n", 1), encoding="utf-8")
    g = load_game(sample_dir)
    g.save_dir = game.save_dir
    g.saves().save(1, sample_state(g), "ベルン")
    d = Driver(g)
    d.key("ENTER")
    d.key("ENTER")
    d.key("ENTER")
    f = d.field
    assert f.msg.active and "おかえりなさい" in " ".join(f.msg.pages[0])


def test_gameover_retry_loads_latest(game):
    store = game.saves()
    st = sample_state(game)
    st.party = st.party[:1]
    st.party[0].hp = 30
    store.save(3, st, "ベルン")
    d = new_driver(game)
    d.app.push(GameOverScene(game, "choose"))
    d.tick(1.5)
    d.key("ENTER")                     # セーブからやり直す
    f = d.scene
    assert isinstance(f, FieldScene) and f.st.map_id == "town_bern" and f.st.gold == 123
    assert len(d.app._stack) == 1


def test_gameover_retry_without_save(game):
    d = new_driver(game)
    d.app.push(GameOverScene(game, "choose"))
    d.tick(1.5)
    d.key("ENTER")
    assert isinstance(d.scene, GameOverScene) and "セーブデータがありません" in d.scene.notice
    d.key("ENTER")
    assert isinstance(d.scene, TitleScene)


def test_gameover_label_runs_before_screen(game, sample_dir):
    sco = sample_dir / "scenario.sco"
    sco.write_text(sco.read_text(encoding="utf-8") + "\n*gameover\nまだ終わりではない……\n@end\n", encoding="utf-8")
    g = load_game(sample_dir)
    g.save_dir = game.save_dir
    d = new_driver(g)
    f = d.field
    b = f.start_battle("slime_2")
    for m in f.st.party:
        m.hp = 0
    b.battle.result = "lose"
    b.closed = True
    d.app.pop()
    f.encounter = b
    d.tick(0.1)
    assert f.msg.active and "まだ終わりではない" in " ".join(f.msg.pages[0])
    d.key("ENTER")
    d.key("ENTER")
    d.tick(0.1)
    assert isinstance(d.scene, GameOverScene)
