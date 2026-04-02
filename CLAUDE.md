# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TaxOpt is a Chinese personal income tax optimization and calculation tool. Given a fixed total annual income, it finds the optimal split between monthly salary and year-end bonus to maximize after-tax take-home pay, following 2025 Chinese tax law.

## Commands

### Run the API server
```bash
uvicorn api:app --reload --host 127.0.0.1 --port 8001
```

### Run tests
```bash
pytest tests/
pytest tests/test_calculator.py          # Core logic tests only
pytest tests/test_api.py                 # API endpoint tests only
pytest tests/test_calculator.py -k "optimize"  # Single test by keyword
```

### Run CLI
```bash
python main.py optimize -t 500000                  # Find optimal split for 500k total
python main.py salary --total 500000 --monthly 20000
python main.py bonus --total 500000 --bonus 100000
python main.py both --monthly 20000 --bonus 100000
python main.py --list-presets                      # Show 42 city presets
python main.py --preset jiangsu-suzhou optimize -t 500000
```

### Dependencies (for web stack only)
```bash
pip install fastapi uvicorn pydantic pytest httpx
```
The CLI uses only Python standard library (3.8+).

## Architecture

### Layered Structure

```
web/index.html (Alpine.js + Tailwind + Chart.js)
      │
api.py (FastAPI) — REST wrapper, serves static frontend
      │
main.py — Core engine: TaxConfig, TaxCalculator, TaxOptimizer
      │
presets/*.json + config.json — 42 city configs
```

### Core Engine (`main.py`)

- **`TaxConfig`** (dataclass): All tax parameters — basic deduction, social security rates/limits, housing fund rates/limits, 6 types of special deductions, annual lump-sum deductions.
- **`TaxCalculator`**: Computes monthly insurance, housing fund, progressive taxes, 12-month breakdowns, and bonus taxes. Key method: `monthly_details()` returns per-month cumulative withholding.
- **`TaxOptimizer`**: Exhaustive search over all monthly salary values (in configurable steps) to find the split that maximizes net take-home or net + provident fund.
- **Tax brackets**: `COMPREHENSIVE_BRACKETS` (7 progressive rates for annual salary income) and `BONUS_BRACKETS_ANNUAL` (year-end bonus, taxed separately).

### Tax Calculation Flow

1. **Insurance base** = clamp(salary, base_min, base_limit)
2. **Monthly deductions** = pension (8%) + medical (2%) + unemployment (0.5%) + employee housing fund
3. **Annual taxable income** = salary×12 − 60000 − special_deductions − deductions×12
4. **Comprehensive tax** = progressive tax on annual taxable income
5. **Bonus tax** = separate progressive tax on year-end bonus (single-rate method)
6. **Net take-home** = total_income − comprehensive_tax − bonus_tax − personal insurance×12

### API Layer (`api.py`)

Thin FastAPI wrapper. `_build_tax_config()` resolves either a `preset_slug` or custom `TaxConfigInput` into a `TaxConfig`, then delegates to `TaxCalculator`/`TaxOptimizer`. Four modes: `optimize`, `salary`, `bonus`, `both`.

### Configuration

All 42 city presets are in `presets/<province-pinyin>-<city-pinyin>.json`. The default config is `config.json` (浙江/杭州, 2025). Key policy note: social security uses calendar year (Jan–Dec) while housing fund uses fiscal year (Jul–Jun); the tool uses a single fixed parameter set as an approximation.

### Objective Options

- `cash` — maximize nominal after-tax take-home
- `cash_plus_provident_fund` — maximize take-home + both employee and employer housing fund contributions
