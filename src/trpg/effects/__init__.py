"""画面エフェクト（基本設計 11 章）。

描画済みの画面バッファに後から効果を重ねる方式。時間で終わるもの（flash / fade / shake / typewriter）と、
解除するまで続くもの（tint）がある。
実装済み: flash / fade_in / fade_out / shake / tint / typewriter / wait / rain / snow / starfall
未実装（何もしない）: move / wipe / blink / aa_show / aa_hide / scroll_text
"""
from __future__ import annotations

import random
from typing import Optional

from ..term import DIM, Buffer, Rect, Style, text_width
from ..term.style import color as to_color

TINT_FG = {"night": 4, "sepia": 3, "red": 1}
IMPLEMENTED = ("flash", "fade_in", "fade_out", "shake", "tint", "typewriter", "wait", "rain", "snow", "starfall")


def _int(kw: dict, key: str, default: int) -> int:
    try:
        return int(kw.get(key, default))
    except (TypeError, ValueError):
        return default


class Effect:
    blocking = True
    needs_key = False

    def __init__(self):
        self.t = 0.0
        self.done = False

    def update(self, dt: float) -> None:
        self.t += dt

    def key(self) -> None:
        pass

    def offset(self) -> tuple[int, int]:
        return (0, 0)

    def apply(self, buf: Buffer) -> None:
        pass


class Flash(Effect):
    def __init__(self, color: str = "white", count: int = 1, interval: int = 80):
        super().__init__()
        try:
            self.bg = to_color("bright_white" if color == "white" else color)
        except ValueError:
            self.bg = 15
        self.count = max(1, count)
        self.interval = max(20, interval) / 1000

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.t >= self.count * self.interval * 2:
            self.done = True

    def apply(self, buf: Buffer) -> None:
        if int(self.t / self.interval) % 2 == 0:
            buf.fill(buf.rect, " ", Style(None, self.bg, 0))


class Fade(Effect):
    """fade_out: 画面 → 暗 → 黒（終了後も黒のまま。fade_in で戻る）"""

    def __init__(self, out: bool, ms: int = 500):
        super().__init__()
        self.out = out
        self.dur = max(50, ms) / 1000

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.t >= self.dur:
            self.done = True

    def level(self) -> float:
        p = min(1.0, self.t / self.dur)
        return p if self.out else 1.0 - p

    def apply(self, buf: Buffer) -> None:
        apply_darkness(buf, self.level())


def apply_darkness(buf: Buffer, level: float) -> None:
    if level >= 0.67:
        buf.clear()
    elif level >= 0.33:
        buf.map_styles(lambda st: st._replace(attrs=st.attrs | DIM, bg=None))


class Shake(Effect):
    def __init__(self, direction: str = "h", power: int = 2, ms: int = 400):
        super().__init__()
        self.dir = direction
        self.power = max(1, min(3, power))
        self.dur = max(50, ms) / 1000

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.t >= self.dur:
            self.done = True

    def offset(self) -> tuple[int, int]:
        sign = 1 if int(self.t * 30) % 2 == 0 else -1
        amount = self.power * sign
        return (amount * 2, 0) if self.dir == "h" else (0, amount)


class Typewriter(Effect):
    """画面中央に文字を 1 文字ずつ表示し、キーで閉じる（章タイトルなど）。"""

    needs_key = True

    def __init__(self, text: str, speed: int = 80):
        super().__init__()
        self.text = text
        self.interval = max(10, speed) / 1000

    def key(self) -> None:
        n = int(self.t / self.interval)
        if n < len(self.text):
            self.t = len(self.text) * self.interval
        else:
            self.done = True

    def apply(self, buf: Buffer) -> None:
        buf.clear()
        n = min(len(self.text), int(self.t / self.interval))
        shown = self.text[:n]
        y = buf.height // 2
        x = (buf.width - text_width(self.text)) // 2
        buf.put(x, y, shown, Style.of("bright_white", bold=True))
        if n >= len(self.text):
            if int(self.t * 3) % 2 == 0:
                buf.put(buf.width // 2, y + 2, "▼", Style.of("yellow"))
            buf.put_center(y + 4, "Enter / Z で続ける", Style.of("gray"))


class Wait(Effect):
    def __init__(self, ms: int):
        super().__init__()
        self.dur = max(0, ms) / 1000

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.t >= self.dur:
            self.done = True


class Starfall(Effect):
    """右上から左下へ流れ星が斜めに降る（count 個、ms ミリ秒）。"""

    SPEED = 40.0   # セル/秒（縦）。横は 2 倍（セルは縦長なので見た目の角度を 45° に近づける）

    def __init__(self, count: int = 8, ms: int = 2000):
        super().__init__()
        self.dur = max(200, ms) / 1000
        self.count = max(1, count)
        rng = random.Random()
        # (出現時刻, 開始位置の割合 0..1 — 上辺の右半分から右辺の上半分へ)
        self.stars = [(rng.uniform(0, self.dur * 0.6), rng.random()) for _ in range(self.count)]

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.t >= self.dur + 1.0:
            self.done = True

    def apply(self, buf: Buffer) -> None:
        W, H = buf.width, buf.height
        head = Style.of("bright_yellow", bold=True)
        tail = Style.of("yellow")
        for born, r in self.stars:
            age = self.t - born
            if age < 0:
                continue
            # 開始点：r<0.5 なら上辺（右半分）、それ以外は右辺（上半分）
            if r < 0.5:
                sx, sy = W * (0.5 + r), 0.0
            else:
                sx, sy = float(W - 1), H * (r - 0.5)
            d = age * self.SPEED
            for k, ch, st in ((0, "*", head), (1, ".", tail), (2, ".", tail), (3, "`", tail)):
                x = int(sx - (d - k) * 2)
                y = int(sy + (d - k))
                if 0 <= x < W and 0 <= y < H and d - k >= 0:
                    buf.put(x, y, ch, st)


class Weather:
    """雨・雪（解除するまで続く。マップ表示領域にだけ降らせる）。"""

    def __init__(self, kind: str, density: int = 1):
        self.kind = kind
        self.density = max(1, min(3, density))
        self.drops: list[list[float]] = []
        self.size = (0, 0)
        self.rng = random.Random()

    def _spawn(self, w: int, h: int, anywhere: bool) -> list[float]:
        speed = self.rng.uniform(18, 28) if self.kind == "rain" else self.rng.uniform(2, 4)
        y = self.rng.uniform(0, h) if anywhere else 0.0
        return [self.rng.uniform(0, w + h * 0.5), y, speed, self.rng.uniform(0, 6.28)]

    def update(self, dt: float) -> None:
        w, h = self.size
        if not w:
            return
        for d in self.drops:
            d[1] += d[2] * dt
            if self.kind == "rain":
                d[0] -= d[2] * dt * 0.5
            else:
                d[3] += dt
                d[0] += 0.6 * dt * (1 if int(d[3]) % 2 else -1)
            if d[1] >= h or d[0] < -1:
                d[:] = self._spawn(w, h, False)

    def apply(self, buf: Buffer, area: Rect) -> None:
        if (area.w, area.h) != self.size:
            self.size = (area.w, area.h)
            n = max(4, area.w * area.h * self.density // (70 if self.kind == "rain" else 110))
            self.drops = [self._spawn(area.w, area.h, True) for _ in range(n)]
        # 全角 1 文字（2 セル）をタイルの区切りに合わせて置く（全角タイルを半分だけ壊さない）
        ch, st = ("／", Style.of("bright_blue")) if self.kind == "rain" else ("＊", Style.of("bright_white"))
        for x, y, _, _ in self.drops:
            ix, iy = int(x) // 2 * 2, int(y)
            if 0 <= ix < area.w - 1 and 0 <= iy < area.h:
                buf.put(area.x + ix, area.y + iy, ch, st, clip=area)


class EffectManager:
    def __init__(self, state_effects: dict):
        self.active: list[Effect] = []
        self.persist = state_effects        # GameState.effects（セーブされる継続エフェクト）
        self.weather: Optional[Weather] = None
        self._sync_weather()

    def _sync_weather(self) -> None:
        """persist の rain / snow 設定に合わせて天気を作り直す（ロード直後にも使う）。"""
        for kind in ("rain", "snow"):
            v = self.persist.get(kind, "off")
            if v != "off":
                if self.weather is None or self.weather.kind != kind:
                    self.weather = Weather(kind, int(v) if v.isdigit() else 1)
                return
        self.weather = None

    @property
    def faded(self) -> bool:
        return self.persist.get("fade") == "out"

    def start(self, name: str, pos: list[str], kw: dict) -> Optional[Effect]:
        """エフェクトを開始する。待つ必要があれば Effect を返す（wait=false なら None）。"""
        eff: Optional[Effect] = None
        if name == "flash":
            color = kw.get("color", pos[0] if pos else "white")
            eff = Flash(color, _int(kw, "count", 1), _int(kw, "interval", 80))
        elif name in ("fade_out", "fade_in"):
            ms = int(pos[0]) if pos and pos[0].isdigit() else _int(kw, "ms", 500)
            eff = Fade(name == "fade_out", ms)
            self.persist["fade"] = "out" if name == "fade_out" else "in"
        elif name == "shake":
            d = kw.get("dir", pos[0] if pos and pos[0] in ("h", "v") else "h")
            nums = [int(p) for p in pos if p.isdigit()]
            eff = Shake(d, _int(kw, "power", nums[0] if nums else 2), _int(kw, "ms", nums[1] if len(nums) > 1 else 400))
        elif name == "tint":
            self.persist["tint"] = pos[0] if pos else "none"
            return None
        elif name == "typewriter":
            eff = Typewriter(pos[0] if pos else "", _int(kw, "speed", 80))
        elif name == "wait":
            eff = Wait(int(pos[0]) if pos and pos[0].isdigit() else _int(kw, "ms", 0))
        elif name in ("rain", "snow"):
            on = not pos or pos[0] != "off"
            other = "snow" if name == "rain" else "rain"
            self.persist[other] = "off"
            self.persist[name] = str(_int(kw, "density", 1)) if on else "off"
            self._sync_weather()
            return None
        elif name == "starfall":
            eff = Starfall(_int(kw, "count", 8), _int(kw, "ms", 2000))
        else:
            return None   # 未実装のエフェクトは何もしない
        self.active.append(eff)
        if kw.get("wait", "true") == "false" and not eff.needs_key:
            return None
        return eff

    def update(self, dt: float) -> None:
        for e in self.active:
            e.update(dt)
        self.active = [e for e in self.active if not e.done]
        if self.weather is not None:
            self.weather.update(dt)

    def key(self) -> bool:
        """キー入力をキー待ちエフェクトに渡す。渡したら True。"""
        for e in self.active:
            if e.needs_key:
                e.key()
                return True
        return False

    def offset(self) -> tuple[int, int]:
        dx = dy = 0
        for e in self.active:
            ox, oy = e.offset()
            dx += ox
            dy += oy
        return dx, dy

    def apply_world(self, buf: Buffer, map_area: Optional[Rect] = None) -> None:
        """マップ・パネルにかける効果（天気・色調・暗転）。会話窓を描く前に呼ぶ。"""
        if self.weather is not None and map_area is not None:
            self.weather.apply(buf, map_area)
        tint = self.persist.get("tint", "none")
        fg = TINT_FG.get(tint)
        if fg is not None:
            buf.map_styles(lambda st: st._replace(fg=fg))
        fading = [e for e in self.active if isinstance(e, Fade)]
        if fading:
            fading[-1].apply(buf)
        elif self.faded:
            buf.clear()

    def apply_overlay(self, buf: Buffer) -> None:
        """画面全体にかける効果（発光・中央文字）。会話窓を描いた後に呼ぶ。"""
        for e in self.active:
            if not isinstance(e, Fade):
                e.apply(buf)
