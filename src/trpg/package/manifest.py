"""manifest.toml の読み込みと検証（基本設計 4 章）。"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field

from ..data.reader import Tbl
from ..data.report import Report, toml_error

FORMAT_VERSION = (1, 0)   # エンジンが対応するデータ形式の版
FILE = "manifest.toml"

GAMEOVER_MODES = ("retry_from_save", "title", "choose")
SAVE_MODES = ("anywhere", "save_point_only")
PARTY_LIMIT = 4
TITLE_EFFECTS = ("", "none", "starfall", "rain", "snow")   # タイトル画面の背景エフェクト


@dataclass
class Manifest:
    id: str = ""
    title: str = ""
    version: str = ""
    author: str = ""
    engine: str = ""
    languages: list[str] = field(default_factory=lambda: ["ja"])
    title_aa: str = ""
    title_effect: str = ""
    gameover: str = "choose"
    save: str = "anywhere"
    party_max: int = PARTY_LIMIT
    start_label: str = "start"
    start_party: list[str] = field(default_factory=list)
    start_gold: int = 0
    start_items: list[str] = field(default_factory=list)


_VER = re.compile(r"^\s*(>=|<=|==|>|<)?\s*(\d+)(?:\.(\d+))?\s*$")


def engine_compatible(spec: str, version: tuple[int, int] = FORMAT_VERSION) -> bool | None:
    """``">=1.0"`` などの指定に対応しているか。書式が不正なら None。"""
    if not spec:
        return True
    ok = True
    for part in spec.split(","):
        m = _VER.match(part)
        if not m:
            return None
        op, major, minor = m.group(1) or "==", int(m.group(2)), int(m.group(3) or 0)
        want = (major, minor)
        ok = ok and {
            ">=": version >= want, "<=": version <= want, "==": version == want,
            ">": version > want, "<": version < want,
        }[op]
    return ok


def parse_manifest(text: str, report: Report) -> Manifest:
    m = Manifest()
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        toml_error(report, FILE, e)
        return m
    root = Tbl(doc, FILE, "manifest", report)

    pkg = root.sub("package")
    m.id = pkg.id("id")
    m.title = pkg.str("title")
    m.version = pkg.str("version", "0.0.0")
    m.author = pkg.str("author", "")
    m.engine = pkg.str("engine", "")
    m.languages = pkg.strlist("languages", ["ja"]) or ["ja"]
    pkg.done()
    compat = engine_compatible(m.engine)
    if compat is None:
        report.error(FILE, None, f'[package] の engine「{m.engine}」の書式が不正です（例: ">=1.0"）')
    elif not compat:
        report.error(FILE, None, f"このシナリオはエンジンのデータ形式 {FORMAT_VERSION[0]}.{FORMAT_VERSION[1]} に対応していません"
                                  f"（要求: {m.engine}）。エンジンを更新してください")

    ts = root.sub("title_screen", {})
    m.title_aa = ts.str("aa", "")
    m.title_effect = ts.str("effect", "", choices=TITLE_EFFECTS)
    ts.done()

    rules = root.sub("rules", {})
    m.gameover = rules.str("gameover", "choose", choices=GAMEOVER_MODES)
    m.save = rules.str("save", "anywhere", choices=SAVE_MODES)
    m.party_max = rules.int("party_max", PARTY_LIMIT, min=1, max=PARTY_LIMIT)
    m.start_label = rules.str("start_label", "start")
    rules.done()

    start = root.sub("start", {})
    m.start_party = start.strlist("party", [])
    m.start_gold = start.int("gold", 0, min=0)
    m.start_items = start.strlist("items", [])
    start.done()
    if not m.start_party:
        report.error(FILE, None, "[start] の party に最初の仲間（主人公）を 1 人以上指定してください")
    elif len(m.start_party) > m.party_max:
        report.error(FILE, None, f"[start] の party が party_max（{m.party_max}）を超えています")

    root.done()
    return m
