import pytest
from trpg.term import width as W


def test_char_width_basic():
    assert W.char_width("a") == 1
    assert W.char_width("あ") == 2
    assert W.char_width("ｱ") == 1          # 半角カナ
    assert W.char_width("木") == 2
    assert W.char_width("＃") == 2          # 全角記号
    assert W.char_width("゙") == 0      # 結合用濁点
    assert W.char_width("\x1b") == 0


def test_ambiguous_switch():
    try:
        assert W.char_width("─") == 1
        W.set_ambiguous_width(2)
        assert W.char_width("─") == 2
    finally:
        W.set_ambiguous_width(1)
    with pytest.raises(ValueError):
        W.set_ambiguous_width(3)


def test_text_width_truncate_pad_wrap():
    assert W.text_width("ABあい") == 6
    assert W.truncate("あいうえお", 5) == "あい"
    assert W.truncate("あいうえお", 7, "…") == "あいう…"
    assert W.pad("あ", 5) == "あ   "
    assert W.pad("あ", 5, "right") == "   あ"
    assert W.pad("あ", 6, "center") == "  あ  "
    assert W.wrap("あいうえお", 4) == ["あい", "うえ", "お"]
    assert W.wrap("ab\ncd", 10) == ["ab", "cd"]
