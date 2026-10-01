"""シナリオパッケージのファイル読み出し（zip / 展開フォルダ）。

zip は第三者配布を想定し、以下を拒否する（要件 6.3）。
- 絶対パス・ドライブ指定・``..`` を含むパス（パストラバーサル）
- ファイル数・展開後サイズ・圧縮率が異常に大きいもの（zip bomb）
"""
from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath
from typing import Optional

MAX_FILES = 10_000
MAX_FILE_SIZE = 32 * 1024 * 1024        # 1 ファイル 32MB
MAX_TOTAL_SIZE = 256 * 1024 * 1024      # 合計 256MB
MAX_RATIO = 200                          # 圧縮率（1MB を超えるファイルのみ判定）
MANIFEST = "manifest.toml"


class PackageError(Exception):
    """パッケージを開けない。メッセージは利用者向けの日本語。"""


def normalize(path: str) -> str:
    """パッケージ内パスを正規化する。不正なら PackageError。"""
    p = path.replace("\\", "/")
    if p.startswith("/") or (len(p) > 1 and p[1] == ":"):
        raise PackageError(f"絶対パスは使えません: {path}")
    parts = [s for s in PurePosixPath(p).parts if s not in ("", ".")]
    if any(s == ".." for s in parts):
        raise PackageError(f"「..」を含むパスは使えません: {path}")
    return "/".join(parts)


class Source:
    """パッケージ内ファイルへのアクセス（基底）。パスは manifest.toml のあるフォルダ基準。"""

    name: str

    def files(self) -> list[str]:
        raise NotImplementedError

    def exists(self, path: str) -> bool:
        raise NotImplementedError

    def read_bytes(self, path: str) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        pass


class DirSource(Source):
    """展開済みフォルダ（開発モード ``--dev``）。"""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.name = str(root)
        if not self.root.is_dir():
            raise PackageError(f"フォルダが見つかりません: {root}")

    def _path(self, path: str) -> Path:
        p = (self.root / normalize(path)).resolve()
        if p != self.root and self.root not in p.parents:
            raise PackageError(f"パッケージ外のファイルは読めません: {path}")
        return p

    def files(self) -> list[str]:
        return sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file())

    def exists(self, path: str) -> bool:
        try:
            return self._path(path).is_file()
        except PackageError:
            return False

    def read_bytes(self, path: str) -> bytes:
        p = self._path(path)
        if not p.is_file():
            raise FileNotFoundError(path)
        if p.stat().st_size > MAX_FILE_SIZE:
            raise PackageError(f"ファイルが大きすぎます: {path}")
        return p.read_bytes()


def _zip_name(info: zipfile.ZipInfo) -> str:
    """Windows の古い zip ツールが作る Shift_JIS のファイル名を救済する。"""
    name = info.filename
    if not (info.flag_bits & 0x800):
        try:
            name = name.encode("cp437").decode("cp932")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return name


class ZipSource(Source):
    def __init__(self, path: Path):
        self.name = str(path)
        try:
            self.zf = zipfile.ZipFile(path)
        except FileNotFoundError:
            raise PackageError(f"ファイルが見つかりません: {path}") from None
        except zipfile.BadZipFile:
            raise PackageError(f"zip ファイルとして読めません: {path}") from None
        try:
            self._index = self._check()
            self.prefix = self._find_root()
        except BaseException:
            self.zf.close()
            raise

    def _check(self) -> dict[str, zipfile.ZipInfo]:
        infos = self.zf.infolist()
        if len(infos) > MAX_FILES:
            raise PackageError(f"ファイル数が多すぎます（{len(infos)} 個、上限 {MAX_FILES}）")
        total = 0
        index: dict[str, zipfile.ZipInfo] = {}
        for info in infos:
            name = normalize(_zip_name(info))
            if info.is_dir() or not name:
                continue
            if info.file_size > MAX_FILE_SIZE:
                raise PackageError(f"ファイルが大きすぎます: {name}")
            if info.file_size > 1024 * 1024 and info.file_size > info.compress_size * MAX_RATIO:
                raise PackageError(f"圧縮率が異常です（zip bomb の可能性）: {name}")
            total += info.file_size
            if total > MAX_TOTAL_SIZE:
                raise PackageError("展開後のサイズが大きすぎます")
            index[name] = info
        return index

    def _find_root(self) -> str:
        """manifest.toml の位置。直下になければ「フォルダごと zip にした」形（A/manifest.toml）も許す。"""
        if MANIFEST in self._index:
            return ""
        candidates = [n for n in self._index if n.count("/") == 1 and n.endswith("/" + MANIFEST)]
        if len(candidates) == 1:
            return candidates[0][: -len(MANIFEST)]
        raise PackageError(f"{MANIFEST} が見つかりません。シナリオパッケージではない可能性があります")

    def files(self) -> list[str]:
        n = len(self.prefix)
        return sorted(k[n:] for k in self._index if k.startswith(self.prefix))

    def exists(self, path: str) -> bool:
        try:
            return (self.prefix + normalize(path)) in self._index
        except PackageError:
            return False

    def read_bytes(self, path: str) -> bytes:
        info = self._index.get(self.prefix + normalize(path))
        if info is None:
            raise FileNotFoundError(path)
        with self.zf.open(info) as f:
            data = f.read(MAX_FILE_SIZE + 1)
        if len(data) > MAX_FILE_SIZE:
            raise PackageError(f"ファイルが大きすぎます: {path}")
        return data

    def close(self) -> None:
        self.zf.close()


def open_source(path: Path) -> Source:
    path = Path(path)
    if path.is_dir():
        src: Source = DirSource(path)
        if not src.exists(MANIFEST):
            raise PackageError(f"{MANIFEST} が見つかりません: {path}")
        return src
    return ZipSource(path)


def read_text(src: Source, path: str) -> Optional[str]:
    """UTF-8（BOM 可）で読む。無ければ None。文字コード不正は PackageError。"""
    if not src.exists(path):
        return None
    data = src.read_bytes(path)
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise PackageError(f"{path} が UTF-8 ではありません（{e.start} バイト目）。UTF-8 で保存し直してください") from None
