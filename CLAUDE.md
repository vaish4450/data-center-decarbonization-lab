# Data Center Decarbonization Lab: assistant briefing

You are my step-by-step build assistant and guide for this repo. Read this whole file before doing anything. Follow the Working Agreement in section 2 on every turn.

## 1. The project

**Decision question:** How should a hypothetical data-center operator combine energy efficiency, clean-electricity procurement, battery storage and cooling flexibility to reduce emissions and manage cost?

- Two **synthetic** campuses: one in **PJM**, one in **CAISO**. No real company's facilities. All facility parameters are flagged assumptions in `config/<iso>.yaml`.
- Public portfolio project (repo is private for now). Owner: Vaishnavi Singh, energy data scientist (power markets, TES/BESS dispatch, Pyomo).
- Methods: **operations research** is the core (LP/MILP dispatch with Pyomo, duals, Pareto frontier, investment sizing). Data science supports it (data pulls, cleaning, load shapes). **Causal inference is NOT claimed**: interventions are counterfactual scenario analysis.
- Snowflake/Databricks are deferred. Do not suggest them until I ask.
- The full project structure lives in my Claude Docs project doc (source of truth for module list, repo tree and 8-week plan): https://claude.ai/code/artifact/ef8c5eb5-e5b7-48a4-87e9-0b1a22dd704b. If this file and the doc disagree, tell me and ask which wins.

### Modules (numbering and detail are in the project doc)
1. Organizational inventory (annual, operational-combustion grid-average basis)
2. Hourly clean-energy matching (an *illustrative hourly matching metric*)
3. Cooling-storage and battery dispatch (Pyomo)
4. Investment sizing and roadmap
5. Embodied carbon
6. PJM large-load policy exposure (hypothetical scenarios built on the FERC order on PJM's rejected IRAS proposal)
7. Dashboard with a map of data-center regions (PJM and CAISO)

### Rough phases (adjust to the doc's 8-week plan)
- [ ] Phase 1: data pull, cleaning, emission factors, facility load model, annual vs hourly matching (PJM first)
- [ ] Phase 2: cooling-storage + battery dispatch, CAISO re-run, 2024 as robustness year
- [ ] Phase 3: investment sizing, Module 6 policy scenarios, dashboard and map
- [ ] Phase 4: embodied carbon, tests, README, polish

## 2. Working Agreement (most important)

I want to build **one small step at a time**, with you consistently interacting with me.

1. **One step per turn.** Propose the single next step, say what it produces and why, then stop. Do not build ahead, do not scaffold the whole repo, do not create files I have not asked for.
2. **Before writing code**, state the goal in one line and list the files you will create or change. Wait for my OK on anything that adds more than ~1 file or ~80 lines.
3. **Always give me the exact command to run** and tell me what output to paste back. When I paste output, say clearly: pass / fail / suspicious, and why, before moving on.
4. **Verify, never assume.** If a number, unit, column, API behavior or file content matters, check it in the data or the docs. Say "I haven't verified this" when that is the case.
5. **Never invent** emission factors, capacity credits, prices, or policy parameters. Source them with a citation, or put them in `config/*.yaml` marked as an assumption for me to approve.
6. **Do not cut scope.** If something must be deferred, put it on the list in section 6, don't delete it.
7. **Format:** direct and fast. Tables and checklists over long prose. Short explanations of *why*, in plain words, because I want to understand each step.
8. **End every reply with** (a) what is now done, (b) 1-3 options for the next step with your recommendation.
9. **When I disagree or I'm confused**, slow down, re-explain with a concrete example from our actual data, and don't defend the earlier answer.
10. **Commit points:** after each working step, suggest a commit message. Run `pytest` first once tests exist. Never commit `.env`, `data/raw`, `data/interim`, or parquet files.
11. If a request would break a ground rule (section 3), say so and propose the compliant version.

## 3. Ground rules the code and writing must respect

- Facilities are synthetic and hypothetical. Never imply data about a real company's site.
- Keep three results separate: **organizational inventory**, **hourly matching**, **intervention impact**. Every intervention number states its counterfactual.
- Call the hourly ratio an "illustrative hourly matching metric". Do not claim it reproduces any company's published score.
- **Battery discharge is clean only to the extent its charging energy was clean** (track charge origin).
- Cooling energy only in v1. Water use is out of scope.
- Emission intensity is a grid-average, operational-combustion figure: not marginal, imports ignored. State this wherever intensity is used.
- Hourly series use a tz-aware **UTC** DatetimeIndex; convert to local time only for shape and reporting.
- Config is per ISO in `config/<iso>.yaml`; switching ISO must not require code changes.
- PJM policy scenarios (IRAS-like curtailment) are hypothetical. FERC order ER26-3515 (Oct 9, 2026) rejected IRAS, New Large Load, BYONC and the VRR exclusion, and accepted the Large Load definition (≥50 MW cumulative peak at a site, one-mile aggregation) and a Large Load Registry. FERC pointed to Non-Firm Contract Demand as a voluntary alternative.

## 4. Environment

- macOS, VS Code, Python venv at `.venv` (conda `(base)` in the prompt is harmless). Packages installed and checked: pandas, requests, python-dotenv, pyarrow, Pyomo + HiGHS (`appsi_highs` works).
- Repo: `data-center-decarbonization-lab`, private. Secrets in `.env` (`EIA_API_KEY=...`, no quotes), gitignored.
- Files are built **as needed**, step by step. A previous full skeleton was deliberately not used. Do not re-propose it.

## 5. Current state (as of Oct 17, 2026)

**Done**
- `pull_eia.py` at repo root: `python pull_eia.py <PJM|CISO> 2025` writes two parquet files per ISO to `data/raw/`:
  - `{iso}_fuel_mix_2025.parquet`: wide table, UTC hourly index, one column per EIA fuel code, values in MWh per hour (= average MW for that hour).
  - `{iso}_demand_2025.parquet`: one column `demand_mw`, one row per UTC hour. Source: EIA `region-data`, `type = D` (system demand). It is a separate EIA series, **not** a sum of the fuel columns.
- Decision: keep just these two files per ISO (no `_long` raw files, no extra columns for now). A data dictionary comes later.

**Data facts so far**

| ISO | Fuel-mix hours | Fuel codes | Demand hours | Notes |
|---|---|---|---|---|
| PJM 2025 | 8,759 (1 missing: 2025-11-03 05:00 UTC) | COL, NG, NUC, OIL, OTH, SUN, WAT, WND | 8,760 | Demand mean ≈ 96,242 MW, min 66,131, max 160,560 |
| CISO 2025 | 8,760 (none missing) | COL, GEO, NG, NUC, OIL, OTH, SUN, WAT, WND | 8,760 | See open issues below |

**Open data issues (not yet resolved)**
- CISO has **negative values** (these are net generation, so this is real data, not an error): SUN slightly negative at night (station power), COL ≈ -1, and `OTH` swings between large negatives and positives. `OTH` **may** be battery storage (charging negative, discharging positive). This is an inference, **not verified**.
- CISO `GEO` has many NaN rows (70,455 rows vs 8,760 × 9 = 78,840 expected). Cause not yet confirmed.
- EIA reports other `region-data` types (DF day-ahead forecast, NG net generation, TI total interchange) that we have **not** pulled. They would allow an exact check: demand ≈ net generation − interchange.
- Units: fuel values are `megawatthours`. The unit label for demand has not been printed or confirmed.

## 6. Next steps (in order; do one at a time, wait for me)

- [ ] Run the CISO diagnostic (NaN counts per column, min/mean/max, hourly average of `OTH`, count of negative hours for OTH and SUN) and decide how to treat `OTH` and `GEO`
- [ ] Optional: generation-vs-demand annual TWh check for both ISOs
- [ ] Confirm demand unit
- [ ] Commit `pull_eia.py`; confirm `.env` and `data/raw` are not tracked (`git check-ignore .env`, `git status`)
- [ ] Cleaning step (new file): fill the PJM missing hour by interpolation, flag it, document it, never touch raw files; output to `data/interim/`
- [ ] Data dictionary (code → name table: COL Coal, NG Natural Gas, NUC Nuclear, OIL Petroleum, OTH Other, SUN Solar, WAT Hydro, WND Wind, GEO Geothermal; units; filled hours)
- [ ] Emission factors file: zeros for NUC/SUN/WND/WAT/GEO as operational combustion; COL/NG/OIL/OTH must come from a **cited** source; decide `OTH` treatment (it is not a fuel if it contains storage)
- [ ] Facility load model (synthetic IT load, PUE, cooling share) in `config/<iso>.yaml`
- [ ] Scenario A (annual matching) vs Scenario B (hourly matching), PJM first
- [ ] Pyomo cooling-storage + battery dispatch with charge-origin tracking
- [ ] CAISO re-run; 2024 as robustness year; Module 6 scenarios; dashboard and map

## 7. How I will talk to you

I will paste terminal output, ask "why" questions, and sometimes say I'm confused. I'd rather get a correct small step than a big guess. If I ask something that sounds simple but depends on our data, check the data first.
