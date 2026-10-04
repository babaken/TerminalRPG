# ============================================================
#  FirstQuest+  scenario.sco
#  元テキスト: docs/scenario/FirstQuestPlus_story.md（1・2章は FirstQuest_story.md に伏線の差分を加えたもの）
#  FirstQuest をもとに、伏線（夢・老婆テラ・黒い閃光・手加減する魔物・母の秘密）を加えている。伏線のフラグは p_ で始まる
#  現在: 第1章、第2章（ch2.sco）、第3章（ch3.sco）。第4章は差し替え中（M8 8-4）
# ============================================================

# ------------------------------------------------------------
#  1-1 錆びた剣を拾う
# ------------------------------------------------------------
*start
@chapter 1 "出会いと旅立ち"
@effect fade_out 10
@effect typewriter "第1章　出会いと旅立ち"
@map house_hero 4 3 dir=down
@effect fade_in 600
窓から朝の光が差し込んでいる。

ミナ「おにいちゃん、おきてー！　カイにいちゃんが来てるよー！」
ミナ「……おにいちゃん、きょうもへんなゆめみた？」
@choice
  - ……どうして？
  - 見てないよ
ミナ「ねごとで『ゼノ』っていってたよー」
ミナ「ゼノってだれー？」
@flag set p_dream_1
@end

# 家から初めて外に出たとき（Map.data の auto イベント）
*ch1_kai_invite
@flag set ch1_invited
@face kai
カイ「おっそいぞ{hero}！　今日は森で探検するって約束だろ？」
カイ「北の『囁きの森』、奥に古い石の祠があるって爺ちゃんが言ってたんだ。見に行こうぜ！」
@choice
  - 行こう！ → *ch1_invite_yes
  - 奥は立入禁止だよ → *ch1_invite_no

*ch1_invite_yes
カイ「さすが{hero}！　そうこなくっちゃ！」
@goto *ch1_invite_end

*ch1_invite_no
カイ「ちょっとだけだって。夕方までに戻れば大丈夫さ！」

*ch1_invite_end
カイ「村の北の出口で待ってるからな！」
@end

# ---- 村の人々 ----
*ch1_kai_talk
@if flag.ch1_invited
  カイ「北の出口から森に行けるぞ。早く来いよ！」
@else
  カイ「おーい、まだ寝ぼけてんのか？」
@endif
@end

*ch1_mother_talk
@if flag.p_family_accept
  母「いってらっしゃい、{hero}。……あなたの帰る場所は、ここよ」
  @end
@endif
@if flag.ch1_farewell
  母「体に気をつけるのよ。……いってらっしゃい」
@elif flag.ch1_raid
  母「外が騒がしいわ……{hero}、気をつけて」
@elif flag.ch1_family_done
  母「ゆうべはよく眠れた？」
@elif flag.got_herbs
  母「日が暮れる前に帰ってきてね」
@else
  母「森へ行くの？　奥へは入っちゃだめよ」
  母「これを持っていきなさい。転んだら使うのよ」
  @item add herb 2
  @flag set got_herbs
  やくそうを 2 つ受け取った。
@endif
@end

*ch1_mina_talk
@if flag.p_family_accept
  ミナ「おにいちゃんは、おにいちゃんだもん！」
  @end
@endif
@if flag.ch1_farewell
  ミナ「おにいちゃん、ぜったい かえってきてね！」
@elif flag.ch1_raid
  ミナ「こわいよう……」
@elif flag.found_sword
  ミナ「おにいちゃんの けん、かっこいいー！」
@else
  ミナ「ミナもいつか森いく！」
@endif
@end

*ch1_farmer_talk
畑のおじさん「最近、北のほうで見慣れない獣の足跡を見たな。気をつけろよ」
@end

# ---- 老婆テラ（村の東の小屋。15年前、森で赤子の{hero}を見つけた）
*p1_tera_talk
@if flag.p3_tera_done
  テラ「森の祠、村の丘、ベルンの協会。……一人で行くんだよ」
  @end
@endif
@if flag.p_family_accept
  @goto *p3_tera
@endif
@if flag.p3_home_open
  テラ「まずは家にお帰り。エマが待ってるよ」
  @end
@endif
@if flag.ch1_raid_done
  テラ「……とうとう、来ちまったんだね」
  テラ「坊や。何があっても、お前さんはロイとエマの子だよ。それだけは忘れるんじゃない」
@elif flag.found_sword
  テラ「その剣……祠の剣を抜いたのかい」
  テラ「……そうかい。時が来たってことかねぇ」
  テラ「夢を見たら、目を覚ましたあとに、家族の顔を思い浮かべるんだよ。いいね」
@elif flag.p_tera_1
  テラ「祠には近づくんじゃないよ。……年寄りの言うことは聞いておくもんさ」
@else
  テラ「おや、ロイのところの坊やかい。……大きくなったねぇ」
  テラ「森へ行くのかい。……祠には近づくんじゃないよ。あそこは、お前さんを……」
  テラ「……いや、なんでもない。年を取ると、口がすべっていけないね」
  @flag set p_tera_1
@endif
@end

*ch1_south_gate
@if flag.ch1_farewell
  @flag set ch1_left_village
  @map field_road 15 1 dir=down transition=fade
  村を背に、{hero}は街道を歩き出した。
@else
  ……今は村を出る理由がない。
  @hero move 0 -1
@endif
@end

# ---- 囁きの森 ----
*ch1_forest_enter
カイ「うわー、やっぱ森は気持ちいいな！」
カイ「よし、どっちが先に祠を見つけるか競争だ！」
@npc kai_forest move 0 -6
@npc kai_forest hide
……カイの足音が遠ざかっていく。

@effect tint night
しばらく歩くうちに、木々が深くなってきた。
「カイ…？」
返事はない。風が葉を揺らす音だけが聞こえる。
@flag set lost_friend
@end

*ch1_kai_forest_talk
カイ「祠はきっと奥のほうだ！」
@end

*ch1_find_sword
苔むした石の祠がある。
祠の前の地面に、何かが突き刺さっている。
……\w500剣だ。\w300ひどく錆びている。
@choice
  - 抜いてみる → *ch1_pull_sword
  - やめておく → *ch1_hesitate_sword

*ch1_hesitate_sword
……でも、なぜか目が離せない。

*ch1_pull_sword
@effect shake h 1 300
柄を握った瞬間、頭の奥で声がした。
@effect flash black count=2
@effect tint invert
\c[gray]『――見つけた』\c[]
@wait 400
@effect tint night
……気のせいだろうか。
@item add rusty_sword
@equip hero rusty_sword
@flag set found_sword
@effect tint none
\c[bright_yellow]{item.rusty_sword}\c[]を手に入れた！　（そのまま装備した）
柄には見慣れない紋章が刻まれている。
……目を閉じた人の顔のようにも見える。
@call *ch1_reunion
@end

*ch1_reunion
@npc kai_forest show
@npc kai_forest move 4 -4
@face kai
カイ「{hero}！！　よかった、どこ行ってたんだよ！」
カイ「途中で振り返ったらいなくてさ…マジで焦ったんだぞ！」
@choice
  - ごめん、迷ってた
  - カイが置いていったんだろ
@if choice == 1
  カイ「…ったく。無事ならいいけどさ」
@else
  カイ「う…それは、ごめん」
@endif
カイ「ん？　その剣どうしたんだ？　ボロボロじゃん」
カイ「祠で拾った？　すげー！　なんか伝説の剣っぽい！」
カイ「……いや、錆びすぎか。ははっ」
カイ「もう日が暮れる。帰ろうぜ」
@face none
@flag set ch1_forest_done
@call *ch1_family
@return

# ---- 家族団らん ----
*ch1_family
@effect fade_out 600
@npc kai_forest hide
@effect tint night
@map house_hero 5 3 dir=up
@effect fade_in 600
母「おかえりなさい。今日はシチューよ」
ミナ「おにいちゃん、なにそれー？　けんー？」
父「…見せてみろ」
父「……古いな。だが、刃筋はまっすぐだ。手入れすれば使えるかもしれん」
父「森の奥に入ったな？」
@choice
  - …ごめんなさい
  - カイと一緒だったから
@if choice == 1
  父「…無事ならいい」
@else
  母「まったく、あの子ったら」
@endif
ミナ「ミナもいつか森いく！」
母「ふふ。ミナはもう少し大きくなってからね」
温かい夕食の時間が過ぎていく。
@effect fade_out 800
――その夜、{hero}は夢を見た。
灰色の影が、遠くからこちらを見ている夢を。
影は、{hero}と同じ顔をしていた。
@effect flash black count=1 interval=200
@effect tint none
@flag set ch1_family_done
@map house_hero 5 3 dir=down
@heal all
@effect fade_in 800
――翌朝。ぐっすり眠って、体の疲れはすっかり取れた。
@effect shake h 3 800
\c[bright_red]ドォン！！\c[]
外から大きな音がした！
母「な、何の音…？」
父「……{hero}、ここにいろ」
@flag set ch1_raid
@return

# ---- 家の人々（夜以降）----
*ch1_father_talk
@if flag.p_family_accept
  父「……剣の手入れを、怠るな」
  @end
@endif
@if flag.ch1_farewell
  父「振り返るな。前だけ見て進め」
@elif flag.ch1_raid
  父「……外の様子を見てくる。お前は――いや、もう止めても聞かんか」
@else
  父「…剣は毎日布で拭いてやれ。錆は少しずつしか落ちん」
@endif
@end

# ------------------------------------------------------------
#  1-2 村を追い出される
# ------------------------------------------------------------
*ch1_raid
@effect shake h 3 600
村人「モ、モンスターだ！　森からモンスターが！」
狼のような魔物たちが、まっすぐこちらへ向かってくる。
村人「お、おい…あいつら、{hero}だけを見てないか…？」
@effect flash red count=2
@battle group=raid_wolves escape=false target_only=hero gameover=title
@flag set ch1_raid_done
……妙だった。魔物は{hero}に飛びかかっても、牙を立てようとはしなかった。
まるで、手加減されているように。
シャドウウルフは最後に{hero}の服をくわえ、森のほうへ引きずろうとして――
黒い霧になって消えた。

@effect rain on
村人たちが、遠巻きにこちらを見ている。
村人「…見たか？　魔物はあの子を連れていこうとしてた」
村人「襲うんじゃない、連れていこうとしてたんだ……」
村人「あの子、魔物の仲間なんじゃないのか…？」
カイ「ち、違う！　{hero}は村を守ってくれたんだろ！」
村長「……みな、静かに」
村長「{hero}。話がある。あとでわしの家に来てくれんか」
@flag set ch1_need_meeting
@end

*ch1_villager_a
村人「……近寄らないでくれ。魔物の仲間なんだろう？」
@end

*ch1_villager_b
村人「あんたのせいで、子どもたちが怖がって外に出られないんだ」
@end

*ch1_villager_c
村人「……助けてくれたことには、礼を言う。でも……」
@end

*ch1_meeting
村長の家には、父の姿もあった。
村長「……{hero}。お前を責めるつもりはない」
村長「じゃが、魔物はまたお前を狙って来るじゃろう。そのとき、村の者が巻き込まれん保証はない」
父「村長、それは……！」
村長「ロイ、わしも辛い。じゃが、わしは村長じゃ」
村長「……{hero}。村を出てくれんか」
@choice
  - …わかりました
  - 僕は何もしていない！
@if choice == 2
  村長「わかっておる。わかっておるのじゃ……」
  村長「それでも、わしは村を守らねばならん」
@endif
父「……{hero}、家に戻るぞ」
@flag set ch1_meeting_done
@effect fade_out 600
@map house_hero 5 4 dir=up
@effect fade_in 600
@goto *ch1_farewell

*ch1_chief_wife_talk
@if flag.ch1_meeting_done
  村長の奥さん「……ごめんなさいね。あの人も、本当はつらいのよ」
@elif flag.ch1_raid
  村長の奥さん「主人が待っていたわ。奥へどうぞ」
@else
  村長の奥さん「あら{hero}ちゃん。主人なら外で村を見回っていますよ」
@endif
@end

*ch1_chief_home_talk
@if flag.ch1_meeting_done
  村長「……すまぬ。お前の無事を、毎日祈っておる」
@else
  村長「……座ってくれ」
@endif
@end

*ch1_chief_talk
@if flag.found_sword
  村長「祠の剣を抜いた、じゃと……？　……そうか」
@else
  村長「囁きの森の奥には昔から近づくなと言い伝えがある。理由？　…わしも知らん」
@endif
@end

*ch1_farewell
母「……これを持っていきなさい」
@gold add 50
@item add herb 3
@item add traveler_clothes
@equip hero traveler_clothes
50 G と {item.herb} 3 つ、{item.traveler_clothes}を受け取った。　（服はそのまま着替えた）
母「あなたは何も悪くない。それだけは忘れないで」
母「……{hero}。あなたが帰ってきたら、話さなきゃいけないことがあるの」
母「今はまだ……ごめんなさい」
父「エマ」
母「……ええ、わかってる」
@flag set p_mother_secret
父「ベルンへ行け。街道を南だ。あそこには冒険者協会がある。腕があれば食っていける」
父「……剣の手入れを怠るな」
ミナ「おにいちゃん、どこいくの？　すぐかえってくる？」
@choice
  - すぐ帰ってくるよ
  - …ミナ、母さんを頼むな
@if choice == 1
  ミナ「やくそくだよ！」
@else
  ミナ「うん…！」
@endif
@flag set ch1_farewell
@effect fade_out 500
@map village_lito 15 15 dir=down
@effect fade_in 500
カイ「{hero}！」
カイ「……ごめん。俺が森に誘わなきゃ」
カイ「でも、お前があの剣を拾ったのは、きっと意味があるんだって俺は思う」
カイ「いつか、すげー冒険者になって帰ってこいよ。村のみんなを見返してやれ！」
@effect rain off
@effect starfall count=6 ms=2500
一筋の流れ星が、南の空へ流れていった。
@end

*ch1_kai_gate_talk
カイ「ほら、行ってこい！　手紙くらい寄こせよな！」
@end

# ------------------------------------------------------------
#  1-3 旅立ち（街道）
# ------------------------------------------------------------
*ch1_road_north
@if flag.p3_home_open
  @map village_lito 15 16 dir=up
  @end
@endif
……今は戻れない。
@hero move 0 1
@end

*ch1_signpost
立て札「北　リト村　／　南　交易都市ベルン」
@end

*ch1_road_merchant
商人「おや、旅の人かい？　この先のベルンまではもうすぐだよ」
商人「道中のお供にどうだい？」
@shop road_merchant
@end

# ------------------------------------------------------------
#  1-3 旅立ち（交易都市ベルン）
# ------------------------------------------------------------
*ch1_gate
門番ハンス「おう、止まれ。見ねぇ顔だな。どっから来た？」
「……リト村から」
門番ハンス「リト村？　あんな北の村から一人でか。…その剣、ずいぶん年季が入ってんな」
門番ハンス「で、何の用だ？」
@choice
  - お金を稼ぎたい
  - 仕事を探している
門番ハンス「なら話は早ぇ。腕に覚えがあるなら冒険者になるこった」
門番ハンス「冒険者協会で登録すりゃ、依頼をこなして金がもらえる。宿代くらいはすぐ稼げるさ」
門番ハンス「協会の場所？　街のもんに聞きな。俺は門から離れられねぇんでな。ははっ」
@flag set ch1_gate_talked
@end

*ch1_guard_talk
@if flag.guild_registered
  門番ハンス「おう、冒険者になったか！　街道のスライム退治なんかは手頃だぞ」
@else
  門番ハンス「協会の場所なら、そのへんの街のもんに聞きな」
@endif
@end

*ch1_bread_talk
@if !flag.ch1_know_guild
  パン屋の娘「冒険者協会？　広場の西、剣と盾の看板の大きな建物よ！」
  パン屋の娘「はい、これおまけ。焼きたてなの！」
  @item add bread
  {item.bread}をもらった。
  @flag set ch1_know_guild
@elif quest.q_lost_cat == active and !flag.found_cat
  パン屋の娘「うちのミケ、見なかった？　あの子、狭くて暗いところが好きなの……」
@elif flag.found_cat
  パン屋の娘「ミケを見つけてくれたのね！　本当にありがとう！」
@else
  パン屋の娘「冒険者協会は広場の西よ。がんばってね！」
@endif
@end

*ch1_patrol_talk
兵士「広場の見回り中だ。最近は街道に魔物が増えている。気をつけてな」
@end

*ch1_trader_talk
商人「ベルンは交易の街だ。北の村々と南の港を結んでる。品物も人も集まるのさ」
@end

*ch1_oldman_talk
老人「若いの、冒険者になるのかね。最近は物騒じゃ、無茶はせんことじゃ」
@end

*ch1_child_talk
@if quest.q_lost_cat == active and !flag.found_cat
  子ども「ねこ？　さっき南西の裏路地に入っていったよ！」
@else
  子ども「協会長のドルガンさんって、片目でドラゴン倒したんだって！」
@endif
@end

*ch1_item_keeper
@if quest.q_delivery == active and !flag.got_package
  道具屋「おっ、協会の依頼を受けてくれたのかい。これを旅鳥亭の主人に頼むよ」
  @item add package
  @flag set got_package
  {item.package}を預かった。
@else
  道具屋「いらっしゃい！」
  @if chapter >= 4
    道具屋「国の倉庫から、よく効く薬が入ったよ！」
    @shop town_item_4
  @else
    @shop town_item
  @endif
@endif
@end

*ch1_weapon_keeper
武具屋「冒険者なら装備はケチるなよ。命あっての物種だ」
@if chapter >= 4
  武具屋「国の注文で鎖帷子を打ったんだ。決戦に行くなら持っていけ」
  @shop town_weapon_4
@else
  @shop town_weapon
@endif
@end

*ch1_cat
猫「……にゃー」
鈴のついた三毛猫が、木箱の陰からこちらを見ている。
@choice
  - そっと抱き上げる
  - 様子を見る
@if choice == 1
  ミケはおとなしく腕の中におさまった。
  @flag set found_cat
  パン屋の娘に届けてあげた。協会に報告しよう。
@else
  猫はこちらをじっと見ている。
@endif
@end

# ---- 冒険者協会 ----
*ch1_sera_talk
@if !flag.guild_registered
  受付セラ「冒険者協会ベルン支部へようこそ。ご依頼ですか？　それとも登録ですか？」
  「登録したい」
  受付セラ「かしこまりました。お名前は……{hero}さんですね」
  受付セラ「登録料はいただいていません。ランクは F から始まって、依頼をこなすと上がっていきます」
  @item add adventurer_card
  @flag set guild_registered
  @effect flash white
  {item.adventurer_card}を受け取った！　冒険者ランク F になった！
  受付セラ「依頼は私に声をかけてくだされば紹介します。達成したら、ここで報告してくださいね」
  @guild
@elif var.ch1_quests >= 3 and !flag.ch1_done
  @goto *ch1_recruit
@elif quest.q_mole == active and !flag.mole_defeated
  受付セラ「カブラ村の依頼、よろしくお願いしますね。村はベルンの南門を出てすぐです」
  @guild
@elif quest.q_blackrock == active and !flag.ch2_found_scroll
  受付セラ「黒岩の洞穴は、東門を出た先の岩山です。……どうか、無事に戻ってきてくださいね」
  @guild
@else
  受付セラ「お疲れさまです、{hero}さん」
  @guild
@endif
@end

*ch1_quest_done
@var ch1_quests += 1
@if var.ch1_quests == 3
  受付セラ「{hero}さん、依頼を 3 つもこなすなんて順調ですね！」
  受付セラ「……少しお話があるので、あとでもう一度声をかけてください」
@endif
@end

*ch1_recruit
受付セラ「{hero}さん、順調ですね！」
受付セラ「そろそろ一人では厳しい依頼も増えてきます。仲間を探してみてはいかがでしょう？」
受付セラ「ちょうど、パーティを探している冒険者が 3 人いるんです。紹介料として 100 G いただきますが……」
@if gold < 100
  受付セラ「……お金が貯まったら、また声をかけてくださいね」
  @guild
  @end
@endif
@choice
  - 紹介してもらう
  - またにする
@if choice == 2
  受付セラ「わかりました。いつでもどうぞ」
  @guild
  @end
@endif
@gold remove 100
100 G を支払った。
@recruit garo mia rina pick=1
@if party.has(garo)
  ガロ「よろしく頼む。…その剣、錆びてるがいい剣だな」
@elif party.has(mia)
  ミア「よろしくね。その剣の紋章…どこかで見た気がするのよね」
@else
  リナ「神のお導きに感謝します。…不思議な気配のする剣ですね」
@endif
受付セラ「いいパーティになりそうですね。これからもよろしくお願いします！」
@flag set ch1_done
@effect typewriter "第1章　完"
@save_point
@goto *ch2_start

*ch1_adv_a_talk
@if flag.ch1_done
  冒険者「仲間ができたか。……最近、腕のいい連中が戻ってこないって噂だ。気をつけろよ」
@else
  冒険者「新入りか？　最初はやくそう集めでもして、街道に慣れるといい」
@endif
@end

*ch1_adv_b_talk
冒険者「スライムは火に弱い。魔法使いがいると楽だぞ」
@end

# ---- 宿屋 ----
*ch1_innkeeper_talk
@if quest.q_delivery == active and flag.got_package and !flag.package_delivered
  宿の主人「おお、道具屋の荷物だね。助かったよ！　協会にもよろしく伝えておくれ」
  @item remove package
  @flag set package_delivered
  荷物を届けた。協会に報告しよう。
@else
  @inn 10
@endif
@end

*ch1_traveler_talk
旅人「南の港町まで行くんだ。ベルンの宿は安くていいよ」
@end

# ---- ロードしたとき（つづきから・全滅からの「セーブから」） ----
# 1章の最後のセーブは 2 章を始める前に保存されるので、そこから再開したら 2 章を始める
*on_load
@if flag.ch1_done and !flag.ch2_rumor
  @goto *ch2_start
@endif
@end

# ---- アイテム ----
*use_return_scroll
@if !map.dungeon
  {item.return_scroll}は、ここでは使えない。
  @end
@endif
{hero}は{item.return_scroll}を広げた。
@effect flash white count=2
@effect fade_out 400
@map town_bern 7 8 dir=down
@effect fade_in 500
ベルンの街に戻ってきた。
@end

@include "ch2.sco"
@include "ch3.sco"
@include "ch4.sco"
