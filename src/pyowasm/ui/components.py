import streamlit as st
from typing import List
from ..models.schema import SequenceRecord

def display_sequence_stats(records: List[SequenceRecord]) -> None:
    """
    配列の統計情報を表示する。

    Args:
        records (List[SequenceRecord]): 表示対象の配列レコードリスト。
    """
    st.subheader("解析結果")
    col1, col2 = st.columns(2)
    col1.metric("配列数", len(records))
    col2.metric("実行環境", "ブラウザ (Wasm)")

    if records:
        lengths = [r.length for r in records]
        st.bar_chart(lengths)

def display_header() -> None:
    """
    アプリケーションのヘッダーとブランディングを表示する。
    """
    st.title("🧬 Pyowasm")
    st.caption("Python × WebAssembly × Bioinformatics")

    st.markdown("""
    ### 🚀 ブラウザが次世代の解析プラットフォームになる
    **Pyowasm** は、環境構築不要のバイオ解析環境です。
    Pythonの柔軟性と、Wasm host（stlite/Pyodide）のポータビリティ、そしてクラウドAPIを統合します。
    """)
