"""フィールド画面：マップ移動・NPC・ワープ・イベント・会話・スクリプト実行（基本設計 2.1 / 4.3 / 4.4）。"""
from __future__ import annotations

import random
from typing import Callable, Optional

from ..app import Scene
from ..data.models import GameMap, MapEvent, Npc
from ..effects import Effect, EffectManager, Fade
from ..game import Game
from ..script.expr import ExprError, evaluate, parse_expr
from ..script.parser import Instr
from ..script.vm import VM, ChoiceReq, KeyWaitReq, MessageReq, ScriptError, WaitReq
from ..term import Action, Buffer, Key, KeyEvent, Rect, Style, pad, truncate, wrap, text_width
from ..term.buffer import BOX_SINGLE
from ..ui import markup
from ..ui.aa import draw_aa
from ..ui.widgets import FRAME, ChoiceWindow, MessageWindow
from ..world import quests as Q
from ..world.state import GameState, format_text

DIR_VEC = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
ACTION_DIR = {Action.UP: "up", Action.DOWN: "down", Action.LEFT: "left", Action.RIGHT: "right"}
HERO_GLYPH = "＠"
DARK_RADIUS = 3
BANNER_SECONDS = 2.0
NPC_STEP_INTERVAL = (1.2, 3.0)
ROUTE_STEP_INTERVAL = 0.6        # 道順で歩く NPC の 1 歩の間隔（秒）


def straight_steps(dx: int, dy: int) -> list[tuple[int, int]]:
    """横→縦の順にまっすぐ進む手順（経路が見つからないときの予備）。"""
    sx = 1 if dx > 0 else -1
    sy = 1 if dy > 0 else -1
    return [(sx, 0)] * abs(dx) + [(0, sy)] * abs(dy)


class Mover:
    """NPC・主人公を 1 マスずつ動かす演出（@npc move / @hero move）。"""

    def __init__(self, get: Callable[[], tuple[int, int]], put: Callable[[int, int], None],
                 dx: int, dy: int, step: float = 0.15, steps: Optional[list[tuple[int, int]]] = None):
        self.get, self.put = get, put
        self.steps: list[tuple[int, int]] = list(steps) if steps is not None else straight_steps(dx, dy)
        self.step = step
        self.t = 0.0

    on_done: Optional[Callable[[], None]] = None

    @property
    def done(self) -> bool:
        return not self.steps

    def update(self, dt: float) -> None:
        self.t += dt
        while self.steps and self.t >= self.step:
            self.t -= self.step
            mx, my = self.steps.pop(0)
            x, y = self.get()
            self.put(x + mx, y + my)
        if not self.steps and self.on_done is not None:
            cb, self.on_done = self.on_done, None
            cb()


class FieldScene(Scene):
    PANEL_W = 34
    MSG_H = 5

    def __init__(self, game: Game, state: GameState):
        self.game = game
        self.gd = game.data
        self.st = state
        self.effects = EffectManager(state.effects)
        self.vm = VM(game.script, state, game.data, self)
        self.msg = MessageWindow()
        self.choice: Optional[ChoiceWindow] = None
        self.choice_cb: Optional[Callable[[int], None]] = None
        self.req: Optional[object] = None
        self.wait_left = 0.0
        self.error: Optional[str] = None
        self.overlays: dict[str, tuple[list[str], int, int]] = {}
        self.pending_auto = True
        self.after_script: Optional[str] = None
        self.pending_labels: list[str] = []   # 依頼達成などで後から実行するスクリプト
        self.background_movers: list[Mover] = []   # wait=false で動かしている演出移動
        self.face: Optional[list[str]] = None      # 会話窓の上に出す顔 AA（@face）
        self._map_area_size = (64, 23)
        self.encounter = None                  # ランダムエンカウントの戦闘画面
        self._when_cache: dict[str, object] = {}
        self._npc_timer: dict[str, float] = {}
        self.enc_left = 0
        self.map: Optional[GameMap] = None
        self.banner = ""                       # ダンジョンの階に入ったときに出すマップ名
        self.banner_left = 0.0
        if state.map_id:
            self._set_map(state.map_id)

    # ============================================================ スクリプト
    def start_script(self, label: str) -> None:
        try:
            self.vm.start(label)
        except ScriptError as e:
            self._script_error(e)
            return
        self._advance()

    def _advance(self) -> None:
        try:
            req = self.vm.step()
        except ScriptError as e:
            self._script_error(e)
            return
        self._handle(req)

    def _handle(self, req: Optional[object]) -> None:
        self.req = req
        if req is None:
            self.msg.close()
            self.choice = None
            self._script_finished()
        elif isinstance(req, MessageReq):
            self.msg.open(req.lines)
        elif isinstance(req, ChoiceReq):
            self.choice = ChoiceWindow([markup.strip(o) for o in req.options])
            self.choice_cb = None
            if self.msg.active:
                self.msg.shown = 10 ** 6   # 質問文は全部表示しておく
        elif isinstance(req, WaitReq):
            self.wait_left = req.seconds

    def _show_gameover(self, mode: str) -> None:
        from .gameover import GameOverScene
        self.app.push(GameOverScene(self.game, mode))

    def _script_finished(self) -> None:
        self.face = None                      # 顔はスクリプトが終わったら消す
        if self.after_script and self.after_script.startswith("gameover:"):
            mode = self.after_script.split(":", 1)[1]
            self.after_script = None
            self._show_gameover(mode)
            return
        if self.after_script == "title":
            self.after_script = None
            self.back_to_title()
            return
        if self.map is None:
            self.error = ("開始スクリプトでマップが設定されていません。\n"
                          f"*{self.game.manifest.start_label} の中で @map を実行してください。")

    def _script_error(self, e: ScriptError) -> None:
        self.vm.stop()
        self.req = None
        self.msg.close()
        self.choice = None
        self.error = f"スクリプトの実行エラー\n{e}"

    def local_message(self, text: str) -> None:
        """スクリプト外から会話窓を出す（スクリプト実行中でなければ閉じたら終わり）。"""
        self._handle(MessageReq([("", text)]))

    # ------------------------------------------------------------ Host（VM から呼ばれる）
    def exec_cmd(self, ins: Instr) -> Optional[object]:
        a = ins.args
        name, pos, kw = a["name"], a["pos"], a["kw"]
        if name == "map":
            return self.change_map(pos[0], int(pos[1]), int(pos[2]), kw.get("dir"), kw.get("transition", "none"))
        if name == "npc":
            return self._cmd_npc(ins, pos)
        if name == "hero":
            if pos[0] == "face":
                self.st.dir = pos[1]
                return None
            dx, dy = int(pos[1]), int(pos[2])
            path = self.find_path((self.st.x, self.st.y), (self.st.x + dx, self.st.y + dy))
            return Mover(lambda: (self.st.x, self.st.y), self._put_hero, dx, dy, steps=path)
        if name == "effect":
            return self._effect(ins, pos[0], pos[1:], kw)
        if name == "face":
            if pos[0] == "none":
                self.face = None
                return None
            path = self.gd.face_path(pos[0], self.game.package.exists)
            if path is None:
                raise ScriptError(ins, f"@face：「{pos[0]}」の顔 AA が見つかりません")
            self.face = self._aa_lines(path)
            return None
        if name == "aa":
            if pos[0] == "show":
                self.overlays[kw.get("name", pos[1])] = (self._aa_lines(pos[1]), int(pos[2]), int(pos[3]))
            else:
                self.overlays.pop(pos[1], None)
            return None
        if name == "battle":
            return self.start_battle(kw["group"], escape=kw.get("escape", "true") != "false",
                                     gameover=kw.get("gameover", ""), target_only=kw.get("target_only", ""),
                                     lose=kw.get("lose", ""), from_script=True,
                                     members=kw["members"].split(",") if kw.get("members") else None,
                                     turns=int(kw.get("turns", 0)))
        if name in ("shop", "inn", "guild", "recruit"):
            return self._open_facility(name, pos, kw)
        if name == "save_point":
            return self.open_save()
        if name == "ending":
            from .ending import EndingScene
            self.after_script = "title"            # エンディング画面を閉じたらタイトルへ
            scene = EndingScene(self, kw.get("text", ""))
            self.app.push(scene)
            return scene
        return MessageReq([("", f"（@{name} は未実装です）")])

    def _open_facility(self, name: str, pos: list[str], kw: dict):
        from .facility import GuildScene, InnScene, RecruitScene, ShopScene
        if name == "shop":
            ov = ShopScene(self, pos[0])
        elif name == "inn":
            ov = InnScene(self, int(pos[0]))
        elif name == "guild":
            ov = GuildScene(self)
        else:
            ov = RecruitScene(self, pos, int(kw.get("pick", 1)), lv=kw.get("lv", ""))
        self.app.push(ov)
        return ov

    # ------------------------------------------------------------ 戦闘
    def start_battle(self, group: str, *, escape: bool = True, gameover: str = "", target_only: str = "",
                     lose: str = "", from_script: bool = False, members: Optional[list[str]] = None,
                     turns: int = 0):
        from .battle import BattleScene
        if group not in self.gd.groups:
            raise ScriptError(None, f"敵グループ「{group}」が定義されていません")
        b = BattleScene(self, group, escape=escape, gameover=gameover, target_only=target_only,
                        lose=lose, from_script=from_script, members=members, turns=turns)
        if not from_script:
            self.encounter = b
        self.app.push(b)
        return b

    def _after_battle(self, b) -> None:
        """戦闘画面が閉じたあと。負けたら負けイベントへ、またはゲームオーバー。"""
        result = b.battle.result
        if result == "timeout":
            # turns= のターン数がたった：負けイベントがあればそこへ、なければスクリプトの続きへ
            result = "lose" if b.lose_label else "escape"
        if result == "lose":
            if b.lose_label:
                for m in self.st.party:          # 負けイベント：倒れた仲間は HP 1 で起き上がる
                    m.hp = max(1, m.hp)
                    m.status.clear()
                try:
                    self.vm.jump(b.lose_label)
                except ScriptError as e:
                    self._script_error(e)
                    return
                self._advance()
                return
            self.vm.stop()
            self.req = None
            self.msg.close()
            self.choice = None
            mode = b.gameover or self.game.manifest.gameover
            if self.vm.has_label("gameover"):
                # *gameover があれば先に実行し、終わったら全滅画面へ
                self.after_script = "gameover:" + mode
                self.start_script("gameover")
                return
            self._show_gameover(mode)
            return
        if b.from_script:
            self._advance()

    # ------------------------------------------------------------ エフェクト（マップ上の物を動かすもの）
    def _aa_lines(self, path: str) -> list[str]:
        lines = self.gd.aa.get(path)
        if lines is None:
            text = self.game.package.read_text(path) or ""
            lines = text.splitlines()          # CRLF（Windows で保存したファイル）にも対応
        return lines

    def _effect(self, ins: Instr, name: str, pos: list[str], kw: dict):
        """@effect。move / aa_show / aa_hide はここで、それ以外は EffectManager で処理する。"""
        wait = kw.get("wait", "true") != "false"
        step = max(10, int(kw.get("ms", 150))) / 1000            # 1 マス（1 セル）あたりの時間
        if name == "move":
            target = kw.get("target", pos[0] if pos else "")
            nums = [int(p) for p in (pos[1:] if "target" not in kw else pos) if p.lstrip("-").isdigit()]
            if len(nums) < 2:
                raise ScriptError(ins, "@effect move には 対象 dx dy を指定してください")
            dx, dy = nums[0], nums[1]
            if target in self.overlays:                          # AA：セル単位でなめらかに動かす
                lines, x, y = self.overlays[target]

                def put(nx: int, ny: int, t=target) -> None:
                    ln, _, _ = self.overlays[t]
                    self.overlays[t] = (ln, nx, ny)
                mv = Mover(lambda t=target: self.overlays[t][1:], put, dx, dy, step=step)
            elif target == "hero":
                path = self.find_path((self.st.x, self.st.y), (self.st.x + dx, self.st.y + dy))
                mv = Mover(lambda: (self.st.x, self.st.y), self._put_hero, dx, dy, step=step, steps=path)
            else:
                npc = self._find_npc(target)
                if npc is None:
                    raise ScriptError(ins, f"@effect move：「{target}」という NPC・AA がいません")
                s = self.st.npc(self.st.map_id, npc.id)
                x, y = self._npc_pos(npc)
                path = self.find_path((x, y), (x + dx, y + dy), mover=npc)
                mv = Mover(lambda: self._npc_pos(npc), lambda nx, ny: s.update(x=nx, y=ny), dx, dy,
                           step=step, steps=path)
            if wait:
                return mv
            self.background_movers.append(mv)
            return None
        if name == "aa_show":
            if len(pos) < 3:
                raise ScriptError(ins, "@effect aa_show には ファイル x y を指定してください")
            lines = self._aa_lines(pos[0])
            x, y = int(pos[1]), int(pos[2])
            key = kw.get("name", pos[0])
            src = kw.get("from", "")
            if not src:
                self.overlays[key] = (lines, x, y)
                return None
            sx, sy = self._offscreen(lines, x, y, src)
            self.overlays[key] = (lines, sx, sy)
            return self._slide(key, x - sx, y - sy, step / 4, wait)
        if name == "aa_hide":
            key = kw.get("name", pos[0] if pos else "")
            if key not in self.overlays:
                return None
            to = kw.get("to", "")
            if not to:
                self.overlays.pop(key, None)
                return None
            lines, x, y = self.overlays[key]
            ex, ey = self._offscreen(lines, x, y, to)
            return self._slide(key, ex - x, ey - y, step / 4, wait, remove=True)
        if name == "scroll_text":
            if "file" in kw:
                text = self.game.package.read_text(kw["file"])
                if text is None:
                    raise ScriptError(ins, f"@effect scroll_text：ファイル「{kw['file']}」がありません")
                kw = dict(kw, _lines=[format_text(ln, self.st, self.gd) for ln in text.splitlines()])
        return self.effects.start(name, pos, kw)

    def _offscreen(self, lines: list[str], x: int, y: int, side: str) -> tuple[int, int]:
        """AA を画面（マップ表示領域）の外に出した位置。"""
        from ..term import text_width
        w = max((text_width(ln) for ln in lines), default=0)
        h = len(lines)
        W, H = self._map_area_size
        return {"left": (-w, y), "right": (W, y), "top": (x, -h), "bottom": (x, H)}.get(side, (x, y))

    def _slide(self, key: str, dx: int, dy: int, step: float, wait: bool, remove: bool = False):
        def get(k=key):
            return self.overlays[k][1:] if k in self.overlays else (0, 0)

        def put(nx: int, ny: int, k=key) -> None:
            if k in self.overlays:
                ln, _, _ = self.overlays[k]
                self.overlays[k] = (ln, nx, ny)

        mv = Mover(get, put, dx, dy, step=step)
        if remove:
            mv.on_done = lambda k=key: self.overlays.pop(k, None)
        if wait:
            return mv
        self.background_movers.append(mv)
        return None

    def open_save(self):
        from .saveload import SaveLoadScene
        sc = SaveLoadScene(self.game, "save", field=self)
        self.app.push(sc)
        return sc

    def _cmd_npc(self, ins: Instr, pos: list[str]) -> Optional[object]:
        npc = self._find_npc(pos[0])
        if npc is None:
            raise ScriptError(ins, f"現在のマップ（{self.st.map_id}）に NPC「{pos[0]}」がいません")
        s = self.st.npc(self.st.map_id, npc.id)
        act = pos[1]
        if act in ("show", "hide"):
            s["hidden"] = act == "hide"
        elif act == "face":
            s["dir"] = pos[2]
        elif act == "move":
            dx, dy = int(pos[2]), int(pos[3])
            x, y = self._npc_pos(npc)
            path = self.find_path((x, y), (x + dx, y + dy), mover=npc)
            return Mover(lambda: self._npc_pos(npc), lambda x, y: s.update(x=x, y=y), dx, dy, steps=path)
        return None

    def find_path(self, start: tuple[int, int], goal: tuple[int, int],
                  mover: Optional[Npc] = None) -> Optional[list[tuple[int, int]]]:
        """木・壁・ほかの人を避けた最短の手順（BFS）。着けなければ None（呼び出し側はまっすぐ進む）。

        mover が NPC なら主人公のいるマスも避ける。動く本人のマスは通ってよい。
        """
        if self.map is None or start == goal:
            return [] if start == goal else None
        hero = (self.st.x, self.st.y)

        def free(p: tuple[int, int]) -> bool:
            if not self.passable(*p):
                return False
            if mover is not None and p == hero:
                return False
            n = self.npc_at(*p)
            return n is None or n is mover

        if not free(goal):
            return None
        prev: dict[tuple[int, int], Optional[tuple[int, int]]] = {start: None}
        queue = [start]
        for cur in queue:
            if cur == goal:
                break
            for vx, vy in DIR_VEC.values():
                nxt = (cur[0] + vx, cur[1] + vy)
                if nxt not in prev and free(nxt):
                    prev[nxt] = cur
                    queue.append(nxt)
        if goal not in prev:
            return None
        steps = []
        node = goal
        while prev[node] is not None:
            p = prev[node]
            steps.append((node[0] - p[0], node[1] - p[1]))
            node = p
        return steps[::-1]

    def _put_hero(self, x: int, y: int) -> None:
        self.st.x, self.st.y = x, y

    # ============================================================ マップ
    def _set_map(self, map_id: str) -> None:
        changed = self.st.map_id != map_id or self.map is None
        self.map = self.gd.maps[map_id]
        self.st.map_id = map_id
        self.st.current_map = self.map
        if self.map.dungeon and changed:
            self.banner = format_text(self.map.name, self.st, self.gd)
            self.banner_left = BANNER_SECONDS
        self._reset_encounter()
        self._npc_timer.clear()

    def change_map(self, map_id: str, x: int, y: int, d: Optional[str] = None,
                   transition: str = "none") -> Optional[Effect]:
        if map_id not in self.gd.maps:
            raise ScriptError(None, f"マップ「{map_id}」が定義されていません")
        self._set_map(map_id)
        Q.on_reach(self.st, self.gd, map_id)
        self.st.x, self.st.y = x, y
        if d:
            self.st.dir = d
        self.pending_auto = True
        if transition == "fade" and not self.effects.faded:
            eff = Fade(False, 400)
            self.effects.active.append(eff)
            return eff
        return None

    def tile_char(self, x: int, y: int) -> str:
        """(x, y) のタイルの文字（@tile で変えていればそれ）。"""
        return self.st.tile_override(self.map.id, x, y) or self.map.rows[y][x]

    def _tile(self, x: int, y: int):
        ts = self.gd.tilesets[self.map.tileset]
        return ts.tiles.get(self.tile_char(x, y))

    def passable(self, x: int, y: int) -> bool:
        if self.map is None or not self.map.in_bounds(x, y):
            return False
        t = self._tile(x, y)
        return t is not None and t.passable

    def _cond(self, src: str) -> bool:
        if not src:
            return True
        ast = self._when_cache.get(src)
        if ast is None:
            ast = self._when_cache[src] = parse_expr(src)
        try:
            return bool(evaluate(ast, self.st))
        except ExprError:
            return False

    def _npc_pos(self, npc: Npc) -> tuple[int, int]:
        s = self.st.npc_state.get(f"{self.st.map_id}:{npc.id}", {})
        return s.get("x", npc.x), s.get("y", npc.y)

    def npc_visible(self, npc: Npc) -> bool:
        s = self.st.npc_state.get(f"{self.st.map_id}:{npc.id}", {})
        if "hidden" in s:
            return not s["hidden"]
        return self._cond(npc.when)

    def _find_npc(self, npc_id: str) -> Optional[Npc]:
        if self.map is None:
            return None
        return next((n for n in self.map.npcs if n.id == npc_id), None)

    def npc_at(self, x: int, y: int) -> Optional[Npc]:
        if self.map is None:
            return None
        for n in self.map.npcs:
            if self.npc_visible(n) and self._npc_pos(n) == (x, y):
                return n
        return None

    def _event_key(self, ev: MapEvent) -> str:
        return f"{self.st.map_id}:{ev.x}:{ev.y}:{ev.label}"

    def _event_ready(self, ev: MapEvent) -> bool:
        return not (ev.once and self._event_key(ev) in self.st.once_events) and self._cond(ev.when)

    def run_event(self, ev: MapEvent) -> None:
        if ev.once:
            self.st.once_events.add(self._event_key(ev))
        self.start_script(ev.label)

    def _reset_encounter(self) -> None:
        enc = self.gd.encounters.get(self.map.encounter) if self.map else None
        self.enc_left = random.randint(*enc.steps) if enc else 0

    # ============================================================ 移動
    def debug_state(self) -> str:
        """--keylog 用: 何を待っているか。"""
        effs = ",".join(f"{type(e).__name__}{'(key)' if e.needs_key else ''}" for e in self.effects.active)
        return (f"map={getattr(getattr(self, 'map', None), 'id', None)} req={type(self.req).__name__ if self.req else None} "
                f"vm_running={self.vm.running} msg_active={self.msg.active} choice={self.choice is not None} "
                f"wait_left={self.wait_left:.2f} effects=[{effs}] fade={self.effects.persist.get('fade')} "
                f"error={bool(getattr(self, 'error', ''))}")

    @property
    def busy(self) -> bool:
        return self.req is not None or self.vm.running or self.msg.active or self.choice is not None

    def try_move(self, d: str) -> None:
        self.st.dir = d
        dx, dy = DIR_VEC[d]
        nx, ny = self.st.x + dx, self.st.y + dy
        if not self.passable(nx, ny) or self.npc_at(nx, ny):
            return
        self.st.x, self.st.y = nx, ny
        self._poison_step()
        for w in self.map.warps:
            if (w.x, w.y) == (nx, ny):
                self.change_map(w.to, w.tx, w.ty, w.dir or None)
                self.effects.active.append(Fade(False, 250))
                return
        for ev in self.map.events:
            if ev.trigger == "touch" and (ev.x, ev.y) == (nx, ny) and self._event_ready(ev):
                self.run_event(ev)
                return
        self._step_encounter()

    def _poison_step(self) -> None:
        """フィールドで毒のまま歩くと 1 歩ごとに HP が 1 減る（1 未満にはならない）。"""
        hurt = False
        for m in self.st.party:
            if m.alive and any(self.gd.statuses.get(s) and self.gd.statuses[s].tick.get("hp_rate", 0) < 0
                               for s in m.status):
                if m.hp > 1:
                    m.hp -= 1
                    hurt = True
        if hurt:
            self.effects.start("flash", ["red"], {"count": "1", "interval": "40", "wait": "false"})

    def _step_encounter(self) -> None:
        enc = self.gd.encounters.get(self.map.encounter) if self.map else None
        if not enc:
            return
        self.enc_left -= 1
        if self.enc_left > 0:
            return
        self._reset_encounter()
        groups = [g for g, _ in enc.table]
        weights = [w for _, w in enc.table]
        gid = random.choices(groups, weights)[0]
        self.start_battle(gid)

    def check_front(self) -> None:
        dx, dy = DIR_VEC[self.st.dir]
        fx, fy = self.st.x + dx, self.st.y + dy
        npc = self.npc_at(fx, fy)
        if npc is not None:
            opposite = {"up": "down", "down": "up", "left": "right", "right": "left"}[self.st.dir]
            self.st.npc(self.st.map_id, npc.id)["dir"] = opposite
            if npc.talk:
                self.start_script(npc.talk)
            return
        for ev in self.map.events:
            if ev.trigger == "check" and (ev.x, ev.y) in ((fx, fy), (self.st.x, self.st.y)) and self._event_ready(ev):
                self.run_event(ev)
                return

    def open_menu(self) -> None:
        from .menu import MenuScene
        self.app.push(MenuScene(self))

    def open_system_menu(self) -> None:
        self.msg.open([("", "どうしますか？")])
        self.msg.shown = 10 ** 6
        self.choice = ChoiceWindow(["つづける", "タイトルにもどる", "ゲームをおわる"], cancel_index=0)

        def done(i: int) -> None:
            self.msg.close()
            if i == 1:
                self.back_to_title()
            elif i == 2:
                self.app.quit()
        self.choice_cb = done

    def back_to_title(self) -> None:
        from .title import TitleScene
        self.app.replace(TitleScene(self.game))

    # ============================================================ 入力
    def on_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        if self.error:
            if Action.OK in actions or Action.CANCEL in actions:
                self.error = None
            return
        if self.effects.key():
            return
        if self.choice is not None:
            if Action.UP in actions:
                self.choice.move(-1)
            elif Action.DOWN in actions:
                self.choice.move(1)
            elif Action.OK in actions or (Action.CANCEL in actions and self.choice.cancel_index is not None):
                idx = self.choice.index if Action.OK in actions else self.choice.cancel_index
                cb = self.choice_cb
                self.choice = None
                self.choice_cb = None
                if cb is not None:
                    cb(idx)
                    return
                self.msg.close()
                try:
                    self.vm.choose(idx)
                except ScriptError as e:
                    self._script_error(e)
                    return
                self._advance()
            return
        if isinstance(self.req, MessageReq):
            if Action.OK in actions or Action.CANCEL in actions:
                if self.msg.advance():
                    self.msg.close()
                    self._advance()
            return
        if isinstance(self.req, KeyWaitReq):
            if Action.OK in actions:
                self._advance()
            return
        if self.busy:
            return
        for a, d in ACTION_DIR.items():
            if a in actions:
                self.try_move(d)
                return
        if Action.OK in actions:
            self.check_front()
        elif Action.CANCEL in actions or Action.MENU in actions:
            self.open_menu()

    # ============================================================ 更新
    def warp_by_item(self, to: str, x: int, y: int, d: str = "") -> None:
        """帰還の巻物など（アイテムの effect = "warp"）で移動する。"""
        self.change_map(to, x, y, d or None)
        self.effects.active.append(Fade(False, 400))

    def update(self, dt: float) -> None:
        self.banner_left = max(0.0, self.banner_left - dt)
        self.st.playtime += dt
        self.msg.update(dt)
        self.effects.update(dt)
        for mv in self.background_movers:
            mv.update(dt)
        self.background_movers = [mv for mv in self.background_movers if not mv.done]
        req = self.req
        if isinstance(req, WaitReq):
            self.wait_left -= dt
            if self.wait_left <= 0:
                self._advance()
        elif isinstance(req, Effect):
            if req.done:
                self._advance()
        elif isinstance(req, Mover):
            req.update(dt)
            if req.done:
                self._advance()
        elif getattr(req, "closed", False):   # 施設・戦闘などの重ね画面が閉じた
            if hasattr(req, "battle"):
                self._after_battle(req)
            else:
                self._advance()
        if self.encounter is not None and self.encounter.closed:
            b, self.encounter = self.encounter, None
            self._after_battle(b)
            return
        if self.busy or self.error or self.map is None or self.encounter is not None:
            return
        if self.pending_labels:
            self.start_script(self.pending_labels.pop(0))
            return
        if self.pending_auto:
            self.pending_auto = False
            for ev in self.map.events:
                if ev.trigger == "auto" and self._event_ready(ev):
                    self.run_event(ev)
                    return
        self._move_npcs(dt)

    def _move_npcs(self, dt: float) -> None:
        for n in self.map.npcs:
            if n.move == "route" and n.route and self.npc_visible(n):
                self._route_step(n, dt)
                continue
            if n.move != "random" or not self.npc_visible(n):
                continue
            t = self._npc_timer.get(n.id)
            if t is None:
                t = random.uniform(*NPC_STEP_INTERVAL)
            t -= dt
            if t <= 0:
                t = random.uniform(*NPC_STEP_INTERVAL)
                x, y = self._npc_pos(n)
                dx, dy = random.choice(list(DIR_VEC.values()))
                nx, ny = x + dx, y + dy
                home_ok = abs(nx - n.x) <= 3 and abs(ny - n.y) <= 3
                if (home_ok and self.passable(nx, ny) and not self.npc_at(nx, ny)
                        and (nx, ny) != (self.st.x, self.st.y)
                        and not any((w.x, w.y) == (nx, ny) for w in self.map.warps)):
                    self.st.npc(self.st.map_id, n.id).update(x=nx, y=ny)
            self._npc_timer[n.id] = t

    def _route_step(self, n: Npc, dt: float) -> None:
        """道順（route）どおりに 1 歩ずつ歩く。ふさがれていたら空くまで待つ。何歩目かは状態に保存する。"""
        t = self._npc_timer.get(n.id, ROUTE_STEP_INTERVAL) - dt
        if t > 0:
            self._npc_timer[n.id] = t
            return
        self._npc_timer[n.id] = ROUTE_STEP_INTERVAL
        s = self.st.npc(self.st.map_id, n.id)
        i = s.get("route_i", 0) % len(n.route)
        step = n.route[i]
        if step != "wait":
            dx, dy = DIR_VEC[step]
            x, y = self._npc_pos(n)
            nx, ny = x + dx, y + dy
            if not self.passable(nx, ny) or self.npc_at(nx, ny) or (nx, ny) == (self.st.x, self.st.y):
                return                              # ふさがれている → 次の機会にもう一度
            s.update(x=nx, y=ny, dir=step)
        s["route_i"] = (i + 1) % len(n.route)

    # ============================================================ 描画
    def draw(self, buf: Buffer, overlay: bool = False) -> None:
        """``overlay=True`` は重ね画面から呼ばれたとき（会話窓・暗転は重ね画面側で描く）。"""
        W, H = buf.width, buf.height
        map_rect = Rect(0, 0, W - self.PANEL_W, H - self.MSG_H)
        panel_rect = Rect(W - self.PANEL_W, 0, self.PANEL_W, H - self.MSG_H)
        msg_rect = Rect(0, H - self.MSG_H, W, self.MSG_H)

        title = format_text(self.map.name, self.st, self.gd) if self.map else ""
        map_inner = buf.box(map_rect, FRAME, title=title, chars=BOX_SINGLE)
        if self.map is not None:
            self._draw_map(buf, map_inner)
        self._draw_panel(buf, buf.box(panel_rect, FRAME, title="パーティ", chars=BOX_SINGLE))
        dx, dy = self.effects.offset()
        if dx or dy:
            copy = buf.copy()
            buf.clear()
            buf.blit(copy, dx, dy)
        # 屋内のマップでは雨・雪を描かない（外に出ればまた降っている）
        weather_area = None if self.map is not None and self.map.indoor else map_inner
        self.effects.apply_world(buf, weather_area)
        if self.banner_left > 0 and self.banner:
            self._draw_banner(buf, map_inner)

        if overlay:
            buf.box(msg_rect, FRAME, chars=BOX_SINGLE)
            return
        if self.msg.active:
            if self.face:
                self._draw_face(buf, msg_rect)
            self.msg.draw(buf, msg_rect, show_cursor=self.choice is None)
        elif not self.effects.faded:
            inner = buf.box(msg_rect, FRAME, chars=BOX_SINGLE)
            buf.put(inner.x + 1, inner.bottom - 1, "移動: 矢印/WASD   話す・調べる: Enter/Z   メニュー: Esc/M",
                    Style.of("gray"), clip=inner)
        if self.choice is not None:
            self.choice.draw(buf, W - 1, H - self.MSG_H + 1)
        self.effects.apply_overlay(buf)
        if self.error:
            self._draw_error(buf)

    def _draw_banner(self, buf: Buffer, area: Rect) -> None:
        """ダンジョンの階に入ったときのマップ名（例：黒岩の洞穴 B3F）。"""
        w = text_width(self.banner) + 6
        rect = Rect(area.x + max(0, (area.w - w) // 2), area.y + 1, min(w, area.w), 3)
        inner = buf.box(rect, Style.of("bright_white"), chars=BOX_SINGLE)
        buf.put(inner.x + 2, inner.y, self.banner, Style.of("bright_white", bold=True), clip=inner)

    def _draw_face(self, buf: Buffer, msg_rect: Rect) -> None:
        """顔 AA を会話窓の左上に枠つきで重ねる。"""
        from ..term import text_width
        lines = self.face or []
        w = min(max((text_width(ln) for ln in lines), default=0) + 4, buf.width // 2)
        h = min(len(lines) + 2, msg_rect.y)
        rect = Rect(msg_rect.x, msg_rect.y - h, w, h)
        inner = buf.box(rect, FRAME, title=self.msg.speaker, chars=BOX_SINGLE)
        draw_aa(buf, inner.x + 1, inner.y, lines, Style.of("bright_white"), self.gd.colors_for(lines),
                clip=inner, transparent=False)

    def _draw_map(self, buf: Buffer, area: Rect) -> None:
        m = self.map
        ts = self.gd.tilesets[m.tileset]
        cols, rows = area.w // 2, area.h
        ox = min(max(0, self.st.x - cols // 2), max(0, m.width - cols))
        oy = min(max(0, self.st.y - rows // 2), max(0, m.height - rows))
        # マップが表示領域より小さいときは中央に寄せる
        px = area.x + max(0, (cols - m.width) // 2) * 2
        py = area.y + max(0, (rows - m.height) // 2)
        hx, hy = self.st.x, self.st.y
        self._map_area_size = (area.w, area.h)

        def visible(x: int, y: int) -> bool:
            return not m.dark or (abs(x - hx) <= DARK_RADIUS and abs(y - hy) <= DARK_RADIUS)

        for ty in range(min(rows, m.height - oy)):
            my = oy + ty
            row = m.rows[my]
            for tx in range(min(cols, m.width - ox)):
                mx = ox + tx
                if not visible(mx, my):
                    continue
                tile = ts.tiles.get(self.st.tile_override(m.id, mx, my) or row[mx])
                if tile is None:
                    continue
                st = Style.of(tile.color) if tile.color else Style()
                buf.put(px + tx * 2, py + ty, tile.glyph, st, clip=area)
        for n in m.npcs:
            if not self.npc_visible(n) or self.effects.hidden(n.id):
                continue
            nx, ny = self._npc_pos(n)
            if ox <= nx < ox + cols and oy <= ny < oy + rows and visible(nx, ny):
                buf.put(px + (nx - ox) * 2, py + (ny - oy), n.glyph,
                        Style.of(n.color or "white", bold=True), clip=area)
        if not self.effects.hidden("hero"):
            buf.put(px + (hx - ox) * 2, py + (hy - oy), HERO_GLYPH, Style.of("bright_white", bold=True), clip=area)
        for key, (lines, x, y) in self.overlays.items():
            if self.effects.hidden(key):
                continue
            draw_aa(buf, area.x + x, area.y + y, lines, Style.of("bright_white"), self.gd.colors_for(lines), clip=area)

    def _draw_panel(self, buf: Buffer, area: Rect) -> None:
        y = area.y
        for mem in self.st.party:
            if y + 1 >= area.bottom:
                break
            job = self.gd.jobs.get(mem.job)
            buf.put(area.x + 1, y, f"{pad(mem.name, 10)}{pad(job.name if job else '', 8)}Lv{mem.lv:>3}",
                    Style.of("bright_white", bold=True), clip=area)
            hp_st = Style.of("bright_red") if mem.hp * 4 <= mem.max_hp else Style.of("white")
            buf.put(area.x + 2, y + 1, f"HP {mem.hp:>3}/{mem.max_hp:>3}  MP {mem.mp:>3}/{mem.max_mp:>3}", hp_st, clip=area)
            y += 3
        pet = self.gd.enemies.get(self.st.pet) if self.st.pet else None
        info = ([f"ペット {pet.name}"] if pet else []) + [f"G {self.st.gold:>8}"]
        if self.st.chapter:
            info.append(f"第{self.st.chapter}章 {self.st.chapter_title}")
        t = int(self.st.playtime)
        info.append(f"TIME {t // 3600:02}:{t // 60 % 60:02}:{t % 60:02}")
        if self.game.dev:
            info.append(f"[dev] {self.st.map_id} ({self.st.x},{self.st.y}) {self.st.dir}")
        y = max(y, area.bottom - len(info))
        for line in info:
            if y < area.bottom:
                buf.put(area.x + 1, y, truncate(line, area.w - 2), Style.of("yellow"), clip=area)
                y += 1

    def _draw_error(self, buf: Buffer) -> None:
        w = min(buf.width - 4, 90)
        lines = []
        for para in self.error.split("\n"):
            lines += wrap(para, w - 4)
        lines += ["", "（Enter で閉じる）"]
        h = len(lines) + 2
        rect = Rect((buf.width - w) // 2, max(0, (buf.height - h) // 2), w, h)
        inner = buf.box(rect, Style.of("bright_red"), title="エラー", chars=BOX_SINGLE)
        for i, line in enumerate(lines):
            buf.put(inner.x + 1, inner.y + i, line, Style.of("bright_white"), clip=inner)
