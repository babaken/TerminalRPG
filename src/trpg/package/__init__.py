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


LANG_DIR = "lang"          # 言語別のファイル：lang/<言語>/scenario.sco などが、その言語のとき元のファイルの代わりになる


@dataclass
class Package:
    path: Path
    source: Source
    manifest: Manifest
    lang: str = ""                     # 本文の言語（manifest.languages の 2 番目以降のときだけ lang/ のファイルを使う）

    @property
    def id(self) -> str:
        return self.manifest.id

    def exists(self, path: str) -> bool:
        return self.source.exists(path)

    def resolve(self, path: str) -> str:
        """実際に読むファイル（言語別のファイルがあればそちら）。"""
        if self.lang and self.lang != self.manifest.languages[0] and self.lang in self.manifest.languages:
            alt = f"{LANG_DIR}/{self.lang}/{path}"
            if self.source.exists(alt):
                return alt
        return path

    def read_text(self, path: str) -> Optional[str]:
        return read_text(self.source, self.resolve(path))

    def lang_dirs(self) -> list[str]:
        """lang/ の下にある言語。"""
        return sorted({f.split("/")[1] for f in self.files() if f.startswith(LANG_DIR + "/") and f.count("/") >= 2})

    def has_translations(self) -> bool:
        return any(l in self.manifest.languages[1:] for l in self.lang_dirs())

    def files(self) -> list[str]:
        return self.source.files()

    def close(self) -> None:
        self.source.close()

    def __enter__(self) -> "Package":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def open_package(path: Path | str, report: Optional[Report] = None, lang: str = "") -> Package:
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
    return Package(Path(path), src, manifest, lang)


@dataclass
class Candidate:
    """起動時に見つかったパッケージ候補。``error`` があれば選択できない。"""
    path: Path
    title: str = ""
    id: str = ""
    version: str = ""
    error: str = ""


def bundled_dirs() -> list[Path]:
    """エンジンに同梱したシナリオの置き場所（pip で入れたとき・exe のとき）。"""
    import sys
    out = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):          # PyInstaller の exe
        out.append(Path(sys._MEIPASS) / "scenarios")
    out.append(Path(__file__).resolve().parent.parent / "bundled")         # pip：trpg/bundled/
    return [d for d in out if d.is_dir()]


def find_scenarios(cwd: Optional[Path] = None) -> list[Candidate]:
    """起動フォルダと scenarios/、そのあとに同梱のシナリオ（同じ ID がすでに見つかっていれば出さない）。"""
    cwd = Path(cwd or Path.cwd())
    found = discover([cwd, cwd / "scenarios"])
    ids = {c.id for c in found if c.id}
    found += [c for c in discover(bundled_dirs()) if not c.id or c.id not in ids]
    return found


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
    "open_package", "discover", "find_scenarios", "bundled_dirs", "REQUIRED_FILES", "OPTIONAL_FILES",
]
