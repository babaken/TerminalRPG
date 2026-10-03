"""UI の言語（日本語 / 英語）。要件 D4：UI のみ英語に切り替えられる。シナリオの本文は翻訳しない。

    tr("やくそうを使った。")             → 今の言語の文（英語の訳がなければ日本語のまま）
    tr("{0}の攻撃！", name)              → "{0} attacks!".format(name)

日本語の文そのものを見出し（キー）にする。英語の訳は en.py の EN に書く。
"""
from __future__ import annotations

from typing import Any, Optional

LANGS = ("ja", "en")
_lang = "ja"
_table: dict[str, str] = {}


def set_lang(lang: str) -> None:
    global _lang, _table
    if lang not in LANGS:
        raise ValueError(f"言語は {' / '.join(LANGS)} のどれかです: {lang}")
    _lang = lang
    if lang == "en":
        from .en import EN
        _table = EN
    else:
        _table = {}


def get_lang() -> str:
    return _lang


def tr(src: str, *args: Any) -> str:
    """UI の文を今の言語にする。args は {0} {1} … に入る。"""
    text = _table.get(src, src)
    return text.format(*args) if args else text


# ---- 選んだ言語を次の起動でも使う（settings.json の "lang"）
def load_lang() -> Optional[str]:
    from .. import settings
    lang = settings.get("lang")
    return lang if lang in LANGS else None


def save_lang(lang: str) -> None:
    from .. import settings
    settings.save(lang=lang)


def lang_label() -> str:
    """タイトル画面の言語の項目（どちらの言語でも見つけられるよう両方の言葉で書く）。"""
    return "言語 / Language：" + ("English" if _lang == "en" else "日本語")
