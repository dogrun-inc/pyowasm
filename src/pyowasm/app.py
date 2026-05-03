import streamlit as st
from pyowasm.ui.components import display_header, display_sequence_stats
from pyowasm.tasks.local.fasta_parser import FastaParserTask

st.set_page_config(page_title="Pyowasm", page_icon="🧬")

# ヘッダー表示
display_header()

# ファイルアップローダー
uploaded_file = st.file_uploader("FASTAファイルをドロップ", type=["fasta"])

if uploaded_file:
    # --- Step 1: Python(Wasm)によるパース ---
    with st.status("Python (Wasm) で解析中...", expanded=True) as status:
        fasta_data = uploaded_file.getvalue().decode("utf-8")
        
        # タスクの実行
        parser = FastaParserTask()
        result = parser.execute(fasta_data)

        warnings = (result.metadata or {}).get("warnings", [])
        for warning in warnings:
            st.warning(warning)
        
        st.write(f"BioPythonを使用して {len(result.records)} 個の配列をパースしました。")
        
        # --- Step 2: 外部API/Wasmツールの実行（プレースホルダ） ---
        st.write("外部APIを確認中...")
        
        status.update(label="解析完了!", state="complete", expanded=False)

    # 結果の表示
    st.divider()
    display_sequence_stats(result.records)
