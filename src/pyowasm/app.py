import streamlit as st
import asyncio
from pyowasm.ui.components import (
    display_header, 
    render_analysis_mode, 
    render_seqtk_mode, 
    render_ortholog_mode
)

st.set_page_config(page_title="Pyowasm", page_icon="🧬", layout="wide")

async def main():
    # ヘッダー表示
    display_header()

    # サイドバーでの機能選択
    st.sidebar.title("🛠️ 分析メニュー")
    mode = st.sidebar.radio(
        "実行するタスクを選択:",
        ["1. 配列統計 (BioPython)", "2. Wasmツール (biowasm)", "3. オーソログ解析 (RBH)"]
    )

    if mode == "1. 配列統計 (BioPython)":
        await render_analysis_mode()
    elif mode == "2. Wasmツール (biowasm)":
        render_seqtk_mode()
    else:
        await render_ortholog_mode()

if __name__ == "__main__":
    asyncio.run(main())
