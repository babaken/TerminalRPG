# ============================================================
#  FirstQuest  第3章　灰の影
#  元テキスト: docs/scenario/FirstQuest_story.md（第3章）
#  現在: 第3章すべて（3-1 調査へ 〜 3-4 最強の敵の話）
# ============================================================

# ------------------------------------------------------------
#  3-1 調査へ（2章のあと、協会長ドルガンに話しかけると始まる）
# ------------------------------------------------------------
*ch3_start
@chapter 3 "灰の影"
@effect fade_out 600
@effect typewriter "第3章　灰の影"
@map guild_bern 13 2 dir=right
@effect fade_in 600
協会長ドルガン「準備はいいか。今回は B11F より先、魔物どもの『目的』を突き止めてもらう」
協会長ドルガン「偵察に出した連中から報告があった。B11F の東の壁が崩れて、奥へ続く道が見つかったそうだ」
協会長ドルガン「……生きて戻れ。それが一番の任務だ」
@quest give q_blackrock_deep
@flag set ch3_started
@tile 26 5 > map=dungeon_b11
指名依頼「黒岩の洞穴の奥」を受けた！
@end

# ------------------------------------------------------------
#  黒岩の洞穴 B12F〜B15F
# ------------------------------------------------------------
*ch3_b12_wall
壁一面に、見たことのない文字が刻まれている。
@if party.has(mia)
  ミア「魔族の文字……少しだけ読めるわ。『……封……剣……贄……』」
@elif party.has(noa)
  ノア「ピピが怖がってる……この字、『……封……剣……贄……』って書いてあるみたい」
@else
  誰にも読めない。だが、ひどく嫌な感じがする。
@endif
@if party.has(garo)
  ガロ「贄……生贄ってことか。冒険者たちは、そのために……」
@elif party.has(rina)
  リナ「贄……まさか、さらわれた人たちは……」
@elif party.has(zara)
  ザラ「贄、ね。……胸くその悪い話だ」
@endif
@end

*ch3_b13_rod
縛られた冒険者が倒れている！
{hero}たちは急いで縄をほどいた。
冒険者ロッド「た、助かった……あんたたち、協会の……？」
冒険者ロッド「奴らは……人を集めて……奥に……運んでいった……」
冒険者ロッド「俺は途中で逃げ出して……ここで捕まって……」
@if party.has(rina)
  リナ「傷を癒やします。……もう大丈夫ですよ」
@endif
{hero}は{item.return_scroll}を広げ、ロッドを地上へ送り出した。
@effect flash white count=2
@flag set rod_rescued
光に包まれて、ロッドの姿が消えた。……巻物はまだ手元にある。
@end

*ch3_b14_door
@if flag.ch3_lost and !flag.ch4_started
  大扉は固く閉ざされている。……剣は、何も応えない。
  @end
@endif
行く手を、巨大な扉がふさいでいる。
扉には、錆びた剣と同じ紋章が刻まれている。
@effect blink hero count=4 interval=150
腰の剣が、かすかに光った――
@effect flash white
重い音を立てて、扉がひとりでに開いた。
@tile 20 1 > map=dungeon_b14
@end

# ------------------------------------------------------------
#  3-2 挫折
# ------------------------------------------------------------
*ch3_garza
@effect tint red
祭壇の上で、黒い炎が燃えている。
灰色の甲冑をまとった魔族が、祭壇の前に立っている。
ガルザ「……来たか。封剣を持つ者よ」
ガルザ「十五年。我らはその剣を探し続けた。まさか、人の子が抜くとはな」
ガルザ「剣は錆び、持ち主は未熟。――今のうちに、消えてもらう」
@effect shake h 3 600
@effect flash black count=2
@battle group=garza_1 escape=false turns=3 lose=*ch3_defeat
@goto *ch3_defeat

*ch3_defeat
ガルザ「その程度か。剣が泣いているぞ」
ガルザが手を振ると、灰色の衝撃波がパーティを襲った。
@effect flash white
@effect shake h 3 600
@party leave #2 keep=injured
{away.injured}が{hero}をかばい、倒れた――
@effect fade_out 1500
……遠くで誰かの声がする。
「――走れ、{hero}！」
@flag set ch3_lost
@tile 20 1 G map=dungeon_b14
@heal all
@map guild_infirmary 3 3 dir=down
@effect tint sepia
@wait 600
@effect fade_in 800
@goto *ch3_rescue

*ch3_rescue
@effect tint none
協会長ドルガン「気がついたか」
協会長ドルガン「洞穴の入口で倒れていたお前たちを、外で待機させていた部隊が見つけた」
協会長ドルガン「{away.injured}は……命は取り留めた。だが、しばらくは動けん」
@if party.has(garo)
  ガロ「……俺がもっと前に出ていれば」
@endif
@if party.has(mia)
  ミア「魔法が……ひとつも通じなかった」
@endif
@if party.has(rina)
  リナ「祈りが……届かなかった……」
@endif
@if party.has(jack)
  ジャック「ツキがなかった、じゃ済まないよな」
@endif
@if party.has(zara)
  ザラ「……悔しい」
@endif
@if party.has(noa)
  ノア「ピピがずっと震えてる……」
@endif
@choice
  - ……もう一度、行く
  - 僕のせいだ
@if choice == 2
  協会長ドルガン「違う。自分を責めるな。責めるなら、弱さを責めろ」
@endif
協会長ドルガン「あの魔族はお前の剣を『封剣』と呼んだそうだな」
協会長ドルガン「風見の神殿の司祭なら、何か知っているかもしれん。北東の山の上だ」
協会長ドルガン「洞穴前の東の落石は、騎士団にどけさせた。そこから山道を登れ」
@tile 27 8 . map=field_blackrock
@tile 29 8 = map=field_blackrock
@end

# ------------------------------------------------------------
#  3-3 強化開始（風見の神殿）
# ------------------------------------------------------------
# 洞穴前の東：3 章でガルザに敗れるまでは落石でふさがっている
*ch3_rockslide
東の岩山への道は、大きな落石でふさがっている。
@end

*ch3_snow_off
@effect snow off
@end

*ch3_mountain_enter
@effect snow on density=1
@if !flag.ch3_mountain_seen
  @flag set ch3_mountain_seen
  冷たい風が吹きつける。山の上に、古い神殿が見える。
@endif
@end

*ch3_temple
司祭オルド「よくぞ参られた。……その剣を、見せていただけますかな」
{hero}は錆びた剣を差し出した。
司祭オルド「……間違いない。封剣アストラ。三百年前、勇者レオンが魔を封じた剣です」
司祭オルド「剣は持ち主の心と共に目覚める。錆は、剣が眠っている証」
司祭オルド「この神殿の奥には、剣を目覚めさせるための試練の間が三つあります」
司祭オルド「ただし試練は、一人ひとりが己と向き合うもの。仲間の力は借りられませぬ」
司祭オルド「お仲間には、別室で修行をしていただきましょう」
@flag set ch3_temple_met
北の三つの扉の先が、試練の間だ。（左から 勇気・慈愛・絆）
@end

*ch3_trial_door
司祭オルドの話を聞こう。
@end

*ch3_altar_talk
祭壇に祈りを捧げた。……体が軽くなった気がする。
@heal all
@end

*ch3_acolyte_talk
@if flag.ch3_done
  修道士「封剣の勇者に、風の加護がありますように」
@else
  修道士「試練の間では、仲間の手は届きません。あなた自身の心だけが頼りです」
@endif
@end

*ch3_ord_talk
@if flag.ch3_done
  司祭オルド「急ぎなさい。儀式が完成すれば、蝕王ヴェルムが蘇る」
  @end
@endif
@if !flag.ch3_temple_met
  @goto *ch3_temple
@endif
@if flag.trial1_done and flag.trial2_done and flag.trial3_done
  @goto *ch3_return_member
@endif
司祭オルド「試練の間は北の三つの扉の先。勇気・慈愛・絆――すべてを越えなさい」
@if flag.trial1_done
  勇気の間：越えた
@else
  勇気の間：まだ
@endif
@if flag.trial2_done
  慈愛の間：越えた
@else
  慈愛の間：まだ
@endif
@if flag.trial3_done
  絆の間：越えた
@else
  絆の間：まだ
@endif
@end

# ---- 勇気の間：自分の影と一人で戦う
*ch3_trial_1
@if flag.trial1_done
  鏡には、自分の姿が映っている。
  @end
@endif
大きな鏡がある。……鏡の中の{hero}が、にやりと笑った。
影の{hero}「お前は弱い。仲間ひとり守れなかった」
影の{hero}「その剣を持つ資格があるか、試してやる」
@battle group=shadow members=hero escape=false lose=*ch3_trial_1_lost
影は、鏡の中へ溶けるように消えた。
@effect flash white count=2
@item replace rusty_sword awakening_sword
@skill add hero fuukouzan
@flag set trial1_done
@heal all
剣の錆が少し落ちた！　{item.awakening_sword}になった！
{hero}は「封光斬」を覚えた！
@end

*ch3_trial_1_lost
影の{hero}「……まだだ。出直してこい」
影は鏡の中へ戻っていった。
@heal all
@end

# ---- 慈愛の間：傷ついた魔物の子
*ch3_trial_2
部屋の奥に、傷ついた魔物の子がうずくまっている。
魔物の子は、震えながらこちらをにらんでいる。
@choice
  - 手当てしてやる
  - 剣を向ける
@if choice == 1
  @flag set helped_pup
  {hero}は傷に布を巻いてやった。魔物の子は小さく鳴いて、光の中へ消えていった。
  @stat hero luk +2
  運が 2 上がった！
@else
  {hero}が剣を向けると、魔物の子は霧のように消えた。
  ……胸の奥に、小さな痛みが残った。
@endif
@flag set trial2_done
@stat hero hp +20
@effect flash white
最大 HP が 20 上がった！
@end

# ---- 絆の間：仲間の幻影
*ch3_trial_3
@if flag.trial3_done
  鏡には、仲間たちの笑顔が映っている気がした。
  @end
@endif
鏡の中に、仲間たちの姿が浮かび上がった。
仲間の幻影「お前のせいで、傷ついた」
仲間の幻影「お前と一緒にいたから、倒れたんだ」
@goto *ch3_trial_3_ask

*ch3_trial_3_ask
@choice
  - ……ごめん
  - 一人で行く
  - それでも一緒に行きたい
@if choice == 1
  仲間の幻影「謝って、どうなる」
  @goto *ch3_trial_3_ask
@elif choice == 2
  仲間の幻影「一人で勝てなかったのは、誰だ」
  @goto *ch3_trial_3_ask
@endif
……幻影たちが、ふっと笑った気がした。
幻影は光の粒になって消えた。
@effect flash white count=2
@flag set trial3_done
これで三つの試練を越えた。司祭オルドのもとへ戻ろう。
@end

# ---- 仲間の復帰
*ch3_return_member
@effect snow off
神殿の扉が開き、見覚えのある顔が入ってくる。
@if away.injured == garo
  ガロ「……待たせたな」
  ガロ「寝てる間、ずっと考えてた。次は、絶対に負けない」
@elif away.injured == mia
  ミア「……待たせちゃったね」
  ミア「寝てる間、ずっと考えてた。次は、絶対に負けない」
@elif away.injured == rina
  リナ「……お待たせしました」
  リナ「眠っている間、ずっと考えていました。次は、絶対に負けません」
@endif
@party return injured
{hero}たちは、ふたたび全員そろった！
仲間たちも、神殿の別室での修行で新しい技を身につけた。
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
@goto *ch3_legend

# ------------------------------------------------------------
#  3-4 最強の敵の話
# ------------------------------------------------------------
*ch3_legend
@effect tint sepia
司祭オルド「三百年前、この地に『三柱の魔』と呼ばれる者たちが現れました」
司祭オルド「大地を喰らう『蝕王』、空を裂く『嵐王』、海を枯らす『渇王』」
司祭オルド「勇者レオンは蝕王を封剣で封じました。残る二柱は、いずこかへ姿を消したといいます」
司祭オルド「ガルザなる魔族は、蝕王の配下でしょう。人を集めているのは……封印を解く『贄』とするため」
@effect tint none
司祭オルド「冒険者たちの失踪……すべて繋がっておりますな」
ガルザの声が、耳の奥によみがえる。――十五年。我らはその剣を探し続けた――
司祭オルド「封印は剣と対になっている。剣が目覚めた今、封印もまた揺らいでいるのです」
司祭オルド「急ぎなさい。儀式が完成すれば、蝕王ヴェルムが蘇る」
@flag set ch3_done
@effect typewriter "第3章　完"
@save_point
協会長ドルガンのもとへ戻ろう。
@end
