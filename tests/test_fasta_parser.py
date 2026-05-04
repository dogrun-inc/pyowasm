from pyowasm.tasks.local.fasta_parser import FastaParserTask

def test_fasta_parser_run():
    """
    FastaParserTaskが正しいFASTAデータをパースできるかテストする。
    """
    fasta_data = ">seq1 description\nATGC\n>seq2\nGCTA"
    parser = FastaParserTask()
    result = parser.run(fasta_data)
    
    assert len(result.records) == 2
    assert result.records[0].id == "seq1"
    assert result.records[0].sequence == "ATGC"
    assert result.records[0].length == 4
    assert result.records[1].id == "seq2"
    assert result.records[1].sequence == "GCTA"


def test_fasta_parser_run_empty_input_returns_zero_records():
    """
    空入力時は成功扱いで0件を返すことを確認する。
    """
    parser = FastaParserTask()
    result = parser.run("")

    assert result.records == []
    assert result.metadata is not None
    assert result.metadata["warnings"] == []


def test_fasta_parser_run_invalid_input_returns_warning_without_raising():
    """
    不正FASTA入力時に例外を外へ投げず、警告を返すことを確認する。
    """
    parser = FastaParserTask()
    result = parser.run("ATGC\nATGC")

    assert result.records == []
    assert result.metadata is not None
    assert len(result.metadata["warnings"]) == 1
    assert "不正" in result.metadata["warnings"][0]
