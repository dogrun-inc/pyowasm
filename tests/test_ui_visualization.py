import pytest
import pandas as pd
import asyncio
from unittest.mock import MagicMock, patch
from pyowasm.ui.components import render_rbh_results, render_rbh_plots, render_ortholog_mode

@pytest.fixture
def sample_rbh_df():
    return pd.DataFrame({
        "query_a": ["seq1", "seq2", "seq3"],
        "query_b": ["seqA", "seqB", "seqC"],
        "identity_a_to_b": [98.0, 95.5, 92.0],
        "identity_b_to_a": [98.0, 95.0, 91.5],
        "bitscore_a_to_b": [200, 150, 100],
        "bitscore_b_to_a": [200, 145, 98]
    })

def test_render_rbh_plots(sample_rbh_df):
    with patch("pyowasm.ui.components.st.pyplot") as mock_pyplot, \
         patch("pyowasm.ui.components.st.write") as mock_write, \
         patch("pyowasm.ui.components.st.columns") as mock_columns:
        
        # Mock columns to return contexts
        mock_col1 = MagicMock()
        mock_col2 = MagicMock()
        mock_columns.return_value = [mock_col1, mock_col2]
        
        render_rbh_plots(sample_rbh_df)
        
        # Check if plots were rendered
        assert mock_pyplot.call_count == 2
        mock_write.assert_any_call("### Identity 分布")
        mock_write.assert_any_call("### ドットプロット (Synteny)")

def test_render_rbh_results(sample_rbh_df):
    with patch("pyowasm.ui.components.st") as mock_st, \
         patch("pyowasm.ui.components.render_rbh_plots") as mock_render_plots:
        
        # Mock columns to return mocks for col1, col2, col3
        mock_col1 = MagicMock()
        mock_col2 = MagicMock()
        mock_col3 = MagicMock()
        mock_st.columns.return_value = [mock_col1, mock_col2, mock_col3]
        
        render_rbh_results(sample_rbh_df)
        
        assert mock_st.header.called
        # Check if metric was called on each column
        mock_col1.metric.assert_called()
        mock_col2.metric.assert_called()
        mock_col3.metric.assert_called()
        
        mock_render_plots.assert_called_once_with(sample_rbh_df)
        mock_st.dataframe.assert_called_once()

def test_render_rbh_results_empty():
    empty_df = pd.DataFrame()
    with patch("pyowasm.ui.components.st.warning") as mock_warning:
        render_rbh_results(empty_df)
        mock_warning.assert_called_once()


def test_render_rbh_plots_limits_large_scatter_data():
    large_df = pd.DataFrame({
        "query_a": [f"q{i}" for i in range(600)],
        "query_b": [f"s{i}" for i in range(600)],
        "identity_a_to_b": [90.0] * 600,
        "identity_b_to_a": [90.0] * 600,
        "bitscore_a_to_b": list(range(600)),
        "bitscore_b_to_a": list(range(600)),
    })

    with patch("pyowasm.ui.components.st.pyplot"), \
         patch("pyowasm.ui.components.st.write"), \
         patch("pyowasm.ui.components.st.columns") as mock_columns, \
         patch("pyowasm.ui.components.st.info") as mock_info, \
         patch("pyowasm.ui.components.sns.scatterplot") as mock_scatter:
        mock_col1 = MagicMock()
        mock_col2 = MagicMock()
        mock_columns.return_value = [mock_col1, mock_col2]

        render_rbh_plots(large_df)

        mock_info.assert_called_once()
        plot_data = mock_scatter.call_args.kwargs["data"]
        assert len(plot_data) == 500


class _FakeUpload:
    def __init__(self, text: str) -> None:
        self._text = text

    def getvalue(self) -> bytes:
        return self._text.encode("utf-8")


def _context_columns(n: int):
    cols = []
    for _ in range(n):
        col = MagicMock()
        col.__enter__.return_value = col
        col.__exit__.return_value = False
        cols.append(col)
    return cols


def test_render_ortholog_mode_faa_upload_executes_task(monkeypatch):
    class FakeTask:
        def __init__(self) -> None:
            self.last_warnings = []
            self.last_excluded_records = []
            self.called = False

        def run(self, sample_a, sample_b, keywords_a=None, keywords_b=None, k=4, top_n=20):
            self.called = True
            assert ">a1" in sample_a
            assert ">b1" in sample_b
            assert keywords_a is not None and keywords_b is not None
            assert k == 4
            assert top_n == 20
            return pd.DataFrame()

        def render(self, result):
            assert isinstance(result, pd.DataFrame)

    fake_task = FakeTask()
    monkeypatch.setattr(
        "pyowasm.tasks.wasm.ortholog_analyzer.OrthologAnalysisTask",
        lambda: fake_task,
    )

    with patch("pyowasm.ui.components.st") as mock_st:
        mock_st.slider.side_effect = [4, 20]
        # input_method (radio) は削除されたため、side_effect から除外。
        # 代わりに text_input (キーワード) が呼ばれる。
        mock_st.text_input.return_value = "caffeine, methyltransferase"
        mock_st.file_uploader.side_effect = [
            _FakeUpload(">a1\nACDE\n"),
            _FakeUpload(">b1\nACDE\n"),
        ]
        mock_st.button.return_value = True
        mock_st.columns.side_effect = [
            _context_columns(2), # col_k, col_top
            _context_columns(2), # col1, col2 (file upload)
        ]
        # st.status は削除されたため、mock_st.status は不要

        asyncio.run(render_ortholog_mode())

        assert fake_task.called


def test_render_ortholog_mode_faa_upload_requires_both_files(monkeypatch):
    class FakeTask:
        def run(self, *args, **kwargs):
            raise AssertionError("run should not be called when one file is missing")

    monkeypatch.setattr(
        "pyowasm.tasks.wasm.ortholog_analyzer.OrthologAnalysisTask",
        lambda: FakeTask(),
    )

    with patch("pyowasm.ui.components.st") as mock_st:
        mock_st.slider.side_effect = [4, 20]
        mock_st.text_input.return_value = "caffeine"
        mock_st.file_uploader.side_effect = [
            _FakeUpload(">a1\nACDE\n"),
            None,
        ]
        mock_st.button.return_value = True
        mock_st.columns.side_effect = [
            _context_columns(2),
            _context_columns(2),
        ]

        asyncio.run(render_ortholog_mode())

        mock_st.warning.assert_called_with("両方の入力データが必要です。")
