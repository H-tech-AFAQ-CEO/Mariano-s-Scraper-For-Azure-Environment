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

## Live Site Status Note
- **Live Target (`marianos.com`)**: Automated access is actively blocked at the TCP/TLS connection layer (`RemoteDisconnected` / `ERR_CONNECTION_RESET`) by the retailer's anti-bot infrastructure (Akamai/WAF). Per instructions and Hard Rule 6, no evasion or stealth tooling has been added; execution runs against robust synthetic test fixtures and fakesite harness.
