Next Steps — Mariano's Scraper Project
======================================

IMPORTANT DISCREPANCY NOTICE:
-----------------------------
This next-steps plan is for the Mariano's scraper project actually present.
There is no Walmart #44 project. No Walmart-specific steps are applicable.

PRIORITY 1 — Unblock live execution (required before any live deliverable):

Step 1 (highest priority): Obtain authorized network access where marianos.com is reachable.
  - The site is blocked at the TCP/TLS layer from this build environment.
  - No code change can bypass this; network access is a hard prerequisite.
  - Do not use evasion, stealth, CAPTCHA solving, or fingerprint spoofing.

Step 2: Configure a real Mariano's location in config/locations.yaml.
  - Provide zipcode, store_details_url (preferred) or ZIP search.
  - Set banner_must_contain tokens (e.g. ["Roosevelt"]) — ALL must appear in the header
    store banner on every page, or the run fails. A location with no tokens is refused.
  - Optional: store_id for cookie verification, canary product URLs.

Step 3: Tune CSS selectors against the live site.
  - Run: $env:PYTHONPATH="src"; python -m marianos.cli doctor --location <id>
  - Review doctor_out/page.html and doctor_out/header.png.
  - Adjust config/selectors.yaml until: banner matches, cards > 0, titles/prices/UPC/PPM
    populate, subcategories discover correctly.
  - Selectors are best-knowledge Kroger-platform defaults; they require live confirmation.

Step 4: Run a local live scrape.
  - Run: $env:PYTHONPATH="src"; python -m marianos.cli run --location <id>
  - Validate output: $env:PYTHONPATH="src"; python -m marianos.check_output
    data/published/marianos-<id>/runs/<run>/dataset.json

Step 5: Configure Azure deployment (separate from collection).
  - Deploy infra/main.bicep via `az deployment group create`.
  - Push image to ACR: `az acr build -r <acr> -t marianos-scraper:1.0.0 .`
  - Start job: `az containerapp job start -g <rg> -n marianos-<id>`

PRIORITY 2 — Future milestones (separate, not part of Milestone 1):

Milestone 2: 500-genuine-product demonstration
  - Observed live run producing >=500 valid products across all required categories
    and applicable subcategories.
  - Complete pagination, no sampling caps.
  - Raw source responses and machine-readable logs as evidence.
  - Coupon-only records kept separate from product counts.

Milestone 3: Full uncapped production traversal
  - All categories and subcategories traversed without demonstration limits.
  - Declared-total coverage >=95% per category.
  - Yield vs baseline >=70% per category, >=80% total.

Milestone 4: Observed recovery validation
  - Interruption recovery: crash + resume produces identical dataset to clean run.
  - Failed/blocked/thin run never replaces last good dataset (latest.json untouched).

Milestone 5: Azure acceptance
  - Observed Azure Container Apps Job execution.
  - Twice-weekly cron (Tue/Fri 08:00 UTC) verified.
  - Blob Storage outputs, Log Analytics traces, lease locking confirmed.

Blockers supported by inspection:
  1. Network access to marianos.com is blocked from this environment (TCP/TLS).
  2. No live Mariano's store is configured in config/locations.yaml.
  3. CSS selectors are untested defaults requiring live tuning.
  4. No Azure deployment has been executed (infra/main.bicep is untested Bicep).
  5. No live dataset, logs, or run report exists.

What will NOT be done:
  - No fabrication of live data, reports, or Azure evidence.
  - No Walmart-specific work (no Walmart project exists here).
  - No bypass of authentication, CAPTCHAs, or access controls.
  - No paid APIs or new subscriptions.
  - No broad Azure subscription access assumed; narrower permissions preferred.