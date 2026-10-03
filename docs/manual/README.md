# シナリオ作成マニュアル

TRPG エンジンで遊べるシナリオ（物語・マップ・敵・アイテム）を作るためのマニュアルです。
プログラムは書きません。テキストファイルを書いて、検証コマンドで確かめながら作ります。

| 章 | 内容 |
|---|---|
| [1. チュートリアル](01_tutorial.md) | 小さなシナリオ「HelloQuest」をゼロから作る（完成品：[sample/HelloQuest](sample/HelloQuest/)） |
| [2. スクリプトリファレンス](02_script.md) | scenario.sco の書き方・全命令・条件式・本文の制御コード |
| [3. エフェクト](03_effects.md) | 画面演出（光る・揺れる・暗転・天気・スタッフロールなど） |
| [4. よくある作り方](04_recipes.md) | 宝箱・NPC の出し分け・依頼・仲間・負けイベント・ダンジョン・章の区切り など |

データファイル（Friends.data / Enemy.data / Items.data / Map.data / Quests.data / manifest.toml）の全項目は、データ仕様書（M6 6-2 で作成予定）にまとめます。それまでは [基本設計書](../basic_design.md) の 3〜9 章を見てください。

## シナリオの中身

```
MyQuest/
├─ manifest.toml   シナリオの名前・ルール・はじめの状態（必須）
├─ Friends.data    職業・仲間（必須）
├─ Enemy.data      敵・敵グループ・出現表（必須）
├─ Map.data        タイル・マップ・NPC・ワープ・イベント・罠（必須）
├─ Items.data      アイテム・スキル・状態異常・ショップ
├─ Quests.data     冒険者協会の依頼
├─ scenario.sco    会話と進行のスクリプト（必須。@include で分割可）
└─ aa/             アスキーアート（*.txt。色は同名の *.color）
```

## 使う道具

| 目的 | コマンド |
|---|---|
| 検証する | `python -m trpg --check scenarios/MyQuest` |
| 遊ぶ（座標表示つき） | `python -m trpg --scenario scenarios/MyQuest --dev` |
| マップを編集する | `python -m trpg.tools.map_editor scenarios/MyQuest` |
| 画像から AA を作る | `python -m trpg.tools.aa_convert image.png -w 24 --color -d scenarios/MyQuest/aa` |
| zip にして配る | `python -m trpg.tools.pack scenarios/MyQuest` |

ツールの詳しい使い方は README を見てください。

## 作るときのコツ

- 少し書いたらすぐ `--check`。エラーはファイル名と行番号つきで出ます。
- 大きな物語は章ごとに `.sco` を分けて `@include`。
- サンプル `scenarios/FirstQuest/`（全 4 章）に、ほぼすべての機能の使い方があります。
