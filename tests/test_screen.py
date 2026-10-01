import io
import re

from trpg.term import Screen, Style


def make(w=10, h=3):
    out = io.StringIO()
    size = [w, h]
    s = Screen(out, size_fn=lambda: tuple(size))
    return s, out, size


def strip(s):
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", s)


def test_first_present_is_full():
    s, out, _ = make()
    s.back.put(0, 0, "hello")
    s.present()
    data = out.getvalue()
    assert "\x1b[2J" in data
    assert "hello" in strip(data)


def test_no_change_no_output():
    s, out, _ = make()
    s.back.put(0, 0, "hello")
    s.present()
    out.truncate(0); out.seek(0)
    s.back.put(0, 0, "hello")
    s.present()
    assert out.getvalue() == ""


def test_diff_only_changed():
    s, out, _ = make()
    s.back.put(0, 1, "abcdef")
    s.present()
    out.truncate(0); out.seek(0)
    s.back.put(3, 1, "X")
    s.present()
    data = out.getvalue()
    assert "\x1b[2;4H" in data
    assert strip(data) == "X"


def test_wide_right_half_change_rewrites_lead():
    s, out, _ = make()
    s.back.put(0, 0, "あい")
    s.present()
    out.truncate(0); out.seek(0)
    s.back.put(0, 0, "あ", Style.of("red"))   # 同じ文字・違う色
    s.present()
    data = out.getvalue()
    assert "\x1b[1;1H" in data
    assert strip(data) == "あ"


def test_style_emitted():
    s, out, _ = make()
    s.back.put(0, 0, "R", Style.of("red", bold=True))
    s.present()
    assert "\x1b[0;1;31m" in out.getvalue()


def test_resize_forces_full_redraw():
    s, out, size = make()
    s.present()
    size[0], size[1] = 20, 5
    assert s.check_resize() is True
    assert (s.width, s.height) == (20, 5)
    assert s.check_resize() is False
    out.truncate(0); out.seek(0)
    s.present()
    assert "\x1b[2J" in out.getvalue()


def test_no_color_mode():
    out = io.StringIO()
    s = Screen(out, size_fn=lambda: (5, 1), use_color=False)
    s.back.put(0, 0, "R", Style.of("red"))
    s.present()
    assert "31" not in out.getvalue().replace("\x1b[2J", "")


def test_cursor_shown_at_input_position_and_hidden_after():
    s, out, _ = make(10, 3)
    s.back.put(0, 0, "abc")
    s.back.cursor = (3, 0)
    s.present()
    data = out.getvalue()
    assert data.endswith("\x1b[1;4H\x1b[?25h")
    out.truncate(0); out.seek(0)
    # 変化なし・カーソル同じ → 何も出さない
    s.back.put(0, 0, "abc")
    s.back.cursor = (3, 0)
    s.present()
    assert out.getvalue() == ""
    # 1 文字追加 → 書いたあとカーソルを入力位置へ戻す
    s.back.put(0, 0, "abcd")
    s.back.cursor = (4, 0)
    s.present()
    assert out.getvalue().endswith("\x1b[1;5H\x1b[?25h")
    out.truncate(0); out.seek(0)
    # 入力画面を抜けた → カーソルを隠す
    s.back.clear()
    s.present()
    assert "\x1b[?25l" in out.getvalue()


def test_clear_resets_cursor():
    s, _, _ = make()
    s.back.cursor = (1, 1)
    s.back.clear()
    assert s.back.cursor is None
