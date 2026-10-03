"""エントリポイント: ``python -m trpg``

- ``python -m trpg``                       起動フォルダと scenarios/ のシナリオを探して起動（複数あれば選択画面）
- ``python -m trpg --scenario PATH``       指定したシナリオ（zip / フォルダ）で起動
- ``python -m trpg --dev``                 開発モード（座標表示など）
- ``python -m trpg --check PATH``          シナリオパッケージを検証して結果を表示
- ``python -m trpg --list``                見つかったシナリオの一覧を表示
- ``python -m trpg --term-demo``           描画・入力のデモ
- ``python -m trpg --keylog``              不具合調査用のキーログを trpg_debug.log に記録
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .term import TerminalError, set_ambiguous_width


def _stdout_utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def cmd_check(path: str) -> int:
    from .package.check import check_package

    print(f"検証: {path}")
    rep, _ = check_package(path)
    print(rep.format() if rep.issues else "問題は見つかりませんでした。")
    return 0 if rep.ok else 1


def cmd_list() -> int:
    from .package import discover
    cands = discover([Path.cwd(), Path.cwd() / "scenarios"])
    if not cands:
        print("シナリオパッケージが見つかりません（起動フォルダか scenarios/ に置いてください）")
        return 1
    for c in cands:
        status = f"× {c.error}" if c.error else "○"
        print(f"{status}  {c.title or '-'}  [{c.id or '-'} {c.version}]  {c.path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _stdout_utf8()
    p = argparse.ArgumentParser(prog="trpg", description="コンソール RPG エンジン")
    p.add_argument("--scenario", metavar="PATH", help="起動するシナリオ（zip / フォルダ）")
    p.add_argument("--dev", action="store_true", help="開発モード（座標などを表示）")
    p.add_argument("--check", metavar="PATH", help="シナリオパッケージ（zip / フォルダ）を検証する")
    p.add_argument("--list", action="store_true", help="見つかったシナリオパッケージを一覧表示する")
    p.add_argument("--term-demo", action="store_true", help="描画・入力のデモを起動する")
    p.add_argument("--ambiguous-width", type=int, choices=(1, 2), default=1,
                   help="曖昧幅文字（─ │ ■ など）の幅。表示が崩れる場合は 2 を試す")
    p.add_argument("--no-color", action="store_true", help="色を使わない")
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--lang", choices=("ja", "en"),
                   help="UI の言語（ja / en）。省略時はタイトル画面で選んだ言語（初めは日本語）")
    p.add_argument("--keylog", action="store_true",
                   help="不具合調査用: 受け取ったキーと画面の状態を trpg_debug.log に記録する")
    args = p.parse_args(argv)
    if args.keylog:
        from . import debuglog
        from . import __version__
        import platform
        path = debuglog.enable()
        debuglog.log(f"trpg {__version__} python {platform.python_version()} {platform.platform()} args={argv or sys.argv[1:]}")
        print(f"キーログを記録します: {path}")

    from .i18n import load_lang, set_lang
    set_lang(args.lang or load_lang() or "ja")

    if args.check:
        return cmd_check(args.check)
    if args.list:
        return cmd_list()
    set_ambiguous_width(args.ambiguous_width)

    from .app import App
    if args.term_demo:
        from .scenes.term_demo import TermDemoScene
        scene = TermDemoScene()
    else:
        scene = _first_scene(args)
        if scene is None:
            return 1
    app = App(scene, fps=args.fps, use_color=not args.no_color)
    try:
        app.run()
    except TerminalError as e:
        print(f"起動できません:\n{e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    return 0


def _first_scene(args):
    """起動するシナリオを決めて最初の画面を返す。端末を初期化する前にエラーを表示するため、ここで読み込む。"""
    from .data import DataError
    from .game import load_game
    from .package import PackageError, discover
    from .scenes.title import SelectScene, TitleScene

    path = args.scenario
    if path is None:
        cands = discover([Path.cwd(), Path.cwd() / "scenarios"])
        if not cands:
            print("シナリオが見つかりません。起動フォルダか scenarios/ にシナリオの zip を置いてください。", file=sys.stderr)
            return None
        if len(cands) > 1:
            return SelectScene(cands, dev=args.dev)
        path = cands[0].path
    try:
        game = load_game(path, dev=args.dev)
    except PackageError as e:
        print(f"シナリオを開けません: {e}", file=sys.stderr)
        return None
    except DataError as e:
        print(f"シナリオにエラーがあります: {path}", file=sys.stderr)
        print(e.report.format(), file=sys.stderr)
        return None
    return TitleScene(game)


if __name__ == "__main__":
    sys.exit(main())
