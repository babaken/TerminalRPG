import pytest

from trpg.term import Action, Key, KeyEvent, KeyMap
from trpg.term.input_posix import parse


def keys(evs):
    return [e.key if e.key is not Key.CHAR else e.char for e in evs]


def test_parse_chars_and_arrows():
    evs, rest = parse("a\x1b[A\x1b[Bあ\r")
    assert rest == ""
    assert keys(evs) == ["a", Key.UP, Key.DOWN, "あ", Key.ENTER]


def test_parse_ss3_and_tilde_and_modifiers():
    evs, _ = parse("\x1bOP\x1b[15~\x1b[3~\x1b[1;5C")
    assert keys(evs) == [Key.F1, Key.F5, Key.DELETE, Key.RIGHT]


def test_parse_incomplete_escape():
    evs, rest = parse("x\x1b")
    assert keys(evs) == ["x"] and rest == "\x1b"
    evs, rest = parse("\x1b[1;")
    assert evs == [] and rest == "\x1b[1;"
    evs, rest = parse("\x1b", final=True)
    assert keys(evs) == [Key.ESC] and rest == ""


def test_parse_double_esc_and_alt():
    evs, _ = parse("\x1b\x1b", final=True)
    assert keys(evs) == [Key.ESC, Key.ESC]
    evs, _ = parse("\x1bx")
    assert keys(evs) == [Key.ESC, "x"]


def test_ctrl_c_raises():
    with pytest.raises(KeyboardInterrupt):
        parse("\x03")


def test_keymap_defaults():
    km = KeyMap()
    assert Action.UP in km.actions(KeyEvent(Key.UP))
    assert Action.UP in km.actions(KeyEvent(Key.CHAR, "W"))
    assert Action.UP in km.actions(KeyEvent(Key.CHAR, "8"))
    assert Action.OK in km.actions(KeyEvent(Key.ENTER))
    assert Action.OK in km.actions(KeyEvent(Key.CHAR, "z"))
    assert Action.CANCEL in km.actions(KeyEvent(Key.ESC))
    assert Action.MENU in km.actions(KeyEvent(Key.CHAR, "m"))
    assert km.actions(KeyEvent(Key.CHAR, "q")) == frozenset()


def test_keymap_from_config():
    km = KeyMap.from_config({"up": ["UP", "k"]})
    assert Action.UP in km.actions(KeyEvent(Key.CHAR, "k"))
    assert Action.UP not in km.actions(KeyEvent(Key.CHAR, "w"))
    with pytest.raises(ValueError):
        KeyMap.from_config({"jump": ["j"]})


def test_keymap_fullwidth_from_ime():
    """IME オンで確定された全角英数字・全角空白も操作として受け付ける。"""
    km = KeyMap()
    assert Action.UP in km.actions(KeyEvent(Key.CHAR, "ｗ"))
    assert Action.UP in km.actions(KeyEvent(Key.CHAR, "Ｗ"))
    assert Action.DOWN in km.actions(KeyEvent(Key.CHAR, "２"))
    assert Action.OK in km.actions(KeyEvent(Key.CHAR, "ｚ"))
    assert Action.OK in km.actions(KeyEvent(Key.CHAR, "　"))
    assert km.actions(KeyEvent(Key.CHAR, "あ")) == frozenset()
