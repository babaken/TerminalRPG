# PyInstaller の設定：TRPG を 1 つの実行ファイル（Windows では TRPG.exe）にまとめる
#   pyinstaller packaging/trpg.spec   → dist/TRPG（.exe）
# -*- mode: python -*-
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    [os.path.join(ROOT, "packaging", "trpg_exe.py")],
    pathex=[os.path.join(ROOT, "src")],
    datas=[(os.path.join(ROOT, "scenarios", name), f"scenarios/{name}") for name in ("FirstQuest", "FirstQuestPlus")],
    hiddenimports=["trpg.i18n.en", "trpg.term.input_win", "trpg.term.input_posix"],
    excludes=["tkinter", "PIL", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="TRPG",
    console=True,          # 端末で動くゲームなのでコンソールを開く
    upx=False,
)
