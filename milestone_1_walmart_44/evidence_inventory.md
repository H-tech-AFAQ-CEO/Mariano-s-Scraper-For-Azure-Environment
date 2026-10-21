Evidence Inventory — Mariano's Scraper Project
==============================================

IMPORTANT DISCREPANCY NOTICE:
-----------------------------
This inventory is for the Mariano's scraper project actually present.
There is no Walmart #44 evidence. No Walmart logs, responses, datasets, or
store #44 configuration exist in this repository.

Classification key:
  [CODE]     Source code file (implementation logic)
  [CONFIG]   Configuration file (tunable, no secrets)
  [DOC]      Documentation file
  [INFRA]    Infrastructure-as-code template (not deployed)
  [TEST]     Offline test (synthetic/fixture-based, not live)
  [FIXTURE]  Static HTML fixture (not a live response)
  [EMPTY]    Directory exists but contains no evidence files
  [MISSING]  Expected artifact not present

Source code (CODE):
  src/marianos/__init__.py          Version
  src/marianos/cli.py               CLI entry point
  src/marianos/common.py            Exceptions, logging, retry helper
  src/marianos/config.py            Configuration loading
  src/marianos/deals.py             Volume vs digital deal classification
  src/marianos/driver.py            Playwright driver (store select, fetch, lazy load)
  src/marianos/extract.py           DOM extraction (listing, PDP, subcategories, records)
  src/marianos/guards.py            Block detection, store matching
  src/marianos/report.py            Run report builder
  src/marianos/runner.py            Run orchestration (lock, verify, canaries, crawl, validate, publish)
  src/marianos/schema.py            22-field schema, empty-string policy, PPM, approx-weight
  src/marianos/storage.py           LocalStorage + AzureBlobStorage, locking
  src/marianos/validate.py          Run-level validation
  src/marianos/check_output.py      Independent dataset checker

Configuration (CONFIG):
  config/categories.csv             28 category rows from Marianos_Category_URLs.csv
  config/locations.yaml             Location template (no live store configured)
  config/selectors.yaml             CSS selectors (Kroger-platform defaults, require live tuning)
  config/settings.yaml              Pacing, retries, block, browser, crawl, validation, publish

Infrastructure (INFRA — not deployed, no live evidence):
  infra/main.bicep                  Azure Container Apps Job Bicep template

Documentation (DOC):
  README.md                         Setup, operation, Azure deployment, cost estimate
  docs/WALKTHROUGH.md               Step-by-step operational guide
  docs/CONTEST_EVIDENCE.md          Mapping of 10 contest evidence items to code/files
  docs/DEMO_VIDEO_GUIDE.md          Demo video script and shot list
  ACCEPTANCE_REPORT.md              Test summary and live-site status note
  Shared_Scraper_Technical_Requirements.docx Client requirements document
  Marianos_Category_URLs.csv        Source category URL list (28 categories)

Tests (TEST — synthetic/fixture, not live):
  tests/test_scraper.py             15 offline unit/end-to-end tests
  tests/fakesite.py                 Synthetic fake Mariano's site + driver
  tests/fixtures/coupons.html       Static HTML fixture (coupon listing)
  tests/fixtures/department.html    Static HTML fixture (department page)
  tests/fixtures/empty_results.html Static HTML fixture (empty results page)
  tests/fixtures/listing_deal.html  Static HTML fixture (listing with deals)
  tests/fixtures/pdp.html           Static HTML fixture (product detail page)

Logs / saved responses / datasets / screenshots:
  doctor_out/                       EMPTY — no saved page.html or header.png from a live run
  data/                             MISSING — no local data directory (no published/rejected datasets)
  No .log files, no .har files, no HAR traces, no execution reports from a live run.

Store configuration evidence:
  config/locations.yaml contains a template location block with:
    - id: chicago-roosevelt (example, not verified)
    - zipcode: "60607"
    - banner_must_contain: [] (empty — store cannot be verified in current config)
    - store_details_url: "" (empty)
    - canaries: [] (empty)
  No actual retailer responses demonstrate store #34 or any Mariano's location.

Walmart #44 evidence:
  MISSING — Not present. No Walmart code, configuration, selectors, store #44
  configuration, or Walmart-sourced data exists in this repository.