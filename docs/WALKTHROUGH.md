# Mariano's Scraper Walkthrough & Operational Guide

This document outlines the step-by-step walkthrough for deploying, operating, verifying, and maintaining the Mariano's catalog scraper on Python 3.12, Playwright, and Azure Container Apps Jobs.

## 1. Architecture Overview
- **Core Components**:
  - [cli.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/cli.py): Entry point supporting `run`, `status`, `doctor`, `discover`, `verify-store`, and `reset`.
  - [runner.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/runner.py): Orchestrates locking, store selection and verification, canary checks, category/subcategory discovery, paged crawling with checkpoints, re-crawling of failed units, validation, and atomic publishing.
  - [driver.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/driver.py): Standard Playwright Chromium driver with zero stealth/evasion plugins by design.
  - [extract.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/extract.py): Pure-function DOM extraction using CSS selector lists from configuration with structural fallbacks.
  - [validate.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/validate.py): Enforces completeness floors, yield comparisons against last baseline, canary pass rates, and schema rules.
  - [storage.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/storage.py): Abstraction layer supporting local directory store (`LocalStorage`) and Azure Blob Storage (`AzureBlobStorage`) with lease locking.

## 2. Step-by-Step Operational Script

### Step A: Local Environment Setup & Tests
```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
$env:PYTHONPATH="src"; python -m unittest discover -s tests -v
```

### Step B: Doctor Self-Check & Subcategory Discovery
- **Doctor check**:
  ```bash
  python -m marianos.cli doctor --location chicago-roosevelt
  ```
  Saves `doctor_out/page.html` and `doctor_out/header.png` for visual inspection and selector tuning in `config/selectors.yaml`.
- **Category Discovery**:
  ```bash
  python -m marianos.cli discover --location chicago-roosevelt
  ```
  Prints the discovered category -> subcategory -> URL tree without scraping products.

### Step C: Store Verification
```bash
python -m marianos.cli verify-store --location chicago-roosevelt
```
Validates that the selected store banner matches `banner_must_contain` in `config/locations.yaml`.

### Step D: Running a Demo or Production Scrape
- **Demo Run (never touches published output)**:
  ```bash
  python -m marianos.cli run --location chicago-roosevelt --demo --only-category Produce
  ```
- **Production Run**:
  ```bash
  python -m marianos.cli run --location chicago-roosevelt
  ```

### Step E: Handling Interruption & Recovery
If a run is interrupted or blocked:
1. The checkpoint is saved in `state/<job>/<run_id>/`.
2. Re-running the command automatically detects the valid unfinished run (within `max_age_hours`), resumes the same `run_id`, skips finished pages, and continues.
3. To abandon an unfinished run:
   ```bash
   python -m marianos.cli reset --location chicago-roosevelt --yes
   ```

### Step F: Failure Protection
If validation fails (yield drop, missing category, schema violation), the run outputs to `rejected/<job>/<run_id>/` and `published/<job>/latest.json` remains **byte-identical** to the last good published dataset.
