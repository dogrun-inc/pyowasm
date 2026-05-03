from Bio.SeqUtils import gc_fraction
from ...models.schema import SequenceRecord, AnalysisResult
from ..base import BaseTask

class SequenceAnalysisTask(BaseTask):
    """
    BioPythonを使用して配列の統計情報（GC含有量、塩基組成など）を計算するタスク。
    """

    def execute(self, records: list[SequenceRecord]) -> AnalysisResult:
        """
        SequenceRecordのリストを受け取り、各レコードの統計情報を計算して更新する。

        Args:
            records (list[SequenceRecord]): 解析対象のレコードリスト。

        Returns:
            AnalysisResult: 統計情報が更新されたレコードを含む結果。
        """
        for record in records:
            # GC含有量の計算
            record.gc_content = gc_fraction(record.sequence) * 100
            
            # 塩基組成の計算（1回走査で効率的に集計）
            composition: dict[str, int] = {}
            for base in record.sequence.upper():
                if base.isalpha():
                    composition[base] = composition.get(base, 0) + 1
            record.base_composition = composition
            
        return AnalysisResult(records=records)
