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
        for l in pkg.lang_dirs():
            if l not in m.languages[1:]:
                rep.warning(f"lang/{l}/", None, f"manifest の languages の 2 番目以降に {l} がないので使われません")
        for l in m.languages[1:]:
            if l not in pkg.lang_dirs():
                continue
            # 言語別のファイルに差し替えて同じ検証をする（誤りは [言語] 付きで出す）
            sub = Report()
            pkg.lang = l
            gd_l = load_game_data(pkg, sub)
            script_l = parse_script(pkg.read_text("scenario.sco") or "", sub, "scenario.sco", loader=pkg.read_text)
            lint_script(script_l, gd_l, sub, pkg, m.start_label)
            pkg.lang = ""
            seen = {(i.level, i.file, i.line, i.message) for i in rep.issues}
            for i in sub.issues:                 # 上の検証と同じものは出さない
                if (i.level, i.file, i.line, i.message) in seen:
                    continue
                i.file = f"lang/{l}/{i.file}" if pkg.exists(f"lang/{l}/{i.file}") else f"[{l}] {i.file}"
                rep.issues.append(i)
            out(f"言語 {l}: lang/{l}/ のファイルで検証しました")
    return rep, m
