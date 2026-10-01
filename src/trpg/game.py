"""1 本のゲーム（シナリオパッケージ＋読み込んだデータ＋スクリプト）をまとめる。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .data import DataError, GameData, Report, load_game_data
from .package import Package, PackageError, open_package
from .script.lint import lint_script
from .script.parser import Script, parse_script


@dataclass
class Game:
    package: Package
    data: GameData
    script: Script
    dev: bool = False

    @property
    def manifest(self):
        return self.package.manifest

    def close(self) -> None:
        self.package.close()


def load_game(path: Path | str, report: Optional[Report] = None, dev: bool = False) -> Game:
    """パッケージを開いて全データとスクリプトを読み、検証する。

    エラーがあれば DataError（report 付き）。開けない場合は PackageError。
    """
    rep = report if report is not None else Report()
    pkg = open_package(path, rep)
    try:
        gd = load_game_data(pkg, rep)
        text = pkg.read_text("scenario.sco") or ""
        script = parse_script(text, rep, "scenario.sco", loader=pkg.read_text)
        lint_script(script, gd, rep, pkg, pkg.manifest.start_label)
        if not rep.ok:
            raise DataError(rep)
    except BaseException:
        pkg.close()
        raise
    return Game(pkg, gd, script, dev)


__all__ = ["Game", "load_game", "PackageError", "DataError"]
