import pytest
from pyowasm.tasks.local.fasta_parser import FastaParserTask

def test_fasta_parser_execute():
    """
    FastaParserTaskが正しいFASTAデータをパースできるかテストする。
    """
    fasta_data = ">seq1 description\nATGC\n>seq2\nGCTA"
    parser = FastaParserTask()
    result = parser.execute(fasta_data)
    
    assert len(result.records) == 2
    assert result.records[0].id == "seq1"
    assert result.records[0].sequence == "ATGC"
    assert result.records[0].length == 4
    assert result.records[1].id == "seq2"
    assert result.records[1].sequence == "GCTA"
