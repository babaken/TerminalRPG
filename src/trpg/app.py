"""アプリケーション本体：シーン管理とフレームループ。"""
from __future__ import annotations

import time
import unicodedata
from typing import Optional

from . import debuglog
from .term import Action, Buffer, Key, KeyEvent, KeyMap, Rect, Style, Terminal
from .term.width import text_width
from .term.width import truncate

MIN_WIDTH = 100
MIN_HEIGHT = 30


IME_NOTICE = "日本語入力（IME）がオンです。［半角/全角］キーでオフにしてください"
IME_NOTICE_SECONDS = 4.0


def looks_like_ime(ev: KeyEvent) -> bool:
    """IME オンのまま押されたキーらしいか（全角の英数字・かな・漢字が届いた）。"""
    if ev.key is not Key.CHAR or not ev.char or ev.char.isascii():
        return False
    return unicodedata.east_asian_width(ev.char[0]) in ("W", "F")


class Scene:
    """画面 1 つ分の処理。サブクラスで on_key / update / draw を実装する。"""

    app: "App"
    accepts_text = False   # True: 文字入力画面（全角文字が来ても IME 警告を出さない）

    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass

    def on_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        pass

    def on_resize(self, width: int, height: int) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, buf: Buffer) -> None:
        pass


class App:
    def __init__(self, scene: Scene, *, fps: int = 30, keymap: Optional[KeyMap] = None,
                 min_size: tuple[int, int] = (MIN_WIDTH, MIN_HEIGHT), use_color: bool = True):
        self.frame_time = 1.0 / fps
        self.keymap = keymap or KeyMap()
        self.min_size = min_size
        self.use_color = use_color
        self.running = False
        self.terminal: Optional[Terminal] = None
        self.notice = ""          # 画面上部に一時的に出すお知らせ
        self.notice_time = 0.0
        self._stack: list[Scene] = []
        self.push(scene)

    # ---------------------------------------------------------------- シーン操作
    @property
    def scene(self) -> Scene:
        return self._stack[-1]

    def push(self, scene: Scene) -> None:
        debuglog.log(f"scene push {type(scene).__name__}")
        scene.app = self
        self._stack.append(scene)
        scene.on_enter()

    def pop(self) -> None:
        debuglog.log(f"scene pop {type(self._stack[-1]).__name__}")
        self._stack.pop().on_exit()
        if not self._stack:
            self.running = False

    def replace(self, scene: Scene) -> None:
        if self._stack:
            self._stack.pop().on_exit()
        self.push(scene)

    def quit(self) -> None:
        self.running = False

    def show_notice(self, text: str, seconds: float = 3.0) -> None:
        self.notice = text
        self.notice_time = seconds

    def dispatch_all(self, events: list[KeyEvent]) -> None:
        """1 フレーム分のキーを順に渡す。

        途中で画面（シーン）が切り替わったら残りは捨てる。まとめて届いたキー
        （連打・入力の滞留）が次の画面に流れ込み、会話を勝手に読み飛ばすのを防ぐ。
        """
        for i, ev in enumerate(events):
            before = self.scene if self._stack else None
            self.dispatch(ev)
            if not self.running:
                return
            if self._stack and self.scene is not before and i + 1 < len(events):
                debuglog.log(f"drop {len(events) - i - 1} keys after scene change")
                return

    def dispatch(self, ev: KeyEvent) -> None:
        """キーを現在のシーンに渡す（IME オンの検出つき）。"""
        actions = self.keymap.actions(ev)
        if debuglog.enabled():
            debuglog.log(f"key  {ev} -> {type(self.scene).__name__} actions={sorted(a.value for a in actions)}")
        if looks_like_ime(ev) and not self.scene.accepts_text:
            self.show_notice(IME_NOTICE, IME_NOTICE_SECONDS)
        self.scene.on_key(ev, actions)

    # ---------------------------------------------------------------- ループ
    def too_small(self, w: int, h: int) -> bool:
        return w < self.min_size[0] or h < self.min_size[1]

    def run(self) -> None:
        try:
            self._run()
        except BaseException as e:
            if not isinstance(e, (KeyboardInterrupt, SystemExit)):
                debuglog.log_exception("App.run")
            raise
        finally:
            debuglog.log("exit")

    def _heartbeat(self, w: int, h: int, small: bool) -> None:
        scene = self.scene
        state = scene.debug_state() if hasattr(scene, "debug_state") else ""
        inp = self.terminal.input if self.terminal else None
        pend = f" pending={inp.pending()}" if inp is not None and hasattr(inp, "pending") else ""
        debuglog.log(f"tick {type(scene).__name__} size={w}x{h}{' SMALL' if small else ''}{pend} {state}")

    def _run(self) -> None:
        with Terminal(use_color=self.use_color) as term:
            self.terminal = term
            screen = term.screen
            self.running = True
            last = time.monotonic()
            first = True
            next_beat = 0.0
            while self.running:
                events = term.input.poll(0 if first else self.frame_time)
                first = False
                if screen.check_resize():
                    self.scene.on_resize(screen.width, screen.height)
                small = self.too_small(screen.width, screen.height)
                now = time.monotonic()
                dt = now - last
                last = now
                if debuglog.enabled():
                    if dt > 0.25:
                        debuglog.log(f"slow frame {dt:.3f}s")
                    if now >= next_beat:
                        next_beat = now + 1.0
                        self._heartbeat(screen.width, screen.height, self.too_small(screen.width, screen.height))
                if not small:  # 画面が小さい間はゲームを一時停止
                    self.dispatch_all(events)
                    if self.running:
                        self.scene.update(dt)
                    self.notice_time = max(0.0, self.notice_time - dt)
                buf = screen.back
                buf.clear()
                if small:
                    self.draw_too_small(buf)
                elif self.running:
                    self.scene.draw(buf)
                    self.draw_notice(buf)
                screen.present()

    def draw_notice(self, buf: Buffer) -> None:
        if self.notice_time <= 0 or not self.notice:
            return
        text = truncate(self.notice, buf.width - 6)
        w = text_width(text) + 4
        rect = Rect((buf.width - w) // 2, 1, w, 3)
        st = Style.of("black", "bright_yellow")
        buf.fill(rect, " ", st)
        buf.put(rect.x + 2, rect.y + 1, text, st)

    def draw_too_small(self, buf: Buffer) -> None:
        lines = [
            "画面が小さすぎます。ウィンドウを広げてください。",
            f"現在: {buf.width} × {buf.height}  /  必要: {self.min_size[0]} × {self.min_size[1]}",
            "（Ctrl+C で終了）",
        ]
        top = max(0, (buf.height - len(lines)) // 2)
        for i, line in enumerate(lines):
            buf.put_center(top + i, truncate(line, buf.width), Style.of("yellow") if i == 0 else Style())
