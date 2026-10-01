"""不具合調査用のログ（``--keylog`` で有効）。

受け取った生のキー、各キーを受けたシーン、毎秒のシーン状態、例外を
起動フォルダの trpg_debug.log に書く。無効時は何もしない。
"""
from __future__ import annotations

import time
import traceback
from pathlib import Path
from typing import Optional, TextIO

_f: Optional[TextIO] = None
_t0 = 0.0


def enable(path: str | Path = "trpg_debug.log") -> Path:
    global _f, _t0
    p = Path(path).resolve()
    _f = open(p, "w", encoding="utf-8", buffering=1)
    _t0 = time.monotonic()
    return p


def enabled() -> bool:
    return _f is not None


def log(msg: str) -> None:
    if _f is not None:
        _f.write(f"{time.monotonic() - _t0:9.3f}  {msg}\n")


def log_exception(where: str) -> None:
    if _f is not None:
        log(f"EXCEPTION in {where}\n{traceback.format_exc()}")


def close() -> None:
    global _f
    if _f is not None:
        _f.close()
        _f = None
