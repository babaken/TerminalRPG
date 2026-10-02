# ============================================================
#  FirstQuest  第2章　影を追う者たち
#  元テキスト: docs/scenario/FirstQuest_story.md（第2章）
#  現在: 第2章すべて（2-1 冒険者が死ぬ事件 〜 2-4 一時帰還・仲間 2 人）
# ============================================================

# ------------------------------------------------------------
#  2-1 冒険者が死ぬ事件（1章の最後から続く）
# ------------------------------------------------------------
*ch2_start
@chapter 2 "影を追う者たち"
@effect fade_out 600
@effect typewriter "第2章　影を追う者たち"
@map guild_bern 10 5 dir=up
@effect fade_in 600
数日後。{hero}たちは今日も冒険者協会に顔を出した。
受付セラ「おはようございます。今日も依頼をお探しですか？」
掲示板の前で、冒険者たちが話し込んでいる。
冒険者「聞いたか？　『銀の牙』のパーティ、帰ってこなかったらしい」
冒険者「またか。今月で 3 組目だぞ。それもベテランばかり」
冒険者「依頼自体は簡単な調査だったはずなんだがな……」
{party.2}「……物騒な話ね」
@flag set ch2_rumor
@goto *ch2_take_kabura

*ch2_take_kabura
受付セラ「{hero}さん、ちょうどよかった。カブラ村から依頼が来ているんです」
受付セラ「畑を荒らす魔物の退治です。モグラのような魔物だそうで……報酬は 200 G」
受付セラ「……最近、失敗する依頼が増えているんです。どうか気をつけて」
@quest give q_mole
依頼「カブラ村の畑荒らし」を受けた！
受付セラ「カブラ村は、ベルンの南門を出てすぐですよ」
@end

# ------------------------------------------------------------
#  2-2 地図を発見
# ------------------------------------------------------------
*ch2_kabura_wife_talk
@if flag.mole_defeated
  村長の妻「本当にありがとう！　これで安心して畑仕事ができるわ」
  @end
@endif
@if quest.q_mole != active
  村長の妻「ようこそカブラ村へ。何もない村だけど、野菜はおいしいのよ」
  @end
@endif
村長の妻「まあ、冒険者さん！　来てくださったのね」
村長の妻「畑が毎晩掘り返されて、作物がみんなだめになってしまって……」
村長の妻「しかも最近は、昼間でも出てくるようになったのよ」
村長の妻「村の南の畑よ。どうか、お願いします」
@flag set ch2_kabura_talked
@end

*ch2_kabura_farmer_talk
@if flag.mole_defeated
  農夫「あのデカブツをやっつけたのか！　あんたら、たいしたもんだ」
@else
  農夫「あいつら、ただ畑を荒らしてるんじゃねぇ。何か探してるみてぇに掘ってやがる」
  @flag set ch2_kabura_talked
@endif
@end

*ch2_kabura_child_talk
@if flag.mole_defeated
  子供「ねえねえ、モグラのおばけ、ほんとにやっつけたの？　すっげー！」
@else
  子供「夜になると、畑の土がもこもこ動くんだよ。こわいよ……」
@endif
@end

*ch2_kabura_elder_talk
老人「昔は東の岩山で鉄が採れてのう。今は廃坑で、誰も近づかん」
老人「……そういえば、あそこから妙な音がするという噂を聞いたわい」
@end

*ch2_mole_battle
@effect shake v 2 800
地面が大きく揺れた！
@effect shake v 3 600
畑の土が盛り上がり、巨大なモグラが顔を出した！
{party.2}「来るわよ、{hero}！」
@battle group=mole_boss escape=false
@goto *ch2_map_drop

*ch2_map_drop
ドリルモールは土の中に崩れ落ちた。
……何かが落ちている。古い羊皮紙だ。
@item add old_map
{item.old_map}を手に入れた！
地図には、ベルンの東の岩山に印がつけられている。
印の横に、見たことのない文字が書かれている。
{party.2}「魔物が地図を持ってるなんて……おかしくない？」
@flag set mole_defeated
これで依頼は達成だ。冒険者協会に報告しよう。
@end

# ------------------------------------------------------------
#  2-3 ダンジョンへ（依頼の報告のあと：Quests.data の on_complete）
# ------------------------------------------------------------
*ch2_report_map
受付セラ「お疲れさまでした！　……あの、それは？」
{hero}は{item.old_map}を見せた。
受付セラ「……！　少々お待ちください。協会長を呼んできます」
@wait 300
@npc dorgan show
@npc dorgan move -4 0
協会長ドルガン「ほう、お前がリト村から来た小僧か。地図を見せてみろ」
協会長ドルガン「……この文字は魔族の文字だ。印の場所は『黒岩の洞穴』。昔、廃坑になった場所だ」
協会長ドルガン「消えた冒険者たちの最後の依頼先が、その近辺に集中している」
協会長ドルガン「{hero}。協会からの指名依頼だ。黒岩の洞穴を調査してくれ」
協会長ドルガン「無理はするな。何かわかったら、必ず戻って報告しろ」
@item remove old_map
@item add map_copy
@quest give q_blackrock
@flag set ch2_map_reported
@effect flash white
指名依頼「黒岩の洞穴の調査」を受けた！　冒険者ランク D になった！
{item.map_copy}を受け取った。
協会長ドルガン「洞穴は街の東門を出た先の岩山だ。門の衛兵には話を通しておく」
協会長ドルガン「……生きて帰れよ」
@end

# ---- ベルンの東門（指名依頼を受けるまでは通行止め）
*ch2_east_guard_talk
衛兵「止まれ。東門は通行止めだ」
衛兵「東の岩山で落石が続いていてな。協会の許可がない者は通すなと言われている」
@if flag.ch2_rumor
  衛兵「……それに、あっちへ向かった冒険者が何組も戻ってこない。悪いことは言わん、近づくな」
@endif
@end

*ch2_east_guard_open_talk
衛兵「協会長から話は聞いている。黒岩の洞穴へ行くんだろう」
衛兵「通っていいぞ。……くれぐれも気をつけてな」
@end

# ---- 協会長ドルガン（地図の報告のあとは協会にいる。マップでは「会」）
*ch2_dorgan_talk
@if flag.ch2_done
  協会長ドルガン「次はあの洞穴の奥だ。……準備ができたら声をかけろ」
@elif flag.ch2_found_scroll
  協会長ドルガン「戻ったか。まずはセラに報告してこい」
@else
  協会長ドルガン「黒岩の洞穴を頼む。東門の衛兵には話を通してある」
  協会長ドルガン「何かわかったら、必ず戻って報告しろ。いいな」
@endif
@end

# ---- 黒岩の洞穴前（field_blackrock）
*ch2_blackrock_out
岩山の裂け目に、洞穴の入口が見える。
入口の前に、武装したゴブリンが立っている。
{party.2}「見張り……？　魔物が見張りを立てるなんて」
@end

*ch2_blackrock_guard
ゴブリン隊長「グルル……ニンゲン……ココハ　トオサン」
@battle group=goblin_guard escape=false
@flag set ch2_guard_done
見張りのゴブリンたちを倒した。
{party.2}「統率された魔物……やっぱり何かあるわね」
@end

# ---- 黒岩の洞穴（dungeon_b01〜b11。暗く、周りしか見えない）
*ch2_cave_enter
洞穴の中は真っ暗だ。手元の明かりで、周りが少しだけ見える。
{party.2}「足元に気をつけて。……奥から嫌な気配がするわ」
@end

*ch2_b01_pack
冒険者のものらしい荷物が転がっている。
@item add herb 2
{item.herb}を 2 つ手に入れた！
中に走り書きのメモが入っている。
「奥へ行くほど……魔物が……統率されて……」
@tile 25 12 _
@end

*ch2_b03_chest
宝箱を開けた！
@item add steel_sword
{item.steel_sword}を手に入れた！
{party.2}「いい剣ね。……でも、その錆びた剣も手放さないほうがいい気がするわ」
@tile 5 3 b
@end

*ch2_b05_spring
澄んだ水が湧き出している。
@heal all
泉の水を飲むと、体の疲れがすっかり取れた！
@end

*ch2_b06_relic
冒険者の遺品が落ちている。
@item add silverfang_emblem
@flag set found_silverfang
{item.silverfang_emblem}を手に入れた。
{party.2}「『銀の牙』……噂の、帰ってこなかったパーティね」
@tile 3 5 _
@end

*ch2_b08_ogre
@effect shake h 2 500
地響きとともに、巨大な影が立ちはだかった！
オーガ「グオオオオ……！」
@battle group=ogre escape=false
@flag set ch2_ogre_done
オーガは崩れ落ちた。この先へ進めそうだ。
@end

*ch2_b10_circle
地面に、何かの模様が描かれている。
{party.2}「……魔法陣の跡ね。何かの儀式に使われたみたい」
古びた地図の写しには、この先の記載はない。
@end

*ch2_return_scroll
@if flag.ch2_found_scroll
  空になった木箱だ。
  @end
@endif
小部屋に古びた木箱がある。
@item add return_scroll
@flag set ch2_found_scroll
@tile 16 14 b
{item.return_scroll}を手に入れた！
{party.2}「帰還の巻物……使えば、すぐ街に戻れるわ」
{party.2}「この先は魔物の気配がずっと濃い。二人じゃ厳しいかもしれない」
@choice
  - 一度戻って報告しよう
  - もう少し進もう
@if choice == 2
  {party.2}「……{hero}、ドルガンさんは『必ず戻って報告しろ』って言ってたでしょ？」
@endif
{hero}は{item.return_scroll}を広げた。
@effect flash white count=3
@effect fade_out 500
@map guild_bern 10 5 dir=up
@effect fade_in 600
……気がつくと、冒険者協会の前に立っていた。
{party.2}「セラさんに報告しましょう」
@end

# ------------------------------------------------------------
#  2-4 一時帰還（指名依頼の報告のあと：Quests.data の on_complete）
# ------------------------------------------------------------
*ch2_report
協会長ドルガン「……戻ったか。よく無事だった」
{hero}たちは、洞穴で見たものを報告した。
入口の見張り、統率された魔物、儀式の跡――
@if flag.found_silverfang
  {hero}は{item.silverfang_emblem}を差し出した。
  協会長ドルガン「銀の牙の紋章……あいつらは、そこで……」
  協会長ドルガン「……届けてくれて、礼を言う」
@endif
協会長ドルガン「魔物が組織立って動いている。こいつはもう、ただの魔物退治じゃない」
協会長ドルガン「国にも報告を上げた。協会と国から、お前たちに戦力を回す」
協会長ドルガン「選べ、{hero}。お前の目で、背中を預けられる奴を」
# 1章で選んだ仲間を覚えておく（加入の台詞を分けるため）
@if party.has(garo)
  @flag set ch2_had_garo
@endif
@if party.has(mia)
  @flag set ch2_had_mia
@endif
@if party.has(rina)
  @flag set ch2_had_rina
@endif
@recruit garo mia rina jack zara noa pick=2 lv=avg
@if party.has(jack)
  ジャック「よろしく！　サイコロの出目が悪いときは、慰めてくれよな」
@endif
@if party.has(zara)
  ザラ「足を引っ張るなよ。……ふん、その剣、悪くない」
@endif
@if party.has(noa)
  ノア「この子（使い魔の小鳥ピピ）もよろしくだって！」
@endif
@if party.has(garo) and !flag.ch2_had_garo
  ガロ「今度こそ一緒に行けるな。前は任せろ」
@endif
@if party.has(mia) and !flag.ch2_had_mia
  ミア「今度こそ一緒に行けるわね。研究費、しっかり稼がせてもらうわよ」
@endif
@if party.has(rina) and !flag.ch2_had_rina
  リナ「今度こそご一緒できますね。皆さんの傷は、私が癒やします」
@endif
協会長ドルガン「いい顔ぶれだ。……次は、あの洞穴の奥だ。準備ができたら声をかけろ」
@flag set ch2_done
@effect typewriter "第2章　完"
@save_point
（第3章「灰の影」は制作中です。このまま街やダンジョンを自由に歩けます）
@end
