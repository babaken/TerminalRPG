"""PyInstaller 用の入口（exe を起動すると python -m trpg と同じ動きをする）。

    pyinstaller packaging/trpg.spec

exe には FirstQuest を同梱する（exe の中の scenarios/）。exe と同じフォルダか scenarios/ に
ほかのシナリオの zip を置けば、それも選べる。セーブは起動フォルダの saves/ に作る。
"""
import sys

from trpg.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
