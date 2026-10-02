@echo off
rem TRPG 起動スクリプト（Windows）
rem
rem   run.bat                      ふつうに起動（ダブルクリックでも可）
rem   run.bat --scenario A.zip     引数はそのままゲームに渡す
rem
rem   1. 仮想環境（.venv）がなければ作る
rem   2. requirements.txt が変わっていれば（初回も）ライブラリを入れる
rem   3. デバッグフラグに応じて起動する
rem
rem ※ このファイルは Shift_JIS で保存しています（コマンドプロンプトで文字化けしないように）
setlocal

rem ---- デバッグフラグ（1 = ON：開発モード＋キーログ trpg_debug.log / 0 = OFF）
rem      set DEBUG=1 してから run.bat を実行しても ON になる
if not defined DEBUG set DEBUG=0

cd /d "%~dp0"
set VENV=.venv
set PY=%VENV%\Scripts\python.exe

rem ---- 1. 仮想環境
if exist "%PY%" goto venv_ok
echo 仮想環境を作ります: %VENV%
py -3 -m venv "%VENV%" 2>nul
if not exist "%PY%" python -m venv "%VENV%"
if not exist "%PY%" (
    echo 仮想環境を作れませんでした。Python 3.11 以上を https://www.python.org/ から入れてください
    goto fail
)
:venv_ok
"%PY%" -c "import sys; sys.exit(sys.version_info < (3, 11))"
if errorlevel 1 (
    echo Python 3.11 以上が必要です。%VENV% フォルダを消して、新しい Python で作り直してください
    goto fail
)

rem ---- 2. ライブラリ（入れたときの requirements.txt の写しと比べる）
set STAMP=%VENV%\requirements.installed
fc /b requirements.txt "%STAMP%" >nul 2>&1
if not errorlevel 1 goto libs_ok
echo ライブラリを入れます（requirements.txt）
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto fail
copy /y requirements.txt "%STAMP%" >nul
:libs_ok

rem ---- 3. 起動
set PYTHONPATH=%~dp0src
if "%DEBUG%"=="1" (
    "%PY%" -m trpg --dev --keylog %*
) else (
    "%PY%" -m trpg %*
)
if errorlevel 1 pause
exit /b %errorlevel%

:fail
pause
exit /b 1
