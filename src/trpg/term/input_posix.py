"""Linux / macOS 用のキー入力。termios で cbreak モードにして 1 キーずつ読む。"""
from __future__ import annotations

import codecs
import os
import select
import time

from .. import debuglog
from .keys import Key, KeyEvent, char_event

ESC_TIMEOUT = 0.03  # ESC 単独押しとエスケープシーケンスを区別する待ち時間

_CSI_FINAL = {
    "A": Key.UP, "B": Key.DOWN, "C": Key.RIGHT, "D": Key.LEFT,
    "H": Key.HOME, "F": Key.END,
    "P": Key.F1, "Q": Key.F2, "R": Key.F3, "S": Key.F4,
}
_CSI_TILDE = {
    "1": Key.HOME, "2": Key.INSERT, "3": Key.DELETE, "4": Key.END,
    "5": Key.PGUP, "6": Key.PGDN, "7": Key.HOME, "8": Key.END,
    "11": Key.F1, "12": Key.F2, "13": Key.F3, "14": Key.F4,
    "15": Key.F5, "17": Key.F6, "18": Key.F7, "19": Key.F8,
    "20": Key.F9, "21": Key.F10, "23": Key.F11, "24": Key.F12,
}


def parse(buf: str, final: bool = False) -> tuple[list[KeyEvent], str]:
    """入力文字列をキーイベント列に分解する。

    途中で切れたエスケープシーケンスは未処理として返す（次の読み込みと連結する）。
    ``final=True`` のときは未完了の ESC を ESC キーとして確定させる。
    """
    events: list[KeyEvent] = []
    i = 0
    n = len(buf)
    while i < n:
        ch = buf[i]
        if ch != "\x1b":
            events.append(char_event(ch))
            i += 1
            continue
        # ESC
        if i + 1 >= n:
            if final:
                events.append(KeyEvent(Key.ESC))
                i += 1
                continue
            return events, buf[i:]
        nxt = buf[i + 1]
        if nxt in "[O":
            j = i + 2
            while j < n and not ("\x40" <= buf[j] <= "\x7e"):
                j += 1
            if j >= n:
                if final:
                    events.append(KeyEvent(Key.ESC))
                    i += 1
                    continue
                return events, buf[i:]
            params, fin = buf[i + 2:j], buf[j]
            if fin == "~":
                key = _CSI_TILDE.get(params.split(";")[0], Key.UNKNOWN)
            else:
                key = _CSI_FINAL.get(fin, Key.UNKNOWN)
            events.append(KeyEvent(key))
            i = j + 1
            continue
        if nxt == "\x1b":
            events.append(KeyEvent(Key.ESC))
            i += 1
            continue
        # Alt+文字 など → ESC として扱い、文字は次で処理
        events.append(KeyEvent(Key.ESC))
        i += 1
    return events, ""


class PosixInput:
    def __init__(self, fd: int | None = None):
        import sys
        self.fd = sys.stdin.fileno() if fd is None else fd
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._pending = ""
        self._saved = None

    # 端末モード
    def start(self) -> None:
        import termios
        import tty
        self._saved = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd, termios.TCSANOW)  # 1 文字入力・エコーなし（Ctrl+C は有効）

    def stop(self) -> None:
        if self._saved is not None:
            import termios
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self._saved)
            self._saved = None

    def _read_available(self, timeout: float) -> bool:
        r, _, _ = select.select([self.fd], [], [], max(0.0, timeout))
        if not r:
            return False
        data = os.read(self.fd, 1024)
        debuglog.log(f"raw  {data!r}")
        if data:
            self._pending += self._decoder.decode(data)
        return True

    def poll(self, timeout: float) -> list[KeyEvent]:
        """最大 ``timeout`` 秒待ち、届いているキーをすべて返す。"""
        deadline = time.monotonic() + timeout
        if not self._pending:
            if not self._read_available(timeout):
                return []
        # すでに来ている分も吸い出す
        while self._read_available(0):
            pass
        events, self._pending = parse(self._pending)
        if self._pending:
            # ESC だけ届いた → 続きを少し待つ
            wait = min(ESC_TIMEOUT, max(0.0, deadline - time.monotonic()) + ESC_TIMEOUT)
            if self._read_available(wait):
                more, self._pending = parse(self._pending)
                events += more
            if self._pending:
                more, self._pending = parse(self._pending, final=True)
                events += more
        return events
