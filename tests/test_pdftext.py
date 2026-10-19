from renamer.pdftext import extract_text


def test_extracts_text_from_all_pages(fixtures_dir):
    text = extract_text(fixtures_dir / "power_2026_10.pdf")
    assert "Λογαριασμός Χαμηλής Τάσης-Ηλεκτρικής Ενέργειας" in text  # σελίδα 1
    assert "Χρέωση Ημερήσιας Ενέργειας: 52kWhX" in text  # σελίδα 2
