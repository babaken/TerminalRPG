"""施設画面：ショップ・宿屋・冒険者協会・仲間選択（基本設計 4.7 / 10.5 @shop @inn @guild @recruit）。

どれもフィールドの上に重ねて表示する画面（Overlay）。スクリプトの命令から開かれ、
閉じるとスクリプトの続きが実行される。
"""
from __future__ import annotations

from ..i18n import tr

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
            buf.put(inner.x + 2, inner.y, tr('（ありません）'), DIM_TEXT, clip=inner)
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
        text = tr('所持金 {0:>7} G', self.st.gold)
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


MAX_STACK = 99           # 1 種類のアイテムを持てる数の上限（ショップで個数を選ぶときの上限）


# ====================================================================== ショップ
class ShopScene(Overlay):
    def __init__(self, field: "FieldScene", shop_id: str):
        super().__init__(field)
        self.shop = self.gd.shops[shop_id]
        self.mode = "top"
        self.list: Optional[ListWindow] = None
        self._top(tr('いらっしゃい！\u3000何にする？'))

    def on_enter(self) -> None:
        pass

    def _top(self, text: str) -> None:
        self.mode = "top"
        self.list = None
        self.ask(text, [tr('かう'), tr('うる'), tr('やめる')], self._top_done, cancel_index=2)

    def _top_done(self, i: int) -> None:
        if i == 0:
            self._open_buy()
        elif i == 1:
            self._open_sell()
        else:
            self.say(tr('またどうぞ！'), then=self.close)

    # ---- 買う
    def _open_buy(self) -> None:
        self.mode = "buy"
        goods = [self.gd.items[i] for i in self.shop.goods if i in self.gd.items]
        self._goods = goods
        self.list = ListWindow([(it.name, f"{it.price} G", it.price <= self.st.gold) for it in goods])

    def _buy(self, it: Item) -> None:
        if it.price > self.st.gold:
            self.say(tr('お金が足りないよ。'))
            return
        if it.type != "equipment":
            # 道具は個数を選んで買う（装備品は 1 つずつ。買ったあと装備するか聞くため）
            have = self.st.items.get(it.id, 0)
            most = MAX_STACK - have
            if it.price > 0:
                most = min(most, self.st.gold // it.price)
            if most <= 0:
                self.say(tr('それ以上は持てないよ。'))
                return
            self._ask_qty("buy", it, most)
            return

        def yes(i: int) -> None:
            if i != 0:
                return
            self.st.gold -= it.price
            self.st.add_item(it.id)
            self._open_buy_keep_cursor()
            able = [m for m in self.st.party if m.can_equip(it.id, self.gd)]
            if it.type == "equipment" and able:
                names = [m.name for m in able] + [tr('装備しない')]

                def eq(j: int) -> None:
                    if j < len(able):
                        old = self.st.equip(able[j], it.id, self.gd)
                        msg = tr('{0}は{1}を装備した。', able[j].name, it.name)
                        if old:
                            msg += tr('（{0}は袋にしまった）', self.gd.items[old].name)
                        self.say([tr('まいどあり！'), msg])
                    else:
                        self.say(tr('まいどあり！'))
                self.ask(tr('いま装備しますか？'), names, eq, cancel_index=len(names) - 1)
            else:
                self.say(tr('まいどあり！'))
        self.ask(tr('{0}を {1} G で買いますか？', it.name, it.price), [tr('はい'), tr('いいえ')], yes, cancel_index=1)

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
        n = self.st.items.get(it.id, 0)
        if n > 1:
            self._ask_qty("sell", it, n)
            return
        self._sell_n(it, 1)

    def _sell_n(self, it: Item, n: int) -> None:
        price = self._sell_price(it) * n
        what = it.name if n == 1 else tr('{0}を {1} 個、合計', it.name, n)

        def yes(i: int) -> None:
            if i == 0:
                self.st.remove_item(it.id, n)
                self.st.gold += price
                idx = self.list.index
                self._open_sell()
                self.list.index = min(idx, max(0, len(self.list.rows) - 1))
                self.say(tr('{0} {1} G で買い取ったよ。', what if n > 1 else tr('{0}を', it.name), price))
        self.ask(tr('{0} {1} G で売りますか？', what if n > 1 else tr('{0}を', it.name), price), [tr('はい'), tr('いいえ')], yes, cancel_index=1)

    # ---- 個数
    def _ask_qty(self, kind: str, it: Item, most: int) -> None:
        self.qty_kind, self.qty_item, self.qty_max, self.qty = kind, it, most, 1
        self.mode = "qty_" + kind

    def _qty_key(self, actions: frozenset[Action]) -> None:
        d = 1 if Action.UP in actions else -1 if Action.DOWN in actions else \
            10 if Action.RIGHT in actions else -10 if Action.LEFT in actions else 0
        if d:
            if self.qty + d > self.qty_max and abs(d) == 1:
                self.qty = 1                         # 上限を超えたら 1 に戻る（↑を押し続けて一周）
            elif self.qty + d < 1 and abs(d) == 1:
                self.qty = self.qty_max
            else:
                self.qty = min(self.qty_max, max(1, self.qty + d))
        elif Action.CANCEL in actions:
            self.mode = self.qty_kind
        elif Action.OK in actions:
            kind, it, n = self.qty_kind, self.qty_item, self.qty
            self.mode = kind
            if kind == "buy":
                self._buy_n(it, n)
            else:
                self._sell_n(it, n)

    def _buy_n(self, it: Item, n: int) -> None:
        total = it.price * n

        def yes(i: int) -> None:
            if i != 0:
                return
            self.st.gold -= total
            self.st.add_item(it.id, n)
            self._open_buy_keep_cursor()
            self.say(tr('まいどあり！'))
        what = tr('{0}を', it.name) if n == 1 else tr('{0}を {1} 個、合計', it.name, n)
        self.ask(tr('{0} {1} G で買いますか？', what, total), [tr('はい'), tr('いいえ')], yes, cancel_index=1)

    # ---- 入力・描画
    def on_ui_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        if self.list is None:
            return
        if self.mode.startswith("qty_"):
            self._qty_key(actions)
            return
        if Action.UP in actions:
            self.list.move(-1)
        elif Action.DOWN in actions:
            self.list.move(1)
        elif Action.CANCEL in actions:
            self._top(tr('ほかに何か？'))
        elif Action.OK in actions and not self.list.empty:
            if self.mode == "buy":
                self._buy(self._goods[self.list.index])
            else:
                self._sell(self._bag[self.list.index][0])

    def _item_detail(self, it: Item) -> list[tuple[str, Style]]:
        lines = [(it.desc or "", TEXT)] if it.desc else []
        if it.type == "equipment":
            stat_txt = "  ".join(f"{tr(STAT_NAMES.get(k, k))}+{v}" for k, v in it.stats.items() if v)
            lines.append((tr('［装備］{0}', stat_txt), HEAD_ST))
            for m in self.st.party:
                if not m.can_equip(it.id, self.gd):
                    lines.append((tr('{0}：装備できない', m.name), DIM_TEXT))
                    continue
                cur = m.equip.get(it.slot)
                parts = []
                for k in ("atk", "def", "mag", "agi"):
                    now = m.stat(k, self.gd)
                    after = now - (self.gd.items[cur].stats.get(k, 0) if cur else 0) + it.stats.get(k, 0)
                    if after != now:
                        parts.append(f"{tr(STAT_NAMES[k])} {now}→{after}")
                mark = tr('（装備中）') if cur == it.id else ""
                lines.append((tr('{0}：{1}{2}', m.name, '  '.join(parts) or tr('変化なし'), mark), TEXT))
        elif it.use:
            lines.append((tr('［使用］{0}', tr('戦闘中も使える') if it.use.get('battle') else tr('フィールドで使う')), HEAD_ST))
        return lines

    def draw_ui(self, buf: Buffer) -> None:
        a = self.area(buf)
        self.draw_gold(buf)
        if self.list is None:
            return
        lrect, drect = self.columns(buf, 40)
        buying = self.mode in ("buy", "qty_buy")
        self.list.draw(buf, lrect, title=tr('{0}（{1}）', self.shop.name, tr('かう') if buying else tr('うる')))
        if not self.list.empty:
            it = self._goods[self.list.index] if buying else self._bag[self.list.index][0]
            self.draw_detail(buf, drect, it.name, self._item_detail(it))
        if self.mode.startswith("qty_"):
            self._draw_qty(buf, lrect)

    def _draw_qty(self, buf: Buffer, lrect: Rect) -> None:
        it = self.qty_item
        unit = it.price if self.qty_kind == "buy" else self._sell_price(it)
        have = self.st.items.get(it.id, 0)
        rect = Rect(lrect.x + 2, min(lrect.bottom - 6, lrect.y + 2 + self.list.index), lrect.w - 4, 6)
        inner = buf.box(rect, Style.of("bright_white"), title=tr('いくつ？'), chars=BOX_SINGLE)
        buf.fill(inner, " ")
        buf.put(inner.x + 1, inner.y, tr('{0}（持っている数 {1}）', it.name, have), TEXT, clip=inner)
        buf.put(inner.x + 1, inner.y + 1, tr('◀ {0:>2} 個 ▶   合計 {1} G', self.qty, unit * self.qty), GOLD_ST, clip=inner)
        buf.put(inner.x + 1, inner.y + 2, tr('↑↓：1 つずつ  ←→：10 ずつ（最大 {0}）', self.qty_max), DIM_TEXT, clip=inner)
        buf.put(inner.x + 1, inner.y + 3, tr('Enter：決定  Esc：やめる'), DIM_TEXT, clip=inner)


# ====================================================================== 宿屋
class InnScene(Overlay):
    def __init__(self, field: "FieldScene", price: int):
        super().__init__(field)
        self.price = price
        if self._all_rested():
            # 全員 HP・MP 満タンで状態異常もない → 泊まっても意味がないので断る（お金も取らない）
            self.say([tr('旅人の宿へようこそ。'), tr('……皆さん、とてもお元気そうですね。今はお休みにならなくても大丈夫ですよ。')],
                     then=self.close)
            return
        self.ask(tr('旅人の宿へようこそ。一晩 {0} G です。お泊まりになりますか？', price),
                 [tr('泊まる'), tr('やめる')], self._done, cancel_index=1)

    def _all_rested(self) -> bool:
        gd = self.gd
        return all(m.hp >= m.stat("hp", gd) and m.mp >= m.stat("mp", gd) and m.sp >= m.max_sp(gd) and not m.status
                   for m in self.st.party)

    def _done(self, i: int) -> None:
        if i != 0:
            self.say(tr('またお越しください。'), then=self.close)
            return
        if self.st.gold < self.price:
            self.say(tr('お金が足りないようですね…。'), then=self.close)
            return
        self.st.gold -= self.price

        def rest() -> None:
            for m in self.st.party:
                m.hp, m.mp = m.stat("hp", self.gd), m.stat("mp", self.gd)
                m.fill_sp(self.gd)
                m.status.clear()
            self.effect("fade_in", 600, lambda: self.say(
                [tr('おはようございます。'), tr('ゆっくり休んで、体力と魔力が回復した！')], then=self.close))
        self.say(tr('ごゆっくりどうぞ。'), then=lambda: self.effect("fade_out", 600, rest))

    def draw_ui(self, buf: Buffer) -> None:
        self.draw_gold(buf)


# ====================================================================== 冒険者協会
class GuildScene(Overlay):
    def __init__(self, field: "FieldScene"):
        super().__init__(field)
        self.mode = "top"
        self.list: Optional[ListWindow] = None
        self._quests: list[Quest] = []
        self._top(tr('冒険者協会へようこそ。ご用件は？'))

    def _top(self, text: str) -> None:
        self.mode = "top"
        self.list = None
        self.ask(text, [tr('依頼を受ける'), tr('依頼を報告する'), tr('受けている依頼'), tr('やめる')], self._top_done, cancel_index=3)

    def _top_done(self, i: int) -> None:
        if i == 0:
            self.mode = "accept"
            self._quests = Q.available(self.st, self.gd, self.field._cond, slots=self.field.game.manifest.random_quests)
            self.list = ListWindow([(f"[{q.rank or '-'}] {q.name}", Q.reward_text(self.gd, q), True) for q in self._quests])
            if self.list.empty:
                self._top(tr('いまお願いできる依頼はありません。ほかにご用件は？'))
        elif i in (1, 2):
            self.mode = "report" if i == 1 else "view"
            self._quests = Q.active(self.st, self.gd)
            self.list = ListWindow([(q.name, tr('達成！') if Q.goal_met(self.st, self.gd, q) else "", True)
                                    for q in self._quests])
            if self.list.empty:
                self._top(tr('受けている依頼はありません。ほかにご用件は？'))
        else:
            self.say(tr('お気をつけて。'), then=self.close)

    def on_ui_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        if self.list is None:
            return
        if Action.UP in actions:
            self.list.move(-1)
        elif Action.DOWN in actions:
            self.list.move(1)
        elif Action.CANCEL in actions:
            self._top(tr('ほかにご用件は？'))
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
                self._top(tr('「{0}」をお願いします。終わったら報告に来てくださいね。', q.name))
        self.ask(tr('「{0}」を受けますか？', q.name), [tr('受ける'), tr('やめる')], yes, cancel_index=1)

    def _report(self, q: Quest) -> None:
        if not Q.goal_met(self.st, self.gd, q):
            self.say(tr('まだ達成していないようです。（{0}）', Q.goal_text(self.st, self.gd, q)))
            return
        res = Q.complete(self.st, self.gd, q)
        if res.label:
            self.field.pending_labels.append(res.label)
        self.say(res.messages, then=lambda: self._top(tr('お疲れさまでした。ほかにご用件は？')))

    def draw_ui(self, buf: Buffer) -> None:
        a = self.area(buf)
        self.draw_gold(buf)
        if self.list is None:
            return
        title = {"accept": tr('依頼掲示板'), "report": tr('依頼の報告'), "view": tr('受けている依頼')}[self.mode]
        lrect, drect = self.columns(buf, 48, 12)
        self.list.draw(buf, lrect, title=title)
        if self.list.empty:
            return
        q = self._quests[self.list.index]
        lines = [(q.desc, TEXT)] if q.desc else []
        lines += [(tr('目標：{0}', Q.goal_text(self.st, self.gd, q)), HEAD_ST),
                  (tr('報酬：{0}', Q.reward_text(self.gd, q)), GOLD_ST)]
        if q.repeatable:
            lines.append((tr('（何度でも受けられる）'), DIM_TEXT))
        self.draw_detail(buf, drect, tr('ランク {0}', q.rank or '-'), lines)


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
            self.say(tr('（仲間にできる人がいません）'), then=self.close)
        else:
            self.say(tr('一緒に旅をする仲間を {0} 人選んでください。', self.left))

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
            self.say(tr('あと {0} 人選んでください。', self.left))
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

                def joined() -> None:                    # 名前を付けたあと（name_input の仲間）
                    if self.left <= 0 or not self.cands:
                        self.say(tr('{0}が仲間になった！', m.name), then=self.close)
                    else:
                        self.say([tr('{0}が仲間になった！', m.name), tr('あと {0} 人選んでください。', self.left)])
                self.field.ask_member_name(m, joined)
            self.ask(tr('{0}を仲間にしますか？', c.name), [tr('はい'), tr('いいえ')], yes, cancel_index=1)

    def draw_ui(self, buf: Buffer) -> None:
        a = self.area(buf)
        lrect, drect = self.columns(buf, 34, 10)
        self.list.draw(buf, lrect, title=tr('仲間を選ぶ（あと {0} 人）', self.left))
        if self.list.empty:
            return
        c = self.gd.characters[self.cands[self.list.index]]
        job = self.gd.jobs.get(c.job)
        s = c.stats
        lines = [
            (f"{job.name if job else c.job}  Lv {self._join_lv(c)}"
             + (tr('（能力は Lv {} のとき）').format(c.lv) if self._join_lv(c) != c.lv else ""), HEAD_ST),
            (f"HP {s.get('hp', 0):>3}  MP {s.get('mp', 0):>3}", TEXT),
            (tr('攻撃 {0:>3}  防御 {1:>3}', s.get('atk', 0), s.get('def', 0)), TEXT),
            (tr('魔力 {0:>3}  素早 {1:>3}', s.get('mag', 0), s.get('agi', 0)), TEXT),
            ("", TEXT),
            (tr('「{0}」', c.recruit_text) if c.recruit_text else "", Style.of("bright_white")),
        ]
        self.draw_detail(buf, drect, c.name, lines)
