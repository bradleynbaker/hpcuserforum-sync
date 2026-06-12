"""
Data models for the proposal generator.

Everything the generator needs is described by a single ProposalConfig, which
can be loaded from a JSON (or YAML, if PyYAML is installed) file. See
sample_data/hpc_cluster.json for a worked example.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional


# ---------------------------------------------------------------------------
# Customer / company
# ---------------------------------------------------------------------------

@dataclass
class Customer:
    name: str                       # contact full name
    title: str = ""                 # contact title
    agency: str = ""                # e.g. "Department of Energy"
    org_unit: str = ""              # e.g. "Office of Science / ASCR"
    email: str = ""
    phone: str = ""
    address: str = ""


@dataclass
class Company:
    """The integrator preparing the proposal (you)."""
    name: str = "CTG Federal"
    tagline: str = "Mission-Focused HPC & IT Solutions for Government"
    rep_name: str = ""
    rep_title: str = "Account Executive"
    rep_email: str = ""
    rep_phone: str = ""
    cage_code: str = ""
    uei: str = ""
    website: str = "www.ctgfederal.com"


# ---------------------------------------------------------------------------
# Quote line items
# ---------------------------------------------------------------------------

@dataclass
class LineItemSpec:
    """A requested item: a SKU + quantity. Pricing comes from the price list."""
    sku: str
    qty: int = 1
    category: str = "other"         # compute|gpu|network|storage|management|rack|software|services|other
    description_override: Optional[str] = None
    discount_pct: Optional[float] = None   # overrides the config-wide default


@dataclass
class PricedLineItem:
    """A LineItemSpec after the price list has been applied."""
    sku: str
    description: str
    manufacturer: str
    category: str
    qty: int
    unit_list: float
    discount_pct: float

    @property
    def unit_net(self) -> float:
        return round(self.unit_list * (1.0 - self.discount_pct / 100.0), 2)

    @property
    def extended(self) -> float:
        return round(self.unit_net * self.qty, 2)

    @property
    def extended_list(self) -> float:
        return round(self.unit_list * self.qty, 2)


# ---------------------------------------------------------------------------
# Engineer + contract vehicle (procurement)
# ---------------------------------------------------------------------------

@dataclass
class Engineer:
    name: str
    title: str = "Senior HPC Solutions Engineer"
    years_experience: int = 10
    clearance: str = ""             # e.g. "Active Top Secret/SCI"
    certifications: List[str] = field(default_factory=list)
    specialties: List[str] = field(default_factory=list)
    summary: str = ""               # optional seed; AI/template will expand
    day_rate: float = 0.0           # used to estimate installation services
    estimated_days: int = 0


@dataclass
class ContractVehicle:
    """A government contract vehicle the customer can buy through."""
    name: str = "NASA SEWP V"
    number: str = ""
    holder: str = "CTG Federal"
    ceiling: str = ""
    naics: str = ""
    period_of_performance: str = ""
    url: str = ""
    notes: str = ""


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------

@dataclass
class ProposalConfig:
    customer: Customer
    company: Company
    engineer: Engineer
    contract: ContractVehicle
    solution_name: str
    line_items: List[LineItemSpec]
    proposal_number: str = ""
    default_discount_pct: float = 0.0
    valid_days: int = 30
    meeting_notes: str = ""             # pasted notes -> richer exec summary
    pricelist_source: str = ""          # URL or path; blank uses the sample
    include_services_line: bool = True

    # -- loading -----------------------------------------------------------

    @classmethod
    def from_dict(cls, d: dict) -> "ProposalConfig":
        return cls(
            customer=Customer(**d["customer"]),
            company=Company(**d.get("company", {})),
            engineer=Engineer(**d["engineer"]),
            contract=ContractVehicle(**d.get("contract", {})),
            solution_name=d["solution_name"],
            line_items=[LineItemSpec(**li) for li in d["line_items"]],
            proposal_number=d.get("proposal_number", ""),
            default_discount_pct=float(d.get("default_discount_pct", 0.0)),
            valid_days=int(d.get("valid_days", 30)),
            meeting_notes=d.get("meeting_notes", ""),
            pricelist_source=d.get("pricelist_source", ""),
            include_services_line=bool(d.get("include_services_line", True)),
        )

    @classmethod
    def load(cls, path: str) -> "ProposalConfig":
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        ext = os.path.splitext(path)[1].lower()
        if ext in (".yaml", ".yml"):
            try:
                import yaml  # type: ignore
            except ImportError as e:
                raise SystemExit(
                    "PyYAML is required for .yaml configs. "
                    "Use a .json config or `pip install pyyaml`."
                ) from e
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        return asdict(self)
