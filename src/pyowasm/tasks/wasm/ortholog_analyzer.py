import pandas as pd
from io import StringIO
from Bio import SeqIO
from Bio.Align import PairwiseAligner, substitution_matrices
from ..base import BaseTask
from ...ui.components import render_rbh_results

class OrthologAnalysisTask(BaseTask):
    """
    BioPython PairwiseAligner を使用して 2 種間のオーソログ解析（RBH）を行うタスク。
    """

    @staticmethod
    def _compute_best_hits(seqs_query, seqs_subject) -> pd.DataFrame:
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
        empty = pd.DataFrame(columns=["query_a", "query_b", "identity_a_to_b", "identity_b_to_a", "bitscore_a_to_b", "bitscore_b_to_a"])
        seqs_a = list(SeqIO.parse(StringIO(sample_a), "fasta"))
        seqs_b = list(SeqIO.parse(StringIO(sample_b), "fasta"))
        if not seqs_a or not seqs_b:
            return empty
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
