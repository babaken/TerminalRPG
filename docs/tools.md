# ツール利用ガイド

TRPG エンジンに付いているコマンドとツールの使い方です。
コマンドは TRPG のフォルダで実行します（`python` の代わりに `run.bat` / `./run.sh` に引数を渡しても同じです）。

| やりたいこと | コマンド |
|---|---|
| 遊ぶ | `run.bat` / `./run.sh`、または `python -m trpg` |
| シナリオを検証する | `python -m trpg --check シナリオ` |
| シナリオを zip にする | `python -m trpg.tools.pack シナリオのフォルダ` |
| 画像から AA を作る | `python -m trpg.tools.aa_convert 画像` |
| マップを編集する | `python -m trpg.tools.map_editor シナリオのフォルダ` |

> 手動で `python -m …` を使うときは `PYTHONPATH=src`（Windows の PowerShell なら `$env:PYTHONPATH="src"`）を設定し、仮想環境の Python（`.venv/bin/python` / `.venv\Scripts\python`）を使います。`pip install -e .`（またはリリースの wheel を `pip install`）すると `trpg` `trpg-pack` `trpg-aa` `trpg-mapedit` のコマンドでも起動できます。Windows の `TRPG.exe` は `python -m trpg` と同じオプションを受け付けます（ツールは入っていません）。

---

## 1. 起動スクリプト（run.bat / run.sh）

| OS | 起動 | デバッグつきで起動 |
|---|---|---|
| Windows | `run.bat`（ダブルクリックでも可） | `run.bat` の `set DEBUG=0` を `1` に書き換える、または `set DEBUG=1` のあとで `run.bat` |
| Linux / macOS | `./run.sh` | `DEBUG=1 ./run.sh` |

1. 仮想環境（`.venv`）がなければ作る（Python 3.11 以上が必要）
2. `requirements.txt` のライブラリを入れる（初回と、`requirements.txt` が変わったときだけ）
3. デバッグが ON なら `--dev --keylog` つきで、OFF ならふつうに起動する

引数はそのままゲームに渡します（`run.bat --scenario FirstQuest.zip`、`./run.sh --check scenarios/FirstQuest`）。
`run.bat` はコマンドプロンプトで文字化けしないよう Shift_JIS で保存しています。

## 2. ゲームのコマンド（python -m trpg）

| オプション | 説明 |
|---|---|
| （なし） | 起動フォルダと `scenarios/` のシナリオを探して起動（複数あれば選択画面） |
| `--scenario パス` | そのシナリオ（zip / フォルダ）で起動 |
| `--dev` | 開発モード：右パネルにマップ ID・座標・向きを表示 |
| `--check パス` | 検証だけして結果を表示（3 章） |
| `--list` | 見つかったシナリオの一覧 |
| `--lang ja` / `--lang en` | UI の言語（メニュー・戦闘・施設などの文）。省略時はタイトル画面の「言語 / Language」で選んだ言語（初めは日本語）。シナリオの本文は翻訳しない |
| `--keylog` | 不具合調査用：受け取ったキー・画面の状態・例外を `trpg_debug.log` に記録 |
| `--ambiguous-width 2` | 罫線（─ │）などの表示がずれるときに試す |
| `--no-color` | 色を使わない |
| `--fps N` | フレームレート（既定 30） |
| `--term-demo` | 描画・入力のデモ（端末の確認用） |

- ウィンドウが 100×30 より小さいと、警告を出してゲームを一時停止します（広げると戻ります）。
- 言語と文字の速さは、フィールドメニューの「システム → 設定」でも変えられます。設定はセーブと同じフォルダの `settings.json` に保存します。
- キー割当は `settings.json` の `"keys"` で変えられます。書いたアクションだけ既定と置き換わります（アクション：`up` `down` `left` `right` `ok` `cancel` `menu`。キー：1 文字か `UP` `ENTER` `ESC` `TAB` `F1` などの名前。スペースは `" "`）。誤りがあると理由を表示して起動しません。
  ```json
  {"lang": "ja", "text_speed": "fast", "keys": {"ok": ["ENTER", "z", "j"], "menu": ["m", "TAB"]}}
  ```
  `text_speed` は `slow` `normal` `fast` `instant`。
- セーブは起動フォルダの `saves/<シナリオID>/slot1〜3.sav`（環境変数 `TRPG_SAVE_DIR` で変更可）。暗号化と改ざん検知をしているので、書き換えたファイルや別シナリオのファイルは読み込みません。
- 不具合を報告するときは `--keylog` で起動して再現し、`trpg_debug.log` を添えてください。

## 3. 検証（--check）

```sh
python -m trpg --check scenarios/FirstQuest     # フォルダ
python -m trpg --check FirstQuest.zip           # zip
```
データとスクリプトのすべての誤りを、ファイル名と行番号つきで表示します（内容は [データ仕様書 10 章](data_spec.md)・[スクリプトリファレンス 9 章](manual/02_script.md)）。
エラーがあるとゲームは起動しません。警告は起動できますが、たいてい綴り間違いです。

## 4. パッケージツール（zip にする）

```sh
python -m trpg.tools.pack scenarios/FirstQuest              # → FirstQuest-<版>.zip を今のフォルダに
python -m trpg.tools.pack scenarios/FirstQuest -o dist/FirstQuest.zip
python -m trpg.tools.pack scenarios/FirstQuest --dry-run    # 入れるファイルを表示するだけ
```
| オプション | 説明 |
|---|---|
| `-o ZIP` | 作る zip（既定：`<フォルダ名>-<版>.zip`） |
| `--strict` | 警告があっても中断する |
| `--force` | 同じ名前の zip を上書きする |
| `--dry-run` | 作らずに、入れるファイルを表示 |

- 先に `--check` と同じ検証をして、エラーがあれば zip を作りません。
- 隠しファイル・`__pycache__`・バックアップ（`*~` `*.bak`）・Python ファイル・zip は入れません。
- manifest.toml が zip の直下に来る形で作り、できた zip をもう一度検証します。
- zip 内の日時を固定するので、同じ中身からは同じ zip ができます。

## 5. AA 変換ツール（画像 → アスキーアート）

`pip install Pillow` が必要です（ゲーム本体には不要。`requirements.txt` の `# Pillow` の `#` を外してもよい）。

```sh
python -m trpg.tools.aa_convert slime.png -w 20 --color --preview          # ファイルを作らず端末で確かめる
python -m trpg.tools.aa_convert slime.png -w 20 --color -d scenarios/MyQuest/aa   # → slime.txt と slime.color
python -m trpg.tools.aa_convert images/ -w 24 -d out/                      # フォルダ内の画像をまとめて
```
| オプション | 説明 |
|---|---|
| `-w N` | 出力の桁数（半角換算、既定 40） |
| `-o TXT` / `-d DIR` | 出力ファイル（画像 1 つのとき）／出力フォルダ（名前は `<画像名>.txt`） |
| `--charset ascii / wide` | 記号のみ（既定）／全角の記号。`--chars " .oO@"` で濃さの順に好きな文字を並べられる |
| `--invert` | 明暗を反転（既定は明るいところほど濃い文字。白い背景の画像はこれを付ける） |
| `--edges` / `--outline` | 輪郭を `- / \| \` の線で描く／線だけを描く。`--edge-threshold 0.3`（小さいほど線が増える） |
| `--color` | 色ファイル（`.color`）も作る。色合いから 15 色のどれかに寄せる |
| `--aspect 0.5` | 文字 1 個の 幅÷高さ。縦長・横長に見えるときに調整 |
| `--preview` | ファイルを作らず、端末に色つきで表示 |
| `--no-trim` / `--force` | 周りの空白を取らない／同じ名前のファイルを上書きする |

透明なところは半角空白になり、戦闘画面などでは下が透けます。

## 6. マップエディタ（TUI）

```sh
python -m trpg.tools.map_editor scenarios/MyQuest
python -m trpg.tools.map_editor scenarios/MyQuest --map town
```
左にマップ、右にタイルの一覧とカーソル位置の情報（タイル・NPC・ワープ・イベント）が出ます。NPC は Map.data の文字、ワープは Ｗ、イベントは Ｅ で表示します。

| キー | 操作 |
|---|---|
| 矢印（PgUp / PgDn / Home / End） | カーソル移動 |
| Enter / Space | 選んでいるタイルで塗る |
| `[` `]` / Tab、`1`〜`9` | タイルを選ぶ |
| `i` | カーソルの下のタイルを選ぶ（スポイト） |
| `p` | ペン（オンの間は動いた先を塗る） |
| `v` | 範囲を選ぶ（矢印で広げて `f`：塗りつぶし、`c`：コピー、Esc：やめる） |
| `b` | コピーした範囲をカーソルの位置に貼り付け（はみ出た分は切り捨て） |
| `r` | マップの大きさを変える（右・下を増減。NPC などが外に出るときは変えない） |
| `n` / `w` / `e` | カーソルの位置に NPC / ワープ / イベントを置く（入力フォーム） |
| `c` | カーソルの位置の NPC などを編集（同じマスに複数あれば選ぶ） |
| `g` | 動かす（矢印で移動、Enter で置く、Esc でやめる） |
| `x` / Delete | 消す（y で確定） |
| `u` | 元に戻す（塗る・範囲・大きさ・NPC など・マップの追加） |
| `o` | NPC・ワープ・イベントの表示／非表示 |
| `m` | マップを切り替える（一覧で `a`：新しいマップ） |
| `s` / F2 | 保存 |
| `q` / Esc | 終わる（未保存なら確認） |
| `?` / F1 | 操作説明 |

入力フォーム：↑↓ で項目、Enter で入力・切り替え（選択肢は ← → でも）、F2 で決定、Esc で取消。ID の重複・文字の幅・道順・ワープ先がマップの外でないかを確かめます。

保存について：
- Map.data のうち、変えたところ（マップの `rows`、NPC などの表の項目、新しいマップ）だけを書き換えます。コメントや書式はそのまま残ります。
- 最初の保存の前に元のファイルを `Map.data.bak` に写します（パッケージツールは `.bak` を zip に入れません）。
- 保存のあと `--check` と同じ検証をして、エラーと警告の件数を表示します。
- 編集できるのはフォルダのシナリオだけです（zip は不可）。
