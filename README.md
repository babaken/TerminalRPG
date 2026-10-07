# TRPG — コンソール RPG エンジン

ASCII アート（文字）で表現する、ターミナルで遊ぶ RPG エンジンです。
物語・マップ・敵・アイテムは **シナリオパッケージ**（テキストファイルの集まり、または zip）に分かれていて、差し替えると別のゲームになります。
サンプルシナリオが 2 本付いています（どちらも全 4 章、エンディングまで）。

| シナリオ | 内容 |
|---|---|
| **FirstQuest** | 王道。錆びた剣を拾った少年が、封じられた魔の王に挑む |
| **FirstQuest+** | どんでん返し。魔物が少年だけを狙う本当の理由――「主人公の正体」の物語（1・2 章は FirstQuest と同じ流れに伏線を加え、3・4 章は別の展開。セーブは別） |

起動すると、どちらで遊ぶかを選ぶ画面が出ます。

## できること

- 2D マップの探索、会話と選択肢、イベント、ダンジョン（暗い階・見えない罠）
- ターン制の戦闘（スキル〔技は SP・魔法は MP〕・属性・状態異常・テイムしたペットと使い魔）
- ショップ・宿屋・冒険者協会の依頼・仲間の加入と一時離脱
- 画面演出（光る・揺れる・暗転・雨や雪・流れ星・スタッフロールなど 16 種）
- 暗号化された 3 スロットのセーブ
- シナリオ制作ツール：検証・zip 化・画像から AA・マップエディタ

## 動作環境

- Python 3.11 以上
- UTF-8 と ANSI エスケープに対応した端末、100 桁 × 30 行以上
  - Windows：**Windows Terminal** 推奨（コマンドプロンプト・PowerShell も可）
  - Linux / macOS：一般的な端末

## 遊ぶ

| OS | 起動 |
|---|---|
| Windows | `run.bat`（ダブルクリックでも可） |
| Linux / macOS | `./run.sh` |

初回は仮想環境とライブラリ（`cryptography`）を自動で用意します。
起動フォルダか `scenarios/` にあるシナリオを探して起動し、複数あれば選択画面になります。
ほかのシナリオの zip は、起動フォルダか `scenarios/` に置くだけで遊べます。

### インストールして遊ぶ（リリースから）

| 方法 | 手順 |
|---|---|
| Windows の exe（Python 不要） | リリースの `TRPG-windows-<版>.zip` を展開して `TRPG.exe` を起動 |
| pip | リリースの `trpg-<版>-py3-none-any.whl` を `pip install trpg-<版>-py3-none-any.whl` → どのフォルダでも `trpg` |

どちらもサンプルシナリオ FirstQuest と FirstQuest+ が入っています（起動フォルダに同じ ID のシナリオがあればそちらを使います）。
セーブは起動フォルダの `saves/` に作ります。

### 操作

| キー | フィールド | 戦闘 |
|---|---|---|
| 矢印 / WASD / テンキー | 移動・選ぶ | ↑↓ コマンドを選ぶ、←→ 相手を選ぶ |
| Enter / Z / Space | 話す・調べる・会話送り・決定 | 決定・メッセージ送り |
| Esc / X / M | メニュー（どうぐ・スキル・そうび・つよさ・いらい・システム） | ひとつ前に戻る |

UI は日本語と英語（タイトル画面の「言語 / Language」、メニューの「システム → 設定」、または `--lang en`）。シナリオの本文は、シナリオが英語版のファイル（`lang/en/`）を持っているときだけ英語になります（FirstQuest・FirstQuest+ は日本語のみ）。
文字の速さもメニューの「システム → 設定」で変えられます。キー割当は `settings.json` で変えられます（[ツール利用ガイド](docs/tools.md)）。
表示がずれるときは `--ambiguous-width 2`、色を使わないなら `--no-color` を付けて起動します（[ツール利用ガイド](docs/tools.md)）。

## シナリオを作る

テキストファイルを書いて、検証コマンドで確かめながら作ります。プログラムは書きません。

1. [シナリオ作成マニュアル](docs/manual/README.md) の **チュートリアル** で、小さなシナリオを 1 本作ってみる
2. [スクリプトリファレンス](docs/manual/02_script.md)・[データ仕様書](docs/data_spec.md) で書き方を調べる
3. [ツール](docs/tools.md) で検証・マップ編集・AA 作成・zip 化

```sh
./run.sh --check scenarios/MyQuest                  # 検証（Windows は run.bat --check …）
./run.sh --scenario scenarios/MyQuest --dev         # 座標を表示しながら遊ぶ
python -m trpg.tools.map_editor scenarios/MyQuest   # マップエディタ
python -m trpg.tools.pack scenarios/MyQuest         # zip にして配る
```

## ドキュメント（`docs/`）

| ファイル | 内容 |
|---|---|
| [`manual/`](docs/manual/README.md) | **シナリオ作成マニュアル**（チュートリアル・スクリプトリファレンス・エフェクト・よくある作り方） |
| [`data_spec.md`](docs/data_spec.md) | **データ仕様書**（シナリオパッケージの全ファイル・全項目） |
| [`tools.md`](docs/tools.md) | **ツール利用ガイド**（起動オプション・検証・パッケージ・AA 変換・マップエディタ） |
| [`development.md`](docs/development.md) | 開発者向けガイド（セットアップ・テスト・CI・ソースの構成） |
| [`requirements.md`](docs/requirements.md) / [`basic_design.md`](docs/basic_design.md) | 要件定義書・基本設計書 |
| [`development_plan.md`](docs/development_plan.md) | 開発計画（マイルストーン） |
| [`scenario/`](docs/scenario/) | FirstQuest・FirstQuest+ の本文（実装メモつき） |

## 開発

リポジトリは https://github.com/babaken/TerminalRPG です。テストは `python -m pytest`、CI は Windows / Linux × Python 3.11 / 3.14。詳しくは [開発者向けガイド](docs/development.md)。

## ライセンス

[MIT License](LICENSE)。エンジン・ツール・ドキュメント・サンプルシナリオ（FirstQuest・FirstQuest+）のすべてに適用します。
