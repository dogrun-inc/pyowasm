import streamlit as st
from ..base import BaseTask
from ...bridge.biowasm import bridge

class SeqtkTask(BaseTask):
    """
    Wasm版 seqtk を使用して配列処理を行うタスク。
    """

    async def run(self, input_filename: str, command: str = "seq -a") -> str:
        """
        seqtkを実行します。
        """
        result = await bridge.run_tool("seqtk/1.3", f"{command} {input_filename}")
        return result

    def render(self, result: str) -> None:
        """
        seqtkの実行結果を表示します。
        """
        st.success("Wasm(seqtk) での処理が完了しました。")
        st.write("### Seqtk 出力")
        st.code(result)
