from io import StringIO
from Bio import SeqIO
from ...models.schema import SequenceRecord, AnalysisResult
from ..base import BaseTask

class FastaParserTask(BaseTask):
    """
    BioPythonを使用してFASTA形式のデータをパースするタスク。
    """

    def execute(self, fasta_content: str) -> AnalysisResult:
        """
        FASTA文字列をパースし、SequenceRecordのリストを含むAnalysisResultを返す。

        Args:
            fasta_content (str): FASTA形式の文字列データ。

        Returns:
            AnalysisResult: パースされたレコードを含む結果。
        """
        records = []
        # StringIOを使用して文字列をファイルライクオブジェクトとして扱う
        fasta_io = StringIO(fasta_content)
        
        for record in SeqIO.parse(fasta_io, "fasta"):
            records.append(SequenceRecord(
                id=str(record.id),
                description=str(record.description),
                sequence=str(record.seq),
                length=len(record.seq)
            ))
            
        return AnalysisResult(records=records)
