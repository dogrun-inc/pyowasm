import sys
import types

import pytest

# Mock external modules
streamlit_module = types.ModuleType("streamlit")
seaborn_module = types.ModuleType("seaborn")
matplotlib_module = types.ModuleType("matplotlib")
pyplot_module = types.ModuleType("matplotlib.pyplot")
matplotlib_module.pyplot = pyplot_module

sys.modules.setdefault("streamlit", streamlit_module)
sys.modules.setdefault("seaborn", seaborn_module)
sys.modules.setdefault("matplotlib", matplotlib_module)
sys.modules.setdefault("matplotlib.pyplot", pyplot_module)

from pyowasm.tasks.wasm.ortholog_analyzer import OrthologAnalysisTask
from Bio.SeqRecord import SeqRecord
from Bio.Seq import Seq


def test_normalize_sequence_uppercases_and_removes_bom() -> None:
    """Test that normalize_sequence uppercases and removes BOM characters."""
    task = OrthologAnalysisTask()
    normalized = task._normalize_sequence("  acd\ufeffE  ")
    assert normalized == "ACDE"


def test_normalize_fasta_content_removes_bom() -> None:
    """Test that normalize_fasta_content removes BOM from FASTA strings."""
    task = OrthologAnalysisTask()
    result = task._normalize_fasta_content("\ufeff>seq1\nACDE\n")
    assert ">seq1" in result
    assert "ACDE" in result
    assert "\ufeff" not in result


def test_filter_records_by_keywords() -> None:
    """Test keyword filtering with case-insensitive matching and separator normalization."""
    task = OrthologAnalysisTask()
    records = [
        SeqRecord(Seq("ACDE"), id="a1", description="caffeine_synthase"),
        SeqRecord(Seq("ACDE"), id="a2", description="caffeine-synthase"),
        SeqRecord(Seq("ACDE"), id="a3", description="unrelated_gene"),
    ]
    
    result = task._filter_records_by_keywords(records, "TestSpecies", ["caffeine synthase"])
    
    # Should match both a1 and a2 (underscore and hyphen treated as space)
    assert len(result) == 2
    assert result[0].id == "a1"
    assert result[1].id == "a2"
    assert any("キーワード抽出" in msg for msg in task.last_warnings)


def test_sanitize_sequences_excludes_invalid() -> None:
    """Test that sequences with non-BLOSUM62 characters are excluded."""
    task = OrthologAnalysisTask()
    records = [
        SeqRecord(Seq("ACDE"), id="valid1", description="good"),
        SeqRecord(Seq("ACDEU"), id="invalid1", description="has_U"),
        SeqRecord(Seq("MKVL"), id="valid2", description="also_good"),
    ]
    
    result = task._sanitize_sequences(records, "TestSpecies")
    
    assert len(result) == 2
    assert result[0].id == "valid1"
    assert result[1].id == "valid2"
    assert len(task.last_excluded_records) == 1
    assert task.last_excluded_records[0]["record_id"] == "invalid1"
    assert "U" in task.last_excluded_records[0]["invalid_chars"]


def test_normalize_text_for_keyword_match() -> None:
    """Test keyword matching normalization (underscores/hyphens -> space, lowercase)."""
    task = OrthologAnalysisTask()
    
    tests = [
        ("caffeine_synthase", "caffeine synthase"),
        ("caffeine-synthase", "caffeine synthase"),
        ("Caffeine-Synthase", "caffeine synthase"),
        ("caffeine  synthase", "caffeine synthase"),
    ]
    
    for input_text, expected in tests:
        result = task._normalize_text_for_keyword_match(input_text)
        assert result == expected, f"Failed for {input_text}: got {result}"