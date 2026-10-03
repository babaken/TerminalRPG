import os
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


@pytest.fixture(autouse=True)
def _lang_ja():
    """UI の言語はテストごとに日本語に戻す（英語のテストが他に影響しないように）。"""
    from trpg.i18n import set_lang
    set_lang(os.environ.get("TRPG_TEST_LANG", "ja"))   # TRPG_TEST_LANG=en で英語の UI のまま全テストを流せる（落ちないかの確認用）
    yield
    set_lang("ja")


@pytest.fixture(autouse=True)
def _text_speed_normal():
    """文字の速さもテストごとに「ふつう」に戻す。"""
    from trpg import settings
    settings.set_text_speed("normal")
    yield
    settings.set_text_speed("normal")
