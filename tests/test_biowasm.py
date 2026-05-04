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
    mock_cli = types.SimpleNamespace(exec=AsyncMock(return_value="seqtk output"))
    biowasm_modules["js"].Aioli.new.return_value = mock_cli

    result = await bridge.run_tool("seqtk/1.3", "seq -a input.fasta")

    assert result == "seqtk output"
    biowasm_modules["js"].Aioli.new.assert_awaited_once_with("seqtk/1.3")
    mock_cli.exec.assert_awaited_once_with("seq -a input.fasta")


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
    biowasm_modules["seqtk_module"].bridge.run_tool = AsyncMock(return_value="mocked output")

    result = await task.run("input.fasta", "seq -a")

    assert result == "mocked output"
    biowasm_modules["seqtk_module"].bridge.run_tool.assert_awaited_once_with(
        "seqtk/1.3", "seq -a input.fasta"
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


def test_display_biowasm_ui_renders_controls_when_idle(biowasm_modules):
    components = biowasm_modules["components_module"]

    with patch.object(components.st, "divider") as mock_divider, \
         patch.object(components.st, "header") as mock_header, \
         patch.object(components.st, "write") as mock_write, \
         patch.object(components.st, "selectbox", return_value="seqtk") as mock_selectbox, \
         patch.object(components.st, "text_input", return_value="seq -a") as mock_text_input, \
         patch.object(components.st, "container", return_value=MagicMock()) as mock_container, \
         patch.object(components.st, "button", return_value=False) as mock_button:
        components.display_biowasm_ui("/tmp/input.fasta")

    mock_divider.assert_called_once()
    mock_header.assert_called_once_with("🛠️ Wasm Tools (biowasm)")
    mock_write.assert_called_once_with("VFS内のファイルを処理します: `/tmp/input.fasta`")
    mock_selectbox.assert_called_once_with("ツールを選択", ["seqtk"])
    mock_text_input.assert_called_once_with("コマンド引数", value="seq -a")
    mock_container.assert_called_once()
    mock_button.assert_called_once_with("Wasmで実行")


def test_display_biowasm_ui_runs_seqtk_and_renders_result(biowasm_modules):
    components = biowasm_modules["components_module"]
    seqtk_module = biowasm_modules["seqtk_module"]
    result_container = MagicMock()
    result_container.__enter__.return_value = result_container
    result_container.__exit__.return_value = None
    spinner = MagicMock()
    spinner.__enter__.return_value = spinner
    spinner.__exit__.return_value = None
    fake_loop = MagicMock()
    fake_loop.is_running.return_value = False

    async def fake_run(self, input_filename, command):
        return f"{command}::{input_filename}"

    def run_until_complete(coro):
        return asyncio.run(coro)

    fake_loop.run_until_complete.side_effect = run_until_complete

    with patch.object(components.st, "divider"), \
         patch.object(components.st, "header"), \
         patch.object(components.st, "write"), \
         patch.object(components.st, "selectbox", return_value="seqtk"), \
         patch.object(components.st, "text_input", return_value="seq -A"), \
         patch.object(components.st, "container", return_value=result_container), \
         patch.object(components.st, "button", return_value=True), \
         patch.object(components.st, "spinner", return_value=spinner), \
         patch("asyncio.get_event_loop", return_value=fake_loop), \
         patch.object(seqtk_module.SeqtkTask, "run", new=fake_run), \
         patch.object(seqtk_module.SeqtkTask, "render") as mock_render:
        components.display_biowasm_ui("/tmp/input.fasta")

    fake_loop.run_until_complete.assert_called_once()
    mock_render.assert_called_once_with("seq -A::/tmp/input.fasta")
