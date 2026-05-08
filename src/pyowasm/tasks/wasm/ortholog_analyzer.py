import pandas as pd
from io import StringIO
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.Align import PairwiseAligner, substitution_matrices
from ..base import BaseTask
from ...ui.components import render_rbh_results

ALLOWED_AMINO_ACIDS = set(substitution_matrices.load("BLOSUM62").alphabet)

class OrthologAnalysisTask(BaseTask):
    """
    BioPython PairwiseAligner を使用して 2 種間のオーソログ解析（RBH）を行うタスク。
    """

    def __init__(self) -> None:
        """直近の入力検証結果を保持する。"""
        self.last_warnings: list[str] = []
        self.last_excluded_records: list[dict[str, object]] = []

    @staticmethod
    def _normalize_fasta_content(fasta_content: str) -> str:
        """FASTA 文字列全体から BOM と行末空白を除去する。"""
        cleaned = fasta_content.replace("\ufeff", "")
        return "\n".join(line.rstrip() for line in cleaned.splitlines())

    @staticmethod
    def _normalize_sequence(sequence: str) -> str:
        """配列文字列をアラインメント前に正規化する。"""
        return sequence.replace("\ufeff", "").strip().upper()

    def _sanitize_sequences(self, records: list[SeqRecord], species_label: str) -> list[SeqRecord]:
        """配列を正規化し、BLOSUM62 非対応文字を含むレコードを除外する。"""
        sanitized_records: list[SeqRecord] = []

        for record in records:
            normalized = self._normalize_sequence(str(record.seq))
            invalid_chars = sorted(set(normalized) - ALLOWED_AMINO_ACIDS)

            if invalid_chars:
                self.last_excluded_records.append({
                    "species": species_label,
                    "record_id": record.id,
                    "invalid_chars": "".join(invalid_chars),
                    "length": len(normalized),
                })
                continue

            sanitized_records.append(
                SeqRecord(Seq(normalized), id=record.id, description=record.description)
            )

        return sanitized_records

    def _update_validation_summary(self) -> None:
        """除外レコード数に応じた警告メッセージを更新する。"""
        if not self.last_excluded_records:
            return

        counts: dict[str, int] = {}
        for record in self.last_excluded_records:
            species = str(record["species"])
            counts[species] = counts.get(species, 0) + 1

        summary = "、".join(f"{species} {count}件" for species, count in counts.items())
        total = len(self.last_excluded_records)
        self.last_warnings.append(
            f"BLOSUM62 非対応文字を含むレコードを除外して続行しました（{summary}、合計 {total}件）。"
        )

    @staticmethod
    def _compute_best_hits(seqs_query: list[SeqRecord], seqs_subject: list[SeqRecord]) -> pd.DataFrame:
        """クエリ集合ごとに最良ヒットを計算する。"""
        aligner = PairwiseAligner()
        aligner.substitution_matrix = substitution_matrices.load("BLOSUM62")
        aligner.open_gap_score = -11
        aligner.extend_gap_score = -1
        self_scores = {r.id: aligner.score(str(r.seq), str(r.seq)) for r in seqs_query}
        rows = []
        for q in seqs_query:
            best_score = None
            best_sid = None
            for s in seqs_subject:
                sc = aligner.score(str(q.seq), str(s.seq))
                if best_score is None or sc > best_score:
                    best_score = sc
                    best_sid = s.id
            if best_sid is not None:
                ss = self_scores[q.id]
                identity = min(best_score / ss * 100, 100.0) if ss > 0 else 0.0
                rows.append({"query": q.id, "subject": best_sid, "identity": identity, "score": float(best_score)})
        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["query", "subject", "identity", "score"])

    async def run(self, sample_a: str, sample_b: str) -> pd.DataFrame:
        """2 種の FAA データから RBH を計算し、必要に応じて不正レコードを除外する。"""
        self.last_warnings = []
        self.last_excluded_records = []
        empty = pd.DataFrame(columns=["query_a", "query_b", "identity_a_to_b", "identity_b_to_a", "bitscore_a_to_b", "bitscore_b_to_a"])
        normalized_a = self._normalize_fasta_content(sample_a)
        normalized_b = self._normalize_fasta_content(sample_b)
        seqs_a = list(SeqIO.parse(StringIO(normalized_a), "fasta"))
        seqs_b = list(SeqIO.parse(StringIO(normalized_b), "fasta"))
        if not seqs_a or not seqs_b:
            return empty
        seqs_a = self._sanitize_sequences(seqs_a, "Species A")
        seqs_b = self._sanitize_sequences(seqs_b, "Species B")
        self._update_validation_summary()
        df_ab = self._compute_best_hits(seqs_a, seqs_b)
        df_ba = self._compute_best_hits(seqs_b, seqs_a)
        if df_ab.empty or df_ba.empty:
            return empty
        rbh = pd.merge(
            df_ab, df_ba,
            left_on=["query", "subject"],
            right_on=["subject", "query"],
            suffixes=("_fwd", "_rev")
        )
        if rbh.empty:
            return empty
        return rbh[["query_fwd", "subject_fwd", "identity_fwd", "identity_rev", "score_fwd", "score_rev"]].rename(columns={
            "query_fwd": "query_a",
            "subject_fwd": "query_b",
            "identity_fwd": "identity_a_to_b",
            "identity_rev": "identity_b_to_a",
            "score_fwd": "bitscore_a_to_b",
            "score_rev": "bitscore_b_to_a",
        })

    def render(self, result: pd.DataFrame) -> None:
        render_rbh_results(result)
