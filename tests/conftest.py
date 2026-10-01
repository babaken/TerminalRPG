import shutil
from pathlib import Path

import pytest

SAMPLE = Path(__file__).resolve().parent.parent / "scenarios" / "FirstQuest"


@pytest.fixture
def sample_dir(tmp_path) -> Path:
    """サンプルシナリオのコピー（テストごとに書き換えてよい）。"""
    d = tmp_path / "FirstQuest"
    shutil.copytree(SAMPLE, d)
    return d


def edit(path: Path, old: str, new: str) -> None:
    s = path.read_text(encoding="utf-8")
    assert old in s, f"not found in {path.name}: {old!r}"
    path.write_text(s.replace(old, new, 1), encoding="utf-8")


@pytest.fixture(autouse=True)
def _save_dir(tmp_path, monkeypatch):
    """セーブはテストごとの一時フォルダへ（リポジトリに saves/ を作らない）。"""
    monkeypatch.setenv("TRPG_SAVE_DIR", str(tmp_path / "saves"))
