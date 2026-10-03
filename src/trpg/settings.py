"""プレイヤーの設定（言語・文字の速さ・キー割当）。セーブと同じフォルダの settings.json に保存する。

    {"lang": "en", "text_speed": "fast", "keys": {"ok": ["ENTER", "z", "SPACE"]}}

ファイルがない・壊れている・書けないときは既定値で遊べる。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TEXT_SPEEDS = {"slow": 0.5, "normal": 1.0, "fast": 2.0, "instant": 0.0}   # 文字送りの速さの倍率（0 は一気に表示）
TEXT_SPEED_NAMES = {"slow": "おそい", "normal": "ふつう", "fast": "はやい", "instant": "一瞬"}


def path() -> Path:
    from .save import default_dir
    return default_dir() / "settings.json"


def load() -> dict[str, Any]:
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def get(key: str, default: Any = None) -> Any:
    return load().get(key, default)


def save(**values: Any) -> None:
    """値を書き足す（ほかの項目はそのまま）。"""
    data = load()
    data.update(values)
    p = path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass                                   # 書けなくても遊べる（次の起動で元に戻るだけ）


# ---- 文字送りの速さ（起動時に settings.json から読み、メニューで変える）
_text_speed = "normal"


def text_speed() -> str:
    return _text_speed


def text_speed_factor() -> float:
    return TEXT_SPEEDS[_text_speed]


def set_text_speed(name: str, store: bool = False) -> None:
    global _text_speed
    if name not in TEXT_SPEEDS:
        raise ValueError(f"文字の速さは {' / '.join(TEXT_SPEEDS)} のどれかです: {name}")
    _text_speed = name
    if store:
        save(text_speed=name)


def load_text_speed() -> None:
    name = get("text_speed")
    set_text_speed(name if name in TEXT_SPEEDS else "normal")
