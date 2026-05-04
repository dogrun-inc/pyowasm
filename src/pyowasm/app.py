import streamlit as st
from pyowasm.ui.components import display_header, display_sequence_stats, display_biowasm_ui
from pyowasm.tasks.local.fasta_parser import FastaParserTask
from pyowasm.tasks.local.sequence_analyzer import SequenceAnalysisTask
from pyowasm.bridge.biowasm import bridge

st.set_page_config(page_title="Pyowasm", page_icon="🧬")

# ヘッダー表示
display_header()

# ファイルアップローダー
uploaded_file = st.file_uploader("FASTAファイルをドロップ", type=["fasta"])

if uploaded_file:
    # --- Step 1: Python(Wasm)によるパース ---
    with st.status("Python (Wasm) で解析中...", expanded=True) as status:
        fasta_data = uploaded_file.getvalue().decode("utf-8")
        
        # VFSへの保存（Wasmツール共有用）
        vfs_path = "input.fasta"
        bridge.write_to_vfs(vfs_path, fasta_data)

        # タスクの実行
        parser = FastaParserTask()
        parse_result = parser.run(fasta_data)

        warnings = (parse_result.metadata or {}).get("warnings", [])
        for warning in warnings:
            st.warning(warning)
        
        st.write(f"BioPythonを使用して {len(parse_result.records)} 個の配列をパースしました。")

        # 解析タスクの実行
        st.write("統計情報を計算中...")
        analyzer = SequenceAnalysisTask()
        analysis_result = analyzer.run(parse_result.records)
        
        # --- Step 2: 外部API/Wasmツールの実行 ---
        st.write("Wasmエンジンの準備完了")
        
        status.update(label="解析完了!", state="complete", expanded=False)

    # 結果の表示
    st.divider()
    display_sequence_stats(analysis_result.records)

    # Biowasm UI の表示
    display_biowasm_ui(vfs_path)
