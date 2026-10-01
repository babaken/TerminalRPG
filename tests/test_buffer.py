from trpg.term import CONT, Buffer, Rect, Style


def cells(buf, y):
    return [c[0] for c in buf.rows[y]]


def test_put_wide():
    b = Buffer(6, 1)
    end = b.put(0, 0, "aあb")
    assert end == 4
    assert cells(b, 0) == ["a", "あ", CONT, "b", " ", " "]


def test_overwrite_left_half_of_wide():
    b = Buffer(4, 1)
    b.put(0, 0, "あい")
    b.put(2, 0, "x")             # 「い」の左半分を上書き
    assert cells(b, 0) == ["あ", CONT, "x", " "]


def test_overwrite_right_half_of_wide():
    b = Buffer(4, 1)
    b.put(0, 0, "あい")
    b.put(1, 0, "x")             # 「あ」の右半分を上書き
    assert cells(b, 0) == [" ", "x", "い", CONT]


def test_wide_over_two_wides():
    b = Buffer(6, 1)
    b.put(0, 0, "あいう")
    b.put(1, 0, "え")            # あ の右半分 + い の左半分
    assert cells(b, 0) == [" ", "え", CONT, " ", "う", CONT]


def test_wide_at_right_edge_becomes_space():
    b = Buffer(3, 1)
    b.put(0, 0, "aあい")
    assert cells(b, 0) == ["a", "あ", CONT]
    b2 = Buffer(3, 1)
    b2.put(2, 0, "あ")
    assert cells(b2, 0) == [" ", " ", " "]


def test_clip():
    b = Buffer(10, 2)
    b.put(0, 0, "あいうえお", clip=Rect(3, 0, 4, 1))
    # あ(0-1)は範囲外、い(2-3)は右半分だけ→空白、う(4-5)は表示、え(6-7)は左半分だけ→空白
    assert cells(b, 0) == [" ", " ", " ", " ", "う", CONT, " ", " ", " ", " "]
    # クリップ外の行には書かない
    b.put(0, 1, "abc", clip=Rect(0, 0, 10, 1))
    assert b.row_text(1).strip() == ""


def test_combining_char_attaches():
    b = Buffer(4, 1)
    b.put(0, 0, "が")
    assert b.rows[0][0][0] == "が"


def test_box_and_fill():
    b = Buffer(6, 3)
    inner = b.box(Rect(0, 0, 6, 3), title="")
    assert inner == Rect(1, 1, 4, 1)
    assert b.row_text(0) == "┌────┐"
    assert b.row_text(2) == "└────┘"
    b.fill(Rect(1, 1, 4, 1), "x")
    assert b.row_text(1) == "│xxxx│"


def test_fill_breaks_wide_on_edges():
    b = Buffer(6, 1)
    b.put(0, 0, "あいう")
    b.fill(Rect(1, 0, 4, 1), ".")
    assert cells(b, 0) == [" ", ".", ".", ".", ".", " "]


def test_put_lines_transparent():
    b = Buffer(5, 1)
    b.put(0, 0, "xxxxx")
    b.put_lines(0, 0, ["a b"], transparent=True)
    assert b.row_text(0) == "axbxx"


def test_map_styles():
    b = Buffer(2, 1)
    b.put(0, 0, "ab", Style.of("red"))
    b.map_styles(lambda st: st._replace(fg=4))
    assert all(c[1].fg == 4 for c in b.rows[0])
