"""シナリオパッケージツール（要件 T-03）：シナリオのフォルダを検証してから zip にする。

    python -m trpg.tools.pack scenarios/FirstQuest              → FirstQuest-0.3.0.zip
    python -m trpg.tools.pack scenarios/FirstQuest -o dist/A.zip
    python -m trpg.tools.pack scenarios/FirstQuest --dry-run    → 入れるファイルの一覧だけ表示

- 検証（``--check`` と同じ）でエラーがあれば zip を作らない。``--strict`` なら警告でも中断する。
- 隠しファイル・``__pycache__``・バックアップ・Python ファイルなど、遊ぶのに要らないものは入れない。
- manifest.toml が zip の直下に来る形で作り、できた zip をもう一度開いて検証する。
- zip 内の日時は固定する（同じ中身なら同じ zip になる）。
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..package.check import check_package
from ..package.source import MANIFEST, MAX_FILE_SIZE, MAX_FILES, MAX_TOTAL_SIZE

# 入れないもの（ファイル名・フォルダ名に対するパターン）
EXCLUDE_DIRS = ("__pycache__", ".*")
EXCLUDE_FILES = (".*", "Thumbs.db", "desktop.ini", "*~", "*.bak", "*.tmp", "*.swp",
                 "*.py", "*.pyc", "*.pyo", "*.zip", "trpg_debug.log")
ZIP_DATE = (2000, 1, 1, 0, 0, 0)


class PackError(Exception):
    """zip を作れない。メッセージは利用者向けの日本語。"""


@dataclass
class FileList:
    files: list[str] = field(default_factory=list)          # 入れるファイル（manifest.toml 基準の相対パス）
    skipped: list[str] = field(default_factory=list)        # 入れないファイル・フォルダ
    total: int = 0                                          # 入れるファイルの合計サイズ


def _match(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def collect(root: Path) -> FileList:
    """zip に入れるファイルを集める。リンクはたどらない。"""
    fl = FileList()
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        for name in sorted(dirnames):
            if _match(name, EXCLUDE_DIRS) or (d / name).is_symlink():
                fl.skipped.append((d / name).relative_to(root).as_posix() + "/")
                dirnames.remove(name)
        for name in sorted(filenames):
            p = d / name
            rel = p.relative_to(root).as_posix()
            if _match(name, EXCLUDE_FILES) or p.is_symlink() or not p.is_file():
                fl.skipped.append(rel)
                continue
            size = p.stat().st_size
            if size > MAX_FILE_SIZE:
                raise PackError(f"ファイルが大きすぎます（上限 {MAX_FILE_SIZE // 1024 // 1024}MB）: {rel}")
            fl.files.append(rel)
            fl.total += size
    fl.files.sort()
    fl.skipped.sort()
    if len(fl.files) > MAX_FILES:
        raise PackError(f"ファイル数が多すぎます（{len(fl.files)} 個、上限 {MAX_FILES}）")
    if fl.total > MAX_TOTAL_SIZE:
        raise PackError(f"合計サイズが大きすぎます（上限 {MAX_TOTAL_SIZE // 1024 // 1024}MB）")
    return fl


def write_zip(root: Path, files: list[str], dest: Path) -> None:
    """一時ファイルに書いてから置き換える（途中で失敗しても壊れた zip を残さない）。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for rel in files:
                info = zipfile.ZipInfo(rel, ZIP_DATE)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                zf.writestr(info, (root / rel).read_bytes())
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()


def default_name(root: Path, version: str) -> str:
    return f"{root.name}-{version}.zip" if version else f"{root.name}.zip"


def _size(n: int) -> str:
    return f"{n / 1024:.1f}KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f}MB"


def pack(src: Path | str, output: Optional[Path | str] = None, *, strict: bool = False,
         force: bool = False, dry_run: bool = False, out: Callable[[str], None] = print) -> Optional[Path]:
    """検証して zip を作る。作った zip のパス（dry_run なら None）を返す。失敗は PackError。"""
    root = Path(src)
    if not root.is_dir():
        raise PackError(f"シナリオのフォルダを指定してください: {src}")
    if not (root / MANIFEST).is_file():
        raise PackError(f"{MANIFEST} がありません。シナリオのフォルダではない可能性があります: {src}")
    root = root.resolve()

    out(f"検証: {src}")
    rep, manifest = check_package(root, out)
    if rep.issues:
        out(rep.format())
    if not rep.ok:
        raise PackError("エラーがあるため zip を作りません")
    if strict and rep.warnings:
        raise PackError("警告があるため zip を作りません（--strict）")

    fl = collect(root)
    out(f"ファイル: {len(fl.files)} 個（{_size(fl.total)}）")
    if fl.skipped:
        out("入れないもの: " + ", ".join(fl.skipped))
    dest = Path(output) if output else Path.cwd() / default_name(root, manifest.version)
    if dry_run:
        for rel in fl.files:
            out(f"  {rel}")
        out(f"作成先（--dry-run のため作りません）: {dest}")
        return None
    if dest.resolve().is_relative_to(root):
        raise PackError(f"シナリオのフォルダの中には作れません: {dest}")
    if dest.exists() and not force:
        raise PackError(f"すでにあります（上書きするには --force）: {dest}")

    write_zip(root, fl.files, dest)
    rep2, _ = check_package(dest, lambda s: None)     # できた zip をそのまま読めるか
    if not rep2.ok:
        dest.unlink()
        raise PackError("作った zip の検証に失敗しました\n" + rep2.format())
    out(f"作成しました: {dest}（{_size(dest.stat().st_size)}）")
    return dest


def main(argv: list[str] | None = None) -> int:
    from ..__main__ import _stdout_utf8
    _stdout_utf8()
    p = argparse.ArgumentParser(prog="python -m trpg.tools.pack",
                                description="シナリオのフォルダを検証してから zip にする")
    p.add_argument("folder", help="シナリオのフォルダ（manifest.toml のあるフォルダ）")
    p.add_argument("-o", "--output", metavar="ZIP", help="作る zip（既定：<フォルダ名>-<版>.zip を今のフォルダに）")
    p.add_argument("--strict", action="store_true", help="警告があっても中断する")
    p.add_argument("--force", action="store_true", help="同じ名前の zip があれば上書きする")
    p.add_argument("--dry-run", action="store_true", help="zip は作らず、入れるファイルを表示する")
    args = p.parse_args(argv)
    try:
        pack(args.folder, args.output, strict=args.strict, force=args.force, dry_run=args.dry_run)
    except PackError as e:
        print(f"中断: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
