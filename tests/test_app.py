from trpg.app import IME_NOTICE, App, Scene, looks_like_ime
from trpg.term import Action, Key, KeyEvent


def ch(c):
    return KeyEvent(Key.CHAR, c)


def test_looks_like_ime():
    assert looks_like_ime(ch("ｗ"))
    assert looks_like_ime(ch("わ"))
    assert looks_like_ime(ch("　"))
    assert not looks_like_ime(ch("w"))
    assert not looks_like_ime(KeyEvent(Key.ENTER))
    assert not looks_like_ime(ch("ｱ"))      # 半角カナは IME 由来とは限らないので対象外


class Rec(Scene):
    def __init__(self, text=False):
        self.accepts_text = text
        self.got = []

    def on_key(self, ev, actions):
        self.got.append((ev, actions))


def test_dispatch_shows_notice_and_still_moves():
    s = Rec()
    app = App(s)
    app.dispatch(ch("ｗ"))
    assert app.notice == IME_NOTICE and app.notice_time > 0
    assert Action.UP in s.got[0][1]           # 全角でも移動として届く


def test_no_notice_in_text_input():
    s = Rec(text=True)
    app = App(s)
    app.dispatch(ch("テ"))
    assert app.notice_time == 0


def test_keys_after_scene_change_are_dropped():
    """1 フレームにまとめて届いたキーは、画面が切り替わったらそこで捨てる。"""
    second = Rec()

    class First(Scene):
        def on_key(self, ev, actions):
            self.app.replace(second)

    app = App(First())
    app.running = True
    app.dispatch_all([KeyEvent(Key.ENTER)] * 5)
    assert app.scene is second
    assert second.got == []
