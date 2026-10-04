# ============================================================
#  FirstQuest+  第4章　終わりの始まり
#  元テキスト: docs/scenario/FirstQuestPlus_story.md（第4章）
#  4-1 ボスの名は 〜 4-4 物語の終わり・帰還。3章のあと、協会長ドルガンに話しかけると始まる
#  玉座の間に入ると、グレイとネイヴ → 虚ろの殻 → 精神世界 → ゼノ 2 形態まで続けて進む
#  （全滅して「セーブから」を選ぶと、玉座の間に入る前から）
# ============================================================

# ------------------------------------------------------------
#  4-1 ボスの名は
# ------------------------------------------------------------
*p4_start
@chapter 4 "終わりの始まり"
@effect fade_out 600
@effect typewriter "第4章　終わりの始まり"
@map guild_bern 13 2 dir=right
@effect fade_in 600
協会長ドルガン「騎士団が洞穴の周りを固める。だが、玉座の間に入れるのはお前たちだけだ」
協会長ドルガン「……{hero}。お前が戻ってこなかったら、わしがお前の親父さんに殴られる。必ず帰ってこい」
受付セラ「{hero}さん。……ここで、待っていますから」
@item add elixir 3
@effect flash white
冒険者ランク B になった！　{item.elixir}を 3 つ受け取った！
協会長ドルガン「街の店にも、国の倉庫から新しい品を回させた。装備を整えていけ」
@flag set p4_started
@end

*p4_throne
@effect tint red
空の玉座の前に、ネイヴとグレイが待っていた。
ネイヴ「お待ちしておりました。……ずいぶんと、余計なものを連れて」
グレイ「器の周りにいる人間は、王が入る邪魔になります。排除しましょう」
@if flag.p_child_spared
  そのとき、玉座の陰から小さな影が飛び出した。
  ……B13F で逃がした、あの子供だ。
  子供「おにいちゃんを……いじめるな……！」
  子供はグレイの腕にしがみつき、詠唱を断ち切った。
  @effect flash magenta
  グレイ「くっ……失敗作が……！」
  子供は暗がりへ駆け去っていった。
  @battle group=grey_naive_spared escape=false gameover=choose
@else
  @battle group=grey_naive escape=false gameover=choose
@endif
@flag set p4_naive_done
@npc naive4 hide
@npc grey4 hide
グレイ「ば……馬鹿な……器が、なぜ人間の側に……」
グレイは崩れ落ち、二度と動かなかった。
ネイヴ「……見事。ですが、もう遅い」
ネイヴ「王はすでに、あなた様の中に」
@goto *p4_zeno_name

*p4_zeno_name
@effect fade_out 500
@map dungeon_shell 15 10 dir=up
@effect fade_in 500
玉座の奥の壁が崩れ、黒い殻のような空間が口を開けていた。
@effect shake v 3 900
@effect flash black count=4
@effect tint invert
頭の奥で、十五年間聞こえていた声が、はっきりと名乗った。
『――余は、虚ろの王ゼノ』
『器よ。よく育った。よく満ちた。……その中身ごと、余がもらい受ける』
@if party.has(garo)
  {name.garo}「{hero}！　しっかりしろ！」
@elif party.has(mia)
  {name.mia}「{hero}！　聞こえる！？」
@endif
仲間の声が、遠くなっていく――
@goto *p4_inner

# ------------------------------------------------------------
#  4-2 ボスとの対決
# ------------------------------------------------------------
*p4_inner
@effect fade_out 800
@map mind_world 15 15 dir=up
@effect tint invert
@effect fade_in 800
……誰もいない村。
家族の家も、カイも、仲間も、色がない。
黒い影が、{hero}と同じ姿で立っていた。
ゼノ『ここがお前の中身か。小さな村だ。すぐに塗りつぶせる』
@battle group=zeno_inner members=hero escape=false turns=3 lose=*p4_voices
@goto *p4_voices

*p4_voices
意識が遠のいていく――
@wait 800
「――{hero}！」
カイ「すげー冒険者になって帰ってこいって言っただろ！」
@effect flash white
ミナ「おにいちゃんは、おにいちゃんだよ！」
母「あなたは、{hero}よ」
父「……剣の手入れを、怠るな」
@effect flash white
テラ「入れ物がいっぱいなら、王の入る隙間はない」
@if party.has(garo)
  {name.garo}「お前の前に立つのは俺だ。……だから、戻ってこい！」
@endif
@if party.has(mia)
  {name.mia}「あんたはあんたよ。私の研究が、それを証明してあげる！」
@endif
@if party.has(rina)
  {name.rina}「あなたを信じることが、私の祈りです！」
@endif
@if party.has(jack)
  {name.jack}「全財産賭けてんだ！　負けんなよ、{hero}！」
@endif
@if party.has(zara)
  {name.zara}「魔物の王になんか、ならせないって言っただろ！」
@endif
@if party.has(noa)
  {name.noa}「ピピも、僕も、ここにいるよ！」
@endif
声が聞こえるたびに、色のない村に、色が戻っていく。
@effect tint none
@effect flash white count=3
ゼノ『な……なぜだ。器が……余を、押し返す……！』
{hero}の手の中で、剣が形を変えていく。
鍵ではない。誰かのためのものでもない。
――これは、{hero}自身の剣だ。
@item replace heart_key_sword own_sword
@item replace rusty_sword own_sword
@skill add hero michiru_hikari
@heal all
{item.own_sword}を手に入れた！　{hero}は「満ちる光」を覚えた！
@goto *p4_final

*p4_final
@effect fade_out 800
@map dungeon_shell 15 8 dir=up
@effect tint red
@effect fade_in 800
気がつくと、仲間たちが{hero}の名を呼び続けていた。
@if party.has(garo)
  {name.garo}「……{hero}？　本当に、{hero}だよな？」
@elif party.has(mia)
  {name.mia}「……{hero}？　本当に、{hero}よね？」
@else
  仲間「……{hero}？　本当に、{hero}なのか？」
@endif
ゼノは器から弾き出され、黒い殻の中で巨大な姿をとった。
@aa show aa/zeno.txt 26 1 name=zeno
ゼノ『器を失えば……余は消える……ならば、すべて道連れに……！』
@aa hide zeno
@effect shake h 3 600
@battle group=zeno_1 escape=false gameover=choose
ゼノ『おのれ……おのれ、器ァ……！』
ゼノの体が裂け、虚ろな真の姿が現れた。
ゼノ『お前の中の記憶……ひとつ残らず、奪ってくれる……！』
@effect flash black count=2
@battle group=zeno_2 escape=false gameover=choose
@goto *p4_zeno_end

# ------------------------------------------------------------
#  4-3 第2・第3の敵への示唆
# ------------------------------------------------------------
*p4_zeno_end
@effect flash white count=2
@effect fade_out 800
@effect tint none
@effect fade_in 800
ゼノ『……器は、お前だけでは……ない……』
ゼノ『余が作ったのではない器が……他にも……いる……』
ゼノ『それを探している者が……余の他にも……』
ゼノは霧のように消えていった。
ネイヴの姿は、どこにもない。
床に、ネイヴのものらしい黒い羽根が一枚落ちている。
@item add black_feather
{item.black_feather}を手に入れた。
@flag set p4_done
@gold add 1000
@effect fade_out 800
@map guild_bern 10 5 dir=up
@effect fade_in 800
@goto *p4_guild

# ------------------------------------------------------------
#  4-4 物語の終わり・帰還
# ------------------------------------------------------------
*p4_guild
協会長ドルガン「……おかえり、{hero}」
協会長ドルガン「『他の器』か。グレイの資料にも、ほかの研究機関の名前があった。国に調べさせる」
受付セラ「おかえりなさい！　……本当に、よかった」
報酬として 1000 G を受け取った。
協会長ドルガン「さあ、村へ帰ってやれ。街道を北だ」
@end

*p4_village
@effect fade_in 600
村の入口に、村の人たちが並んでいる。
村長「{hero}……お前が何者であろうと、この村の子じゃ。すまなかった」
村人「魔物の仲間なんて言って、悪かった……！」
村人「おかえり、{hero}！」
カイ「な？　言っただろ、お前があの剣を拾ったのには意味があるって！」
母「……おかえりなさい、{hero}」
@choice
  - ただいま
  - ただいま、母さん
@if choice == 2
  母は、目に涙を浮かべて笑った。
  母「……おかえり。わたしの、自慢の子」
@endif
@flag set p4_home
@goto *p4_epilogue

*p4_home_talk
村の人たちが、うれしそうにこちらを見ている。
@end

*p4_epilogue
@effect fade_out 1000
@effect tint night
@effect fade_in 1000
その夜、{hero}は仲間たちと村の丘に登った。
{hero}の手の甲の紋章は、もう消えていた。
@if party.has(garo)
  {name.garo}「次はどこへ行く？　どこだろうと、前は任せろ」
@endif
@if party.has(mia)
  {name.mia}「『他の器』……研究のしがいがありそうね」
@endif
@if party.has(rina)
  {name.rina}「器を探している人たちがいるなら、その人たちも救いたいです」
@endif
@if party.has(jack)
  {name.jack}「賭けは俺の勝ちだったな。配当は……まあ、旅の続きでいいや」
@endif
@if party.has(zara)
  {name.zara}「次の器が敵になるなら、その前に見つけ出す」
@endif
@if party.has(noa)
  {name.noa}「ピピがね、南の空がざわざわするって」
@endif
@effect starfall count=12
空を見上げると、流れ星がひとつ、遠い南の空へ落ちていった。
――どこかで、別の「器」が、同じ空を見上げているのかもしれない。
@effect fade_out 1500
@effect tint none
@effect typewriter "FirstQuest+　―完―"
@effect scroll_text file=credits.txt speed=2
@ending text="{hero}は、{hero}のまま、明日を生きていく"
