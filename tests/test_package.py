import zipfile

import pytest

from trpg.data import DataError, Report
from trpg.package import PackageError, discover, open_package
from trpg.package.manifest import engine_compatible
from trpg.package.source import normalize

from conftest import edit


def zip_dir(src, dest, prefix=""):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in src.rglob("*"):
            if p.is_file():
                z.write(p, prefix + p.relative_to(src).as_posix())
    return dest


def test_open_folder_and_zip(sample_dir, tmp_path):
    with open_package(sample_dir) as pkg:
        assert pkg.manifest.id == "firstquest"
        assert pkg.exists("Map.data")
    z = zip_dir(sample_dir, tmp_path / "A.zip")
    with open_package(z) as pkg:
        assert pkg.manifest.title == "FirstQuest"
        assert "aa/slime.txt" in pkg.files()


def test_zip_with_top_folder(sample_dir, tmp_path):
    z = zip_dir(sample_dir, tmp_path / "B.zip", prefix="FirstQuest/")
    with open_package(z) as pkg:
        assert pkg.read_text("scenario.sco").startswith("#")


def test_normalize_rejects_traversal():
    assert normalize("aa\\x.txt") == "aa/x.txt"
    assert normalize("./aa//x.txt") == "aa/x.txt"
    for bad in ("../x", "aa/../../x", "/etc/passwd", "C:/x"):
        with pytest.raises(PackageError):
            normalize(bad)


def test_zip_traversal_rejected(tmp_path):
    z = tmp_path / "evil.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("manifest.toml", "")
        zf.writestr("../evil.txt", "x")
    with pytest.raises(PackageError, match=r"\.\."):
        open_package(z)


def test_zip_bomb_rejected(tmp_path):
    z = tmp_path / "bomb.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.toml", "")
        zf.writestr("big.txt", b"\0" * (5 * 1024 * 1024))
    with pytest.raises(PackageError, match="圧縮率"):
        open_package(z)


def test_not_a_package(tmp_path):
    z = tmp_path / "other.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("readme.txt", "x")
    with pytest.raises(PackageError, match="manifest.toml"):
        open_package(z)
    (tmp_path / "broken.zip").write_bytes(b"not zip")
    with pytest.raises(PackageError, match="zip"):
        open_package(tmp_path / "broken.zip")


def test_missing_required_file(sample_dir):
    (sample_dir / "Enemy.data").unlink()
    with pytest.raises(DataError) as ei:
        open_package(sample_dir)
    assert any(i.file == "Enemy.data" for i in ei.value.report.errors)


def test_manifest_errors(sample_dir):
    m = sample_dir / "manifest.toml"
    edit(m, 'gameover = "choose"', 'gameover = "restart"')
    edit(m, 'engine = ">=1.0"', 'engine = ">=9.0"')
    edit(m, 'id = "firstquest"', 'id = "First Quest"')
    with pytest.raises(DataError) as ei:
        open_package(sample_dir)
    text = ei.value.report.format()
    assert "restart" in text and "retry_from_save" in text
    assert "対応していません" in text
    assert "英小文字" in text


def test_manifest_toml_syntax_error_has_line(sample_dir):
    m = sample_dir / "manifest.toml"
    edit(m, 'title = "FirstQuest"', 'title = FirstQuest')
    with pytest.raises(DataError) as ei:
        open_package(sample_dir)
    err = ei.value.report.errors[0]
    assert err.file == "manifest.toml" and err.line == 4


def test_engine_compatible():
    assert engine_compatible(">=1.0") is True
    assert engine_compatible(">=1.1") is False
    assert engine_compatible("1.0") is True
    assert engine_compatible(">=1.0,<2") is True
    assert engine_compatible("latest") is None
    assert engine_compatible("") is True


def test_discover(sample_dir, tmp_path):
    zip_dir(sample_dir, tmp_path / "A.zip")
    with zipfile.ZipFile(tmp_path / "photos.zip", "w") as zf:
        zf.writestr("a.jpg", "x")
    found = discover([tmp_path])
    names = {c.path.name: c for c in found}
    assert "A.zip" in names and names["A.zip"].error == ""
    assert "FirstQuest" in names            # 展開フォルダも候補
    assert "photos.zip" not in names        # シナリオでない zip は無視


def test_utf8_bom_ok_and_sjis_rejected(sample_dir):
    sco = sample_dir / "scenario.sco"
    sco.write_bytes("\ufeff*start\n".encode("utf-8"))
    with open_package(sample_dir) as pkg:
        assert pkg.read_text("scenario.sco") == "*start\n"
        (sample_dir / "scenario.sco").write_bytes("村長".encode("cp932"))
        with pytest.raises(PackageError, match="UTF-8"):
            pkg.read_text("scenario.sco")
