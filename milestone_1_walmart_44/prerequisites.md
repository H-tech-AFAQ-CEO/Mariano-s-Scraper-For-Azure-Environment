Minimum Prerequisites — Genuine Future Live Run (Mariano's Scraper)
====================================================================

IMPORTANT DISCREPANCY NOTICE:
-----------------------------
This prerequisite assessment is for the Mariano's scraper project actually present.
There is no Walmart #44 project. No Walmart credentials, cookies, private tokens,
or authenticated customer accounts are required or assumed.

Azure deployment requirements are listed separately and are NOT required for
Milestone 1 or for a future local live run.

| Requirement                            | Why it is needed                                      | Already available? | Minimum action                                  |
|----------------------------------------|-------------------------------------------------------|--------------------|-------------------------------------------------|
| Source code + repository metadata      | Execute the scraper implementation                    | Yes                | None — present at commit 019cd63                |
| Python 3.12 runtime                    | Run the scraper                                       | Yes (3.12.10)      | None                                            |
| Playwright + Chromium browser          | Browser automation for page loads                     | Partially          | Run `python -m playwright install chromium`     |
| PyYAML, beautifulsoup4, lxml           | Config parsing, HTML extraction                       | Yes                | None                                            |
| azure-storage-blob, azure-identity     | Azure Blob Storage backend (future Azure milestone)   | Yes (installed)    | Not required for local live run                 |
| Permitted outbound network to marianos.com | Fetch live category pages, product pages, store finder | NO (blocked at TCP/TLS from this environment) | Authorized network where marianos.com is reachable |
| Mariano's store configuration          | Select and verify the correct store                   | Partially          | Configure locations.yaml with store #34 ZIP/URL + banner_must_contain tokens |
| CSS selectors tuned to live site       | Parse product cards, prices, PPM, deals, subcategories | Partially (defaults only) | Run `python -m marianos.cli doctor --location <id>` and tune config/selectors.yaml |
| Local disk space                       | Save datasets, logs, checkpoints, reports             | Yes                | None                                            |
| Execution time (~1-3 hours per run)    | Full category traversal                               | Yes                | None                                            |
| Retailer credentials / cookies / tokens| NOT required by design (no authentication built in)   | Not required       | None                                            |
| Paid APIs / third-party services       | NOT required by design                                | Not required       | None                                            |
| Azure subscription / ACR / storage     | Only for future Azure deployment milestone            | NO                 | Separate milestone — not in scope for Milestone 1 |

Classification for Milestone 1:
  - Confirmed available: Source code, Python runtime, PyYAML, bs4, lxml, local disk, execution time
  - Partially available: Playwright (installed but Chromium browser not yet downloaded), store configuration (template only, no live store)
  - Missing: Network access to marianos.com, live store configuration, tuned selectors
  - Not required for Milestone 1: Azure subscription, retailer credentials, paid APIs

Minimum action to unblock a local live run:
  1. Obtain network access where marianos.com is reachable.
  2. Configure a Mariano's location in config/locations.yaml (zipcode, store_details_url or ZIP search, banner_must_contain tokens).
  3. Run `python -m marianos.cli doctor --location <id>` and tune config/selectors.yaml.
  4. Run `python -m marianos.cli run --location <id>` for a local live run.