import streamlit as st
from pyowasm.ui.components import (
    display_header, 
    render_analysis_mode, 
    render_seqtk_mode, 
    render_ortholog_mode
)

st.set_page_config(page_title="Pyowasm", page_icon="🧬", layout="wide")

# ヘッダー表示
display_header()

# サイドバーでの機能選択
st.sidebar.title("🛠️ 分析メニュー")
mode = st.sidebar.radio(
    "実行するタスクを選択:",
    ["1. 配列統計 (BioPython)", "2. Wasmツール直接実行 (Seqtk)", "3. オーソログ解析デモ (RBH/BLAST)"]
)

if mode == "1. 配列統計 (BioPython)":
    render_analysis_mode()
elif mode == "2. Wasmツール直接実行 (Seqtk)":
    await render_seqtk_mode()
else:
    await render_ortholog_mode()
