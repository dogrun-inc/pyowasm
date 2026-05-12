import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import asyncio
from typing import List, Dict, Optional
from ..models.schema import SequenceRecord
from ..core.stats import get_identity_stats

MAX_RBH_SCATTER_POINTS = 500

# (render_rbh_plots, render_rbh_results は変更なし)

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
        if len(plot_df) > MAX_RBH_SCATTER_POINTS:
            plot_df = plot_df.nlargest(MAX_RBH_SCATTER_POINTS, "bitscore_a_to_b")
            st.info(
                f"RBH件数が多いため、ドットプロットは bitscore 上位 {MAX_RBH_SCATTER_POINTS} 件のみ表示しています。"
            )
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

async def render_analysis_mode() -> None:
    """
    配列統計解析モードのUIを表示します。
    """
    st.subheader("📊 配列統計解析")
    st.info("BioPythonを使用して、アップロードされたFASTAファイルの基本統計を計算します。")

    uploaded_file = st.file_uploader("FASTAファイルをアップロード", type=["fasta", "faa", "fastq"])

    if st.button("📊 解析を実行", use_container_width=True):
        if uploaded_file:
            # オーバーレイを表示
            overlay = st.empty()
            overlay.markdown("<style>#loading-overlay { display: flex !important; }</style>", unsafe_allow_html=True)
            
            # ブラウザに描画させるために一時停止
            await asyncio.sleep(0.1)
            
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

            # 結果を表示し、オーバーレイを消すためにリラン
            st.session_state["analysis_result"] = analysis_result.records
            overlay.empty()
            st.rerun()
        else:
            st.warning("解析対象のファイルをアップロードしてください。")

    if "analysis_result" in st.session_state:
        display_sequence_stats(st.session_state["analysis_result"])


async def render_seqtk_mode() -> None:
    """
    Seqtk実行モードのUIを表示します。
    """
    st.subheader("🔧 Wasmツール (biowasm)")
    st.info("JS/Wasm ブリッジを介して、ブラウザ内で seqtk を直接実行します。")

    from ..bridge.biowasm import bridge

    if not bridge.is_available():
        st.info(bridge.unavailable_message())
        return

    uploaded_file = st.file_uploader("ファイルをアップロード", type=["fasta", "fastq"])
    vfs_path = "input.fasta"
    input_content = None

    if uploaded_file:
        input_content = uploaded_file.getvalue().decode("utf-8")
        bridge.write_to_vfs(vfs_path, input_content)

    await display_biowasm_ui(vfs_path, input_content=input_content)

async def render_ortholog_mode() -> None:
    """
    オーソログ解析モードのUIを表示します。
    """
    st.subheader("🧪 オーソログ解析 (RBH)")
    st.info("Wasm 上で RBH 解析パイプラインを実行します。")

    keyword_input = st.text_input(
        "キーワード抽出用キーワード（カンマ区切り）",
        value="caffeine synthase, methyltransferase, xanthosine",
        help="解析対象の配列を絞り込むためのキーワード。カンマ区切りで入力してください。"
    )
    target_keywords = [k.strip() for k in keyword_input.split(",") if k.strip()]

    col_k, col_top = st.columns(2)

    with col_k:
        k_size = st.slider(
            "k-mer サイズ (k)",
            min_value=3, max_value=6, value=4,
            help="アミノ酸 k-mer のサイズ。大きいほど精度↑・ヒット率↓。",
        )
    with col_top:
        top_n = st.slider(
            "候補数 (top_n)",
            min_value=5, max_value=100, value=20,
            help="k-mer スコア上位何件に精密アラインメントを実施するか。",
        )

    st.write("### FAA ファイルをアップロード")
    col1, col2 = st.columns(2)
    data_a, data_b = "", ""
    with col1:
        file_a = st.file_uploader("Species A の FAA ファイル", type=["faa", "fasta"])
        if file_a:
            data_a = file_a.getvalue().decode("utf-8")
    with col2:
        file_b = st.file_uploader("Species B の FAA ファイル", type=["faa", "fasta"])
        if file_b:
            data_b = file_b.getvalue().decode("utf-8")

    if st.button("🚀 RBHパイプラインを実行", use_container_width=True):
        if data_a and data_b:
            # オーバーレイを表示
            overlay = st.empty()
            overlay.markdown("<style>#loading-overlay { display: flex !important; }</style>", unsafe_allow_html=True)

            # ブラウザに描画させるために一時停止
            await asyncio.sleep(0.1)

            from ..tasks.wasm.ortholog_analyzer import OrthologAnalysisTask
            task = OrthologAnalysisTask()
            try:
                with st.status("RBH解析実行中...", expanded=True) as status:
                    result = task.run(
                        data_a,
                        data_b,
                        keywords_a=target_keywords,
                        keywords_b=target_keywords,
                        k=k_size,
                        top_n=top_n,
                    )
                    status.update(label="解析完了!", state="complete")
                
                # 結果を保持（リランで消えないように）
                st.session_state["ortholog_result"] = result
                st.session_state["ortholog_warnings"] = task.last_warnings
                st.session_state["ortholog_excluded"] = task.last_excluded_records
                
                # オーバーレイを消すためにリラン
                overlay.empty()
                st.rerun()
            except Exception as e:
                st.error(f"RBH解析でエラーが発生しました: {e}")
        else:
            st.warning("両方の入力データが必要です。")

    if "ortholog_result" in st.session_state:
        for warning_message in st.session_state.get("ortholog_warnings", []):
            st.warning(warning_message)
        if st.session_state.get("ortholog_excluded"):
            with st.expander("除外したレコード一覧を表示"):
                st.dataframe(pd.DataFrame(st.session_state["ortholog_excluded"]))
        render_rbh_results(st.session_state["ortholog_result"])

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
    import time

    tool_options = ["seqtk"]
    selected_tool = st.selectbox("ツールを選択", tool_options)


    is_busy = st.session_state.get("is_processing", False) or st.session_state.get("pyowasm_seqtk_job_id") is not None

    result_key = "pyowasm_seqtk_last_result"

    if selected_tool == "seqtk":
        from ..tasks.wasm.seqtk import SeqtkTask

        command = st.text_input("コマンド引数", value="seq -a")

        result_container = st.container()

        job_key = "pyowasm_seqtk_job_id"
        job_start_time_key = "pyowasm_seqtk_job_start_time"
        task = SeqtkTask()

        if st.button("🚀 Wasmで実行", key="pyowasm_seqtk_run", use_container_width=True, disabled=is_busy):
            # 新しい実行の前に過去の結果をクリア
            if result_key in st.session_state:
                del st.session_state[result_key]
                
            job_id = task.start(input_filename, command, input_content=input_content)
            if job_id.startswith("ERROR:"):
                with result_container:
                    st.error(job_id.replace("ERROR:", "", 1).strip())
            else:
                st.session_state[job_key] = job_id
                st.session_state[job_start_time_key] = time.time()
                # 実行開始時にオーバーレイを表示
                st.markdown("<style>#loading-overlay { display: flex !important; }</style>", unsafe_allow_html=True)
                await asyncio.sleep(0.1)
                st.rerun()

        current_job_id = st.session_state.get(job_key)
        if current_job_id:
            # ポーリングループ
            while True:
                status = task.poll(str(current_job_id))
                if status["status"] == "running":
                    elapsed = time.time() - st.session_state.get(job_start_time_key, time.time())
                    with result_container:
                        # 画面上の進捗表示
                        st.info(f"⏳ seqtk 実行中です... ({elapsed:.1f}秒経過)")
                    # オーバーレイを確実に表示
                    st.markdown("<style>#loading-overlay { display: flex !important; }</style>", unsafe_allow_html=True)
                    await asyncio.sleep(0.5)
                else:
                    # 完了
                    st.session_state[result_key] = status["result"]
                    task.cleanup(str(current_job_id))
                    del st.session_state[job_key]
                    if job_start_time_key in st.session_state:
                        del st.session_state[job_start_time_key]
                    # オーバーレイを消すためにリラン
                    st.rerun()
                    break

        # 保存された結果がある場合は表示
        if result_key in st.session_state:
            with result_container:
                task.render(st.session_state[result_key])

def display_header() -> None:
    """
    アプリケーションのヘッダーとブランディングを表示する。
    """
    st.title("🧬 Pyowasm")
    st.caption("Python × WebAssembly × Bioinformatics")

