# コンソールRPG エンジン 基本設計書 v0.2

- 作成日: 2026-10-01（v0.1） / 更新: 2026-10-01（v0.2：実装内容を反映、フィールドメニュー・セーブ／ロードを追記）
- 前提: 要件定義書 v1.1（`requirements.md`）、開発計画（`development_plan.md`）
- 対象: ソフトウェア構成 / 画面設計 / データ仕様 / スクリプト構文 / エフェクト / セーブ形式 / 戦闘計算式 / 検証
- 表記: **【済】** 実装済み　**【一部】** 一部実装　**【未】** 未実装（設計のみ）　**【変更】** 実装で設計を変えた点

---

## 1. ソフトウェア構成

### 1.1 リポジトリ構成（現状）
```
TRPG/
├─ pyproject.toml / README.md / .gitignore
├─ .github/workflows/test.yml   … CI（Windows・Linux で pytest）
├─ docs/                        … 要件・設計・計画・シナリオ本文
├─ src/trpg/
│  ├─ __main__.py      【済】 起動・コマンドライン（--scenario --dev --check --list --term-demo --keylog）
│  ├─ app.py           【済】 シーンスタック、フレームループ、画面サイズ不足時の一時停止、IME 検出、入力破棄
│  ├─ game.py          【済】 パッケージ＋データ＋スクリプトをまとめて読み込み・検証
│  ├─ debuglog.py      【済】 --keylog 用の調査ログ
│  ├─ term/            【済】 端末抽象化
│  │  ├─ width.py         文字幅（unicodedata の East Asian Width）
│  │  ├─ style.py         色・属性・SGR
│  │  ├─ buffer.py        セルバッファ（全角の分断補正、枠、塗り、AA、カーソル位置）
│  │  ├─ screen.py        ダブルバッファ・差分出力・リサイズ検知・入力カーソル表示
│  │  ├─ input_win.py     Windows：ReadConsoleInputW で入力レコードを直接読む【変更】
│  │  ├─ input_posix.py   Linux：termios cbreak＋エスケープシーケンス解析
│  │  ├─ keys.py          キーイベント・アクション・キー割当（全角英数字も受理）
│  │  └─ terminal.py      端末の初期化と後始末（VT 有効化・UTF-8 化）
│  ├─ ui/widgets.py    【済】 会話窓・選択肢窓
│  ├─ scenes/
│  │  ├─ title.py         【済】 タイトル・名前入力・シナリオ選択
│  │  ├─ field.py         【済】 フィールド（移動・NPC・ワープ・イベント・エンカウント・スクリプト実行）
│  │  ├─ facility.py      【済】 ショップ・宿屋・冒険者協会・仲間選択（フィールドに重ねる画面）
│  │  ├─ battle.py        【済】 戦闘画面
│  │  ├─ gameover.py      【済】 全滅画面
│  │  ├─ term_demo.py     【済】 描画・入力デモ
│  │  ├─ menu.py          【済】 フィールドメニュー（どうぐ・スキル・そうび・つよさ・いらい・システム）
│  │  └─ saveload.py      【済】 セーブ／ロード画面（3 スロット）
│  ├─ package/         【済】 zip・フォルダ読込、安全チェック、manifest 検証、パッケージ探索
│  ├─ data/            【済】 .data（TOML）の読込・型検証・相互参照チェック、データクラス
│  ├─ script/          【済】 条件式（expr）・構文解析（parser）・実行（vm）・検証（lint）
│  ├─ effects/         【一部】 画面エフェクト（11 章）
│  ├─ battle/core.py   【済】 戦闘の進行と計算（画面に依存しない）
│  ├─ world/
│  │  ├─ state.py         【済】 ゲーム状態（パーティ・所持品・フラグ・位置・依頼・継続エフェクト）
│  │  ├─ quests.py        【済】 依頼の受注・進み具合・達成
│  │  ├─ growth.py        【済】 経験値・レベルアップ・習得スキル
│  │  └─ items.py         【済】 フィールドでのアイテム・スキルの使用
│  ├─ save/            【済】 直列化・暗号化・スロット管理
│  └─ i18n/            【未】 UI 文言（ja / en）
├─ tools/              【未】 aa_convert / map_editor / pack（lint は本体の --check に統合【変更】）
├─ scenarios/FirstQuest/  サンプルシナリオ（展開形式）
└─ tests/              【済】 pytest（端末なしで画面にキーを送る通しプレイを含む）
```

### 1.2 コマンド
| コマンド | 状態 | 内容 |
|---|---|---|
| `python -m trpg` | 【済】 | 起動フォルダと `scenarios/` を探索。1 つならそのまま、複数なら選択画面 |
| `python -m trpg --scenario PATH` | 【済】 | 指定パッケージ（zip / フォルダ）で起動 |
| `python -m trpg --dev` | 【済】 | 開発モード（右パネルにマップ ID・座標・向き） |
| `python -m trpg --check PATH` | 【済】 | データとスクリプトを検証し、ファイル名・行番号つきで表示（旧 T-04） |
| `python -m trpg --list` | 【済】 | 見つかったパッケージの一覧 |
| `python -m trpg --term-demo` | 【済】 | 描画・入力デモ |
| `python -m trpg --keylog` | 【済】 | 受け取ったキー・画面状態・例外を `trpg_debug.log` に記録 |
| `--ambiguous-width 1/2` `--no-color` `--fps N` | 【済】 | 表示オプション |
| `python -m tools.aa_convert` ほか | 【未】 | 8 章のツール |

- 開発モードでの F5 スクリプト再読込は【未】。
- シナリオにエラーがあるとゲームは起動せず、端末を初期化する前に検証結果を表示する。

### 1.3 シーン遷移（現状）
```
[起動] → [シナリオ選択]* → [タイトル] ─ はじめから → [名前入力]** → [フィールド（*start 実行）]
                                    └ つづきから → [ロード画面] → [フィールド（*on_load 実行）]
[フィールド] ⇄ [メニュー：どうぐ / スキル / そうび / つよさ / いらい / システム（セーブ・タイトル・おわる）]
             ⇄ [重ね画面：ショップ / 宿屋 / 冒険者協会 / 仲間選択]
             ⇄ [戦闘] ─ 勝利・逃走 → フィールド
                       └ 全滅 → lose= があれば負けイベントへ、なければ [全滅画面] → タイトル
*  候補が複数のときのみ   ** 主人公の name_input = true のとき
```
- 重ね画面（Overlay）と戦闘画面はシーンスタックに積む。スクリプトの命令から開いた場合、閉じるとスクリプトの続きを実行する。
- スクリプト VM はフィールドが持ち、`@map` `@battle` `@shop` などの命令は VM からフィールド（Host）に渡される。
- 1 フレームにまとめて届いたキーは、途中で画面が切り替わったら残りを捨てる（押しためたキーで会話が飛ばされないように）。

---

## 2. 画面設計（最小 100×30）

### 2.1 フィールド画面【済】
```
┌─ ハジマリ村 ────────────────────────────────────┐┌─ パーティ ──────────────────────┐
│ 木木木木木木木木木木木木木木．木木木木…          ││ ユウ      勇者    Lv  2         │
│ 木．．家家家．．．．．．．．．．…（マップ）       ││  HP  38/ 38  MP   7/  7         │
│                                                ││                                 │
│                                                ││ G       54                      │
│                                                ││ 第1章 出会いと旅立ち            │
│                                                ││ TIME 00:12:40                   │
└────────────────────────────────────────────────┘└─────────────────────────────────┘
┌───────────────────────────────────────────────────────────────────────────────────┐
│ 母「おかえり。森は楽しかった？」                                          ▼      │
└───────────────────────────────────────────────────────────────────────────────────┘
```
- 右パネル幅 34 桁、会話窓 5 行。残りをマップ表示に充てる。マップが表示領域より小さいときは中央寄せ。
- タイルは常に 2 セル幅。主人公は `＠`。NPC は Map.data の glyph（全角 1 文字）。
- `dark = true` のマップは主人公の周囲 3 マスだけ表示。
- 会話のないときは操作説明を表示。開発モードでは右パネルにマップ ID・座標・向き。
- 選択肢窓は会話窓の右上に重ねる。

### 2.2 施設画面（重ね画面）【済】【変更】
- フィールドの会話窓より上の全面（右パネルも含む）に重ねる：左にリスト、右上に所持金、右下に説明。
- ショップ：かう／うる。説明欄に装備した場合の能力変化（例「ユウ：攻撃 13→18」）と装備できない仲間を表示。購入後「いま装備しますか？」。
- 冒険者協会：依頼を受ける／報告する／受けている依頼。説明欄に目標（進み具合つき）と報酬。
- 仲間選択：候補のリストと、職業・Lv・能力・紹介文。
- 宿屋：全員の HP・MP が満タンで状態異常もないときは泊まれない（「皆さんお元気そうですね」と断り、お金も取らない）。

### 2.3 戦闘画面【済】
```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         ▼                                                    │
│            .---.         .---.         .---.        （敵の AA を横並び）     │
│           /  o o\       /  o o\       /  o o\                                │
│          スライムＡ    スライムＢ    スライムＣ                              │
└──────────────────────────────────────────────────────────────────────────────┘
┌──────────────────┐┌──────────────────┐┌──────────────────┐┌──────────────────┐
│▶ユウ             ││ミア              ││                  ││                  │
│HP   7/30         ││HP  24/24         ││                  ││                  │
│MP   5/5   ど     ││MP  22/22         ││                  ││                  │
└──────────────────┘└──────────────────┘└──────────────────┘└──────────────────┘
┌─ ユウ ─────────────┐┌──────────────────────────────────────────────────────────┐
│ ▶ たたかう         ││ スライムが 3 匹あらわれた！                              │
│   スキル           ││                                                          │
│   どうぐ           ││                                                          │
│   ぼうぎょ         ││                                                          │
│   にげる           ││                                                          │
└────────────────────┘└──────────────────────────────────────────────────────────┘
```
- 上：敵表示（高さ ＝ 画面高 − 5 − 8）。名前に重複があれば全角の Ａ・Ｂ… を付ける。狙っている敵の上に ▼。
- 敵の AA が入りきらないときは `aa/<名前>_s.txt`（縮小版）を探し、それもなければ名前だけ表示。
- 中：味方 4 枠（各 5 行）。HP が半分以下で黄、1/4 以下で赤。状態異常は頭文字（どく→「ど」）。
- 下：左にコマンド（幅 22）、右にメッセージ。メッセージ再生中は全幅。
- 攻撃を受けた敵は点滅、味方は枠が赤く点滅し画面が左右に揺れる。開始時に白く 2 回発光。
- メッセージは 1 行ごとに 0.55 秒で自動送り（決定キーで早送り）。最後は ▽ でキー待ち。

### 2.4 フィールドメニュー【済】
- Esc / X / M で開く。会話窓より上を消して、左にメニュー、右上に所持金、右にパーティ（各段階ではリストと説明）。
- どうぐ：つかう（対象を選ぶ）／すてる（だいじなものは捨てられない）。効果がなければ消費しない。effect = "script" のアイテムはメニューを閉じてそのラベルを実行。
- スキル：仲間を選び、フィールドで使える回復スキルを使う（戦闘用スキルは選べない表示）。
- そうび：仲間 → 部位 → 袋の装備品（その職業が装備できるもの）／はずす。説明欄に能力の変化（上がる緑・下がる赤）。
- つよさ：Lv・経験値と次の Lv まで・HP/MP・能力（装備による増減）・装備・スキル・状態。←→ で仲間を切替。
- いらい：受けている依頼と進み具合。達成済みは「協会に報告しよう」。
- システム：セーブ（`save = "save_point_only"` のシナリオでは不可）／タイトルにもどる／ゲームをおわる（確認あり）。

### 2.5 全滅画面【済】
- 「全滅してしまった……」を 1.2 秒かけて表示し、gameover 設定に応じた選択肢を出す（4.9）。

### 2.6 名前入力画面【済】
- 入力位置に端末のカーソルを表示する（日本語入力の変換中の文字がそこに出る）【変更】。
- 「日本語は Enter で変換を確定してから、もう一度 Enter」「決定したら［半角/全角］で日本語入力をオフに」を案内。

### 2.7 サイズ不足画面【済】
- 「画面が小さすぎます」と現在・必要サイズを表示し、ゲームを一時停止（キーも無視）。

### 2.8 IME オンの通知【済】【変更】
- 文字入力以外の画面で全角の英数字・かな・漢字が届いたら、画面上部に 4 秒間「日本語入力（IME）がオンです。［半角/全角］キーでオフにしてください」。
- 全角の英数字（ｗ・８・全角空白など）は半角に正規化して操作として受け付ける。

---

## 3. データ共通仕様【済】

- 文字コード UTF-8（BOM 可）、改行 LF/CRLF。Shift_JIS は読み込み時にエラー（UTF-8 で保存し直すよう案内）。
- `.data` / `manifest.toml` は TOML 1.0。
- ID は `^[a-z][a-z0-9_]*$`。種別（敵・アイテム…）ごとに一意。重複はエラー。
- 未知の項目は警告（綴り間違いの検出）。型・範囲・選択肢の誤りはエラー。読み込みは止めずにすべての問題を集める。
- エラー表示にはファイル名と行番号（その項目の `id = "…"` の行、なければ `[[…]]` の行）。
- パスは zip ルート（manifest.toml のある階層）からの相対パス、区切りは `/`。
- 多言語の上書き（`name_en` など）は【未】。

---

## 4. manifest.toml【済】
```toml
[package]
id = "firstquest"            # 必須。セーブの紐づけに使用
title = "FirstQuest"         # 必須
version = "0.1.0"
author = "bbk"
engine = ">=1.0"             # 対応エンジンのデータ形式版（>= <= == > < と , 区切り）
languages = ["ja"]

[title_screen]
aa = "aa/title.txt"
effect = "starfall"          # 【未】タイトル背景エフェクトは未表示

[rules]
gameover = "choose"          # retry_from_save | title | choose
save = "anywhere"            # anywhere | save_point_only（セーブ実装時に有効）
party_max = 4                # 1〜4
start_label = "start"

[start]
party = ["hero"]             # 必須（1 人以上、party_max 以下）
gold = 0
items = []
```
- データ形式版はエンジン側 `FORMAT_VERSION = (1, 0)`。

---

## 5. Friends.data（職業・キャラクター）【済】
```toml
[[job]]
id = "warrior"
name = "戦士"
growth = { hp = 9, mp = 0, atk = 3, def = 3, mag = 0, agi = 1, luk = 1 }   # Lv アップ時の平均上昇量
equip = ["sword", "axe", "light_armor", "heavy_armor", "shield", "accessory"]  # 装備できる category
skills = [ { lv = 3, skill = "power_slash" } ]

[[character]]
id = "hero"
name = "ユウ"
name_input = true            # ニューゲーム時に名前入力
job = "hero"
lv = 1
stats = { hp = 30, mp = 5, atk = 8, def = 6, mag = 3, agi = 6, luk = 5 }   # hp 必須
equip = { armor = "cloth" }  # weapon / armor / shield / accessory
face = "aa/face_hero.txt"    # 【未】顔 AA は未表示
recruit_text = "…"           # 仲間選択画面の紹介文
```
- 職業の `equip` が空なら何でも装備できる。装飾品も category（例 `accessory`）で判定する【変更】。
- 途中加入のキャラは、その Lv に見合う累計経験値から始まる（14 章の式）。
- `@party add` の `lv=avg`（平均 Lv に合わせる）は【未】。

---

## 6. Enemy.data（敵・グループ・出現表）【済】
```toml
[[enemy]]
id = "mole"
name = "ハタケモグラ"
aa = "aa/mole.txt"                # 必須。縮小版は aa/mole_s.txt（任意）
stats = { hp = 40, atk = 12, def = 6, agi = 5, luk = 3 }   # hp 必須、他は省略時 0
exp = 18
gold = 12
weak = ["fire"]                   # 1.5 倍
resist = ["earth"]                # 0.5 倍（属性名は 7 章の 5 種）
immune_status = []
drops = [ { item = "herb", rate = 0.2 } ]
tameable = true
tame_rate = 0.15
ai = "pattern"                    # attack_only | random | pattern
[[enemy.actions]]
skill = "attack"                  # attack / defend は組み込み。それ以外は Items.data の [[skill]]
weight = 3
target = "random"                 # random | lowest_hp | all | id:キャラID
[[enemy.actions]]
skill = "dig_attack"
when = "self.hp_rate < 0.5"       # 条件式（self.hp_rate / self.hp / self.mp / self.turn ＋ 通常の名前空間）

[[group]]
id = "mole_pack"
members = ["mole", "mole"]        # 6 体以上は警告

[[encounter]]
id = "forest_1"
steps = [12, 24]                  # 何歩ごとに抽選（最小・最大）
table = [ { group = "slime_2", weight = 5 }, { group = "bat_1", weight = 2 } ]
```
- `ai = "random" / "pattern"` で actions が無いとエラー。MP が足りない行動・条件を満たさない行動は候補から外し、候補がなければ通常攻撃。

---

## 7. Items.data（アイテム・スキル・状態異常・ショップ）【済】
```toml
[[item]]
id = "herb"
name = "やくそう"
type = "consumable"               # consumable | equipment | key
price = 8                         # 0 = 売れない
desc = "HP を 30 回復する。"
use = { field = true, battle = true, target = "ally_one", effect = "heal", power = 30 }
#   effect: heal | heal_mp | cure（status を治す）| revive（power % で復活）| script（label を実行）| skill（skill を発動）
#   consume: 使うと減るか（既定 consumable なら true）

[[item]]
id = "rusty_sword"
type = "equipment"
slot = "weapon"                   # weapon | armor | shield | accessory（装備品は必須）
category = "sword"                # 職業の equip と照合
stats = { atk = 5 }

[[skill]]
id = "fire"
name = "ファイア"
mp = 4
target = "enemy_one"              # self | ally_one | ally_all | enemy_one | enemy_all
kind = "magic"                    # physical | magic | heal | buff | debuff | status | tame | escape
element = "fire"                  # fire | ice | thunder | holy | dark
power = 20
status = ""                       # 付与する状態異常
status_rate = 0.0                 # status 指定時の既定は 1.0
anim = "flash:red"                # 【未】戦闘中の演出

[[status]]
id = "poison"
name = "どく"
turns = [3, 5]
tick = { hp_rate = -0.08 }        # ターン終了時（負ならダメージ）
field = true                      # 戦闘後も残る
skip_turn = false                 # true なら行動できない（麻痺・眠り）

[[shop]]
id = "town_weapon"
name = "ベルンの武具屋"
goods = ["copper_sword", "leather_armor", "wood_shield"]
sell_rate = 0.5
```
- `attack` `defend` はエンジン組み込みのスキル名で、データでは使えない。
- フィールドでのアイテム使用はメニューの「どうぐ」から【済】（`world/items.py`）。

---

## 8. Map.data【済】
```toml
[[tileset]]
id = "default"
[tileset.tiles]
"#" = { glyph = "＃", pass = false, color = "gray",   name = "壁" }
"." = { glyph = "．", pass = true,  color = "green",  name = "地面" }
"=" = { glyph = "：", pass = true,  color = "yellow", name = "道" }

[[map]]
id = "forest_1"
name = "囁きの森"                 # {hero} などの置き換え可
tileset = "default"
encounter = "forest_1"           # 省略時エンカウントなし
dark = false
indoor = false                    # true：屋内。雨・雪を表示しない（天気の状態は保ったまま）
rows = [ "TTTTT…", … ]            # 1 文字 = 1 タイル。全行同じ長さ
bgm = ""                          # 予約（音なし）

[[map.event]]
x = 20
y = 1
trigger = "check"                 # touch（踏む）| check（調べる：正面か足元）| auto（マップに入ったとき）
label = "ch1_find_sword"
once = true
when = "flag.lost_friend"

[[map.warp]]
x = 15
y = 15
to = "village_lito"
tx = 15
ty = 1
dir = "up"                        # 移動後の向き（任意）

[[map.npc]]
id = "kai"                        # マップ内で一意
glyph = "友"                      # 表示幅 2
color = "cyan"
x = 16
y = 13
move = "fixed"                    # fixed | random（初期位置から ±3 マス）| route【未】
talk = "ch1_kai_talk"
when = "!flag.ch1_forest_done"    # 条件を満たすときだけ出現（@npc show/hide が優先）
```
- タイルの glyph は表示幅 2。全角文字（East Asian Width が F/W）を使う。曖昧幅の文字は警告（端末でずれるため）。
- ワープ先が通行できないタイル、NPC が壁の上、などは警告。マップ外の座標はエラー。

---

## 9. Quests.data【済】
```toml
[[quest]]
id = "q_herb"
name = "やくそう集め"
giver = "guild"
rank = "F"
desc = "…"
goal = { type = "deliver", item = "herb", count = 3 }   # deliver | defeat（group=敵グループ or 敵 ID）| reach（map）| flag（flag）
reward = { gold = 30, exp = 0, items = [] }
repeatable = true
when = "flag.guild_registered"   # 掲示板に出る条件【変更：追加】
on_complete = "ch1_quest_done"   # 達成報告のあとに実行するラベル
```
- 討伐数は戦闘勝利時に数える（敵グループ指定なら 1 戦 1 回、敵 ID 指定なら倒した数）。reach はそのマップに入った時点で達成。
- 納品物は報告時に渡す。経験値は生存メンバーで等分。

---

## 10. scenario.sco 構文【済】

### 10.1 基本ルール
- 1 行 1 文。インデントは意味を持たない。`#` で始まる行はコメント。
- `@include "ch2.sco"` で分割ファイルを読み込める（循環はエラー）。

### 10.2 文の種類
| 形式 | 意味 |
|---|---|
| `*ラベル` | ジャンプ先・イベント入口（重複はエラー） |
| `話者「本文」` | 台詞。連続する台詞は 1 つの会話窓にまとめ、窓の行数を超えたらページ送り |
| 地の文 | 話者なしの本文 |
| 空行 | 改ページ |
| `@命令 引数…` | 命令（位置引数と `名前=値`。値は数値・識別子・`"文字列"`） |

- 本文中の置き換え【済】：`{hero}` `{party.2}` `{var.名前}` `{item.ID}`（アイテム名）`{gold}`。
- 本文中の制御コード `\w500` `\c[red]…\c[]` `\s2` は【未】。

### 10.3 条件式【済】
| 名前空間 | 内容 |
|---|---|
| `flag.名前` / `!flag.名前` | 真偽（未定義は false） |
| `var.名前` | 整数（未定義は 0） |
| `gold` / `item.ID` | 所持金 / 所持数 |
| `party.size` / `party.has(ID)` | パーティ |
| `quest.ID` | none / active / done / failed |
| `choice` | 直前の選択肢の番号（1 始まり） |
| `chapter` | 章番号 |
| `self.hp_rate` など | 敵の行動条件でのみ |
- 演算子：`== != < <= > >=` `and or not !` 括弧。ドットのない未知の名前（`done` など）は文字列。

### 10.4 命令一覧
| 命令 | 状態 | 説明 |
|---|---|---|
| `@goto *L` `@call *L` `@return` `@end` | 【済】 | 制御 |
| `@if 式` `@elif` `@else` `@endif` | 【済】 | 分岐（構文解析時にジャンプへ展開。対応不一致はエラー） |
| `@choice` ＋ `- 表示 → *L` | 【済】 | `→` 省略時は `choice` に番号のみ |
| `@wait ms` `@keywait` | 【済】 | 待ち |
| `@flag set/clear 名前` `@var 名前 = 式`（`+=` `-=`） | 【済】 | 状態 |
| `@item add/remove ID [数]` `@gold add/remove 数` | 【済】 | 所持品・所持金 |
| `@party add/remove ID` | 【済】 | 加入・離脱（`lv=avg` は【未】） |
| `@equip キャラID アイテムID` | 【済】【変更：追加】 | 袋のアイテムを装備（元の装備は袋へ） |
| `@heal all` | 【済】 | 全員の HP・MP・状態異常を回復 |
| `@quest give/done/fail ID` | 【済】 | 依頼の状態を直接変更 |
| `@chapter n "タイトル"` | 【済】 | 章（右パネルに表示） |
| `@map ID x y [dir=] [transition=fade]` | 【済】 | マップ移動 |
| `@npc ID show/hide/move dx dy/face 向き` `@hero move dx dy/face 向き` | 【済】 | 演出移動（1 マス 0.15 秒）。目的地（現在地＋dx,dy）まで木・壁・ほかの人を避けた最短経路で歩く（NPC は主人公のマスも避ける）。目的地が通れないか着けないときは横→縦にまっすぐ進む |
| `@aa show ファイル x y [name=]` `@aa hide 名前` | 【済】 | AA を重ねて表示 |
| `@effect 名前 引数… [wait=false]` | 【一部】 | 11 章 |
| `@shop ID` `@inn 価格` `@guild` `@recruit 候補… pick=n` | 【済】 | 施設画面（閉じると続きを実行） |
| `@battle group=ID [escape=false] [gameover=] [target_only=ID] [lose=*L]` | 【済】 | イベント戦闘 |
| `@face ID` | 【未】 | 何もしない |
| `@save_point` | 【済】 | セーブ画面を開く（閉じるとスクリプトの続きを実行） |
| `@ending` | 【一部】 | 「おわり」を表示してタイトルへ（スタッフロールは【未】） |

### 10.5 予約ラベル
| ラベル | 状態 |
|---|---|
| `*start` | 【済】ニューゲーム（manifest の start_label で変更可） |
| `*gameover` | 【済】全滅時（lose= なし）に全滅画面の前に実行 |
| `*on_load` | 【済】ロード直後に実行（ロード時はマップの auto イベントは起こさない） |

---

## 11. エフェクト
| 名前 | 状態 | 引数 |
|---|---|---|
| `flash` | 【済】 | `色` `count=1` `interval=80` |
| `fade_out` / `fade_in` | 【済】 | `ms`（fade_out 後は fade_in まで黒のまま。セーブ対象） |
| `shake` | 【済】 | `h|v` `power(1〜3)` `ms` |
| `tint` | 【済】 | `night|sepia|red|none`（継続・セーブ対象）。`invert` は【未】 |
| `typewriter` | 【済】 | `"文字"` `speed=80`。表示後「Enter / Z で続ける」でキー待ち |
| `wait` | 【済】 | `ms` |
| `rain` / `snow` | 【済】【変更】 | `on|off` `density=1〜3`。継続・セーブ対象。全角の ／・＊ をタイルの区切りに合わせて描く |
| `starfall` | 【済】 | `count=8` `ms=2000`。右上から左下へ流れ星 |
| `move` `wipe` `blink` `aa_show` `aa_hide` `scroll_text` | 【未】 | 呼ばれても何もしない |

- 描画順：マップ → 天気 → 色調 → 暗転 → 会話窓 → 発光・中央文字・流れ星。
- 色が使えない端末（`--no-color`）では色指定を無視する。

---

## 12. AA ファイル形式【一部】
- `*.txt`（UTF-8）。1 行目が `;;` で始まればメタ行として読み飛ばす（配置基準などの解釈は【未】）。
- 戦闘では半角空白を透過として重ねる。
- `*.color`（1 文字ずつの色）は【未】。

---

## 13. セーブ形式【済】
| 項目 | 内容 |
|---|---|
| 場所 | `<セーブフォルダ>/<package.id>/slot1.sav`〜`slot3.sav`。セーブフォルダは環境変数 `TRPG_SAVE_DIR`、なければ起動フォルダの `saves/` |
| 構造 | `"TRPGSAV"`（7 バイト）＋ 形式版（1 バイト、現在 1）＋ nonce（12 バイト）＋ 暗号文（認証タグ 16 バイト込み） |
| 暗号 | AES-256-GCM（`cryptography`）。鍵 ＝ HKDF-SHA256(エンジン埋め込みの秘密値, salt = package.id, info = "trpg-save-v1")。AAD ＝ package.id |
| 平文 | JSON を zlib 圧縮。`{package: {id, version}, saved_at, summary: {hero, lv, chapter, chapter_title, map_name, playtime}, state: {...}}` |
| 書き込み | 一時ファイルに書いてから置き換える（途中で落ちても元のセーブを壊さない） |
| 拒否 | 改ざん・別シナリオ →「セーブデータが壊れているか、別のシナリオのものです」。形式違い・ゴミファイルも拒否。スロット一覧には「読み込めません」と表示 |
| 互換 | state の項目が欠けていても既定値で読む（古いセーブとの互換）。シナリオの version は AAD に含めない（シナリオ更新後も読める） |

- 保存対象：`world/state.py` の GameState すべて（パーティ・所持金・所持品・フラグ・変数・依頼と進み具合・章・位置と向き・一度きりイベント・NPC の状態・継続エフェクト・プレイ時間・ペット）。
- セーブはフィールド操作中（メニュー）か `@save_point` の時点。VM の状態は保存しない（`@save_point` 以降のスクリプトはロード時には再実行されない）。
- ロード：タイトルの「つづきから」（セーブがあれば既定で選択）、全滅画面の「セーブからやり直す」（最後にセーブしたスロット）。

## 14. 戦闘・成長の計算式【済】（実装値）

| 項目 | 式 |
|---|---|
| 行動順 | `agi × 乱数(0.8〜1.2)` の降順。防御は順番に関係なくそのターンの最初から有効 |
| 逃走 | 行動順の前に判定。成功率 `0.5 + (味方平均agi − 敵平均agi)/100`（0.2〜0.95）。失敗すると味方全員そのターン行動なし。`escape=false` なら「逃げられない」 |
| 物理ダメージ | `max(1, (atk + 技の威力 − 相手def/2) × 乱数(0.9〜1.1))`、防御中は × 0.5 |
| 会心 | 通常攻撃のみ。確率 `max(luk/256, 1/32)`。防御力を無視して `atk × 1.5` |
| 回避 | 物理のみ。`(相手agi − 自分agi)/200`（0〜20%） |
| 魔法ダメージ | `max(1, (威力 + mag×0.8 − 相手mag×0.3) × 属性倍率 × 乱数(0.9〜1.1))`、防御中は × 0.5。弱点 1.5・耐性 0.5 |
| 回復 | `威力 + mag × 0.5` |
| 状態異常 | 付与率 status_rate。かかったら turns の範囲で残りターンを決め、ターン終了時に tick を適用し 1 減らす |
| 強化・弱体（buff/debuff） | 攻撃 ＋威力（既定 5）／守備 −威力 を 3 ターン（簡易版） |
| テイム | `tame_rate × (1 + (1 − 相手HP率))`（最大 0.95）。成功で戦闘から外れ、GameState.pet に記録（随伴戦闘は【未】） |
| 経験値 | 倒した敵の合計を生存メンバーで等分 |
| レベルアップ | 次の Lv に必要な累計経験値 `round(10 × lv^2.2)`。上昇量は職業の growth ＋ {−1, 0, 0, +1} |
| フィールドの毒 | 1 歩ごとに HP −1（1 未満にはならない）【変更：追加】 |
| 負けイベント | `lose=` 指定時、全滅しても倒れた仲間を HP 1 にしてそのラベルへ |

- 乱数は戦闘ごとに `random.Random` を作る（グローバルの `random.seed()` で再現可能。テストで使用）。

---

## 15. 検証（--check）【済】
| 種類 | 内容 |
|---|---|
| パッケージ | manifest の必須項目・選択肢・対応エンジン版、必須ファイル、UTF-8 |
| データ | 型・範囲・選択肢、ID の書式と重複、未知の項目（警告）、未定義 ID の参照（職業・装備・ドロップ・スキル・状態異常・敵・グループ・出現表・マップ・タイルセット・ショップ品目・依頼の目標と報酬）、装備欄と slot の不一致、AA ファイルの欠落、マップ行の長さ、タイルセットにない記号、glyph の表示幅（曖昧幅は警告）、イベント・ワープ・NPC のマップ外座標、壁の上の NPC・ワープ先（警告） |
| スクリプト | 構文（未知の命令・引数の数と種類・キーワード・@if/@endif の対応・@include）、ラベルの重複と未定義、開始ラベル、条件式の誤り（when を含む）、@map の座標（マップ外はエラー、壁は警告）、存在しないアイテム・キャラ・依頼・ショップ・敵グループ・NPC・AA、@equip に装備品以外、使われていないラベル（警告）、一度も立てないのに参照されるフラグ（警告）、データ側からのラベル参照（talk・event・on_complete・アイテムの script） |

---

## 16. テスト【済】
- `python -m pytest`（現在 129 件）。セーブはテストごとの一時フォルダに書く。端末を使わずにシーンへキーを送り、画面バッファを文字列で確かめる。
- `tests/test_chapter1.py`：1 章を最初から「第1章 完」まで自動プレイ（戦闘は自動で戦う）。30 種の乱数で完走を確認済み。
- Windows 実機の確認は手動（キー入力の調査は `--keylog`）。
