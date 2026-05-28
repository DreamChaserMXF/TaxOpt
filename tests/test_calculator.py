"""
核心税务计算单元测试 — 手工推导期望值，保护计算逻辑在 Web 化过程中不被破坏。

当前状态：这批测试应能通过（TaxCalculator 已实现）。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import (
    TaxConfig,
    TaxCalculator,
    TaxOptimizer,
    _progressive_tax,
    enrich_result_with_provident_fund,
    load_tax_config_from_json,
    result_from_salary_bonus_split,
    BONUS_BRACKETS_ANNUAL,
    COMPREHENSIVE_BRACKETS,
)


def brute_force_optimize(
    calc: TaxCalculator,
    total_annual: float,
    step: int = 1,
    objective: str = "cash",
    extra_income: float = 0.0,
    stock_grants=None,
):
    """参考穷举器：作为断点搜索优化器的真值基线。"""
    if stock_grants is None:
        stock_grants = []

    stock_grants_total = sum(stock_grants)
    salary_bonus_pool = total_annual - extra_income - stock_grants_total
    if salary_bonus_pool < -0.01:
        raise ValueError("额外激励与股票激励之和不能超过全年名义收入")
    if salary_bonus_pool < 0:
        salary_bonus_pool = 0.0

    best = None
    best_score = float("-inf")
    best_tax_at_score = float("inf")
    cap = int(salary_bonus_pool // 12)
    total_stock_tax = sum(calc.bonus_tax(g) for g in stock_grants)
    iterations = 0

    for monthly_salary in range(0, cap + 1, step):
        bonus = salary_bonus_pool - monthly_salary * 12
        if bonus < 0:
            continue

        iterations += 1
        comp_tax, bonus_tax, annual_personal_deduction, annual_pf_total, _ins, _hf = (
            calc._calc_annual_tax(monthly_salary, bonus, extra_income)
        )
        total_tax = comp_tax + bonus_tax + total_stock_tax
        net = total_annual - total_tax - annual_personal_deduction
        score = net + annual_pf_total if objective == "cash_plus_provident_fund" else net

        if score > best_score or (score == best_score and total_tax < best_tax_at_score):
            best_score = score
            best_tax_at_score = total_tax
            best = (monthly_salary, bonus)

    assert best is not None, "穷举参考器未找到任何候选方案"
    result = result_from_salary_bonus_split(
        calc,
        salary_bonus_pool,
        best[0],
        best[1],
        extra_income=extra_income,
        stock_grants=stock_grants,
    )
    result["_iterations"] = iterations
    return result

# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def minimal_config():
    """零社保零公积金，隔离社保变量，单独验证个税逻辑。"""
    return TaxConfig(
        basic_deduction=60000,
        pension_rate=0.0,
        medical_rate=0.0,
        unemployment_rate=0.0,
        housing_fund_employee_rate=0.0,
        housing_fund_employer_rate=0.0,
    )


@pytest.fixture
def full_config():
    """标准费率，无基数上下限，验证社保+公积金全额计算。"""
    return TaxConfig(
        basic_deduction=60000,
        pension_rate=0.08,
        medical_rate=0.02,
        unemployment_rate=0.005,
        housing_fund_employee_rate=0.12,
        housing_fund_employer_rate=0.12,
    )


@pytest.fixture
def hangzhou_config():
    """杭州市区口径：社保基数 4986–25299，公积金基数 2490–40694，12% 双边。"""
    return TaxConfig(
        basic_deduction=60000,
        social_security_base_min=4986,
        social_security_base_limit=25299,
        pension_rate=0.08,
        medical_rate=0.02,
        unemployment_rate=0.005,
        housing_fund_base_min=2490,
        housing_fund_base_limit=40694,
        housing_fund_employee_rate=0.12,
        housing_fund_employer_rate=0.12,
    )


# ──────────────────────────────────────────────
# 税率表
# ──────────────────────────────────────────────

class TestProgressiveTax:
    def test_zero_income_returns_zero(self):
        assert _progressive_tax(0, COMPREHENSIVE_BRACKETS) == 0.0

    def test_negative_income_returns_zero(self):
        assert _progressive_tax(-500, COMPREHENSIVE_BRACKETS) == 0.0

    def test_first_bracket_boundary(self):
        # 36000 × 3% − 0 = 1080（边界值，仍属第一档）
        assert _progressive_tax(36000, COMPREHENSIVE_BRACKETS) == pytest.approx(1080.0)

    def test_second_bracket(self):
        # 100000 × 10% − 2520 = 7480
        assert _progressive_tax(100000, COMPREHENSIVE_BRACKETS) == pytest.approx(7480.0)

    def test_third_bracket(self):
        # 200000 × 20% − 16920 = 23080
        assert _progressive_tax(200000, COMPREHENSIVE_BRACKETS) == pytest.approx(23080.0)

    def test_bonus_first_bracket_boundary(self):
        # 年终奖 36000，对应月均 3000，第一档边界：36000 × 3% − 0 = 1080
        assert _progressive_tax(36000, BONUS_BRACKETS_ANNUAL) == pytest.approx(1080.0)

    def test_bonus_second_bracket(self):
        # 年终奖 60000，(36000, 144000]：60000 × 10% − 210 = 5790
        # 注意：速算扣除数用的是月度口径 210，不是 210×12
        assert _progressive_tax(60000, BONUS_BRACKETS_ANNUAL) == pytest.approx(5790.0)

    def test_bonus_third_bracket(self):
        # 年终奖 200000，(144000, 300000]：200000 × 20% − 1410 = 38590
        assert _progressive_tax(200000, BONUS_BRACKETS_ANNUAL) == pytest.approx(38590.0)


# ──────────────────────────────────────────────
# 月度三险与公积金计算
# ──────────────────────────────────────────────

class TestMonthlyInsuranceAndHousingFund:
    def test_zero_rates_insurance_all_zero(self, minimal_config):
        calc = TaxCalculator(minimal_config)
        ins = calc.monthly_insurance(20000)
        assert ins["pension"] == 0.0
        assert ins["medical"] == 0.0
        assert ins["unemployment"] == 0.0
        assert ins["total"] == 0.0

    def test_zero_rates_housing_fund_all_zero(self, minimal_config):
        calc = TaxCalculator(minimal_config)
        hf = calc.monthly_housing_fund(20000)
        assert hf["employee"] == 0.0
        assert hf["employer"] == 0.0

    def test_full_rates_insurance_no_cap(self, full_config):
        """
        月薪 20000，无基数上下限。

        pension      = 20000 × 8%   = 1600
        medical      = 20000 × 2%   = 400
        unemployment = 20000 × 0.5% = 100
        total        = 2100（纯三险）
        """
        calc = TaxCalculator(full_config)
        ins = calc.monthly_insurance(20000)
        assert ins["pension"] == pytest.approx(1600.0)
        assert ins["medical"] == pytest.approx(400.0)
        assert ins["unemployment"] == pytest.approx(100.0)
        assert ins["total"] == pytest.approx(2100.0)

    def test_full_rates_housing_fund_no_cap(self, full_config):
        """
        月薪 20000，无基数上下限。

        employee = 20000 × 12% = 2400
        employer = 20000 × 12% = 2400
        """
        calc = TaxCalculator(full_config)
        hf = calc.monthly_housing_fund(20000)
        assert hf["employee"] == pytest.approx(2400.0)
        assert hf["employer"] == pytest.approx(2400.0)

    def test_salary_above_cap(self, hangzhou_config):
        """
        月薪 50000 超出社保基数上限 25299，公积金基数上限 40694。

        三险基数 clamp 到 25299：pension = 25299 × 8% = 2023.92
        公积金基数 clamp 到 40694：employee = 40694 × 12% = 4883.28
        """
        calc = TaxCalculator(hangzhou_config)
        ins = calc.monthly_insurance(50000)
        hf = calc.monthly_housing_fund(50000)
        assert ins["pension"] == pytest.approx(25299 * 0.08)
        assert ins["medical"] == pytest.approx(25299 * 0.02)
        assert ins["unemployment"] == pytest.approx(25299 * 0.005)
        assert hf["employee"] == pytest.approx(40694 * 0.12)
        assert hf["employer"] == pytest.approx(40694 * 0.12)

    def test_salary_below_min(self, hangzhou_config):
        """
        月薪 1000 低于社保基数下限 4986，公积金基数下限 2490。

        三险基数 clamp 到 4986，公积金基数 clamp 到 2490。
        """
        calc = TaxCalculator(hangzhou_config)
        ins = calc.monthly_insurance(1000)
        hf = calc.monthly_housing_fund(1000)
        assert ins["pension"] == pytest.approx(4986 * 0.08)
        assert ins["medical"] == pytest.approx(4986 * 0.02)
        assert hf["employee"] == pytest.approx(2490 * 0.12)
        assert hf["employer"] == pytest.approx(2490 * 0.12)

    def test_employer_rate_defaults_to_employee_rate(self, tmp_path):
        """JSON 未写 housing_fund_employer_rate 时，应由 load_tax_config_from_json 将其设为与个人比例相同。"""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"housing_fund_employee_rate": 0.07}', encoding="utf-8")
        cfg = load_tax_config_from_json(json_file)
        calc = TaxCalculator(cfg)
        hf = calc.monthly_housing_fund(10000)
        assert hf["employee"] == pytest.approx(700.0)
        assert hf["employer"] == pytest.approx(700.0)


# ──────────────────────────────────────────────
# 完整年度计算（result_from_salary_bonus_split）
# ──────────────────────────────────────────────

class TestResultFromSalaryBonusSplit:
    # ── 场景 A：极简，无社保无公积金 ──────────────────

    def test_scenario_a_total_tax(self, minimal_config):
        """
        场景 A：月薪 10000，无年终奖，零社保。

        taxable = 10000×12 − 60000 = 60000
        60000 ∈ (36000, 144000]：tax = 60000 × 10% − 2520 = 3480
        """
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0)
        assert r["total_tax"] == pytest.approx(3480.0)

    def test_scenario_a_social_security_zero(self, minimal_config):
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0)
        assert r["annual_social_security"] == pytest.approx(0.0)

    def test_scenario_a_provident_fund_zero(self, minimal_config):
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0)
        assert r["annual_provident_fund"] == pytest.approx(0.0)

    def test_scenario_a_net_take_home(self, minimal_config):
        """net_take_home = 120000 − 3480 − 0 = 116520"""
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0)
        assert r["net_take_home"] == pytest.approx(116520.0)

    def test_scenario_a_cash_plus_pf_equals_cash(self, minimal_config):
        """无公积金时，现金+公积金 = 现金到手。"""
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0)
        assert r["net_take_home_including_provident_fund"] == pytest.approx(116520.0)

    def test_scenario_a_effective_tax_rate(self, minimal_config):
        """effective_tax_rate = 3480 / 120000 ≈ 2.9%"""
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0)
        assert r["effective_tax_rate"] == pytest.approx(3480 / 120000)

    # ── 场景 B：全额社保公积金，无基数限制 ────────────

    def test_scenario_b_annual_social_security(self, full_config):
        """
        场景 B：月薪 20000，无年终奖，全额社保公积金。

        月社保（个人三险）= 20000×(8%+2%+0.5%) = 2100
        月公积金（个人）= 20000×12% = 2400
        月合计个人 = 4500；年社保 = 4500 × 12 = 54000
        """
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 240000, 20000, 0)
        assert r["annual_social_security"] == pytest.approx(54000.0)

    def test_scenario_b_annual_provident_fund(self, full_config):
        """
        年公积金（个人+公司）= (2400+2400) × 12 = 57600
        """
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 240000, 20000, 0)
        assert r["annual_provident_fund"] == pytest.approx(57600.0)

    def test_scenario_b_total_tax(self, full_config):
        """
        taxable = 240000 − 60000 − 54000 = 126000
        126000 ∈ (36000, 144000]：tax = 126000 × 10% − 2520 = 10080
        """
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 240000, 20000, 0)
        assert r["total_tax"] == pytest.approx(10080.0)

    def test_scenario_b_net_take_home(self, full_config):
        """net_take_home = 240000 − 10080 − 54000 = 175920"""
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 240000, 20000, 0)
        assert r["net_take_home"] == pytest.approx(175920.0)

    def test_scenario_b_cash_plus_pf(self, full_config):
        """net_take_home_including_provident_fund = 175920 + 57600 = 233520"""
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 240000, 20000, 0)
        assert r["net_take_home_including_provident_fund"] == pytest.approx(233520.0)

    # ── 场景 C：含年终奖 ───────────────────────────────

    def test_scenario_c_bonus_tax(self, full_config):
        """
        场景 C：月薪 20000，年终奖 60000，合计 300000。

        年终奖税：60000 ∈ (36000, 144000]：60000 × 10% − 210 = 5790
        注：速算扣除数为月度口径 210，非 210×12。
        """
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 300000, 20000, 60000)
        assert r["bonus_tax"] == pytest.approx(5790.0)

    def test_scenario_c_comprehensive_tax_unchanged(self, full_config):
        """工资综合所得税不因年终奖拆分而变化，仍为 10080。"""
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 300000, 20000, 60000)
        assert r["comprehensive_annual_tax"] == pytest.approx(10080.0)

    def test_scenario_c_total_tax(self, full_config):
        """total_tax = 10080 + 5790 = 15870"""
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 300000, 20000, 60000)
        assert r["total_tax"] == pytest.approx(15870.0)

    def test_scenario_c_net_take_home(self, full_config):
        """net_take_home = 300000 − 15870 − 54000 = 230130"""
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 300000, 20000, 60000)
        assert r["net_take_home"] == pytest.approx(230130.0)

    def test_scenario_c_cash_plus_pf(self, full_config):
        """net_take_home_including_provident_fund = 230130 + 57600 = 287730"""
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 300000, 20000, 60000)
        assert r["net_take_home_including_provident_fund"] == pytest.approx(287730.0)

    def test_scenario_c_bonus_after_tax(self, full_config):
        """bonus_after_tax = 60000 − 5790 = 54210"""
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 300000, 20000, 60000)
        assert r["bonus_after_tax"] == pytest.approx(54210.0)

    # ── 不变量验证 ────────────────────────────────────

    def test_cash_plus_pf_invariant(self, full_config):
        """任意拆分下：net_take_home_including_provident_fund = net_take_home + annual_provident_fund"""
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 500000, 30000, 140000)
        assert r["net_take_home_including_provident_fund"] == pytest.approx(
            r["net_take_home"] + r["annual_provident_fund"], abs=0.01
        )

    def test_effective_burden_rate_invariant(self, full_config):
        """effective_burden_rate = (total_tax + annual_social_security) / total"""
        calc = TaxCalculator(full_config)
        total = 300000
        r = result_from_salary_bonus_split(calc, total, 20000, 60000)
        expected = (r["total_tax"] + r["annual_social_security"]) / total
        assert r["effective_burden_rate"] == pytest.approx(expected, abs=1e-9)


# ──────────────────────────────────────────────
# 网页 8 个核心指标字段完整性
# ──────────────────────────────────────────────

# 名义收入卡片由前端计算 annual_salary + bonus，其余卡片直接取以下字段
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


class TestCardFields:
    def test_all_card_fields_present(self, full_config):
        """result 字典必须包含网页 8 个核心指标卡片所需的全部字段。"""
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 300000, 20000, 60000)
        for field in CARD_FIELDS:
            assert field in r, f"缺少字段：{field}"

    def test_social_security_card_is_annual(self, full_config):
        """社保卡片取年度个人五险一金总额，值应为 54000。"""
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 300000, 20000, 60000)
        assert r["annual_social_security"] == pytest.approx(54000.0)

    def test_cash_plus_pf_card_value(self, full_config):
        """现金+公积金卡片 = 到手现金 + 公积金（个人+公司全年）。"""
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 300000, 20000, 60000)
        assert r["net_take_home_including_provident_fund"] == pytest.approx(
            r["net_take_home"] + r["annual_provident_fund"]
        )

    def test_all_card_fields_are_non_negative(self, full_config):
        """8 个指标所需字段均应为非负数。"""
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 300000, 20000, 60000)
        for field in CARD_FIELDS:
            assert r[field] >= 0, f"{field} 不应为负数"

    def test_card_fields_with_zero_provident_fund(self, minimal_config):
        """零公积金时所有卡片字段均应正常存在。"""
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0)
        for field in CARD_FIELDS:
            assert field in r


# ──────────────────────────────────────────────
# 月度明细
# ──────────────────────────────────────────────

class TestMonthlyDetails:
    def test_returns_twelve_rows(self, minimal_config):
        calc = TaxCalculator(minimal_config)
        details = calc.monthly_details(10000)
        assert len(details) == 12

    def test_month_numbers_are_sequential(self, minimal_config):
        calc = TaxCalculator(minimal_config)
        details = calc.monthly_details(10000)
        assert [d["month"] for d in details] == list(range(1, 13))

    def test_month1_in_first_bracket(self, minimal_config):
        """
        月薪 20000，无社保，无额外扣除。

        第 1 月累计应税所得 = 20000 − 5000 = 15000
        0 < 15000 ≤ 36000：cum_tax = 15000 × 3% = 450
        month_tax = 450；after_tax = 20000 − 0 − 450 = 19550
        """
        calc = TaxCalculator(minimal_config)
        details = calc.monthly_details(20000)
        m1 = details[0]
        assert m1["tax"] == pytest.approx(450.0)
        assert m1["after_tax_salary"] == pytest.approx(19550.0)

    def test_month2_same_bracket(self, minimal_config):
        """
        第 2 月累计应税所得 = 30000；cum_tax = 900
        month_tax = 900 − 450 = 450；after_tax = 19550
        """
        calc = TaxCalculator(minimal_config)
        details = calc.monthly_details(20000)
        m2 = details[1]
        assert m2["tax"] == pytest.approx(450.0)
        assert m2["after_tax_salary"] == pytest.approx(19550.0)

    def test_month3_crosses_bracket(self, minimal_config):
        """
        第 3 月累计应税所得 = 45000，跨入 10% 档。

        cum_tax(3) = 45000 × 10% − 2520 = 1980
        cum_tax(2) = 30000 × 3% = 900
        month_tax = 1080；after_tax = 20000 − 0 − 1080 = 18920
        """
        calc = TaxCalculator(minimal_config)
        details = calc.monthly_details(20000)
        m3 = details[2]
        assert m3["tax"] == pytest.approx(1080.0)
        assert m3["after_tax_salary"] == pytest.approx(18920.0)

    def test_month12_high_bracket(self, minimal_config):
        """
        第 12 月累计应税所得 = 240000 − 60000 = 180000，进入 20% 档。

        cum_tax(12) = 180000 × 20% − 16920 = 19080
        cum_tax(11)：165000 × 20% − 16920 = 16080
        month_tax = 3000；after_tax = 20000 − 0 − 3000 = 17000
        """
        calc = TaxCalculator(minimal_config)
        details = calc.monthly_details(20000)
        m12 = details[11]
        assert m12["tax"] == pytest.approx(3000.0)
        assert m12["after_tax_salary"] == pytest.approx(17000.0)

    def test_annual_tax_sum_matches_result(self, full_config):
        """月度税额之和应等于 _calc_annual_tax 的综合所得税。"""
        calc = TaxCalculator(full_config)
        comp_tax, _, _, _, ins, hf = calc._calc_annual_tax(20000, 0)
        details = calc.monthly_details(20000, ins, hf)
        assert sum(d["tax"] for d in details) == pytest.approx(comp_tax, abs=0.01)

    def test_monthly_detail_has_required_keys(self, full_config):
        """每行明细需含网页表格所需的全部字段。"""
        required = {
            "month", "salary", "insurance", "housing_fund", "tax",
            "after_tax_salary", "after_tax_including_provident_fund",
        }
        calc = TaxCalculator(full_config)
        details = calc.monthly_details(20000)
        for row in details:
            assert required.issubset(row.keys()), f"第 {row.get('month')} 月明细缺字段"


# ──────────────────────────────────────────────
# TaxOptimizer
# ──────────────────────────────────────────────

# ──────────────────────────────────────────────
# 额外激励与股票激励
# ──────────────────────────────────────────────

class TestExtraIncomeAndStockGrants:
    """
    使用 minimal_config（零社保零公积金）隔离变量，专门验证额外激励与股票激励逻辑。
    """

    # ── 额外激励 (extra_income) ─────────────────────

    def test_extra_income_increases_comprehensive_tax(self, minimal_config):
        """
        额外激励并入综合所得，应使综合所得税额增加。

        月薪 10000，无年终奖，零社保。
        base:    taxable = 120000 − 60000 = 60000；tax = 60000×10% − 2520 = 3480
        extra=20000: taxable = 80000；tax = 80000×10% − 2520 = 5480
        """
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0, extra_income=20000)
        assert r["comprehensive_annual_tax"] == pytest.approx(5480.0)

    def test_extra_income_does_not_affect_bonus_tax(self, minimal_config):
        """额外激励不影响年终奖税额。"""
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0, extra_income=20000)
        assert r["bonus_tax"] == pytest.approx(0.0)

    def test_extra_income_included_in_nominal_income(self, minimal_config):
        """nominal_income 含 extra_income。"""
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0, extra_income=20000)
        assert r["nominal_income"] == pytest.approx(140000.0)

    def test_extra_income_net_take_home(self, minimal_config):
        """
        net_take_home = nominal_income − total_tax − 社保
        = 140000 − 5480 − 0 = 134520
        """
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0, extra_income=20000)
        assert r["net_take_home"] == pytest.approx(134520.0)

    def test_extra_income_effective_rate_uses_nominal(self, minimal_config):
        """effective_tax_rate 分母为 nominal_income（含 extra_income）。"""
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0, extra_income=20000)
        assert r["effective_tax_rate"] == pytest.approx(5480.0 / 140000.0)

    # ── 股票激励 (stock_grants) ─────────────────────

    def test_single_stock_grant_tax(self, minimal_config):
        """
        单笔股票激励按年终奖方式计税。
        60000 ∈ (36000, 144000]：60000×10% − 210 = 5790
        """
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0, stock_grants=[60000])
        assert len(r["stock_grants"]) == 1
        assert r["stock_grants_tax"][0] == pytest.approx(5790.0)
        assert r["total_stock_tax"] == pytest.approx(5790.0)

    def test_single_stock_grant_net_take_home(self, minimal_config):
        """
        net_take_home = (120000 + 60000) − (3480 + 5790) − 0 = 170730
        """
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0, stock_grants=[60000])
        assert r["net_take_home"] == pytest.approx(170730.0)

    def test_multiple_grants_taxed_independently(self, minimal_config):
        """
        两笔相同金额的股票激励独立计税，不合并。

        各 60000：each tax = 5790，合计 11580
        若合并为 120000：120000×10% − 210 = 11790（与独立不同，验证确实是独立计税）
        """
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0, stock_grants=[60000, 60000])
        assert r["stock_grants_tax"][0] == pytest.approx(5790.0)
        assert r["stock_grants_tax"][1] == pytest.approx(5790.0)
        assert r["total_stock_tax"] == pytest.approx(11580.0)
        # 若合并，结果为 11790，独立计税节税 210 元
        assert r["total_stock_tax"] != pytest.approx(11790.0)

    def test_multiple_grants_nominal_income(self, minimal_config):
        """nominal_income 含所有股票激励金额。"""
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0, stock_grants=[60000, 36000])
        assert r["nominal_income"] == pytest.approx(216000.0)

    def test_stock_grant_does_not_affect_comprehensive_tax(self, minimal_config):
        """股票激励不并入综合所得，综合所得税不变。"""
        calc = TaxCalculator(minimal_config)
        r_base = result_from_salary_bonus_split(calc, 120000, 10000, 0)
        r_grant = result_from_salary_bonus_split(calc, 120000, 10000, 0, stock_grants=[100000])
        assert r_grant["comprehensive_annual_tax"] == pytest.approx(r_base["comprehensive_annual_tax"])

    # ── 组合场景 ─────────────────────────────────

    def test_combined_extra_income_and_stock_grant(self, minimal_config):
        """
        月薪 10000，extra=20000，stock=[60000]。

        taxable = 120000 + 20000 − 60000 = 80000；comp_tax = 5480
        stock_tax = 5790；total_tax = 11270
        nominal = 120000 + 20000 + 60000 = 200000
        net = 200000 − 11270 = 188730
        """
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(
            calc, 120000, 10000, 0, extra_income=20000, stock_grants=[60000]
        )
        assert r["comprehensive_annual_tax"] == pytest.approx(5480.0)
        assert r["total_stock_tax"] == pytest.approx(5790.0)
        assert r["total_tax"] == pytest.approx(11270.0)
        assert r["nominal_income"] == pytest.approx(200000.0)
        assert r["net_take_home"] == pytest.approx(188730.0)

    # ── 向后兼容 ──────────────────────────────────

    def test_defaults_backward_compatible(self, minimal_config):
        """不传新参数时，与原函数行为完全一致。"""
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0)
        assert r["extra_income"] == 0.0
        assert r["stock_grants"] == []
        assert r["stock_grants_tax"] == []
        assert r["total_stock_tax"] == 0.0
        assert r["total_tax"] == pytest.approx(3480.0)
        assert r["net_take_home"] == pytest.approx(116520.0)
        assert r["nominal_income"] == pytest.approx(120000.0)

    def test_negative_extra_income_raises(self, minimal_config):
        """额外激励为负数时应抛出 ValueError。"""
        calc = TaxCalculator(minimal_config)
        with pytest.raises(ValueError, match="额外激励"):
            result_from_salary_bonus_split(calc, 120000, 10000, 0, extra_income=-1)

    def test_negative_stock_grant_raises(self, minimal_config):
        """股票激励金额为负数时应抛出 ValueError。"""
        calc = TaxCalculator(minimal_config)
        with pytest.raises(ValueError, match="股票激励"):
            result_from_salary_bonus_split(calc, 120000, 10000, 0, stock_grants=[-1000])


class TestTaxOptimizer:
    def test_monthly_details_insurance_matches_best_salary(self, full_config):
        """
        optimize() 的 monthly_details 中 insurance/housing_fund 必须对应最优月薪，
        而非循环末次迭代的月薪。

        回归测试：修复前 best_ins/best_hf 在循环后指向最后一次迭代（m = cap），
        若最优月薪 < cap，月度明细会使用错误的三险/公积金分项值。

        full_config + total=300000 时，含年终奖的拆分比纯月薪更优，
        因此最优月薪必然小于 cap（25000），可验证此边界。
        """
        calc = TaxCalculator(full_config)
        result = TaxOptimizer(calc).optimize(300000)
        best_monthly = result["monthly_salary"]
        cap = int(300000 // 12)
        assert best_monthly < cap, "前提不成立：最优月薪应小于 cap，无法触发原 bug"

        expected_ins = calc.monthly_insurance(best_monthly)
        expected_hf = calc.monthly_housing_fund(best_monthly)
        for row in result["monthly_details"]:
            assert row["insurance"]["total"] == pytest.approx(expected_ins["total"])
            assert row["housing_fund"]["employee"] == pytest.approx(expected_hf["employee"])
            assert row["housing_fund"]["employer"] == pytest.approx(expected_hf["employer"])

    @pytest.mark.parametrize("total_annual", [120000, 200000, 300000, 500000])
    def test_optimize_matches_bruteforce_for_cash_objective(self, full_config, total_annual):
        calc = TaxCalculator(full_config)
        optimized = TaxOptimizer(calc).optimize(total_annual, step=1, objective="cash")
        brute = brute_force_optimize(calc, total_annual, step=1, objective="cash")

        assert optimized["monthly_salary"] == brute["monthly_salary"]
        assert optimized["bonus"] == pytest.approx(brute["bonus"])
        assert optimized["total_tax"] == pytest.approx(brute["total_tax"])
        assert optimized["net_take_home"] == pytest.approx(brute["net_take_home"])

    @pytest.mark.parametrize("total_annual", [300000, 500000, 1000000])
    def test_optimize_matches_bruteforce_for_cash_plus_pf_objective(self, full_config, total_annual):
        calc = TaxCalculator(full_config)
        optimized = TaxOptimizer(calc).optimize(
            total_annual,
            step=1,
            objective="cash_plus_provident_fund",
        )
        brute = brute_force_optimize(
            calc,
            total_annual,
            step=1,
            objective="cash_plus_provident_fund",
        )

        assert optimized["monthly_salary"] == brute["monthly_salary"]
        assert optimized["bonus"] == pytest.approx(brute["bonus"])
        assert optimized["net_take_home_including_provident_fund"] == pytest.approx(
            brute["net_take_home_including_provident_fund"]
        )

    @pytest.mark.parametrize("step", [1, 37, 1000])
    def test_optimize_matches_bruteforce_across_steps(self, hangzhou_config, step):
        calc = TaxCalculator(hangzhou_config)
        total_annual = 500000

        optimized = TaxOptimizer(calc).optimize(total_annual, step=step, objective="cash")
        brute = brute_force_optimize(calc, total_annual, step=step, objective="cash")

        assert optimized["monthly_salary"] == brute["monthly_salary"]
        assert optimized["bonus"] == pytest.approx(brute["bonus"])
        assert optimized["net_take_home"] == pytest.approx(brute["net_take_home"])

    def test_optimize_matches_bruteforce_with_extra_income_and_stock_grants(self, minimal_config):
        calc = TaxCalculator(minimal_config)
        total_annual = 500000
        extra_income = 60000
        stock_grants = [30000, 50000]

        optimized = TaxOptimizer(calc).optimize(
            total_annual,
            step=1,
            objective="cash",
            extra_income=extra_income,
            stock_grants=stock_grants,
        )
        brute = brute_force_optimize(
            calc,
            total_annual,
            step=1,
            objective="cash",
            extra_income=extra_income,
            stock_grants=stock_grants,
        )

        assert optimized["monthly_salary"] == brute["monthly_salary"]
        assert optimized["bonus"] == pytest.approx(brute["bonus"])
        assert optimized["total_tax"] == pytest.approx(brute["total_tax"])
        assert optimized["net_take_home"] == pytest.approx(brute["net_take_home"])

    def test_breakpoint_candidates_cover_bruteforce_optimum_and_are_sparse(self, hangzhou_config):
        calc = TaxCalculator(hangzhou_config)
        optimizer = TaxOptimizer(calc)
        total_annual = 2010000
        brute = brute_force_optimize(calc, total_annual, step=1, objective="cash")
        salary_bonus_pool = total_annual

        candidates = optimizer._candidate_monthly_salaries(
            salary_bonus_pool,
            step=1,
            extra_income=0.0,
        )

        assert brute["monthly_salary"] in candidates
        assert candidates == sorted(set(candidates))
        assert len(candidates) < brute["_iterations"] / 100

    def test_breakpoint_candidates_snap_around_base_thresholds(self, hangzhou_config):
        calc = TaxCalculator(hangzhou_config)
        optimizer = TaxOptimizer(calc)
        candidates = optimizer._candidate_monthly_salaries(
            500000,
            step=1000,
            extra_income=0.0,
        )

        assert 2000 in candidates and 3000 in candidates
        assert 4000 in candidates and 5000 in candidates
        assert 25000 in candidates and 26000 in candidates
        assert 40000 in candidates and 41000 in candidates
