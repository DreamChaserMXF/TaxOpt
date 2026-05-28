import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import (  # noqa: E402
    PRESETS_DIR,
    TaxCalculator,
    TaxConfig,
    TaxOptimizer,
    adaptive_search_step,
    load_tax_config_from_json,
    result_from_salary_bonus_split,
    validate_tax_config,
)


ROOT = Path(__file__).resolve().parent.parent
MINIPROGRAM_UTILS = ROOT / "miniprogram" / "utils"

MINIMAL_CONFIG = {
    "basic_deduction": 60000,
    "pension_rate": 0.0,
    "medical_rate": 0.0,
    "unemployment_rate": 0.0,
    "housing_fund_employee_rate": 0.0,
    "housing_fund_employer_rate": 0.0,
    "social_security_base_min": 0,
    "social_security_base_limit": 0,
    "housing_fund_base_min": 0,
    "housing_fund_base_limit": 0,
    "children_education": 0,
    "continuing_education": 0,
    "serious_illness": 0,
    "housing_loan_interest": 0,
    "housing_rent": 0,
    "elderly_support": 0,
    "annual_additional_deduction": 0,
}

FULL_CONFIG = {
    "basic_deduction": 60000,
    "pension_rate": 0.08,
    "medical_rate": 0.02,
    "unemployment_rate": 0.005,
    "housing_fund_employee_rate": 0.12,
    "housing_fund_employer_rate": 0.12,
    "social_security_base_min": 0,
    "social_security_base_limit": 0,
    "housing_fund_base_min": 0,
    "housing_fund_base_limit": 0,
    "children_education": 0,
    "continuing_education": 0,
    "serious_illness": 0,
    "housing_loan_interest": 0,
    "housing_rent": 0,
    "elderly_support": 0,
    "annual_additional_deduction": 0,
}


def expected_result(payload):
    if payload.get("preset_slug"):
        cfg = load_tax_config_from_json(PRESETS_DIR / f"{payload['preset_slug']}.json")
    else:
        cfg = TaxConfig(**payload["config"])

    validate_tax_config(cfg)
    calc = TaxCalculator(cfg)

    if payload["mode"] == "optimize":
        total = payload["total"]
        return TaxOptimizer(calc).optimize(
            total,
            adaptive_search_step(total),
            objective=payload.get("objective", "cash"),
            extra_income=payload.get("extra_income", 0.0),
            stock_grants=payload.get("stock_grants", []),
        )

    monthly = payload["monthly"]
    bonus = payload["bonus"]
    return result_from_salary_bonus_split(
        calc,
        monthly * 12 + bonus,
        monthly,
        bonus,
        extra_income=payload.get("extra_income", 0.0),
        stock_grants=payload.get("stock_grants", []),
    )


def assert_deep_close(actual, expected, path="result"):
    if isinstance(expected, dict):
        assert set(actual.keys()) == set(expected.keys()), path
        for key, expected_value in expected.items():
            assert_deep_close(actual[key], expected_value, f"{path}.{key}")
        return

    if isinstance(expected, list):
        assert len(actual) == len(expected), path
        for index, expected_value in enumerate(expected):
            assert_deep_close(actual[index], expected_value, f"{path}[{index}]")
        return

    if isinstance(expected, (int, float)):
        assert actual == pytest.approx(expected, abs=0.01), path
        return

    assert actual == expected, path


def run_miniprogram_api(tmp_path, payloads):
    if shutil.which("node") is None:
        pytest.skip("node is required for miniprogram offline parity tests")

    for source_name, target_name in (
        ("tax-core.js", "tax-core.mjs"),
        ("presets-data.js", "presets-data.mjs"),
        ("api.js", "api.mjs"),
    ):
        source = (MINIPROGRAM_UTILS / source_name).read_text(encoding="utf-8")
        source = source.replace("./tax-core.js", "./tax-core.mjs")
        source = source.replace("./presets-data.js", "./presets-data.mjs")
        (tmp_path / target_name).write_text(source, encoding="utf-8")

    runner = tmp_path / "runner.mjs"
    runner.write_text(
        """
import { readFileSync } from 'node:fs'
import { api } from './api.mjs'

const input = JSON.parse(readFileSync(0, 'utf8'))
const results = []
for (const payload of input.payloads) {
  results.push(await api.calculate(payload))
}
const presets = await api.getPresets()
const hangzhou = await api.getPreset('zhejiang-hangzhou')
console.log(JSON.stringify({
  results,
  presetsCount: presets.length,
  firstPreset: presets[0],
  hangzhou,
}))
""".strip(),
        encoding="utf-8",
    )

    completed = subprocess.run(
        ["node", str(runner)],
        input=json.dumps({"payloads": payloads}, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def test_miniprogram_calculator_matches_python_core(tmp_path):
    payloads = [
        {
            "mode": "calc",
            "monthly": 10000,
            "bonus": 0,
            "config": MINIMAL_CONFIG,
        },
        {
            "mode": "calc",
            "monthly": 20000,
            "bonus": 60000,
            "extra_income": 20000,
            "stock_grants": [30000, 10000],
            "config": FULL_CONFIG,
        },
        {
            "mode": "optimize",
            "total": 300000,
            "objective": "cash",
            "config": FULL_CONFIG,
        },
        {
            "mode": "optimize",
            "total": 860000,
            "objective": "cash_plus_provident_fund",
            "extra_income": 60000,
            "stock_grants": [30000, 120000],
            "preset_slug": "zhejiang-hangzhou",
        },
        {
            "mode": "calc",
            "monthly": 35000,
            "bonus": 144000,
            "preset_slug": "shanghai-shanghai",
        },
    ]

    actual = run_miniprogram_api(tmp_path, payloads)
    expected = [expected_result(payload) for payload in payloads]

    for index, expected_item in enumerate(expected):
        assert_deep_close(actual["results"][index], expected_item, f"results[{index}]")


def test_miniprogram_presets_are_available_offline(tmp_path):
    actual = run_miniprogram_api(tmp_path, [])

    assert actual["presetsCount"] == len(list(PRESETS_DIR.glob("*.json")))
    assert actual["firstPreset"] == {
        "slug": "anhui-hefei",
        "label": "安徽 · 合肥",
        "province": "安徽",
    }
    assert actual["hangzhou"]["social_security_base_min"] == pytest.approx(4986.0)
    assert actual["hangzhou"]["housing_fund_employee_rate"] == pytest.approx(0.12)


def test_miniprogram_api_does_not_depend_on_server_requests():
    source = (MINIPROGRAM_UTILS / "api.js").read_text(encoding="utf-8")

    assert "uni.request" not in source
    assert "BASE_URL" not in source
    assert "127.0.0.1" not in source
