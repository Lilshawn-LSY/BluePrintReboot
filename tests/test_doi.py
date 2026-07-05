from ingest.doi import is_probable_doi, normalize_doi


def test_normalize_doi_common_formats() -> None:
    assert normalize_doi(" doi:10.1000/ABC.Def ") == "10.1000/abc.def"
    assert normalize_doi("DOI: 10.5555/Test-Case") == "10.5555/test-case"
    assert normalize_doi("DOI 10.1111/pce.13021") == "10.1111/pce.13021"
    assert normalize_doi("https://doi.org/10.1038/S41586-020-2649-2") == "10.1038/s41586-020-2649-2"
    assert normalize_doi("http://dx.doi.org/10.1145/3368089.3409742") == "10.1145/3368089.3409742"


def test_is_probable_doi() -> None:
    assert is_probable_doi("10.1000/example")
    assert is_probable_doi("https://doi.org/10.1038/s41586-020-2649-2")
    assert not is_probable_doi("")
    assert not is_probable_doi("not a doi")
    assert not is_probable_doi("11.1000/example")
