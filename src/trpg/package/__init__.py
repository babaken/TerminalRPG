"""シナリオパッケージ（zip / 展開フォルダ）の検出と読み込み。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from ..data.report import DataError, Report
from .manifest import FILE as MANIFEST_FILE
from .manifest import FORMAT_VERSION, Manifest, parse_manifest
from .source import PackageError, Source, open_source, read_text

REQUIRED_FILES = ("scenario.sco", "Map.data", "Enemy.data", "Friends.data")
OPTIONAL_FILES = ("Items.data", "Quests.data")


@dataclass
class Package:
    path: Path
    source: Source
    manifest: Manifest

    @property
    def id(self) -> str:
        return self.manifest.id

    def exists(self, path: str) -> bool:
        return self.source.exists(path)

    def read_text(self, path: str) -> Optional[str]:
        return read_text(self.source, path)

    def files(self) -> list[str]:
        return self.source.files()

    def close(self) -> None:
        self.source.close()

    def __enter__(self) -> "Package":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def open_package(path: Path | str, report: Optional[Report] = None) -> Package:
    """パッケージを開いて manifest と必須ファイルを検証する。

    エラーがあれば DataError（report つき）を送出する。``report`` を渡すと警告もそこに集まる。
    """
    rep = report if report is not None else Report()
    src = open_source(Path(path))
    try:
        text = read_text(src, MANIFEST_FILE)
        if text is None:
            raise PackageError(f"{MANIFEST_FILE} が見つかりません")
        manifest = parse_manifest(text, rep)
        for f in REQUIRED_FILES:
            if not src.exists(f):
                rep.error(f, None, "必須ファイルがありません（ファイル名の大文字・小文字も確認してください）")
        if not rep.ok:
            raise DataError(rep)
    except BaseException:
        src.close()
        raise
    return Package(Path(path), src, manifest)


@dataclass
class Candidate:
    """起動時に見つかったパッケージ候補。``error`` があれば選択できない。"""
    path: Path
    title: str = ""
    id: str = ""
    version: str = ""
    error: str = ""


def discover(dirs: Iterable[Path | str]) -> list[Candidate]:
    """フォルダ内の *.zip と、manifest.toml を含むサブフォルダを探す。"""
    seen: set[Path] = set()
    found: list[Candidate] = []
    for d in dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            rp = p.resolve()
            if rp in seen:
                continue
            is_pkg = (p.is_file() and p.suffix.lower() == ".zip") or (p.is_dir() and (p / MANIFEST_FILE).is_file())
            if not is_pkg:
                continue
            seen.add(rp)
            c = Candidate(p)
            try:
                with open_package(p) as pkg:
                    c.title, c.id, c.version = pkg.manifest.title, pkg.manifest.id, pkg.manifest.version
            except PackageError as e:
                if p.is_file() and "manifest.toml が見つかりません" in str(e):
                    continue  # シナリオではない zip は無視
                c.error = str(e)
            except DataError as e:
                c.error = f"データに {len(e.report.errors)} 件のエラーがあります（--check で詳細を表示）"
            found.append(c)
    return found


__all__ = [
    "Package", "PackageError", "Candidate", "Manifest", "FORMAT_VERSION",
    "open_package", "discover", "REQUIRED_FILES", "OPTIONAL_FILES",
]
