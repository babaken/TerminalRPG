# HelloQuest  scenario.sco

*start
@chapter 1 "はじめての冒険"
@map village 9 6 dir=up
@effect fade_in 600
村長「おお、{hero}。ちょうどよいところに来た」
村長「北の草原に大きなスライムが住みついて困っておる。退治してくれんか」
@flag set got_quest
@end

*elder_talk
@if flag.boss_done
  村長「ありがとう、{hero}！　村の英雄じゃ」
  @goto *ending
@elif flag.got_quest
  村長「大スライムは北の草原の奥じゃ。気をつけてな」
@endif
@end

*shop_talk
道具屋「いらっしゃい！」
@shop village_shop
@end

*boss
地面がぶるぶると揺れた……！
大スライムがあらわれた！
@battle group=boss escape=false
@flag set boss_done
大スライムをやっつけた！　村長に知らせよう。
@end

*ending
@effect starfall count=6
村に、平和が戻った。
@ending text="{hero}の冒険は、まだ始まったばかり"
