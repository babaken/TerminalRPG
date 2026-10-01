import pytest

from trpg.data import DataError, Report, load_game_data
from trpg.package import open_package

from conftest import edit


def load(d):
    rep = Report()
    with open_package(d, rep) as pkg:
        gd = load_game_data(pkg, rep)
    return gd, rep


def msgs(rep):
    return "\n".join(i.format() for i in rep.issues)


def test_sample_loads_clean(sample_dir):
    gd, rep = load(sample_dir)
    assert rep.issues == [], msgs(rep)
    assert gd.characters["hero"].name_input is True
    assert gd.enemies["shadow_wolf"].actions[0].target == "id:hero"
    assert gd.maps["village_lito"].width == 32
    assert gd.tilesets["default"].tiles["."].passable is True
    assert gd.statuses["poison"].on_field is True
    assert gd.aa["aa/slime.txt"][1].strip() == "/  o o\\"
    labels = {l for l, _, _ in gd.label_refs}
    assert {"ch1_kai_talk", "ch1_forest_enter", "use_return_scroll"} <= labels


def test_undefined_references(sample_dir):
    edit(sample_dir / "Enemy.data", 'members = ["slime", "slime"]', 'members = ["slime", "slimee"]')
    edit(sample_dir / "Enemy.data", '{ item = "herb", rate = 0.1 }', '{ item = "potion", rate = 0.1 }')
    edit(sample_dir / "Friends.data", 'job = "warrior"', 'job = "knight"')
    edit(sample_dir / "Map.data", 'to = "house_hero"', 'to = "house_heroo"')
    gd, rep = load(sample_dir)
    text = msgs(rep)
    assert "敵「slimee」が定義されていません" in text
    assert "アイテム「potion」が定義されていません" in text
    assert "職業「knight」が定義されていません" in text
    assert "ワープ先マップ「house_heroo」" in text
    assert len(rep.errors) == 4


def test_error_points_to_entry_line(sample_dir):
    edit(sample_dir / "Enemy.data", 'stats = { hp = 8, atk = 5', 'stats = { hp = "8", atk = 5')
    _, rep = load(sample_dir)
    [err] = rep.errors
    text = (sample_dir / "Enemy.data").read_text(encoding="utf-8").splitlines()
    assert text[err.line - 1].strip() == 'id = "slime"'
    assert "stats の hp" in err.message and "整数" in err.message


def test_duplicate_id_and_unknown_key(sample_dir):
    edit(sample_dir / "Items.data", 'id = "copper_sword"', 'id = "rusty_sword"')
    edit(sample_dir / "Items.data", 'price = 8\n', 'price = 8\nprise = 9\n')
    _, rep = load(sample_dir)
    text = msgs(rep)
    assert "ID「rusty_sword」が重複" in text
    assert "prise: 未知の項目" in text


def test_map_row_length_and_tiles(sample_dir):
    m = sample_dir / "Map.data"
    edit(m, '"T..HHH.........................T",', '"T..HHH........................T",')
    edit(m, '"T..............................T",', '"T.........?....................T",')
    _, rep = load(sample_dir)
    text = msgs(rep)
    assert "行目の長さ（31）" in text
    assert "にない記号があります: '?'" in text


def test_glyph_width_and_ambiguous(sample_dir):
    m = sample_dir / "Map.data"
    edit(m, '"#" = { glyph = "＃"', '"#" = { glyph = "#"')
    edit(m, '"t" = { glyph = "机"', '"t" = { glyph = "■ "')
    _, rep = load(sample_dir)
    assert any("表示幅が 1" in e.message for e in rep.errors)
    assert any("曖昧幅" in w.message for w in rep.warnings)


def test_choices_and_ranges(sample_dir):
    e = sample_dir / "Enemy.data"
    edit(e, 'ai = "random"', 'ai = "smart"')
    edit(e, 'rate = 0.2', 'rate = 1.5')
    edit(e, 'weak = ["fire"]\ndrops', 'weak = ["wind"]\ndrops')
    _, rep = load(sample_dir)
    text = msgs(rep)
    assert "「smart」は使えません" in text
    assert "1.0 以下" in text
    assert "属性「wind」" in text


def test_ai_requires_actions(sample_dir):
    edit(sample_dir / "Enemy.data", 'stats = { hp = 8, atk = 5, def = 2, agi = 3, luk = 1 }',
         'stats = { hp = 8, atk = 5, def = 2, agi = 3, luk = 1 }\nai = "random"')
    _, rep = load(sample_dir)
    assert any("[[enemy.actions]]" in e.message for e in rep.errors)


def test_npc_on_wall_warning_and_out_of_bounds(sample_dir):
    m = sample_dir / "Map.data"
    edit(m, 'id = "kai"\nglyph = "友"\ncolor = "cyan"\nx = 15\ny = 2', 'id = "kai"\nglyph = "友"\ncolor = "cyan"\nx = 0\ny = 2')
    edit(m, 'id = "chief"\nglyph = "長"\ncolor = "white"\nx = 16\ny = 5', 'id = "chief"\nglyph = "長"\ncolor = "white"\nx = 99\ny = 5')
    _, rep = load(sample_dir)
    assert any("NPC kai が通行できない" in w.message for w in rep.warnings)
    assert any("NPC chief の座標 (99, 5) がマップ外" in e.message for e in rep.errors)


def test_toml_syntax_error(sample_dir):
    edit(sample_dir / "Quests.data", 'rank = "F"', 'rank = F')
    _, rep = load(sample_dir)
    [err] = rep.errors
    line = (sample_dir / "Quests.data").read_text(encoding="utf-8").splitlines().index('rank = F') + 1
    assert err.file == "Quests.data" and err.line == line and "書式エラー" in err.message


def test_missing_aa_and_bad_equip(sample_dir):
    (sample_dir / "aa" / "bat.txt").unlink()
    edit(sample_dir / "Friends.data", 'equip = { armor = "cloth" }', 'equip = { weapon = "cloth" }')
    _, rep = load(sample_dir)
    text = msgs(rep)
    assert "AA ファイル「aa/bat.txt」が見つかりません" in text
    assert "weapon に「cloth」は装備できません" in text


def test_strict_raises(sample_dir):
    edit(sample_dir / "Enemy.data", 'members = ["bat"]', 'members = []')
    with open_package(sample_dir) as pkg:
        with pytest.raises(DataError):
            load_game_data(pkg, strict=True)
