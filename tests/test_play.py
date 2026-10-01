"""通しプレイのテスト：端末を使わずに実際の画面（シーン）へキーを送り、1章冒頭を最後まで進める。"""
from collections import deque

import pytest

from trpg.app import App
from trpg.game import load_game
from trpg.scenes.battle import BattleScene
from trpg.scenes.field import DIR_VEC, FieldScene
from trpg.scenes.title import TitleScene
from trpg.term import Buffer, Key, KeyEvent
from trpg.term.buffer import CONT


class Driver:
    def __init__(self, game, w=100, h=30):
        self.app = App(TitleScene(game))
        self.app.running = True
        self.w, self.h = w, h

    @property
    def scene(self):
        return self.app.scene

    def key(self, k: str) -> None:
        ev = KeyEvent(Key[k]) if k in Key.__members__ and len(k) > 1 else KeyEvent(Key.CHAR, k)
        self.scene.on_key(ev, self.app.keymap.actions(ev))
        self.tick(0.05)

    def tick(self, secs: float, step: float = 1 / 30) -> None:
        t = 0.0
        while t < secs:
            self.scene.update(step)
            t += step

    def screen(self) -> str:
        buf = Buffer(self.w, self.h)
        self.scene.draw(buf)
        return "\n".join("".join(c[0] for c in row if c[0] != CONT) for row in buf.rows)

    # ---- 戦闘 ----
    def fight(self, max_keys: int = 2000) -> str:
        """戦闘画面を自動で進める：先頭の敵を攻撃、HP が 1/3 を切ったらやくそう。結果を返す。"""
        b = self.scene
        assert isinstance(b, BattleScene)
        for _ in range(max_keys):
            if self.scene is not b:
                return b.battle.result
            if b.mode == "command":
                a = b.actor
                if a.hp * 3 < a.max_hp and b.st.items.get("herb"):
                    labels = [l for l, _ in b._menu()]
                    while labels[b.menu_i] != "どうぐ":
                        self.key("DOWN")
                    self.key("ENTER")
                    while b.list_items[b.list_i][3].id != "herb":
                        self.key("DOWN")
                    self.key("ENTER")
                    while b.targets[b.target_i] is not a:
                        self.key("RIGHT")
                    self.key("ENTER")
                else:
                    while b.menu_i != 0:
                        self.key("UP")
                    self.key("ENTER")        # たたかう
                    self.key("ENTER")        # 先頭の敵
            else:
                self.key("ENTER")
                self.tick(0.2)
        raise AssertionError("戦闘が終わらない")

    # ---- フィールド用 ----
    @property
    def field(self) -> FieldScene:
        assert isinstance(self.scene, FieldScene), type(self.scene)
        return self.scene

    def settle(self, max_presses: int = 200, choose: int = 0) -> list[str]:
        """スクリプト・会話が終わるまで決定キーを押し続け、表示された会話を返す。"""
        seen = []
        for _ in range(max_presses):
            if isinstance(self.scene, BattleScene):
                assert self.fight() != "lose", "戦闘に負けた"
                continue
            f = self.field
            assert f.error is None, f.error
            self.tick(0.3)
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
                self.key("ENTER")  # typewriter などのキー待ち
                continue
            return seen
        raise AssertionError("終わらない: " + " / ".join(seen[-3:]))

    def walk_to(self, tx: int, ty: int) -> None:
        """BFS で経路を探して歩く。途中の会話・戦闘通知は閉じて続行する。"""
        names = {(0, -1): "UP", (0, 1): "DOWN", (-1, 0): "LEFT", (1, 0): "RIGHT"}
        start_map = self.field.st.map_id
        for _ in range(400):
            if isinstance(self.scene, BattleScene):
                assert self.fight() != "lose", "戦闘に負けた"
                continue
            f = self.field
            if (f.st.x, f.st.y) == (tx, ty) or f.st.map_id != start_map:
                return  # 到着、またはワープでマップが変わった
            if f.busy:
                self.settle()
                continue
            start = (f.st.x, f.st.y)
            prev = {start: None}
            q = deque([start])
            while q:
                cur = q.popleft()
                if cur == (tx, ty):
                    break
                for dx, dy in DIR_VEC.values():
                    nxt = (cur[0] + dx, cur[1] + dy)
                    ok = nxt == (tx, ty) or (f.passable(*nxt) and not f.npc_at(*nxt)
                                             and not any((w.x, w.y) == nxt for w in f.map.warps))
                    if nxt not in prev and ok and f.map.in_bounds(*nxt):
                        prev[nxt] = cur
                        q.append(nxt)
            assert (tx, ty) in prev, f"{f.st.map_id}: ({tx},{ty}) へ行けない"
            node = (tx, ty)
            while prev[node] != start:
                node = prev[node]
            self.key(names[(node[0] - start[0], node[1] - start[1])])
        raise AssertionError("到着できない")


@pytest.fixture(autouse=True)
def _seed():
    import random
    random.seed(12345)


@pytest.fixture
def game(sample_dir):
    g = load_game(sample_dir)
    yield g
    g.close()


def test_chapter1_opening_playthrough(game):
    d = Driver(game)
    assert "はじめから" in d.screen()

    d.key("ENTER")                      # はじめから → 名前入力
    assert "主人公の名前" in d.screen()
    for _ in range(2):
        d.key("BACKSPACE")
    for ch in "ケン":
        d.key(ch)
    d.key("ENTER")

    f = d.field
    assert f.st.hero.name == "ケン"
    d.key("ENTER")                      # 章タイトル（typewriter）を表示しきる
    d.key("ENTER")                      # 閉じる
    talk = d.settle()
    assert any("窓から朝の光" in t for t in talk)
    assert (f.st.map_id, f.st.x, f.st.y) == ("house_hero", 4, 3)
    assert f.st.chapter == 1

    # 母と話す → やくそう 2 個
    d.walk_to(8, 3)
    f.st.dir = "up"
    d.key("ENTER")
    talk = d.settle()
    assert f.st.items.get("herb") == 2 and "got_herbs" in f.st.flags

    # 家を出る → カイの誘い（auto イベント、選択肢 2 番目）
    d.walk_to(5, 7)
    assert f.st.map_id == "village_lito"
    talk = d.settle(choose=1)
    assert any("ちょっとだけだって" in t for t in talk), talk
    assert "ch1_invited" in f.st.flags

    # 南の出口は通れない
    d.walk_to(15, 17)
    d.settle()
    assert f.st.y == 16

    # 北の出口 → 森
    d.walk_to(15, 0)
    assert f.st.map_id == "forest_1"
    talk = d.settle()
    assert "lost_friend" in f.st.flags
    assert f.st.effects.get("tint") == "night"
    assert not f.npc_visible(f._find_npc("kai"))

    # 祠を調べる → 剣 → 再会 → 家族団らん
    d.walk_to(20, 2)
    f.st.dir = "up"
    d.key("ENTER")
    talk = d.settle()
    joined = " ".join(talk)
    assert "錆びた剣を手に入れた" in joined
    assert "ケン！！" in joined                     # {hero} の置き換え
    assert "刃筋はまっすぐだ" in joined
    assert "found_sword" in f.st.flags and "ch1_family_done" in f.st.flags
    assert f.st.hero.equip.get("weapon") == "rusty_sword" and "rusty_sword" not in f.st.items
    assert f.st.map_id == "house_hero"
    assert f.st.effects.get("tint") == "none" and f.st.effects.get("fade") == "in"

    screen = d.screen()
    assert "ケンの家" in screen                     # マップ名の {hero}
    assert "＠" in screen


def test_system_menu_back_to_title(game):
    d = Driver(game)
    d.key("ENTER")
    d.key("ENTER")
    d.key("ENTER")
    d.key("ENTER")
    d.settle()
    d.key("ESC")
    assert "メニュー" in d.screen() and "システム" in d.screen()
    for _ in range(5):
        d.key("DOWN")
    d.key("ENTER")                       # システム
    assert "タイトルにもどる" in d.screen()
    d.key("DOWN")
    d.key("ENTER")                       # タイトルにもどる
    d.key("ENTER")                       # はい
    assert isinstance(d.scene, TitleScene)


def test_script_runtime_error_is_shown(game, sample_dir):
    d = Driver(game)
    d.key("ENTER")
    d.key("ENTER")
    f = d.field
    f.vm.stop()
    f.req = None
    f.effects.active.clear()
    f.start_script("no_such_label")
    assert f.error and "no_such_label" in f.error
    assert "エラー" in d.screen()
    d.key("ENTER")
    assert f.error is None


def test_chief_is_in_one_place_only(game):
    """襲撃の前は村長は外だけ、襲撃のあとは家の中だけにいる（同時に 2 か所に出ない）。"""
    d = Driver(game)
    for _ in range(4):
        d.key("ENTER")
    d.settle()
    f = d.field
    gd = game.data

    def visible(map_id, npc_id):
        f._set_map(map_id)
        npc = next(n for n in gd.maps[map_id].npcs if n.id == npc_id)
        return f.npc_visible(npc)

    assert visible("village_lito", "chief") and not visible("house_chief", "chief_in")
    assert visible("house_chief", "chief_wife")
    f.st.flags.add("ch1_raid")
    assert not visible("village_lito", "chief") and visible("house_chief", "chief_in")
