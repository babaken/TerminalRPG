# ============================================================
#  FirstQuest+  第3章　器
#  元テキスト: docs/scenario/FirstQuestPlus_story.md（第3章）
#  3-1 調査へ 〜 3-4 最強の敵の話。2章のあと、協会長ドルガンに話しかけると始まる
#  フラグ: p3_started → p3_revealed（正体） → p3_split（仲間の離脱） → p3_home_open → p_family_accept
#          → p3_tera_done → p3_mem1〜3（記憶の場所） → p3_returned → p3_done
# ============================================================

# ------------------------------------------------------------
#  3-1 調査へ
# ------------------------------------------------------------
*p3_start
@chapter 3 "器"
@effect fade_out 600
@effect typewriter "第3章　器"
@map guild_bern 13 2 dir=right
@effect fade_in 600
協会長ドルガン「グレイの研究室から、これが見つかった」
ドルガンは、焼け焦げた紙の束を机に置いた。
協会長ドルガン「『器計画』……赤子に魔の核を植え、王の新しい体とする」
協会長ドルガン「十五年前、成功例が一体だけあったと書いてある」
協会長ドルガン「その成功例は、北の森で行方不明になったそうだ」
@if party.has(garo)
  ガロ「北の森って……」
@elif party.has(mia)
  ミア「北の森って……」
@elif party.has(rina)
  リナ「北の森、ですか……」
@endif
……{hero}の生まれた村は、北の森のそばにある。
協会長ドルガン「……黒岩の洞穴の最深部を調べろ。全部、そこにあるはずだ」
協会長ドルガン「B11F の東の壁が崩れて、奥へ続く道が見つかった。……生きて戻れ」
@quest give q_blackrock_deep
@flag set p3_started
@tile 26 5 > map=dungeon_b11
指名依頼「黒岩の洞穴の最深部」を受けた！
@end

# ------------------------------------------------------------
#  黒岩の洞穴 B12F〜B15F
# ------------------------------------------------------------
*p3_b12_note
壁ぎわの岩棚に、紙の束が押し込まれている。
グレイの字だ。
「被験体は全て失敗。核が肉体を拒む」
「やはり、王が選んだ器でなければ」
「――十五年前の器は、生きている。王の声が、それを告げている」
@if party.has(mia)
  ミア「器……。人間を、入れ物みたいに……」
@elif party.has(garo)
  ガロ「人を入れ物扱いか。……胸くその悪い話だ」
@elif party.has(rina)
  リナ「人を、入れ物のように……。なんて酷い……」
@endif
@flag set p3_note
@end

*p3_b13_child
小さな影が、泉のそばでうずくまっている。
……子供だ。腕の半分が、黒い鱗に覆われている。
子供「……こないで……」
子供「ぼく……うつわ……じゃ……なかった……」
@choice
  - 剣を構える
  - そっと道をあける
@flag set p3_child_met
@if choice == 1
  子供は、牙をむいて飛びかかってきた！
  @battle group=nari_child escape=false
  倒れた子供は、小さな人の姿に戻った。……もう動かない。
  {hero}は、しばらくその場を動けなかった。
@else
  {hero}は剣を下ろし、ゆっくりと道をあけた。
  子供は{hero}の顔をじっと見つめ――
  子供「……おにいちゃん……おなじ……におい……」
  そう言い残して、暗がりへ走り去っていった。
  @flag set p_child_spared
@endif
@end

*p3_b14_door
@if flag.p3_door_open
  @end
@endif
行く手を、巨大な扉がふさいでいる。
扉には、錆びた剣と同じ紋章――目を閉じた人の顔が刻まれている。
@effect blink hero count=4 interval=150
{hero}が近づくと、扉の顔が、ゆっくりと目を開いた。
@effect flash black
重い音を立てて、扉がひとりでに開いた。
……まるで、帰りを待っていたかのように。
@flag set p3_door_open
@tile 20 1 > map=dungeon_b14
@end

*p3_b14_mural
岩壁一面に、大きな壁画が描かれている。
B10F で見た壁画の、続きだ。
魔物が、赤子に剣を握らせている。
赤子の額には、剣と同じ紋章――目を閉じた人の顔。
@effect blink hero count=3 interval=200
……{hero}の手の甲が、かすかにうずいた。
@flag set p_mural_2
@end

# ------------------------------------------------------------
#  3-2 挫折
# ------------------------------------------------------------
*p3_naive
@effect tint red
空の玉座の前に、黒衣の魔族とグレイが立っている。
グレイ「お待ちしていましたよ。……いや、お帰りなさい、と言うべきでしょうか」
@npc naive move 0 8
魔将ネイヴが一歩前に出て、{hero}の前に片膝をついた。
@effect shake h 1 300
@wait 1500
ネイヴ「――お帰りなさいませ。我らが王の器よ」
ネイヴ「十五年前、あなた様は北の森で人間に拾われた。我らはずっと、あなた様を探しておりました」
ネイヴ「その剣は鍵。あなた様が握った瞬間から、王の目覚めは始まっております」
ネイヴ「村の者があなた様を恐れたのも無理はない。あなた様は――我らの側の存在なのですから」
@effect flash black count=3
仲間たちが、言葉を失って{hero}を見ている。
@choice
  - 嘘だ
  - ……
@if choice == 1
  ネイヴ「では、ご自分の手を」
@endif
{hero}の手の甲に、剣と同じ紋章が浮かんでいる。
@effect blink hero count=6 interval=120
ネイヴ「今日はご挨拶のみ。いずれ王ご自身がお迎えに上がります」
グレイ「器が満ちるのを、楽しみにしていますよ」
@effect fade_out 800
@npc naive hide
@npc grey hide
@flag set p3_revealed
@effect tint none
@effect fade_in 800
二人の姿は、闇に溶けるように消えていた。
@goto *p3_split

*p3_split
@effect fade_out 800
@map field_blackrock 14 3 dir=down
@effect tint night
@effect rain on density=2
@effect fade_in 800
洞穴の入口。外は、冷たい雨が降っていた。
@if party.has(garo) and flag.ch2_had_garo
  ガロ「……{hero}、知ってたのか？」
@elif party.has(mia) and flag.ch2_had_mia
  ミア「……{hero}、知ってたの？」
@elif party.has(rina) and flag.ch2_had_rina
  リナ「……{hero}さん、ご存じだったのですか？」
@endif
「知らなかった」
誰も、それ以上は何も言わなかった。
……ひとりが、少し離れた岩の陰で立ち止まっている。
誰と話す？
@choice
  - ガロ → *p3_leave_garo @if party.has(garo) and !flag.ch2_had_garo
  - ミア → *p3_leave_mia @if party.has(mia) and !flag.ch2_had_mia
  - リナ → *p3_leave_rina @if party.has(rina) and !flag.ch2_had_rina
  - ジャック → *p3_leave_jack @if party.has(jack)
  - ザラ → *p3_leave_zara @if party.has(zara)
  - ノア → *p3_leave_noa @if party.has(noa)

*p3_leave_garo
ガロ「……前に立つと決めた相手が、敵の王だったなんてな。少し、頭を冷やさせてくれ」
@party leave garo keep=left
@goto *p3_split_end

*p3_leave_mia
ミア「研究者としては興味深いわ。……でも、友達としては、今は顔を見られない」
@party leave mia keep=left
@goto *p3_split_end

*p3_leave_rina
リナ「神は……私に何を試しているのでしょう。祈る時間をください」
@party leave rina keep=left
@goto *p3_split_end

*p3_leave_jack
ジャック「悪い、{hero}。今回ばかりは、賭ける度胸がない」
@party leave jack keep=left
@goto *p3_split_end

*p3_leave_zara
ザラ「強い奴には興味がある。だが、魔物の王になる奴と組む気はない」
@party leave zara keep=left
@goto *p3_split_end

*p3_leave_noa
ノア「魔物とだって話せばわかるって言ったのは僕なのに……ごめん、怖いんだ」
@party leave noa keep=left
@goto *p3_split_end

*p3_split_end
{away.left}は、雨の中を一人で歩いていった。
@flag set p3_split
@effect fade_out 1000
残った仲間たちも、言葉少なにベルンへ戻った。
@effect rain off
@effect tint none
@map guild_bern 13 2 dir=right
@effect fade_in 800
協会長ドルガン「……話は聞いた」
協会長ドルガン「お前が何者だろうと、協会はお前を追い出したりはせん」
協会長ドルガン「だが、今のお前に必要なのは、剣の稽古じゃなさそうだ」
協会長ドルガン「……一度、家に帰ってこい。リト村の村長には、わしから話を通しておく」
@flag set p3_home_open
@end

# ------------------------------------------------------------
#  3-3 強化開始
# ------------------------------------------------------------
*p3_home
村は、しんと静まり返っていた。
{hero}の姿を見た村人たちが、慌てて家の戸を閉めていく。
カイ「――{hero}！」
戸の閉まる音の中を、カイが一人だけ駆け寄ってきた。
カイ「……話は、村長から聞いた。魔物の王の、器だって」
カイ「でもさ、関係ねーよ。お前はお前だ。森で一緒に迷子になった、あの{hero}だろ」
カイ「おばさんが家の前で待ってる。……早く行ってやれ。俺は、うちの前にいるから」
@flag set p3_kai_met
……家の前で、母が待っていた。
母「……帰ってきたのね」
母「話さなきゃいけないこと、話すわね」
@effect fade_out 600
@map house_hero 5 4 dir=up
@effect fade_in 600
@goto *p3_confession

*p3_confession
@effect tint sepia
母「十五年前の冬。テラおばあさんが、森で赤ちゃんを拾ってきたの」
母「祠の前で、泣きもせずに、じっと空を見ている子だった」
母「額には、変な模様があったわ。テラおばあさんは『この子は普通の子じゃない』って」
母「でも、私たちには子供がいなかった。……あなたを抱いたとき、この子は私の子だって思ったの」
@effect tint none
父「……模様は、一年もしないうちに消えた。だから、忘れたことにした」
父「お前が何者だろうと、俺たちが育てた。それだけだ」
ミナ「おにいちゃんは、おにいちゃんだよ？」
@choice
  - ……ありがとう
  - でも、僕は魔物の王の――
@if choice == 2
  母「違う。あなたは、{hero}よ。私たちがつけた名前の、私たちの子」
@endif
窓の外を、流れ星が流れていった。
@effect starfall count=4
@flag set p_family_accept
母「テラおばあさんにも、会っていきなさい。……ずっと、あなたのことを気にかけていたのよ」
@end

# ---- 里帰りのあとのカイ（村の南西、カイの家の前）
*p3_kai_talk
@if flag.p3_mem1
  カイ「祠、行ってきたのか。……そっか」
  カイ「すげー冒険者になって帰ってこいって言ったの、まだ有効だからな」
@elif flag.p3_tera_done
  カイ「森の祠に行くのか？　……あそこ、秘密基地にしようって言ったよな」
  カイ「行ってこいよ。今度は置いていかねーから、待ってる」
@else
  カイ「テラばあちゃんのとこにも行ってみろよ。お前のこと、ずっと気にしてたんだぜ」
@endif
@end

*p3_tera
テラ「……来たかい。いつか来ると思っていたよ」
テラ「器ってのはね、空っぽの入れ物さ。だから王が入れる」
テラ「でもね、お前さんは空っぽじゃない。十五年、ロイとエマとミナと、村のみんなで満たしてきたんだ」
テラ「入れ物がいっぱいなら、王の入る隙間はない。……あたしはそう信じてるよ」
テラ「剣をお貸し。この剣は鍵だ。鍵ってのは、閉めることもできる」
テラは剣を両手で包み、目を閉じて、何かを小さくつぶやいた。
@effect flash white count=2
@item replace rusty_sword heart_key_sword
@skill add hero kokoro_tozashi
錆びた剣は{item.heart_key_sword}になった！　{hero}は「心閉ざし」を覚えた！
テラ「あとは、お前さん自身が自分を信じられるかどうかさ」
テラ「三つ、行っておいで。お前さんを満たしてきたものが、残っている場所へ」
テラ「カイと遊んだ森の祠。ロイと星を見た村の丘。……それから、初めて仲間ができた場所」
テラ「そこで、自分の中にいるものと向き合っておいで。一人でね」
@flag set p3_tera_done
@end

# ---- 記憶の場所（主人公ひとりの戦い。負けたら回復して出直す）
*p3_mem_forest
苔むした祠の前に立つと、子供の頃の声が聞こえた。
@effect tint sepia
カイ「{hero}、こっちこっち！　秘密基地にしようぜ！」
カイ「大人になったら、二人ですげー冒険者になるんだ。約束な！」
@effect tint none
……祠の陰から、黒い影が立ち上がった。{hero}と同じ顔をしている。
影の{hero}「その約束も、空っぽの器が見た夢だ」
@battle group=shadow members=hero escape=false lose=*p3_mem_lost
影は、子供の笑い声の中に溶けて消えた。
@stat hero hp +20
@flag set p3_mem1
@heal all
{hero}の最大 HP が 20 上がった！
@call *p3_mem_check
@end

*p3_mem_hill
村の丘に登ると、満天の星が広がっていた。
@effect tint night
@effect starfall count=5
父「あれが北の星だ。迷ったら、あれを探せ」
父「……どこにいても、同じ星が見える。だから、迷っても帰ってこられる」
星の光をさえぎるように、黒い騎士が現れた。
@battle group=mem_hill members=hero escape=false lose=*p3_mem_lost
騎士は、星の光に焼かれるように崩れ落ちた。
@effect tint none
@stat hero mag +10
@skill add hero hoshiyomi
@flag set p3_mem2
@heal all
{hero}の魔力が 10 上がった！　「星詠み」を覚えた！
@call *p3_mem_check
@end

*p3_mem_guild
初めて協会に来た日に座った、隅の机だ。
@effect tint sepia
受付セラ「{hero}さん、ちょうど、パーティを探している冒険者がいるんです」
@if flag.ch2_had_garo
  ガロ「よろしく頼む。…その剣、錆びてるがいい剣だな」
@elif flag.ch2_had_mia
  ミア「よろしくね。その剣の紋章…どこかで見た気がするのよね」
@else
  リナ「神のお導きに感謝します。…不思議な気配のする剣ですね」
@endif
@effect tint none
机の向こうに、初めての依頼で戦った魔物たちの幻が立っている。
@battle group=mem_guild members=hero escape=false lose=*p3_mem_lost
幻は、協会のにぎやかな声の中に消えていった。
@flag set p3_mem3
@heal all
仲間たちとの日々が、{hero}を満たしていく――
@if flag.p3_mem1 and flag.p3_mem2
  @goto *p3_return
@endif
@call *p3_mem_check
@end

*p3_mem_lost
……気がつくと、膝をついていた。影は、もう見えない。
@heal all
まだ、向き合いきれていない。もう一度来よう。
@end

*p3_mem_check
@if flag.p3_mem1 and flag.p3_mem2 and flag.p3_mem3
  三つの記憶の場所を巡った。……ベルンの協会へ戻ろう。
@endif
@return

# ---- 仲間の復帰（記憶の場所を巡り終えて協会に入ると）
*p3_return
{away.left}が、協会の入口に立っていた。
{away.left}「……ずっと考えてた」
@if away.left == garo
  ガロ「お前の前に立つと決めたのは俺だ。相手が誰でも、それは変わらん」
@elif away.left == mia
  ミア「器が満ちていれば王は入れない――テラさんの仮説、研究させてもらうわ。そばでね」
@elif away.left == rina
  リナ「祈りの答えがわかりました。あなたを信じることが、私の祈りです」
@elif away.left == jack
  ジャック「全財産、お前に賭けることにした。……まあ、全財産っつっても 12G だけどな」
@elif away.left == zara
  ザラ「魔物の王になんか、ならせない。……そのために、そばにいる」
@elif away.left == noa
  ノア「ピピがね、{hero}は怖くないって。……僕より先にわかってたんだ」
@endif
@party return left
@flag set p3_returned
{hero}たちは、ふたたび全員そろった！
離れていた間、仲間たちもそれぞれに腕を磨いていた。
@if party.has(garo)
  @skill add garo whirlwind
  ガロは「旋風斬」を覚えた！
@endif
@if party.has(mia)
  @skill add mia flame_storm
  ミアは「フレイムストーム」を覚えた！
@endif
@if party.has(rina)
  @skill add rina heal_all
  リナは「ハイヒール」を覚えた！
@endif
@if party.has(jack)
  @skill add jack jackpot
  ジャックは「ジャックポット」を覚えた！
@endif
@if party.has(zara)
  @skill add zara fierce_strike
  ザラは「猛攻」を覚えた！
@endif
@if party.has(noa)
  @skill add noa beast_call
  ノアは「群れの咆哮」を覚えた！
@endif
@goto *p3_legend

# ------------------------------------------------------------
#  3-4 最強の敵の話
# ------------------------------------------------------------
*p3_legend
@effect fade_out 500
@map guild_bern 13 2 dir=right
@effect fade_in 500
協会長ドルガン「グレイの残した資料を全部読んだ」
協会長ドルガン「虚ろの王ゼノ。三百年前、勇者に肉体を滅ぼされ、魂だけになった魔物の王だ」
協会長ドルガン「奴は器に入り込むことで復活する。器が本物なら、完全な姿で」
協会長ドルガン「玉座の間の奥に、ゼノの魂が封じられた『虚ろの殻』がある。ネイヴたちはそこで、お前を待っている」
協会長ドルガン「行かなきゃ奴らはお前を狙い続ける。……行けば、奴に乗っ取られるかもしれない」
@choice
  - 行く
  - ……行く。自分で終わらせる
協会長ドルガン「……いい目だ。お前の親父さんに似てる」
@flag set p3_done
@effect typewriter "第3章　完"
@save_point
協会長に声をかければ、第4章が始まる。
@end
