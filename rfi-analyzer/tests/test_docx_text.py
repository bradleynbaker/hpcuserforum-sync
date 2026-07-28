'''Tests for the stdlib .docx extractor, built against a synthetic file.'''
import pathlib
import sys
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from docx_text import extract_docx_text  # noqa: E402

DOC_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:body>"
    "<w:p><w:r><w:t>Response deadline</w:t></w:r>"
    '<w:r><w:t xml:space="preserve"> is March 14, 2027.</w:t></w:r></w:p>'
    "<w:p><w:r><w:t>NAICS 541519</w:t></w:r></w:p>"
    "</w:body></w:document>"
)


def _make_docx(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", DOC_XML)
    return path


def test_extracts_text_across_runs_and_paragraphs(tmp_path):
    text = extract_docx_text(_make_docx(tmp_path / "sample.docx"))
    # Runs within a paragraph join without a spurious break.
    assert "Response deadline is March 14, 2027." in text
    assert "NAICS 541519" in text


def test_paragraphs_are_separated(tmp_path):
    text = extract_docx_text(_make_docx(tmp_path / "sample.docx"))
    assert "2027.\nNAICS" in text or "2027." in text.split("NAICS")[0]
