"""戦闘画面（基本設計 2.2 / 4.5）。進行と計算は battle.core に任せ、ここは入力と表示だけを受け持つ。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Iterator, Optional

from ..app import Scene
from ..battle.core import Battle, Battler, Command
from ..data.models import Skill
from ..term import Action, Buffer, KeyEvent, Rect, Style, pad, text_width, truncate
from ..term.buffer import BOX_SINGLE
from ..ui.aa import draw_aa
from ..ui.widgets import CURSOR, DIM_TEXT, FRAME, TEXT

if TYPE_CHECKING:
    from .field import FieldScene

MSG_WAIT = 0.55          # メッセージ 1 行ごとの待ち（決定キーで早送り）
HIT_BLINK = 0.35
INTRO_FLASH = 0.35
ANIM_FLASH = 0.3
PARTY_ROWS = 5
BOTTOM_ROWS = 8
CMD_W = 22

TARGET_ENEMY = ("enemy_one",)
TARGET_ALLY = ("ally_one",)


class BattleScene(Scene):
    def __init__(self, field: "FieldScene", group: str, *, escape: bool = True, gameover: str = "",
                 target_only: str = "", lose: str = "", from_script: bool = False, rng=None):
        self.field = field
        self.gd = field.gd
        self.st = field.st
        self.battle = Battle(self.gd, self.st, group, escape=escape, target_only=target_only, rng=rng)
        self.gameover = gameover
        self.lose_label = lose.lstrip("*")
        self.from_script = from_script
        self.closed = False
        # 表示
        self.log: list[str] = []
        self.blink: dict[int, float] = {}       # id(battler) → 残り時間
        self.shake = 0.0
        self.flash = INTRO_FLASH
        self.anim_flash: Optional[tuple[int, float]] = None    # スキル演出の発光（背景色, 残り秒）
        self.t = 0.0
        # イベント再生
        self._gen: Optional[Iterator] = None
        self._then: Optional[Callable[[], None]] = None
        self._wait = 0.0
        # 入力
        self.mode = "events"                     # events / command / target / list
        self.actors: list[Battler] = []
        self.actor_i = 0
        self.cmds: dict[Battler, Command] = {}
        self.menu_i = 0
        self.list_items: list[tuple[str, str, bool, object]] = []
        self.list_i = 0
        self.list_kind = ""
        self.targets: list[Battler] = []
        self.target_i = 0
        self._pending: Optional[Command] = None
        self._play(self.battle.intro(), self._begin_input)

    # ================================================================ イベント再生
    def _play(self, gen: Iterator, then: Callable[[], None]) -> None:
        self.mode = "events"
        self._gen = gen
        self._then = then
        self._wait = 0.0

    def _step_events(self) -> None:
        """待ち時間がなくなるまでイベントを進める。"""
        while self._gen is not None and self._wait <= 0:
            try:
                kind, val = next(self._gen)
            except StopIteration:
                self._gen = None
                then, self._then = self._then, None
                if then:
                    then()
                return
            if kind == "msg":
                self.log.append(val)
                self.log = self.log[-(BOTTOM_ROWS - 2):]
                self._wait = MSG_WAIT
            elif kind == "clear":
                self.log = []
            elif kind == "hit":
                self.blink[id(val)] = HIT_BLINK
                if val.side == "party":
                    self.shake = 0.25
            elif kind == "heal":
                self.blink[id(val)] = HIT_BLINK
            elif kind == "anim":
                self._play_anim(*val)

    # ================================================================ スキルの演出
    def _play_anim(self, anim: str, targets: list) -> None:
        """Items.data の skill.anim（"flash:red,shake" など）を再生する。メッセージ送りはその間止める。"""
        from ..data.models import parse_anim
        from ..term.style import color as to_color
        for name, arg in parse_anim(anim):
            if name == "flash":
                try:
                    bg = to_color(arg or "bright_white")
                except ValueError:
                    bg = 15
                self.anim_flash = (bg, ANIM_FLASH)
            elif name == "shake":
                power = int(arg) if arg.isdigit() else 1
                self.shake = max(self.shake, 0.2 * max(1, min(3, power)))
            elif name == "blink":
                for t in targets:
                    self.blink[id(t)] = HIT_BLINK
        self._wait = max(self._wait, ANIM_FLASH)

    # ================================================================ 入力
    def _begin_input(self) -> None:
        if self.battle.result:
            self._end()
            return
        self.actors = self.battle.actors()
        self.cmds = {}
        self.actor_i = 0
        if not self.actors:                      # 全員動けない → そのまま敵のターン
            self._run_round()
            return
        self.mode = "command"
        self.menu_i = 0

    @property
    def actor(self) -> Battler:
        return self.actors[self.actor_i]

    def _menu(self) -> list[tuple[str, bool]]:
        a = self.actor
        has_skill = bool(a.skills())
        has_item = any(self._battle_items())
        return [("たたかう", True), ("スキル", has_skill), ("どうぐ", has_item),
                ("ぼうぎょ", True), ("にげる", self.battle.can_escape)]

    def _battle_items(self):
        for iid, n in self.st.items.items():
            it = self.gd.items.get(iid)
            if it and it.type == "consumable" and it.use.get("battle") and n > 0:
                yield it, n

    def _set_cmd(self, c: Command) -> None:
        self.cmds[self.actor] = c
        if c.kind == "escape":
            self._run_round()
            return
        self.actor_i += 1
        while self.actor_i < len(self.actors) and not self.actors[self.actor_i].can_act():
            self.actor_i += 1
        if self.actor_i >= len(self.actors):
            self._run_round()
        else:
            self.mode = "command"
            self.menu_i = 0

    def _run_round(self) -> None:
        self._play(self.battle.run_round(self.cmds), self._after_round)

    def _after_round(self) -> None:
        if self.battle.result:
            self._end()
        else:
            self._begin_input()

    def _end(self) -> None:
        self._play(self.battle.finish(), self._close_after_key)

    def _close_after_key(self) -> None:
        self.mode = "done"

    def close(self) -> None:
        self.closed = True
        self.app.pop()

    # ---- 対象選択
    def _choose_target(self, cmd: Command, side: str) -> None:
        self._pending = cmd
        self.targets = self.battle.alive("enemy") if side == "enemy" else [b for b in self.battle.party if not b.gone]
        self.target_i = 0
        if side == "ally":
            self.target_i = self.targets.index(self.actor) if self.actor in self.targets else 0
        self.mode = "target"

    def _skill_chosen(self, sk: Skill) -> None:
        c = Command("skill", skill=sk.id)
        if sk.target in TARGET_ENEMY or sk.kind == "tame":
            self._choose_target(c, "enemy")
        elif sk.target in TARGET_ALLY:
            self._choose_target(c, "ally")
        else:
            self._set_cmd(c)

    def on_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        ok, cancel = Action.OK in actions, Action.CANCEL in actions
        up, down = Action.UP in actions, Action.DOWN in actions
        left, right = Action.LEFT in actions, Action.RIGHT in actions
        if self.flash > 0:
            return
        if self.mode == "events":
            if ok or cancel:
                self._wait = 0.0                 # 早送り
            return
        if self.mode == "done":
            if ok or cancel:
                self.close()
            return
        if self.mode == "command":
            items = self._menu()
            if up:
                self.menu_i = (self.menu_i - 1) % len(items)
            elif down:
                self.menu_i = (self.menu_i + 1) % len(items)
            elif cancel and self.actor_i > 0:
                self.actor_i -= 1
                self.cmds.pop(self.actor, None)
                self.menu_i = 0
            elif ok:
                label, enabled = items[self.menu_i]
                if not enabled:
                    return
                if label == "たたかう":
                    self._choose_target(Command("attack"), "enemy")
                elif label == "スキル":
                    self.list_kind = "skill"
                    self.list_items = [(sk.name, f"MP {sk.mp}", self.actor.mp >= sk.mp, sk) for sk in self.actor.skills()]
                    self.list_i = 0
                    self.mode = "list"
                elif label == "どうぐ":
                    self.list_kind = "item"
                    self.list_items = [(it.name, f"×{n}", True, it) for it, n in self._battle_items()]
                    self.list_i = 0
                    self.mode = "list"
                elif label == "ぼうぎょ":
                    self._set_cmd(Command("defend"))
                elif label == "にげる":
                    self._set_cmd(Command("escape"))
            return
        if self.mode == "list":
            if up:
                self.list_i = (self.list_i - 1) % len(self.list_items)
            elif down:
                self.list_i = (self.list_i + 1) % len(self.list_items)
            elif cancel:
                self.mode = "command"
            elif ok:
                _, _, enabled, obj = self.list_items[self.list_i]
                if not enabled:
                    return
                if self.list_kind == "skill":
                    self._skill_chosen(obj)
                else:
                    tgt = obj.use.get("target", "ally_one")
                    c = Command("item", item=obj.id)
                    if tgt == "ally_one":
                        self._choose_target(c, "ally")
                    elif tgt == "enemy_one":
                        self._choose_target(c, "enemy")
                    else:
                        self._set_cmd(c)
            return
        if self.mode == "target":
            if left or up:
                self.target_i = (self.target_i - 1) % len(self.targets)
            elif right or down:
                self.target_i = (self.target_i + 1) % len(self.targets)
            elif cancel:
                self.mode = "list" if self._pending.kind in ("skill", "item") else "command"
            elif ok:
                c = self._pending
                c.target = self.targets[self.target_i]
                self._pending = None
                self._set_cmd(c)

    # ================================================================ 更新
    def update(self, dt: float) -> None:
        self.t += dt
        if self.flash > 0:
            self.flash -= dt
            return
        for k in list(self.blink):
            self.blink[k] -= dt
            if self.blink[k] <= 0:
                del self.blink[k]
        self.shake = max(0.0, self.shake - dt)
        if self.anim_flash is not None:
            bg, left = self.anim_flash
            self.anim_flash = (bg, left - dt) if left - dt > 0 else None
        if self.mode == "events":
            self._wait -= dt
            self._step_events()

    def debug_state(self) -> str:
        return f"mode={self.mode} turn={self.battle.turn} result={self.battle.result} log={self.log[-1:] }"

    # ================================================================ 描画
    def draw(self, buf: Buffer) -> None:
        W, H = buf.width, buf.height
        if self.flash > 0:
            if int(self.flash * 12) % 2 == 0:
                buf.fill(buf.rect, " ", Style.of(bg="bright_white"))
            return
        ea_h = H - PARTY_ROWS - BOTTOM_ROWS
        self._draw_enemies(buf, Rect(0, 0, W, ea_h))
        self._draw_party(buf, Rect(0, ea_h, W, PARTY_ROWS))
        bottom = Rect(0, ea_h + PARTY_ROWS, W, BOTTOM_ROWS)
        if self.mode in ("command", "list", "target"):
            self._draw_command(buf, Rect(0, bottom.y, CMD_W, bottom.h))
            msg_rect = Rect(CMD_W, bottom.y, W - CMD_W, bottom.h)
        else:
            msg_rect = bottom
        self._draw_log(buf, msg_rect)
        if self.mode == "list":
            self._draw_list(buf, Rect(CMD_W, max(0, bottom.y - 9), min(44, W - CMD_W), 9))
        if self.shake > 0:
            copy = buf.copy()
            buf.clear()
            buf.blit(copy, 2 if int(self.shake * 30) % 2 == 0 else -2, 0)
        if self.anim_flash is not None:
            bg, left = self.anim_flash
            if int(left / 0.075) % 2 == 0:                  # 2 回明滅
                buf.fill(Rect(0, 0, W, ea_h), " ", Style(None, bg, 0))

    def _aa(self, b: Battler, small: bool = False) -> list[str]:
        path = b.enemy.aa
        if small:
            path = path[:-4] + "_s.txt" if path.endswith(".txt") else path
        lines = self.gd.aa.get(path)
        return lines if lines else []

    def _draw_enemies(self, buf: Buffer, area: Rect) -> None:
        buf.box(area, FRAME, chars=BOX_SINGLE)
        shown = [e for e in self.battle.enemies if e.alive or id(e) in self.blink]
        if not shown:
            return
        inner = area.inset(1)
        gap = 4
        arts = [self._aa(e) for e in shown]
        widths = [max([text_width(x) for x in a] + [text_width(e.name)]) for a, e in zip(arts, shown)]
        if sum(widths) + gap * (len(shown) - 1) > inner.w:
            arts = [self._aa(e, small=True) or [] for e in shown]
            widths = [max([text_width(x) for x in a] + [text_width(e.name)]) for a, e in zip(arts, shown)]
        if sum(widths) + gap * (len(shown) - 1) > inner.w:
            arts = [[] for _ in shown]                       # 入りきらない → 名前だけ
            widths = [text_width(e.name) + 2 for e in shown]
        total = sum(widths) + gap * (len(shown) - 1)
        x = inner.x + max(0, (inner.w - total) // 2)
        name_y = inner.bottom - 1
        art_bottom = name_y - 1
        targeting = self.mode == "target" and self.targets and self.targets[0].side == "enemy"
        for e, art, w in zip(shown, arts, widths):
            blink_on = id(e) in self.blink and int(self.t * 20) % 2 == 0
            dead_fade = not e.alive
            if not blink_on and not dead_fade:
                top = art_bottom - len(art) + 1
                ax = x + (w - max([text_width(a) for a in art] + [0])) // 2
                cut = max(0, inner.y - top)
                colors = self.gd.colors_for(art)
                draw_aa(buf, ax, max(inner.y, top), art[cut:], Style.of("bright_white"),
                        colors[cut:] if colors else None, clip=inner)
            sel = targeting and self.targets[self.target_i] is e
            nst = CURSOR if sel else (DIM_TEXT if dead_fade else TEXT)
            buf.put(x + (w - text_width(e.name)) // 2, name_y, e.name, nst, clip=inner)
            if sel:
                top = art_bottom - len(art)
                buf.put(x + w // 2 - 1, max(inner.y, top), "▼", CURSOR, clip=inner)
            x += w + gap

    def _draw_party(self, buf: Buffer, area: Rect) -> None:
        allies = self.battle.allies
        n = max(4, len(self.battle.party)) + (1 if self.battle.pet else 0)
        w = area.w // n
        targeting = self.mode == "target" and self.targets and self.targets[0].side == "party"
        cur = self.actor if self.mode in ("command", "list", "target") and self.actors else None
        for i, b in enumerate(allies):
            if b.pet:
                i = n - 1                                   # ペットは右端
            rect = Rect(area.x + i * w, area.y, w if i < n - 1 else area.w - i * w, area.h)
            sel = targeting and self.targets[self.target_i] is b
            hit = id(b) in self.blink and int(self.t * 20) % 2 == 0
            frame = Style.of("bright_red") if hit else (CURSOR if sel or b is cur else FRAME)
            inner = buf.box(rect, frame, title="ペット" if b.pet else "", chars=BOX_SINGLE)
            name_st = CURSOR if b is cur else Style.of("bright_white", bold=True)
            label = ("▶" if b is cur else "") + b.name
            buf.put(inner.x, inner.y, truncate(label, inner.w), name_st, clip=inner)
            if not b.alive:
                buf.put(inner.x, inner.y + 1, "たおれている", Style.of("bright_red"), clip=inner)
                continue
            hp_st = Style.of("bright_red") if b.hp * 4 <= b.max_hp else (Style.of("yellow") if b.hp * 2 <= b.max_hp else TEXT)
            buf.put(inner.x, inner.y + 1, f"HP {b.hp:>3}/{b.max_hp:<3}", hp_st, clip=inner)
            st_names = "".join(self.gd.statuses[s].name[:1] for s in b.status if s in self.gd.statuses)
            mp_text = f"MP {b.mp:>3}/{b.max_mp:<3}" + (f" {st_names}" if st_names else "")
            buf.put(inner.x, inner.y + 2 if inner.h > 2 else inner.y + 1, mp_text,
                    Style.of("bright_magenta") if st_names else TEXT, clip=inner)

    def _draw_command(self, buf: Buffer, rect: Rect) -> None:
        inner = buf.box(rect, FRAME, title=self.actor.name if self.actors else "", chars=BOX_SINGLE)
        for i, (label, enabled) in enumerate(self._menu()):
            sel = i == self.menu_i and self.mode == "command"
            st = CURSOR if sel else (TEXT if enabled else DIM_TEXT)
            buf.put(inner.x + 1, inner.y + i, ("▶ " if sel else "  ") + label, st, clip=inner)

    def _draw_log(self, buf: Buffer, rect: Rect) -> None:
        inner = buf.box(rect, FRAME, chars=BOX_SINGLE)
        lines = self.log
        if self.mode == "target":
            lines = ["だれに？（←→ で選ぶ　Enter で決定　Esc でもどる）"]
        elif self.mode in ("command", "list") and not lines:
            lines = [f"{self.actor.name}はどうする？"]
        for i, line in enumerate(lines[-inner.h:]):
            buf.put(inner.x + 1, inner.y + i, truncate(line, inner.w - 2), TEXT, clip=inner)
        if self.mode == "done" and int(self.t * 3) % 2 == 0:
            buf.put(inner.right - 2, inner.bottom - 1, "▽", CURSOR, clip=inner)

    def _draw_list(self, buf: Buffer, rect: Rect) -> None:
        title = "スキル" if self.list_kind == "skill" else "どうぐ"
        inner = buf.box(rect, FRAME, title=title, chars=BOX_SINGLE)
        top = max(0, self.list_i - inner.h + 2)
        for row, (name, right, enabled, _) in enumerate(self.list_items[top:top + inner.h - 1]):
            i = top + row
            sel = i == self.list_i
            st = CURSOR if sel else (TEXT if enabled else DIM_TEXT)
            buf.put(inner.x + 1, inner.y + row, ("▶ " if sel else "  ") + pad(name, inner.w - 12) + right, st, clip=inner)
        if self.list_items:
            obj = self.list_items[self.list_i][3]
            desc = getattr(obj, "desc", "") or ""
            buf.put(inner.x + 1, inner.bottom - 1, truncate(desc, inner.w - 2), DIM_TEXT, clip=inner)
