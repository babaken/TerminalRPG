"""Windows 用入力の変換ロジック（ReadConsoleInputW のレコード → KeyEvent）を検証する。

実際の API 呼び出しは Windows でしか動かないため、変換部（Translator）だけを試す。
"""
from trpg.term import Key
from trpg.term.input_win import VK_PROCESSKEY, KeyRecord, Translator


def keys(evs):
    return [e.key if e.key is not Key.CHAR else e.char for e in evs]


def test_basic_keys():
    tr = Translator()
    evs = tr.feed([
        KeyRecord(True, 0x26, ""), KeyRecord(False, 0x26, ""),        # ↑ 押す・離す
        KeyRecord(True, 0x41, "a"), KeyRecord(True, 0x0D, "\r"),
        KeyRecord(True, 0x1B, "\x1b"), KeyRecord(True, 0x74, ""),     # Esc, F5
        KeyRecord(True, 0x08, "\x08"),
    ])
    assert keys(evs) == [Key.UP, "a", Key.ENTER, Key.ESC, Key.F5, Key.BACKSPACE]


def test_enter_and_esc_without_char_from_ime():
    """日本語入力オン時に文字なし（uChar=0）で届く Enter / Esc も拾う（msvcrt では消えていた）。"""
    tr = Translator()
    evs = tr.feed([KeyRecord(True, 0x0D, ""), KeyRecord(True, 0x1B, "")])
    assert keys(evs) == [Key.ENTER, Key.ESC]


def test_ime_committed_text_and_ignored_keys():
    tr = Translator()
    evs = tr.feed([
        KeyRecord(True, VK_PROCESSKEY, ""),          # IME 処理中
        KeyRecord(True, 0x10, ""),                   # Shift
        KeyRecord(True, 0xF3, ""),                   # 半角/全角
        KeyRecord(True, 0x00, "テ"), KeyRecord(True, 0x00, "ス"), KeyRecord(True, 0x00, "ト"),
    ])
    assert keys(evs) == ["テ", "ス", "ト"]


def test_numpad_digit_and_repeat():
    tr = Translator()
    evs = tr.feed([KeyRecord(True, 0x68, "8", repeat=3)])   # テンキー 8 を押しっぱなし
    assert keys(evs) == ["8", "8", "8"]


def test_surrogate_pair():
    tr = Translator()
    hi, lo = "😀".encode("utf-16-le")[0:2].decode("utf-16-le", "surrogatepass"), \
        "😀".encode("utf-16-le")[2:4].decode("utf-16-le", "surrogatepass")
    evs = tr.feed([KeyRecord(True, 0, hi)])
    assert evs == []
    evs = tr.feed([KeyRecord(True, 0, lo)])
    assert keys(evs) == ["😀"]


def test_alt_char_ignored_but_altgr_kept():
    tr = Translator()
    assert tr.feed([KeyRecord(True, 0x41, "a", ctrl_state=0x02)]) == []
    assert keys(tr.feed([KeyRecord(True, 0x51, "@", ctrl_state=0x02 | 0x08)])) == ["@"]
