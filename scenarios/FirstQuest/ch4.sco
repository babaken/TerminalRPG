# ============================================================
#  FirstQuest  第4章　終わりの始まり
#  元テキスト: docs/scenario/FirstQuest_story.md（第4章）
# ============================================================

# ------------------------------------------------------------
#  4-1 ボスの名は（3章のあと、協会長ドルガンに話しかけると始まる）
# ------------------------------------------------------------
*ch4_start
@chapter 4 "終わりの始まり"
@effect fade_out 600
@effect typewriter "第4章　終わりの始まり"
@map guild_bern 13 2 dir=right
@effect fade_in 600
協会長ドルガン「……蝕王ヴェルム、か。おとぎ話だと思っていた」
協会長ドルガン「国の騎士団が洞穴の周りを固める。だが、中に入れるのはお前たちだけだ。あの扉は剣にしか開けられん」
受付セラ「{hero}さん。……必ず、帰ってきてくださいね」
@item add elixir 3
@effect flash white
冒険者ランク B になった！　{item.elixir}を 3 つ受け取った！
協会長ドルガン「行ってこい、冒険者」
@flag set ch4_started
@end

# ------------------------------------------------------------
#  4-2 ボスとの対決（儀式の間）
# ------------------------------------------------------------
*ch4_garza2
@effect tint red
祭壇の黒い炎は、前よりもずっと大きくなっている。
ガルザ「懲りずに来たか。……ほう、剣が目を覚ましかけているな」
ガルザ「だが遅い。贄はそろった。蝕王様の復活は止められぬ」
@effect shake h 3 600
@battle group=garza_2 escape=false gameover=choose
@npc garza2 hide
ガルザ「ば、馬鹿な……人の子ごときに……」
ガルザ「だが……我が血をもって……儀式は……成る……！」
@effect shake v 3 1500
@effect flash red count=3
@effect tint invert
@wait 300
@effect tint red
祭壇の炎がガルザを飲み込み、巨大な影が立ち上がった。
@aa show aa/verm.txt 18 1 name=verm
ヴェルム「――三百年。長い眠りであった」
ヴェルム「その剣……レオンの剣か。また余を封じに来たか、人の子よ」
ヴェルム「だが今の余は、まだ目覚めきってはおらぬ。お前もまた、剣を目覚めさせきってはおらぬ」
ヴェルム「面白い。ならば試してやろう」
@aa hide verm
@battle group=verm_1 escape=false gameover=choose
@goto *ch4_sword_awake

*ch4_sword_awake
ヴェルム「……まだだ。余はまだ終わらぬ！」
ヴェルムの体から、闇があふれ出す。
仲間たち「{hero}！！」
@if party.has(garo)
  ガロ「立て、{hero}！　前は俺が守る！」
@endif
@if party.has(mia)
  ミア「あきらめないで！　あんたの剣、まだ光ってる！」
@endif
@if party.has(rina)
  リナ「祈りは届きます……今度こそ！」
@endif
@if party.has(jack)
  ジャック「ここが勝負どころだろ、{hero}！」
@endif
@if party.has(zara)
  ザラ「見せてみろ。お前の、本当の力を！」
@endif
@if party.has(noa)
  ノア「ピピが言ってる……その剣、目を覚ますって！」
@endif
――剣が、熱い。
@effect flash white count=5 interval=60
@effect starfall count=12
錆が剥がれ落ち、まばゆい刃が姿を現した。
@item replace awakening_sword astra
@item replace rusty_sword astra
@skill add hero seal_light
@heal all
封剣アストラが目覚めた！　{hero}は「封印の光」を覚えた！
@battle group=verm_2 escape=false gameover=choose
@goto *ch4_verm_end

# ------------------------------------------------------------
#  4-3 第2・第3の敵への示唆
# ------------------------------------------------------------
*ch4_verm_end
@effect flash white count=2
ヴェルム「……見事だ、人の子よ……」
ヴェルム「だが、覚えておけ……」
ヴェルム「嵐王と渇王は……すでに目覚めている……」
ヴェルム「余は三柱のうち、最も弱き者に過ぎぬ……ふ、ふふ……」
@effect fade_out 1500
ヴェルムの体は、灰となって崩れ落ちた。
@effect tint none
@effect fade_in 800
祭壇の炎が消え、洞穴に静けさが戻った。
奥の檻に、さらわれていた人々の姿がある。
{hero}たちは、人々を連れて洞穴を出た。
@flag set ch4_done
@quest done q_blackrock_deep
@gold add 1000
@effect fade_out 800
@map guild_bern 10 5 dir=up
@effect fade_in 800
@goto *ch4_return_guild

# ------------------------------------------------------------
#  4-4 物語の終わり・帰還
# ------------------------------------------------------------
*ch4_return_guild
協会長ドルガン「……やりやがったな」
協会長ドルガン「さらわれた人たちは全員無事だ。お前たちのおかげだ」
受付セラ「おかえりなさい、{hero}さん！」
協会長ドルガン「嵐王と渇王、か。……国にも、他の支部にも伝える。これから忙しくなるぞ」
報酬として 1000 G を受け取った。
協会長ドルガン「それはそうと、お前に客だ」
@flag set ch4_returned
@npc kai_guild move 0 -2
カイ「よっ、{hero}！」
カイ「すげーな！　噂がリト村まで届いてるぞ。『封剣の勇者』だってさ！」
カイ「村長がさ……謝りたいって。みんなもだ」
カイ「おばさんもおじさんもミナも待ってる。一度、帰ってこいよ」
@flag set ch4_kai
カイ「先に村へ戻ってるからな！　街道を北だぞ」
@npc kai_guild hide
@end

*ch4_kai_guild_talk
カイ「リト村で待ってるぞ！　街道を北だ」
@end

*ch4_village
@effect fade_in 600
村の入口に、村の人たちが並んでいる。
村長「{hero}……すまなかった。わしらは、お前を信じてやれなんだ」
村人たち「すまなかった……！」「おかえり！」
ミナ「おにいちゃーーん！！」
母「……おかえりなさい」
父「…………剣の手入れは、怠らなかったようだな」
@choice
  - ただいま
  - （何も言わず家族を抱きしめる）
@if choice == 2
  {hero}は何も言わず、家族を抱きしめた。
  母「……大きくなったわね」
@else
  ミナ「おかえりなさい、おにいちゃん！」
@endif
@flag set ch4_home
@goto *ch4_epilogue

*ch4_home_talk
@if flag.ch4_home
  村の人たちが、うれしそうにこちらを見ている。
@endif
@end

*ch4_epilogue
@effect fade_out 1000
@effect tint night
@effect fade_in 1000
その夜、{hero}は仲間たちと村の丘に登った。
@if party.has(garo)
  ガロ「次はどこへ行く？　どこだろうと、前は任せろ」
@endif
@if party.has(mia)
  ミア「嵐王に渇王……研究のしがいがありそうね」
@endif
@if party.has(rina)
  リナ「傷ついた人がいる限り、私も一緒に行きます」
@endif
@if party.has(jack)
  ジャック「ツキはまだまだ続きそうだ。な、{hero}」
@endif
@if party.has(zara)
  ザラ「……悪くない旅だった。次も、悪くないだろう」
@endif
@if party.has(noa)
  ノア「ピピも、次の旅が楽しみだって！」
@endif
@effect starfall count=10
空には、いくつもの流れ星が流れていく。
――三柱の魔は、まだ二柱残っている。
冒険は、終わりではなく、始まったばかりだ。
@effect fade_out 1500
@effect tint none
@effect typewriter "FirstQuest　―完―"
@effect scroll_text file=credits.txt speed=2
@ending text="{hero}の冒険は、まだ始まったばかり"
