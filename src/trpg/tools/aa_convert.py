"""AA 変換ツール（要件 T-01）：画像（PNG / JPG など）をアスキーアートのテキストにする。Pillow を使う。

    python -m trpg.tools.aa_convert slime.png -w 20 --color          → slime.txt と slime.color
    python -m trpg.tools.aa_convert images/ -d scenarios/A/aa -w 24   → フォルダ内の画像をまとめて変換
    python -m trpg.tools.aa_convert slime.png -w 20 --color --preview → ファイルを作らず端末に表示

- 明るいところほど濃い文字にする（端末の背景が黒のため）。白い背景の画像は ``--invert`` を使う。
- 透明なところは半角空白（戦闘画面などで下が透ける）。
- ``--charset ascii``（記号のみ、既定）/ ``wide``（全角の記号）/ ``--chars`` で好きな文字の並び。
- ``--edges`` で輪郭を - | / \\ の線で描く（``--outline`` なら線だけ）。``--color`` で色ファイル（基本設計 12 章）も作る。
"""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..term.style import COLOR_CODES
from ..term.width import char_width, text_width

CHARSETS = {
    "ascii": " .:-=+*#%@",
    "wide": "  ・：＋＊＃＠",          # 先頭は半角空白 2 つ（透過させるため全角空白は使わない）
}
EDGE_CHARS = {"ascii": "-/|\\", "wide": "－／｜＼"}       # 0° 45° 90° 135° の線
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
MIN_WIDTH, MAX_WIDTH = 4, 200


class ConvertError(Exception):
    """変換できない。メッセージは利用者向けの日本語。"""


@dataclass
class Options:
    width: int = 40                   # 出力の桁数（半角換算）
    charset: str = "ascii"
    chars: Optional[str] = None       # 濃さの順に並べた文字（指定すれば charset より優先）
    invert: bool = False
    edges: bool = False
    outline: bool = False             # 輪郭の線だけを描く（中は空白）
    edge_threshold: float = 0.3       # 0〜1。小さいほど線が増える
    color: bool = False
    aspect: float = 0.5               # 文字 1 個の 幅 ÷ 高さ（半角）
    trim: bool = True


def _need_pillow():
    try:
        from PIL import Image, ImageOps  # noqa: F401
    except ImportError:
        raise ConvertError("Pillow が必要です：pip install Pillow") from None


def _ramp(opts: Options) -> list[str]:
    """濃さの順の「マス」の並び。全角の文字は 1 マス、半角は 1 マス = 1 文字（wide では半角 2 文字で 1 マス）。"""
    if opts.chars:
        widths = {char_width(c) for c in opts.chars}
        if len(opts.chars) < 2 or len(widths) != 1 or widths == {0}:
            raise ConvertError("--chars は同じ幅（すべて半角かすべて全角）の文字を 2 つ以上並べてください")
        if widths == {2}:
            return ["  "] + list(opts.chars)
        return list(opts.chars)
    if opts.charset == "wide":
        return ["  "] + list(CHARSETS["wide"][2:])
    return list(CHARSETS["ascii"])


def nearest_color(rgb: tuple[int, int, int]) -> str:
    """RGB に近い色コード。鮮やかさが低ければ灰・白、そうでなければ色相で 6 色から選び、明るければ大文字。
    黒（k）は端末の背景に溶けるので使わない（暗い色は灰色 K にする）。"""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    if s < 0.25 or v < 0.15:
        return "K" if v < 0.6 else ("w" if v < 0.9 else "W")
    code = "rygcbm"[int((h * 360 + 30) // 60) % 6]
    return code.upper() if v >= 0.85 else code


def convert(image, opts: Options) -> tuple[list[str], list[str]]:
    """PIL の画像を AA の行と色ファイルの行にする（色は opts.color のときだけ）。"""
    _need_pillow()
    from PIL import Image, ImageOps

    if not MIN_WIDTH <= opts.width <= MAX_WIDTH:
        raise ConvertError(f"幅は {MIN_WIDTH}〜{MAX_WIDTH} で指定してください")
    ramp = _ramp(opts)
    cell_w = 2 if char_width(ramp[-1]) == 2 else 1          # 1 マスの桁数
    edge_chars = EDGE_CHARS["wide" if cell_w == 2 else "ascii"]
    cols = max(1, opts.width // cell_w)
    img = image.convert("RGBA")
    ratio = opts.aspect * cell_w                             # 1 マスの 幅 ÷ 高さ
    rows = max(1, round(img.height / img.width * cols * ratio))

    small = img.resize((cols, rows), Image.Resampling.BOX)
    alpha = small.getchannel("A")
    gray = ImageOps.autocontrast(small.convert("RGB").convert("L"))
    if opts.invert:
        gray = ImageOps.invert(gray)
    g = gray.tobytes()
    a = alpha.tobytes()
    raw = small.convert("RGB").tobytes()
    colors_px = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]

    edge_map = _edge_map(img, cols, rows, opts) if opts.edges or opts.outline else {}
    lines, colors = [], []
    n = len(ramp)
    for y in range(rows):
        line, crow = [], []
        for x in range(cols):
            i = y * cols + x
            if a[i] < 128:
                cell = ramp[0]
            else:
                cell = ramp[0] if opts.outline else ramp[min(n - 1, g[i] * n // 256)]
                if i in edge_map:
                    cell = edge_chars[edge_map[i]]
            line.append(cell)
            code = "." if cell.strip() == "" else nearest_color(colors_px[i])
            crow.append(code * len(cell))
        lines.append("".join(line))
        colors.append("".join(crow))
    if opts.trim:
        lines, colors = _trim(lines, colors)
    return lines, (colors if opts.color else [])


EDGE_SUB = 4          # 輪郭は 1 マスを 4×4 に分けた細かさで調べる


def _edge_map(img, cols: int, rows: int, opts: Options) -> dict[int, int]:
    """輪郭のあるマス → 線の向き（0:─ 1:／ 2:│ 3:＼）。マスの中の輪郭の向きを平均する。"""
    from PIL import Image, ImageOps
    n = EDGE_SUB
    w, h = cols * n, rows * n
    big = img.resize((w, h), Image.Resampling.BOX)
    bg = Image.new("RGB", big.size, (0, 0, 0))
    bg.paste(big.convert("RGB"), mask=big.getchannel("A"))   # 透明なところは背景（黒）
    gray = ImageOps.autocontrast(bg.convert("L"))
    if opts.invert:
        gray = ImageOps.invert(gray)
        gray.paste(0, mask=ImageOps.invert(big.getchannel("A")).point(lambda v: 255 if v >= 128 else 0))
    v = gray.tobytes()

    def px(x, y):
        return v[min(max(y, 0), h - 1) * w + min(max(x, 0), w - 1)]

    acc: dict[int, list[float]] = {}
    for y in range(h):
        for x in range(w):
            gx = (px(x + 1, y - 1) + 2 * px(x + 1, y) + px(x + 1, y + 1)
                  - px(x - 1, y - 1) - 2 * px(x - 1, y) - px(x - 1, y + 1))
            gy = (px(x - 1, y + 1) + 2 * px(x, y + 1) + px(x + 1, y + 1)
                  - px(x - 1, y - 1) - 2 * px(x, y - 1) - px(x + 1, y - 1))
            mag = math.hypot(gx, gy)
            if mag / 1020 <= opts.edge_threshold:
                continue
            t = 2 * math.atan2(gx, gy)                  # 向きは 180° で一周なので角度を 2 倍して平均する
            c = acc.setdefault((y // n) * cols + x // n, [0.0, 0.0])
            c[0] += mag * math.cos(t)
            c[1] += mag * math.sin(t)
    out = {}
    for i, (cx, cy) in acc.items():
        angle = math.degrees(math.atan2(cy, cx)) / 2 % 180
        out[i] = int((angle + 22.5) // 45) % 4
    return out


def _trim(lines: list[str], colors: list[str]) -> tuple[list[str], list[str]]:
    """右端の空白、上下の空行、全行に共通する左の空白を取る（色の行も同じだけ取る）。"""
    keep = [i for i, s in enumerate(lines) if s.strip(" ")]
    if not keep:
        return [], []
    lines = lines[keep[0]: keep[-1] + 1]
    colors = colors[keep[0]: keep[-1] + 1]
    indent = min(len(s) - len(s.lstrip(" ")) for s in lines if s.strip(" "))
    out_l, out_c = [], []
    for s, c in zip(lines, colors):
        s, c = s[indent:], c[indent:]
        s = s.rstrip(" ")
        out_l.append(s)
        out_c.append(c[: len(s)].rstrip("."))
    return out_l, out_c


def convert_file(path: Path | str, opts: Options) -> tuple[list[str], list[str]]:
    _need_pillow()
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(path) as im:
            im.seek(0)                                        # GIF などは 1 コマ目
            return convert(im, opts)
    except FileNotFoundError:
        raise ConvertError(f"ファイルが見つかりません: {path}") from None
    except (UnidentifiedImageError, OSError) as e:
        raise ConvertError(f"画像として読めません: {path}（{e}）") from None


def inputs(paths: list[str]) -> list[Path]:
    """引数の画像を並べる。フォルダならその中（直下）の画像すべて。"""
    out: list[Path] = []
    for s in paths:
        p = Path(s)
        if p.is_dir():
            found = sorted(q for q in p.iterdir() if q.is_file() and q.suffix.lower() in IMAGE_EXTS)
            if not found:
                raise ConvertError(f"画像がありません: {p}")
            out.extend(found)
        else:
            out.append(p)
    return out


def write(dest: Path, lines: list[str], colors: list[str], force: bool) -> list[Path]:
    """AA（と色ファイル）を書く。作ったファイルを返す。"""
    targets = [dest] + ([dest.with_suffix(".color")] if colors else [])
    for t in targets:
        if t.exists() and not force:
            raise ConvertError(f"すでにあります（上書きするには --force）: {t}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    if colors:
        while colors and not colors[-1]:
            colors = colors[:-1]
        targets[1].write_text("\n".join(colors) + "\n", encoding="utf-8", newline="\n")
    return targets


def preview(lines: list[str], colors: list[str]) -> str:
    """端末で確かめるための ANSI 色つき文字列。"""
    out = []
    for i, s in enumerate(lines):
        crow = colors[i] if i < len(colors) else ""
        buf, cur = [], None
        for j, ch in enumerate(s):
            code = crow[j] if j < len(crow) else "."
            n = COLOR_CODES.get(code)
            if n != cur:
                buf.append("\x1b[0m" if n is None else f"\x1b[{30 + n if n < 8 else 82 + n}m")
                cur = n
            buf.append(ch)
        out.append("".join(buf) + "\x1b[0m")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    from ..__main__ import _stdout_utf8
    _stdout_utf8()
    p = argparse.ArgumentParser(prog="python -m trpg.tools.aa_convert",
                                description="画像（PNG / JPG など）をアスキーアートにする")
    p.add_argument("images", nargs="+", help="画像ファイル、または画像の入ったフォルダ")
    p.add_argument("-w", "--width", type=int, default=40, help="出力の桁数（半角換算、既定 40）")
    p.add_argument("-o", "--output", metavar="TXT", help="出力ファイル（画像が 1 つのとき）")
    p.add_argument("-d", "--out-dir", metavar="DIR", default=".", help="出力フォルダ（既定：今のフォルダ。名前は <画像名>.txt）")
    p.add_argument("--charset", choices=sorted(CHARSETS), default="ascii", help="ascii：記号のみ（既定） / wide：全角の記号")
    p.add_argument("--chars", help="濃さの順に並べた文字（例：\" .oO@\"）。charset より優先")
    p.add_argument("--invert", action="store_true", help="明暗を反転する（白い背景の画像向け）")
    p.add_argument("--edges", action="store_true", help="輪郭を - | / \\ の線で描く")
    p.add_argument("--outline", action="store_true", help="輪郭の線だけを描く（中は空白）")
    p.add_argument("--edge-threshold", type=float, default=0.3, help="輪郭とみなす強さ 0〜1（既定 0.3、小さいほど線が増える）")
    p.add_argument("--color", action="store_true", help="色ファイル（.color）も作る")
    p.add_argument("--aspect", type=float, default=0.5, help="文字 1 個の 幅÷高さ（既定 0.5。縦長に見えるときは小さく）")
    p.add_argument("--no-trim", action="store_true", help="周りの空白を取らない")
    p.add_argument("--preview", action="store_true", help="ファイルを作らず端末に表示する")
    p.add_argument("--force", action="store_true", help="同じ名前のファイルがあれば上書きする")
    args = p.parse_args(argv)
    opts = Options(width=args.width, charset=args.charset, chars=args.chars, invert=args.invert,
                   edges=args.edges, outline=args.outline, edge_threshold=args.edge_threshold, color=args.color,
                   aspect=args.aspect, trim=not args.no_trim)
    try:
        if not 0 < opts.aspect <= 2:
            raise ConvertError("--aspect は 0 より大きく 2 以下で指定してください")
        files = inputs(args.images)
        if args.output and len(files) != 1:
            raise ConvertError("-o は画像が 1 つのときだけ使えます（複数なら -d）")
        for f in files:
            lines, colors = convert_file(f, opts)
            if args.preview:
                print(f"── {f}（{max((text_width(s) for s in lines), default=0)} 桁 × {len(lines)} 行）")
                print(preview(lines, colors if opts.color else []))
                continue
            dest = Path(args.output) if args.output else Path(args.out_dir) / (f.stem + ".txt")
            made = write(dest, lines, colors, args.force)
            print(f"{f} → " + " / ".join(str(m) for m in made) + f"（{len(lines)} 行）")
    except ConvertError as e:
        print(f"中断: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
