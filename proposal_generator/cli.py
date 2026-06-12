"""
Command-line entry point for the proposal generator.

  python -m proposal_generator --config sample_data/hpc_cluster.json
  python -m proposal_generator --config my.json --out proposal.pdf \
        --pricelist https://example.com/pricelist.xlsx --vsdx arch.vsdx
  python -m proposal_generator --config my.json --notes meeting.txt

With no --config, the bundled HPC cluster sample is used.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import builder, diagram
from .models import ProposalConfig
from .pricelist import apply_to_config, load_price_list


def _default_config_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "sample_data", "hpc_cluster.json")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="proposal_generator",
        description="Generate a 4-page federal IT proposal (cover, quote, "
                    "architecture diagram, engineer bio + contract vehicle).",
    )
    p.add_argument("--config", default="", metavar="FILE",
                   help="Proposal config JSON/YAML (default: bundled HPC sample)")
    p.add_argument("--out", default="proposal.pdf", metavar="FILE",
                   help="Output PDF path (default: proposal.pdf)")
    p.add_argument("--pricelist", default="", metavar="URL_OR_PATH",
                   help="Manufacturer price list URL/CSV/XLSX "
                        "(overrides config; default: bundled sample)")
    p.add_argument("--vsdx", nargs="?", const="auto", default=None, metavar="FILE",
                   help="Also export an editable Visio diagram. "
                        "Bare flag uses <out>.vsdx; or give a path.")
    p.add_argument("--notes", default="", metavar="FILE",
                   help="Text file of meeting notes to enrich the executive summary")
    args = p.parse_args(argv)

    config_path = args.config or _default_config_path()
    if not os.path.exists(config_path):
        print(f"ERROR: config not found: {config_path}", file=sys.stderr)
        return 1

    print(f"[CONFIG]    {config_path}")
    cfg = ProposalConfig.load(config_path)

    if args.notes:
        with open(args.notes, "r", encoding="utf-8") as f:
            cfg.meeting_notes = (cfg.meeting_notes + "\n" + f.read()).strip()
        print(f"[NOTES]     loaded {args.notes}")

    # price list: CLI flag > config field > bundled sample
    source = args.pricelist or cfg.pricelist_source
    price_list, src_desc = load_price_list(source)
    print(f"[PRICELIST] {len(price_list)} SKUs from {src_desc}")

    priced, totals, warnings = apply_to_config(
        price_list, cfg.line_items, cfg.default_discount_pct,
    )
    for w in warnings:
        print(f"[WARN]      {w}")
    print(f"[QUOTE]     {len(priced)} line items — "
          f"subtotal {totals.subtotal_net:,.2f} USD "
          f"({totals.discount_avg_pct:g}% avg discount)")

    out_path = builder.build_proposal(cfg, priced, totals, args.out, src_desc)
    print(f"[PDF]       {out_path}")

    if args.vsdx is not None:
        vsdx_path = args.vsdx
        if vsdx_path in ("auto", "", None):
            vsdx_path = os.path.splitext(args.out)[0] + ".vsdx"
        diagram.export_vsdx(vsdx_path, priced)
        print(f"[VSDX]      {vsdx_path}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
