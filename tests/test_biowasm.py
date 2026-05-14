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


def test_biowasm_bridge_write_to_vfs(biowasm_modules):
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    filename = "test.fasta"
    content = ">seq1\nATGC"

    result = bridge.write_to_vfs(filename, content)

    assert result == filename
    biowasm_modules["js"].FS.writeFile.assert_called_once_with(filename, content)


def test_seqtk_task_run(biowasm_modules):
    task = biowasm_modules["seqtk_module"].SeqtkTask()
    biowasm_modules["bridge_module"].bridge.start_tool_job = MagicMock(return_value="job-1")

    result = task.start("input.fasta", "seq -a")

    assert result == "job-1"
    biowasm_modules["bridge_module"].bridge.start_tool_job.assert_called_once_with(
        "seqtk/1.3", "seqtk seq -a input.fasta", files=None
    )


def test_seqtk_task_run_does_not_duplicate_input_filename(biowasm_modules):
    task = biowasm_modules["seqtk_module"].SeqtkTask()
    biowasm_modules["bridge_module"].bridge.start_tool_job = MagicMock(return_value="job-2")

    result = task.start("input.fasta", "seq -a input.fasta")

    assert result == "job-2"
    biowasm_modules["bridge_module"].bridge.start_tool_job.assert_called_once_with(
        "seqtk/1.3", "seqtk seq -a input.fasta", files=None
    )


def test_seqtk_task_run_with_input_content_mounts_file(biowasm_modules):
    task = biowasm_modules["seqtk_module"].SeqtkTask()
    biowasm_modules["bridge_module"].bridge.start_tool_job = MagicMock(return_value="job-3")

    result = task.start("input.fasta", "seq -a", input_content=">seq1\nATGC")

    assert result == "job-3"
    biowasm_modules["bridge_module"].bridge.start_tool_job.assert_called_once_with(
        "seqtk/1.3", "seqtk seq -a input.fasta", files={"input.fasta": ">seq1\nATGC"}
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
         patch.object(components.st, "number_input", return_value=60) as mock_number_input, \
         patch.object(components.st, "container", return_value=MagicMock()) as mock_container, \
         patch.object(components.st, "button", return_value=False) as mock_button:
        await components.display_biowasm_ui("/tmp/input.fasta")

    mock_divider.assert_not_called()
    mock_header.assert_not_called()
    mock_selectbox.assert_called_once_with("ツールを選択", ["seqtk"])
    mock_text_input.assert_called_once_with("コマンド引数", value="seq -a")
    mock_number_input.assert_called_once()
    mock_container.assert_called_once()
    # ボタン名が「🚀 Wasmで実行」に変更された
    mock_button.assert_called_once_with("🚀 Wasmで実行", key="pyowasm_seqtk_run", use_container_width=True, disabled=False)


@pytest.mark.asyncio
async def test_display_biowasm_ui_runs_seqtk_and_renders_result(biowasm_modules):
    components = biowasm_modules["components_module"]
    seqtk_module = biowasm_modules["seqtk_module"]
    result_container = MagicMock()
    result_container.__enter__.return_value = result_container
    result_container.__exit__.return_value = None

    def fake_start(self, input_filename, command, input_content=None):
        return "job-1"

    with patch.object(components.st, "divider"), \
         patch.object(components.st, "header"), \
         patch.object(components.st, "write"), \
         patch.object(components.st, "selectbox", return_value="seqtk"), \
         patch.object(components.st, "text_input", return_value="seq -A"), \
         patch.object(components.st, "number_input", return_value=60), \
         patch.object(components.st, "container", return_value=result_container), \
         patch.object(components.st, "button", side_effect=[True, False]), \
         patch.object(components.st, "rerun"), \
         patch.object(components.st, "markdown"), \
         patch.object(seqtk_module.SeqtkTask, "start", new=fake_start), \
         patch.object(seqtk_module.SeqtkTask, "poll", return_value={"status": "success", "result": "seq -A::/tmp/input.fasta"}), \
         patch.object(seqtk_module.SeqtkTask, "cleanup"), \
         patch.object(seqtk_module.SeqtkTask, "render") as mock_render:
        components.st.session_state["pyowasm_seqtk_job_id"] = "job-1"
        await components.display_biowasm_ui("/tmp/input.fasta")

    mock_render.assert_called_once_with("seq -A::/tmp/input.fasta")


@pytest.mark.asyncio
async def test_biowasm_bridge_run_tool_returns_error_when_js_eval_returns_error_status(biowasm_modules):
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    biowasm_modules["js"].eval.return_value = '{"status": "error", "message": "Aioli failed", "debug": ["step1", "step2"]}'

    result = await bridge.run_tool("seqtk/1.3", "seq -a input.fasta")

    assert "Wasm実行エラー: Aioli failed" in result
    assert "--- Debug Trace ---" in result
    assert "step1" in result


@pytest.mark.asyncio
async def test_biowasm_bridge_run_tool_returns_error_when_exit_code_nonzero(biowasm_modules):
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    biowasm_modules["js"].eval.return_value = (
        '{"status": "success", "data": {"stdout": "", "stderr": "error message", "exitCode": 1}, "debug": []}'
    )

    result = await bridge.run_tool("seqtk/1.3", "seq -a input.fasta")

    assert "Wasm実行エラー: error message" in result
    assert "--- Debug Trace ---" in result


@pytest.mark.asyncio
async def test_biowasm_bridge_run_tool_returns_bridge_error_on_exception(biowasm_modules):
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    biowasm_modules["js"].eval.side_effect = RuntimeError("JS evaluation failed")

    result = await bridge.run_tool("seqtk/1.3", "seq -a input.fasta")

    assert "ブリッジ通信エラー: JS evaluation failed" in result
    assert "--- Debug Trace ---" in result


@pytest.mark.asyncio
async def test_biowasm_bridge_run_tool_skips_mount_when_input_file_not_in_args(biowasm_modules):
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    biowasm_modules["js"].eval.return_value = '{"status": "success", "data": "output", "debug": ["mount_skipped"]}'

    result = await bridge.run_tool("seqtk/1.3", "version")

    assert result == "output"
    biowasm_modules["js"].eval.assert_awaited_once()


def test_biowasm_bridge_write_to_vfs_fallback_when_fs_write_fails(biowasm_modules, tmp_path):
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    biowasm_modules["js"].FS.writeFile.side_effect = AttributeError("FS not available")
    
    test_file = str(tmp_path / "test.fasta")
    result = bridge.write_to_vfs(test_file, ">seq1\nATGC")

    assert hasattr(biowasm_modules["js"], "_pyowasm_upload_text")
    assert result == test_file
    import os
    assert os.path.exists(test_file)


def test_seqtk_task_render_error_with_debug_trace(biowasm_modules):
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
    """task.start() が例外を投げた場合、上位（または呼び出し元）で処理されるか st.error で表示されることを確認"""
    components = biowasm_modules["components_module"]
    seqtk_module = biowasm_modules["seqtk_module"]
    result_container = MagicMock()
    result_container.__enter__.return_value = result_container
    result_container.__exit__.return_value = None

    def fake_start_with_error(self, input_filename, command, input_content=None):
        return "ERROR:Task execution failed"

    with patch.object(components.st, "divider"), \
         patch.object(components.st, "header"), \
         patch.object(components.st, "write"), \
         patch.object(components.st, "selectbox", return_value="seqtk"), \
         patch.object(components.st, "text_input", return_value="seq -a"), \
         patch.object(components.st, "container", return_value=result_container), \
         patch.object(components.st, "button", side_effect=[True, False]), \
         patch.object(components.st, "error") as mock_error, \
         patch.object(seqtk_module.SeqtkTask, "start", new=fake_start_with_error):
        await components.display_biowasm_ui("/tmp/input.fasta")

    # task.start が "ERROR:" で始まる文字列を返すと st.error が呼ばれる
    mock_error.assert_called_once_with("Task execution failed")


def test_biowasm_bridge_reports_unavailable_in_non_pyodide_env(monkeypatch):
    monkeypatch.delitem(sys.modules, "js", raising=False)
    monkeypatch.delitem(sys.modules, "pyodide", raising=False)
    monkeypatch.delitem(sys.modules, "pyodide.ffi", raising=False)

    bridge_module = importlib.import_module("pyowasm.bridge.biowasm")
    bridge_module = importlib.reload(bridge_module)
    bridge = bridge_module.BiowasmBridge()

    assert bridge.is_available() is False
    assert "Wasm ツールを利用できません" in bridge.unavailable_message()


@pytest.mark.asyncio
async def test_render_seqtk_mode_shows_info_when_wasm_unavailable(biowasm_modules):
    components = biowasm_modules["components_module"]

    with patch("pyowasm.bridge.biowasm.bridge.is_available", return_value=False), \
         patch("pyowasm.bridge.biowasm.bridge.unavailable_message", return_value="Wasm無効"), \
         patch.object(components.st, "info") as mock_info, \
         patch.object(components.st, "file_uploader") as mock_uploader:
        await components.render_seqtk_mode()

    # 最初の st.subheader 等は無視して info が呼ばれたか確認
    mock_info.assert_any_call("Wasm無効")
    mock_uploader.assert_not_called()


@pytest.mark.asyncio
async def test_display_biowasm_ui_handles_timeout(biowasm_modules):
    """ポーリングがタイムアウトした場合にエラーを表示しクリーンアップされることを確認"""
    components = biowasm_modules["components_module"]
    seqtk_module = biowasm_modules["seqtk_module"]
    result_container = MagicMock()
    result_container.__enter__.return_value = result_container
    result_container.__exit__.return_value = None

    # 開始時間と現在時間を操作してタイムアウトをシミュレート
    start_time = 1000.0
    # elapsed = 1100 - 1000 = 100 > 60 (timeout)
    current_time = 1100.0

    with patch.object(components.st, "selectbox", return_value="seqtk"), \
         patch.object(components.st, "text_input", return_value="seq -a"), \
         patch.object(components.st, "number_input", return_value=60), \
         patch.object(components.st, "container", return_value=result_container), \
         patch.object(components.st, "button", return_value=False), \
         patch.object(components.st, "rerun") as mock_rerun, \
         patch.object(components.st, "error") as mock_error, \
         patch.object(components.time, "time", return_value=current_time), \
         patch.object(seqtk_module.SeqtkTask, "cleanup") as mock_cleanup:
        
        components.st.session_state["pyowasm_seqtk_job_id"] = "job-timeout"
        components.st.session_state["pyowasm_seqtk_job_start_time"] = start_time
        
        await components.display_biowasm_ui("/tmp/input.fasta")

    mock_error.assert_called_once()
    assert "タイムアウトしました" in str(mock_error.call_args)
    mock_cleanup.assert_called_once_with("job-timeout")
    mock_rerun.assert_called_once()
    assert "pyowasm_seqtk_job_id" not in components.st.session_state
