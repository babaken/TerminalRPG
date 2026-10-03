"""ゲームデータのデータクラス（基本設計 5〜9 章）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

STAT_KEYS = ("hp", "mp", "atk", "def", "mag", "agi", "luk")
ELEMENTS = ("fire", "ice", "thunder", "holy", "dark")
EQUIP_SLOTS = ("weapon", "armor", "shield", "accessory")
ITEM_TYPES = ("consumable", "equipment", "key")
TARGETS = ("self", "ally_one", "ally_all", "enemy_one", "enemy_all")
SKILL_KINDS = ("physical", "magic", "heal", "buff", "debuff", "status", "tame", "escape")
AI_TYPES = ("attack_only", "random", "pattern")
EVENT_TRIGGERS = ("touch", "check", "auto")
NPC_MOVES = ("fixed", "random", "route")
QUEST_GOALS = ("deliver", "defeat", "reach", "flag")
SKILL_ANIMS = ("flash", "shake", "blink")   # スキルの anim（"flash:red,shake" のようにカンマで重ねられる）


def parse_anim(text: str) -> list[tuple[str, str]]:
    """"flash:red,shake:2" → [("flash", "red"), ("shake", "2")]"""
    out = []
    for part in text.split(","):
        part = part.strip()
        if part:
            name, _, arg = part.partition(":")
            out.append((name.strip(), arg.strip()))
    return out


USE_EFFECTS = ("heal", "heal_mp", "cure", "revive", "script", "skill", "warp")

# エンジン組み込みのスキル（データに書かなくても使える）
BUILTIN_SKILLS = ("attack", "defend")

Stats = dict  # {"hp": int, ...}


@dataclass
class Job:
    id: str
    name: str
    growth: Stats = field(default_factory=dict)
    equip: list[str] = field(default_factory=list)          # 装備可能カテゴリ
    skills: list[tuple[int, str]] = field(default_factory=list)  # (習得Lv, スキルID)
    sp_base: int = 0          # Lv1 の最大 SP（技に使う。魔法は MP）
    sp_growth: int = 0        # Lv が 1 上がるごとに増える最大 SP
    sp_regen: int = 3         # 戦闘中、毎ターンの終わりに回復する SP


@dataclass
class Character:
    id: str
    name: str
    job: str
    lv: int = 1
    stats: Stats = field(default_factory=dict)
    equip: dict[str, str] = field(default_factory=dict)
    face: str = ""
    name_input: bool = False
    recruit_text: str = ""
    familiar: str = ""        # 使い魔（敵 ID）：このキャラが戦闘に出ていると一緒に戦う。強さはこのキャラの Lv で決まる


@dataclass
class EnemyAction:
    skill: str
    weight: int = 1
    when: str = ""
    target: str = "random"


@dataclass
class Enemy:
    id: str
    name: str
    aa: str
    stats: Stats
    exp: int = 0
    gold: int = 0
    weak: list[str] = field(default_factory=list)
    resist: list[str] = field(default_factory=list)
    immune_status: list[str] = field(default_factory=list)
    drops: list[tuple[str, float]] = field(default_factory=list)
    tameable: bool = False
    tame_rate: float = 0.0
    ai: str = "attack_only"
    actions: list[EnemyAction] = field(default_factory=list)
    copy: str = ""            # キャラクター ID：戦闘開始時のそのキャラの能力値を写す（試練の「影」など）
    growth: Stats = field(default_factory=dict)   # 使い魔のとき：主人の Lv が 1 上がるごとに増える能力値


@dataclass
class Group:
    id: str
    members: list[str]


@dataclass
class Encounter:
    id: str
    steps: tuple[int, int]
    table: list[tuple[str, int]]  # (group, weight)


@dataclass
class Item:
    id: str
    name: str
    type: str
    price: int = 0
    desc: str = ""
    slot: str = ""
    category: str = ""
    stats: Stats = field(default_factory=dict)
    use: dict = field(default_factory=dict)
    raw: tuple[str, str] = ()   # name・desc に {hero} があるときの元の文（world.items.personalize が名前を入れる）


@dataclass
class Skill:
    id: str
    name: str
    mp: int = 0
    sp: int = 0               # 技に使う SP（MP と両方は書かない）
    target: str = "enemy_one"
    kind: str = "physical"
    element: str = ""
    power: int = 0
    status: str = ""          # 付与する状態異常
    status_rate: float = 0.0
    anim: str = ""
    desc: str = ""


@dataclass
class StatusDef:
    id: str
    name: str
    turns: tuple[int, int] = (3, 3)
    tick: dict = field(default_factory=dict)
    on_field: bool = False      # 戦闘後もフィールドで継続するか（データ上のキーは field）
    skip_turn: bool = False


@dataclass
class Shop:
    id: str
    name: str
    goods: list[str]
    sell_rate: float = 0.5


@dataclass
class Tile:
    char: str
    glyph: str
    passable: bool
    color: str = ""
    name: str = ""


@dataclass
class TileSet:
    id: str
    tiles: dict[str, Tile]


@dataclass
class MapEvent:
    x: int
    y: int
    label: str
    trigger: str = "check"
    once: bool = False
    when: str = ""


@dataclass
class Warp:
    x: int
    y: int
    to: str
    tx: int
    ty: int
    dir: str = ""


@dataclass
class Npc:
    id: str
    glyph: str
    x: int
    y: int
    color: str = ""
    move: str = "fixed"
    talk: str = ""
    when: str = ""
    route: list[str] = field(default_factory=list)   # move = "route" の道順（up/down/left/right/wait を繰り返す）


ROUTE_STEPS = ("up", "down", "left", "right", "wait")


TRAP_TARGETS = ("one", "all")


@dataclass
class Trap:
    """見えない罠の種類（Map.data の [[trap]]）。踏むまで見えず、踏むと glyph が見えるようになる。"""
    id: str
    name: str
    glyph: str                 # 見えるようになったときの文字（表示幅 2）
    color: str = ""
    target: str = "one"        # one：仲間 1 人（ランダム）/ all：全員
    damage_rate: float = 0.1   # 最大 HP に対するダメージの割合（HP は 1 より下がらない）
    status: str = ""           # かかる状態異常（例 poison）
    message: str = ""          # 踏んだときの文


@dataclass
class GameMap:
    id: str
    name: str
    tileset: str
    rows: list[str]
    encounter: str = ""
    dark: bool = False
    indoor: bool = False      # 屋内：雨・雪を表示しない（天気の状態は保ったまま）
    dungeon: bool = False     # ダンジョンの階：入ったときに名前を表示。条件式 map.dungeon が真になる
    traps: tuple[int, int] = (0, 0)      # 見えない罠の数（最小, 最大）。初めて入ったときにランダムに置く
    trap_kinds: list[str] = field(default_factory=list)   # 置く罠の種類（空ならすべての [[trap]]）
    events: list[MapEvent] = field(default_factory=list)
    warps: list[Warp] = field(default_factory=list)
    npcs: list[Npc] = field(default_factory=list)

    @property
    def width(self) -> int:
        return len(self.rows[0]) if self.rows else 0

    @property
    def height(self) -> int:
        return len(self.rows)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= y < self.height and 0 <= x < self.width


@dataclass
class Quest:
    id: str
    name: str
    goal: dict
    reward: dict
    giver: str = "guild"
    desc: str = ""
    rank: str = ""
    repeatable: bool = False
    on_complete: str = ""
    when: str = ""            # 掲示板に出す条件（条件式）


@dataclass
class GameData:
    jobs: dict[str, Job] = field(default_factory=dict)
    characters: dict[str, Character] = field(default_factory=dict)
    enemies: dict[str, Enemy] = field(default_factory=dict)
    groups: dict[str, Group] = field(default_factory=dict)
    encounters: dict[str, Encounter] = field(default_factory=dict)
    items: dict[str, Item] = field(default_factory=dict)
    skills: dict[str, Skill] = field(default_factory=dict)
    statuses: dict[str, StatusDef] = field(default_factory=dict)
    shops: dict[str, Shop] = field(default_factory=dict)
    tilesets: dict[str, TileSet] = field(default_factory=dict)
    traps: dict[str, Trap] = field(default_factory=dict)
    maps: dict[str, GameMap] = field(default_factory=dict)
    quests: dict[str, Quest] = field(default_factory=dict)
    aa: dict[str, list[str]] = field(default_factory=dict)  # AA ファイル（パス → 行）
    aa_color: dict[str, list[str]] = field(default_factory=dict)  # AA の色（AA のパス → 色コードの行）
    # スクリプトのラベルを参照している箇所（label, file, line）。scenario.sco 読込後に照合する
    label_refs: list[tuple[str, str, Optional[int]]] = field(default_factory=list)

    def colors_for(self, lines: list[str]) -> Optional[list[str]]:
        """gd.aa から取り出した AA の行リストに対応する色（.color がなければ None）。"""
        for path, art in self.aa.items():
            if art is lines:
                return self.aa_color.get(path)
        return None

    def face_path(self, ident: str, exists) -> Optional[str]:
        """@face の ID から顔 AA のファイルを決める。

        1. Friends.data のキャラクターで face が指定されていればそれ
        2. なければ aa/face_<ID>.txt（NPC など Friends.data にいない人向け）
        3. ID 自体が .txt のパスならそれ
        exists(path) で存在を確かめ、見つからなければ None。
        """
        c = self.characters.get(ident)
        for path in ((c.face if c else ""), f"aa/face_{ident}.txt", ident if ident.endswith(".txt") else ""):
            if path and exists(path):
                return path
        return None

    def summary(self) -> str:
        parts = [
            ("職業", self.jobs), ("キャラクター", self.characters), ("敵", self.enemies),
            ("敵グループ", self.groups), ("出現表", self.encounters), ("アイテム", self.items),
            ("スキル", self.skills), ("状態異常", self.statuses), ("ショップ", self.shops),
            ("タイルセット", self.tilesets), ("マップ", self.maps), ("クエスト", self.quests),
            ("AA", self.aa),
        ]
        return " / ".join(f"{n} {len(d)}" for n, d in parts)
