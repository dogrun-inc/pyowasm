import pandas as pd
import re
from collections import defaultdict
from io import StringIO
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.Align import PairwiseAligner, substitution_matrices
from ..base import BaseTask

ALLOWED_AMINO_ACIDS = set(substitution_matrices.load("BLOSUM62").alphabet)

class OrthologAnalysisTask(BaseTask):
    """
    k-mer 候補絞り込み + BioPython PairwiseAligner を使用して 2 種間のオーソログ解析（RBH）を行うタスク。
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

    @staticmethod
    def _normalize_text_for_keyword_match(text: str) -> str:
        """キーワード照合用に区切り文字を空白へ寄せて正規化する。"""
        normalized = text.replace("_", " ").replace("-", " ").lower()
        return re.sub(r"\s+", " ", normalized).strip()

    def _filter_records_by_keywords(
        self,
        records: list[SeqRecord],
        species_label: str,
        keywords: list[str],
    ) -> list[SeqRecord]:
        """description にキーワードを含むレコードのみ残す。"""
        cleaned_keywords = [k.strip() for k in keywords if k and k.strip()]
        if not cleaned_keywords:
            return records

        pattern = re.compile(
            "|".join(re.escape(self._normalize_text_for_keyword_match(k)) for k in cleaned_keywords),
            re.IGNORECASE,
        )

        selected: list[SeqRecord] = []
        for record in records:
            normalized_description = self._normalize_text_for_keyword_match(record.description)
            if pattern.search(normalized_description):
                selected.append(record)

        filtered_out = len(records) - len(selected)
        self.last_warnings.append(
            f"{species_label} をキーワード抽出しました（キーワード {len(cleaned_keywords)}件、"
            f"抽出 {len(selected)}件、除外 {filtered_out}件）。"
        )
        return selected

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
    def _build_kmer_index(seqs: list[SeqRecord], k: int = 4) -> dict[str, set[str]]:
        """k-mer インデックスを構築する。

        Returns:
            {kmer文字列: {seq_id, ...}} の辞書
        """
        index: dict[str, set[str]] = defaultdict(set)
        for record in seqs:
            seq = str(record.seq)
            for i in range(len(seq) - k + 1):
                index[seq[i:i + k]].add(record.id)
        return index

    @staticmethod
    def _get_candidates(
        query_record: SeqRecord,
        subject_index: dict[str, set[str]],
        subject_kmer_sets: dict[str, set[str]],
        top_n: int = 20,
        k: int = 4,
    ) -> list[tuple[str, float]]:
        """クエリに対して Jaccard 類似度上位 top_n の候補 subject ID を返す。

        Returns:
            [(seq_id, jaccard_score), ...] (降順ソート済み)
        """
        query_seq = str(query_record.seq)
        query_kmers = set(query_seq[i:i + k] for i in range(len(query_seq) - k + 1))

        shared_counts: dict[str, int] = {}
        for kmer in query_kmers:
            if kmer in subject_index:
                for sid in subject_index[kmer]:
                    shared_counts[sid] = shared_counts.get(sid, 0) + 1

        if not shared_counts:
            return []

        candidates: list[tuple[str, float]] = []
        for sid, shared in shared_counts.items():
            subject_kmers = subject_kmer_sets[sid]
            union = len(query_kmers) + len(subject_kmers) - shared
            jaccard = shared / union if union > 0 else 0.0
            candidates.append((sid, jaccard))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_n]

    def _compute_best_hits_fast(
        self,
        seqs_query: list[SeqRecord],
        seqs_subject: list[SeqRecord],
        k: int = 4,
        top_n: int = 20,
    ) -> pd.DataFrame:
        """k-mer 候補絞り込み + PairwiseAligner で各クエリの最良ヒットを計算する。

        全組合せ (N×M) ではなく、k-mer Jaccard 類似度上位 top_n 候補のみ
        精密アラインメントを実施して処理量を削減する。
        """
        # subject の k-mer インデックスと k-mer 集合を構築
        subject_index = self._build_kmer_index(seqs_subject, k)
        subject_dict = {r.id: r for r in seqs_subject}
        subject_kmer_sets: dict[str, set[str]] = {
            r.id: set(str(r.seq)[i:i + k] for i in range(len(str(r.seq)) - k + 1))
            for r in seqs_subject
        }

        aligner = PairwiseAligner()
        aligner.substitution_matrix = substitution_matrices.load("BLOSUM62")
        aligner.open_gap_score = -11
        aligner.extend_gap_score = -1

        self_scores = {r.id: aligner.score(str(r.seq), str(r.seq)) for r in seqs_query}

        rows: list[dict[str, float | str]] = []
        total_aligned = 0

        for query_record in seqs_query:
            candidates = self._get_candidates(
                query_record, subject_index, subject_kmer_sets, top_n, k
            )

            # k-mer に共通部分がない場合は全 subject を対象にして精密アラインメント
            if not candidates:
                candidates = [(r.id, 0.0) for r in seqs_subject]

            best_score: float | None = None
            best_sid: str | None = None

            for sid, _ in candidates:
                s_record = subject_dict[sid]
                sc = aligner.score(str(query_record.seq), str(s_record.seq))
                total_aligned += 1
                if best_score is None or sc > best_score:
                    best_score = sc
                    best_sid = sid

            if best_sid is not None and best_score is not None:
                ss = self_scores[query_record.id]
                identity = min(best_score / ss * 100, 100.0) if ss > 0 else 0.0
                rows.append({
                    "query": query_record.id,
                    "subject": best_sid,
                    "identity": identity,
                    "bitscore": float(best_score),
                })

        total_pairs = len(seqs_query) * len(seqs_subject)
        self.last_warnings.append(
            f"k-mer候補絞り込み完了: {total_aligned:,}ペアのみ精密アラインメントを実施"
            f"（全組合せ {total_pairs:,}ペアから削減、k={k}、top_n={top_n}）"
        )

        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["query", "subject", "identity", "bitscore"])

    async def run(
        self,
        sample_a: str,
        sample_b: str,
        keywords_a: list[str] | None = None,
        keywords_b: list[str] | None = None,
        k: int = 4,
        top_n: int = 20,
    ) -> pd.DataFrame:
        """k-mer 候補絞り込み + PairwiseAligner で 2 種間の RBH（相互最良ヒット）解析を行う。"""
        self.last_warnings = []
        self.last_excluded_records = []
        empty = pd.DataFrame(columns=["query_a", "query_b", "identity_a_to_b", "identity_b_to_a", "bitscore_a_to_b", "bitscore_b_to_a"])

        # FASTA パース
        normalized_a = self._normalize_fasta_content(sample_a)
        normalized_b = self._normalize_fasta_content(sample_b)
        seqs_a = list(SeqIO.parse(StringIO(normalized_a), "fasta"))
        seqs_b = list(SeqIO.parse(StringIO(normalized_b), "fasta"))

        if not seqs_a or not seqs_b:
            return empty

        # キーワード抽出
        if keywords_a:
            seqs_a = self._filter_records_by_keywords(seqs_a, "Species A", keywords_a)
        if keywords_b:
            seqs_b = self._filter_records_by_keywords(seqs_b, "Species B", keywords_b)

        if not seqs_a or not seqs_b:
            return empty

        # 配列正規化
        seqs_a = self._sanitize_sequences(seqs_a, "Species A")
        seqs_b = self._sanitize_sequences(seqs_b, "Species B")

        if not seqs_a or not seqs_b:
            return empty

        self._update_validation_summary()

        # A→B および B→A の最良ヒットを k-mer + PairwiseAligner で計算
        df_ab = self._compute_best_hits_fast(seqs_a, seqs_b, k=k, top_n=top_n)
        df_ba = self._compute_best_hits_fast(seqs_b, seqs_a, k=k, top_n=top_n)

        if df_ab.empty or df_ba.empty:
            self.last_warnings.append("配列検索でヒットが見つかりませんでした。")
            return empty

        # RBH（相互最良ヒット）検出
        rbh = pd.merge(
            df_ab, df_ba,
            left_on=["query", "subject"],
            right_on=["subject", "query"],
            suffixes=("_fwd", "_rev")
        )

        if rbh.empty:
            self.last_warnings.append("相互最良ヒット（RBH）が見つかりませんでした。")
            return empty

        self.last_warnings.append(
            f"✅ RBH解析完了: {len(rbh)}件のオーソログを検出しました（k-mer k={k}、top_n={top_n}）"
        )

        return rbh[["query_fwd", "subject_fwd", "identity_fwd", "identity_rev", "bitscore_fwd", "bitscore_rev"]].rename(columns={
            "query_fwd": "query_a",
            "subject_fwd": "query_b",
            "identity_fwd": "identity_a_to_b",
            "identity_rev": "identity_b_to_a",
            "bitscore_fwd": "bitscore_a_to_b",
            "bitscore_rev": "bitscore_b_to_a",
        })

