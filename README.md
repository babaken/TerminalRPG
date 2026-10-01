# TRPG — コンソール RPG エンジン

ASCII アートで表現する、ターミナル用の RPG エンジンです。設計資料は `docs/` にあります。

## 現在の実装状況

| 工程 | 状況 |
|---|---|
| 端末レイヤ（描画・入力・サイズ検知） `src/trpg/term/` | 実装済み |
| メインループ・シーン管理 `src/trpg/app.py` | 実装済み（最小限） |
| シナリオパッケージ読込（zip / フォルダ） `src/trpg/package/` | 実装済み |
| データ読込・検証（.data → データ） `src/trpg/data/` | 実装済み |
| スクリプト（構文解析・実行・検証） `src/trpg/script/` | 実装済み |
| タイトル・名前入力・フィールド移動・会話・選択肢 `src/trpg/scenes/` | 実装済み |
| エフェクト `src/trpg/effects/` | flash / fade_in / fade_out / shake / tint / typewriter / wait / rain / snow / starfall |
| ショップ・宿屋・冒険者協会（依頼）・仲間選択 `src/trpg/scenes/facility.py` | 実装済み |
| 戦闘（ターン制・スキル・道具・状態異常・逃走・テイム・経験値とレベルアップ） `src/trpg/battle/` `scenes/battle.py` | 実装済み |
| 全滅時の画面（タイトルへ／セーブから） `scenes/gameover.py` | 実装済み（「セーブから」はセーブ実装待ち） |
| FirstQuest `scenarios/FirstQuest/` | 1章「出会いと旅立ち」すべて遊べる |
| フィールドメニュー（どうぐ・スキル・そうび・つよさ・いらい・システム） `scenes/menu.py` | 実装済み |
| セーブ / ロード | 未着手（M1 で実装） |

## 動作環境

- Python 3.11 以上（外部ライブラリ不要）
- UTF-8 と ANSI エスケープに対応した端末、100 桁 × 30 行以上
  - Windows: **Windows Terminal** 推奨（コマンドプロンプト・PowerShell も可）
  - Linux: 一般的な端末エミュレータ

## 起動

```powershell
cd TRPG
$env:PYTHONPATH="src"
python -m trpg              # 起動フォルダと scenarios\ のシナリオを探して起動（複数あれば選択画面）
python -m trpg --dev        # 開発モード（右パネルにマップ ID・座標を表示）
python -m trpg --scenario FirstQuest.zip
python -m trpg --term-demo  # 描画・入力のデモ
python -m trpg --keylog     # 不具合調査用: 受け取ったキーと画面の状態を trpg_debug.log に記録
```
または `pip install -e .` のあとで `trpg` コマンドを実行します。

ゲーム中の操作
| キー | 動作 |
|---|---|
| 矢印 / WASD / テンキー | 移動、選択肢のカーソル移動 |
| Enter / Z / Space | 話す・調べる、会話送り（表示途中なら全文表示）、決定 |
| Esc / X / M | メニューを開く（どうぐ・スキル・そうび・つよさ・いらい・システム）。メニュー内では Esc でひとつ戻る |

戦闘中の操作
| キー | 動作 |
|---|---|
| ↑↓ | コマンド・スキル・道具を選ぶ |
| ←→ | 相手を選ぶ |
| Enter / Z | 決定、メッセージの早送り |
| Esc / X | ひとつ前に戻る（前の仲間のコマンドにも戻れる） |

オプション
| オプション | 説明 |
|---|---|
| `--ambiguous-width 2` | 罫線（─ │）などの表示がずれるときに試す |
| `--no-color` | 色を使わない |
| `--fps N` | フレームレート（既定 30） |

## シナリオの検証

```sh
python -m trpg --check scenarios/FirstQuest     # フォルダ
python -m trpg --check FirstQuest.zip           # zip
python -m trpg --list                           # 起動フォルダと scenarios/ のパッケージ一覧
```
データ（未定義の ID 参照・型の誤り・マップ行の長さ違い・タイルの表示幅・存在しない AA ファイル・綴り間違い）と
スクリプト（未知の命令・引数の誤り・条件式の誤り・存在しないラベル / マップ / アイテム / NPC・マップ外や壁の中の座標・
@if と @endif の対応・使われていないラベル・一度も立てていないフラグ）を、ファイル名と行番号つきで表示します。
シナリオに誤りがあるとゲームは起動せず、同じ内容を表示します。zip はフォルダごと圧縮した形（`FirstQuest/manifest.toml`）でも読めます。

ウィンドウを 100×30 より小さくすると、警告を出してゲームを一時停止します。大きくすると自動で元に戻ります。

## ドキュメント（`docs/`）

| ファイル | 内容 |
|---|---|
| `requirements.md` | 要件定義書 v1.1 |
| `basic_design.md` | 基本設計書 v0.2（データ仕様・スクリプト構文・計算式。【済】【未】で実装状況を表示） |
| `development_plan.md` | 開発計画（マイルストーン M1〜M7、GitHub での管理方針） |
| `scenario/FirstQuest_story.md` | FirstQuest 本文（案A） |
| `scenario/FirstQuestPlus_story.md` | FirstQuest+ 本文（案C、保留） |
| `plot_options.md` | 3・4 章のプロット案 |

## 開発

- リポジトリ: https://github.com/babaken/TRPG
- `main` は常に動く状態に保ち、作業は `feature/<内容>` ブランチ → プルリクエストで取り込む
- プッシュ・プルリクエストで GitHub Actions が Windows / Linux × Python 3.11 / 3.14 のテストを実行する

## テスト

```sh
pip install pytest
python -m pytest
```

## ソース構成（端末レイヤ）

| ファイル | 役割 |
|---|---|
| `term/width.py` | 文字の表示幅（全角 2 / 半角 1 / 結合文字 0）、切り詰め・折り返し |
| `term/style.py` | 色・属性、ANSI SGR 生成 |
| `term/buffer.py` | セルバッファ（全角の分断を自動補正）、文字・枠・塗り・AA 描画 |
| `term/screen.py` | ダブルバッファ、差分のみ出力、リサイズ検知 |
| `term/input_win.py` / `input_posix.py` | キー入力（Windows: ReadConsoleInputW で入力レコードを直接読む / Linux: termios） |
| `term/keys.py` | キーイベント、アクション（移動・決定・キャンセル・メニュー）とキー割当 |
| `term/terminal.py` | 端末の初期化・後始末（Windows の VT 有効化・UTF-8 化を含む） |
| `app.py` | シーンスタックとフレームループ、画面サイズ不足時の一時停止 |
| `scenes/term_demo.py` | 動作確認用デモ |
| `package/source.py` | zip / フォルダの読み出し、パストラバーサル・zip bomb 対策、Shift_JIS ファイル名の救済 |
| `package/manifest.py` | manifest.toml の検証、対応エンジン版の判定 |
| `package/__init__.py` | パッケージを開く・探す（`open_package` / `discover`） |
| `data/reader.py` | 型チェックつきの値取り出し、未知の項目の警告 |
| `data/models.py` | 職業・キャラ・敵・アイテム・マップ・クエスト等のデータクラス |
| `data/loader.py` | 各 .data の読み込みと相互参照チェック |
| `data/report.py` | エラー・警告の収集と表示（ファイル名・行番号つき） |
| `script/expr.py` | 条件式（flag / var / gold / item / party / quest / choice）の解析と評価 |
| `script/parser.py` | scenario.sco の構文解析（@if をジャンプに展開、@include、引数チェック） |
| `script/vm.py` | スクリプト実行機。会話・選択肢・待ちで止まり、再開できる |
| `script/lint.py` | スクリプトとデータの突き合わせ検証 |
| `world/state.py` | ゲームの進行状態（パーティ・所持品・フラグ・位置）、{hero} などの置き換え |
| `effects/__init__.py` | 画面エフェクト |
| `ui/widgets.py` | 会話窓（折り返し・ページ送り・1 文字ずつ表示）、選択肢窓 |
| `game.py` | パッケージ・データ・スクリプトをまとめて読み込み・検証 |
| `scenes/title.py` | タイトル・名前入力・シナリオ選択 |
| `scenes/field.py` | フィールド（移動・NPC・ワープ・イベント・スクリプト実行・エンカウント） |
| `scenes/facility.py` | ショップ・宿屋・冒険者協会・仲間選択（フィールドに重ねて表示） |
| `world/quests.py` | 依頼の受注・進み具合・達成報告 |
| `world/growth.py` | 経験値・レベルアップ・覚えるスキル |
| `battle/core.py` | 戦闘の進行と計算（画面に依存しない。行動順・ダメージ・会心・回避・属性・状態異常・敵 AI・逃走・テイム・報酬） |
| `scenes/battle.py` | 戦闘画面（敵の AA 表示・コマンド入力・対象選択・メッセージ） |
| `scenes/gameover.py` | 全滅時の画面 |
| `scenes/menu.py` | フィールドメニュー |
| `world/items.py` | フィールドでのアイテム・スキルの使用 |
