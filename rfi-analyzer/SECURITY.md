# Security

## Reporting a vulnerability

Please report security issues privately through GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)
rather than opening a public issue. We'll acknowledge within a few days.

## Things to know before you point this at a document

**`--llm` sends document text to a third party.** The `--llm` flag and the
`/analyze?llm=1` route transmit the extracted text to the Anthropic API. Do not
use them on classified, export-controlled, or otherwise restricted material, or
on anything you are not cleared to send outside your organization. The default
path — heuristics only — is fully offline and makes no network calls.

**The HTTP server has no authentication.** `ocr_server.py` implements no
authentication, authorization, or rate limiting whatsoever. It binds to
`127.0.0.1` by default for that reason. If you run it with `--host 0.0.0.0` or
in the bundled container, put it behind something that does authenticate, on a
network you control. Do not expose it to the internet.

**Uploaded documents are processed on disk.** OCR rasterizes pages to temporary
files. On a shared host, other local users may be able to read them while
processing is in flight.

**Don't commit real solicitations.** See CONTRIBUTING.md — test fixtures should
be short inline strings, not real documents.
