#!/usr/bin/env python3
"""
index.html 生成スクリプト

scripts/template.html 内の {{PLACEHOLDER:path}} を
対応する Python ソースファイルの内容に置換して index.html を生成する。

使用方法:
    python scripts/generate_index.py

設計詳細は scripts/DESIGN.md を参照。
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TEMPLATE_PATH = Path(__file__).parent / "template.html"
OUTPUT_PATH = REPO_ROOT / "index.html"

GENERATED_HEADER = "<!-- このファイルは scripts/generate_index.py により自動生成されます。手編集禁止。 -->\n"
PLACEHOLDER_RE = re.compile(r"\{\{PLACEHOLDER:([^}]+)\}\}")


def to_js_string_raw(content: str) -> str:
    """
    Python ソースコードの文字列を JavaScript の String.raw テンプレートリテラル式に変換する。

    バッククォートが含まれる場合は分割結合式を生成する。
    例: String.raw`part1` + "`" + String.raw`part2`
    """
    parts = content.split("`")
    if len(parts) == 1:
        return f"String.raw`{content}`"

    js_parts = [f'String.raw`{part}`' for part in parts]
    return ' + "`" + '.join(js_parts)


def replace_placeholder(match: re.Match) -> str:
    """プレースホルダーに対応するファイルを読み込み、JavaScript埋め込み用文字列に変換する。"""
    rel_path = match.group(1).strip()
    src_path = REPO_ROOT / rel_path

    if not src_path.exists():
        raise FileNotFoundError(str(src_path))

    content = src_path.read_text(encoding="utf-8")
    return to_js_string_raw(content)


def main() -> None:
    """テンプレートを展開して index.html を生成し、欠落ファイルがあればまとめて報告する。"""
    if not TEMPLATE_PATH.exists():
        print(f"[ERROR] テンプレートが見つかりません: {TEMPLATE_PATH}", file=sys.stderr)
        sys.exit(1)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    # 先に全プレースホルダーを検査し、不足ファイルをまとめて報告する。
    missing_files: list[Path] = []
    for match in PLACEHOLDER_RE.finditer(template):
        rel_path = match.group(1).strip()
        src_path = REPO_ROOT / rel_path
        if not src_path.exists():
            missing_files.append(src_path)

    if missing_files:
        print("[ERROR] 以下のファイルが見つかりません:", file=sys.stderr)
        for path in missing_files:
            print(f"  - {path}", file=sys.stderr)
        sys.exit(1)

    output = PLACEHOLDER_RE.sub(replace_placeholder, template)
    output = GENERATED_HEADER + output

    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(f"[OK] 生成完了: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
