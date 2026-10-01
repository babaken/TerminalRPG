"""施設画面：ショップ・宿屋・冒険者協会・仲間選択（基本設計 4.7 / 10.5 @shop @inn @guild @recruit）。

どれもフィールドの上に重ねて表示する画面（Overlay）。スクリプトの命令から開かれ、
閉じるとスクリプトの続きが実行される。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from ..app import Scene
from ..data.models import Item, Quest
from ..term import Action, Buffer, KeyEvent, Rect, Style, pad, text_width, truncate, wrap
from ..term.buffer import BOX_SINGLE
from ..ui.widgets import CURSOR, DIM_TEXT, FRAME, TEXT, ChoiceWindow, MessageWindow
from ..world import quests as Q
from ..world.state import Member

if TYPE_CHECKING:
    from .field import FieldScene

GOLD_ST = Style.of("yellow")
HEAD_ST = Style.of("bright_cyan", bold=True)
STAT_NAMES = {"hp": "HP", "mp": "MP", "atk": "攻撃", "def": "防御", "mag": "魔力", "agi": "素早", "luk": "運"}


class ListWindow:
    """スクロールする選択リスト。各行は (左の文字, 右の文字, 選べるか)。"""

    def __init__(self, rows: list[tuple[str, str, bool]], height: int = 10):
        self.rows = rows
        self.index = 0
        self.top = 0
        self.height = height

    @property
    def empty(self) -> bool:
        return not self.rows

    def move(self, d: int) -> None:
        if self.rows:
            self.index = (self.index + d) % len(self.rows)

    def draw(self, buf: Buffer, rect: Rect, title: str = "") -> None:
        inner = buf.box(rect, FRAME, title=title, chars=BOX_SINGLE)
        h = inner.h
        if self.index < self.top:
            self.top = self.index
        elif self.index >= self.top + h:
            self.top = self.index - h + 1
        if not self.rows:
            buf.put(inner.x + 2, inner.y, "（ありません）", DIM_TEXT, clip=inner)
            return
        for i in range(h):
            j = self.top + i
            if j >= len(self.rows):
                break
            left, right, ok = self.rows[j]
            sel = j == self.index
            st = CURSOR if sel else (TEXT if ok else DIM_TEXT)
            buf.put(inner.x, inner.y + i, ("▶" if sel else " ") + " " + left, st, clip=inner)
            if right:
                buf.put(inner.right - text_width(right) - 1, inner.y + i, right, st, clip=inner)
        if self.top > 0:
            buf.put(inner.right - 2, inner.y - 1, "▲", DIM_TEXT)
        if self.top + h < len(self.rows):
            buf.put(inner.right - 2, inner.bottom, "▼", DIM_TEXT)


class Overlay(Scene):
    """フィールドの上に重ねる画面の基底。会話（say）と選択肢（ask）の小さな仕組みを持つ。"""

    def __init__(self, field: "FieldScene"):
        self.field = field
        self.gd = field.gd
        self.st = field.st
        self.closed = False
        self.msg = MessageWindow()
        self.choice: Optional[ChoiceWindow] = None
        self._choice_cb: Optional[Callable[[int], None]] = None
        self._after_msg: Optional[Callable[[], None]] = None
        self._wait_effect = None
        self._after_effect: Optional[Callable[[], None]] = None

    # ---- 部品
    def say(self, lines: list[str] | str, then: Optional[Callable[[], None]] = None) -> None:
        if isinstance(lines, str):
            lines = [lines]
        self.msg.open([("", ln) for ln in lines])
        self._after_msg = then

    def ask(self, question: str, options: list[str], cb: Callable[[int], None],
            cancel_index: Optional[int] = None) -> None:
        self.msg.open([("", question)])
        self.msg.shown = 10 ** 6
        self._after_msg = None
        self.choice = ChoiceWindow(options, cancel_index=cancel_index)
        self._choice_cb = cb

    def effect(self, name: str, ms: int, then: Callable[[], None]) -> None:
        self._wait_effect = self.field.effects.start(name, [str(ms)], {})
        self._after_effect = then

    def close(self) -> None:
        self.closed = True
        self.app.pop()

    # ---- Scene
    def update(self, dt: float) -> None:
        self.msg.update(dt)
        self.field.effects.update(dt)
        if self._wait_effect is not None and self._wait_effect.done:
            self._wait_effect = None
            cb, self._after_effect = self._after_effect, None
            if cb:
                cb()

    def on_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        if self._wait_effect is not None:
            return
        if self.choice is not None:
            if Action.UP in actions:
                self.choice.move(-1)
            elif Action.DOWN in actions:
                self.choice.move(1)
            elif Action.OK in actions or (Action.CANCEL in actions and self.choice.cancel_index is not None):
                idx = self.choice.index if Action.OK in actions else self.choice.cancel_index
                cb = self._choice_cb
                self.choice = None
                self._choice_cb = None
                self.msg.close()
                if cb:
                    cb(idx)
            return
        if self.msg.active:
            if Action.OK in actions or Action.CANCEL in actions:
                if self.msg.advance():
                    self.msg.close()
                    cb, self._after_msg = self._after_msg, None
                    if cb:
                        cb()
            return
        self.on_ui_key(ev, actions)

    def on_ui_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        pass

    def draw(self, buf: Buffer) -> None:
        self.field.draw(buf, overlay=True)
        self.draw_ui(buf)
        H = buf.height
        if self.msg.active:
            self.msg.draw(buf, Rect(0, H - self.field.MSG_H, buf.width, self.field.MSG_H),
                          show_cursor=self.choice is None)
        if self.choice is not None:
            self.choice.draw(buf, buf.width - 1, H - self.field.MSG_H + 1)
        self.field.effects.apply_overlay(buf)

    def draw_ui(self, buf: Buffer) -> None:
        pass

    # ---- 共通の表示
    def area(self, buf: Buffer) -> Rect:
        """会話窓より上の全面（ここに施設のウィンドウを重ねる）。"""
        return Rect(0, 0, buf.width, buf.height - self.field.MSG_H)

    def columns(self, buf: Buffer, list_w: int = 46, list_h: int = 14) -> tuple[Rect, Rect]:
        """左にリスト、右（所持金の下）に説明を置く配置。"""
        a = self.area(buf)
        lw = min(list_w, a.w // 2)
        lrect = Rect(a.x + 1, a.y + 1, lw, min(list_h, a.h - 2))
        drect = Rect(lrect.right + 1, a.y + 4, max(10, a.right - lrect.right - 2), max(3, min(list_h, a.h - 5)))
        return lrect, drect

    def draw_gold(self, buf: Buffer) -> None:
        a = self.area(buf)
        text = f"所持金 {self.st.gold:>7} G"
        w = text_width(text) + 4
        inner = buf.box(Rect(a.right - w - 1, a.y, w, 3), FRAME, chars=BOX_SINGLE)
        buf.put(inner.x + 1, inner.y, text, GOLD_ST)

    def draw_detail(self, buf: Buffer, rect: Rect, title: str, lines: list[tuple[str, Style]]) -> None:
        inner = buf.box(rect, FRAME, title=title, chars=BOX_SINGLE)
        y = inner.y
        for text, st in lines:
            for ln in wrap(text, max(1, inner.w - 2)):
                if y >= inner.bottom:
                    return
                buf.put(inner.x + 1, y, ln, st, clip=inner)
                y += 1


# ====================================================================== ショップ
class ShopScene(Overlay):
    def __init__(self, field: "FieldScene", shop_id: str):
        super().__init__(field)
        self.shop = self.gd.shops[shop_id]
        self.mode = "top"
        self.list: Optional[ListWindow] = None
        self._top("いらっしゃい！　何にする？")

    def on_enter(self) -> None:
        pass

    def _top(self, text: str) -> None:
        self.mode = "top"
        self.list = None
        self.ask(text, ["かう", "うる", "やめる"], self._top_done, cancel_index=2)

    def _top_done(self, i: int) -> None:
        if i == 0:
            self._open_buy()
        elif i == 1:
            self._open_sell()
        else:
            self.say("またどうぞ！", then=self.close)

    # ---- 買う
    def _open_buy(self) -> None:
        self.mode = "buy"
        goods = [self.gd.items[i] for i in self.shop.goods if i in self.gd.items]
        self._goods = goods
        self.list = ListWindow([(it.name, f"{it.price} G", it.price <= self.st.gold) for it in goods])

    def _buy(self, it: Item) -> None:
        if it.price > self.st.gold:
            self.say("お金が足りないよ。")
            return

        def yes(i: int) -> None:
            if i != 0:
                return
            self.st.gold -= it.price
            self.st.add_item(it.id)
            self._open_buy_keep_cursor()
            able = [m for m in self.st.party if m.can_equip(it.id, self.gd)]
            if it.type == "equipment" and able:
                names = [m.name for m in able] + ["装備しない"]

                def eq(j: int) -> None:
                    if j < len(able):
                        old = self.st.equip(able[j], it.id, self.gd)
                        msg = f"{able[j].name}は{it.name}を装備した。"
                        if old:
                            msg += f"（{self.gd.items[old].name}は袋にしまった）"
                        self.say(["まいどあり！", msg])
                    else:
                        self.say("まいどあり！")
                self.ask("いま装備しますか？", names, eq, cancel_index=len(names) - 1)
            else:
                self.say("まいどあり！")
        self.ask(f"{it.name}を {it.price} G で買いますか？", ["はい", "いいえ"], yes, cancel_index=1)

    def _open_buy_keep_cursor(self) -> None:
        idx = self.list.index if self.list else 0
        self._open_buy()
        self.list.index = min(idx, max(0, len(self.list.rows) - 1))

    # ---- 売る
    def _sell_price(self, it: Item) -> int:
        return int(it.price * self.shop.sell_rate)

    def _open_sell(self) -> None:
        self.mode = "sell"
        items = [(self.gd.items[i], n) for i, n in self.st.items.items() if i in self.gd.items]
        items = [(it, n) for it, n in items if it.type != "key" and it.price > 0]
        self._bag = items
        self.list = ListWindow([(f"{it.name} ×{n}", f"{self._sell_price(it)} G", True) for it, n in items])

    def _sell(self, it: Item) -> None:
        price = self._sell_price(it)

        def yes(i: int) -> None:
            if i == 0:
                self.st.remove_item(it.id)
                self.st.gold += price
                idx = self.list.index
                self._open_sell()
                self.list.index = min(idx, max(0, len(self.list.rows) - 1))
                self.say(f"{it.name}を {price} G で買い取ったよ。")
        self.ask(f"{it.name}を {price} G で売りますか？", ["はい", "いいえ"], yes, cancel_index=1)

    # ---- 入力・描画
    def on_ui_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        if self.list is None:
            return
        if Action.UP in actions:
            self.list.move(-1)
        elif Action.DOWN in actions:
            self.list.move(1)
        elif Action.CANCEL in actions:
            self._top("ほかに何か？")
        elif Action.OK in actions and not self.list.empty:
            if self.mode == "buy":
                self._buy(self._goods[self.list.index])
            else:
                self._sell(self._bag[self.list.index][0])

    def _item_detail(self, it: Item) -> list[tuple[str, Style]]:
        lines = [(it.desc or "", TEXT)] if it.desc else []
        if it.type == "equipment":
            stat_txt = "  ".join(f"{STAT_NAMES.get(k, k)}+{v}" for k, v in it.stats.items() if v)
            lines.append((f"［装備］{stat_txt}", HEAD_ST))
            for m in self.st.party:
                if not m.can_equip(it.id, self.gd):
                    lines.append((f"{m.name}：装備できない", DIM_TEXT))
                    continue
                cur = m.equip.get(it.slot)
                parts = []
                for k in ("atk", "def", "mag", "agi"):
                    now = m.stat(k, self.gd)
                    after = now - (self.gd.items[cur].stats.get(k, 0) if cur else 0) + it.stats.get(k, 0)
                    if after != now:
                        parts.append(f"{STAT_NAMES[k]} {now}→{after}")
                mark = "（装備中）" if cur == it.id else ""
                lines.append((f"{m.name}：{'  '.join(parts) or '変化なし'}{mark}", TEXT))
        elif it.use:
            lines.append((f"［使用］{'戦闘中も使える' if it.use.get('battle') else 'フィールドで使う'}", HEAD_ST))
        return lines

    def draw_ui(self, buf: Buffer) -> None:
        a = self.area(buf)
        self.draw_gold(buf)
        if self.list is None:
            return
        lrect, drect = self.columns(buf, 40)
        self.list.draw(buf, lrect, title=f"{self.shop.name}（{'かう' if self.mode == 'buy' else 'うる'}）")
        if not self.list.empty:
            it = self._goods[self.list.index] if self.mode == "buy" else self._bag[self.list.index][0]
            self.draw_detail(buf, drect, it.name, self._item_detail(it))


# ====================================================================== 宿屋
class InnScene(Overlay):
    def __init__(self, field: "FieldScene", price: int):
        super().__init__(field)
        self.price = price
        if self._all_rested():
            # 全員 HP・MP 満タンで状態異常もない → 泊まっても意味がないので断る（お金も取らない）
            self.say(["旅人の宿へようこそ。", "……皆さん、とてもお元気そうですね。今はお休みにならなくても大丈夫ですよ。"],
                     then=self.close)
            return
        self.ask(f"旅人の宿へようこそ。一晩 {price} G です。お泊まりになりますか？",
                 ["泊まる", "やめる"], self._done, cancel_index=1)

    def _all_rested(self) -> bool:
        gd = self.gd
        return all(m.hp >= m.stat("hp", gd) and m.mp >= m.stat("mp", gd) and not m.status
                   for m in self.st.party)

    def _done(self, i: int) -> None:
        if i != 0:
            self.say("またお越しください。", then=self.close)
            return
        if self.st.gold < self.price:
            self.say("お金が足りないようですね…。", then=self.close)
            return
        self.st.gold -= self.price

        def rest() -> None:
            for m in self.st.party:
                m.hp, m.mp = m.stat("hp", self.gd), m.stat("mp", self.gd)
                m.status.clear()
            self.effect("fade_in", 600, lambda: self.say(
                ["おはようございます。", "ゆっくり休んで、体力と魔力が回復した！"], then=self.close))
        self.say("ごゆっくりどうぞ。", then=lambda: self.effect("fade_out", 600, rest))

    def draw_ui(self, buf: Buffer) -> None:
        self.draw_gold(buf)


# ====================================================================== 冒険者協会
class GuildScene(Overlay):
    def __init__(self, field: "FieldScene"):
        super().__init__(field)
        self.mode = "top"
        self.list: Optional[ListWindow] = None
        self._quests: list[Quest] = []
        self._top("冒険者協会へようこそ。ご用件は？")

    def _top(self, text: str) -> None:
        self.mode = "top"
        self.list = None
        self.ask(text, ["依頼を受ける", "依頼を報告する", "受けている依頼", "やめる"], self._top_done, cancel_index=3)

    def _top_done(self, i: int) -> None:
        if i == 0:
            self.mode = "accept"
            self._quests = Q.available(self.st, self.gd, self.field._cond)
            self.list = ListWindow([(f"[{q.rank or '-'}] {q.name}", Q.reward_text(self.gd, q), True) for q in self._quests])
            if self.list.empty:
                self._top("いまお願いできる依頼はありません。ほかにご用件は？")
        elif i in (1, 2):
            self.mode = "report" if i == 1 else "view"
            self._quests = Q.active(self.st, self.gd)
            self.list = ListWindow([(q.name, "達成！" if Q.goal_met(self.st, self.gd, q) else "", True)
                                    for q in self._quests])
            if self.list.empty:
                self._top("受けている依頼はありません。ほかにご用件は？")
        else:
            self.say("お気をつけて。", then=self.close)

    def on_ui_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        if self.list is None:
            return
        if Action.UP in actions:
            self.list.move(-1)
        elif Action.DOWN in actions:
            self.list.move(1)
        elif Action.CANCEL in actions:
            self._top("ほかにご用件は？")
        elif Action.OK in actions and not self.list.empty:
            q = self._quests[self.list.index]
            if self.mode == "accept":
                self._accept(q)
            elif self.mode == "report":
                self._report(q)

    def _accept(self, q: Quest) -> None:
        def yes(i: int) -> None:
            if i == 0:
                Q.accept(self.st, q)
                self._top(f"「{q.name}」をお願いします。終わったら報告に来てくださいね。")
        self.ask(f"「{q.name}」を受けますか？", ["受ける", "やめる"], yes, cancel_index=1)

    def _report(self, q: Quest) -> None:
        if not Q.goal_met(self.st, self.gd, q):
            self.say(f"まだ達成していないようです。（{Q.goal_text(self.st, self.gd, q)}）")
            return
        res = Q.complete(self.st, self.gd, q)
        if res.label:
            self.field.pending_labels.append(res.label)
        self.say(res.messages, then=lambda: self._top("お疲れさまでした。ほかにご用件は？"))

    def draw_ui(self, buf: Buffer) -> None:
        a = self.area(buf)
        self.draw_gold(buf)
        if self.list is None:
            return
        title = {"accept": "依頼掲示板", "report": "依頼の報告", "view": "受けている依頼"}[self.mode]
        lrect, drect = self.columns(buf, 48, 12)
        self.list.draw(buf, lrect, title=title)
        if self.list.empty:
            return
        q = self._quests[self.list.index]
        lines = [(q.desc, TEXT)] if q.desc else []
        lines += [(f"目標：{Q.goal_text(self.st, self.gd, q)}", HEAD_ST),
                  (f"報酬：{Q.reward_text(self.gd, q)}", GOLD_ST)]
        if q.repeatable:
            lines.append(("（何度でも受けられる）", DIM_TEXT))
        self.draw_detail(buf, drect, f"ランク {q.rank or '-'}", lines)


# ====================================================================== 仲間選択
class RecruitScene(Overlay):
    def __init__(self, field: "FieldScene", candidates: list[str], pick: int = 1, lv: str = ""):
        super().__init__(field)
        from ..world.growth import resolve_level
        self.target_lv = resolve_level(self.st, lv)      # 選び始めた時点のパーティで決める
        self.cands = [c for c in candidates if c in self.gd.characters and self.st.member(c) is None]
        self.left = min(pick, len(self.cands), max(0, self.field.game.manifest.party_max - len(self.st.party)))
        self.list = ListWindow([])
        self._refresh()
        if self.left <= 0:
            self.say("（仲間にできる人がいません）", then=self.close)
        else:
            self.say(f"一緒に旅をする仲間を {self.left} 人選んでください。")

    def _join_lv(self, c) -> int:
        """加入するときのレベル（lv= 指定があればそこまで上がる）。"""
        return max(c.lv, self.target_lv or 0)

    def _refresh(self) -> None:
        rows = []
        for cid in self.cands:
            c = self.gd.characters[cid]
            job = self.gd.jobs.get(c.job)
            rows.append((f"{pad(c.name, 10)}{job.name if job else ''}", f"Lv {self._join_lv(c)}", True))
        self.list.rows = rows
        self.list.index = min(self.list.index, max(0, len(rows) - 1))

    def on_ui_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        if Action.UP in actions:
            self.list.move(-1)
        elif Action.DOWN in actions:
            self.list.move(1)
        elif Action.CANCEL in actions:
            self.say(f"あと {self.left} 人選んでください。")
        elif Action.OK in actions and not self.list.empty:
            cid = self.cands[self.list.index]
            c = self.gd.characters[cid]

            def yes(i: int) -> None:
                if i != 0:
                    return
                from ..world.growth import raise_to_level
                m = Member.from_data(self.gd, cid)
                raise_to_level(m, self.gd, self.target_lv)
                self.st.party.append(m)
                self.cands.remove(cid)
                self.left -= 1
                self._refresh()
                if self.left <= 0 or not self.cands:
                    self.say(f"{c.name}が仲間になった！", then=self.close)
                else:
                    self.say([f"{c.name}が仲間になった！", f"あと {self.left} 人選んでください。"])
            self.ask(f"{c.name}を仲間にしますか？", ["はい", "いいえ"], yes, cancel_index=1)

    def draw_ui(self, buf: Buffer) -> None:
        a = self.area(buf)
        lrect, drect = self.columns(buf, 34, 10)
        self.list.draw(buf, lrect, title=f"仲間を選ぶ（あと {self.left} 人）")
        if self.list.empty:
            return
        c = self.gd.characters[self.cands[self.list.index]]
        job = self.gd.jobs.get(c.job)
        s = c.stats
        lines = [
            (f"{job.name if job else c.job}  Lv {self._join_lv(c)}"
             + ("（能力は Lv {} のとき）".format(c.lv) if self._join_lv(c) != c.lv else ""), HEAD_ST),
            (f"HP {s.get('hp', 0):>3}  MP {s.get('mp', 0):>3}", TEXT),
            (f"攻撃 {s.get('atk', 0):>3}  防御 {s.get('def', 0):>3}", TEXT),
            (f"魔力 {s.get('mag', 0):>3}  素早 {s.get('agi', 0):>3}", TEXT),
            ("", TEXT),
            (f"「{c.recruit_text}」" if c.recruit_text else "", Style.of("bright_white")),
        ]
        self.draw_detail(buf, drect, c.name, lines)
