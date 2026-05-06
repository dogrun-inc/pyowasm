import pandas as pd
from io import StringIO
from typing import Optional

def calculate_rbh(forward_tsv: str, reverse_tsv: str) -> pd.DataFrame:
    """
    2つのBLAST結果（TSV形式）から、レシプロカルベストヒット（RBH）を計算します。

    Args:
        forward_tsv (str): クエリAからデータベースBへのBLAST結果。
        reverse_tsv (str): クエリBからデータベースAへのBLAST結果。

    Returns:
        pd.DataFrame: RBHペアのデータフレーム。
    """
    # BLAST outfmt 6 のカラム名
    columns = [
        "query", "subject", "identity", "alignment_length", "mismatches", 
        "gap_opens", "q_start", "q_end", "s_start", "s_end", "evalue", "bitscore"
    ]

    def get_best_hits(tsv_content: str) -> pd.DataFrame:
        if not tsv_content.strip():
            return pd.DataFrame(columns=columns)
        
        df = pd.read_csv(StringIO(tsv_content), sep="\t", names=columns)
        # 各クエリに対して最大の bitscore を持つヒットを抽出
        # 同じスコアがある場合は最初のものを採用
        best_hits = df.sort_values("bitscore", ascending=False).drop_duplicates("query")
        return best_hits

    df_ab = get_best_hits(forward_tsv)
    df_ba = get_best_hits(reverse_tsv)

    if df_ab.empty or df_ba.empty:
        return pd.DataFrame()

    # RBHの条件: AのベストヒットがBであり、かつBのベストヒットがAであること
    # df_ab: query=A_id, subject=B_id
    # df_ba: query=B_id, subject=A_id
    
    # 内部結合で一致するペアを探す
    rbh = pd.merge(
        df_ab, 
        df_ba, 
        left_on=["query", "subject"], 
        right_on=["subject", "query"],
        suffixes=("_fwd", "_rev")
    )

    # 必要なカラムのみ抽出して整理
    result = rbh[[
        "query_fwd", "subject_fwd", "identity_fwd", "identity_rev", "bitscore_fwd", "bitscore_rev"
    ]].rename(columns={
        "query_fwd": "query_a",
        "subject_fwd": "query_b",
        "identity_fwd": "identity_a_to_b",
        "identity_rev": "identity_b_to_a",
        "bitscore_fwd": "bitscore_a_to_b",
        "bitscore_rev": "bitscore_b_to_a"
    })

    return result

def get_identity_stats(rbh_df: pd.DataFrame) -> dict:
    """
    RBHの結果からIdentityの統計情報を取得します。
    
    Args:
        rbh_df (pd.DataFrame): calculate_rbh で取得したデータフレーム。
        
    Returns:
        dict: 平均、中央値、カウントなどの統計。
    """
    if rbh_df.empty:
        return {"count": 0, "mean": 0.0, "median": 0.0}
    
    # identity_a_to_b を統計の対象とする
    stats = {
        "count": len(rbh_df),
        "mean": float(rbh_df["identity_a_to_b"].mean()),
        "median": float(rbh_df["identity_a_to_b"].median()),
        "min": float(rbh_df["identity_a_to_b"].min()),
        "max": float(rbh_df["identity_a_to_b"].max()),
    }
    return stats
