"""
scripts/generate_index.py のユニットテスト
"""

import re
import sys
from pathlib import Path

import pytest

# scripts/ ディレクトリをモジュールとしてインポートできるようにパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from generate_index import (
    GENERATED_HEADER,
    PLACEHOLDER_RE,
    to_js_string_raw,
    replace_placeholder,
    main,
    REPO_ROOT,
)


# ---------------------------------------------------------------------------
# to_js_string_raw
# ---------------------------------------------------------------------------

class TestToJsStringRaw:
    def test_no_backtick(self):
        """バッククォートを含まない場合は単純な String.raw テンプレートになる。"""
        result = to_js_string_raw("hello world")
        assert result == "String.raw`hello world`"

    def test_single_backtick(self):
        """バッククォート1つを含む場合は分割結合式になる。"""
        result = to_js_string_raw("foo `bar` baz")
        assert result == 'String.raw`foo ` + "`" + String.raw`bar` + "`" + String.raw` baz`'

    def test_multiple_backticks(self):
        """バッククォート複数を含む場合も正しく分割される。"""
        # "`a` `b`" には3つのバッククォートがあるので split で4片 → 結合後5片
        result = to_js_string_raw("`a` `b`")
        parts = result.split(' + "`" + ')
        assert len(parts) == 5
        for part in parts:
            assert part.startswith("String.raw`")
            assert part.endswith("`")

    def test_empty_string(self):
        """空文字列でも問題なく変換できる。"""
        result = to_js_string_raw("")
        assert result == "String.raw``"

    def test_newlines_preserved(self):
        """改行を含むコードが正しく埋め込まれる。"""
        code = "line1\nline2\nline3"
        result = to_js_string_raw(code)
        assert "line1\nline2\nline3" in result


# ---------------------------------------------------------------------------
# replace_placeholder
# ---------------------------------------------------------------------------

class TestReplacePlaceholder:
    def test_replaces_with_file_content(self, tmp_path):
        """プレースホルダーが対応ファイルの内容に置換される。"""
        src_file = tmp_path / "sample.py"
        src_file.write_text("x = 1\n", encoding="utf-8")

        # REPO_ROOT を tmp_path に差し替えてモンキーパッチ
        import generate_index as gi
        original = gi.REPO_ROOT
        gi.REPO_ROOT = tmp_path
        try:
            match = PLACEHOLDER_RE.search("{{PLACEHOLDER:sample.py}}")
            result = replace_placeholder(match)
        finally:
            gi.REPO_ROOT = original

        assert result == "String.raw`x = 1\n`"

    def test_raises_when_file_not_found(self, tmp_path):
        """存在しないファイルを指定すると FileNotFoundError が発生する。"""
        import generate_index as gi
        original = gi.REPO_ROOT
        gi.REPO_ROOT = tmp_path
        try:
            match = PLACEHOLDER_RE.search("{{PLACEHOLDER:nonexistent.py}}")
            with pytest.raises(FileNotFoundError):
                replace_placeholder(match)
        finally:
            gi.REPO_ROOT = original


# ---------------------------------------------------------------------------
# main (統合テスト)
# ---------------------------------------------------------------------------

class TestMain:
    def _setup(self, tmp_path: Path, template_content: str, py_files: dict) -> None:
        """tmp_path にテンプレートと Python ファイルを配置する。"""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "template.html").write_text(template_content, encoding="utf-8")
        for rel_path, content in py_files.items():
            target = tmp_path / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def test_generates_output_file(self, tmp_path, monkeypatch):
        """main() を実行すると index.html が生成される。"""
        import generate_index as gi
        template = "<script>\nconst code = {{PLACEHOLDER:src/app.py}};\n</script>"
        self._setup(tmp_path, template, {"src/app.py": "print('hello')\n"})

        monkeypatch.setattr(gi, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(gi, "TEMPLATE_PATH", tmp_path / "scripts" / "template.html")
        monkeypatch.setattr(gi, "OUTPUT_PATH", tmp_path / "index.html")

        main()
        assert (tmp_path / "index.html").exists()

    def test_output_starts_with_generated_header(self, tmp_path, monkeypatch):
        """生成ファイルの先頭に自動生成コメントが付く。"""
        import generate_index as gi
        template = "<html>{{PLACEHOLDER:src/app.py}}</html>"
        self._setup(tmp_path, template, {"src/app.py": "pass\n"})

        monkeypatch.setattr(gi, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(gi, "TEMPLATE_PATH", tmp_path / "scripts" / "template.html")
        monkeypatch.setattr(gi, "OUTPUT_PATH", tmp_path / "index.html")

        main()
        content = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert content.startswith(GENERATED_HEADER)

    def test_placeholder_is_replaced(self, tmp_path, monkeypatch):
        """プレースホルダーが Python コードに置換される。"""
        import generate_index as gi
        template = "const x = {{PLACEHOLDER:src/mod.py}};"
        self._setup(tmp_path, template, {"src/mod.py": "y = 42\n"})

        monkeypatch.setattr(gi, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(gi, "TEMPLATE_PATH", tmp_path / "scripts" / "template.html")
        monkeypatch.setattr(gi, "OUTPUT_PATH", tmp_path / "index.html")

        main()
        content = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert "{{PLACEHOLDER:" not in content
        assert "y = 42" in content

    def test_backtick_in_source_is_escaped(self, tmp_path, monkeypatch):
        """ソース中のバッククォートが分割結合式に変換される。"""
        import generate_index as gi
        template = "const x = {{PLACEHOLDER:src/mod.py}};"
        self._setup(tmp_path, template, {"src/mod.py": "s = `hello`\n"})

        monkeypatch.setattr(gi, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(gi, "TEMPLATE_PATH", tmp_path / "scripts" / "template.html")
        monkeypatch.setattr(gi, "OUTPUT_PATH", tmp_path / "index.html")

        main()
        content = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert '+ "`" +' in content

    def test_multiple_placeholders(self, tmp_path, monkeypatch):
        """複数のプレースホルダーがそれぞれ対応ファイルで置換される。"""
        import generate_index as gi
        template = "{{PLACEHOLDER:src/a.py}} and {{PLACEHOLDER:src/b.py}}"
        self._setup(tmp_path, template, {
            "src/a.py": "a = 1\n",
            "src/b.py": "b = 2\n",
        })

        monkeypatch.setattr(gi, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(gi, "TEMPLATE_PATH", tmp_path / "scripts" / "template.html")
        monkeypatch.setattr(gi, "OUTPUT_PATH", tmp_path / "index.html")

        main()
        content = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert "a = 1" in content
        assert "b = 2" in content

    def test_exits_when_template_not_found(self, tmp_path, monkeypatch):
        """テンプレートが存在しない場合は SystemExit が発生する。"""
        import generate_index as gi
        monkeypatch.setattr(gi, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(gi, "TEMPLATE_PATH", tmp_path / "scripts" / "nonexistent.html")
        monkeypatch.setattr(gi, "OUTPUT_PATH", tmp_path / "index.html")

        with pytest.raises(SystemExit):
            main()

    def test_reports_all_missing_files(self, tmp_path, monkeypatch, capsys):
        """不足ファイルが複数ある場合に、すべてまとめて報告される。"""
        import generate_index as gi
        template = "{{PLACEHOLDER:src/a.py}} and {{PLACEHOLDER:src/b.py}}"
        self._setup(tmp_path, template, {})

        monkeypatch.setattr(gi, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(gi, "TEMPLATE_PATH", tmp_path / "scripts" / "template.html")
        monkeypatch.setattr(gi, "OUTPUT_PATH", tmp_path / "index.html")

        with pytest.raises(SystemExit):
            main()

        captured = capsys.readouterr()
        assert "以下のファイルが見つかりません" in captured.err
        assert str(tmp_path / "src" / "a.py") in captured.err
        assert str(tmp_path / "src" / "b.py") in captured.err
