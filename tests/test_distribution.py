"""配布（pip の wheel・Windows の exe）に関する確認。"""
from __future__ import annotations

import tomllib
from pathlib import Path

from trpg import package as pkg

ROOT = Path(__file__).resolve().parent.parent


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_pyproject_lists_all_engine_packages():
    """src/trpg のサブパッケージを pyproject.toml の packages に書き忘れていない。"""
    listed = set(_pyproject()["tool"]["setuptools"]["packages"])
    src = ROOT / "src"
    actual = {".".join(p.parent.relative_to(src).parts) for p in (src / "trpg").rglob("__init__.py")
              if "__pycache__" not in p.parts}
    assert actual - listed == set()


def test_pyproject_bundles_firstquest():
    cfg = _pyproject()["tool"]["setuptools"]
    dirs = cfg["package-dir"]
    assert dirs["trpg.bundled.FirstQuest"] == "scenarios/FirstQuest"
    assert (ROOT / dirs["trpg.bundled.FirstQuest"] / "manifest.toml").is_file()
    # FirstQuest のサブフォルダもすべて packages に入っている
    sub = {"trpg.bundled.FirstQuest." + p.name for p in (ROOT / "scenarios/FirstQuest").iterdir() if p.is_dir()}
    assert sub <= set(cfg["packages"])


def test_find_scenarios_falls_back_to_bundled(tmp_path, monkeypatch):
    monkeypatch.setattr(pkg, "bundled_dirs", lambda: [ROOT / "scenarios"])
    found = pkg.find_scenarios(tmp_path)
    assert "firstquest" in [c.id for c in found]


def test_find_scenarios_prefers_local_copy(tmp_path, monkeypatch):
    import shutil
    shutil.copytree(ROOT / "scenarios/FirstQuest", tmp_path / "scenarios/FirstQuest")
    monkeypatch.setattr(pkg, "bundled_dirs", lambda: [ROOT / "scenarios"])
    found = [c for c in pkg.find_scenarios(tmp_path) if c.id == "firstquest"]
    assert len(found) == 1
    assert found[0].path.parent == tmp_path / "scenarios"


def test_spec_bundles_firstquest():
    spec = (ROOT / "packaging/trpg.spec").read_text(encoding="utf-8")
    assert "scenarios/FirstQuest" in spec
