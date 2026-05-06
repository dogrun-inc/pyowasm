import pytest
import pandas as pd
from pyowasm.core.stats import calculate_rbh

def test_calculate_rbh_basic():
    # A->B
    # seq1 -> seqA (bitscore 100)
    # seq2 -> seqB (bitscore 50)
    forward = "seq1\tseqA\t100.0\t100\t0\t0\t1\t100\t1\t100\t0.0\t100.0\n" \
              "seq2\tseqB\t90.0\t100\t0\t0\t1\t100\t1\t100\t0.0\t50.0"
    
    # B->A
    # seqA -> seq1 (bitscore 100)
    # seqB -> seqX (bitscore 80) - seq2 is not the best hit for seqB
    reverse = "seqA\tseq1\t100.0\t100\t0\t0\t1\t100\t1\t100\t0.0\t100.0\n" \
              "seqB\tseqX\t100.0\t100\t0\t0\t1\t100\t1\t100\t0.0\t80.0"

    df = calculate_rbh(forward, reverse)
    
    assert len(df) == 1
    assert df.iloc[0]["query_a"] == "seq1"
    assert df.iloc[0]["query_b"] == "seqA"
    assert df.iloc[0]["bitscore_a_to_b"] == 100.0

def test_calculate_rbh_multiple_hits():
    # seq1 has two hits, seqA (100) is better than seqB (90)
    forward = "seq1\tseqA\t100.0\t100\t0\t0\t1\t100\t1\t100\t0.0\t100.0\n" \
              "seq1\tseqB\t90.0\t100\t0\t0\t1\t100\t1\t100\t0.0\t90.0"
    
    # seqA's best hit is seq1
    reverse = "seqA\tseq1\t100.0\t100\t0\t0\t1\t100\t1\t100\t0.0\t100.0"

    df = calculate_rbh(forward, reverse)
    
    assert len(df) == 1
    assert df.iloc[0]["query_a"] == "seq1"
    assert df.iloc[0]["query_b"] == "seqA"

def test_calculate_rbh_non_reciprocal():
    # seq1 -> seqA (100)
    forward = "seq1\tseqA\t100.0\t100\t0\t0\t1\t100\t1\t100\t0.0\t100.0"
    # seqA -> seq2 (100) -- seq1 is NOT the best hit for seqA
    reverse = "seqA\tseq2\t100.0\t100\t0\t0\t1\t100\t1\t100\t0.0\t100.0"

    df = calculate_rbh(forward, reverse)
    
    assert len(df) == 0

def test_calculate_rbh_empty():
    df = calculate_rbh("", "")
    assert len(df) == 0
    assert isinstance(df, pd.DataFrame)
