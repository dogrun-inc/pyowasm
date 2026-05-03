from dataclasses import dataclass
from typing import List, Optional

@dataclass
class SequenceRecord:
    """
    塩基配列またはアミノ酸配列の個別のレコードを保持するデータクラス。
    """
    id: str
    description: str
    sequence: str
    length: int
    gc_content: float = 0.0
    base_composition: Optional[dict[str, int]] = None

@dataclass
class AnalysisResult:
    """
    解析全体の実行結果を保持するデータクラス。
    """
    records: List[SequenceRecord]
    metadata: Optional[dict] = None
