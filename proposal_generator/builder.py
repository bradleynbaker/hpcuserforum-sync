"""
Assemble the proposal PDF.

  Page 1  Cover
  Page 2  Quote   (priced bill of materials + totals)
  Page 3  Architecture diagram
  Page 4  Engineer bio + government contract vehicle

Built directly on a ReportLab canvas for precise, 4-page layout control;
Platypus Paragraph/Table flowables are positioned by hand.
"""

from __future__ import annotations

import datetime
from typing import List, Tuple

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

from . import ai, diagram
from .models import ProposalConfig
from .pricelist import PricedLineItem, QuoteTotals

PAGE_W, PAGE_H = letter
MARGIN = 0.75 * inch
CONTENT_W = PAGE_W - 2 * MARGIN

NAVY = HexColor("#1F4E79")
BLUE = HexColor("#2E75B6")
GREY = HexColor("#525252")
LIGHT = HexColor("#EDF2F8")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _money(v: float) -> str:
    return f"${v:,.2f}"


def _style(name: str, **kw) -> ParagraphStyle:
    base = dict(fontName="Helvetica", fontSize=10, leading=14, textColor=colors.black)
    base.update(kw)
    return ParagraphStyle(name, **base)


def _draw_para(c: canvas.Canvas, text: str, style: ParagraphStyle,
               x: float, y_top: float, width: float) -> float:
    """Draw a Paragraph with its top edge at y_top. Returns height consumed."""
    p = Paragraph(text.replace("\n", "<br/>"), style)
    w, h = p.wrap(width, PAGE_H)
    p.drawOn(c, x, y_top - h)
    return h


def _fit(c: canvas.Canvas, text: str, font: str, size: float, max_w: float) -> str:
    """Truncate text with an ellipsis so it fits within max_w at the given font."""
    if not text or c.stringWidth(text, font, size) <= max_w:
        return text
    ell = "…"
    while text and c.stringWidth(text + ell, font, size) > max_w:
        text = text[:-1]
    return text.rstrip() + ell


def _kv_table(pairs, label_w: float, total_w: float, bg, label_color,
              border=None) -> Table:
    """Two-column label/value table with wrapping values and a fill color."""
    lbl = _style("kvl", fontSize=9, leading=11, fontName="Helvetica-Bold",
                 textColor=label_color)
    val = _style("kvv", fontSize=9, leading=11)
    data = [[Paragraph(f"{k}", lbl), Paragraph(v, val)] for k, v in pairs]
    t = Table(data, colWidths=[label_w, total_w - label_w])
    cmds = [
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]
    if border is not None:
        cmds.append(("BOX", (0, 0), (-1, -1), 1, border))
    t.setStyle(TableStyle(cmds))
    return t


def _header(c: canvas.Canvas, company_name: str, title: str) -> float:
    """Top band on content pages. Returns y of the first content line."""
    band_h = 0.55 * inch
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - band_h, PAGE_W, band_h, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(MARGIN, PAGE_H - band_h + 0.18 * inch, company_name)
    c.setFont("Helvetica", 10)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - band_h + 0.18 * inch, title)
    return PAGE_H - band_h - 0.4 * inch


def _footer(c: canvas.Canvas, cfg: ProposalConfig, page_no: int) -> None:
    c.setStrokeColor(HexColor("#CCCCCC"))
    c.setLineWidth(0.5)
    c.line(MARGIN, 0.6 * inch, PAGE_W - MARGIN, 0.6 * inch)
    c.setFillColor(GREY)
    c.setFont("Helvetica", 7.5)
    c.drawString(MARGIN, 0.42 * inch,
                 f"{cfg.company.name}  |  Proprietary & Confidential — Prepared for "
                 f"{cfg.customer.agency or cfg.customer.name}")
    c.drawRightString(PAGE_W - MARGIN, 0.42 * inch, f"Page {page_no} of 4")


# ---------------------------------------------------------------------------
# Page 1 — Cover
# ---------------------------------------------------------------------------

def _cover_page(c: canvas.Canvas, cfg: ProposalConfig) -> None:
    # top color band
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 2.6 * inch, PAGE_W, 2.6 * inch, stroke=0, fill=1)
    c.setFillColor(BLUE)
    c.rect(0, PAGE_H - 2.75 * inch, PAGE_W, 0.15 * inch, stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 26)
    c.drawString(MARGIN, PAGE_H - 1.5 * inch, cfg.company.name)
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(MARGIN, PAGE_H - 1.9 * inch, cfg.company.tagline)

    # title block
    y = PAGE_H - 4.0 * inch
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(MARGIN, y, "Information Technology")
    c.drawString(MARGIN, y - 0.4 * inch, "Solution Proposal")

    c.setFillColor(GREY)
    c.setFont("Helvetica", 15)
    c.drawString(MARGIN, y - 0.95 * inch, cfg.solution_name)

    # prepared-for / prepared-by boxes
    box_y = 2.7 * inch
    box_h = 1.7 * inch
    box_w = (CONTENT_W - 0.3 * inch) / 2.0

    def info_box(x, heading, lines):
        c.setFillColor(LIGHT)
        c.roundRect(x, box_y, box_w, box_h, 6, stroke=0, fill=1)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x + 0.2 * inch, box_y + box_h - 0.35 * inch, heading)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 10)
        ty = box_y + box_h - 0.65 * inch
        avail = box_w - 0.4 * inch
        for ln in lines:
            if ln:
                c.drawString(x + 0.2 * inch, ty, _fit(c, ln, "Helvetica", 10, avail))
                ty -= 0.22 * inch

    cust = cfg.customer
    info_box(MARGIN, "PREPARED FOR", [
        cust.name,
        cust.title,
        cust.agency,
        cust.org_unit,
        cust.email,
    ])
    comp = cfg.company
    info_box(MARGIN + box_w + 0.3 * inch, "PREPARED BY", [
        comp.rep_name or comp.name,
        comp.rep_title,
        comp.name,
        comp.rep_email or comp.website,
        comp.rep_phone,
    ])

    # meta strip
    today = datetime.date.today()
    valid_until = today + datetime.timedelta(days=cfg.valid_days)
    c.setFillColor(GREY)
    c.setFont("Helvetica", 9.5)
    meta = []
    if cfg.proposal_number:
        meta.append(f"Proposal No. {cfg.proposal_number}")
    meta.append(f"Date: {today:%B %d, %Y}")
    meta.append(f"Valid through: {valid_until:%B %d, %Y}")
    c.drawString(MARGIN, 1.9 * inch, "     |     ".join(meta))

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(MARGIN, 1.0 * inch,
                 "This document contains proprietary and confidential information and "
                 "is intended solely for the named recipient.")


# ---------------------------------------------------------------------------
# Page 2 — Quote
# ---------------------------------------------------------------------------

def _quote_page(c: canvas.Canvas, cfg: ProposalConfig,
                priced: List[PricedLineItem], totals: QuoteTotals,
                services_total: float, pricelist_src: str) -> None:
    y = _header(c, cfg.company.name, "Quote & Bill of Materials")

    # executive summary
    summary = ai.executive_summary(cfg.customer, cfg.solution_name, priced, cfg.meeting_notes)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN, y, "Executive Summary")
    y -= 0.22 * inch
    y -= _draw_para(c, summary, _style("sum", fontSize=9, leading=12.5), MARGIN, y, CONTENT_W)
    y -= 0.25 * inch

    # quote table
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN, y, "Bill of Materials")
    y -= 0.2 * inch

    cell = _style("cell", fontSize=7.5, leading=9)
    cell_r = _style("cellr", fontSize=7.5, leading=9, alignment=2)
    head = _style("head", fontSize=7.5, leading=9, textColor=colors.white,
                  fontName="Helvetica-Bold")

    data = [[
        Paragraph("SKU", head), Paragraph("Description", head),
        Paragraph("Mfr", head), Paragraph("Qty", head),
        Paragraph("Unit List", head), Paragraph("Disc %", head),
        Paragraph("Unit Net", head), Paragraph("Extended", head),
    ]]
    for p in priced:
        data.append([
            Paragraph(p.sku, cell),
            Paragraph(p.description, cell),
            Paragraph(p.manufacturer, cell),
            Paragraph(str(p.qty), cell_r),
            Paragraph(_money(p.unit_list), cell_r),
            Paragraph(f"{p.discount_pct:g}", cell_r),
            Paragraph(_money(p.unit_net), cell_r),
            Paragraph(_money(p.extended), cell_r),
        ])

    col_w = [0.95, 2.25, 0.7, 0.4, 0.85, 0.5, 0.85, 0.95]
    col_w = [w * inch for w in col_w]
    scale = CONTENT_W / sum(col_w)
    col_w = [w * scale for w in col_w]

    tbl = Table(data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#CCCCCC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    w, h = tbl.wrap(CONTENT_W, PAGE_H)
    tbl.drawOn(c, MARGIN, y - h)
    y = y - h - 0.25 * inch

    # totals
    rows: List[Tuple[str, str]] = [
        ("Hardware/Software List Price", _money(totals.subtotal_list)),
    ]
    if totals.total_savings > 0:
        rows.append((f"Discount ({totals.discount_avg_pct:g}% avg)",
                     f"-{_money(totals.total_savings)}"))
    rows.append(("Hardware/Software Subtotal", _money(totals.subtotal_net)))
    if services_total > 0:
        rows.append(("Engineering & Installation Services", _money(services_total)))
    grand = round(totals.subtotal_net + services_total, 2)
    rows.append(("Total Proposed Price (USD)", _money(grand)))

    tot_w = 3.2 * inch
    tot_x = PAGE_W - MARGIN - tot_w
    ty = y
    for i, (label, val) in enumerate(rows):
        is_total = (i == len(rows) - 1)
        rh = 0.26 * inch if is_total else 0.22 * inch
        if is_total:
            c.setFillColor(NAVY)
            c.rect(tot_x, ty - rh, tot_w, rh, stroke=0, fill=1)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 10)
        else:
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 9)
        c.drawString(tot_x + 0.1 * inch, ty - rh + 0.06 * inch, label)
        c.drawRightString(tot_x + tot_w - 0.1 * inch, ty - rh + 0.06 * inch, val)
        ty -= rh

    # source note
    c.setFillColor(GREY)
    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(MARGIN, ty - 0.05 * inch,
                 f"Pricing applied from manufacturer price list: {pricelist_src}. "
                 f"Prices in USD; valid {cfg.valid_days} days. Taxes not included "
                 f"(government purchases typically tax-exempt).")


# ---------------------------------------------------------------------------
# Page 3 — Architecture diagram
# ---------------------------------------------------------------------------

def _diagram_page(c: canvas.Canvas, cfg: ProposalConfig,
                  priced: List[PricedLineItem]) -> None:
    y = _header(c, cfg.company.name, "Solution Architecture")
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARGIN, y, "Reference Architecture")
    y -= 0.25 * inch
    c.setFillColor(colors.black)
    y -= _draw_para(
        c,
        "The diagram below illustrates the logical architecture of the proposed "
        "solution, from authenticated agency users through the security boundary, "
        "high-speed interconnect, compute and accelerator tier, parallel storage, "
        "and cluster management. An editable Microsoft Visio (.vsdx) version is "
        "delivered alongside this proposal.",
        _style("d", fontSize=9.5, leading=13), MARGIN, y, CONTENT_W,
    )
    y -= 0.15 * inch

    diagram.draw_architecture(
        c, priced,
        x=MARGIN, y_top=y, width=CONTENT_W, height=y - 1.0 * inch,
        title="Logical architecture — generated from the quoted configuration",
    )


# ---------------------------------------------------------------------------
# Page 4 — Engineer bio + contract vehicle
# ---------------------------------------------------------------------------

def _team_page(c: canvas.Canvas, cfg: ProposalConfig) -> None:
    y = _header(c, cfg.company.name, "Delivery Team & Procurement")
    eng = cfg.engineer

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARGIN, y, "Installation Engineer")
    y -= 0.28 * inch

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN, y, eng.name)
    c.setFillColor(GREY)
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(MARGIN, y - 0.18 * inch, eng.title)
    y -= 0.42 * inch

    bio = ai.engineer_bio(eng, cfg.solution_name)
    y -= _draw_para(c, bio, _style("bio", fontSize=10, leading=14), MARGIN, y, CONTENT_W)
    y -= 0.2 * inch

    # credentials box
    creds = [
        ("Experience", f"{eng.years_experience} years"),
        ("Clearance", eng.clearance or "Available upon request"),
        ("Certifications", ", ".join(eng.certifications) or "Available upon request"),
        ("Specialties", ", ".join(eng.specialties) or "HPC systems integration"),
    ]
    cred_tbl = _kv_table(creds, 1.5 * inch, CONTENT_W, LIGHT, NAVY)
    w, box_h = cred_tbl.wrap(CONTENT_W, PAGE_H)
    cred_tbl.drawOn(c, MARGIN, y - box_h)
    y = y - box_h - 0.4 * inch

    # contract vehicle
    cv = cfg.contract
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARGIN, y, "Procurement — Government Contract Vehicle")
    y -= 0.28 * inch
    c.setFillColor(colors.black)
    y -= _draw_para(
        c,
        f"All hardware, software, and services in this proposal are available "
        f"for immediate procurement through the contract vehicle below, "
        f"streamlining acquisition and ensuring compliant, competitively-priced "
        f"ordering for {cfg.customer.agency or cfg.customer.name}.",
        _style("cv", fontSize=10, leading=14), MARGIN, y, CONTENT_W,
    )
    y -= 0.15 * inch

    cv_rows = [
        ("Contract Vehicle", cv.name),
        ("Contract Number", cv.number or "Available upon request"),
        ("Contract Holder", cv.holder),
        ("Contract Ceiling", cv.ceiling),
        ("Period of Performance", cv.period_of_performance),
        ("NAICS", cv.naics),
        ("Ordering / Info", cv.url),
    ]
    cv_rows = [(k, v) for k, v in cv_rows if v]

    green = HexColor("#548235")
    cv_tbl = _kv_table(cv_rows, 1.9 * inch, CONTENT_W,
                       HexColor("#F2F7E9"), green, border=green)
    w, box_h = cv_tbl.wrap(CONTENT_W, PAGE_H)
    cv_tbl.drawOn(c, MARGIN, y - box_h)

    if cv.notes:
        y = y - box_h - 0.25 * inch
        c.setFillColor(GREY)
        _draw_para(c, cv.notes, _style("note", fontSize=8.5, leading=11,
                                       textColor=GREY), MARGIN, y, CONTENT_W)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def build_proposal(cfg: ProposalConfig, priced: List[PricedLineItem],
                   totals: QuoteTotals, out_path: str, pricelist_src: str) -> str:
    """Render the 4-page proposal PDF. Returns the output path."""
    services_total = 0.0
    if cfg.include_services_line and cfg.engineer.day_rate and cfg.engineer.estimated_days:
        services_total = round(cfg.engineer.day_rate * cfg.engineer.estimated_days, 2)

    c = canvas.Canvas(out_path, pagesize=letter)
    c.setTitle(f"{cfg.solution_name} — IT Proposal")
    c.setAuthor(cfg.company.name)

    _cover_page(c, cfg)
    _footer(c, cfg, 1)
    c.showPage()

    _quote_page(c, cfg, priced, totals, services_total, pricelist_src)
    _footer(c, cfg, 2)
    c.showPage()

    _diagram_page(c, cfg, priced)
    _footer(c, cfg, 3)
    c.showPage()

    _team_page(c, cfg)
    _footer(c, cfg, 4)
    c.showPage()

    c.save()
    return out_path
