import streamlit as st
from typing import Optional
from ..base import BaseTask
from ...bridge.biowasm import bridge

class SeqtkTask(BaseTask):
    """
    Wasm版 seqtk を使用して配列処理を行うタスク。
    """

    async def run(
        self,
        input_filename: str,
        command: str = "seq -a",
        input_content: Optional[str] = None,
    ) -> str:
        """
        seqtkを実行します。
        """
        full_command = command.strip()
        if input_filename not in full_command.split():
            full_command = f"{full_command} {input_filename}"

        files = None
        if input_content is not None:
            files = {input_filename: input_content}

        result = await bridge.seqtk(full_command, files=files)
        return result

    def render(self, result: str) -> None:
        """
        seqtkの実行結果を表示します。
        """
        st.write("### Seqtk 出力")
        if result.startswith("Wasm実行エラー:") or result.startswith("ブリッジ通信エラー:"):
            st.error("Wasm(seqtk) 実行でエラーが発生しました。")
            if "--- Debug Trace ---" in result:
                message, trace = result.split("--- Debug Trace ---", 1)
                st.code(message.strip())
                with st.expander("デバッグトレースを表示", expanded=True):
                    st.code(trace.strip())
            else:
                st.code(result)
            return

        st.success("Wasm(seqtk) での処理が完了しました。")
        st.code(result)
