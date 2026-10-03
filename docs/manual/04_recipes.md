# よくある作り方（レシピ集）

FirstQuest（`scenarios/FirstQuest/`）で実際に使っている書き方です。

---

## 宝箱（一度だけ開けられる）

Map.data：宝箱のタイル（通れない）と、開いた宝箱のタイルを用意し、宝箱の上に「調べる」イベントを置きます。
```toml
"B" = { glyph = "箱", pass = false, color = "bright_yellow", name = "宝箱" }
"b" = { glyph = "箱", pass = false, color = "gray",          name = "開いた宝箱" }

[[map.event]]
x = 5
y = 3
trigger = "check"
label = "b3_chest"
once = true
```
scenario.sco：中身を渡し、`@tile` で開いた宝箱に変えます（セーブに残る）。
```
*b3_chest
宝箱を開けた！
@item add steel_sword
{item.steel_sword}を手に入れた！
@tile 5 3 b
@end
```

## 話の進み具合で NPC を出し分ける

NPC の `when` に条件を書きます。同じ人を別の場所に出すときは、ID を変えて 2 人書きます。
```toml
[[map.npc]]
id = "chief"              # 襲撃の前は外にいる
x = 16
y = 5
talk = "chief_talk"
when = "!flag.raid"

[[map.npc]]
id = "chief_in"           # 襲撃のあとは家の中（house_chief のマップ側に書く）
x = 5
y = 3
talk = "chief_home_talk"
when = "flag.raid"
```

## マップに入ったときの出来事

```toml
[[map.event]]
x = 0
y = 0
trigger = "auto"
label = "first_visit"
once = true
```
`auto` はマップに入るたびに調べられ、条件を満たす最初の 1 つだけが起きます（`once` で一度きり）。

## 通行止め（あとで開く）

道の上に NPC を立たせ、`when` で消します。
```toml
[[map.npc]]
id = "gate_guard"
glyph = "兵"
x = 39                     # ワープ（出口）のマスの上
y = 11
talk = "gate_closed"
when = "!flag.permit"
```
落石などはタイルで道をふさぎ、`@tile` で開けても作れます。

## 依頼（冒険者協会）

Quests.data：
```toml
[[quest]]
id = "q_slime"
name = "街道のスライム退治"
rank = "F"
desc = "スライムを 5 体退治してください。"
goal = { type = "defeat", group = "slime", count = 5 }   # deliver / defeat / reach / flag
reward = { gold = 60, exp = 10 }
when = "flag.guild_registered"       # 掲示板に出る条件
on_complete = "quest_done"           # 報告のあとに実行するラベル
```
受付の人の `talk` で `@guild` を開けば、受注・報告ができます。物語の依頼は `@quest give ID` で直接渡し、`goal = { type = "flag", flag = … }` にすると、フラグを立てた時点で報告できるようになります。

**ランダムの依頼**：`random = true` を付けると、掲示板の枠（manifest の `[rules] random_quests`、既定 3）にランダムに貼られ、受けると別の依頼が補充されます（何度でも受けられる）。エリアごとに `when` とランクを上げておくと、行ける中でいちばん新しいエリアの依頼が必ず 1 つ出ます。
```toml
[[quest]]
id = "qr_mole"
name = "カブラ村のモグラ退治"
rank = "E"                            # 街道（F）より新しいエリア
goal = { type = "defeat", group = "mole", count = 4 }
reward = { gold = 100, exp = 45 }
random = true
when = "flag.ch2_rumor"               # カブラ村に行けるようになったら
```

## 仲間を選んで加える

```
@recruit garo mia rina pick=1
@if party.has(garo)
  ガロ「よろしく頼む」
@elif party.has(mia)
  ミア「よろしくね」
@endif
```
`lv=avg` を付けると、パーティの平均レベルで加わります。すでにいる仲間は候補に出ません。

## 選んだ仲間ごとに台詞を変える

仲間によって口調が違うので、`{party.2}` に共通の台詞を言わせず、人ごとに書き分けます。
```
@if party.has(garo)
  ガロ「来るぞ！」
@elif party.has(rina)
  リナ「来ます！」
@elif party.has(mia)
  ミア「来るわよ！」
@endif
```

## 負けイベント（勝てない戦い）

```
@battle group=boss_1 escape=false turns=3 lose=*defeated
@goto *defeated

*defeated
ボス「その程度か」
```
3 ターンたつか全滅すると `*defeated` へ進みます（倒れた仲間は HP 1 で起き上がる）。

## 仲間の一時離脱と復帰

```
@party leave #2 keep=injured
{away.injured}が{hero}をかばい、倒れた――
…
@if away.injured == mia
  ミア「待たせちゃったね」
@endif
@party return injured
```
`keep=` の名前で、レベル・装備ごと覚えておきます（セーブに残る）。

## 主人公一人の試練

```
@battle group=shadow members=hero escape=false lose=*retry
```
Enemy.data で `copy = "hero"` の敵を作ると、主人公と同じ能力値の「影」になります（名前に `{hero}` 可）。

## 武器の進化

```
@item replace rusty_sword awakening_sword
@skill add hero fuukouzan
```
袋の中でも装備中でも入れ替わります。

## ダンジョン

- マップに `dark = true`（周りしか見えない）と `dungeon = true`（入ると階の名前を表示）。
- 階段はタイル（「上」「下」）の上にワープを置く。
- 見えない罠：Map.data に `[[trap]]` を書き、マップに `traps = [2, 3]`（初めて入ったときにランダムに置く）。
- 帰還アイテム：`use = { field = true, effect = "warp", to = "town", x = 7, y = 8, when = "map.dungeon" }`。
- 回復の泉：「調べる」イベントで `@heal all`。

## 章の区切りとセーブ

```
@flag set ch1_done
@effect typewriter "第1章　完"
@save_point
@goto *ch2_start
```
注意：`@save_point` のセーブはその時点で保存されるので、**続きの場面はロードしても実行されません**。次の章を始める処理は、`*on_load` か、話しかけたときなど「状態から判断して始まる」形にしておくと安全です。
```
*on_load
@if flag.ch1_done and !flag.ch2_started
  @goto *ch2_start
@endif
@end
```

## 古いセーブを補正する

シナリオを更新して、すでに通り過ぎた場面で新しい処理（`@tile` など）を足したときは、`*on_load` で補います。
```
*on_load
@if flag.ch3_lost
  @tile 27 8 . map=field_blackrock
@endif
@end
```

## ペット・使い魔

- テイマーの「手なずける」（スキルの `kind = "tame"`）で仲間にした魔物は、次の戦闘から自動で戦います。`@pet 敵ID` でも渡せます。
- Friends.data のキャラに `familiar = "pipi"` と書くと、そのキャラが戦うとき一緒に戦う使い魔になります。強さは敵データの `growth` と主人の Lv で決まります。

## 英語の本文を付ける

UI は `--lang en` やタイトル画面の「言語 / Language」で英語になりますが、シナリオの本文はシナリオ側で用意します。
1. manifest.toml に `languages = ["ja", "en"]` と書く
2. 訳したファイルを `lang/en/` に同じ名前で置く（`lang/en/scenario.sco`、`lang/en/Items.data` など。全部でなくてよい）

UI が英語のときは `lang/en/` のファイルを、ないものは元のファイルを使います。ID・ラベル・フラグは元のファイルとそろえてください（セーブは両方の言語で共通です）。
`--check` は `lang/en/` に差し替えた形でも検証し、誤りを `lang/en/scenario.sco:12` のように表示します。
