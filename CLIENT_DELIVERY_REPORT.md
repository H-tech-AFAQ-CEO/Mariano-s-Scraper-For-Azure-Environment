# Mariano's Scraper — Client Delivery Report

**Project:** Mariano's Catalog Scraper for Microsoft Azure  
**Client Entry:** #34  
**Report Date:** 2026-10-21  
**Source Commit:** `019cd63cb1f2dc4029bff1042f7849e1a47ea440` (branch `main`)  
**Repository:** https://github.com/H-tech-AFAQ-CEO/Mariano-s-Scraper-For-Azure-Environment.git  
**Built by:** Zulqarnain Ahmad, with team leader Afaq Ahmad  
**Zulqarnain Freelancer:** https://www.freelancer.com/u/zulqarnaina43  
**Afaq Ahmad (Team Leader):** https://github.com/H-tech-AFAQ-CEO · https://www.freelancer.com/u/AFAQCEO

---

## Executive Summary

A complete, production-ready Mariano's grocery catalog scraper has been built, configured, and tested offline. The full source code, configuration, Azure infrastructure, documentation, and test suite are delivered on GitHub. All 15 offline unit and end-to-end tests pass. The scraper is ready for live execution once network access to marianos.com and a store configuration are provided.

**Current status:** Demonstrated and verified offline; live execution pending authorized network access.

---

## 1. What Was Delivered

### 1.1 Source Code (complete, unencrypted)

| Module | Purpose |
|--------|---------|
| `src/marianos/cli.py` | Entry point: `run`, `status`, `doctor`, `discover`, `verify-store`, `reset` |
| `src/marianos/runner.py` | Run orchestration: lock → store verify → canaries → discover → crawl → validate → publish |
| `src/marianos/driver.py` | Playwright Chromium driver: store selection, page fetch, lazy loading |
| `src/marianos/extract.py` | Pure-function DOM extraction: listings, PDPs, subcategories, product records |
| `src/marianos/schema.py` | Exact 22-field JSON order, empty-string policy, PPM, approx-weight exclusion |
| `src/marianos/deals.py` | Volume vs digital deal classification, retailer wording preserved |
| `src/marianos/guards.py` | Silent-block detection, store banner verification |
| `src/marianos/report.py` | Run report / evidence pack (counts, runtime, completeness, examples, store proof) |
| `src/marianos/validate.py` | Run-level validation: completeness floors, yield vs baseline, canaries, schema |
| `src/marianos/storage.py` | Local + Azure Blob storage, lease locking, atomic publish |
| `src/marianos/check_output.py` | Independent dataset validator |
| `src/marianos/common.py` | Structured JSON logging, retries, exceptions |

### 1.2 Configuration (externalized, no code changes needed)

| File | Purpose |
|------|---------|
| `config/categories.csv` | 28 categories from `Marianos_Category_URLs.csv` |
| `config/locations.yaml` | Store location template (needs live store details) |
| `config/selectors.yaml` | CSS selectors (Kroger-platform defaults, needs live tuning) |
| `config/settings.yaml` | Pacing, retries, block handling, validation floors, private-label brands |

### 1.3 Azure Infrastructure (defined, not deployed)

| File | Purpose |
|------|---------|
| `infra/main.bicep` | Container Apps Job per location, twice-weekly cron, Blob Storage, managed identity, Log Analytics, failure alert |

### 1.4 Docker & Dependencies

| File | Purpose |
|------|---------|
| `Dockerfile` | Playwright Chromium container image |
| `requirements.txt` | playwright, PyYAML, beautifulsoup4, lxml, azure-storage-blob, azure-identity |

### 1.5 Documentation

| File | Purpose |
|------|---------|
| `README.md` | Setup, operation, Azure deployment, cost estimate (~$7–15/month/location) |
| `docs/WALKTHROUGH.md` | Step-by-step operational guide |
| `docs/CONTEST_EVIDENCE.md` | Maps all 10 required contest evidence items to code/files |
| `docs/DEMO_VIDEO_GUIDE.md` | Demo video script and shot list |
| `ACCEPTANCE_REPORT.md` | Test summary and live-site status note |

---

## 2. What Is Verified (Offline Tests — 15/15 Pass)

| Test | What It Proves |
|------|----------------|
| `test_field_order_and_blanks` | 22 fields in exact order; `gupc=""`, `unit_price=""`; no `nulls`; no `remarks`/`gupc14` |
| `test_approx` | Approximate-weight products excluded ("approx", "approximately", "~", "avg", etc.) |
| `test_deals_brief_examples` | Volume vs digital classification for every brief example; no invented BOGO prices |
| `test_unknown_markup_still_parses` | Structural fallback extraction works when CSS classes change |
| `test_happy_path_and_output` | End-to-end run produces valid 22-field JSON; dedupe works; store verified; report SHA-256 present |
| `test_interruption_resumes_without_refetching_done_pages` | Crash + resume skips finished pages; same dataset as clean run |
| `test_failed_run_never_replaces_good_data` | Failed/blocked run goes to `rejected/`; `latest.json` untouched |
| `test_yield_drop_vs_baseline_rejected` | Thin category vs baseline is rejected |
| `test_store_mismatch_aborts_and_publishes_nothing` | Store mismatch aborts run; nothing published |
| `test_blocked_response_stops_run_resumably` | 403/blocked stops run; checkpoint kept; resumable |
| `test_lock_prevents_overlap` | Concurrent runs refused; lease auto-expires |
| `test_repeat_run_is_stable_and_uses_canaries` | Repeat run stable; 10 canaries tested |
| `test_unverifiable_store_config_fails` | Store without `banner_must_contain` is refused |
| `test_with_page` | Pagination URL construction correct |
| `test_fixtures` | Real-HTML fixture regression for listing, PDP, department, empty results, coupons |

**Important:** These tests use a synthetic fake site and HTML fixtures. They prove the logic, not compatibility with the live marianos.com markup.

---

## 3. Client Requirements — Coverage Matrix

| Client Requirement | Status | Evidence |
|--------------------|--------|----------|
| 22-field JSON in required order | Implemented | `src/marianos/schema.py:5-13` |
| Missing values as empty strings (no nulls) | Implemented | `src/marianos/schema.py:42-47` |
| `gupc` and `unit_price` empty | Implemented | `src/marianos/schema.py:48-49` |
| PPM scraped directly, never calculated | Implemented | `src/marianos/extract.py:13-16` |
| Approximate-weight products excluded | Implemented | `src/marianos/schema.py:16-23` |
| Volume vs digital offers separate | Implemented | `src/marianos/deals.py` |
| Retailer wording preserved; no calculated prices | Implemented | `src/marianos/deals.py:26-31` |
| Coupon-only records separate from product counts | Implemented | `src/marianos/validate.py` (coupon_cats exclusion) |
| Store verified on every page; mismatch aborts | Implemented | `src/marianos/guards.py`, `runner.py` |
| Dedupe by UPC (else URL) | Implemented | `src/marianos/extract.py:260` |
| Page-level checkpoints; resume skips finished pages | Implemented | `src/marianos/runner.py:270` |
| Failed run never replaces `latest.json` | Implemented | `src/marianos/runner.py:360-380` |
| Machine-readable structured logs | Implemented | `src/marianos/common.py` |
| Categories configurable outside code | Implemented | `config/categories.csv` |
| Locations configurable outside code | Implemented | `config/locations.yaml` |
| Secrets outside source code | Implemented | `config.py:proxy_from_env()` (env vars only) |
| Twice-weekly Azure cron | Defined in Bicep | `infra/main.bicep:13` |
| No stealth, CAPTCHA solving, or fingerprint spoofing | By design | `driver.py` header comment |

---

## 4. What Is NOT Yet Done (Requires Client Access)

The following items **cannot** be completed from this build environment because `marianos.com` is blocked at the TCP/TLS connection layer (observed: `RemoteDisconnected` / `ERR_CONNECTION_RESET`). No evasion or stealth tooling is included by design.

| Item | What Is Needed From You |
|------|------------------------|
| Live selector tuning | Authorized network where marianos.com loads; run `python -m marianos.cli doctor --location <id>` |
| Store #34 configuration | Store ID, details URL, or ZIP code + `banner_must_contain` tokens in `config/locations.yaml` |
| ≥500 genuine product dataset | Live run after selectors tuned and store configured |
| Raw source responses & logs | Live execution output |
| Current run report | Generated from live run |
| Azure deployment & acceptance | Azure subscription/ACR/storage access to deploy `infra/main.bicep` |
| Observed recovery test | Live run with interruption simulation |
| Store #34 fulfillment verification | Actual retailer responses from live run |

---

## 5. Prerequisites for Live Execution

### 5.1 Network Access (hard blocker)

`marianos.com` is unreachable from this environment. I need:
- A VPN, corporate network, or any connection where `marianos.com` loads normally
- No authentication, cookies, or tokens are required by the scraper design

### 5.2 Store Configuration

Add to `config/locations.yaml`:
```yaml
- id: store-34
  enabled: true
  zipcode: "<ZIP>"
  store_details_url: "<Mariano's store details URL>"
  banner_must_contain: ["<store name token>"]
  canaries: []
```

### 5.3 Azure Access (for deployment milestone only)

- ACR login server, storage account URL, Container Apps environment
- OR Contributor access to your Azure subscription to deploy `infra/main.bicep`

---

## 6. Timeline (Conditional on Access)

| Phase | Duration | Trigger |
|-------|----------|---------|
| Commit confirmation + failure-log capture + prerequisite assessment | 1 business day | After network + store access granted |
| Live selector tuning + store verification | 1 business day | After network access |
| ≥500-product live demonstration | 1–2 business days | After selectors tuned |
| Full uncapped traversal | 1–2 business days | After 500-product demo |
| Observed recovery validation | 1 business day | After full traversal |
| Azure acceptance | 1–2 business days | After Azure credentials provided |

**Total estimate: 2–3 business days for the live demonstration, conditional on access scope.**

---

## 7. What Will NOT Be Done

- No fabrication of live data, run reports, or Azure evidence
- No bypass of authentication, CAPTCHAs, or retailer access controls
- No stealth plugins, CAPTCHA solving, or fingerprint spoofing
- No paid APIs or new subscriptions required
- No broad Azure subscription access assumed; narrower permissions preferred
- No Walmart-specific work (this is a Mariano's project; no Walmart code exists)

---

## 8. Team & Credibility

- **Zulqarnain Ahmad** — Builder, https://www.freelancer.com/u/zulqarnaina43
- **Afaq Ahmad** (Team Leader) — https://github.com/H-tech-AFAQ-CEO · https://www.freelancer.com/u/AFAQCEO
- **GitHub Repository:** https://github.com/H-tech-AFAQ-CEO/Mariano-s-Scraper-For-Azure-Environment.git
- **Code Standard:** Clean, documented, test-covered, no hidden telemetry, no remote kill-switch, no undisclosed dependencies, secrets never in source, unencrypted and ready for transfer
- **Availability:** Available for additional scraping/automation projects of this kind

---

## 9. Immediate Next Step

**Grant network access to marianos.com and provide store #34 details.** Once those are available, I will:

1. Tune `config/selectors.yaml` against the live site via `doctor`
2. Configure the store in `config/locations.yaml`
3. Run the observed live scrape producing ≥500 genuine products
4. Deliver the dataset, run report, machine-readable logs, and raw response evidence
5. Proceed to Azure deployment when credentials are provided

---

**All source code, configuration, tests, documentation, and infrastructure are already on GitHub at commit `019cd63` and ready for your review.**
