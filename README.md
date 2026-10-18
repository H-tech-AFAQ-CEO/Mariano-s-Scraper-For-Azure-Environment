# Mariano's Scraper (Python + Playwright, Azure Container Apps Job)

Location-specific catalog scraper for marianos.com. Scrapes every category in `config/categories.csv` and its
subcategories for each store in `config/locations.yaml`, writes the 22-field JSON in the required order, validates the
run, and **only then** publishes it. Runs twice a week as a scheduled Azure Container Apps Job.

## Team / Attribution

Built by **Zulqarnain Ahmad** in collaboration with team leader **Afaq Ahmad**.

- Zulqarnain Ahmad: https://www.freelancer.com/u/zulqarnaina43
- Afaq Ahmad (Team leader): https://github.com/H-tech-AFAQ-CEO · https://www.freelancer.com/u/AFAQCEO

This entry is submitted on behalf of the above team.

> ## READ FIRST: what has and has not been verified
> | Verified (automated tests, `python -m unittest discover -s tests`) | NOT verified (needs your first live run) |
> |---|---|
> | 22-field order, empty-string policy, `gupc`/`unit_price` always `""`, no `remarks`/`gupc14` | **That the default CSS selectors match marianos.com.** They are best-knowledge Kroger-platform defaults; structural fallbacks (the `/p/<slug>/<UPC>` URL, `$` regex) soften but do not remove this risk. |
> | Volume vs digital deal classification for every example in the brief; no calculated/invented deal prices | **Store selection UI flow** (`driver.select_store`) against the live store finder. |
> | Approx-weight exclusion, dedupe (pagination overlap, repeated category placement) | **Whether Mariano's/Kroger's bot protection allows your run** (no evasion is built in, by design). |
> | Page-level checkpoint **resume** after a crash (cost ≈ one clean run, not crash-point + rerun) | The Azure Blob storage backend and `infra/main.bicep` (written, never executed: no Azure access where this was built). |
> | A bad/blocked/thin/mismatched run is **rejected and never replaces** the last good dataset | Real counts, runtime, and cost numbers. |
> | Store mismatch aborts the run; overlapping runs are refused; fresh runs never inherit another run's checkpoints | |
>
> The tests use a **synthetic fake site** (`tests/fakesite.py`). They prove the logic, not compatibility with the real site.
> **Run `python -m marianos.cli doctor --location <id>` first** (see Setup step 4) and tune `config/selectors.yaml` from its output.

## Layout
```
config/  settings.yaml  locations.yaml  selectors.yaml  categories.csv   <- all tuning lives here, no code edits
src/marianos/  cli.py runner.py driver.py extract.py deals.py schema.py validate.py guards.py report.py storage.py config.py check_output.py
tests/         unit + end-to-end (fake site) tests
infra/main.bicep   Container Apps Job per location, cron, storage, logs, managed identity
Dockerfile  requirements.txt
```

## Setup
1. **Configure the location** in `config/locations.yaml`: `zipcode`, `store_details_url` (preferred) or ZIP search, optional `store_id`,
   and **`banner_must_contain`** (e.g. `["Roosevelt"]`): *all* tokens must appear in the header store banner on every page or the run fails.
   A location with no tokens cannot be verified and is refused.
2. **Local dry setup**: `pip install -r requirements.txt && playwright install chromium`
3. **Tests**: `PYTHONPATH=src python -m unittest discover -s tests -v`
4. **Live self-check (do this before anything else)**: `PYTHONPATH=src python -m marianos.cli doctor --location <id> [--url <category url>]`
   prints status/latency, hit counts for every selector, the store banner, the first parsed cards, and discovered subcategories, and saves
   `doctor_out/page.html` + `header.png`. Fix `config/selectors.yaml` until: banner matches, cards > 0, titles/prices/UPC populate, subcategories look right.
5. **First local run**: `PYTHONPATH=src python -m marianos.cli run --location <id>` (output under `./data/published/marianos-<id>/`).
6. **Validate the file independently**: `PYTHONPATH=src python -m marianos.check_output data/published/marianos-<id>/runs/<run>/dataset.json`

### Azure deployment
```bash
az group create -n rg-marianos -l centralus
az acr build -r <acr> -t marianos-scraper:1.0.0 .
az deployment group what-if -g rg-marianos -f infra/main.bicep -p image=<acr>.azurecr.io/marianos-scraper:1.0.0 acrName=<acr> locations='["<id>"]'
az deployment group create  -g rg-marianos -f infra/main.bicep -p image=... acrName=<acr> locations='["<id>"]'
az containerapp job start -g rg-marianos -n marianos-<id>      # observed fresh run
```
Schedule: `0 8 * * 2,5` UTC (Tue + Fri), parameter `cron`. Secrets (proxy only, if you are authorised to use one) are Bicep `@secure()` params, stored as Container Apps secrets and injected as
`PROXY_SERVER/PROXY_USERNAME/PROXY_PASSWORD`. Storage uses a managed identity (no keys). Nothing secret is in source or config.

## How it works
1. **Lock** `marianos-<id>` (blob lease renewed by a thread; auto-expires if the container dies) → overlapping runs for the same job are refused (exit 3).
2. **Select + verify store**, then every page fetched re-checks the header banner. Cookie store-id check if `store_id` is set. Any mismatch aborts the run (`StoreMismatch`); a mismatch also fails validation.
3. **Canaries**: product pages from the last good run (10 random, saved at publish) plus any configured in `locations.yaml` must still load with a title, a price and the right store, at start and end.
4. **Discover** subcategories per category (depth ≤ 2), plus the category page itself as a catch-all unit (processed last so subcategory labels win on dedupe). Coupons page is handled as its own listing type.
5. **Crawl** each unit: load page (lazy-scroll + "load more"), parse, checkpoint **after every page**; keep requesting `?page=N+1` until a page yields nothing new (does not trust a "next" selector).
6. **Assemble** → dedupe by UPC (else URL without query) → **validate** → **publish or reject** (below).

### Category-completeness detection
Every CSV category must produce units; a unit with zero products is accepted **only** if the page shows an explicit "no results" marker on a recognisable Mariano's page; otherwise it is a failure (a blocked page is not an empty category).
Units compare collected vs the site's declared "N results" (≥ 95%). Per-category raw yield must be ≥ 70% of the last successful run; total ≥ 80%. First run (no baseline) uses absolute minimums and flags `no_baseline_first_successful_run`.
Failed/incomplete units get one more pass before validation.

### Silent-blocking detection
HTTP 401/403/429 and challenge-page markers (Akamai/Incapsula/captcha text) → `BlockedError`: cooldown, retry, and after `max_blocks_per_run` the run stops and stays resumable. A 200 page without recognisable content is a `ShapeError`.
Further safeguards: canary products, per-category yield vs baseline, declared-total coverage, latency tracking (slow pages double pacing automatically; >25% slow pages fails validation), and field-completeness floors (title/url/image/price/UPC/weight).
**No stealth plugins, CAPTCHA solving or fingerprint spoofing are included.** If the site challenges you, the correct response is to stop and get authorisation, not to evade.

### How failed runs are prevented from replacing good data
Output is written to `published/<job>/runs/<run_id>/` and read back and hash-checked **before** the pointer `published/<job>/latest.json` is atomically overwritten. A run that fails validation
is written to `rejected/<job>/<run_id>/` (dataset + report for diagnosis) and `latest.json` is untouched. Crashes/interrupts never reach the publish step. Blob soft-delete (14 days) is a second safety net.

## Operation / maintenance / recovery
| Situation | What happens | What you do |
|---|---|---|
| Run published | exit 0 | nothing |
| Validation rejected | exit 2, old data intact | read `rejected/.../report.json` → `validation.issues`; fix selectors/pacing; rerun |
| Interrupted / blocked / crashed | exit 1, checkpoint kept (valid 36 h) | `az containerapp job start ...`: it **resumes the same run** and skips finished pages |
| Another run active | exit 3 | nothing (lease frees itself within 60 s of a crash) |
| Site layout changed | yields/completeness fail → rejected | `doctor`, edit `selectors.yaml`, rebuild image (`az acr build`) |
| Want to force a fresh run | | delete `state/<job>/<run_id>/` blobs or wait > 36 h |

Monitoring: JSON logs go to stdout → Log Analytics (`ContainerAppConsoleLogs_CL`): events `run_start, page_done, unit_status, blocked, retry, store_mismatch, canaries, run_final`. Add an Azure Monitor alert on failed job executions and on `run_final` with status ≠ published.
`python -m marianos.cli status --location <id>` shows the latest published pointer.

### Add a location
Append a block to `config/locations.yaml` (unique `id`, ZIP/store URL, `banner_must_contain`), rebuild the image, and add the id to the Bicep `locations` array. No code change.
### Add / change a category
Edit `config/categories.csv` (`Category (Auto)`, `URL`, `Scope`). Missing categories fail validation, so removing one is intentional. A `/savings/.../coupons` URL is treated as the coupons type.

## Output conventions (decisions to confirm with the contest owner)
- All values are strings; prices are plain decimals with 2 places (`"3.49"`), no `$`. Missing = `""`.
- `ppm` is the displayed text with whitespace collapsed (e.g. `$0.25/oz`), never calculated; empty if not displayed.
- `regular_price`/`sale_price`: struck-through price = regular, current = sale; otherwise only regular.
- `volume_deals_price` / `digital_deals_price` hold a price **only when explicitly displayed** (`$1.99 each`, `Must buy 4 at $1.99`, `2 for $5` → `5.00`). For multi-buy offers the displayed amount is the *bundle* price and the quantity is in the description. **Confirm this convention.**
- Digital = clip/activate/coupon wording or a coupon/clip element; loyalty-card wording alone stays volume. Promo text that is neither is not stored (the top unclassified strings are listed in each report for review).
- `store_brand` = `yes` when title/brand starts with a configured private-label name (`settings.yaml`), else `no`.
- Store fields come from the banner when exposed, else from `locations.yaml` (noted in the report). `zipcode` is the configured/verified store ZIP.
- `crawl_date` = UTC date the run started (kept for resumed runs). Dedupe: UPC, else URL without query; first (most specific) category wins.
- **Coupons category**: coupon cards are emitted as records (`category=Coupons`, text in `digital_deals_description`, no price/UPC) and are excluded from completeness stats. Confirm how the contest owner wants coupons represented.

## Estimated monthly operating cost (per location, estimates: verify with the Azure Pricing Calculator)
Assumes ~8.7 runs/month, ~3 h/run at 2 vCPU / 4 GiB (**runtime is a guess until the first live run**).
| Item | Estimate |
|---|---|
| Container Apps Job compute (≈188k vCPU-s, ≈376k GiB-s/month; subscription free grant ≈180k/360k) | ~$0–6 |
| Azure Container Registry (Basic) | ~$5 (shareable across scrapers) |
| Blob Storage (< 1 GB + transactions) | < $1 |
| Log Analytics (~0.1–0.3 GB/run) | ~$1–3 |
| **Total** | **≈ $7–15** |
| Paid proxies / third-party APIs | **None included or required by default.** If Mariano's blocks datacenter IPs and you are authorised to use a proxy, add that vendor's price (not estimated here). |

## Compliance and IP
Kroger-family site terms may restrict automated access. Confirm authorisation before running at scale. The scraper paces requests, identifies as a normal browser session, and makes no attempt to bypass access controls.
No telemetry, no remote kill-switch, no embedded secrets; the only network calls are to marianos.com and your Azure storage (Playwright browsers are downloaded at image build time from Microsoft's CDN). Source is delivered unencrypted.
