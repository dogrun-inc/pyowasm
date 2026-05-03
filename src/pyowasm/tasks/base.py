from abc import ABC, abstractmethod
from typing import Any
from ..models.schema import AnalysisResult

class BaseTask(ABC):
    """
    すべての解析タスクの基底となる抽象クラス。
    """

    @abstractmethod
    def execute(self, input_data: Any) -> AnalysisResult:
        """
        タスクを実行し、解析結果を返す。

        Args:
            input_data (Any): タスクへの入力データ。

        Returns:
            AnalysisResult: 解析結果オブジェクト。
        """
        pass
