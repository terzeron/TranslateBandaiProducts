# Repository Guidelines

## Project Structure & Modules
- `smart_incremental_mirror.py`: Incremental site mirroring with SQLite metadata per site (`smart_mirror_<site>.db`).
- `extract_site_products.py`: Parse mirrored content into structured product lists (`*_products.txt`).
- `convert_bandai_product_ja2ko.py`: Bandai manual HTML → KO name mapping and HTML generation.
- `run.sh` / `mirror_site.sh`: Orchestration for end‑to‑end and per‑site runs.
- Mirrors: `www.dalong.net/`, `manual.bandai-hobby.net/`, `kr.gundam.info/`, `gcd/`.
- Data: `mapping/` (JA↔KO mappings), logs (`*.log`), caches/DBs (`smart_mirror_*.db`).

## Build, Test, Run
- End‑to‑end: `./run.sh` — mirrors, extracts, translates, and emits HTML/outputs.
- Per‑site: `./mirror_site.sh <dalong|bandai-hobby|gundaminfo|gcd> -c -e` — mirror (-c) then extract (-e).
- Direct mirror: `python3 smart_incremental_mirror.py <base_url> <out_dir> <max_pages> <site>`
  Example: `python3 smart_incremental_mirror.py https://kr.gundam.info kr.gundam.info 2000 gundaminfo`
- Direct extract: `python3 extract_site_products.py <site_dir> <out_file> <site>`
  Example: `python3 extract_site_products.py kr.gundam.info gundaminfo_products.txt gundaminfo`

## Coding Style & Conventions
- Python 3.8+, 4‑space indent, UTF‑8 files.
- Names: files/functions `snake_case`, classes `CapWords`; module‑level constants `UPPER_SNAKE`.
- Type hints where practical; prefer pure, testable helpers.
- Logging: use `logging` (no print) with informative, rate‑limited messages.
- I/O paths under site roots; avoid hardcoding absolute paths.

## Testing Guidelines
- Smoke tests: run `./mirror_site.sh gundaminfo -c -e`, then verify `kr.gundam.info/` and `gundaminfo_products.txt` updated.
- Determinism: re‑run should skip unchanged files (check logs for “건너뛰기”).
- Spot‑check extracted fields (name/brand/scale) for a few entries.

## Commit & PR Guidelines
- Commit style: Conventional Commits preferred (e.g., `feat:`, `fix:`, `refactor:`); Korean or English OK. Use present tense and concise scope.
- Include: purpose, affected scripts, commands run, before/after samples (paths or snippet), and performance impact (URLs/sec, skipped vs downloaded) when relevant.
- PRs: link issues, describe site(s) impacted, attach example outputs/log excerpts; keep changes focused.

## Security & Ops Tips
- Be gentle to origins: keep built‑in delays; avoid tight loops and excessive retries.
- Do not commit large DBs/logs unintentionally; respect `.gitignore`.
- Handle PDFs/binaries in binary mode; never embed secrets in code or logs.
