import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from typing import List, Dict, Optional
from ..models.schema import SequenceRecord
from ..core.stats import get_identity_stats

def render_rbh_plots(rbh_df: pd.DataFrame) -> None:
    """
    RBHの結果を可視化するグラフを生成・表示します。
    """
    if rbh_df.empty:
        st.warning("表示するデータがありません。")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.write("### Identity 分布")
        fig, ax = plt.subplots()
        sns.histplot(rbh_df["identity_a_to_b"], bins=20, kde=True, ax=ax, color="skyblue")
        ax.set_xlabel("Identity (%)")
        ax.set_ylabel("Frequency")
        st.pyplot(fig)

    with col2:
        st.write("### ドットプロット (Synteny)")
        # インデックスに基づく簡易的なドットプロット
        # クエリ名をソートして並べることで大まかな傾向を見る
        plot_df = rbh_df.copy()
        plot_df = plot_df.sort_values(["query_a", "query_b"])
        
        fig, ax = plt.subplots()
        sns.scatterplot(
            data=plot_df, 
            x="query_a", 
            y="query_b", 
            size="bitscore_a_to_b", 
            hue="identity_a_to_b",
            ax=ax,
            legend=False,
            alpha=0.6
        )
        ax.set_xticks([]) # ラベルが多いと重なるため非表示
        ax.set_yticks([])
        ax.set_xlabel("Species A Genes")
        ax.set_ylabel("Species B Genes")
        st.pyplot(fig)

def render_rbh_results(rbh_df: pd.DataFrame) -> None:
    """
    RBH解析の結果サマリーとグラフを表示します。
    """
    st.divider()
    st.header("📊 オーソログ解析結果 (RBH)")

    stats = get_identity_stats(rbh_df)
    
    if stats["count"] == 0:
        st.warning("オーソログが見つかりませんでした。")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("オーソログ数", stats["count"])
    col2.metric("平均一致率", f"{stats['mean']:.1f} %")
    col3.metric("最高一致率", f"{stats['max']:.1f} %")

    render_rbh_plots(rbh_df)

    with st.expander("詳細データ一覧を表示"):
        st.dataframe(rbh_df)

def render_analysis_mode() -> None:
    """
    配列統計解析モードのUIを表示します。
    """
    st.subheader("📊 配列統計解析")
    st.info("BioPythonを使用して、アップロードされたFASTAファイルの基本統計を計算します。")

    uploaded_file = st.file_uploader("FASTAファイルをアップロード", type=["fasta", "faa", "fastq"])

    if uploaded_file:
        from ..tasks.local.fasta_parser import FastaParserTask
        from ..tasks.local.sequence_analyzer import SequenceAnalysisTask
        from ..bridge.biowasm import bridge

        with st.status("Python (Wasm) で解析中...", expanded=True) as status:
            fasta_data = uploaded_file.getvalue().decode("utf-8")
            bridge.write_to_vfs("input.fasta", fasta_data)

            parser = FastaParserTask()
            parse_result = parser.run(fasta_data)

            analyzer = SequenceAnalysisTask()
            analysis_result = analyzer.run(parse_result.records)

            status.update(label="解析完了!", state="complete")

        display_sequence_stats(analysis_result.records)

async def render_seqtk_mode() -> None:
    """
    Seqtk実行モードのUIを表示します。
    """
    st.subheader("🔧 Wasm ツール実行 (Seqtk)")
    st.markdown(r"""
    JS/Wasm ブリッジを介して、ブラウザ内で \`seqtk\` を直接実行します。
    """)
    from ..bridge.biowasm import bridge
    uploaded_file = st.file_uploader("ファイルをアップロード", type=["fasta", "fastq"])
    vfs_path = "input.fasta"
    input_content = None

    if uploaded_file:
        input_content = uploaded_file.getvalue().decode("utf-8")
        bridge.write_to_vfs(vfs_path, input_content)

    await display_biowasm_ui(vfs_path, input_content=input_content)

async def render_ortholog_mode() -> None:
    """
    オーソログ解析デモモードのUIを表示します。
    """
    st.subheader("🧪 コーヒー品種間オーソログ解析デモ")
    st.markdown("""
    アラビカ種 vs ロブスタ種。
    Wasm 上で RBH 解析パイプラインを実行します。
    """)

    input_method = st.radio("入力方法を選択:", ["サンプルテキスト", "FAAファイルをアップロード"], horizontal=True)

    sample_a = ">arabica_P1 caffeine_synthase\\nMEVEKVKVGVDGFGRIGRLVTRAAFNSGKVDIVAINDPFIDLNYM\\n>arabica_P2 coffee_aroma\\nMAQTQGTRKVCYYYDRKGRRKSRKPRK"
    sample_b = ">robusta_P1 caffeine_synthase\\nMEVEKVKVGVDGFGRIGRLVTRAAFNSGKVDIVAINDPFIDLNYM\\n>robusta_P3 unexpected_hit\\nMAQTQGTRKVCYYYDRKGRRKSRK"

    data_a, data_b = "", ""

    if input_method == "サンプルテキスト":
        col1, col2 = st.columns(2)
        with col1:
            data_a = st.text_area("Species A (Arabica) サンプル", sample_a, height=150)
        with col2:
            data_b = st.text_area("Species B (Robusta) サンプル", sample_b, height=150)
    else:
        col1, col2 = st.columns(2)
        with col1:
            file_a = st.file_uploader("Species A の FAA ファイル", type=["faa", "fasta"])
            if file_a:
                data_a = file_a.getvalue().decode("utf-8")
        with col2:
            file_b = st.file_uploader("Species B の FAA ファイル", type=["faa", "fasta"])
            if file_b:
                data_b = file_b.getvalue().decode("utf-8")

    if st.button("RBHパイプラインを実行"):
        if data_a and data_b:
            from ..tasks.wasm.ortholog_analyzer import OrthologAnalysisTask
            task = OrthologAnalysisTask()
            try:
                with st.status("Wasm-BLAST 実行中...", expanded=True) as status:
                    result = await task.run(data_a, data_b)
                    status.update(label="解析完了!", state="complete")
                task.render(result)
            except Exception as e:
                st.error(f"RBH解析でエラーが発生しました: {e}")
        else:
            st.warning("両方の入力データが必要です。")

def display_sequence_stats(records: List[SequenceRecord]) -> None:
    """
    配列の統計情報を表示する。
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


async def display_biowasm_ui(input_filename: str, input_content: Optional[str] = None) -> None:
    """
    Wasmバイオ情報学ツールを操作するためのUIを表示する。

    Args:
        input_filename (str): 入力ファイルのパス（VFS内）。
    """
    st.divider()
    st.header("🛠️ Wasm Tools (biowasm)")
    st.write(f"VFS内のファイルを処理します: \\`{input_filename}\\`")

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
                    result = await task.run(input_filename, command, input_content=input_content)

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
