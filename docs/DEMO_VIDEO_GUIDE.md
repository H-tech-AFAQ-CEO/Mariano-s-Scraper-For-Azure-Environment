# Demo Video Guide — Mariano's Scraper (Contest Entry #34)

Use this document as the script and shot list for your demonstration video to the contest holder.

---

## 1. Opening / Introduction (0:00–0:45)

**On screen:** Your face / webcam, then screen share of the GitHub repo.

**Say:**

> "Hi, I'm Zulqarnain Ahmad, collaborating with my team leader Afaq Ahmad. We're submitting entry #34 for the Mariano's scraper contest. This is a production-ready, location-specific grocery catalog scraper built for Microsoft Azure. It's written in Python with Playwright, deployed as an Azure Container Apps Job, and designed to run twice per week without manual intervention.

> You can find the full source at github.com/H-tech-AFAQ-CEO/Mariano-s-Scraper-For-Azure-Environment, revision 1f043f2. My GitHub is github.com/H-tech-AFAQ-CEO and my team leader's profile is github.com/H-tech-AFAQ-CEO with Freelancer profile freelancer.com/u/AFAQCEO. My Freelancer profile is freelancer.com/u/zulqarnaina43.

> Beyond this project, we've built similar scraping and automation tools — you can see my Play Store portfolio at [INSERT YOUR PLAY STORE DEVELOPER LINK HERE] — and we're available for more projects of this kind."

---

## 2. What This Project Is (0:45–1:30)

**On screen:** README.md and project file tree.

**Say:**

> "This scraper collects location-specific products, prices, measurements, promotions, categories, and subcategories from marianos.com, a Kroger-owned chain.

> Key facts:
> - Scrapes each configured location twice per week via Azure cron.
> - Supports multiple locations without code changes — just add a block to config/locations.yaml.
> - Processes every category in Marianos_Category_URLs.csv, including subcategories to depth 2.
> - Outputs exactly 22 JSON fields in the required order: zipcode through crawl_date.
> - Missing values are empty strings, never nulls.
> - gupc and unit_price are intentionally empty — they're calculated by the downstream pipeline, not invented here.
> - PPM (price per measure, like $0.25/oz) is scraped directly from the site, never calculated.
> - Volume deals and digital deals are distinguished and the retailer's exact wording is preserved.
> - Products with approximate weight ('approx', 'approximately', '~', etc.) are excluded.
> - Store selection is verified on every page; a mismatch aborts the run.
> - Duplicates are detected by UPC (else URL). Failed, thin, or blocked runs never replace the last good dataset."

---

## 3. How It Works — Architecture Walkthrough (1:30–3:00)

**On screen:** Open `docs/WALKTHROUGH.md`, `src/marianos/runner.py`, `src/marianos/driver.py`, `src/marianos/extract.py`, `src/marianos/validate.py`, `src/marianos/storage.py`, `infra/main.bicep`.

**Say:**

> "Here's the architecture, step by step.

> **One. Lock.** Before anything runs, the job acquires a blob lease for `marianos-<location-id>`. If another run is already active, the new run exits with code 3 — overlapping runs are refused. The lease auto-expires if the container crashes, so no manual unlock is needed.

> **Two. Select and verify store.** Playwright Chromium opens the Mariano's store finder, selects the configured store by details URL or ZIP search, then reads the header banner. Every configured `banner_must_contain` token must appear on every page, or the run fails with `StoreMismatch`. A store-selected screenshot is saved as evidence.

> **Three. Canaries.** Ten product pages from the last good run (plus any manually configured canaries) are fetched at start and end. Each must load with a title and a price, or the run is flagged.

> **Four. Discover.** For each category in categories.csv, the scraper walks subcategory links (depth ≤ 2) and builds a crawl plan. The category root is processed last as a catch-all, so subcategory labels win on dedupe.

> **Five. Crawl.** Each unit is crawled page by page with lazy scrolling and 'load more' clicking. After every page, a checkpoint is written to Azure Blob state storage. Pagination continues until a page yields nothing new — it doesn't trust a 'next' button. Controlled pacing (2.5–6s random delays), retries with backoff, and adaptive slow-page backoff keep the run polite and stable.

> **Six. Assemble and validate.** Records are assembled, deduplicated by UPC (else URL without query), then validated. Validation checks: store verification events, no missing categories, no failed units, yield vs baseline (≥70% per category, ≥80% total), schema field order, no nulls, gupc/unit_price empty, no approx-weight records, completeness floors (title 99.5%, URL 99.5%, image 95%, price 98%, UPC 90%, weight 70%), canary pass rate (≥80%), and abnormal latency (<25% slow pages).

> **Seven. Publish or reject.** If validation passes, the dataset and report are written to `published/<job>/runs/<run_id>/`, read back and hash-checked, and only then is `latest.json` atomically overwritten. If validation fails, outputs go to `rejected/<job>/<run_id>/` and `latest.json` is left untouched — the last good data is never overwritten by a bad run.

> **Azure deployment:** infra/main.bicep provisions one Container Apps Job per location with twice-weekly cron (Tue/Fri 08:00 UTC), Azure Blob Storage with 14-day soft-delete, managed identity (no keys), Log Analytics, and a failure alert rule. Secrets (proxy credentials, if authorised) come only from Azure Key Vault or Container Apps secrets — never from source code."

---

## 4. Live Demo Steps (3:00–5:00)

**On screen:** Terminal, `config/`, `src/`, repo.

**Say and show:**

> "Now let me show you the actual commands.

> **Setup:**
> `pip install -r requirements.txt`
> `python -m playwright install chromium`

> **Tests (offline, all pass):**
> `PYTHONPATH=src python -m unittest discover -s tests -v`
> [Show 15/15 OK]

> **Doctor (live selector tuning):**
> `PYTHONPATH=src python -m marianos.cli doctor --location <your-store-id>`
> [Show page.html and header.png saved, selector hit counts, parsed cards, subcategories]

> **Verify store:**
> `PYTHONPATH=src python -m marianos.cli verify-store --location <your-store-id>`

> **Run:**
> `PYTHONPATH=src python -m marianos.cli run --location <your-store-id>`
> [Show JSON logs: run_start, page_done, unit_status, canaries, run_final]

> **Validate output:**
> `PYTHONPATH=src python -m marianos.check_output data/published/marianos-<id>/runs/<run>/dataset.json`
> [Show records count, by_category, completeness, duplicates]

> **Status:**
> `PYTHONPATH=src python -m marianos.cli status --location <your-store-id>`

> **Add a location:** Edit `config/locations.yaml` — no code change. Rebuild image, add id to Bicep `locations` array.

> **Add a category:** Edit `config/categories.csv` — no code change."

---

## 5. What Is Complete vs. Remaining (5:00–5:45)

**On screen:** README.md "what has and has not been verified" table, ACCEPTANCE_REPORT.md.

**Say:**

> "**Complete and verified offline:**
> - All 15 unit and end-to-end tests pass.
> - 22-field JSON schema, empty-string policy, gupc/unit_price empty, no remarks/gupc14.
> - Volume vs digital deal classification for every brief example.
> - Approx-weight exclusion, dedupe, store mismatch abort, failed-run protection, lock overlap, interruption resume.
> - Full Azure infrastructure defined in Bicep.
> - Documentation: README, walkthrough, contest evidence mapping.

> **Remaining — requires live execution from an authorised network:**
> - Live CSS selector tuning against marianos.com (the site is blocked at the network layer from this build environment).
> - Real store configuration in config/locations.yaml with banner_must_contain tokens.
> - Observed live run producing ≥500 valid products, logs, and run report.
> - Azure deployment via `az acr build` and `infra/main.bicep`.

> I will not fabricate live data, reports, or Azure evidence. Once live access is available, all of the above can be executed and submitted for review."

---

## 6. About Me / My Team / Why Hire Us (5:45–6:45)

**On screen:** Your GitHub profile, Freelancer profiles, Play Store link.

**Say:**

> "I'm Zulqarnain Ahmad, and I built this scraper in collaboration with my team leader Afaq Ahmad.

> - Zulqarnain Ahmad: freelancer.com/u/zulqarnaina43
> - Afaq Ahmad (Team leader): github.com/H-tech-AFAQ-CEO · freelancer.com/u/AFAQCEO
> - GitHub repo: github.com/H-tech-AFAQ-CEO/Mariano-s-Scraper-For-Azure-Environment
> - Play Store portfolio: [INSERT YOUR PLAY STORE DEVELOPER LINK HERE]

> I've checked your profile — you have fantastic reviews from other sellers and workers, and you've developed apps yourself. I can tell you we operate at that same standard: clean, documented, test-covered code; no hidden telemetry; no remote kill-switch; no undisclosed dependencies; secrets never in source. Everything here is unencrypted and ready for transfer.

> We're not just scraper builders — we're full-stack automation engineers. If you have more projects of this kind — grocery, retail, e-commerce, price monitoring, or any data extraction on Azure or elsewhere — we'd welcome the opportunity to work with you."

---

## 7. Closing / Call to Action (6:45–7:00)

**On screen:** Repo URL, your contact info.

**Say:**

> "The full source code, configuration, infrastructure, tests, and documentation are all in the repository. I'm ready to complete the live run and Azure deployment from an authorised network as soon as access is available. Thank you for reviewing entry #34 — I look forward to working with you."

---

## Video Production Tips

| Segment | Visual | Audio Tone |
|---------|--------|------------|
| Intro | Webcam + GitHub repo | Friendly, confident |
| What it is | README + file tree | Clear, factual |
| Architecture | Code files, diagrams | Technical but paced |
| Live demo | Terminal commands | Step-by-step, deliberate |
| Complete vs remaining | README table | Honest, transparent |
| About us | Profiles, repo | Professional, capable |
| Close | Repo URL + contact | Polite, call to action |

**Total target length:** 6–7 minutes.  
**Aspect ratio:** 16:9, 1080p.  
**Narration:** Clear English, moderate pace, pause between major sections.

---

## Placeholders to Fill Before Recording

- `[INSERT YOUR PLAY STORE DEVELOPER LINK HERE]` — your Google Play Console developer URL
- `<your-store-id>` — the Mariano's location id you configure in `config/locations.yaml`
- Exact live run outputs (records count, runtime, category counts) — fill in after the observed run

---

**File location:** `docs/DEMO_VIDEO_GUIDE.md`  
**Source revision:** `1f043f20a04b10ff3d9caa56541aee924f794cfd`  
**Repo:** `https://github.com/H-tech-AFAQ-CEO/Mariano-s-Scraper-For-Azure-Environment.git`