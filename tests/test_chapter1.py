"""1章を最初から最後まで通しでプレイするテスト（実際の画面にキーを送る）。

戦闘（村の襲撃・ランダムエンカウント）は Driver.fight で自動的に戦って勝つ。乱数は固定。
"""
import pytest

from test_play import Driver, _seed  # noqa: F401  （_seed: 乱数を固定する autouse fixture）
from trpg.scenes.battle import BattleScene
from trpg.game import load_game
from trpg.scenes.facility import Overlay
from trpg.scenes.field import FieldScene


@pytest.fixture
def game(sample_dir):
    g = load_game(sample_dir)
    yield g
    g.close()


class Play(Driver):
    def settle(self, max_presses: int = 200, choose: int = 0) -> list[str]:
        """フィールドの会話を進める。施設などの重ね画面が開いたらそこで止まる。"""
        seen: list[str] = []
        for _ in range(max_presses):
            if isinstance(self.scene, BattleScene):
                assert self.fight() != "lose", "戦闘に負けた"
                continue
            if not isinstance(self.scene, FieldScene):
                return seen
            f = self.scene
            assert f.error is None, f.error
            self.tick(0.3)
            if isinstance(self.scene, BattleScene):
                continue
            if not isinstance(self.scene, FieldScene):
                return seen
            if f.choice is not None:
                for _ in range(choose):
                    self.key("DOWN")
                self.key("ENTER")
                continue
            if f.msg.active:
                page = " ".join(f.msg.pages[f.msg.page])
                if not seen or seen[-1] != page:
                    seen.append(page)
                self.key("ENTER")
                continue
            if f.busy or f.effects.active:
                self.key("ENTER")
                continue
            return seen
        raise AssertionError("終わらない: " + " / ".join(seen[-3:]))

    def ov(self) -> Overlay:
        assert isinstance(self.scene, Overlay), type(self.scene)
        return self.scene

    def ov_read(self) -> list[str]:
        """重ね画面の会話を選択肢が出るか閉じるまで読み進める。"""
        seen = []
        for _ in range(50):
            sc = self.scene
            if not isinstance(sc, Overlay) or sc.choice is not None:
                return seen
            if sc.msg.active:
                seen.append(" ".join(sc.msg.pages[sc.msg.page]))
                self.key("ENTER")
                continue
            return seen
        raise AssertionError("重ね画面が進まない")

    def ov_choose(self, i: int) -> None:
        sc = self.ov()
        if sc.choice is None and getattr(sc, "mode", "").startswith("qty_"):
            self.key("ENTER")                    # ショップの個数（1 個のまま決定）
        assert sc.choice is not None, "選択肢が出ていない"
        for _ in range(i):
            self.key("DOWN")
        self.key("ENTER")

    def ov_pick(self, name: str) -> None:
        """リストから名前で選んで決定。"""
        sc = self.ov()
        rows = [r[0] for r in sc.list.rows]
        idx = next(i for i, r in enumerate(rows) if name in r)
        while sc.list.index != idx:
            self.key("DOWN")
        self.key("ENTER")

    def talk(self, x: int, y: int, face: str, choose: int = 0) -> list[str]:
        """(x, y) に立って face 向きに話しかけ、会話を最後まで読む（重ね画面が開いたらそこで止まる）。"""
        self.walk_to(x, y)
        self.field.st.dir = face
        self.key("ENTER")
        return self.settle(choose=choose)

    def back_to_field(self) -> list[str]:
        """重ね画面が閉じたあとのスクリプトの続きを読む。"""
        assert isinstance(self.scene, FieldScene)
        self.tick(0.1)
        return self.settle()


def test_chapter1_full_playthrough(game):
    d = Play(game)
    d.key("ENTER")
    d.key("ENTER")                       # 名前はユウのまま
    d.key("ENTER")
    d.key("ENTER")
    d.settle()
    f = d.field

    # ---- 1-1 森で剣を拾う（詳細は test_play で確認済み）
    d.walk_to(5, 7)
    d.settle()
    d.walk_to(15, 0)
    d.settle()
    d.walk_to(20, 2)
    f.st.dir = "up"
    d.key("ENTER")
    d.settle()
    assert "ch1_raid" in f.st.flags and f.st.map_id == "house_hero"
    assert f.st.hero.stat("atk", game.data) == 8 + 5          # 錆びた剣の分

    # ---- 1-2 襲撃 → 村長の家 → 別れ
    d.walk_to(5, 7)                      # 外に出ると襲撃
    talk = d.settle()
    j = " ".join(talk)
    assert "{hero}だけ" not in j and "ユウだけを見てないか" in j
    assert "ch1_raid_done" in f.st.flags and f.st.effects.get("rain") == "1"
    assert not f.npc_visible(f._find_npc("wolf1"))

    gold0, herb0 = f.st.gold, f.st.items.get("herb", 0)
    d.walk_to(14, 4)                     # 村長の家へ
    assert f.st.map_id == "house_chief"
    talk = d.settle(choose=1)
    j = " ".join(talk)
    assert "村を出てくれんか" in j and "わかっておるのじゃ" in j
    assert "南の空へ流れていった" in j
    assert "ch1_farewell" in f.st.flags and f.st.gold == gold0 + 50
    assert f.st.hero.equip["armor"] == "traveler_clothes"
    assert f.st.items["herb"] == herb0 + 3      # 母から
    assert f.st.effects.get("rain") == "off"
    assert (f.st.map_id, f.st.x, f.st.y) == ("village_lito", 15, 15)

    talk = d.talk(14, 15, "down")        # 門のカイ
    assert any("手紙くらい寄こせ" in t for t in talk)

    # ---- 1-3 街道
    d.walk_to(15, 17)
    d.settle()
    assert f.st.map_id == "field_road" and "ch1_left_village" in f.st.flags
    d.walk_to(15, 0)                     # 村へは戻れない
    d.settle()
    assert f.st.map_id == "field_road" and f.st.y == 1

    d.walk_to(7, 9)                      # 先に着いてから所持金を控える（道中の戦闘で変わるので）
    gold0, herb0 = f.st.gold, f.st.items.get("herb", 0)
    d.talk(7, 9, "left")                 # 旅の商人 → ショップ
    d.ov_read()
    d.ov_choose(0)                       # かう
    d.ov_pick("やくそう")
    d.ov_choose(0)                       # はい
    d.ov_read()
    d.key("ESC")                         # リスト → 最初の選択肢
    d.ov_choose(2)                       # やめる
    d.ov_read()
    d.back_to_field()
    assert f.st.gold == gold0 - 8 and f.st.items["herb"] == herb0 + 1

    # ---- ベルン
    d.walk_to(15, 17)
    assert f.st.map_id == "town_bern"
    talk = d.settle()
    assert "ch1_gate_talked" in f.st.flags

    talk = d.talk(17, 9, "up")           # パン屋の娘：協会の場所
    assert "ch1_know_guild" in f.st.flags and f.st.items.get("bread") == 1

    # 道具屋でやくそうを 3 個以上に（道中の戦闘で使っているかもしれないので）
    d.talk(14, 11, "up")
    d.ov_read()
    d.ov_choose(0)
    while f.st.items.get("herb", 0) < 3:
        d.ov_pick("やくそう")
        d.ov_choose(0)
        d.ov_read()
    d.key("ESC")
    d.ov_choose(2)
    d.ov_read()
    d.back_to_field()

    d.walk_to(7, 7)                      # 協会へ
    assert f.st.map_id == "guild_bern"
    gold0, herb0 = f.st.gold, f.st.items["herb"]
    assert herb0 >= 3
    talk = d.talk(10, 4, "up")           # セラ：登録 → 協会画面
    assert "guild_registered" in f.st.flags
    d.ov_read()
    d.ov_choose(0)                       # 依頼を受ける
    for name in ("やくそう集め", "迷子の猫", "荷物の配達"):
        d.ov_pick(name)
        d.ov_choose(0)                   # 受ける
        d.ov_read()
        d.ov_choose(0)                   # 依頼を受ける（もう一度）
    d.key("ESC")
    d.ov_choose(1)                       # 依頼を報告する
    d.ov_pick("やくそう集め")
    msgs = d.ov_read()
    assert any("依頼「やくそう集め」を達成した" in m for m in msgs)
    d.ov_choose(3)                       # やめる
    d.ov_read()
    d.back_to_field()
    assert f.st.quests["q_herb"] == "done" and f.st.vars.get("ch1_quests") == 1
    assert f.st.items.get("herb", 0) == herb0 - 3 and f.st.gold == gold0 + 30

    # 迷子の猫
    d.walk_to(10, 9)
    assert f.st.map_id == "town_bern"
    talk = d.talk(3, 21, "left")
    assert "found_cat" in f.st.flags
    # 荷物の配達
    d.talk(14, 11, "up")
    assert "got_package" in f.st.flags
    d.walk_to(31, 6)
    assert f.st.map_id == "bern_inn"
    d.talk(7, 4, "up")
    assert "package_delivered" in f.st.flags and "package" not in f.st.items

    gold0 = f.st.gold
    # 報告（2 件）
    d.walk_to(7, 7)
    d.walk_to(31, 7)
    d.walk_to(7, 7)
    assert f.st.map_id == "guild_bern"
    d.talk(10, 4, "up")
    d.ov_read()
    d.ov_choose(1)
    d.ov_pick("迷子の猫")
    d.ov_read()
    d.ov_choose(1)
    d.ov_pick("荷物の配達")
    d.ov_read()
    d.ov_choose(3)
    d.ov_read()
    talk = d.back_to_field()
    assert f.st.vars.get("ch1_quests") == 3
    assert any("少しお話があるので" in t for t in talk)
    assert f.st.items.get("cat_collar") == 1
    assert f.st.gold == gold0 + 40 + 30

    # ---- 仲間選び → 1章 完
    gold0 = f.st.gold
    d.talk(10, 4, "up")                  # セラ → 紹介
    d.settle()                           # 選択肢「紹介してもらう」で @recruit が開く
    d.ov_read()
    d.ov_pick("ミア")
    d.ov_choose(0)
    d.ov_read()
    talk = d.back_to_field()
    # 1章の最後でセーブ画面が開く → スロット 1 にセーブ
    from trpg.scenes.saveload import SaveLoadScene
    sc = d.scene
    assert isinstance(sc, SaveLoadScene)
    d.key("ENTER")
    while d.scene is sc:
        d.key("ENTER")
    assert game.saves().info(1).ok
    talk += d.back_to_field()
    j = " ".join(talk)
    assert "その剣の紋章" in j
    assert f.st.gold == gold0 - 100
    assert [m.id for m in f.st.party] == ["hero", "mia"]
    assert "ch1_done" in f.st.flags
    assert "数日後" in j and "ch2_rumor" in f.st.flags      # そのまま第2章へ
    assert f.st.chapter == 2 and f.st.quests["q_mole"] == "active"
