import sys
import types

import pytest

streamlit_module = types.ModuleType("streamlit")
seaborn_module = types.ModuleType("seaborn")
matplotlib_module = types.ModuleType("matplotlib")
pyplot_module = types.ModuleType("matplotlib.pyplot")
matplotlib_module.pyplot = pyplot_module

sys.modules.setdefault("streamlit", streamlit_module)
sys.modules.setdefault("seaborn", seaborn_module)
sys.modules.setdefault("matplotlib", matplotlib_module)
sys.modules.setdefault("matplotlib.pyplot", pyplot_module)

from pyowasm.tasks.wasm.ortholog_analyzer import OrthologAnalysisTask


def test_normalize_sequence_uppercases_and_removes_bom() -> None:
    task = OrthologAnalysisTask()

    normalized = task._normalize_sequence("  acd\ufeffe  ")

    assert normalized == "ACDE"


@pytest.mark.asyncio
async def test_run_excludes_invalid_records_and_continues() -> None:
    task = OrthologAnalysisTask()
    sample_a = ">a1\nacde\n"
    sample_b = ">b1\nACDE\n>b2\nACDU\n"

    result = await task.run(sample_a, sample_b)

    assert len(result) == 1
    assert result.iloc[0]["query_a"] == "a1"
    assert result.iloc[0]["query_b"] == "b1"
    assert len(task.last_excluded_records) == 1
    assert task.last_excluded_records[0]["record_id"] == "b2"
    assert task.last_excluded_records[0]["invalid_chars"] == "U"
    assert any("合計 1件" in message for message in task.last_warnings)


@pytest.mark.asyncio
async def test_run_handles_bom_without_excluding_record() -> None:
    task = OrthologAnalysisTask()
    sample_a = ">a1\nACD\ufeffE\n"
    sample_b = ">b1\nACDE\n"

    result = await task.run(sample_a, sample_b)

    assert len(result) == 1
    assert task.last_excluded_records == []
    assert task.last_warnings == []