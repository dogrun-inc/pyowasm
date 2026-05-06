import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from pyowasm.ui.components import render_rbh_results, render_rbh_plots

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
