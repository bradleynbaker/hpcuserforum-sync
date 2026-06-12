"""
proposal_generator — Generate a complete federal IT proposal from a meeting.

Given a customer/solution configuration, this package produces a polished,
multi-page proposal PDF:

  Page 1  Cover page          (customer, agency, solution, prepared-by)
  Page 2  Quote              (manufacturer price list applied to a config)
  Page 3  Architecture diagram (rendered in-PDF; editable .vsdx export too)
  Page 4  Engineer bio + government contract vehicle to procure against

The "AI" pieces (executive summary, engineer bio) use the Claude API when
ANTHROPIC_API_KEY is set, and fall back to clean templates when it is not,
so the tool always runs.
"""

from .models import (
    Customer,
    LineItemSpec,
    PricedLineItem,
    Engineer,
    ContractVehicle,
    Company,
    ProposalConfig,
)

__all__ = [
    "Customer",
    "LineItemSpec",
    "PricedLineItem",
    "Engineer",
    "ContractVehicle",
    "Company",
    "ProposalConfig",
    "__version__",
]

__version__ = "0.1.0"
