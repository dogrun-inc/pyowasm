import streamlit as st
from ..base import BaseTask
from ...bridge.biowasm import bridge
from ...core.stats import calculate_rbh
from ...ui.components import render_rbh_results

class OrthologAnalysisTask(BaseTask):
    """
    Wasm-BLAST を使用して 2 種間のオーソログ解析（RBH）を行うタスク。
    """

    async def run(self, sample_a: str, sample_b: str) -> any:
        """
        RBH パイプラインを実行します。
        """
        # 1. Species B の DB 作成
        await bridge.makeblastdb(sample_b, db_name="sp_b", db_type="prot")
        
        # 2. A -> B 検索
        fwd_tsv = await bridge.blastp(sample_a, db_name="sp_b", options="-outfmt 6")
        
        # 3. Species A の DB 作成
        await bridge.makeblastdb(sample_a, db_name="sp_a", db_type="prot")
        
        # 4. B -> A 検索
        rev_tsv = await bridge.blastp(sample_b, db_name="sp_a", options="-outfmt 6")
        
        # 5. RBH 計算
        rbh_df = calculate_rbh(fwd_tsv, rev_tsv)
        return rbh_df

    def render(self, result: any) -> None:
        """
        解析結果を表示します。
        """
        render_rbh_results(result)
