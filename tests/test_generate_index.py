"""
scripts/generate_index.py のユニットテスト
"""

import re
import sys
import json
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
    def test_basic_string(self):
        """String.raw 形式ではなく JSON 文字列として出力される（最新の generate_index.py の挙動）。"""
        result = to_js_string_raw("hello world")
        assert result == '"hello world"'

    def test_json_escaping(self):
        """改行やクォートが JSON エスケープされる。"""
        result = to_js_string_raw('line1\n"line2"')
        assert result == '"line1\\n\\"line2\\""'

    def test_script_tag_escaping(self):
        """</script> タグがパースエラー防止のためにエスケープされる。"""
        result = to_js_string_raw("<div></script></div>")
        # </script> が <\/script> に置換されていることを確認。
        assert r"<\/script>" in result
        assert "</script>" not in result

    def test_empty_string(self):
        """空文字列でも問題なく変換できる。"""
        result = to_js_string_raw("")
        assert result == '""'


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

        assert result == '"x = 1\\n"'

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
        monkeypatch.setattr(sys, "argv", ["generate_index.py"])

        main()
        assert (tmp_path / "index.html").exists()

    def test_output_starts_with_generated_header(self, tmp_path, monkeypatch):
        """通常時、生成ファイルの先頭に自動生成コメントが付く。"""
        import generate_index as gi
        template = "<html>{{PLACEHOLDER:src/app.py}}</html>"
        self._setup(tmp_path, template, {"src/app.py": "pass\n"})

        monkeypatch.setattr(gi, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(gi, "TEMPLATE_PATH", tmp_path / "scripts" / "template.html")
        monkeypatch.setattr(gi, "OUTPUT_PATH", tmp_path / "index.html")
        monkeypatch.setattr(sys, "argv", ["generate_index.py"])

        main()
        content = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert content.startswith(GENERATED_HEADER)

    def test_output_does_not_have_header_when_pretty(self, tmp_path, monkeypatch):
        """--pretty 指定時、生成ファイルの先頭に自動生成コメントが付かない。"""
        import generate_index as gi
        template = "<html>{{PLACEHOLDER:src/app.py}}</html>"
        self._setup(tmp_path, template, {"src/app.py": "pass\n"})

        monkeypatch.setattr(gi, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(gi, "TEMPLATE_PATH", tmp_path / "scripts" / "template.html")
        monkeypatch.setattr(gi, "OUTPUT_PATH", tmp_path / "index.html")
        monkeypatch.setattr(sys, "argv", ["generate_index.py", "--pretty"])

        main()
        content = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert not content.startswith(GENERATED_HEADER)

    def test_placeholder_is_replaced(self, tmp_path, monkeypatch):
        """プレースホルダーが Python コードに置換される。"""
        import generate_index as gi
        template = "const x = {{PLACEHOLDER:src/mod.py}};"
        self._setup(tmp_path, template, {"src/mod.py": "y = 42\n"})

        monkeypatch.setattr(gi, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(gi, "TEMPLATE_PATH", tmp_path / "scripts" / "template.html")
        monkeypatch.setattr(gi, "OUTPUT_PATH", tmp_path / "index.html")
        monkeypatch.setattr(sys, "argv", ["generate_index.py"])

        main()
        content = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert "{{PLACEHOLDER:" not in content
        assert "y = 42" in content

    def test_script_tag_in_source_is_escaped(self, tmp_path, monkeypatch):
        """ソース中の </script> タグがエスケープされる。"""
        import generate_index as gi
        template = "const x = {{PLACEHOLDER:src/mod.py}};"
        self._setup(tmp_path, template, {"src/mod.py": "s = '</script>'\n"})

        monkeypatch.setattr(gi, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(gi, "TEMPLATE_PATH", tmp_path / "scripts" / "template.html")
        monkeypatch.setattr(gi, "OUTPUT_PATH", tmp_path / "index.html")
        monkeypatch.setattr(sys, "argv", ["generate_index.py"])

        main()
        content = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert '<\\/script>' in content

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
        monkeypatch.setattr(sys, "argv", ["generate_index.py"])

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
        monkeypatch.setattr(sys, "argv", ["generate_index.py"])

        with pytest.raises(SystemExit):
            main()

        captured = capsys.readouterr()
        assert "以下のファイルが見つかりません" in captured.err
        assert str(tmp_path / "src" / "a.py") in captured.err
        assert str(tmp_path / "src" / "b.py") in captured.err
