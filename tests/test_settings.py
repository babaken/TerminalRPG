"""設定（文字の速さ・言語・キー割当）と、シナリオ本文の言語別ファイル（lang/<言語>/）のテスト。"""
import shutil

import pytest

from conftest import edit
from test_menu import d, game, menu, top  # noqa: F401
from test_play import Driver, _seed  # noqa: F401
from trpg import settings
from trpg.__main__ import load_keymap
from trpg.game import load_game
from trpg.i18n import get_lang, set_lang
from trpg.package.check import check_package
from trpg.scenes.title import TitleScene
from trpg.term import Action, Key, KeyEvent, KeyMap
from trpg.ui.widgets import MessageWindow


# ---------------------------------------------------------------- settings.json
def test_settings_keep_other_values():
    settings.save(lang="en")
    settings.save(text_speed="fast")
    assert settings.load() == {"lang": "en", "text_speed": "fast"}


def test_broken_settings_file_is_ignored():
    settings.path().parent.mkdir(parents=True, exist_ok=True)
    settings.path().write_text("{壊れている", encoding="utf-8")
    assert settings.load() == {}
    settings.load_text_speed()
    assert settings.text_speed() == "normal"


# ---------------------------------------------------------------- 文字の速さ
def _chars_after(secs: float) -> int:
    w = MessageWindow()
    w.open([("", "あいうえおかきくけこさしすせそ")])
    w.update(secs)
    return w.shown


def test_text_speed_changes_message_speed():
    normal = _chars_after(0.2)
    settings.set_text_speed("fast")
    assert _chars_after(0.2) > normal
    settings.set_text_speed("slow")
    assert _chars_after(0.2) < normal
    settings.set_text_speed("instant")
    assert _chars_after(0.01) == 15


def test_text_speed_is_loaded_from_settings():
    settings.save(text_speed="instant")
    settings.load_text_speed()
    assert settings.text_speed() == "instant"
    with pytest.raises(ValueError):
        settings.set_text_speed("turbo")


# ---------------------------------------------------------------- メニュー → システム → 設定
def _open_settings(d):
    m = top(d, "システム")
    d.key("DOWN")
    d.key("ENTER")                                # 設定
    assert "文字の速さ：ふつう" in d.screen()
    return m


def test_menu_settings_text_speed(d):
    _open_settings(d)
    d.key("ENTER")                                # ふつう → はやい
    assert settings.text_speed() == "fast"
    assert "文字の速さ：はやい" in d.screen()
    assert settings.get("text_speed") == "fast"   # 次の起動でも使う
    for _ in range(3):
        d.key("ENTER")                            # 一瞬 → おそい → ふつう
    assert settings.text_speed() == "normal"


def test_menu_settings_language(d):
    m = _open_settings(d)
    d.key("DOWN")
    d.key("ENTER")
    assert get_lang() == "en"
    assert settings.get("lang") == "en"
    assert "Text speed: Normal" in d.screen()
    assert m.views[0].list.rows[0][0] == "Item"  # メニューの項目も英語になる
    d.key("ESC")                                  # 設定を閉じる
    assert isinstance(d.scene, type(m))


# ---------------------------------------------------------------- キー割当
def test_keymap_from_settings():
    settings.save(keys={"ok": ["ENTER", "j"], "menu": ["TAB"]})
    km = load_keymap()
    assert Action.OK in km.actions(KeyEvent(Key.CHAR, "j"))
    assert Action.OK not in km.actions(KeyEvent(Key.CHAR, "z"))       # 書いたアクションは置き換え
    assert Action.MENU in km.actions(KeyEvent(Key.TAB))
    assert Action.CANCEL in km.actions(KeyEvent(Key.CHAR, "x"))       # 書かないものは既定のまま


@pytest.mark.parametrize("keys", [{"jump": ["j"]}, {"ok": ["ENTRE"]}, {"ok": "z"}, ["z"]])
def test_bad_keymap_is_reported(keys, capsys):
    settings.save(keys=keys)
    assert load_keymap() is None
    assert "キー割当の設定に誤りがあります" in capsys.readouterr().err


def test_keymap_rejects_unknown_key_name():
    with pytest.raises(ValueError, match="不明なキー名"):
        KeyMap.from_config({"up": ["UPP"]})


# ---------------------------------------------------------------- 本文の言語別ファイル（要件 F-72）
@pytest.fixture
def bilingual(sample_dir):
    """英語の本文を少しだけ持つ FirstQuest（lang/en/scenario.sco）。"""
    edit(sample_dir / "manifest.toml", 'languages = ["ja"]', 'languages = ["ja", "en"]')
    (sample_dir / "lang/en").mkdir(parents=True)
    shutil.copy(sample_dir / "scenario.sco", sample_dir / "lang/en/scenario.sco")
    edit(sample_dir / "lang/en/scenario.sco", "窓から朝の光が差し込んでいる。", "Morning light pours in through the window.")
    return sample_dir


def test_lang_overlay(bilingual):
    g = load_game(bilingual, lang="en")
    try:
        assert g.package.read_text("scenario.sco").count("Morning light") == 1
        assert g.package.has_translations()
    finally:
        g.close()
    g = load_game(bilingual, lang="ja")
    try:
        assert "Morning light" not in g.package.read_text("scenario.sco")
    finally:
        g.close()


def test_lang_overlay_needs_languages_in_manifest(bilingual):
    edit(bilingual / "manifest.toml", 'languages = ["ja", "en"]', 'languages = ["ja"]')
    g = load_game(bilingual, lang="en")
    try:
        assert "Morning light" not in g.package.read_text("scenario.sco")
        assert not g.package.has_translations()
    finally:
        g.close()
    rep, _ = check_package(bilingual, out=lambda s: None)
    assert any("lang/en/" in i.file and "languages" in i.message for i in rep.warnings)


def test_check_validates_lang_files(bilingual):
    rep, _ = check_package(bilingual, out=lambda s: None)
    assert rep.ok
    edit(bilingual / "lang/en/scenario.sco", "Morning light pours in through the window.", "@nosuchcommand")
    rep, _ = check_package(bilingual, out=lambda s: None)
    assert [i.file for i in rep.errors] == ["lang/en/scenario.sco"]


def test_title_language_toggle_reloads_scenario(bilingual):
    g = load_game(bilingual, lang="ja")
    d = Driver(g)
    t = d.scene
    assert isinstance(t, TitleScene)
    while t.index != TitleScene.LANG_INDEX:
        d.key("DOWN")
    d.key("ENTER")
    assert get_lang() == "en"
    assert t.game is not g and t.game.package.lang == "en"
    assert "Morning light" in t.game.package.read_text("scenario.sco")
    t.game.close()


def test_field_language_change_applies_at_title(bilingual):
    g = load_game(bilingual, lang="ja")
    d = Driver(g)
    for _ in range(4):
        d.key("ENTER")
    d.settle()
    set_lang("en")
    d.field.back_to_title()
    t = d.scene
    assert isinstance(t, TitleScene) and t.game.package.lang == "en"
    t.game.close()
