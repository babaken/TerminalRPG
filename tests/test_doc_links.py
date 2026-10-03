"""README と docs/ の Markdown の相対リンクが、すべて存在するファイル・フォルダを指していること。"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_LINK = re.compile(r"\]\(([^)\s]+)\)")


def test_relative_links_resolve():
    files = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
    broken = []
    for md in files:
        for target in _LINK.findall(md.read_text(encoding="utf-8")):
            if re.match(r"[a-z]+://", target) or target.startswith("#"):
                continue
            path = (md.parent / target.split("#", 1)[0]).resolve()
            if not path.exists():
                broken.append(f"{md.relative_to(ROOT)} → {target}")
    assert not broken, "リンク切れ: " + ", ".join(broken)
