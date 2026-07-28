'''Tests for the offline heuristic extractors.

Deliberately uses short inline strings rather than real solicitations — see
CONTRIBUTING.md. Nothing here needs poppler, tesseract, or an API key.
'''
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rfi_analyzer import (  # noqa: E402
    build_markdown,
    find_acronyms,
    find_deadline,
    find_points_of_contact,
    heuristic_analysis,
)


class TestFindDeadline:
    def test_prefers_date_near_a_deadline_cue(self):
        text = ("The contract was awarded on January 2, 2026. "
                "Responses are due no later than March 14, 2027.")
        assert find_deadline(text) == "March 14, 2027"

    def test_falls_back_to_first_date_when_no_cue(self):
        assert find_deadline("Issued March 14, 2027 by the agency.")

    def test_returns_none_when_no_date_present(self):
        assert find_deadline("There is no date anywhere in this sentence.") is None


class TestFindPointsOfContact:
    def test_extracts_role_and_name(self):
        pocs = find_points_of_contact("The Contracting Officer is Jane Doe.")
        assert {"role": "Contracting Officer", "name": "Jane Doe"} in pocs

    def test_dedupes_repeated_contacts(self):
        text = "Contracting Officer Jane Doe ... Contracting Officer Jane Doe"
        assert len(find_points_of_contact(text)) == 1

    def test_no_contacts_returns_empty_list(self):
        assert find_points_of_contact("Nothing to see here.") == []


class TestFindAcronyms:
    def test_captures_inline_definitions(self):
        found = find_acronyms("the Defense Intelligence Agency (DIA) requires")
        assert found["DIA"] == "Defense Intelligence Agency"

    @pytest.mark.xfail(
        reason="Known bug: the acronym pattern's character class includes spaces, "
               "so it swallows preceding capitalised words — 'REQUEST FOR "
               "INFORMATION Defense Intelligence Agency (DIA)' yields the whole "
               "run rather than just the agency name.",
        strict=True,
    )
    def test_does_not_swallow_preceding_capitalised_words(self):
        found = find_acronyms("REQUEST FOR INFORMATION Defense Intelligence Agency (DIA)")
        assert found["DIA"] == "Defense Intelligence Agency"

    def test_respects_the_limit(self):
        text = " ".join(f"Some Long Name{i} (AB{i})" for i in range(60))
        assert len(find_acronyms(text, limit=5)) <= 5


class TestHeuristicAnalysis:
    SAMPLE = (
        "REQUEST FOR INFORMATION\n"
        "Defense Intelligence Agency (DIA)\n"
        "Subject: Enterprise IT Services\n"
        "Responses are due no later than March 14, 2027.\n"
        "Submit responses to contracts@example.gov or call (555) 123-4567.\n"
        "The Contracting Officer is Jane Doe.\n"
        "NAICS code 541519 applies.\n"
        "Responses shall be no more than 20 pages.\n"
    )

    def test_returns_all_expected_keys(self):
        result = heuristic_analysis(self.SAMPLE)
        for key in ("document_type", "issuing_agency", "subject",
                    "response_deadline", "submission_emails",
                    "points_of_contact", "phones", "naics_codes",
                    "page_limit", "technologies_mentioned", "acronyms"):
            assert key in result

    def test_extracts_the_obvious_fields(self):
        r = heuristic_analysis(self.SAMPLE)
        assert "contracts@example.gov" in r["submission_emails"]
        assert "541519" in r["naics_codes"]
        assert r["response_deadline"] == "March 14, 2027"
        assert r["page_limit"] == 20
        assert r["issuing_agency"] == "Defense Intelligence Agency"
        assert {"role": "Contracting Officer", "name": "Jane Doe"} in r["points_of_contact"]

    def test_document_type_matches_lowercase_prose(self):
        r = heuristic_analysis("this request for information seeks responses")
        assert r["document_type"] == "Request for Information"

    def test_document_type_matches_a_bare_acronym(self):
        # The acronym alternatives are literal uppercase, so these do match.
        assert heuristic_analysis("This RFI seeks responses")["document_type"] == (
            "Request for Information"
        )

    @pytest.mark.xfail(
        reason="Known bug: _DOC_TYPES phrase patterns are lowercase and matched "
               "without re.IGNORECASE, so anything other than all-lowercase prose "
               "fails. Title Case and the ALL-CAPS headings used by most real "
               "solicitations both miss. See 'Known limits' in the README.",
        strict=True,
    )
    @pytest.mark.parametrize("heading", [
        "This Request for Information seeks responses.",
        "REQUEST FOR INFORMATION",
        "Sources Sought Notice",
    ])
    def test_document_type_is_case_insensitive(self, heading):
        assert heuristic_analysis(heading)["document_type"] is not None

    def test_survives_ocr_style_line_wrapping(self):
        # OCR splits phrases across line breaks; contextual extractors run
        # against a whitespace-normalized copy so this must still work.
        wrapped = "Responses are due no later\nthan March 14,\n2027."
        assert heuristic_analysis(wrapped)["response_deadline"] is not None

    def test_empty_document_does_not_raise(self):
        result = heuristic_analysis("")
        assert result["submission_emails"] == []
        assert result["points_of_contact"] == []


class TestBuildMarkdown:
    def test_renders_a_brief_from_a_heuristic_record(self):
        sample = TestHeuristicAnalysis.SAMPLE
        record = {
            "source": "sample.pdf",
            "extraction": {"method": "text-layer", "page_count": 1,
                           "char_count": len(sample)},
            "heuristics": heuristic_analysis(sample),
            "text": sample,
        }
        md = build_markdown(record)
        assert isinstance(md, str) and md.strip()
        assert "541519" in md
        assert "sample.pdf" in md

    def test_renders_without_an_llm_section(self):
        record = {
            "source": "s.pdf",
            "extraction": {"method": "ocr", "page_count": 0, "char_count": 0},
            "heuristics": heuristic_analysis(""),
            "text": "",
        }
        assert build_markdown(record).strip()
