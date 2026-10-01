"""端末抽象化レイヤ（描画・入力・サイズ検知）。"""
from .buffer import BOX_ASCII, BOX_DOUBLE, BOX_SINGLE, CONT, Buffer, Rect
from .keys import Action, Key, KeyEvent, KeyMap
from .screen import Screen
from .style import BOLD, DIM, REVERSE, UNDERLINE, DEFAULT, Style
from .terminal import Terminal, TerminalError
from .width import char_width, pad, set_ambiguous_width, text_width, truncate, wrap

__all__ = [
    "Buffer", "Rect", "CONT", "BOX_SINGLE", "BOX_DOUBLE", "BOX_ASCII",
    "Action", "Key", "KeyEvent", "KeyMap",
    "Screen", "Style", "DEFAULT", "BOLD", "DIM", "REVERSE", "UNDERLINE",
    "Terminal", "TerminalError",
    "char_width", "text_width", "truncate", "pad", "wrap", "set_ambiguous_width",
]
