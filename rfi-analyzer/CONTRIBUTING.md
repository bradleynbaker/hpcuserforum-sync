# Contributing

Thanks for helping. This tool gets better mostly by seeing more real
solicitations, so extraction fixes and test cases are the highest-value
contributions.

## Getting set up

```bash
git clone https://github.com/<owner>/rfi-analyzer.git
cd rfi-analyzer
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# System tools, only needed to exercise the OCR path:
apt-get install poppler-utils tesseract-ocr   # or: brew install poppler tesseract
```

Run the checks:

```bash
pytest -q          # tests
ruff check .       # lint
```

Both run in CI on every pull request. The test suite deliberately avoids
requiring poppler or tesseract — tests that need them skip cleanly when the
binaries are absent, so `pytest` passes on a bare checkout.

## Never commit a real solicitation

**Do not add real government solicitations, client documents, or anything
competition-sensitive to this repository**, including as test fixtures. Write
tests against short inline strings that reproduce the *pattern* you're fixing:

```python
def test_deadline_with_cob_phrasing():
    text = "Responses are due no later than COB 14 March 2027."
    assert find_deadline(text) == "14 March 2027"
```

That is easier to read, runs faster, and keeps the repository free of material
nobody vetted for release.

## Making a change

1. Open an issue first for anything larger than a bug fix, so we can agree on
   the approach before you spend time on it.
2. Branch off `main`.
3. Add a test that fails without your change.
4. Keep the style of the surrounding code — match its naming, comment density,
   and idiom rather than introducing a new one.
5. Open a pull request and fill in the template.

## Good first issues

Two known extraction bugs already have failing tests written for them, marked
`xfail` so CI stays green. Pick either one, make the test pass, and remove the
`@pytest.mark.xfail` decorator:

- `test_document_type_is_case_insensitive` — document-type phrases are matched
  case-sensitively, so only all-lowercase prose registers.
- `test_does_not_swallow_preceding_capitalised_words` — the acronym regex is
  greedy across spaces and captures more than the definition.

These markers are `strict=True`, so a fix turns the run red until the decorator
comes off — that's deliberate, it stops a fix landing without the marker being
cleaned up.

## What makes a good extraction fix

The heuristics in `rfi_analyzer.py` are regex over OCR text, so they fail in
specific, reproducible ways. When you hit one:

- **Narrow the pattern, don't broaden it.** A regex that matches more deadlines
  but also matches the contract award date is a net loss.
- **Add the failing phrasing as a test case.** That's the part that stops it
  regressing.
- **Remember OCR noise.** Real input contains `l` for `1`, `O` for `0`, and
  words split across line breaks. `heuristic_analysis()` runs contextual
  extractors against a whitespace-normalized copy for exactly this reason.

## Scope

In scope: extraction accuracy, new document formats, output formats, server
ergonomics, packaging, docs.

Out of scope: anything that submits a response, scrapes a procurement portal, or
automates interaction with a government system. This tool reads documents you
already have.

## Reporting bugs

Open an issue with the phrasing that failed and what you expected instead — a
one-line reproduction beats a description. **Redact anything sensitive first.**
