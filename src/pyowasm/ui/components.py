import streamlit as st
import pandas as pd
from typing import List
from ..models.schema import SequenceRecord

def display_sequence_stats(records: List[SequenceRecord]) -> None:
    """
    配列の統計情報を表示する。

    Args:
        records (List[SequenceRecord]): 表示対象の配列レコードリスト。
    """
    st.subheader("解析結果サマリー")
    col1, col2, col3 = st.columns(3)
    col1.metric("配列数", len(records))
    
    avg_len = sum(r.length for r in records) / len(records) if records else 0
    col2.metric("平均長", f"{avg_len:.1f} bp")
    
    avg_gc = sum(r.gc_content for r in records) / len(records) if records else 0
    col3.metric("平均GC含有量", f"{avg_gc:.1f} %")

    if records:
        st.divider()
        st.subheader("詳細解析")
        
        # 配列長の分布
        st.write("### 配列長の分布")
        lengths = [r.length for r in records]
        st.bar_chart(lengths)
        
        # GC含有量の分布
        st.write("### GC含有量の分布 (%)")
        gc_contents = [r.gc_content for r in records]
        st.line_chart(gc_contents)
        
        # 個別レコードの塩基組成
        if len(records) == 1:
            st.write("### 塩基組成")
            comp = records[0].base_composition
            if comp:
                df_comp = pd.DataFrame(list(comp.items()), columns=["Base", "Count"])
                st.bar_chart(df_comp.set_index("Base"))

async def display_biowasm_ui(input_filename: str) -> None:
    """
    Wasmバイオ情報学ツールを操作するためのUIを表示する。

    Args:
        input_filename (str): 入力ファイルのパス（VFS内）。
    """
    st.divider()
    st.header("🛠️ Wasm Tools (biowasm)")
    st.write(f"VFS内のファイルを処理します: `{input_filename}`")

    tool_options = ["seqtk"]
    selected_tool = st.selectbox("ツールを選択", tool_options)

    if selected_tool == "seqtk":
        command = st.text_input("コマンド引数", value="seq -a")
        
        result_container = st.container()
        
        if st.button("Wasmで実行"):
            from ..tasks.wasm.seqtk import SeqtkTask
            
            try:
                task = SeqtkTask()
                with st.spinner(f"{selected_tool} を実行中..."):
                    # 直接 await を使用して結果を待機する
                    result = await task.run(input_filename, command)

                with result_container:
                    task.render(result)
            except Exception as e:
                with result_container:
                    st.error(f"実行エラー: {str(e)}")

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
