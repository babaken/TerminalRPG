# スクリプトリファレンス（scenario.sco）

会話・分岐・イベントの流れは `scenario.sco` に書きます。ここではすべての書き方と命令をまとめます。
間違いは `python -m trpg --check シナリオ` がファイル名と行番号つきで教えてくれます。

---

## 1. 基本

| 書き方 | 意味 |
|---|---|
| `*ラベル` | 場面の入口。`@goto` やマップのイベント・NPC の `talk` から呼ばれる。名前は英数字と `_` |
| `話者「本文」` | 台詞。続けて書いた台詞は 1 つの会話窓にまとめ、入りきらなければページ送り |
| 地の文 | 話者のない本文（ナレーション） |
| 空行 | 改ページ |
| `@命令 引数…` | 命令。引数は空白区切り、`名前=値` の形も使う。空白を含む値は `"…"` で囲む |
| `# …` | コメント（行頭） |
| `@include "ch2.sco"` | 別ファイルを読み込む（章ごとに分けると管理しやすい） |
| `@end` | 場面の終わり |

インデント（字下げ）は意味を持ちません。`@if` の中を字下げしておくと読みやすくなります。

```
*elder_talk
@if flag.boss_done
  村長「ありがとう！」
@else
  村長「北の草原を頼む」
@endif
@end
```

### 予約ラベル
| ラベル | いつ実行されるか |
|---|---|
| `*start` | ニューゲームのとき（manifest の `start_label` で変更可） |
| `*on_load` | セーブを読み込んだ直後。古いセーブの補正などに使う（ロード時はマップの auto イベントは起きない） |
| `*gameover` | 全滅したとき（`@battle` に `lose=` がない場合）、全滅画面の前に |

---

## 2. 本文

### 置き換え
| 書き方 | 置き換わるもの |
|---|---|
| `{hero}` | 主人公の名前 |
| `{name.ID}` | キャラクターの名前（`{name.garo}`）。名前を付けられる仲間は、付けた名前になる（まだ加わっていなければ Friends.data の名前） |
| `{pet}` | ペット（手なずけた魔物）の名前。名前を付けていなければ魔物の名前 |
| `{party.2}` | パーティの 2 番目の名前（`{party.1}` は主人公） |
| `{item.ID}` | アイテムの名前（`{item.herb}` → やくそう） |
| `{var.名前}` | 変数の値 |
| `{gold}` | 所持金 |
| `{away.名前}` | `@party leave … keep=名前` で抜けている仲間の名前 |

話者名にも使えます：`{party.2}「行こう！」` `{name.garo}「前は任せろ」`。`{name.ID}` `{item.ID}` の ID の誤りは `--check` で見つかります。

### 制御コード
| 書き方 | 効果 |
|---|---|
| `\w500` | ここで 500 ミリ秒待つ |
| `\c[red]…\c[]` | 文字色（色名：black red green yellow blue magenta cyan white gray と bright_〜） |
| `\s2` / `\s0.5` / `\s1` / `\s0` | 文字送りの速さを 2 倍 / 半分 / 元に戻す / 残りを一気に表示 |
| `\\` | 「\」そのもの |

```
カイ「……\w600まさか、\c[bright_red]あれ\c[]が？」
```

---

## 3. 選択肢

```
@choice
  - 行こう！ → *go
  - やめておく → *stay
```
- `→ *ラベル` を書くと、その選択肢を選んだときにジャンプします。
- 省略すると次の行へ進み、選んだ番号（1 始まり）が `choice` に入ります。
- 行の最後に `@if 条件` を書くと、条件が成り立つときだけその選択肢を出します。`choice` の番号は出なかったものも含めて書いた順で数えます。ひとつも出ないと実行時のエラーです。

```
@choice
  - ガロ → *leave_garo @if party.has(garo)
  - ミア → *leave_mia @if party.has(mia)
  - リナ → *leave_rina @if party.has(rina)
```

```
@choice
  - はい
  - いいえ
@if choice == 2
  村長「そうか……」
  @end
@endif
```

---

## 4. 分岐・変数・フラグ

| 命令 | 説明 |
|---|---|
| `@if 条件` … `@elif 条件` … `@else` … `@endif` | 条件で分ける（入れ子も可） |
| `@goto *L` | ジャンプ |
| `@call *L` … `@return` | 呼び出して戻る（共通の処理に） |
| `@flag set 名前` / `@flag clear 名前` | フラグ（はい／いいえ）を立てる・消す |
| `@var 名前 = 式` / `+= 式` / `-= 式` | 変数（整数） |
| `@wait ミリ秒` / `@keywait` | 待つ / キーを押すまで待つ |

### 条件式
| 書き方 | 値 |
|---|---|
| `flag.名前` / `!flag.名前` | フラグが立っているか（立てていなければ偽） |
| `var.名前` | 変数（未設定は 0） |
| `gold` / `item.ID` | 所持金 / アイテムの数 |
| `party.size` / `party.has(ID)` | パーティの人数 / その仲間がいるか |
| `quest.ID` | 依頼の状態：`none` `active` `done` `failed` |
| `choice` | 直前の選択肢の番号 |
| `chapter` | 章の番号 |
| `map` / `map.dungeon` / `map.dark` / `map.indoor` | 今いるマップの ID / マップの設定 |
| `pet` | 手なずけた魔物の ID（いなければ `""`） |
| `away.名前` | 一時的に抜けている仲間の ID（いなければ `""`） |

演算子：`==` `!=` `<` `<=` `>` `>=`、`and` `or` `not`（`!`）、括弧。
ドットのない名前（`done` など）や `"…"` は文字列です。

```
@if gold >= 100 and !flag.paid
@if quest.q_slime == done
@if party.has(mia) or party.size == 4
@if map == dungeon_b11
```

---

## 5. 状態を変える命令

| 命令 | 説明 |
|---|---|
| `@item add ID [数]` / `@item remove ID [数]` | アイテムを増やす・減らす |
| `@item replace 旧ID 新ID` | 袋の中も、装備中のものも入れ替える（武器の進化など） |
| `@gold add 数` / `@gold remove 数` | 所持金 |
| `@party add ID [lv=avg\|数]` | 仲間を加える（`lv=avg` でパーティの平均 Lv まで上げて加入） |
| `@party remove ID` | 仲間を外す |
| `@party leave ID\|#番号 [keep=名前]` | 一時的に抜ける（`keep=` で能力・装備ごと覚えておく） |
| `@party return 名前` | `keep=` で抜けた仲間を同じ状態で戻す |
| `@equip キャラID アイテムID` | 袋のアイテムを装備する |
| `@skill add\|remove キャラID\|all スキルID` | スキルを覚える・忘れる（職業の習得表とは別） |
| `@stat キャラID 能力 +N\|-N` | 能力値（hp mp atk def mag agi luk）を増減 |
| `@heal all` | 全員の HP・MP・SP・状態異常を回復 |
| `@quest give\|done\|fail ID` | 依頼の状態を直接変える |
| `@chapter 番号 "タイトル"` | 章（右パネルに表示） |
| `@pet 敵ID` / `@pet release` | ペットにする・手放す |
| `@tile x y 文字 [map=ID]` | マップのタイルを書き換える（宝箱を開ける・扉を開く。セーブに残る） |

---

## 6. マップ・人物

| 命令 | 説明 |
|---|---|
| `@map ID x y [dir=up\|down\|left\|right] [transition=fade]` | マップを移る |
| `@npc ID show` / `@npc ID hide` | NPC を出す・消す（マップの `when` より優先） |
| `@npc ID move dx dy` | NPC を歩かせる（壁や木を避けて最短で） |
| `@npc ID face 向き` | NPC の向き |
| `@hero move dx dy` / `@hero face 向き` | 主人公を歩かせる・向きを変える |
| `@aa show ファイル x y [name=名前]` / `@aa hide 名前` | AA をマップ上に重ねて出す・消す |
| `@face ID` / `@face none` | 会話窓の左上に顔 AA を出す（`aa/face_ID.txt` など） |

---

## 7. 施設・戦闘・セーブ

| 命令 | 説明 |
|---|---|
| `@shop ID` | ショップ（Items.data の `[[shop]]`）。閉じると続きへ |
| `@inn 値段` | 宿屋 |
| `@guild` | 冒険者協会（依頼の受注・報告） |
| `@recruit 候補… pick=数 [lv=avg]` | 仲間を選ぶ画面 |
| `@battle group=ID [escape=false] [gameover=…] [lose=*L] [target_only=ID] [members=ID,…] [turns=N]` | イベント戦闘。勝つと次の行へ |
| `@save_point` | セーブ画面を開く |
| `@ending [text="…"]` | エンディング画面 → タイトルへ |

`@battle` の指定：
- `escape=false`：逃げられない
- `gameover=title|retry_from_save|choose`：全滅したときの扱い（省略時は manifest）
- `lose=*L`：負けイベント。全滅しても全滅画面にならず、`*L` へ（倒れた仲間は HP 1 で起き上がる）
- `target_only=ID`：敵がその仲間だけを狙う
- `members=hero,mia`：その仲間だけで戦う（試練など）。ペットも出すなら `pet` を加える
- `turns=3`：3 ターンたつと終わる（`lose=` があればそこへ、なければ続きへ）

---

## 8. マップ側からスクリプトを呼ぶ

| Map.data | いつ |
|---|---|
| `[[map.npc]] talk = "ラベル"` | NPC に話しかけたとき |
| `[[map.event]] trigger = "check"` | そのマスを調べたとき（正面か足元） |
| `[[map.event]] trigger = "touch"` | そのマスを踏んだとき |
| `[[map.event]] trigger = "auto"` | マップに入ったとき（1 回の入場で 1 つだけ） |

イベントに `once = true` で一度きり、`when = "条件"` で条件つきになります。NPC にも `when` が書けます（条件を満たすときだけ出る）。

ほかに、依頼の `on_complete`、アイテムの `use = { effect = "script", label = … }` からもラベルを呼べます。

---

## 9. 検証（--check）で見つかること

- 命令の書き間違い・引数の数や種類・`@if` と `@endif` の対応
- 存在しないラベル・マップ・アイテム・キャラ・敵グループ・NPC・依頼・ショップ・AA ファイル
- マップの外の座標（エラー）、壁の上の座標（警告）
- 条件式の誤り、本文の制御コードの誤り
- どこからも使われていないラベル、一度も立てていないのに参照しているフラグ（警告）
