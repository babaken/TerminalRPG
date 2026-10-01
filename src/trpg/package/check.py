"""シナリオパッケージの検証（``--check`` とパッケージツールで共用）。"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from ..data import DataError, Report, load_game_data
from .manifest import Manifest
from .source import PackageError


def check_package(path: Path | str, out: Callable[[str], None] = print) -> tuple[Report, Optional[Manifest]]:
    """データとスクリプトを検証して経過を ``out`` に出す。開けなかったときはエラー入りの Report と None を返す。"""
    from . import open_package
    from ..script.lint import lint_script
    from ..script.parser import parse_script

    rep = Report()
    try:
        pkg = open_package(path, rep)
    except PackageError as e:
        rep.error(str(path), None, str(e))
        return rep, None
    except DataError as e:
        return e.report, None
    with pkg:
        m = pkg.manifest
        out(f"タイトル: {m.title}（ID: {m.id} / 版: {m.version}）")
        gd = load_game_data(pkg, rep)
        out(f"読込: {gd.summary()}")
        script = parse_script(pkg.read_text("scenario.sco") or "", rep, "scenario.sco", loader=pkg.read_text)
        lint_script(script, gd, rep, pkg, m.start_label)
        out(f"スクリプト: ラベル {len(script.labels)} / 命令 {len(script.instrs)}")
    return rep, m
