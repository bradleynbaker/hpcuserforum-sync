"""
Solution architecture diagram.

Two outputs, both derived from the priced configuration:

  * draw_architecture(canvas, ...)  — renders a clean "Visio-style" block
                                       diagram directly onto a ReportLab page.
  * export_vsdx(path, ...)          — writes a minimal, editable Microsoft
                                       Visio (.vsdx) file of the same diagram.

The diagram is built from category counts (compute / gpu / storage / network /
management), so it reflects whatever configuration is quoted.
"""

from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass
from typing import Dict, List, Tuple
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch

from .models import PricedLineItem


# ---------------------------------------------------------------------------
# Build the logical tiers from the configuration
# ---------------------------------------------------------------------------

@dataclass
class Tier:
    label: str
    sublabel: str
    color: str


def _count(items: List[PricedLineItem], category: str) -> int:
    return sum(p.qty for p in items if p.category == category)


def tiers_from_items(items: List[PricedLineItem]) -> List[Tier]:
    """Map a configuration into an ordered top-to-bottom set of tiers."""
    n_compute = _count(items, "compute")
    n_gpu = _count(items, "gpu")
    n_net = _count(items, "network")
    n_storage = _count(items, "storage")
    n_mgmt = _count(items, "management")

    tiers: List[Tier] = []
    tiers.append(Tier("Agency Users / Enterprise Network",
                      "Authenticated researchers & workloads", "#1F4E79"))
    tiers.append(Tier("Boundary / Login & Security",
                      "Login nodes, firewall, CAC/PIV authentication", "#2E75B6"))

    net_sub = f"{n_net} network device(s)" if n_net else "High-speed fabric"
    tiers.append(Tier("High-Speed Interconnect Fabric",
                      f"{net_sub} — InfiniBand / 100GbE", "#548235"))

    compute_sub_parts = []
    if n_compute:
        compute_sub_parts.append(f"{n_compute} compute node(s)")
    if n_gpu:
        compute_sub_parts.append(f"{n_gpu} GPU accelerator(s)")
    compute_sub = " · ".join(compute_sub_parts) or "Compute nodes"
    tiers.append(Tier("Compute Cluster", compute_sub, "#C55A11"))

    storage_sub = f"{n_storage} storage unit(s) — parallel filesystem" if n_storage \
        else "Parallel / scratch storage"
    tiers.append(Tier("Storage Tier", storage_sub, "#7030A0"))

    mgmt_sub = f"{n_mgmt} management node(s) — provisioning & scheduler" if n_mgmt \
        else "Cluster management & job scheduler"
    tiers.append(Tier("Management & Orchestration", mgmt_sub, "#525252"))

    return tiers


# ---------------------------------------------------------------------------
# ReportLab rendering (page 3)
# ---------------------------------------------------------------------------

def draw_architecture(c, items: List[PricedLineItem], x: float, y_top: float,
                      width: float, height: float, title: str = "") -> None:
    """Draw the architecture diagram onto an existing ReportLab canvas `c`.

    (x, y_top) is the top-left corner of the drawing area.
    """
    tiers = tiers_from_items(items)
    n = len(tiers)

    gap = 0.22 * inch
    box_h = (height - gap * (n - 1)) / n
    box_w = width * 0.74
    box_x = x + (width - box_w) / 2.0

    centers: List[Tuple[float, float]] = []
    cur_top = y_top

    for tier in tiers:
        box_bottom = cur_top - box_h
        cx = box_x + box_w / 2.0
        cy = box_bottom + box_h / 2.0
        centers.append((cx, cy))

        # box
        c.setFillColor(HexColor(tier.color))
        c.setStrokeColor(HexColor("#FFFFFF"))
        c.setLineWidth(1)
        c.roundRect(box_x, box_bottom, box_w, box_h, 6, stroke=1, fill=1)

        # label
        c.setFillColor(HexColor("#FFFFFF"))
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(cx, cy + 3, tier.label)
        c.setFont("Helvetica", 8)
        c.drawCentredString(cx, cy - 9, tier.sublabel)

        cur_top = box_bottom - gap

    # connectors between consecutive tiers
    c.setStrokeColor(HexColor("#9E9E9E"))
    c.setLineWidth(1.4)
    for i in range(len(centers) - 1):
        x0, y0 = centers[i]
        x1, y1 = centers[i + 1]
        top_box_bottom = y0 - box_h / 2.0
        bot_box_top = y1 + box_h / 2.0
        c.line(x0, top_box_bottom, x1, bot_box_top)
        # arrowhead
        ah = 4
        c.setFillColor(HexColor("#9E9E9E"))
        c.lines([(x1 - ah, bot_box_top + ah, x1, bot_box_top),
                 (x1 + ah, bot_box_top + ah, x1, bot_box_top)])

    if title:
        c.setFillColor(HexColor("#1F4E79"))
        c.setFont("Helvetica-Oblique", 9)
        c.drawCentredString(x + width / 2.0, y_top - height - 0.28 * inch, title)


# ---------------------------------------------------------------------------
# Minimal editable Visio (.vsdx) export
# ---------------------------------------------------------------------------
#
# A .vsdx is an Open Packaging Conventions ZIP. We emit the minimal parts Visio
# needs to open the file and show a stack of labelled rectangles connected
# top-to-bottom — the same architecture shown in the PDF, but editable.

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/visio/document.xml" ContentType="application/vnd.ms-visio.drawing.main+xml"/>
  <Override PartName="/visio/pages/pages.xml" ContentType="application/vnd.ms-visio.pages+xml"/>
  <Override PartName="/visio/pages/page1.xml" ContentType="application/vnd.ms-visio.page+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/document" Target="visio/document.xml"/>
</Relationships>"""

_DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<VisioDocument xmlns="http://schemas.microsoft.com/office/visio/2012/main" xml:space="preserve">
  <DocumentSettings TopPage="0" DefaultTextStyle="0"/>
</VisioDocument>"""

_DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/pages" Target="pages/pages.xml"/>
</Relationships>"""

_PAGES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Pages xmlns="http://schemas.microsoft.com/office/visio/2012/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xml:space="preserve">
  <Page ID="0" NameU="Solution Architecture" Name="Solution Architecture" ViewScale="-1" ViewCenterX="4.25" ViewCenterY="5.5">
    <PageSheet>
      <Cell N="PageWidth" V="8.5"/>
      <Cell N="PageHeight" V="11"/>
    </PageSheet>
    <Rel r:id="rId1"/>
  </Page>
</Pages>"""

_PAGES_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/page" Target="page1.xml"/>
</Relationships>"""


def _rect_shape(shape_id: int, pin_x: float, pin_y: float,
                w: float, h: float, text: str, fill_rgb: str) -> str:
    return f"""    <Shape ID="{shape_id}" NameU="Box{shape_id}" Type="Shape">
      <Cell N="PinX" V="{pin_x:.3f}"/>
      <Cell N="PinY" V="{pin_y:.3f}"/>
      <Cell N="Width" V="{w:.3f}"/>
      <Cell N="Height" V="{h:.3f}"/>
      <Cell N="LocPinX" V="{w/2:.3f}" F="Width*0.5"/>
      <Cell N="LocPinY" V="{h/2:.3f}" F="Height*0.5"/>
      <Cell N="FillForegnd" V="{fill_rgb}"/>
      <Cell N="LineColor" V="#FFFFFF"/>
      <Cell N="Char.Color" V="#FFFFFF"/>
      <Cell N="Char.Size" V="0.13888888888889"/>
      <Section N="Geometry" IX="0">
        <Cell N="NoFill" V="0"/>
        <Row T="RelMoveTo" IX="1"><Cell N="X" V="0"/><Cell N="Y" V="0"/></Row>
        <Row T="RelLineTo" IX="2"><Cell N="X" V="1"/><Cell N="Y" V="0"/></Row>
        <Row T="RelLineTo" IX="3"><Cell N="X" V="1"/><Cell N="Y" V="1"/></Row>
        <Row T="RelLineTo" IX="4"><Cell N="X" V="0"/><Cell N="Y" V="1"/></Row>
        <Row T="RelLineTo" IX="5"><Cell N="X" V="0"/><Cell N="Y" V="0"/></Row>
      </Section>
      <Text>{escape(text)}</Text>
    </Shape>"""


def _connector_shape(shape_id: int, from_id: int, to_id: int,
                     x0: float, y0: float, x1: float, y1: float) -> str:
    begin_x, begin_y = x0, y0
    end_x, end_y = x1, y1
    w = end_x - begin_x
    h = end_y - begin_y
    return f"""    <Shape ID="{shape_id}" NameU="Connector{shape_id}" Type="Shape">
      <Cell N="PinX" V="{(begin_x+end_x)/2:.3f}"/>
      <Cell N="PinY" V="{(begin_y+end_y)/2:.3f}"/>
      <Cell N="Width" V="{abs(w) if abs(w)>0.001 else 0.001:.3f}"/>
      <Cell N="Height" V="{abs(h) if abs(h)>0.001 else 0.001:.3f}"/>
      <Cell N="BeginX" V="{begin_x:.3f}"/>
      <Cell N="BeginY" V="{begin_y:.3f}"/>
      <Cell N="EndX" V="{end_x:.3f}"/>
      <Cell N="EndY" V="{end_y:.3f}"/>
      <Cell N="LineColor" V="#9E9E9E"/>
      <Cell N="EndArrow" V="4"/>
      <Section N="Geometry" IX="0">
        <Cell N="NoFill" V="1"/>
        <Row T="MoveTo" IX="1"><Cell N="X" V="{begin_x:.3f}"/><Cell N="Y" V="{begin_y:.3f}"/></Row>
        <Row T="LineTo" IX="2"><Cell N="X" V="{end_x:.3f}"/><Cell N="Y" V="{end_y:.3f}"/></Row>
      </Section>
    </Shape>"""


def _build_page1(items: List[PricedLineItem]) -> str:
    tiers = tiers_from_items(items)
    n = len(tiers)

    page_h = 11.0
    top_margin = 1.0
    bottom_margin = 1.0
    usable = page_h - top_margin - bottom_margin
    gap = 0.4
    box_h = (usable - gap * (n - 1)) / n
    box_w = 4.5
    center_x = 4.25

    shapes: List[str] = []
    connect_rows: List[str] = []
    centers: List[float] = []

    cur_top = page_h - top_margin
    sid = 1
    box_ids: List[int] = []
    for tier in tiers:
        cy = cur_top - box_h / 2.0
        centers.append(cy)
        label = tier.label
        if tier.sublabel:
            label = f"{tier.label}\n{tier.sublabel}"
        shapes.append(_rect_shape(sid, center_x, cy, box_w, box_h, label, tier.color))
        box_ids.append(sid)
        sid += 1
        cur_top -= (box_h + gap)

    for i in range(len(centers) - 1):
        top_cy = centers[i]
        bot_cy = centers[i + 1]
        y0 = top_cy - box_h / 2.0
        y1 = bot_cy + box_h / 2.0
        shapes.append(_connector_shape(sid, box_ids[i], box_ids[i + 1],
                                       center_x, y0, center_x, y1))
        connect_rows.append(
            f'    <Connect FromSheet="{sid}" FromCell="BeginX" ToSheet="{box_ids[i]}" ToCell="PinX"/>\n'
            f'    <Connect FromSheet="{sid}" FromCell="EndX" ToSheet="{box_ids[i+1]}" ToCell="PinX"/>'
        )
        sid += 1

    shapes_xml = "\n".join(shapes)
    connects_xml = "\n".join(connect_rows)
    connects_block = f"\n  <Connects>\n{connects_xml}\n  </Connects>" if connects_xml else ""

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<PageContents xmlns="http://schemas.microsoft.com/office/visio/2012/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xml:space="preserve">
  <Shapes>
{shapes_xml}
  </Shapes>{connects_block}
</PageContents>"""


def export_vsdx(path: str, items: List[PricedLineItem]) -> str:
    """Write a minimal editable Visio (.vsdx) file. Returns the path."""
    page1 = _build_page1(items)
    parts = {
        "[Content_Types].xml": _CONTENT_TYPES,
        "_rels/.rels": _ROOT_RELS,
        "visio/document.xml": _DOCUMENT_XML,
        "visio/_rels/document.xml.rels": _DOCUMENT_RELS,
        "visio/pages/pages.xml": _PAGES_XML,
        "visio/pages/_rels/pages.xml.rels": _PAGES_RELS,
        "visio/pages/page1.xml": page1,
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in parts.items():
            z.writestr(name, content)
    return path
