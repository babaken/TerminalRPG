# エフェクト（@effect）

`@effect 名前 引数…` で画面の演出を入れます。たいていは終わるまで待ってから次の行へ進みます。
`move` `aa_show` `aa_hide` は `wait=false` を付けると待たずに進みます（演出と会話を同時に）。

| 名前 | 書き方の例 | 効果 |
|---|---|---|
| `flash` | `@effect flash white count=2 interval=80` | 画面が光る（色・回数・間隔） |
| `fade_out` / `fade_in` | `@effect fade_out 600` / `@effect fade_in 600` | 暗転・明転（ミリ秒）。fade_out のあとは fade_in まで黒のまま |
| `wipe` | `@effect wipe right 400` / `@effect wipe out left` | 境目が進む場面転換（`out` で覆う） |
| `shake` | `@effect shake h 3 600` | 画面を揺らす（h 横 / v 縦、強さ 1〜3、ミリ秒） |
| `tint` | `@effect tint night` | 色調：`night` `sepia` `red` `invert` `none`（戻す）。セーブに残る |
| `rain` / `snow` | `@effect rain on density=2` / `@effect snow off` | 雨・雪（`indoor = true` のマップでは降らない）。セーブに残る |
| `starfall` | `@effect starfall count=10 ms=2000` | 流れ星 |
| `typewriter` | `@effect typewriter "第1章　はじまり"` | 画面中央に 1 文字ずつ表示 → キー待ち |
| `wait` | `@effect wait 500` | 待つ |
| `blink` | `@effect blink hero count=4 interval=150` | 点滅（NPC ID・`hero`・AA の名前） |
| `move` | `@effect move kai 0 -6 ms=150` | NPC・主人公を歩かせる／AA をなめらかに動かす |
| `aa_show` | `@effect aa_show aa/dragon.txt 10 2 name=dragon from=right` | AA を出す（`from=` で画面の外から滑り込む） |
| `aa_hide` | `@effect aa_hide dragon to=left` | AA を消す（`to=` で外へ滑り出る） |
| `scroll_text` | `@effect scroll_text file=credits.txt speed=2` | スタッフロール（下から上へ流れる。決定キーで飛ばす） |

## 組み合わせの例

章のはじまり：
```
@effect fade_out 10
@effect typewriter "第2章　影を追う者たち"
@map guild 10 5 dir=up
@effect fade_in 600
```

ボスの登場：
```
@effect shake v 3 800
@effect flash red count=3
@effect tint red
魔王「――よくぞ来た」
```

回想：
```
@effect tint sepia
長老「三百年前……」
@effect tint none
```

エンディング：
```
@effect starfall count=10
@effect fade_out 1500
@effect typewriter "HelloQuest　―完―"
@effect scroll_text file=credits.txt speed=2
@ending
```

## スキルの演出（Items.data の anim）

スキルに `anim = "flash:red,shake:2"` のように書くと、使ったときに演出が入ります。
`flash:色` `shake:強さ` `blink` を `,` でつなげます。
