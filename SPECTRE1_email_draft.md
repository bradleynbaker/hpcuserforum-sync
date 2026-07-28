**Subject:** SPECTRE-1 Scratch (ORNL) — capture brief and pricing matrix

**Attach:** `SPECTRE1_Capture_Brief.pdf` · `SPECTRE1_Pricing_Matrix.xlsx`

---

Attaching our capture brief and the fill-in pricing/compliance matrix for the ORNL SPECTRE-1 Scratch storage RFP (Attachment C v0.4, May 2026).

**Recommendation**

Bid a hybrid flash + CMR-HDD parallel file system. Shortlist, in order: DDN EXAScaler, IBM Storage Scale System, HPE Cray E2000, VDURA V5000, WEKA. Appendix A of the brief documents everything we ruled out and why.

**Three things that decide this**

1. **The media ban caps HDDs at 26 TB.** §3.2 bars HAMR, MAMR and SMR, which excludes Seagate Mozaic, WD UltraSMR and Toshiba's high-capacity line. Most vendors' 2027 capacity quotes assume 30–40 TB drives and lose 35–50% of their density when requoted on CMR.

2. **Power is the binding constraint, not floor space.** 60 A / 208 V dual-fed diverse gives 17.3 kW per rack, and ORNL's 275 kW cap divided by 16 racks is the same number. The 8-rack base bid has roughly 138 kW to work with. All-HDD spends 114 kW of that on JBODs and starves the endpoint layer.

3. **72% of files are under 64 KiB but consume 0.03% of the bytes.** A flash tier of well under 1 PB absorbs every inode and every small file; HDD carries the rest. Sizing flash from the actual distribution rather than a rule of thumb is our clearest technical differentiator.

**Deal shape**

Split into two fixed-price subcontracts. The hardware and install award carries NAICS 541519 IT Value Added Resellers with a 150-employee size standard — worth confirming the set-aside status early, as it determines whether we bid direct or team.

**Two open items before anyone builds a config**

- Does the 150–250 PB requirement apply to the 8-rack base bid or the full 16-rack build? Under the strict reading the honest answer is ~150 PB, and 250 PB is unreachable without all-flash. This moves the bid by a factor of two.
- Does a FIPS-certified SED exist at 26 TB? The SED SKU historically trails the leading capacity by a generation. If it does not exist, every capacity number in the brief moves.

The brief carries 48 edge cases with severity ratings, 13 clarification questions ordered by impact, and the full appendix of no-bid decisions. The workbook has the Compliance Matrix pre-populated with all 63 Attachment C requirements, and the Media Options tab automatically flags any HAMR/MAMR/SMR, missing SED, or TAA failure.

Competition sensitive — internal use.
