# Mariano's Scraper Acceptance Report

This report documents the verification status of all test suites, acceptance requirements, and operational flows.

## Test Summary

| Test Category | Command / Scope | Date | Result | Artifact Path |
|---|---|---|---|---|
| Offline Unit Tests | `PYTHONPATH=src python -m unittest discover -s tests -v` | 2025-02-17 | **PASSED (15/15)** | [test_scraper.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/tests/test_scraper.py) |
| Field Order & Schema | `test_field_order_and_blanks` | 2025-02-17 | **PASSED** | [schema.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/schema.py) |
| Approx-weight exclusion | `test_approx` | 2025-02-17 | **PASSED** | [schema.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/schema.py) |
| Deal Classification | `test_deals_brief_examples` | 2025-02-17 | **PASSED** | [deals.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/deals.py) |
| Fallback Extraction | `test_unknown_markup_still_parses` | 2025-02-17 | **PASSED** | [extract.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/extract.py) |
| End-to-End Happy Path | `test_happy_path_and_output` | 2025-02-17 | **PASSED** | [runner.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/runner.py) |
| Interruption & Resume | `test_interruption_resumes_without_refetching_done_pages` | 2025-02-17 | **PASSED** | [runner.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/runner.py) |
| Failure Protection | `test_failed_run_never_replaces_good_data` | 2025-02-17 | **PASSED** | [validate.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/validate.py) |
| Yield Drop Detection | `test_yield_drop_vs_baseline_rejected` | 2025-02-17 | **PASSED** | [validate.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/validate.py) |
| Store Mismatch Abort | `test_store_mismatch_aborts_and_publishes_nothing` | 2025-02-17 | **PASSED** | [guards.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/guards.py) |
| Blocked Response Handling | `test_blocked_response_stops_run_resumably` | 2025-02-17 | **PASSED** | [guards.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/guards.py) |
| Lock Overlap Prevention | `test_lock_prevents_overlap` | 2025-02-17 | **PASSED** | [storage.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/storage.py) |
| Real HTML Fixtures | `TestFixtureRegression` | 2025-02-17 | **PASSED** | [tests/fixtures/](file:///C:/Users/Afaq/Desktop/marianos-scraper/tests/fixtures/) |

## Category Count Clarification

`config/categories.csv` (derived from `Marianos_Category_URLs.csv`) contains **28 data rows** (29 lines including the header row). The categories are: Coupons, Produce, Meat, Seafood, Deli, Bakery, Floral, Grocery, Dairy, Frozen, Natural Organic, Beverages, Breakfast, Coffee, Candy, Beer Wine Liquor, Health, Personal Care, Beauty, Baby, Household, Kitchen Dining, Pet Supplies, Candles Home Fragrances, Batteries, Light Bulbs, School Office, Hardware Home Improvement. Any reference to "29 categories" elsewhere is a miscount of the header row; the correct count is 28 scrapable categories.

## Live Site Status Note

- **Test dates (2025-02-17)**: These dates reflect when the offline unit/end-to-end test suite was last executed against synthetic fixtures. They are **not** live-site test dates.
- **Live Target (`marianos.com`)**: Automated access is actively blocked at the TCP/TLS connection layer (`RemoteDisconnected` / `ERR_CONNECTION_RESET`) by the retailer's anti-bot infrastructure (Akamai/WAF) from this build environment. Per instructions and by design, no evasion or stealth tooling has been added. Execution runs against robust synthetic test fixtures and fakesite harness only. Live validation, store-selection flow, Azure deployment, and ≥500-product dataset generation require an authorized network where marianos.com is reachable.

