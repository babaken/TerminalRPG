"""MP と SP の表示（技は SP、魔法は MP）。"""
from __future__ import annotations


def cost_text(sk) -> str:
    """スキルの消費。"""
    return f"SP {sk.sp}" if sk.sp else f"MP {sk.mp}"


def points_text(mp: int, max_mp: int, sp: int, max_sp: int) -> str:
    """MP と SP。持っていないほうは出さない（両方あれば短く、両方なければ MP 0/0）。"""
    parts = []
    if max_mp or not max_sp:
        parts.append(f"MP {mp:>3}/{max_mp:<3}" if not max_sp else f"MP{mp:>3}")
    if max_sp:
        parts.append(f"SP {sp:>3}/{max_sp:<3}" if not max_mp else f"SP{sp:>3}")
    return " ".join(parts)
