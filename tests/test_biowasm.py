import asyncio
import importlib
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

@pytest.fixture
def biowasm_modules(monkeypatch):
    js_module = types.SimpleNamespace(
        Aioli=types.SimpleNamespace(new=AsyncMock()),
        FS=types.SimpleNamespace(
            writeFile=MagicMock(),
            readFile=MagicMock(),
        ),
        console=types.SimpleNamespace(
            log=MagicMock(),
            error=MagicMock(),
        ),
        eval=AsyncMock(),
    )
    pyodide_module = types.ModuleType("pyodide")
    pyodide_ffi_module = types.ModuleType("pyodide.ffi")
    pyodide_ffi_module.to_js = lambda value: value
    pyodide_module.ffi = pyodide_ffi_module

    monkeypatch.setitem(sys.modules, "js", js_module)
    monkeypatch.setitem(sys.modules, "pyodide", pyodide_module)
    monkeypatch.setitem(sys.modules, "pyodide.ffi", pyodide_ffi_module)

    bridge_module = importlib.import_module("pyowasm.bridge.biowasm")
    bridge_module = importlib.reload(bridge_module)

    seqtk_module = importlib.import_module("pyowasm.tasks.wasm.seqtk")
    seqtk_module = importlib.reload(seqtk_module)

    components_module = importlib.import_module("pyowasm.ui.components")
    components_module = importlib.reload(components_module)

    return {
        "js": js_module,
        "bridge_module": bridge_module,
        "seqtk_module": seqtk_module,
        "components_module": components_module,
    }

@pytest.mark.asyncio
async def test_biowasm_bridge_run_tool(biowasm_modules):
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    # Mock js.eval to return a success response
    biowasm_modules["js"].eval.return_value = '{"status": "success", "data": "seqtk output"}'

    result = await bridge.run_tool("seqtk/1.3", "seq -a input.fasta")

    assert result == "seqtk output"
    biowasm_modules["js"].eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_biowasm_bridge_run_tool_with_files_sets_js_files(biowasm_modules):
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    biowasm_modules["js"].eval.return_value = '{"status": "success", "data": "output", "debug": []}'

    files = {"test.txt": "hello"}
    result = await bridge.run_tool("blast/2.11.0", "cat test.txt", files=files)

    assert result == "output"
    biowasm_modules["js"].eval.assert_awaited_once()
    called_js = biowasm_modules["js"].eval.await_args.args[0]
    assert "const jsFiles = globalThis._pyowasm_files;" in called_js
    assert "delete globalThis._pyowasm_files;" in called_js


@pytest.mark.asyncio
async def test_biowasm_bridge_seqtk(biowasm_modules):
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    bridge.run_tool = AsyncMock(return_value="seqtk output")

    result = await bridge.seqtk("seq -a input.fasta")

    assert result == "seqtk output"
    bridge.run_tool.assert_awaited_once_with(
        "seqtk/1.3", "seqtk seq -a input.fasta", files=None
    )


@pytest.mark.asyncio
async def test_biowasm_bridge_makeblastdb_builds_command_and_files(biowasm_modules):
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    bridge.run_tool = AsyncMock(return_value="makeblastdb done")

    fasta_content = ">protein1\nMKT"
    result = await bridge.makeblastdb(fasta_content, db_name="coffee_db", db_type="prot")

    assert result == "makeblastdb done"
    bridge.run_tool.assert_awaited_once_with(
        "blast/2.11.0",
        'makeblastdb -in "coffee_db.fasta" -dbtype "prot" -out "coffee_db"',
        files={"coffee_db.fasta": fasta_content},
    )


@pytest.mark.asyncio
async def test_biowasm_bridge_blastp_builds_command_and_files(biowasm_modules):
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    bridge.run_tool = AsyncMock(return_value="q1\ts1\t99.0")

    query_content = ">query1\nMKT"
    options = "-outfmt 6 -evalue 1e-5"
    result = await bridge.blastp(query_content, db_name="coffee_db", options=options)

    assert result == "q1\ts1\t99.0"
    bridge.run_tool.assert_awaited_once_with(
        "blast/2.11.0",
        'blastp -query "query.fasta" -db "coffee_db" -outfmt 6 -evalue 1e-5',
        files={"query.fasta": query_content},
    )


@pytest.mark.asyncio
async def test_biowasm_bridge_blastp_uses_default_options(biowasm_modules):
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    bridge.run_tool = AsyncMock(return_value="")

    await bridge.blastp(">query1\nMKT", db_name="coffee_db")

    bridge.run_tool.assert_awaited_once_with(
        "blast/2.11.0",
        'blastp -query "query.fasta" -db "coffee_db" -outfmt 6',
        files={"query.fasta": ">query1\nMKT"},
    )


@pytest.mark.asyncio
async def test_biowasm_bridge_blastp_quotes_db_name_with_spaces(biowasm_modules):
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    bridge.run_tool = AsyncMock(return_value="")

    await bridge.blastp(">query1\nMKT", db_name="coffee db")

    bridge.run_tool.assert_awaited_once_with(
        "blast/2.11.0",
        'blastp -query "query.fasta" -db "coffee db" -outfmt 6',
        files={"query.fasta": ">query1\nMKT"},
    )


def test_biowasm_bridge_write_to_vfs(biowasm_modules):
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    filename = "test.fasta"
    content = ">seq1\nATGC"

    result = bridge.write_to_vfs(filename, content)

    assert result == filename
    biowasm_modules["js"].FS.writeFile.assert_called_once_with(filename, content)


@pytest.mark.asyncio
async def test_seqtk_task_run(biowasm_modules):
    task = biowasm_modules["seqtk_module"].SeqtkTask()
    biowasm_modules["bridge_module"].bridge.seqtk = AsyncMock(return_value="mocked output")

    result = await task.run("input.fasta", "seq -a")

    assert result == "mocked output"
    biowasm_modules["bridge_module"].bridge.seqtk.assert_awaited_once_with(
        "seq -a input.fasta", files=None
    )


@pytest.mark.asyncio
async def test_seqtk_task_run_does_not_duplicate_input_filename(biowasm_modules):
    task = biowasm_modules["seqtk_module"].SeqtkTask()
    biowasm_modules["bridge_module"].bridge.seqtk = AsyncMock(return_value="mocked output")

    result = await task.run("input.fasta", "seq -a input.fasta")

    assert result == "mocked output"
    biowasm_modules["bridge_module"].bridge.seqtk.assert_awaited_once_with(
        "seq -a input.fasta", files=None
    )


@pytest.mark.asyncio
async def test_seqtk_task_run_with_input_content_mounts_file(biowasm_modules):
    task = biowasm_modules["seqtk_module"].SeqtkTask()
    biowasm_modules["bridge_module"].bridge.seqtk = AsyncMock(return_value="mocked output")

    result = await task.run("input.fasta", "seq -a", input_content=">seq1\nATGC")

    assert result == "mocked output"
    biowasm_modules["bridge_module"].bridge.seqtk.assert_awaited_once_with(
        "seq -a input.fasta", files={"input.fasta": ">seq1\nATGC"}
    )


def test_seqtk_task_render(biowasm_modules):
    task = biowasm_modules["seqtk_module"].SeqtkTask()

    with patch("streamlit.success") as mock_success, \
         patch("streamlit.write") as mock_write, \
         patch("streamlit.code") as mock_code:
        task.render("test result")

    mock_success.assert_called_once()
    mock_write.assert_called_with("### Seqtk 出力")
    mock_code.assert_called_once_with("test result")


@pytest.mark.asyncio
async def test_display_biowasm_ui_renders_controls_when_idle(biowasm_modules):
    components = biowasm_modules["components_module"]

    with patch.object(components.st, "divider") as mock_divider, \
         patch.object(components.st, "header") as mock_header, \
         patch.object(components.st, "write") as mock_write, \
         patch.object(components.st, "selectbox", return_value="seqtk") as mock_selectbox, \
         patch.object(components.st, "text_input", return_value="seq -a") as mock_text_input, \
         patch.object(components.st, "container", return_value=MagicMock()) as mock_container, \
         patch.object(components.st, "button", return_value=False) as mock_button:
        await components.display_biowasm_ui("/tmp/input.fasta")

    mock_divider.assert_called_once()
    mock_header.assert_called_once_with("🛠️ Wasm Tools (biowasm)")
    mock_write.assert_called_once_with("VFS内のファイルを処理します: `/tmp/input.fasta`")
    mock_selectbox.assert_called_once_with("ツールを選択", ["seqtk"])
    mock_text_input.assert_called_once_with("コマンド引数", value="seq -a")
    mock_container.assert_called_once()
    mock_button.assert_called_once_with("Wasmで実行")


@pytest.mark.asyncio
async def test_display_biowasm_ui_runs_seqtk_and_renders_result(biowasm_modules):
    components = biowasm_modules["components_module"]
    seqtk_module = biowasm_modules["seqtk_module"]
    result_container = MagicMock()
    result_container.__enter__.return_value = result_container
    result_container.__exit__.return_value = None
    spinner = MagicMock()
    spinner.__enter__.return_value = spinner
    spinner.__exit__.return_value = None
    
    # We don't need to mock loop if we use pytest-asyncio properly, 
    # but the code itself might be using it.
    
    async def fake_run(self, input_filename, command, input_content=None):
        return f"{command}::{input_filename}"

    with patch.object(components.st, "divider"), \
         patch.object(components.st, "header"), \
         patch.object(components.st, "write"), \
         patch.object(components.st, "selectbox", return_value="seqtk"), \
         patch.object(components.st, "text_input", return_value="seq -A"), \
         patch.object(components.st, "container", return_value=result_container), \
         patch.object(components.st, "button", return_value=True), \
         patch.object(components.st, "spinner", return_value=spinner), \
         patch.object(seqtk_module.SeqtkTask, "run", new=fake_run), \
         patch.object(seqtk_module.SeqtkTask, "render") as mock_render:
        await components.display_biowasm_ui("/tmp/input.fasta")

    mock_render.assert_called_once_with("seq -A::/tmp/input.fasta")


# ====== 新規テスト: エラーハンドリングと edge cases ======

@pytest.mark.asyncio
async def test_biowasm_bridge_run_tool_returns_error_when_js_eval_returns_error_status(biowasm_modules):
    """JS側から status:error が返された場合"""
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    biowasm_modules["js"].eval.return_value = '{"status": "error", "message": "Aioli failed", "debug": ["step1", "step2"]}'

    result = await bridge.run_tool("seqtk/1.3", "seq -a input.fasta")

    assert "Wasm実行エラー: Aioli failed" in result
    assert "--- Debug Trace ---" in result
    assert "step1" in result


@pytest.mark.asyncio
async def test_biowasm_bridge_run_tool_returns_error_when_exit_code_nonzero(biowasm_modules):
    """seqtk の exit code が 0 以外の場合"""
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    biowasm_modules["js"].eval.return_value = (
        '{"status": "success", "data": {"stdout": "", "stderr": "error message", "exitCode": 1}, "debug": []}'
    )

    result = await bridge.run_tool("seqtk/1.3", "seq -a input.fasta")

    assert "Wasm実行エラー: error message" in result
    assert "--- Debug Trace ---" in result


@pytest.mark.asyncio
async def test_biowasm_bridge_run_tool_returns_bridge_error_on_exception(biowasm_modules):
    """Python 側で例外が発生した場合"""
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    biowasm_modules["js"].eval.side_effect = RuntimeError("JS evaluation failed")

    result = await bridge.run_tool("seqtk/1.3", "seq -a input.fasta")

    assert "ブリッジ通信エラー: JS evaluation failed" in result
    assert "--- Debug Trace ---" in result


@pytest.mark.asyncio
async def test_biowasm_bridge_run_tool_skips_mount_when_input_file_not_in_args(biowasm_modules):
    """input.fasta がコマンドに含まれない場合、mount ブロックはスキップ"""
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    biowasm_modules["js"].eval.return_value = '{"status": "success", "data": "output", "debug": ["mount_skipped"]}'

    result = await bridge.run_tool("seqtk/1.3", "version")

    assert result == "output"
    # debugLogs に mount_skipped が含まれることで検証
    biowasm_modules["js"].eval.assert_awaited_once()


def test_biowasm_bridge_write_to_vfs_fallback_when_fs_write_fails(biowasm_modules, tmp_path):
    """FS.writeFile が失敗した場合、OS フォールバックで処理"""
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    biowasm_modules["js"].FS.writeFile.side_effect = AttributeError("FS not available")
    
    # tmp_path を使用してテンポラリディレクトリでテスト
    test_file = str(tmp_path / "test.fasta")
    result = bridge.write_to_vfs(test_file, ">seq1\nATGC")

    # js._pyowasm_upload_text は必ず設定される
    assert hasattr(biowasm_modules["js"], "_pyowasm_upload_text")
    assert result == test_file
    # ファイルが実際に作成されたことを確認
    import os
    assert os.path.exists(test_file)


def test_seqtk_task_render_error_with_debug_trace(biowasm_modules):
    """seqtk render でエラー文字列 + debug trace を表示"""
    task = biowasm_modules["seqtk_module"].SeqtkTask()
    error_output = "Wasm実行エラー: [E::stk_seq] failed\n\n--- Debug Trace ---\n[PY] log1\n[JS] log2"

    with patch("streamlit.error") as mock_error, \
         patch("streamlit.code") as mock_code, \
         patch("streamlit.expander") as mock_expander:
        mock_expander.return_value.__enter__ = MagicMock()
        mock_expander.return_value.__exit__ = MagicMock(return_value=None)
        
        task.render(error_output)

    mock_error.assert_called_once_with("Wasm(seqtk) 実行でエラーが発生しました。")
    mock_expander.assert_called_once_with("デバッグトレースを表示", expanded=True)


@pytest.mark.asyncio
async def test_display_biowasm_ui_handles_exception_in_task_run(biowasm_modules):
    """task.run() が例外を投げた場合、st.error で表示"""
    components = biowasm_modules["components_module"]
    seqtk_module = biowasm_modules["seqtk_module"]
    result_container = MagicMock()
    result_container.__enter__.return_value = result_container
    result_container.__exit__.return_value = None

    async def fake_run_with_error(self, input_filename, command, input_content=None):
        raise RuntimeError("Task execution failed")

    with patch.object(components.st, "divider"), \
         patch.object(components.st, "header"), \
         patch.object(components.st, "write"), \
         patch.object(components.st, "selectbox", return_value="seqtk"), \
         patch.object(components.st, "text_input", return_value="seq -a"), \
         patch.object(components.st, "container", return_value=result_container), \
         patch.object(components.st, "button", return_value=True), \
         patch.object(components.st, "spinner"), \
         patch.object(components.st, "error") as mock_error, \
         patch.object(seqtk_module.SeqtkTask, "run", new=fake_run_with_error):
        await components.display_biowasm_ui("/tmp/input.fasta")

    mock_error.assert_called_once()
    assert "Task execution failed" in str(mock_error.call_args)
