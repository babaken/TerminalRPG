"""シナリオ作成マニュアルの見本（docs/manual/sample/HelloQuest）が検証に通り、最後まで遊べること。"""
import shutil
from pathlib import Path

import pytest

from test_chapter1 import Play
from test_play import _seed  # noqa: F401
from trpg.game import load_game
from trpg.package.check import check_package
from trpg.scenes.ending import EndingScene

SAMPLE = Path(__file__).resolve().parent.parent / "docs" / "manual" / "sample" / "HelloQuest"


def test_sample_has_no_issues():
    rep, manifest = check_package(SAMPLE, lambda s: None)
    assert manifest.id == "helloquest" and not rep.issues, rep.format()


@pytest.fixture
def game(tmp_path):
    d = tmp_path / "HelloQuest"
    shutil.copytree(SAMPLE, d)
    g = load_game(d)
    yield g
    g.close()


def test_sample_playthrough(game):
    d = Play(game)
    for _ in range(4):
        d.key("ENTER")
    talk = " ".join(d.settle())
    f = d.field
    st = f.st
    assert "北の草原に大きなスライム" in talk and st.map_id == "village"
    talk = d.talk(9, 6, "up")
    assert any("北の草原の奥" in t for t in talk)
    d.walk_to(9, 0)
    assert st.map_id == "meadow"
    d.walk_to(9, 2)
    d.settle()
    assert "boss_done" in st.flags
    d.walk_to(9, 9)
    assert st.map_id == "village"
    d.talk(9, 6, "up")
    for _ in range(100):
        if isinstance(d.scene, EndingScene):
            break
        d.key("ENTER")
        d.tick(0.2)
    assert isinstance(d.scene, EndingScene)
