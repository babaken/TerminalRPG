"""端末の初期化・後始末をまとめたコンテキストマネージャ。

    with Terminal() as term:
        term.screen.back.put(0, 0, "こんにちは")
        term.screen.present()
        events = term.input.poll(0.1)
"""
from __future__ import annotations

import os
import sys
from typing import Optional

from .screen import Screen


class TerminalError(RuntimeError):
    """端末が使えない（対応していない）ときのエラー。メッセージは利用者向けの日本語。"""


class _WinConsole:
    """Windows: VT（ANSI エスケープ）処理と UTF-8 出力を有効化し、終了時に元へ戻す。"""

    ENABLE_PROCESSED_OUTPUT = 0x0001
    ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self._ctypes = ctypes
        self._k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._k32.GetStdHandle.restype = wintypes.HANDLE
        self._out = self._k32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        self._mode = wintypes.DWORD()
        self._saved_mode: Optional[int] = None
        self._saved_cp: Optional[int] = None

    def start(self) -> None:
        k32 = self._k32
        if not k32.GetConsoleMode(self._out, self._ctypes.byref(self._mode)):
            raise TerminalError(
                "Windows コンソールを取得できません。\n"
                "Windows Terminal / コマンドプロンプト / PowerShell から起動してください。\n"
                "（MSYS2 / Git Bash の mintty 上では Windows 版 Python のキー入力が使えません。"
                "mintty で遊ぶ場合は MSYS2 の Python を使うか、`winpty python -m trpg` で起動してください）"
            )
        self._saved_mode = self._mode.value
        new_mode = self._mode.value | self.ENABLE_PROCESSED_OUTPUT | self.ENABLE_VIRTUAL_TERMINAL_PROCESSING
        if not k32.SetConsoleMode(self._out, new_mode):
            raise TerminalError(
                "この端末は ANSI エスケープシーケンスに対応していません。\n"
                "Windows 10 以降の Windows Terminal で起動してください。"
            )
        self._saved_cp = k32.GetConsoleOutputCP()
        k32.SetConsoleOutputCP(65001)  # UTF-8

    def stop(self) -> None:
        if self._saved_mode is not None:
            self._k32.SetConsoleMode(self._out, self._saved_mode)
            self._saved_mode = None
        if self._saved_cp is not None:
            self._k32.SetConsoleOutputCP(self._saved_cp)
            self._saved_cp = None


def _make_input():
    if os.name == "nt":
        from .input_win import WinInput
        return WinInput()
    from .input_posix import PosixInput
    return PosixInput()


class Terminal:
    def __init__(self, use_color: bool = True):
        self.use_color = use_color
        self.screen: Optional[Screen] = None
        self.input = None
        self._console = None
        self._started: list = []

    def __enter__(self) -> "Terminal":
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise TerminalError("端末（ターミナル）から起動してください。入出力がリダイレクトされています。")
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if os.name == "nt":
                self._console = _WinConsole()
                self._console.start()
                self._started.append(self._console)
            self.input = _make_input()
            self.input.start()
            self._started.append(self.input)
            self.screen = Screen(sys.stdout, use_color=self.use_color)
            self.screen.start()
            self._started.append(self.screen)
        except BaseException:
            self._cleanup()
            raise
        return self

    def __exit__(self, *exc) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        while self._started:
            obj = self._started.pop()
            try:
                obj.stop()
            except Exception:
                pass
