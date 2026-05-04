from io import StringIO
from Bio import SeqIO
from ...models.schema import SequenceRecord, AnalysisResult
from ..base import BaseTask

class FastaParserTask(BaseTask):
    """
    BioPythonを使用してFASTA形式のデータをパースするタスク。
    """

    def run(self, fasta_content: str) -> AnalysisResult:
        """
        FASTA文字列をパースし、SequenceRecordのリストを含むAnalysisResultを返す。

        Args:
            fasta_content (str): FASTA形式の文字列データ。

        Returns:
            AnalysisResult: パースされたレコードを含む結果。
        """
        records = []
        warnings: list[str] = []

        if not fasta_content.strip():
            return AnalysisResult(records=records, metadata={"warnings": warnings})

        first_non_empty_line = next((line for line in fasta_content.splitlines() if line.strip()), "")
        if first_non_empty_line and not first_non_empty_line.startswith(">"):
            warnings.append("FASTAヘッダ(`>`)から始まっていないため、入力形式が不正の可能性があります。")

        # StringIOを使用して文字列をファイルライクオブジェクトとして扱う
        fasta_io = StringIO(fasta_content)

        try:
            for record in SeqIO.parse(fasta_io, "fasta"):
                records.append(SequenceRecord(
                    id=str(record.id),
                    description=str(record.description),
                    sequence=str(record.seq),
                    length=len(record.seq)
                ))
        except ValueError as error:
            warnings.append(f"FASTAのパース中に警告が発生しました: {error}")

        return AnalysisResult(records=records, metadata={"warnings": warnings})
