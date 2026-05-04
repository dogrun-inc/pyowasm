import pytest
from pyowasm.tasks.local.fasta_parser import FastaParserTask
from pyowasm.tasks.local.sequence_analyzer import SequenceAnalysisTask

def test_sequence_analysis_execute():
    """
    SequenceAnalysisTaskがGC含有量と塩基組成を正しく計算できるかテストする。
    """
    fasta_data = ">seq1\nATGC"
    parser = FastaParserTask()
    parse_result = parser.run(fasta_data)
    
    analyzer = SequenceAnalysisTask()
    analysis_result = analyzer.run(parse_result.records)
    
    record = analysis_result.records[0]
    assert record.gc_content == 50.0  # (G+C)/4 = 2/4 = 50%
    assert record.base_composition == {"A": 1, "T": 1, "G": 1, "C": 1}
