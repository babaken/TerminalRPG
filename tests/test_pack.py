"""3-1：パッケージツール（検証してから zip にする）のテスト。"""
import tomllib
import zipfile

import pytest

from trpg.game import load_game
from trpg.tools.pack import PackError, main, pack

from conftest import edit


def quiet(_):
    pass


def test_pack_makes_playable_zip(sample_dir, tmp_path, monkeypatch):
    (sample_dir / "__pycache__").mkdir()
    (sample_dir / "__pycache__" / "x.pyc").write_bytes(b"x")
    (sample_dir / ".DS_Store").write_bytes(b"x")
    (sample_dir / "aa" / "slime.txt~").write_text("old", encoding="utf-8")
    (sample_dir / "plugin.py").write_text("print('no')", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    dest = pack(sample_dir, out=quiet)
    version = tomllib.loads((sample_dir / "manifest.toml").read_text(encoding="utf-8"))["package"]["version"]
    assert dest == tmp_path / f"FirstQuest-{version}.zip"
    names = zipfile.ZipFile(dest).namelist()
    assert "manifest.toml" in names and "aa/slime.color" in names       # manifest が直下
    assert not [n for n in names if "pycache" in n or n.startswith(".") or n.endswith(("~", ".py"))]
    g = load_game(dest)                                                 # そのまま遊べる
    assert g.manifest.id == "firstquest"
    g.close()


def test_pack_is_reproducible(sample_dir, tmp_path):
    a = pack(sample_dir, tmp_path / "a.zip", out=quiet)
    (sample_dir / "Map.data").touch()                                   # 日時が変わっても同じ zip
    b = pack(sample_dir, tmp_path / "b.zip", out=quiet)
    assert a.read_bytes() == b.read_bytes()


def test_pack_stops_on_error(sample_dir, tmp_path):
    edit(sample_dir / "scenario.sco", "*start", "*start_x")
    lines = []
    with pytest.raises(PackError, match="エラーがあるため"):
        pack(sample_dir, tmp_path / "x.zip", out=lines.append)
    assert not (tmp_path / "x.zip").exists()
    assert any("エラー" in s for s in lines)


def test_pack_strict_stops_on_warning(sample_dir, tmp_path):
    sco = sample_dir / "scenario.sco"
    sco.write_text(sco.read_text(encoding="utf-8") + "\n*never_used\n@end\n", encoding="utf-8")
    assert pack(sample_dir, tmp_path / "ok.zip", out=quiet)              # 警告だけなら作る
    with pytest.raises(PackError, match="--strict"):
        pack(sample_dir, tmp_path / "ng.zip", strict=True, out=quiet)


def test_pack_overwrite_and_inside(sample_dir, tmp_path):
    dest = pack(sample_dir, tmp_path / "a.zip", out=quiet)
    with pytest.raises(PackError, match="--force"):
        pack(sample_dir, dest, out=quiet)
    assert pack(sample_dir, dest, force=True, out=quiet) == dest
    with pytest.raises(PackError, match="中には作れません"):
        pack(sample_dir, sample_dir / "a.zip", out=quiet)


def test_pack_rejects_non_folder(tmp_path, sample_dir):
    with pytest.raises(PackError, match="フォルダを指定"):
        pack(tmp_path / "none", out=quiet)
    with pytest.raises(PackError, match="manifest.toml がありません"):
        pack(sample_dir / "aa", out=quiet)


def test_dry_run_and_cli(sample_dir, tmp_path, capsys):
    assert pack(sample_dir, tmp_path / "d.zip", dry_run=True, out=quiet) is None
    assert not (tmp_path / "d.zip").exists()
    assert main([str(sample_dir), "-o", str(tmp_path / "c.zip")]) == 0
    assert "作成しました" in capsys.readouterr().out
    assert main([str(sample_dir), "-o", str(tmp_path / "c.zip")]) == 1
    assert "中断" in capsys.readouterr().err
