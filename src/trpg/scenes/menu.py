"""フィールドメニュー（要件 4.8）：どうぐ・スキル・そうび・つよさ・いらい・システム。

フィールドの上に重ねる画面。各階層は「ビュー」（リスト＋決定時の処理＋説明欄）として積み、
Esc でひとつ戻る（最上位で Esc ならメニューを閉じる）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

from ..data.models import EQUIP_SLOTS
from ..term import Action, Buffer, KeyEvent, Rect, Style, pad, text_width
from ..term.buffer import BOX_SINGLE
from ..ui.widgets import DIM_TEXT, FRAME, TEXT
from ..world import items as I
from ..world import quests as Q
from ..world.growth import exp_for_next, skills_of
from ..world.state import Member
from .facility import GOLD_ST, HEAD_ST, STAT_NAMES, ListWindow, Overlay

if TYPE_CHECKING:
    from .field import FieldScene

SLOT_NAMES = {"weapon": "武器", "armor": "防具", "shield": "盾", "accessory": "装飾"}
TOP = ["どうぐ", "スキル", "そうび", "つよさ", "いらい", "システム", "とじる"]
MENU_W = 16


@dataclass
class View:
    title: str
    list: ListWindow
    on_ok: Callable[[int], None]
    detail: Optional[Callable[[int], list[tuple[str, Style]]]] = None
    payload: list = field(default_factory=list)


class MenuScene(Overlay):
    def __init__(self, field: "FieldScene"):
        super().__init__(field)
        self.views: list[View] = []
        self.status_member: Optional[Member] = None
        self._push(View("メニュー", ListWindow([(t, "", True) for t in TOP]), self._top_ok))

    # ================================================================ ビュー操作
    def _push(self, v: View) -> None:
        self.views.append(v)

    def _pop(self) -> None:
        if len(self.views) > 1:
            self.views.pop()
        else:
            self.close()

    def _back_to(self, depth: int) -> None:
        del self.views[depth:]

    def _refresh(self, rows: list[tuple[str, str, bool]], payload: Optional[list] = None) -> None:
        v = self.views[-1]
        v.list.rows = rows
        v.list.index = min(v.list.index, max(0, len(rows) - 1))
        if payload is not None:
            v.payload = payload

    def on_ui_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        if self.status_member is not None:
            if Action.OK in actions or Action.CANCEL in actions:
                self.status_member = None
            elif Action.LEFT in actions or Action.RIGHT in actions:
                party = self.st.party
                i = party.index(self.status_member)
                self.status_member = party[(i + (1 if Action.RIGHT in actions else -1)) % len(party)]
            return
        v = self.views[-1]
        if Action.UP in actions:
            v.list.move(-1)
        elif Action.DOWN in actions:
            v.list.move(1)
        elif Action.CANCEL in actions or Action.MENU in actions:
            self._pop()
        elif Action.OK in actions and not v.list.empty:
            if v.list.rows[v.list.index][2]:
                v.on_ok(v.list.index)

    # ================================================================ 共通：仲間を選ぶ
    def _member_rows(self) -> list[tuple[str, str, bool]]:
        rows = []
        for m in self.st.party:
            hp = f"HP {m.hp:>3}/{m.max_hp:<3}" if m.alive else "たおれている"
            rows.append((pad(m.name, 10), f"{hp} MP {m.mp:>3}/{m.max_mp:<3}", True))
        return rows

    def _pick_member(self, title: str, cb: Callable[[Member], None]) -> None:
        self._push(View(title, ListWindow(self._member_rows()),
                        lambda i: cb(self.st.party[i]), lambda i: self._member_detail(self.st.party[i])))

    def _member_detail(self, m: Member) -> list[tuple[str, Style]]:
        job = self.gd.jobs.get(m.job)
        st_names = "・".join(self.gd.statuses[s].name for s in m.status if s in self.gd.statuses)
        lines = [(f"{job.name if job else m.job}  Lv {m.lv}", HEAD_ST),
                 (f"HP {m.hp}/{m.max_hp}   MP {m.mp}/{m.max_mp}", TEXT)]
        if st_names:
            lines.append((f"状態：{st_names}", Style.of("bright_magenta")))
        return lines

    # ================================================================ 最上位
    def _top_ok(self, i: int) -> None:
        name = TOP[i]
        if name == "どうぐ":
            self._open_items()
        elif name == "スキル":
            self._pick_member("だれのスキル？", self._open_skills)
        elif name == "そうび":
            self._pick_member("だれのそうび？", self._open_equip)
        elif name == "つよさ":
            self.status_member = self.st.party[0]
        elif name == "いらい":
            self._open_quests()
        elif name == "システム":
            self._open_system()
        else:
            self.close()

    # ================================================================ どうぐ
    def _item_rows(self):
        ids = [i for i in self.st.items if i in self.gd.items and self.st.items[i] > 0]
        order = {"consumable": 0, "equipment": 1, "key": 2}
        ids.sort(key=lambda i: (order.get(self.gd.items[i].type, 3), self.gd.items[i].name))
        rows = []
        for iid in ids:
            it = self.gd.items[iid]
            mark = "★" if it.type == "key" else ""
            rows.append((f"{mark}{it.name}", f"×{self.st.items[iid]}", True))
        return rows, ids

    def _open_items(self) -> None:
        rows, ids = self._item_rows()
        if not rows:
            self.say("何も持っていない。")
            return
        self._push(View("どうぐ", ListWindow(rows, 12), self._item_ok, self._item_detail, ids))

    def _reload_items(self) -> None:
        rows, ids = self._item_rows()
        if not rows:
            self._back_to(1)
            return
        self._refresh(rows, ids)

    def _item_detail(self, i: int) -> list[tuple[str, Style]]:
        it = self.gd.items[self.views[-1].payload[i]]
        lines = [(it.desc, TEXT)] if it.desc else []
        if it.type == "equipment":
            stat = "  ".join(f"{STAT_NAMES.get(k, k)}+{v}" for k, v in it.stats.items() if v)
            lines.append((f"［装備品・{SLOT_NAMES.get(it.slot, it.slot)}］{stat}", HEAD_ST))
        elif it.type == "key":
            lines.append(("［だいじなもの］", HEAD_ST))
        if it.use:
            where = "フィールド・戦闘" if it.use.get("field") and it.use.get("battle") else \
                ("フィールド" if it.use.get("field") else "戦闘中のみ")
            lines.append((f"［使用］{where}", DIM_TEXT))
        return lines

    def _item_ok(self, i: int) -> None:
        iid = self.views[-1].payload[i]
        it = self.gd.items[iid]
        opts = ["つかう", "すてる", "やめる"]

        def chosen(k: int) -> None:
            if k == 0:
                self._use_item(iid)
            elif k == 1:
                self._discard(iid)
        self.ask(f"{it.name}をどうする？", opts, chosen, cancel_index=2)

    def _use_item(self, iid: str) -> None:
        it = self.gd.items[iid]
        if not I.usable_on_field(it):
            self.say("ここでは使えない。" if it.use else f"{it.name}は使うものではない。")
            return

        def apply(target: Optional[Member]) -> None:
            res = I.use_item(self.st, self.gd, iid, target)
            if res.label:
                # 帰還の巻物など：メニューを閉じてスクリプトを実行
                self.field.pending_labels.append(res.label)
                self.close()
                return
            depth = 2
            self._back_to(depth)
            self._reload_items()
            self.say(res.messages)
        if I.needs_target(it):
            self._pick_member(f"だれに{it.name}を使う？", apply)
        else:
            apply(None)

    def _discard(self, iid: str) -> None:
        it = self.gd.items[iid]
        if it.type == "key":
            self.say("それを捨てるなんて とんでもない！")
            return

        def yes(k: int) -> None:
            if k == 0:
                self.st.remove_item(iid)
                self._reload_items()
                self.say(f"{it.name}を捨てた。")
        self.ask(f"{it.name}を 1 つ捨てますか？", ["はい", "いいえ"], yes, cancel_index=1)

    # ================================================================ スキル
    def _open_skills(self, m: Member) -> None:
        sks = I.field_skills(m, self.gd)
        all_sk = [self.gd.skills[s] for s in skills_of(m, self.gd)]
        if not all_sk:
            self.say(f"{m.name}はスキルを覚えていない。")
            return
        rows = [(sk.name, f"MP {sk.mp}", sk in sks and m.mp >= sk.mp and m.alive) for sk in all_sk]

        def ok(i: int) -> None:
            sk = all_sk[i]

            def apply(t: Member) -> None:
                res = I.use_skill(self.gd, m, sk, t, self.st.party)
                self._back_to(3)
                v = self.views[-1]
                v.list.rows = [(s.name, f"MP {s.mp}", s in sks and m.mp >= s.mp) for s in all_sk]
                self.say(res.messages)
            if sk.target == "ally_one":
                self._pick_member(f"だれに{sk.name}を使う？", apply)
            else:
                apply(m)

        def detail(i: int) -> list[tuple[str, Style]]:
            sk = all_sk[i]
            lines = [(sk.desc, TEXT)] if sk.desc else []
            if sk not in sks:
                lines.append(("戦闘中に使うスキル", DIM_TEXT))
            return lines
        self._push(View(f"{m.name}のスキル", ListWindow(rows), ok, detail))

    # ================================================================ そうび
    def _slot_rows(self, m: Member) -> list[tuple[str, str, bool]]:
        rows = []
        for slot in EQUIP_SLOTS:
            iid = m.equip.get(slot)
            name = self.gd.items[iid].name if iid in self.gd.items else "（なし）"
            rows.append((f"{SLOT_NAMES[slot]}：{name}", "", True))
        return rows

    def _open_equip(self, m: Member) -> None:
        def ok(i: int) -> None:
            self._open_equip_slot(m, EQUIP_SLOTS[i])
        self._push(View(f"{m.name}のそうび", ListWindow(self._slot_rows(m)), ok,
                        lambda i: self._status_lines(m, short=True)))

    def _open_equip_slot(self, m: Member, slot: str) -> None:
        cands = [iid for iid in self.st.items if iid in self.gd.items and self.gd.items[iid].slot == slot
                 and self.gd.items[iid].type == "equipment" and m.can_equip(iid, self.gd)]
        rows = [(self.gd.items[iid].name, f"×{self.st.items[iid]}", True) for iid in cands]
        payload: list = list(cands)
        if m.equip.get(slot):
            rows.append(("はずす", "", True))
            payload.append(None)
        if not rows:
            self.say("装備できるものを持っていない。")
            return

        def ok(i: int) -> None:
            iid = payload[i]
            if iid is None:
                old = self.st.unequip(m, slot)
                msg = f"{m.name}は{self.gd.items[old].name}をはずした。"
            else:
                old = self.st.equip(m, iid, self.gd)
                msg = f"{m.name}は{self.gd.items[iid].name}を装備した。"
            self.views.pop()
            self._refresh(self._slot_rows(m))
            self.say(msg)

        def detail(i: int) -> list[tuple[str, Style]]:
            iid = payload[i]
            cur = m.equip.get(slot)
            lines = []
            for k in ("atk", "def", "mag", "agi", "luk"):
                now = m.stat(k, self.gd)
                after = now - (self.gd.items[cur].stats.get(k, 0) if cur else 0) + \
                    (self.gd.items[iid].stats.get(k, 0) if iid else 0)
                st = Style.of("bright_green") if after > now else (Style.of("bright_red") if after < now else TEXT)
                lines.append((f"{pad(STAT_NAMES[k], 4)} {now:>3} → {after:>3}", st))
            if iid and self.gd.items[iid].desc:
                lines.insert(0, (self.gd.items[iid].desc, DIM_TEXT))
            return lines
        self._push(View(f"{SLOT_NAMES[slot]}を選ぶ", ListWindow(rows), ok, detail, payload))

    # ================================================================ つよさ
    def _status_lines(self, m: Member, short: bool = False) -> list[tuple[str, Style]]:
        job = self.gd.jobs.get(m.job)
        lines = [(f"{job.name if job else m.job}  Lv {m.lv}", HEAD_ST)]
        if not short:
            nxt = exp_for_next(m.lv)
            lines.append((f"経験値 {m.exp}（次の Lv まで {max(0, nxt - m.exp)}）", TEXT))
        lines.append((f"HP {m.hp}/{m.max_hp}   MP {m.mp}/{m.max_mp}", TEXT))
        for k in ("atk", "def", "mag", "agi", "luk"):
            bonus = m.equip_bonus(k, self.gd)
            extra = f"（+{bonus}）" if bonus > 0 else (f"（{bonus}）" if bonus < 0 else "")
            lines.append((f"{pad(STAT_NAMES[k], 4)} {m.stat(k, self.gd):>3}{extra}", TEXT))
        if short:
            return lines
        lines.append(("", TEXT))
        for slot in EQUIP_SLOTS:
            iid = m.equip.get(slot)
            lines.append((f"{SLOT_NAMES[slot]}：{self.gd.items[iid].name if iid in self.gd.items else '（なし）'}", TEXT))
        sks = [self.gd.skills[s].name for s in skills_of(m, self.gd)]
        lines.append((f"スキル：{'、'.join(sks) if sks else 'なし'}", TEXT))
        if m.status:
            names = "・".join(self.gd.statuses[s].name for s in m.status if s in self.gd.statuses)
            lines.append((f"状態：{names}", Style.of("bright_magenta")))
        return lines

    # ================================================================ いらい
    def _open_quests(self) -> None:
        qs = Q.active(self.st, self.gd)
        if not qs:
            self.say("受けている依頼はない。")
            return
        rows = [(q.name, "達成！" if Q.goal_met(self.st, self.gd, q) else "", True) for q in qs]

        def detail(i: int) -> list[tuple[str, Style]]:
            q = qs[i]
            out = [(q.desc, TEXT)] if q.desc else []
            out += [(f"目標：{Q.goal_text(self.st, self.gd, q)}", HEAD_ST), (f"報酬：{Q.reward_text(self.gd, q)}", GOLD_ST)]
            if Q.goal_met(self.st, self.gd, q):
                out.append(("協会に報告しよう。", Style.of("bright_green")))
            return out
        self._push(View("受けている依頼", ListWindow(rows), lambda i: None, detail))

    # ================================================================ システム
    def _open_system(self) -> None:
        opts = ["セーブ", "タイトルにもどる", "ゲームをおわる", "やめる"]

        def chosen(k: int) -> None:
            if k == 0:
                if self.game_manifest().save == "save_point_only":
                    self.say("ここではセーブできない。（セーブできる場所で行ってください）")
                else:
                    from .saveload import SaveLoadScene
                    self.app.push(SaveLoadScene(self.field.game, "save", field=self.field))
            elif k == 1:
                self.ask("タイトルにもどりますか？（セーブしていない進行は失われます）", ["はい", "いいえ"],
                         lambda j: self._to_title() if j == 0 else None, cancel_index=1)
            elif k == 2:
                self.ask("ゲームをおわりますか？（セーブしていない進行は失われます）", ["はい", "いいえ"],
                         lambda j: self.app.quit() if j == 0 else None, cancel_index=1)
        self.ask("システム", opts, chosen, cancel_index=3)

    def game_manifest(self):
        return self.field.game.manifest

    def _to_title(self) -> None:
        self.close()
        self.field.back_to_title()

    # ================================================================ 描画
    def draw_ui(self, buf: Buffer) -> None:
        a = self.area(buf)
        buf.fill(a, " ")                 # 下のフィールドが透けないように消す
        self.draw_gold(buf)
        top = self.views[0]
        top.list.draw(buf, Rect(a.x + 1, a.y, MENU_W, len(TOP) + 2), title="メニュー")
        x0 = a.x + 1 + MENU_W + 1
        if self.status_member is not None:
            m = self.status_member
            rect = Rect(x0, a.y + 3, min(56, a.right - x0 - 1), min(a.h - 3, 20))
            self.draw_detail(buf, rect, f"{m.name}のつよさ（←→ で切替）", self._status_lines(m))
            return
        if len(self.views) == 1:
            self._draw_party(buf, Rect(x0, a.y + 3, min(60, a.right - x0 - 1), min(a.h - 3, 3 * len(self.st.party) + 2)))
            return
        v = self.views[-1]
        lw = min(36, (a.right - x0) // 2)
        lrect = Rect(x0, a.y + 3, lw, min(14, a.h - 3))
        v.list.draw(buf, lrect, title=v.title)
        if v.detail and not v.list.empty:
            drect = Rect(lrect.right + 1, a.y + 3, max(10, a.right - lrect.right - 2), min(14, a.h - 3))
            self.draw_detail(buf, drect, "", v.detail(v.list.index))

    def _draw_party(self, buf: Buffer, rect: Rect) -> None:
        inner = buf.box(rect, FRAME, title="パーティ", chars=BOX_SINGLE)
        y = inner.y
        for m in self.st.party:
            if y + 1 >= inner.bottom + 1:
                break
            job = self.gd.jobs.get(m.job)
            buf.put(inner.x + 1, y, f"{pad(m.name, 10)}{pad(job.name if job else '', 10)}Lv {m.lv}",
                    Style.of("bright_white", bold=True), clip=inner)
            hp_st = Style.of("bright_red") if m.hp * 4 <= m.max_hp else TEXT
            st_names = "・".join(self.gd.statuses[s].name for s in m.status if s in self.gd.statuses)
            buf.put(inner.x + 2, y + 1, f"HP {m.hp:>3}/{m.max_hp:<3}  MP {m.mp:>3}/{m.max_mp:<3}  {st_names}",
                    hp_st, clip=inner)
            y += 3
