# Mariano's Connectivity & Store-Response Test Plan

## Purpose
Verify network connectivity to marianos.com, select and verify the correct Mariano's store (Vernon Hills, IL), and confirm live page responses before the 500-product live demonstration.

## Prerequisites (must be in place before running)
1. **Network access** where `https://www.marianos.com` loads normally (this build environment is blocked at TCP/TLS).
2. **Store configured** in `config/locations.yaml` (Vernon Hills store block added below).
3. **Python 3.12 + Playwright Chromium** installed (`pip install -r requirements.txt && python -m playwright install chromium`).

## Step 1 — Connectivity probe (run now from authorized network)

```powershell
# Test HTTPS connectivity to marianos.com
curl -vI https://www.marianos.com/

# Expected: HTTP 200, TLS handshake succeeds, HTML headers returned
# Observed from this build environment: RemoteDisconnected / ERR_CONNECTION_RESET
```

**Success criteria:** HTTP 200 response received, TLS certificate valid, no connection reset.

## Step 2 — Store configuration

The Vernon Hills store block has been added to `config/locations.yaml`:

```yaml
- id: vernon-hills
  enabled: true
  zipcode: "60061"
  store_id: ""
  store_details_url: ""
  store_name: "Mariano's Vernon Hills"
  store_location: "1720 N Milwaukee Ave, Vernon Hills, IL 60061"
  store_logo: ""
  banner_must_contain: ["Vernon Hills", "60061"]
  canaries: []
```

**Note:** `banner_must_contain` tokens must ALL appear in the header store banner on every page. If the live banner differs, update these tokens from `doctor` output. A location with empty `banner_must_contain` is refused by design.

## Step 3 — Doctor self-check (requires network access)

```powershell
$env:PYTHONPATH="src"; python -m marianos.cli doctor --location vernon-hills --url https://www.marianos.com/d/produce
```

**What this does:**
- Selects the Vernon Hills store via the store finder
- Fetches the Produce category page
- Saves `doctor_out/page.html` (full HTML) and `doctor_out/header.png` (top banner strip)
- Prints: status, latency, HTML bytes, selector hit counts (store_banner, card, title, size, price_current, price_original, ppm, promo, promo_digital, next_page, subcategory_links)
- Parses listing: banner, card count, declared_total, has_next, first 3 cards as JSON
- Discovers subcategories

**Success criteria:**
- `status=200`, `html_bytes > 4000`
- `banner` contains "Vernon Hills" and "60061"
- `cards > 0` (product cards parsed)
- `title`, `price_current`, `ppm` selectors hit > 0
- `subcategories` discovered (non-empty list)

**If cards = 0:** Update `config/selectors.yaml` card/title/size/price_current/ppm selectors based on `doctor_out/page.html`, then re-run.

## Step 4 — Store verification (requires network access)

```powershell
$env:PYTHONPATH="src"; python -m marianos.cli verify-store --location vernon-hills
```

**What this does:**
- Selects the store
- Fetches the home page
- Parses the header banner and logo
- Checks `banner_must_contain` tokens against the live banner
- Checks `store_id` against the store cookie (if configured)

**Success criteria:** `Store verification: PASSED`

## Step 5 — Category discovery (requires network access)

```powershell
$env:PYTHONPATH="src"; python -m marianos.cli discover --location vernon-hills
```

**What this does:** Prints the category → subcategory → URL tree without scraping products.

**Success criteria:** All 28 categories from `config/categories.csv` appear with discovered subcategory URLs.

## Step 6 — Live run (requires Steps 1-5 to pass)

```powershell
$env:PYTHONPATH="src"; python -m marianos.cli run --location vernon-hills
```

**What this does:** Full crawl of all categories/subcategories with checkpoints, validation, and atomic publish.

**Success criteria:** `run_final` status = `published`, records >= 500, no validation issues.

## Step 7 — Independent output validation

```powershell
$env:PYTHONPATH="src"; python -m marianos.check_output data/published/marianos-vernon-hills/runs/<run-id>/dataset.json
```

**Success criteria:** `fields: OK`, `violations: none`, `duplicates: 0`, `records >= 500`.

---

## Observed Failure (from this build environment, documented)

| Field | Value |
|-------|-------|
| Error | `RemoteDisconnected` / `ERR_CONNECTION_RESET` |
| Endpoint | `https://www.marianos.com/` |
| Method | GET |
| HTTP status | None (connection fails before response) |
| Failure type | Network / TLS connection blocked |
| Response body received | No |
| Can run now? | No — requires authorized network where marianos.com is reachable |

## Proxy / Environment Dependency

- **Residential proxy:** Not requested, not approved, not needed by design. Standard Playwright Chromium with normal browser user-agent and controlled pacing (2.5–6s delays). If marianos.com blocks datacenter IPs after live access is granted, a residential proxy would be a separate client-approved add-on.
- **Broad Azure access:** Not requested. Azure deployment (`infra/main.bicep`) is a separate future milestone requiring only resource-scoped permissions (ACR push, Container Apps Job, Blob Storage write).
- **Initial cost ceiling:** ~$7–15/month per location (Azure), proxy not included.

## Next Delivery Date

Within 2–3 business days after network access to marianos.com and Vernon Hills store confirmation are provided.
