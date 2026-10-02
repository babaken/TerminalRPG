# ============================================================
#  FirstQuest  第3章　灰の影
#  元テキスト: docs/scenario/FirstQuest_story.md（第3章）
#  現在: 3-1 調査へ 〜 3-2 挫折（医務室）まで
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
@if flag.ch3_lost
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
（風見の神殿は制作中です。次の更新で続きを遊べるようになります）
@end
