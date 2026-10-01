"""Windows コンソール用のキー入力。

Windows Terminal / コマンドプロンプト / PowerShell で動作する。

msvcrt.getwch() は「文字コードを持つキー」しか返さないため、日本語入力（IME）が
絡んで Enter や Esc が文字なし（uChar=0）で届くと読み飛ばされ、キーが届かない・
まとめて届くといった症状になる。ここでは ReadConsoleInputW で入力レコードを直接読み、
Enter・Esc・矢印などは仮想キーコードで判定する。
"""
from __future__ import annotations

from typing import Iterable, NamedTuple, Optional

from .. import debuglog
from .keys import Key, KeyEvent, char_event

# 仮想キーコード → キー（文字の有無に関係なく判定する）
VK_KEYS = {
    0x0D: Key.ENTER, 0x1B: Key.ESC, 0x08: Key.BACKSPACE, 0x09: Key.TAB,
    0x26: Key.UP, 0x28: Key.DOWN, 0x25: Key.LEFT, 0x27: Key.RIGHT,
    0x24: Key.HOME, 0x23: Key.END, 0x21: Key.PGUP, 0x22: Key.PGDN,
    0x2D: Key.INSERT, 0x2E: Key.DELETE,
    0x70: Key.F1, 0x71: Key.F2, 0x72: Key.F3, 0x73: Key.F4, 0x74: Key.F5, 0x75: Key.F6,
    0x76: Key.F7, 0x77: Key.F8, 0x78: Key.F9, 0x79: Key.F10, 0x7A: Key.F11, 0x7B: Key.F12,
}
VK_PROCESSKEY = 0xE5  # IME が処理中のキー（文字はまだ確定していない）

KEY_EVENT = 0x0001
LEFT_ALT, RIGHT_ALT = 0x0002, 0x0001
LEFT_CTRL, RIGHT_CTRL = 0x0008, 0x0004


class KeyRecord(NamedTuple):
    down: bool
    vk: int
    char: str          # "" なら文字なし
    repeat: int = 1
    ctrl_state: int = 0


class Translator:
    """KeyRecord の列を KeyEvent に変換する（サロゲートペアをまたいで状態を持つ）。"""

    def __init__(self):
        self._high: Optional[str] = None

    def feed(self, records: Iterable[KeyRecord]) -> list[KeyEvent]:
        out: list[KeyEvent] = []
        for r in records:
            if not r.down:
                continue
            n = max(1, r.repeat)
            key = VK_KEYS.get(r.vk)
            if key is not None:
                # Ctrl+H（BackSpace と同じ VK）などの誤判定を避けるため、文字が制御文字か無い場合のみ
                if not r.char or r.char < " " or r.char == "\x7f" or key in (Key.ENTER, Key.ESC):
                    out.extend([KeyEvent(key)] * n)
                    continue
            ch = r.char
            if not ch:
                continue  # Shift・Ctrl・半角/全角・IME 処理中（VK_PROCESSKEY）など
            if "\ud800" <= ch <= "\udbff":
                self._high = ch
                continue
            if "\udc00" <= ch <= "\udfff":
                if self._high is None:
                    continue
                ch, self._high = self._high + ch, None
                ch = ch.encode("utf-16", "surrogatepass").decode("utf-16")
            alt = r.ctrl_state & (LEFT_ALT | RIGHT_ALT)
            ctrl = r.ctrl_state & (LEFT_CTRL | RIGHT_CTRL)
            if alt and not ctrl:
                continue  # Alt+文字 は使わない（AltGr = Ctrl+Alt は文字として通す）
            ev = char_event(ch)
            out.extend([ev] * n)
        return out


class WinInput:
    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class KEY_EVENT_RECORD(ctypes.Structure):
            _fields_ = [("bKeyDown", wintypes.BOOL), ("wRepeatCount", wintypes.WORD),
                        ("wVirtualKeyCode", wintypes.WORD), ("wVirtualScanCode", wintypes.WORD),
                        ("uChar", wintypes.WCHAR), ("dwControlKeyState", wintypes.DWORD)]

        class _EVENT(ctypes.Union):
            _fields_ = [("KeyEvent", KEY_EVENT_RECORD), ("_pad", ctypes.c_byte * 16)]

        class INPUT_RECORD(ctypes.Structure):
            _fields_ = [("EventType", wintypes.WORD), ("Event", _EVENT)]

        self._ct = ctypes
        self._INPUT_RECORD = INPUT_RECORD
        self._buf = (INPUT_RECORD * 64)()
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetStdHandle.restype = wintypes.HANDLE
        k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k32.GetNumberOfConsoleInputEvents.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k32.ReadConsoleInputW.argtypes = [wintypes.HANDLE, ctypes.POINTER(INPUT_RECORD), wintypes.DWORD,
                                          ctypes.POINTER(wintypes.DWORD)]
        k32.FlushConsoleInputBuffer.argtypes = [wintypes.HANDLE]
        self._k32 = k32
        self._h = k32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        self._DWORD = wintypes.DWORD
        self._tr = Translator()

    def start(self) -> None:
        self._k32.FlushConsoleInputBuffer(self._h)

    def stop(self) -> None:
        self._k32.FlushConsoleInputBuffer(self._h)

    def _available(self) -> int:
        n = self._DWORD(0)
        if not self._k32.GetNumberOfConsoleInputEvents(self._h, self._ct.byref(n)):
            return 0
        return n.value

    def _read_records(self) -> list[KeyRecord]:
        read = self._DWORD(0)
        if not self._k32.ReadConsoleInputW(self._h, self._buf, len(self._buf), self._ct.byref(read)):
            return []
        recs: list[KeyRecord] = []
        for i in range(read.value):
            r = self._buf[i]
            if r.EventType != KEY_EVENT:
                debuglog.log(f"rec  type={r.EventType}")
                continue
            k = r.Event.KeyEvent
            ch = k.uChar or ""
            rec = KeyRecord(bool(k.bKeyDown), k.wVirtualKeyCode, ch if ch != "\x00" else "",
                            k.wRepeatCount, k.dwControlKeyState)
            if debuglog.enabled():
                debuglog.log(f"rec  {'down' if rec.down else 'up  '} vk={rec.vk:#04x} "
                             f"ch={('U+%04X' % ord(rec.char)) if rec.char else '-'} rep={rec.repeat} "
                             f"ctrl={rec.ctrl_state:#x}")
            recs.append(rec)
        return recs

    def poll(self, timeout: float) -> list[KeyEvent]:
        """最大 ``timeout`` 秒待ち、届いているキーをすべて返す。"""
        import time
        deadline = time.monotonic() + timeout
        events: list[KeyEvent] = []
        while True:
            left = deadline - time.monotonic()
            if self._available() == 0:
                if left <= 0:
                    return events
                # 入力が来るまで待つ（来たら即座に戻る）
                self._k32.WaitForSingleObject(self._h, max(1, int(left * 1000)))
                if self._available() == 0:
                    return events
            while self._available():
                events += self._tr.feed(self._read_records())
            if events:
                return events
            # キー以外（キーを離した・フォーカス等）だけだった → 残り時間で待ち直す
