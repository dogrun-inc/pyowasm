#!/usr/bin/env python3
"""
index.html 生成スクリプト

scripts/template.html 内の {{PLACEHOLDER:path}} を
対応する Python ソースファイルの内容に置換して index.html を生成する。

使用方法:
    python scripts/generate_index.py
    python scripts/generate_index.py --pretty

設計詳細は scripts/DESIGN.md を参照。
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TEMPLATE_PATH = Path(__file__).parent / "template.html"
OUTPUT_PATH = REPO_ROOT / "index.html"

GENERATED_HEADER = "<!-- このファイルは scripts/generate_index.py により自動生成されます。手編集禁止。 -->\n"
PLACEHOLDER_RE = re.compile(r"\{\{PLACEHOLDER:([^}]+)\}\}")


def to_js_string_raw(content: str, pretty: bool = False) -> str:
    """
    Python ソースコード文字列を JavaScript の安全な文字列リテラルへ変換する。

    デフォルトは安全性優先の1行JSON文字列。
    --pretty 指定時は可読性優先で複数行配列+join形式へ変換する。
    """
    if pretty:
        lines = content.split("\n")
        quoted_lines = ",\n".join(
            f"  {json.dumps(line, ensure_ascii=False)}" for line in lines
        )
        js_code = f"[\n{quoted_lines}\n].join(\"\\n\")"
    else:
        js_code = json.dumps(content, ensure_ascii=False)

    # HTML 内の <script> タグを壊さないようにエスケープする
    return js_code.replace("</script>", "<\\/script>")


def replace_placeholder(match: re.Match, pretty: bool = False) -> str:
    """プレースホルダーに対応するファイルを読み込み、JavaScript埋め込み用文字列に変換する。"""
    rel_path = match.group(1).strip()
    src_path = REPO_ROOT / rel_path

    if not src_path.exists():
        raise FileNotFoundError(str(src_path))

    content = src_path.read_text(encoding="utf-8")
    return to_js_string_raw(content, pretty=pretty)


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。"""
    parser = argparse.ArgumentParser(description="template.html から index.html を生成します。")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="可読性優先で複数行の JavaScript 文字列表現を使用します。",
    )
    return parser.parse_args()


def main() -> None:
    """テンプレートを展開して index.html を生成し、欠落ファイルがあればまとめて報告する。"""
    args = parse_args()

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

    output = PLACEHOLDER_RE.sub(lambda match: replace_placeholder(match, pretty=args.pretty), template)
    if not args.pretty:
        output = GENERATED_HEADER + output

    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(f"[OK] 生成完了: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
