# IT Proposal Generator

Come out of a customer meeting and generate a complete, client-ready IT
proposal PDF in seconds. Each proposal is exactly four pages:

| Page | Contents |
|------|----------|
| 1 | **Cover** — solution name, customer/agency, prepared-by, date, validity |
| 2 | **Quote** — manufacturer price list applied to your configuration, with per-line discounts and totals |
| 3 | **Architecture diagram** — a Visio-style block diagram generated from the quoted configuration (an editable `.vsdx` is exported too) |
| 4 | **Engineer bio + procurement** — the named installation engineer and the government contract vehicle to buy through |

The executive summary and engineer bio are written by the Claude API when
`ANTHROPIC_API_KEY` is set, and fall back to clean templates otherwise — so it
always runs, online or offline.

## Install

```bash
pip install -r requirements.txt
```

Core dependencies: `reportlab` (PDF) and `openpyxl` (XLSX price lists).
`anthropic` is optional (AI narrative).

## Quick start

```bash
# Uses the bundled federal HPC-cluster sample + sample price list
python -m proposal_generator --out proposal.pdf --vsdx
```

This produces `proposal.pdf` and `proposal.vsdx`.

## Usage

```bash
python -m proposal_generator \
    --config  sample_data/hpc_cluster.json \   # your proposal config (JSON or YAML)
    --pricelist  https://vendor.example/pricelist.xlsx \  # URL, .csv, or .xlsx
    --notes   meeting_notes.txt \               # pasted meeting notes (enriches the summary)
    --out     romero_doe_hpc.pdf \
    --vsdx    romero_doe_hpc.vsdx
```

| Flag | Meaning |
|------|---------|
| `--config FILE` | Proposal config (JSON, or YAML if PyYAML is installed). Defaults to the bundled HPC sample. |
| `--pricelist URL_OR_PATH` | Manufacturer price list. Accepts an http(s) URL, `.csv`, or `.xlsx`. Overrides the config's `pricelist_source`. Defaults to the bundled sample. |
| `--notes FILE` | Text file of meeting notes; folded into the executive summary. |
| `--out FILE` | Output PDF path (default `proposal.pdf`). |
| `--vsdx [FILE]` | Also export an editable Visio diagram. Bare flag → `<out>.vsdx`. |

`ANTHROPIC_API_KEY` enables AI-written narrative; `PROPOSAL_AI_MODEL` overrides
the model (default `claude-sonnet-4-6`).

## Configuration

A proposal is described by one JSON/YAML file — see
[`sample_data/hpc_cluster.json`](sample_data/hpc_cluster.json). Key sections:

- `customer`, `company` — who it's for and who's preparing it
- `solution_name`, `proposal_number`, `valid_days`, `default_discount_pct`
- `meeting_notes` — optional; enriches the executive summary
- `line_items` — `[{ "sku", "qty", "category" }]`. `category` is one of
  `compute | gpu | network | storage | management | rack | software | services`
  and drives the architecture diagram.
- `engineer` — name, title, certs, clearance, specialties, plus `day_rate` and
  `estimated_days` for the installation-services line
- `contract` — the government contract vehicle (name, number, ceiling, NAICS…)

### Price list format

A CSV or XLSX with a header row. Recognized columns (case-insensitive):

```
sku, description, manufacturer, unit_price, category
```

SKUs in `line_items` are matched against the price list; quantity and discount
are applied to compute extended pricing. Any SKU not found is flagged in the
console and listed at `$0` so nothing is silently dropped.

## Notes

- The bundled price list (`sample_data/pricelist_sample.csv`) is representative
  sample data. Real manufacturer price lists are partner-gated — point
  `--pricelist` at your authorized file or feed.
- The `.vsdx` export is a minimal, editable Visio drawing of the same
  architecture shown on page 3.
