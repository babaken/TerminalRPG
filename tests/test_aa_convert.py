"""3-2：AA 変換ツールのテスト。"""
import pytest

pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

from trpg.data import Report, load_game_data  # noqa: E402
from trpg.package import open_package  # noqa: E402
from trpg.term.width import char_width, text_width  # noqa: E402
from trpg.tools.aa_convert import (  # noqa: E402
    ConvertError, Options, convert, convert_file, main, nearest_color, preview)


def slime(path=None):
    im = Image.new("RGBA", (200, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((20, 30, 180, 150), fill=(40, 200, 60, 255))
    d.ellipse((60, 60, 85, 85), fill=(255, 255, 255, 255))
    d.ellipse((115, 60, 140, 85), fill=(255, 255, 255, 255))
    if path:
        im.save(path)
    return im


def square_on_white():
    im = Image.new("RGB", (100, 100), "white")
    ImageDraw.Draw(im).rectangle((25, 25, 75, 75), fill="black")
    return im


def test_width_and_transparency():
    lines, colors = convert(slime(), Options(width=24, trim=False))
    assert colors == []
    assert all(len(s) == 24 for s in lines)
    assert len(lines) == round(160 / 200 * 24 * 0.5)
    assert lines[0].strip() == ""                       # 上の透明な部分は空白
    lines, _ = convert(slime(), Options(width=24))
    assert lines[0] and lines[0] == lines[0].rstrip() and min(len(s) - len(s.lstrip()) for s in lines) == 0


def test_brightness_and_invert():
    lines, _ = convert(square_on_white(), Options(width=20, trim=False))
    mid = lines[len(lines) // 2]
    assert mid[0] == "@" and mid[10] == " "             # 明るい → 濃い文字、黒 → 空白
    lines, _ = convert(square_on_white(), Options(width=20, invert=True))
    assert len(lines) <= 6 and lines.count("@" * 10 + ".") >= 4      # 反転：黒い四角だけが残る（縁は中間の濃さ）


def test_edges_and_outline():
    lines, _ = convert(square_on_white(), Options(width=20, invert=True, outline=True))
    text = "\n".join(lines)
    assert "|" in text and "-" in text and "@" not in text
    assert set(lines[len(lines) // 2].strip()) == {"|", " "} or lines[len(lines) // 2].strip()[0] == "|"
    lines, _ = convert(square_on_white(), Options(width=20, invert=True, edges=True))
    assert "@" in "".join(lines) and "|" in "".join(lines)


def test_wide_charset():
    lines, _ = convert(slime(), Options(width=30, charset="wide"))
    for s in lines:
        assert all(char_width(c) == 2 or c == " " for c in s)
        assert text_width(s) <= 30
    lines, _ = convert(slime(), Options(width=30, chars=" .oO"))
    assert set("".join(lines)) <= set(" .oO")
    with pytest.raises(ConvertError):
        convert(slime(), Options(chars="a"))
    with pytest.raises(ConvertError):
        convert(slime(), Options(chars=" あa"))
    with pytest.raises(ConvertError):
        convert(slime(), Options(width=2))


def test_color_file_matches_aa():
    lines, colors = convert(slime(), Options(width=24, color=True))
    assert "G" in "".join(colors) or "g" in "".join(colors)
    assert "W" in "".join(colors)                       # 目は白
    for s, c in zip(lines, colors):
        assert len(c) <= len(s)
        for ch, code in zip(s, c):
            assert (code == ".") == (ch == " ")
    assert nearest_color((10, 10, 10)) == "K"            # 黒は背景に溶けるので使わない
    assert "\x1b[92m" in preview(lines, colors) or "\x1b[32m" in preview(lines, colors)


def test_cli_writes_files_that_engine_reads(sample_dir, tmp_path, capsys):
    src = tmp_path / "img"
    src.mkdir()
    slime(src / "blob.png")
    square_on_white().save(src / "box.jpg")
    (src / "note.txt").write_text("x", encoding="utf-8")
    aa = sample_dir / "aa"
    assert main([str(src), "-d", str(aa), "-w", "16", "--color"]) == 0
    assert (aa / "blob.txt").exists() and (aa / "blob.color").exists() and (aa / "box.txt").exists()
    assert main([str(src / "blob.png"), "-d", str(aa)]) == 1          # 上書きしない
    assert "--force" in capsys.readouterr().err
    assert main([str(src / "blob.png"), "-d", str(aa), "--force", "--color"]) == 0

    edit_enemy = sample_dir / "Enemy.data"
    s = edit_enemy.read_text(encoding="utf-8")
    edit_enemy.write_text(s.replace('aa = "aa/slime.txt"', 'aa = "aa/blob.txt"', 1), encoding="utf-8")
    rep = Report()
    with open_package(sample_dir, rep) as pkg:
        gd = load_game_data(pkg, rep)
    assert rep.ok and not rep.warnings, rep.format()
    assert gd.aa_color["aa/blob.txt"]


def test_cli_errors(tmp_path, capsys):
    assert main([str(tmp_path / "none.png")]) == 1
    (tmp_path / "bad.png").write_bytes(b"not an image")
    assert main([str(tmp_path / "bad.png")]) == 1
    assert "画像として読めません" in capsys.readouterr().err
    slime(tmp_path / "a.png")
    slime(tmp_path / "b.png")
    assert main([str(tmp_path / "a.png"), str(tmp_path / "b.png"), "-o", str(tmp_path / "x.txt")]) == 1
    assert main([str(tmp_path / "a.png"), "--preview", "--color", "-w", "12"]) == 0
    assert "\x1b[" in capsys.readouterr().out
    assert convert_file(tmp_path / "a.png", Options(width=12))[0]
