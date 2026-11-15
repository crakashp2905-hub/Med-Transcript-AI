from io import BytesIO
import zipfile

import pytest

from services.review.document_exports import render_document_export


@pytest.mark.parametrize("format", ["pdf", "docx"])
def test_approved_document_export_preserves_note_text(format):
    text = (
        "APPROVED CLINICAL NOTE\n"
        "Encounter: synthetic-encounter\n"
        "Subjective\n"
        "The patient reports a mild cough.\n"
        "Independent clinical gold: false; recipient EHR conformance: untested.\n"
    )
    rendered = render_document_export(format, text)
    assert rendered
    if format == "pdf":
        assert rendered.startswith(b"%PDF-1.4")
        assert b"The patient reports a mild cough." in rendered
        assert rendered.endswith(b"%%EOF\n")
    else:
        with zipfile.ZipFile(BytesIO(rendered)) as archive:
            assert archive.testzip() is None
            document = archive.read("word/document.xml").decode("utf-8")
            assert "The patient reports a mild cough." in document
            assert "recipient EHR conformance: untested." in document


def test_pdf_export_fails_closed_for_glyphs_outside_win_ansi():
    with pytest.raises(UnicodeEncodeError):
        render_document_export("pdf", "Unsupported glyph: \u03b2")
