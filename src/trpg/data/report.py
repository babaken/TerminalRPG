"""検証結果（エラー・警告）の収集と表示。

読み込みは最初のエラーで止めず、できる限り続けて問題をすべて集める。
シナリオ制作者向けにファイル名・行番号つきの日本語メッセージを出す。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

ERROR = "error"
WARNING = "warning"


@dataclass
class Issue:
    level: str
    file: str
    line: Optional[int]
    message: str

    def format(self) -> str:
        label = "エラー" if self.level == ERROR else "警告  "
        loc = self.file + (f":{self.line}" if self.line else "")
        return f"{label} {loc}  {self.message}"


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)

    def error(self, file: str, line: Optional[int], message: str) -> None:
        self.issues.append(Issue(ERROR, file, line, message))

    def warning(self, file: str, line: Optional[int], message: str) -> None:
        self.issues.append(Issue(WARNING, file, line, message))

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, other: "Report") -> None:
        self.issues.extend(other.issues)

    def format(self) -> str:
        lines = [i.format() for i in sorted(self.issues, key=lambda i: (i.level != ERROR, i.file, i.line or 0))]
        lines.append(f"エラー {len(self.errors)} 件 / 警告 {len(self.warnings)} 件")
        return "\n".join(lines)


class DataError(Exception):
    """エラーを含む Report を持つ例外。"""

    def __init__(self, report: Report):
        self.report = report
        super().__init__(report.format())


_TOML_POS = re.compile(r"\(at line (\d+), column (\d+)\)")


def toml_error(report: Report, file: str, exc: Exception) -> None:
    """tomllib の例外を日本語のエラーとして登録する。"""
    msg = str(exc)
    m = _TOML_POS.search(msg)
    line = int(m.group(1)) if m else None
    detail = _TOML_POS.sub("", msg).strip()
    col = f"{m.group(2)} 文字目付近" if m else ""
    report.error(file, line, f"TOML の書式エラーです{('（' + col + '）') if col else ''}: {detail}")


def find_id_line(text: str, ident: str) -> Optional[int]:
    """``id = "ident"`` が書かれた行番号を探す（エラー表示用）。"""
    pat = re.compile(r'^\s*id\s*=\s*["\']' + re.escape(ident) + r'["\']', re.M)
    m = pat.search(text)
    return text.count("\n", 0, m.start()) + 1 if m else None


def find_table_line(text: str, header: str, index: int) -> Optional[int]:
    """``[[header]]`` の index 番目（0 始まり）の行番号。"""
    pat = re.compile(r"^\s*\[\[\s*" + re.escape(header) + r"\s*\]\]", re.M)
    for i, m in enumerate(pat.finditer(text)):
        if i == index:
            return text.count("\n", 0, m.start()) + 1
    return None
