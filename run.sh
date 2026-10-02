#!/bin/sh
# TRPG 起動スクリプト（Linux / macOS）
#
#   ./run.sh                         ふつうに起動
#   DEBUG=1 ./run.sh                 デバッグつきで起動（開発モード＋キーログ trpg_debug.log）
#   ./run.sh --scenario A.zip        引数はそのままゲームに渡す
#
# 1. 仮想環境（.venv）がなければ作る
# 2. requirements.txt が変わっていれば（初回も）ライブラリを入れる
# 3. デバッグフラグに応じて起動する

# ---- デバッグフラグ（1 = ON / 0 = OFF）。環境変数 DEBUG で上書きできる
DEBUG=${DEBUG:-0}

cd "$(dirname "$0")" || exit 1
VENV=.venv
PY="$VENV/bin/python"

# ---- 1. 仮想環境
if [ ! -x "$PY" ]; then
    echo "仮想環境を作ります: $VENV"
    if ! python3 -m venv "$VENV"; then
        echo "仮想環境を作れませんでした。Python 3.11 以上と venv を入れてください"
        echo "（Debian / Ubuntu なら: sudo apt install python3-venv）"
        exit 1
    fi
fi
if ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
    echo "Python 3.11 以上が必要です（$("$PY" --version)）。$VENV を消して、新しい Python で作り直してください"
    exit 1
fi

# ---- 2. ライブラリ（入れたときの requirements.txt の写しと比べる）
STAMP="$VENV/requirements.installed"
if ! cmp -s requirements.txt "$STAMP"; then
    echo "ライブラリを入れます（requirements.txt）"
    "$PY" -m pip install -r requirements.txt || exit 1
    cp requirements.txt "$STAMP"
fi

# ---- 3. 起動
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
if [ "$DEBUG" = 1 ]; then
    set -- --dev --keylog "$@"
fi
exec "$PY" -m trpg "$@"
