"""
AI-generated narrative for the proposal (executive summary + engineer bio).

Uses the Claude API when ANTHROPIC_API_KEY is set; otherwise falls back to
clean, deterministic templates so the generator always produces a complete
document offline.

Model can be overridden with PROPOSAL_AI_MODEL (default: claude-sonnet-4-6).
"""

from __future__ import annotations

import os
from typing import List

from .models import Customer, Engineer, PricedLineItem

DEFAULT_MODEL = os.environ.get("PROPOSAL_AI_MODEL", "claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# Claude client (optional)
# ---------------------------------------------------------------------------

def _client():
    """Return an Anthropic client, or None if unavailable."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError:
        return None
    try:
        return Anthropic()
    except Exception:
        return None


def _ask(prompt: str, system: str, max_tokens: int = 700) -> str | None:
    client = _client()
    if client is None:
        return None
    try:
        resp = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        text = "\n".join(parts).strip()
        return text or None
    except Exception as e:  # network/auth/etc. — degrade gracefully
        print(f"[AI] Claude call failed ({e}); using template fallback.")
        return None


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------

def executive_summary(customer: Customer, solution_name: str,
                      items: List[PricedLineItem], meeting_notes: str = "") -> str:
    inventory = ", ".join(
        f"{p.qty}× {p.description or p.sku}" for p in items[:8] if p.qty
    )
    system = (
        "You are a senior federal IT capture/solutions writer at a government "
        "systems integrator. Write concise, credible, non-hyperbolic prose. "
        "No markdown, no bullet symbols — plain paragraphs only."
    )
    prompt = (
        f"Write a 2-paragraph executive summary for an IT solution proposal.\n"
        f"Customer: {customer.name}"
        + (f", {customer.title}" if customer.title else "")
        + (f", {customer.agency}" if customer.agency else "")
        + f"\nSolution name: {solution_name}\n"
        f"Key components: {inventory}\n"
        + (f"Notes from the customer meeting: {meeting_notes}\n" if meeting_notes else "")
        + "Focus on mission outcomes, then the proposed approach. ~120 words."
    )
    out = _ask(prompt, system)
    if out:
        return out

    # ---- template fallback ----
    who = customer.agency or customer.name
    notes_line = (
        f" Building on the priorities discussed in our meeting — {meeting_notes.strip()} —"
        if meeting_notes else ""
    )
    return (
        f"{solution_name} is engineered to advance the mission of {who} by "
        f"delivering a turnkey, high-performance computing environment that is "
        f"secure, scalable, and ready for accreditation in a federal "
        f"environment.{notes_line} The proposed architecture pairs current-"
        f"generation compute and accelerators with a high-speed interconnect "
        f"and parallel storage so that demanding workloads complete faster and "
        f"researchers spend less time waiting on infrastructure.\n\n"
        f"This proposal provides a complete bill of materials priced from the "
        f"manufacturer's current price list, a reference architecture, and a "
        f"named senior engineer to deliver the installation. All hardware, "
        f"software, and integration services are available for immediate "
        f"procurement through an established government contract vehicle, "
        f"streamlining acquisition for {customer.name or 'your team'}."
    )


# ---------------------------------------------------------------------------
# Engineer bio
# ---------------------------------------------------------------------------

def engineer_bio(engineer: Engineer, solution_name: str) -> str:
    system = (
        "You are writing a professional staff biography for a federal proposal. "
        "Third person, confident but factual, no markdown. One tight paragraph."
    )
    certs = ", ".join(engineer.certifications) or "industry certifications"
    specs = ", ".join(engineer.specialties) or "HPC systems integration"
    prompt = (
        f"Write a ~110-word professional bio for the engineer who will lead "
        f"installation of '{solution_name}'.\n"
        f"Name: {engineer.name}\nTitle: {engineer.title}\n"
        f"Experience: {engineer.years_experience} years\n"
        f"Clearance: {engineer.clearance or 'N/A'}\n"
        f"Certifications: {certs}\nSpecialties: {specs}\n"
        + (f"Seed details: {engineer.summary}\n" if engineer.summary else "")
        + "Emphasize hands-on delivery in government environments."
    )
    out = _ask(prompt, system)
    if out:
        return out

    # ---- template fallback ----
    clearance = f" Holding an {engineer.clearance}," if engineer.clearance else ""
    return (
        f"{engineer.name} is a {engineer.title} with {engineer.years_experience} "
        f"years of experience designing, deploying, and supporting high-"
        f"performance computing environments for government and research "
        f"organizations.{clearance} {engineer.name.split()[0]} specializes in "
        f"{specs}, and will personally lead the installation, integration, and "
        f"acceptance testing of {solution_name} on site. Credentials include "
        f"{certs}. From rack-and-stack and fabric bring-up through scheduler "
        f"configuration, benchmarking, and knowledge transfer to your staff, "
        f"{engineer.name.split()[0]} ensures the system is delivered fully "
        f"operational, documented, and ready to support mission workloads from "
        f"day one."
    )
