# Contest Evidence Mapping

This document maps each of the 10 required contest evidence items to the corresponding project files, code modules, and output artifacts.

| Required Evidence Item | Implementation & Location |
|---|---|
| **1. Structured JSON using all required fields** | [schema.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/schema.py) (`FIELDS` definition, exact 22 fields in order, empty string default, `gupc` and `unit_price` empty). |
| **2. Total unique count, runtime and count by category** | [report.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/report.py) (`counts` object in `report.json`). |
| **3. Duplicate count and field-completeness statistics** | [validate.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/validate.py) (`completeness()` and duplicate check logic). |
| **4. Examples of PPM, volume deals, digital deals and products without deals** | [report.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/report.py) (`examples` dictionary in `report.json`). |
| **5. Evidence that the correct store was selected** | [guards.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/guards.py) and [runner.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/runner.py) (`store_verification` and evidence screenshot in `report.json`). |
| **6. Explanation of category-completeness and silent-blocking detection** | [README.md](file:///C:/Users/Afaq/Desktop/marianos-scraper/README.md) and [validate.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/validate.py). |
| **7. Explanation of how failed runs are prevented from replacing good data** | [runner.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/runner.py) (`_finish()` validates before atomic pointer update; rejected runs stored separately). |
| **8. Architecture, technologies and all paid proxies, APIs or services** | [README.md](file:///C:/Users/Afaq/Desktop/marianos-scraper/README.md) (Python 3.12, Playwright, Azure Container Apps Jobs, Azure Blob Storage, managed identity, zero paid proxies by default). |
| **9. Estimated monthly operating cost** | [README.md](file:///C:/Users/Afaq/Desktop/marianos-scraper/README.md) (estimated $7–15/month per location based on Azure pricing). |
| **10. Evidence that the scraper generated the submitted data** | [report.py](file:///C:/Users/Afaq/Desktop/marianos-scraper/src/marianos/report.py) (`proof` object containing dataset SHA-256 hash, host, Python version, platform, and config hashes). |
