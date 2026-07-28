# SPECTRE-1 Scratch Storage — Solution Fit Analysis

**Source:** Attachment C, *SPECTRE-1 Scratch Storage System Technical Requirements* v0.4 (May 2026),
plus Attachments A, B, and F (draft subcontracts).
**Customer:** UT-Battelle, LLC / Oak Ridge National Laboratory, on behalf of "the Sponsor."
**Site:** 1 Bethel Valley Road, Bldg 5300, DC-1N, Oak Ridge, TN — new classified DC dedicated to the Sponsor.
**Transitions to:** Department of War (DoW) under RMF for full ATO.

---

## 1. Bottom line

Bid a **hybrid flash + CMR-HDD parallel file system** — not all-flash, not all-HDD.

Ranked shortlist:

| # | Solution | Why |
|---|----------|-----|
| 1 | **DDN EXAScaler** (AI400X3/X3M flash SSU + SFA/ES 4U102 HDD SSUs) | Lustre, native POSIX, bare-metal control plane, deepest DOE/DoD classified field-service bench, hybrid SSU shipping 2026 |
| 2 | **IBM Storage Scale System** (SSS 6000 flash + HDD expansion) | GPFS **stores files ≤ ~3.5 KiB inside the inode** — a direct hit on the 40.2% of files that are ≤4 KiB. Best-in-class for this exact file distribution |
| 3 | **HPE Cray Supercomputing Storage Systems E2000** (Lustre) | Native Slingshot; ORNL's own Frontier/Orion is the same file system run by the same ops staff — unmatched past performance *at this site* |
| 4 | **VDURA V5000 + WD Data102 shelves** | Architecture is almost a literal answer to the RFP: VeLO director nodes hold metadata **and small files** on NVMe, VPOD/HDD for bulk; 2026 roadmap targets ~200 PB usable / 2.5 TB/s |
| 5 | **WEKA** | Best raw small-file/metadata IOPS of the field; true POSIX client; but all-flash economics at this capacity are hard to close |
| — | **VAST Data** | Only bid if ORNL relaxes "POSIX" — see §5 |

The competition will not be decided on bandwidth. It will be decided on **four constraints that most
OEMs' standard 2027 capacity configurations violate on day one** (§3), and on the
**non-technical gates** in §7 that eliminate vendors regardless of how good the array is.

---

## 2. Deal shape (from Attachment F)

The procurement is deliberately **split into two subcontracts**:

| | Hardware & Install | OEM Maintenance & Support |
|---|---|---|
| PoP | 10/31/2026 – 10/30/2032 | 12/15/2026 – 12/14/2032 |
| Type | Commercial Items, Fixed Price | Commercial Items, Fixed Price |
| NAICS | 541519 — **IT Value Added Resellers, 150-employee size standard** | 541519 — Other Computer Related Services, $34M size standard |

This matters. Attachment C repeatedly says *"This section is to be quoted by the OEM"* (§3.1.8 Software
Support, §5 Support and Maintenance, §8.4 Maintenance Plan). The structure invites a **VAR-primed hardware
award paired with an OEM-primed maintenance award**, with an explicit handoff: *"After acceptance tests
conclude, a handoff of system responsibility will occur from the hardware awardee to the maintenance/support
awardee."*

The hardware subcontract carrying the **ITVAR NAICS with a 150-employee size standard** is the single most
important commercial fact in the package for a value-added reseller. Confirm the small-business set-aside
status early — it shapes whether this is a direct bid or a teaming play.

**Schedule:** Delivery Q1CY2027 · Acceptance Q2CY2027 · Limited production Q3CY2027 · Full production Dec 2027 ·
Earliest decommissioning Q2CY2031. Facility mods complete before Q4CY2026.

Note two inconsistencies worth a clarification question: maintenance PoP starts 12/15/2026 but §5.1 says
maintenance begins *upon Acceptance* (Q2CY2027); and earliest decommissioning (Q2CY2031) precedes the end
of the 6-year maintenance PoP (12/2032).

---

## 3. The four constraints that decide this competition

### 3.1 No HAMR, no MAMR, no SMR — this caps HDDs at 26 TB

> §3.2: *"When applicable, use PMR/CMR technology for all HDDs; HAMR, MAMR, and Shingled recording devices are not permitted."*

This is the highest-impact line in the document and it is easy to miss.

- Seagate's 30 TB+ Mozaic drives are **HAMR** — excluded.
- WD's 32 TB / 40 TB-class drives are **UltraSMR** — excluded.
- Toshiba's high-capacity parts are **MAMR** — excluded.
- The largest compliant drive is the **WD Ultrastar DC HC590 at 26 TB** (ePMR/CMR, 11-platter, SAS or SATA,
  2.5M-hr MTBF), with 24 TB as the safe volume part.

Every OEM's default 2027 capacity-optimized quote will assume 30–40 TB drives. Under this rule they lose
roughly **35–50% of the capacity per rack-unit and per watt** they were counting on. Any competitor who
quotes HAMR/SMR is non-compliant; any who requotes on CMR sees their density collapse. Build the bid on
26 TB CMR from the start and make the substitution risk explicit.

**Open item:** confirm a **FIPS-certified SED SKU exists at 26 TB**. The HC590 is documented with Instant
Secure Erase; a FIPS 140-2-certified or 140-3-compliant SED variant at top capacity is *not* confirmed and
the SED/FIPS SKU historically lags the leading capacity by a generation. If it does not exist, the
compliant ceiling drops to 24 TB or lower and every capacity number below moves with it. **Resolve this
with the drive vendor before sizing anything.**

### 3.2 Power, not floor space, is the binding constraint

The electrical spec quietly sets the whole system envelope:

- 3-phase **60 A / 208 VAC** receptacles → 21.6 kVA, derated 80% continuous = **17.3 kW usable per feed**
- Dual-fed **diverse** (one utility, one UPS) — so you must design to survive on **one** side: 17.3 kW/rack
- Total cap **275 kW** across production + cluster management + 5300-DC TDS
- 275 kW ÷ 16 production racks ≈ **17.2 kW/rack** — which confirms ORNL sized the budget at exactly one
  60 A feed per rack. The two numbers are the same constraint stated twice.

Cooling is *not* the limit: an RDHX at 11 gpm with a 15 °F delta removes roughly 24 kW, comfortably above
the 17.3 kW electrical ceiling. **Design to watts, not to BTUs or to rack units.**

And because §3.2 requires the base proposal to occupy only **50% of production floor space = 8 racks**, the
base bid has a hard budget of roughly **138 kW**.

### 3.3 What 138 kW actually buys

A WD Ultrastar Data102 4U102 JBOD draws **~1,300 W typical** (1,600–1,800 W max). Working the numbers:

| Media strategy | Max in 8 racks / 138 kW | 400G endpoints affordable | Verdict |
|---|---|---|---|
| **All-HDD** (26 TB CMR) | ~87 JBODs → 230 PB raw → **~184 PB usable** @ 8+2 | ~20 (only ~24 kW left after disk) | Capacity ✓, bandwidth-starved ✗, small-file ✗✗ |
| **All-flash** (61.44 TB QLC) | **~250 PB usable**, ~4 racks of the 8 | ~48–64 | Technically the *best* fit for the envelope — but cost and NAND lead time ✗✗ |
| **Hybrid** (recommended) | **~150–180 PB usable** | ~30–40 | Balanced; lands at the low end of the band |

Two conclusions fall out of this, and both are worth putting in front of ORNL:

1. **All-flash fits the facility envelope *better* than all-HDD.** Spinning disk is what blows the power
   budget — 87 JBODs consume 114 kW and leave almost nothing for the servers that carry the 400G endpoints.
   This is counterintuitive and it is the strongest argument for a flash-heavy hybrid.
2. **In 8 racks you land near 150 PB — the bottom of the 150–250 PB band.** Reaching 250 PB requires either
   the full 16 racks or an all-flash build. See the clarification question in §6.

### 3.4 The file distribution is a metadata problem, not a capacity problem

§4.1's distribution by file count, converted to bytes (log-midpoint estimate):

| Bucket | % of files | ≈ % of bytes |
|---|---|---|
| ≤ 4 KiB | 40.2% | ~0.003% |
| ≤ 32 KiB | 24.0% | ~0.016% |
| ≤ 64 KiB | 8.1% | ~0.014% |
| ≤ 256 KiB | 9.7% | ~0.06% |
| ≤ 1 MiB | 3.8% | ~0.09% |
| ≤ 4 MiB | 9.8% | ~0.9% |
| ≤ 16 MiB | 1.1% | ~0.4% |
| ≤ 1 GiB | 2.9% | ~21.7% |
| > 1 GiB | 0.5% | ~76.8% |

**72.3% of files consume ~0.03% of the bytes.** Mean file size lands around 25–30 MiB, which at 200 PB
implies **roughly 4–10 billion inodes** (the estimate is sensitive to the ≤1 GiB bucket midpoint — plan for 10B).

The design consequence is clean and it is the core of the technical win theme:

> A flash tier of only **~0.5–1 PB usable** holds *every* inode plus *every* file ≤ 64 KiB — absorbing
> 72% of all file operations — while HDD carries 99.97% of the bytes. Small files are cheap to solve here.
> Spend the flash budget on metadata and the small-file population, and the rest on capacity.

This is also where the file systems genuinely differ:

- **IBM Storage Scale (GPFS)** stores file data *inside the 4 KiB inode* when it fits (~3.5 KiB payload). The
  40.2% of files that are ≤4 KiB require **zero data-block I/O** — read and write complete in the metadata
  operation itself. No competitor has a cleaner answer to this specific distribution.
- **Lustre** needs **Data-on-MDT** plus PFL and DNE2 striping, with flash MDTs, to get equivalent behavior.
  It works and DDN/HPE both know how to tune it, but it is configuration, not architecture.
- **VDURA/PanFS** routes small files to the VeLO director nodes on NVMe by design.
- **WEKA** distributes metadata across the cluster and is the strongest performer of the group on pure
  small-file IOPS.

---

## 4. Recommended reference configuration (base bid, 8 racks)

| Layer | Content | Capacity | Power |
|---|---|---|---|
| Metadata + small-file tier | ~8 × 2U24 NVMe TLC, FIPS SED (30.72 TB class) | ~0.6 PB usable | ~12 kW |
| Performance flash pool | 61.44 TB QLC E1.L, **FIPS 140-3 Level 2 capable** | ~25 PB usable | ~15 kW |
| Capacity tier | ~60 × 4U102, 26 TB ePMR CMR SED | 159 PB raw → ~127 PB usable @ 8+2 | ~78 kW |
| Endpoint/server layer | ~30 servers × 400G (Slingshot / UE / IB) | — | ~36 kW |
| Mgmt + TOR switching | 2 TOR per rack (customer-provided network) | — | ~8 kW |
| **Total** | | **~152 PB usable** | **~137 kW** |

Rack budget: ~306U of the available 400U — leaves genuine headroom for cabling, RDHX depth, and the
service clearances the 52" freight aisle implies. The remaining 8 racks are priced as SSU growth options
per §3.2, taking the system to ~300 PB usable at full build.

Plus, priced separately per the RFP:
- **2 × TDS** — each a minimal but complete instance: metadata server, one flash SSU, one HDD SSU, and
  management. One lives in the 17th rack at 5300-DC; the second's location is unstated (see §6).
- **On-site parts cache** sized from MTBF to sustain 2 weeks with no refresh, including hot spare nodes of
  every type.
- **1 × on-site System Software Analyst, DOE Q-cleared**, 4 years + 5th/6th year options.
- RHEL licensing and support, file system licensing, HA licensing.

**Prefer small SSU granularity.** Two TDS systems each requiring "a minimal set of each component" is a
fixed cost that scales with how coarse the building block is. A vendor whose minimum viable unit is a 2U
flash + 4U disk pair prices the TDS line item far better than one whose minimum unit is a populated rack.
On a competitive fixed-price bid this line item is a real differentiator.

---

## 5. Vendor-by-vendor

### DDN EXAScaler — *recommended lead*
Lustre with a native POSIX client and a single namespace proven at exabyte scale; installs on bare metal
with no orchestrator anywhere in the data or control path. The AI400X3 delivers ~190 GB/s per appliance, and
the **AI400X3M announced at ISC 2026 adds hybrid flash+HDD support and 30 PB per rack**, with GA expected end
of Q3 2026 — which lands right before the Q1CY2027 delivery. DDN has the deepest cleared field-service
organization in this market and extensive DOE/DoD classified past performance.
**Risks:** mdtest against a 70%-aged namespace (§5.1 below); Data-on-MDT tuning is real engineering, not a
checkbox; AI400X3M GA timing leaves little schedule margin ahead of delivery.

### IBM Storage Scale System — *strongest pure technical fit for the file distribution*
GPFS single POSIX namespace, native client, bare-metal RPM install, no orchestrator. Data-in-inode is the
decisive architectural advantage against a workload where 40% of files are ≤4 KiB. Declustered RAID (GNR)
gives fast rebuilds on 26 TB drives — which matters more than it sounds, since rebuild windows on
high-capacity CMR are long. IBM also brings the deepest ATO/RMF documentation practice of any vendor here
and has ORNL pedigree (Summit's Alpine).
**Risks:** flash $/PB; IBM's HDD-tier emphasis has softened in favor of flash, so confirm 26 TB CMR SED
support in the expansion enclosures explicitly; verify the hybrid config is a supported SKU and not a
special bid.

### HPE Cray Storage Systems E2000 — *the incumbent-advantage play*
Lustre, >2× E1000 I/O, ~190 GB/s read / 140 GB/s write per chassis, native **Slingshot** (200 Gb/s with a
400 Gb/s option) or 400 Gb/s InfiniBand. If SPECTRE-1's compute is an HPE Cray EX system, this is the
native-fabric answer. And ORNL already runs Orion — a 679 PB ClusterStor Lustre file system — with the same
operations staff who will run this one. That past-performance argument is very hard to beat *at this site*.
**Risks:** same Lustre small-file caveats as DDN; if HPE also wins the SPECTRE-1 compute award, the
hardware/maintenance split in Attachment F may cut against a single-vendor stack.

### VDURA V5000 + WD Data102 — *the architectural dark horse*
1U VeLO director nodes handle metadata **and small files** on NVMe; 5U VPOD nodes and now WD Data60/Data102
shelves carry bulk capacity. PanFS is POSIX and bare-metal. VDURA's published 2026 phase-2 target is
~200 PB usable at 2.5 TB/s — essentially the RFP's requirement restated. The March 2026 WD disk-shelf
pairing is exactly the hybrid this workload wants.
**Risks:** company scale against a 6-year fixed-price classified PoP; no cleared on-site services bench of
its own; smaller install base at 150 PB+. This one **needs a prime with cleared staff and financial
depth** — which is precisely the gap a VAR fills, and makes it the most interesting teaming opportunity
in the field.

### WEKA — *best small-file engine, hardest business case*
True POSIX client, kernel-bypass, and the strongest metadata/small-file IOPS in the field — the §4.1
distribution plays to WEKA's strengths more than anyone's. On §3.2.3, WEKA runs its services in **LXC
containers but requires no container orchestrator**, so it is defensible against the requirement as written.
**Risks:** the capacity story. All-flash at 150–250 PB is a hard budget close, and WEKA's capacity tier is
object storage, which complicates "a single POSIX-compliant namespace" and adds footprint the 8-rack
envelope does not have. Bid only with a crisp written answer to both.

### VAST Data — *bid only if ORNL relaxes POSIX*
Genuinely excellent at small files and QLC efficiency. But two requirements land against it:
- **§3.2.2 "single POSIX-compliant namespace."** VAST has no native POSIX client — access is NFS/SMB/S3.
  NFSv4.1 with RDMA and nconnect gets close, but for MPI-IO on a Slingshot/IB fabric, "POSIX semantics over
  NFS" is a substantive technical difference, not a marketing one.
- **§3.2.3 container preference.** VAST's DASE data path is built on Docker containers (CNodes). No
  Kubernetes is required, so it is arguable — but it is arguing against the grain of a stated preference.

Ask the clarification question in §6 before investing in a VAST bid.

### Poor fit — do not bid
Pure FlashBlade (namespace scale and POSIX), Dell PowerScale/OneFS (NFS/SMB, not a parallel POSIX file
system at this performance point), Qumulo and NetApp (not HPC scratch), object stores generally, and
BeeGFS (support depth insufficient for a 6-year fixed-price classified PoP). Hammerspace is interesting as
an orchestration overlay but not as the primary scratch namespace.

---

## 6. Clarification questions to submit

Ordered by how much they change the bid.

1. **Does the 150–250 PB usable requirement apply to the 8-rack base proposal, or to the full 16-rack
   build-out?** §3.2 requires proposing at 50% of floor space; §3.2.2 states the namespace requirement
   without qualifying which. Under the strict reading (150–250 PB in 8 racks at ~138 kW), the analysis in
   §3.3 shows the answer is ~150 PB — the very bottom of the band — and 250 PB is unreachable without
   all-flash. **This single answer moves the bid by a factor of two.**
2. **Is "PB" decimal (10^15) or binary (PiB)?** If PiB, every capacity number rises 12.6% and the 8-rack
   case fails outright.
3. **Is a FIPS-certified SED required at 26 TB, and will ORNL accept a lower drive capacity or
   software/filesystem-level encryption if no FIPS SED SKU exists at that capacity?** §3.2 requires FIPS
   140-2-certified or 140-3-compliant SEDs for *all* storage media. This may be unsatisfiable at the top
   CMR capacity.
4. **Does "POSIX-compliant namespace" require a native POSIX client, or is POSIX semantics delivered over
   NFSv4.1/RDMA acceptable?** Determines whether VAST-class solutions are in scope at all.
5. **What is SPECTRE-1's compute fabric — Slingshot, Ultra Ethernet, or InfiniBand?** §3.2 lists all three.
   Slingshot is HPE-proprietary and materially advantages HPE; UE/400 GbE levels the field.
6. **Where does the second TDS live?** §3.2.1 requires two identical TDS; §7 accounts for only the
   "5300-DC TDS" in the 17-rack footprint. Is the second at another ORNL location, an unclassified
   enclave, or vendor site — and does it need to be cleared?
7. **Who provides key management for the SEDs?** §3.3 lists RSA, LDAP, DNS, and license management as
   Company-provided but does not mention a KMIP key manager.
8. **Will ORNL define the namespace-aging methodology for acceptance before award?** See §5.1 below — this
   is the largest technical risk in the package.
9. **Can the maintenance PoP start date (12/15/2026) be reconciled with §5.1's "begins upon successful
   completion of Acceptance" (Q2CY2027)?**

---

## 7. Gates that eliminate vendors regardless of the array

These are not differentiators — they are pass/fail, and several will disqualify otherwise-strong OEMs.

| Requirement | Where | Why it eliminates people |
|---|---|---|
| **All personnel US citizens** — staff, vendors, *and subcontractors* — across design, development, integration, and operation | §3.1.11 | Rules out any OEM with offshore engineering in the delivery path. This is broader than most vendors' standard "US persons for on-site work" posture. Dual citizenship case-by-case |
| **DOE Q-cleared on-site System Software Analyst** | §5.5 | Clearance sponsorship and lead time. Very few storage OEMs have cleared analysts to spare |
| **No hardware leaves the site — destroyed by ORNL** | §5.3 | Every FRU, every drive, for 6 years, with no failure-analysis returns. Requires a full hardware-retention service priced across the entire BOM. Some OEMs will not warranty without returns |
| **TAA compliance** on all hardware, software, and integrated components | §3.1.6 | Drive and chassis sourcing; certification of substantial transformation |
| **Critical/High CVSS v4 fixes available and applied within 30 days** | §3.1.8 | A hard contractual SLA on third-party dependencies, not just the vendor's own code. Requires a real SBOM practice |
| **NIST 800-53 High + 800-223 + 800-207 + 800-193 + 800-161, FIPS 140-3, STIG/SCAP** with SCIS, SSP, CM Plan, IR Plan delivered | §3.1.1, §3.1.13, §3.1.14 | Full ATO documentation package. This is a professional-services line item measured in hundreds of hours — price it explicitly, do not absorb it |
| **No container orchestrator** in data path or control plane | §3.2.3 | Stated as a preference, not a mandate. Favors Lustre and GPFS; VAST and WEKA need a written rebuttal |
| **Optical or shielded twisted pair between all cabinets** | §3.1.4 | Rules out passive DAC between racks; budget for AOC/optics across the whole inter-rack fabric |
| **All connectivity overhead; no raised floor; 52" freight aisle; on-grade** | §7 | Cabinet depth, delivery, and cable management planning. Extra-deep 1300mm cabinets permitted |
| **RDHX on every cabinet** — ≤11 gpm, 60–68 °F supply, room-neutral at 75 °F inlet, BACnet/IP, leak detection with auto-shutoff, check valve on return, control valve on supply, <5% parasitic heat during maintenance | §7.2 | A detailed and unusually specific mechanical spec. The Offeror supplies, uncrates, stages, mounts, and connects the RDHXs and control valves. Engage a mechanical partner early — this is not a storage-vendor competency |

### 7.1 The acceptance risk nobody prices correctly

> §4.2: *"All acceptance tests will be performed against a namespace formatted with the same configuration as
> production and is **artificially aged at roughly 70% utilization**."*

IOR and mdtest, at 70% full, against a namespace holding billions of files, with results compared directly
to published specifications — and §8.5 adds injected failures and a stability test that keeps the system
fully subscribed.

Every vendor datasheet number is generated on an empty file system. Metadata performance on an aged,
70%-full namespace with billions of inodes can be **materially** below fresh-system numbers — allocator
fragmentation, MDT free-space behavior, and QLC garbage collection all work against you. This is where
acceptance is won or lost, and it is the most likely source of an acceptance-delay claim.

Two mitigations, both worth acting on now:

1. **Benchmark aged, publish aged.** Quote acceptance-relevant numbers from a 70%-aged test, not the
   datasheet. Discounting your own headline figure is uncomfortable in a competitive bid — but so is
   missing acceptance in Q2CY2027 on a fixed-price subcontract.
2. **Negotiate the aging methodology.** §8.5 states the acceptance test plan specifics are "determined
   during contract negotiation." How the namespace is aged — file size mix, create/delete churn, directory
   fan-out — swings mdtest results by large factors. Getting that methodology defined and agreed is the
   highest-leverage negotiation item in the entire package.

---

## 8. Win themes

1. **"We read the media restriction."** Lead with a CMR-only 26 TB design and a named FIPS SED part.
   Competitors quoting HAMR or SMR density are non-compliant; competitors who requote lose a third of their
   rack density. Make the evaluators aware this constraint exists and that only some bids honor it.
2. **"Power is the real constraint, and hybrid is the only thing that fits."** Show the 17.3 kW/rack
   arithmetic. Demonstrating that all-HDD starves the endpoint layer — and that ORNL's own 275 kW figure
   equals exactly one 60 A feed per rack — proves engineering rather than asserting it.
3. **"72% of your files, 0.03% of your bytes."** Sizing the flash tier from the actual §4.1 distribution
   rather than a percentage rule-of-thumb is the clearest possible signal that the design was done for
   *this* workload.
4. **"Aged benchmarks, because that's what acceptance measures."** Publishing 70%-aged numbers builds
   credibility and de-risks the acceptance gate for both parties.
5. **Bid all three media options as the pricing matrix invites** (§1: all-HDD, all-flash, hybrid; choice of
   adapter; choice of media capacity) with **lead times attached to each**. The RFP explicitly wants to trade
   scope against schedule under the 2026 NAND/HDD supply crunch — an Offeror who hands ORNL that lever, with
   honest lead times, is easier to award to.

---

*Prepared from the RFP package as issued. Capacity, power, and inode figures are engineering estimates from
the stated assumptions and should be re-derived against vendor-confirmed part numbers — in particular the
26 TB FIPS SED question in §3.1, which moves every capacity number in this document.*
