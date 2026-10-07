# 開発者向けガイド

TRPG エンジン本体を開発する人向けの情報です。シナリオを作るだけなら [シナリオ作成マニュアル](manual/README.md) を見てください。

## セットアップ（手動）

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt pytest Pillow   # Windows: .venv\Scripts\pip install …
```
（または `pip install -e .[dev]`。`run.bat` / `run.sh` を一度実行しても仮想環境とライブラリが用意されます）

## テスト

```sh
python -m pytest            # pyproject.toml で pythonpath = src を設定済み
```
- 端末なしで画面にキーを送る通しプレイ（FirstQuest・FirstQuest+ の各章・マニュアルの見本 HelloQuest）を含みます。
- 乱数は固定しているので、結果は毎回同じです。
- セーブは各テストの一時フォルダに作ります（`TRPG_SAVE_DIR`）。
- データ仕様書（`docs/data_spec.md`）が読み込み処理と食い違っていないかも確かめます。
- `TRPG_TEST_LANG=en python -m pytest` で英語の UI のまま流せます（日本語の文を確かめるテストは失敗・待ち続けるので、`timeout` を付けてファイルごとに流し、`AssertionError` 以外の例外が出ていないかを見ます）。

## CI

GitHub Actions（`.github/workflows/test.yml`）が、プッシュとプルリクエストごとに Windows / Linux × Python 3.11 / 3.14 で次を実行します。
1. `python -m trpg --check scenarios/FirstQuest`（FirstQuestPlus も）
2. `python -m trpg.tools.pack scenarios/FirstQuest --strict`（FirstQuestPlus も。警告があると失敗）
3. `python -m pytest`

### 配布物のビルド

`.github/workflows/build.yml` が、プルリクエスト（`src/` `scenarios/` `packaging/` `pyproject.toml` を変えたとき）・手動実行・`v*` のタグで次を作ります。
- Windows：PyInstaller（`packaging/trpg.spec`）で `TRPG.exe` を作り、空のフォルダで `--list` して FirstQuest と FirstQuest+ が見えるか確かめ、`TRPG-windows-<版>.zip`（exe と `packaging/README_windows.txt`）にする
- wheel：`python -m build --wheel` → 新しい仮想環境に入れて、空のフォルダで `trpg --list` を確かめる

どちらも Actions の成果物（Artifacts）に残り、タグのときはリリースに添付します。
手元で作るときは `pip install build pyinstaller` のあと `python -m build --wheel`（→ `dist/`）／`pyinstaller packaging/trpg.spec`（→ `dist/TRPG`、その OS 用）。

- wheel には `scenarios/` のシナリオ（FirstQuest・FirstQuestPlus）を `trpg/bundled/<名前>/` として入れます（`pyproject.toml` の `package-dir`）。exe では PyInstaller の展開先の `scenarios/<名前>`。シナリオを足したら `pyproject.toml` と `packaging/trpg.spec` にも足します（`tests/test_distribution.py` が確かめます）。
- シナリオは `find_scenarios()`（`src/trpg/package/__init__.py`）が「起動フォルダ・`scenarios/`」→「同梱」の順に探し、同じ ID は起動フォルダ側を使います。
- `src/trpg/` にサブパッケージを足したら `pyproject.toml` の `packages` にも足します（`tests/test_distribution.py` が確かめます）。

## 作業の流れ

- リポジトリ：https://github.com/babaken/TerminalRPG
- `main` は常に動く状態に保つ。作業は `feature/<内容>`（ドキュメントは `docs/<内容>`、修正は `fix/<内容>`）のブランチ → プルリクエストで取り込む。
- マイルストーンごとに `v0.x.0` のタグを付け、GitHub のリリースに FirstQuest・FirstQuest+ の zip（パッケージツールで作成）を添付する。
- 計画と進み具合は [開発計画](development_plan.md)。

## UI の文を足すとき

画面に出す文は `tr("…")` で包み、英語の訳を `src/trpg/i18n/en.py` に足します（日本語の文がそのまま見出し）。
名前や数は `tr("{0}の攻撃！", name)` のように `{0}` `{1}` で渡します。比べるときは訳す前の日本語の見出しで比べます（訳した文で比べると英語のとき一致しない）。

## ソースの構成（`src/trpg/`）

| 場所 | 役割 |
|---|---|
| `__main__.py` | コマンドライン（`python -m trpg`） |
| `app.py` | シーンスタックとフレームループ、画面サイズ不足時の一時停止、IME オンの検出 |
| `game.py` | パッケージ・データ・スクリプトをまとめて読み込み・検証 |
| `term/` | 端末：表示幅（全角 2）、色、セルバッファ、差分描画、キー入力（Windows：ReadConsoleInputW / Linux：termios）、キー割当 |
| `package/` | zip・フォルダの読み出しと安全チェック、manifest、パッケージの探索、検証（`check.py`） |
| `data/` | .data の読み込み（`loader.py`）、データクラス（`models.py`）、型チェック（`reader.py`）、エラー・警告（`report.py`） |
| `script/` | 条件式（`expr.py`）、構文解析（`parser.py`）、実行（`vm.py`）、データとの突き合わせ検証（`lint.py`） |
| `world/` | ゲームの状態（`state.py`）、依頼（`quests.py`）、成長（`growth.py`）、フィールドでのアイテム（`items.py`）、見えない罠（`traps.py`） |
| `battle/core.py` | 戦闘の進行と計算（画面に依存しない） |
| `effects/` | 画面エフェクト |
| `ui/` | 会話窓・選択肢窓（`widgets.py`）、本文の制御コード（`markup.py`）、AA の色（`aa.py`）、MP / SP の表示（`points.py`） |
| `scenes/` | タイトル・フィールド・施設（ショップ・宿屋・協会・仲間選択）・メニュー・戦闘・全滅・セーブ／ロード・エンディング |
| `save/` | セーブの形式・暗号化（AES-256-GCM）・スロット管理 |
| `i18n/` | UI の言語：`tr("日本語の文", 引数…)` で今の言語の文にする。英語の訳は `en.py`（訳の抜けは `tests/test_i18n.py` が検出）。設定は `settings.json` |
| `tools/` | パッケージツール（`pack.py`）、AA 変換（`aa_convert.py`）、マップエディタ（`map_editor.py`・`mapfile.py`・`objform.py`） |

設計の詳細と経緯は [基本設計書](basic_design.md)、要件は [要件定義書](requirements.md)。
