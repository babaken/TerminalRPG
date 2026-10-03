"""セーブ／ロード（要件 4.9・6.2、基本設計 13 章）。

- ファイル: <セーブフォルダ>/<package.id>/slot1.sav 〜 slot3.sav
- 形式: MAGIC "TRPGSAV" | 形式版 1 バイト | nonce 12 バイト | 暗号文（AES-256-GCM、認証タグ付き）
- 鍵: HKDF-SHA256(エンジン埋め込みの秘密値, salt = package.id)
- AAD: package.id（別シナリオのセーブは復号できない）
- 平文: GameState を JSON にして zlib 圧縮したもの

目標は「一般の利用者が読めない・書き換えたら検知して読み込まない」こと。
鍵は配布物に含まれるため、解析されれば復号できる（要件 6.2 の前提どおり）。
"""
from __future__ import annotations

import json
import os
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..world.state import GameState, Member

MAGIC = b"TRPGSAV"
FORMAT = 1
SLOTS = 3
NONCE_LEN = 12
_SECRET = b"trpg-console-rpg-engine/save-key/v1/7f3c9a1e5b2d4086"


class SaveError(Exception):
    """セーブ／ロードの失敗。メッセージは利用者向けの日本語。"""


def default_dir() -> Path:
    """セーブフォルダ。環境変数 TRPG_SAVE_DIR があればそれ、なければ起動フォルダの saves/。"""
    env = os.environ.get("TRPG_SAVE_DIR")
    return Path(env) if env else Path.cwd() / "saves"


# ================================================================ 状態 ⇄ 辞書
def _member_to_dict(m: Member) -> dict:
    return {"id": m.id, "name": m.name, "job": m.job, "lv": m.lv, "base": dict(m.base),
            "hp": m.hp, "mp": m.mp, "exp": m.exp, "equip": dict(m.equip), "status": list(m.status),
            "extra_skills": list(m.extra_skills), "sp": m.sp}


def _member_from_dict(md: dict) -> Member:
    return Member(
        id=md["id"], name=md["name"], job=md["job"], lv=int(md["lv"]), base=dict(md["base"]),
        hp=int(md.get("hp", 0)), mp=int(md.get("mp", 0)), exp=int(md.get("exp", 0)),
        equip=dict(md.get("equip", {})), status=list(md.get("status", [])),
        extra_skills=list(md.get("extra_skills", [])), sp=int(md.get("sp", -1)),
    )


def state_to_dict(st: GameState) -> dict:
    return {
        "party": [_member_to_dict(m) for m in st.party],
        "away": {k: _member_to_dict(m) for k, m in st.away.items()},
        "gold": st.gold,
        "items": dict(st.items),
        "flags": sorted(st.flags),
        "vars": dict(st.vars),
        "quests": dict(st.quests),
        "quest_progress": dict(st.quest_progress),
        "chapter": st.chapter,
        "chapter_title": st.chapter_title,
        "map_id": st.map_id, "x": st.x, "y": st.y, "dir": st.dir,
        "once_events": sorted(st.once_events),
        "npc_state": {k: dict(v) for k, v in st.npc_state.items()},
        "effects": dict(st.effects),
        "playtime": st.playtime,
        "pet": st.pet,
        "tiles": {k: dict(v) for k, v in st.tiles.items()},
        "traps": {k: [list(t) for t in v] for k, v in st.traps.items()},
    }


def state_from_dict(d: dict) -> GameState:
    """辞書から GameState を作る。足りない項目は既定値（古いセーブとの互換）。"""
    st = GameState()
    for md in d.get("party", []):
        st.party.append(_member_from_dict(md))
    st.away = {k: _member_from_dict(md) for k, md in d.get("away", {}).items()}
    st.gold = int(d.get("gold", 0))
    st.items = {k: int(v) for k, v in d.get("items", {}).items()}
    st.flags = set(d.get("flags", []))
    st.vars = {k: int(v) for k, v in d.get("vars", {}).items()}
    st.quests = dict(d.get("quests", {}))
    st.quest_progress = {k: int(v) for k, v in d.get("quest_progress", {}).items()}
    st.chapter = int(d.get("chapter", 0))
    st.chapter_title = d.get("chapter_title", "")
    st.map_id = d.get("map_id", "")
    st.x, st.y = int(d.get("x", 0)), int(d.get("y", 0))
    st.dir = d.get("dir", "down")
    st.once_events = set(d.get("once_events", []))
    st.npc_state = {k: dict(v) for k, v in d.get("npc_state", {}).items()}
    st.effects = dict(d.get("effects", {}))
    st.playtime = float(d.get("playtime", 0.0))
    st.pet = d.get("pet", "")
    st.tiles = {k: {p: str(c) for p, c in v.items()} for k, v in d.get("tiles", {}).items()}
    st.traps = {k: [[int(t[0]), int(t[1]), str(t[2]), bool(t[3])] for t in v] for k, v in d.get("traps", {}).items()}
    return st


# ================================================================ 暗号化
def _aead(package_id: str):
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    except ImportError:
        raise SaveError("セーブ機能には cryptography が必要です（pip install cryptography）") from None
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=package_id.encode("utf-8"),
               info=b"trpg-save-v1").derive(_SECRET)
    return AESGCM(key)


def encode(payload: dict, package_id: str) -> bytes:
    plain = zlib.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    nonce = os.urandom(NONCE_LEN)
    ct = _aead(package_id).encrypt(nonce, plain, package_id.encode("utf-8"))
    return MAGIC + bytes([FORMAT]) + nonce + ct


def decode(data: bytes, package_id: str) -> dict:
    head = len(MAGIC) + 1 + NONCE_LEN
    if len(data) < head + 16 or not data.startswith(MAGIC):
        raise SaveError("セーブデータではありません")
    if data[len(MAGIC)] != FORMAT:
        raise SaveError("このエンジンでは読めない形式のセーブデータです")
    nonce = data[len(MAGIC) + 1:head]
    try:
        from cryptography.exceptions import InvalidTag
    except ImportError:
        raise SaveError("セーブ機能には cryptography が必要です（pip install cryptography）") from None
    try:
        plain = _aead(package_id).decrypt(nonce, data[head:], package_id.encode("utf-8"))
    except InvalidTag:
        raise SaveError("セーブデータが壊れているか、別のシナリオのものです") from None
    try:
        return json.loads(zlib.decompress(plain).decode("utf-8"))
    except (zlib.error, ValueError):
        raise SaveError("セーブデータが壊れています") from None


# ================================================================ スロット
@dataclass
class SlotInfo:
    slot: int
    exists: bool
    ok: bool = False
    error: str = ""
    saved_at: float = 0.0
    hero: str = ""
    lv: int = 0
    chapter: int = 0
    chapter_title: str = ""
    map_name: str = ""
    playtime: float = 0.0

    def label(self) -> str:
        if not self.exists:
            return "（空き）"
        if not self.ok:
            return f"（読み込めません：{self.error}）"
        t = int(self.playtime)
        ch = f"第{self.chapter}章" if self.chapter else ""
        when = time.strftime("%m/%d %H:%M", time.localtime(self.saved_at))
        return f"{self.hero} Lv{self.lv}  {ch} {self.map_name}  {t // 3600:02}:{t // 60 % 60:02}  [{when}]"


class SaveStore:
    def __init__(self, package_id: str, version: str = "", base: Optional[Path] = None):
        self.package_id = package_id
        self.version = version
        self.dir = (base or default_dir()) / package_id

    def path(self, slot: int) -> Path:
        if not 1 <= slot <= SLOTS:
            raise ValueError(slot)
        return self.dir / f"slot{slot}.sav"

    def save(self, slot: int, st: GameState, map_name: str = "") -> None:
        payload = {
            "package": {"id": self.package_id, "version": self.version},
            "saved_at": time.time(),
            "summary": {
                "hero": st.hero.name if st.hero else "", "lv": st.hero.lv if st.hero else 0,
                "chapter": st.chapter, "chapter_title": st.chapter_title,
                "map_name": map_name, "playtime": st.playtime,
            },
            "state": state_to_dict(st),
        }
        data = encode(payload, self.package_id)
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self.path(slot).with_suffix(".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, self.path(slot))      # 書き込み途中で落ちても元のセーブは壊さない
        except OSError as e:
            raise SaveError(f"セーブファイルを書き込めません（{e.strerror or e}）") from None

    def _read(self, slot: int) -> dict:
        p = self.path(slot)
        try:
            data = p.read_bytes()
        except FileNotFoundError:
            raise SaveError("セーブデータがありません") from None
        except OSError as e:
            raise SaveError(f"セーブファイルを読めません（{e.strerror or e}）") from None
        payload = decode(data, self.package_id)
        if payload.get("package", {}).get("id") != self.package_id:
            raise SaveError("別のシナリオのセーブデータです")
        return payload

    def load(self, slot: int) -> GameState:
        return state_from_dict(self._read(slot)["state"])

    def info(self, slot: int) -> SlotInfo:
        if not self.path(slot).exists():
            return SlotInfo(slot, exists=False)
        try:
            p = self._read(slot)
        except SaveError as e:
            return SlotInfo(slot, exists=True, ok=False, error=str(e))
        s = p.get("summary", {})
        return SlotInfo(slot, True, True, "", float(p.get("saved_at", 0)), s.get("hero", ""), int(s.get("lv", 0)),
                        int(s.get("chapter", 0)), s.get("chapter_title", ""), s.get("map_name", ""),
                        float(s.get("playtime", 0)))

    def infos(self) -> list[SlotInfo]:
        return [self.info(i) for i in range(1, SLOTS + 1)]

    def any_save(self) -> bool:
        return any(i.exists and i.ok for i in self.infos())

    def latest(self) -> Optional[int]:
        ok = [i for i in self.infos() if i.exists and i.ok]
        return max(ok, key=lambda i: i.saved_at).slot if ok else None
