import streamlit as st
from typing import Any, Optional
from ..base import BaseTask
from ...bridge.biowasm import bridge

class SeqtkTask(BaseTask):
    """
    Wasm版 seqtk を使用して配列処理を行うタスク。
    """

    def run(self, input_data: Any) -> str:
        """
        BaseTask 互換の実行入口。

        既存のUI実装は start/poll を使用するが、
        抽象基底クラス要件を満たすため run を提供する。
        """
        if not isinstance(input_data, dict):
            return "Wasm実行エラー: 入力形式が不正です。"

        input_filename = str(input_data.get("input_filename", "input.fasta"))
        command = str(input_data.get("command", "seq -a"))
        input_content_raw = input_data.get("input_content")
        input_content = str(input_content_raw) if input_content_raw is not None else None

        return self.start(
            input_filename=input_filename,
            command=command,
            input_content=input_content,
        )

    def start(
        self,
        input_filename: str,
        command: str = "seq -a",
        input_content: Optional[str] = None,
    ) -> str:
        """
        seqtk の実行ジョブを開始し、ジョブIDを返す。
        """
        full_command = command.strip()
        if input_filename not in full_command.split():
            full_command = f"{full_command} {input_filename}"

        files = None
        if input_content is not None:
            files = {input_filename: input_content}

        return bridge.start_tool_job("seqtk/1.3", f"seqtk {full_command}" if not full_command.startswith("seqtk") else full_command, files=files)

    def poll(self, job_id: str) -> dict[str, str]:
        """実行中ジョブの状態を取得する。"""
        return bridge.get_tool_job_result(job_id)

    def cleanup(self, job_id: str) -> None:
        """完了したジョブをクリーンアップする。"""
        bridge.clear_tool_job(job_id)

    def render(self, result: str) -> None:
        """
        seqtkの実行結果を表示します。
        """
        st.write("### Seqtk 出力")
        if (
            result.startswith("Wasm実行エラー:")
            or result.startswith("ブリッジ通信エラー:")
            or "Wasm ツールを利用できません" in result
        ):
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
