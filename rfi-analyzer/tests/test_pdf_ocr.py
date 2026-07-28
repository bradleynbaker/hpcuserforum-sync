'''Tests for pdf_ocr. Anything needing poppler/tesseract skips cleanly.'''
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pdf_ocr  # noqa: E402


def test_ocr_result_round_trips_to_dict():
    r = pdf_ocr.OcrResult(text="hello", method="text-layer", pages=["hello"],
                          page_count=1, char_count=5, source="x.pdf")
    d = r.to_dict()
    assert d["method"] == "text-layer"
    assert d["page_count"] == 1


def test_check_dependencies_lists_missing_binaries():
    # Returns a list of missing binaries — empty when everything is installed.
    missing = pdf_ocr.check_dependencies()
    assert isinstance(missing, list)
    assert all(isinstance(m, str) for m in missing)


def test_check_dependencies_skips_ocr_binaries_when_not_needed():
    assert len(pdf_ocr.check_dependencies(need_ocr=False)) <= len(
        pdf_ocr.check_dependencies(need_ocr=True)
    )


def test_defaults_are_sane():
    assert pdf_ocr.DEFAULT_DPI >= 150
    assert pdf_ocr.DEFAULT_LANG
    assert pdf_ocr.DEFAULT_TEXT_LAYER_MIN_CHARS > 0


def test_missing_file_raises_filenotfound(tmp_path):
    # Raised before any external binary is invoked, so this needs no poppler.
    with pytest.raises(FileNotFoundError):
        pdf_ocr.extract_text(tmp_path / "does-not-exist.pdf")
