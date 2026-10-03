"""UI の言語（日本語 / 英語）。要件 D4：UI のみ英語に切り替えられる。シナリオの本文は翻訳しない。

    tr("やくそうを使った。")             → 今の言語の文（英語の訳がなければ日本語のまま）
    tr("{0}の攻撃！", name)              → "{0} attacks!".format(name)

日本語の文そのものを見出し（キー）にする。英語の訳は en.py の EN に書く。
"""
from __future__ import annotations

import json
from pathlib import Path
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


# ---- 設定ファイル（選んだ言語を次の起動でも使う）。場所はセーブと同じフォルダの settings.json
def settings_path() -> Path:
    from ..save import default_dir
    return default_dir() / "settings.json"


def load_lang() -> Optional[str]:
    try:
        lang = json.loads(settings_path().read_text(encoding="utf-8")).get("lang")
    except (OSError, ValueError, AttributeError):
        return None
    return lang if lang in LANGS else None


def save_lang(lang: str) -> None:
    path = settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data["lang"] = lang
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass                                   # 書けなくても遊べる（次の起動で元の言語になるだけ）


def lang_label() -> str:
    """タイトル画面の言語の項目（どちらの言語でも見つけられるよう両方の言葉で書く）。"""
    return "言語 / Language：" + ("English" if _lang == "en" else "日本語")
