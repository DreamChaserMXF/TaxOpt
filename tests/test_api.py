"""
API 接口测试。

依赖：pip install fastapi httpx pytest
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from api import app

client = TestClient(app)

# ──────────────────────────────────────────────
# 公共常量
# ──────────────────────────────────────────────

CARD_FIELDS = [
    "annual_salary",
    "bonus",
    "net_take_home",
    "annual_provident_fund",
    "net_take_home_including_provident_fund",
    "total_tax",
    "effective_tax_rate",
    "annual_insurance",
    "effective_burden_rate",
]

# 零社保零公积金配置
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

# 标准费率，无基数限制
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


# ──────────────────────────────────────────────
# GET /api/presets
# ──────────────────────────────────────────────

class TestPresetsListEndpoint:
    def test_status_200(self):
        r = client.get("/api/presets")
        assert r.status_code == 200

    def test_returns_list(self):
        data = client.get("/api/presets").json()
        assert isinstance(data, list)

    def test_at_least_42_presets(self):
        data = client.get("/api/presets").json()
        assert len(data) >= 42

    def test_each_item_has_slug_and_label(self):
        data = client.get("/api/presets").json()
        for item in data:
            assert "slug" in item, f"缺少 slug：{item}"
            assert "label" in item, f"缺少 label：{item}"

    def test_slug_is_nonempty_string(self):
        data = client.get("/api/presets").json()
        for item in data:
            assert isinstance(item["slug"], str) and item["slug"]

    def test_known_slugs_present(self):
        """几个已知城市预设必须存在。"""
        slugs = {item["slug"] for item in client.get("/api/presets").json()}
        for expected in ["zhejiang-hangzhou", "beijing-beijing", "shanghai-shanghai"]:
            assert expected in slugs, f"未找到预设：{expected}"


# ──────────────────────────────────────────────
# GET /api/presets/{slug}
# ──────────────────────────────────────────────

class TestPresetDetailEndpoint:
    def test_hangzhou_status_200(self):
        r = client.get("/api/presets/zhejiang-hangzhou")
        assert r.status_code == 200

    def test_hangzhou_ss_base_min(self):
        data = client.get("/api/presets/zhejiang-hangzhou").json()
        assert data["social_security_base_min"] == pytest.approx(4986.0)

    def test_hangzhou_ss_base_limit(self):
        data = client.get("/api/presets/zhejiang-hangzhou").json()
        assert data["social_security_base_limit"] == pytest.approx(25299.0)

    def test_hangzhou_hf_rate(self):
        data = client.get("/api/presets/zhejiang-hangzhou").json()
        assert data["housing_fund_employee_rate"] == pytest.approx(0.12)

    def test_shanghai_hf_rate_is_7_percent(self):
        """上海公积金比例为 7%，非全国常见的 12%。"""
        data = client.get("/api/presets/shanghai-shanghai").json()
        assert data["housing_fund_employee_rate"] == pytest.approx(0.07)

    def test_unknown_preset_returns_404(self):
        r = client.get("/api/presets/nonexistent-city-xyz")
        assert r.status_code == 404

    def test_response_contains_all_taxconfig_fields(self):
        """预设详情应包含 TaxConfig 的全部 17 个字段。"""
        expected_fields = {
            "basic_deduction",
            "social_security_base_min", "social_security_base_limit",
            "pension_rate", "medical_rate", "unemployment_rate",
            "housing_fund_base_min", "housing_fund_base_limit",
            "housing_fund_employee_rate", "housing_fund_employer_rate",
            "children_education", "continuing_education", "serious_illness",
            "housing_loan_interest", "housing_rent", "elderly_support",
            "annual_additional_deduction",
        }
        data = client.get("/api/presets/zhejiang-hangzhou").json()
        assert expected_fields.issubset(data.keys())


# ──────────────────────────────────────────────
# POST /api/calculate — 数值正确性
# ──────────────────────────────────────────────

class TestCalculateNumerics:
    """每个场景的期望值均经手工推导，与 test_calculator.py 中的场景对应。"""

    def test_salary_mode_no_ss_total_tax(self):
        """
        场景 A：salary 模式，月薪 10000，无社保。
        tax = 60000 × 10% − 2520 = 3480
        """
        r = client.post("/api/calculate", json={
            "mode": "salary", "total": 120000, "monthly": 10000,
            "config": MINIMAL_CONFIG,
        })
        assert r.status_code == 200
        assert r.json()["total_tax"] == pytest.approx(3480.0)

    def test_salary_mode_no_ss_net_take_home(self):
        """net_take_home = 120000 − 3480 = 116520"""
        r = client.post("/api/calculate", json={
            "mode": "salary", "total": 120000, "monthly": 10000,
            "config": MINIMAL_CONFIG,
        })
        assert r.json()["net_take_home"] == pytest.approx(116520.0)

    def test_salary_mode_with_ss_and_pf(self):
        """
        场景 B：salary 模式，月薪 20000，全额社保公积金。
        annual_ss=54000, annual_pf=57600, tax=10080
        net_take_home=175920, net+pf=233520
        """
        r = client.post("/api/calculate", json={
            "mode": "salary", "total": 240000, "monthly": 20000,
            "config": FULL_CONFIG,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["annual_social_security"] == pytest.approx(54000.0)
        assert data["annual_provident_fund"] == pytest.approx(57600.0)
        assert data["total_tax"] == pytest.approx(10080.0)
        assert data["net_take_home"] == pytest.approx(175920.0)
        assert data["net_take_home_including_provident_fund"] == pytest.approx(233520.0)

    def test_bonus_mode_with_year_end_bonus(self):
        """
        场景 C：bonus 模式，总收入 300000，年终奖 60000（月薪 20000）。
        bonus_tax = 5790, total_tax = 15870
        net_take_home = 230130, net+pf = 287730
        """
        r = client.post("/api/calculate", json={
            "mode": "bonus", "total": 300000, "bonus": 60000,
            "config": FULL_CONFIG,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["bonus_tax"] == pytest.approx(5790.0)
        assert data["total_tax"] == pytest.approx(15870.0)
        assert data["net_take_home"] == pytest.approx(230130.0)
        assert data["net_take_home_including_provident_fund"] == pytest.approx(287730.0)

    def test_both_mode_matches_bonus_mode(self):
        """both 模式传月薪+年终奖，结果应与 bonus 模式一致。"""
        r_both = client.post("/api/calculate", json={
            "mode": "both", "monthly": 20000, "bonus": 60000,
            "config": FULL_CONFIG,
        })
        r_bonus = client.post("/api/calculate", json={
            "mode": "bonus", "total": 300000, "bonus": 60000,
            "config": FULL_CONFIG,
        })
        assert r_both.status_code == 200
        for field in CARD_FIELDS:
            assert r_both.json()[field] == pytest.approx(r_bonus.json()[field], abs=0.01)

    def test_optimize_mode_returns_valid_split(self):
        """optimize 模式：月薪 × 12 + 年终奖 = 全年收入。"""
        r = client.post("/api/calculate", json={
            "mode": "optimize", "total": 300000,
            "config": FULL_CONFIG,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["monthly_salary"] * 12 + data["bonus"] == pytest.approx(300000.0, abs=0.01)

    def test_optimize_mode_cash_plus_pf_objective(self):
        """cash_plus_provident_fund 目标的优化结果仍包含全部卡片字段。"""
        r = client.post("/api/calculate", json={
            "mode": "optimize", "total": 300000,
            "objective": "cash_plus_provident_fund",
            "config": FULL_CONFIG,
        })
        assert r.status_code == 200
        for field in CARD_FIELDS:
            assert field in r.json()


# ──────────────────────────────────────────────
# POST /api/calculate — 指标卡片字段完整性
# ──────────────────────────────────────────────

class TestCardFieldsInAPIResponse:
    @pytest.mark.parametrize("mode,extra", [
        ("salary",   {"total": 300000, "monthly": 20000}),
        ("bonus",    {"total": 300000, "bonus": 60000}),
        ("both",     {"monthly": 20000, "bonus": 60000}),
        ("optimize", {"total": 300000}),
    ])
    def test_all_card_fields_present(self, mode, extra):
        """所有计算模式的响应均须包含卡片所需的全部字段。"""
        r = client.post("/api/calculate", json={"mode": mode, "config": FULL_CONFIG, **extra})
        assert r.status_code == 200
        data = r.json()
        for field in CARD_FIELDS:
            assert field in data, f"模式={mode} 缺少字段：{field}"

    @pytest.mark.parametrize("mode,extra", [
        ("salary",   {"total": 300000, "monthly": 20000}),
        ("bonus",    {"total": 300000, "bonus": 60000}),
        ("both",     {"monthly": 20000, "bonus": 60000}),
        ("optimize", {"total": 300000}),
    ])
    def test_cash_plus_pf_invariant(self, mode, extra):
        """任意模式下：现金+公积金 = 到手现金 + 公积金。"""
        r = client.post("/api/calculate", json={"mode": mode, "config": FULL_CONFIG, **extra})
        data = r.json()
        expected = data["net_take_home"] + data["annual_provident_fund"]
        assert data["net_take_home_including_provident_fund"] == pytest.approx(expected, abs=0.01)

    def test_response_contains_monthly_details(self):
        """响应应包含 12 条月度明细，供网页表格渲染。"""
        r = client.post("/api/calculate", json={
            "mode": "salary", "total": 300000, "monthly": 20000,
            "config": FULL_CONFIG,
        })
        data = r.json()
        assert "monthly_details" in data
        assert len(data["monthly_details"]) == 12

    def test_all_card_fields_non_negative(self):
        r = client.post("/api/calculate", json={
            "mode": "salary", "total": 300000, "monthly": 20000,
            "config": FULL_CONFIG,
        })
        data = r.json()
        for field in CARD_FIELDS:
            assert data[field] >= 0, f"{field} 不应为负数"


# ──────────────────────────────────────────────
# POST /api/calculate — 使用预设城市
# ──────────────────────────────────────────────

class TestCalculateWithPreset:
    def test_preset_slug_accepted(self):
        """通过 preset_slug 指定城市时，接口应正常返回结果。"""
        r = client.post("/api/calculate", json={
            "mode": "salary", "total": 300000, "monthly": 20000,
            "preset_slug": "zhejiang-hangzhou",
        })
        assert r.status_code == 200

    def test_preset_slug_overrides_config(self):
        """同时传 preset_slug 与 config 时，preset_slug 优先（或至少不报错）。"""
        r = client.post("/api/calculate", json={
            "mode": "salary", "total": 300000, "monthly": 20000,
            "preset_slug": "zhejiang-hangzhou",
            "config": MINIMAL_CONFIG,
        })
        # 服务端选择 preset_slug，社保不为 0
        assert r.status_code == 200
        assert r.json()["annual_social_security"] > 0

    def test_unknown_preset_slug_returns_422_or_404(self):
        r = client.post("/api/calculate", json={
            "mode": "salary", "total": 300000, "monthly": 20000,
            "preset_slug": "nonexistent-city-xyz",
        })
        assert r.status_code in (422, 404)


# ──────────────────────────────────────────────
# POST /api/calculate — 输入校验
# ──────────────────────────────────────────────

class TestCalculateValidation:
    def test_salary_mode_missing_monthly_returns_422(self):
        """salary 模式缺少 monthly 字段时应返回 422。"""
        r = client.post("/api/calculate", json={
            "mode": "salary", "total": 300000,
            "config": MINIMAL_CONFIG,
        })
        assert r.status_code == 422

    def test_bonus_mode_missing_bonus_returns_422(self):
        r = client.post("/api/calculate", json={
            "mode": "bonus", "total": 300000,
            "config": MINIMAL_CONFIG,
        })
        assert r.status_code == 422

    def test_both_mode_missing_monthly_returns_422(self):
        r = client.post("/api/calculate", json={
            "mode": "both", "bonus": 60000,
            "config": MINIMAL_CONFIG,
        })
        assert r.status_code == 422

    def test_invalid_mode_returns_422(self):
        r = client.post("/api/calculate", json={
            "mode": "invalid_mode", "total": 300000,
            "config": MINIMAL_CONFIG,
        })
        assert r.status_code == 422

    def test_neither_config_nor_preset_returns_422(self):
        """既未传 config 也未传 preset_slug 时，应返回 422。"""
        r = client.post("/api/calculate", json={
            "mode": "salary", "total": 300000, "monthly": 20000,
        })
        assert r.status_code == 422

    def test_invalid_tax_rate_returns_422(self):
        """社保费率超出 [0,1] 时应被校验拒绝。"""
        bad_config = {**FULL_CONFIG, "pension_rate": 1.5}
        r = client.post("/api/calculate", json={
            "mode": "salary", "total": 300000, "monthly": 20000,
            "config": bad_config,
        })
        assert r.status_code == 422

    def test_ss_base_min_gt_limit_returns_422(self):
        """社保基数下限 > 上限时应被校验拒绝。"""
        bad_config = {**FULL_CONFIG, "social_security_base_min": 30000, "social_security_base_limit": 10000}
        r = client.post("/api/calculate", json={
            "mode": "salary", "total": 300000, "monthly": 20000,
            "config": bad_config,
        })
        assert r.status_code == 422


# ──────────────────────────────────────────────
# POST /api/export/excel
# ──────────────────────────────────────────────

class TestExportExcel:
    def _calc_result(self):
        r = client.post("/api/calculate", json={
            "mode": "salary", "total": 300000, "monthly": 20000,
            "config": FULL_CONFIG,
        })
        assert r.status_code == 200
        return r.json()

    def test_export_returns_200(self):
        result = self._calc_result()
        r = client.post("/api/export/excel", json={"result": result})
        assert r.status_code == 200

    def test_export_content_type_is_xlsx(self):
        result = self._calc_result()
        r = client.post("/api/export/excel", json={"result": result})
        assert "spreadsheetml" in r.headers["content-type"]

    def test_export_content_disposition_has_filename(self):
        result = self._calc_result()
        r = client.post("/api/export/excel", json={"result": result})
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert ".xlsx" in cd

    def test_export_body_is_nonempty(self):
        result = self._calc_result()
        r = client.post("/api/export/excel", json={"result": result})
        assert len(r.content) > 1000

    def test_export_with_custom_title(self):
        result = self._calc_result()
        r = client.post("/api/export/excel", json={"result": result, "title": "测试标题"})
        assert r.status_code == 200
        assert r.status_code == 200
        assert "attachment" in r.headers.get("content-disposition", "")

    def test_export_with_bonus(self):
        r_calc = client.post("/api/calculate", json={
            "mode": "bonus", "total": 300000, "bonus": 60000,
            "config": FULL_CONFIG,
        })
        result = r_calc.json()
        r = client.post("/api/export/excel", json={"result": result})
        assert r.status_code == 200
        assert len(r.content) > 1000
