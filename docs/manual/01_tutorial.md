# チュートリアル：はじめてのシナリオ「HelloQuest」

村長から頼まれて、草原の大スライムを退治する――そんな小さなシナリオを、ゼロから作ります。
完成したものは [`sample/HelloQuest/`](sample/HelloQuest/) にあります（このマニュアルの例はテストで動作を確認しています）。

所要時間の目安：30 分〜1 時間

---

## 0. 準備

- TRPG が動く状態にしておきます（README の「かんたん起動」：Windows は `run.bat`、Linux は `./run.sh`）。
- テキストエディタ（UTF-8 で保存できるもの）。メモ帳・VS Code など。
- 以下のコマンドは TRPG のフォルダで実行します（`run.sh` / `run.bat` に引数を渡しても同じです）。

```sh
python -m trpg --check scenarios/HelloQuest      # 検証
python -m trpg --scenario scenarios/HelloQuest   # 遊ぶ
```
（`python` が見つからないときは `.venv/bin/python`、Windows は `.venv\Scripts\python`。`PYTHONPATH=src` が必要です。`run.sh --check …` なら設定不要です）

## 1. フォルダを作る

`scenarios/` の下に `HelloQuest` フォルダを作り、次のファイルを置きます。

```
scenarios/HelloQuest/
├─ manifest.toml   … シナリオの名前・はじめの状態（必須）
├─ Friends.data    … 職業と仲間（必須）
├─ Enemy.data      … 敵・敵の組み合わせ・出現表（必須）
├─ Map.data        … タイル・マップ・NPC・ワープ・イベント（必須）
├─ Items.data      … アイテム・スキル・ショップ
├─ scenario.sco    … 会話と進行のスクリプト（必須）
└─ aa/             … アスキーアート（敵・タイトル画面）
```

`.data` は TOML という書式です。`#` から行末はコメントです。文字コードは UTF-8 にしてください。

## 2. manifest.toml：シナリオの身分証

```toml
[package]
id = "helloquest"          # 英小文字・数字・_。セーブデータの紐づけに使うので、公開後は変えない
title = "HelloQuest"
version = "1.0.0"
author = "あなたの名前"
engine = ">=1.0"
languages = ["ja"]

[title_screen]
aa = "aa/title.txt"        # タイトル画面の AA
effect = "starfall"        # 背景の演出：starfall / rain / snow / none

[rules]
gameover = "choose"        # 全滅したら：choose（選ぶ）/ retry_from_save / title
save = "anywhere"          # どこでもセーブ（save_point_only なら @save_point だけ）
party_max = 4
start_label = "start"      # ニューゲームで最初に実行するラベル

[start]
party = ["hero"]           # 最初のパーティ（Friends.data のキャラクター ID）
gold = 20
items = ["herb"]
```

## 3. Friends.data：主人公

職業（`[[job]]`）とキャラクター（`[[character]]`）を書きます。

```toml
[[job]]
id = "hero"
name = "勇者"
growth = { hp = 7, mp = 2, atk = 2, def = 2, mag = 1, agi = 2, luk = 1 }   # レベルアップ時の平均上昇量
equip = ["sword", "light_armor"]                    # 装備できる種類（アイテムの category）
skills = [ { lv = 2, skill = "power_slash" } ]      # Lv 2 で「強撃」を覚える
sp = { base = 8, growth = 2 }                       # 技に使う SP（Lv1 で 8、Lv ごとに +2）

[[character]]
id = "hero"
name = "ユウ"
name_input = true          # ニューゲームで名前を入力できる（本文では {hero}）
job = "hero"
lv = 1
stats = { hp = 30, mp = 5, atk = 8, def = 6, mag = 3, agi = 6, luk = 5 }
equip = { weapon = "wood_sword" }
```

## 4. Items.data：やくそう・木の剣・強撃・お店

```toml
[[item]]
id = "herb"
name = "やくそう"
type = "consumable"        # consumable（消耗品）/ equipment（装備）/ key（だいじなもの）
price = 8
desc = "HP を 30 回復する。"
use = { field = true, battle = true, target = "ally_one", effect = "heal", power = 30 }

[[item]]
id = "wood_sword"
name = "木の剣"
type = "equipment"
slot = "weapon"            # weapon / armor / shield / accessory
category = "sword"         # 職業の equip と照らし合わせる
price = 20
stats = { atk = 3 }

[[skill]]
id = "power_slash"
name = "強撃"
sp = 6                     # 技は SP、魔法は mp = … で MP を使う
target = "enemy_one"
kind = "physical"
power = 8
anim = "shake:2"           # 使ったときの演出

[[shop]]
id = "village_shop"
name = "村の道具屋"
goods = ["herb", "wood_sword"]
```

## 5. Enemy.data：スライムと大スライム

```toml
[[enemy]]
id = "slime"
name = "スライム"
aa = "aa/slime.txt"        # 戦闘画面に出す AA
stats = { hp = 8, atk = 5, def = 2, agi = 3, luk = 1 }
exp = 4
gold = 3
drops = [ { item = "herb", rate = 0.2 } ]   # 20% でやくそうを落とす

[[enemy]]
id = "big_slime"
name = "大スライム"
aa = "aa/slime.txt"
stats = { hp = 30, atk = 7, def = 3, agi = 2, luk = 1 }
exp = 20
gold = 15

[[group]]                  # 一緒に出てくる敵の組み合わせ
id = "slime_2"
members = ["slime", "slime"]

[[group]]
id = "boss"
members = ["big_slime"]

[[encounter]]              # ランダムエンカウント（マップの encounter で使う）
id = "meadow"
steps = [10, 20]           # 10〜20 歩ごとに
table = [ { group = "slime_2", weight = 1 } ]
```

`aa/slime.txt` には好きなアスキーアートを書きます（画像から作るなら `python -m trpg.tools.aa_convert`）。

```
   .---.
  /  o o\
 |   ~   |
  `-----'
```

## 6. Map.data：村と草原

まずタイル（地形の部品）を決めます。1 文字の記号に、画面での見た目（全角 1 文字）と通れるかどうかを割り当てます。

```toml
[[tileset]]
id = "default"
[tileset.tiles]
"#" = { glyph = "＃", pass = false, color = "gray",         name = "壁" }
"." = { glyph = "．", pass = true,  color = "green",        name = "地面" }
"T" = { glyph = "木", pass = false, color = "bright_green", name = "木" }
"H" = { glyph = "家", pass = false, color = "yellow",       name = "家" }
"=" = { glyph = "：", pass = true,  color = "yellow",       name = "道" }
```

マップは `rows` に 1 行ずつ書きます（全行同じ長さ）。座標は左上が (0, 0)、右へ x、下へ y です。

```toml
[[map]]
id = "village"
name = "はじまりの村"
tileset = "default"
rows = [
  "TTTTTTTTT=TTTTTTTTTT",
  "T........=.........T",
  "T..HHH...=...HHH...T",
  "T..HHH...=...HHH...T",
  "T........=.........T",
  "T..................T",
  "T..................T",
  "TTTTTTTTTTTTTTTTTTTT",
]

[[map.warp]]               # 北の出口（9, 0）に立つと草原の (9, 8) へ
x = 9
y = 0
to = "meadow"
tx = 9
ty = 8
dir = "up"

[[map.npc]]                # 村長。話しかけると *elder_talk を実行
id = "elder"
glyph = "長"
color = "white"
x = 9
y = 5
talk = "elder_talk"

[[map.npc]]
id = "shopkeeper"
glyph = "商"
color = "yellow"
x = 14
y = 4
talk = "shop_talk"
```

草原（`meadow`）も同じように書き、`encounter = "meadow"` でスライムが出るようにします。
奥の (9, 2) に「踏んだら一度だけ起きる」イベントを置きます。

```toml
[[map.event]]
x = 9
y = 2
trigger = "touch"          # touch（踏む）/ check（調べる）/ auto（マップに入ったとき）
label = "boss"
once = true
```

> マップは手で書く代わりに **マップエディタ**（`python -m trpg.tools.map_editor scenarios/HelloQuest`）でも作れます。

## 7. scenario.sco：話の流れ

`*ラベル` から次の `@end` までが 1 つの場面です。`話者「台詞」` で会話、`@命令` で処理を書きます。

```
*start
@chapter 1 "はじめての冒険"
@map village 9 6 dir=up
@effect fade_in 600
村長「おお、{hero}。ちょうどよいところに来た」
村長「北の草原に大きなスライムが住みついて困っておる。退治してくれんか」
@flag set got_quest
@end
```

- `*start` はニューゲームで最初に実行されます（manifest の `start_label`）。
- `@map` で主人公をマップに置き、`@effect fade_in` で黒から明るくします。
- `{hero}` は主人公の名前に置き換わります。
- `@flag set` で「依頼を受けた」ことを覚えておきます。

村長に話しかけたときは、フラグで台詞を変えます。

```
*elder_talk
@if flag.boss_done
  村長「ありがとう、{hero}！　村の英雄じゃ」
  @goto *ending
@elif flag.got_quest
  村長「大スライムは北の草原の奥じゃ。気をつけてな」
@endif
@end
```

道具屋はショップ画面を開くだけです。

```
*shop_talk
道具屋「いらっしゃい！」
@shop village_shop
@end
```

草原の奥のイベントで戦闘します。`escape=false` で逃げられないボス戦になります。勝つと次の行へ進みます（負けたら全滅画面）。

```
*boss
地面がぶるぶると揺れた……！
大スライムがあらわれた！
@battle group=boss escape=false
@flag set boss_done
大スライムをやっつけた！　村長に知らせよう。
@end
```

最後にエンディングです。

```
*ending
@effect starfall count=6
村に、平和が戻った。
@ending text="{hero}の冒険は、まだ始まったばかり"
```

## 8. 検証する

```sh
python -m trpg --check scenarios/HelloQuest
```

「問題は見つかりませんでした。」と出れば OK です。間違いがあると、ファイル名と行番号つきで教えてくれます。

```
エラー Map.data:13  [[map]] village の rows: 8 行目の長さ（20）が 1 行目（19）と違います
エラー scenario.sco:15  ラベル *endin が scenario.sco にありません
警告   scenario.sco:16  フラグ got_quest は参照されていますが、@flag set されている箇所がありません
警告   scenario.sco:34  ラベル *ending はどこからも使われていません
```
（`@goto *endin` の打ち間違い、`@flag set got_quset` の綴り間違い、マップの行の長さ違い、の例）

エラーがあるとゲームは起動しません。警告は起動できますが、たいてい綴り間違いなので直しましょう。

## 9. 遊ぶ

```sh
python -m trpg --scenario scenarios/HelloQuest
python -m trpg --scenario scenarios/HelloQuest --dev   # 右パネルにマップ ID と座標を表示
```

`--dev` は座標を確かめながらイベントを置くときに便利です。

## 10. zip にして配る

```sh
python -m trpg.tools.pack scenarios/HelloQuest     # → HelloQuest-1.0.0.zip
```

できた zip を、遊ぶ人の TRPG フォルダか `scenarios/` に置けば、起動時に選べます。

---

## 次に読むもの

- [スクリプトリファレンス](02_script.md)：すべての命令と条件式
- [エフェクト](03_effects.md)：画面演出
- [よくある作り方](04_recipes.md)：宝箱・仲間の加入・依頼・ダンジョン・負けイベントなど
- データファイルの全項目は [データ仕様書](../data_spec.md)（M6 6-2 で作成予定）。それまでは [基本設計書](../basic_design.md) の 3〜9 章と、サンプル `scenarios/FirstQuest/` を参考にしてください
