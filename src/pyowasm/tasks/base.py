from abc import ABC, abstractmethod
from typing import Any
from ..models.schema import AnalysisResult

class BaseTask(ABC):
    """
    すべての解析タスクの基底となる抽象クラス。
    """

    @abstractmethod
    def run(self, input_data: Any) -> Any:
        """
        タスクを実行し、解析結果を返す。

        Args:
            input_data (Any): タスクへの入力データ。

        Returns:
            Any: 解析結果。
        """
        pass

    def render(self, result: Any) -> None:
        """
        解析結果をStreamlit UIにレンダリングします。
        デフォルトでは結果をコードブロックとして表示します。
        """
        import streamlit as st
        st.write("### 解析結果")
        st.code(str(result))
