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
    # mock pyodide
    pyodide_module = types.ModuleType("pyodide")
    pyodide_ffi_module = types.ModuleType("pyodide.ffi")
    pyodide_ffi_module.to_js = lambda value: value
    pyodide_module.ffi = pyodide_ffi_module

    monkeypatch.setitem(sys.modules, "js", js_module)
    monkeypatch.setitem(sys.modules, "pyodide", pyodide_module)
    monkeypatch.setitem(sys.modules, "pyodide.ffi", pyodide_ffi_module)

    bridge_module = importlib.import_module("pyowasm.bridge.biowasm")
    bridge_module = importlib.reload(bridge_module)

    return {
        "js": js_module,
        "bridge_module": bridge_module,
    }

@pytest.mark.asyncio
async def test_biowasm_bridge_makeblastdb(biowasm_modules):
    """makeblastdb が正しく run_tool を呼び出すことを確認"""
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    bridge.run_tool = AsyncMock(return_value="makeblastdb success")
    
    fasta = ">seq1\nMAGT"
    result = await bridge.makeblastdb(fasta, db_name="mydb", db_type="prot")
    
    assert result == "makeblastdb success"
    bridge.run_tool.assert_awaited_once_with(
        "blast/2.11.0",
        "makeblastdb -in mydb.fasta -dbtype prot -out mydb",
        files={"mydb.fasta": fasta}
    )

@pytest.mark.asyncio
async def test_biowasm_bridge_blastp(biowasm_modules):
    """blastp が正しく run_tool を呼び出すことを確認"""
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    bridge.run_tool = AsyncMock(return_value="blastp results")
    
    query = ">query\nMAGT"
    result = await bridge.blastp(query, db_name="mydb")
    
    assert result == "blastp results"
    bridge.run_tool.assert_awaited_once_with(
        "blast/2.11.0",
        "blastp -query query.fasta -db mydb -outfmt 6",
        files={"query.fasta": query}
    )

@pytest.mark.asyncio
async def test_biowasm_bridge_run_tool_with_files(biowasm_modules):
    """run_tool が files 引数を JS に正しく渡すことを確認"""
    bridge = biowasm_modules["bridge_module"].BiowasmBridge()
    biowasm_modules["js"].eval.return_value = '{"status": "success", "data": "output", "debug": []}'
    
    files = {"test.txt": "hello"}
    await bridge.run_tool("tool", "cmd test.txt", files=files)
    
    # js._pyowasm_files がセットされていることを確認
    assert biowasm_modules["js"]._pyowasm_files == files
    biowasm_modules["js"].eval.assert_awaited_once()
