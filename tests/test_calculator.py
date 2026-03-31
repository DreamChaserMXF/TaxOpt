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
    _progressive_tax,
    enrich_result_with_provident_fund,
    result_from_salary_bonus_split,
    BONUS_BRACKETS_ANNUAL,
    COMPREHENSIVE_BRACKETS,
)

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
        # 38000 × 3% − 0 = 1140（边界值，仍属第一档）
        assert _progressive_tax(38000, COMPREHENSIVE_BRACKETS) == pytest.approx(1140.0)

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
# 月度社保计算
# ──────────────────────────────────────────────

class TestMonthlySocialSecurity:
    def test_zero_rates_all_zero(self, minimal_config):
        calc = TaxCalculator(minimal_config)
        ss = calc.monthly_social_security(20000)
        assert ss["pension"] == 0.0
        assert ss["medical"] == 0.0
        assert ss["unemployment"] == 0.0
        assert ss["housing_fund_employee"] == 0.0
        assert ss["housing_fund_employer"] == 0.0
        assert ss["total"] == 0.0

    def test_full_rates_no_cap(self, full_config):
        """
        月薪 20000，无基数上下限。

        pension     = 20000 × 8%    = 1600
        medical     = 20000 × 2%    = 400
        unemployment= 20000 × 0.5%  = 100
        fund_e      = 20000 × 12%   = 2400
        fund_u      = 20000 × 12%   = 2400
        total       = 1600+400+100+2400 = 4500（个人部分）
        """
        calc = TaxCalculator(full_config)
        ss = calc.monthly_social_security(20000)
        assert ss["pension"] == pytest.approx(1600.0)
        assert ss["medical"] == pytest.approx(400.0)
        assert ss["unemployment"] == pytest.approx(100.0)
        assert ss["housing_fund_employee"] == pytest.approx(2400.0)
        assert ss["housing_fund_employer"] == pytest.approx(2400.0)
        assert ss["total"] == pytest.approx(4500.0)

    def test_salary_above_ss_cap(self, hangzhou_config):
        """
        月薪 50000 超出社保基数上限 25299，公积金基数上限 40694。

        社保基数 clamp 到 25299：pension = 25299 × 8% = 2023.92
        公积金基数 clamp 到 40694：fund_e = 40694 × 12% = 4883.28
        """
        calc = TaxCalculator(hangzhou_config)
        ss = calc.monthly_social_security(50000)
        assert ss["pension"] == pytest.approx(25299 * 0.08)
        assert ss["medical"] == pytest.approx(25299 * 0.02)
        assert ss["unemployment"] == pytest.approx(25299 * 0.005)
        assert ss["housing_fund_employee"] == pytest.approx(40694 * 0.12)
        assert ss["housing_fund_employer"] == pytest.approx(40694 * 0.12)

    def test_salary_below_ss_min(self, hangzhou_config):
        """
        月薪 1000 低于社保基数下限 4986，公积金基数下限 2490。

        社保基数 clamp 到 4986，公积金 clamp 到 2490。
        """
        calc = TaxCalculator(hangzhou_config)
        ss = calc.monthly_social_security(1000)
        assert ss["pension"] == pytest.approx(4986 * 0.08)
        assert ss["medical"] == pytest.approx(4986 * 0.02)
        assert ss["housing_fund_employee"] == pytest.approx(2490 * 0.12)
        assert ss["housing_fund_employer"] == pytest.approx(2490 * 0.12)

    def test_employer_rate_defaults_to_employee_rate(self):
        """housing_fund_employer_rate 未配置时应与个人比例相同。"""
        cfg = TaxConfig(
            housing_fund_employee_rate=0.07,
            housing_fund_employer_rate=0.07,  # 模拟 JSON 未写时由 load 设置为相同值
        )
        calc = TaxCalculator(cfg)
        ss = calc.monthly_social_security(10000)
        assert ss["housing_fund_employee"] == pytest.approx(700.0)
        assert ss["housing_fund_employer"] == pytest.approx(700.0)


# ──────────────────────────────────────────────
# 完整年度计算（result_from_salary_bonus_split）
# ──────────────────────────────────────────────

class TestResultFromSalaryBonusSplit:
    # ── 场景 A：极简，无社保无公积金 ──────────────────

    def test_scenario_a_total_tax(self, minimal_config):
        """
        场景 A：月薪 10000，无年终奖，零社保。

        taxable = 10000×12 − 60000 = 60000
        60000 ∈ (38000, 148000]：tax = 60000 × 10% − 2520 = 3480
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

        月社保（个人）= 20000×(8%+2%+0.5%) + 20000×12% = 2100 + 2400 = 4500
        年社保 = 4500 × 12 = 54000
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
        126000 ∈ (38000, 148000]：tax = 126000 × 10% − 2520 = 10080
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
# 网页 6 个核心指标字段完整性
# ──────────────────────────────────────────────

SIX_CARD_FIELDS = [
    "net_take_home",                          # 卡片①：年度到手现金
    "total_tax",                              # 卡片②：全年纳税合计
    "effective_tax_rate",                     # 卡片③：综合税负率
    "annual_provident_fund",                  # 卡片④：公积金总额
    "annual_social_security",                 # 卡片⑤：社保（新增）
    "net_take_home_including_provident_fund", # 卡片⑥：到手现金+公积金（新增）
]


class TestSixCardFields:
    def test_all_six_fields_present(self, full_config):
        """result 字典必须包含网页 6 个核心指标卡片的全部字段。"""
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 300000, 20000, 60000)
        for field in SIX_CARD_FIELDS:
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

    def test_all_six_fields_are_non_negative(self, full_config):
        """6 个指标均应为非负数。"""
        calc = TaxCalculator(full_config)
        r = result_from_salary_bonus_split(calc, 300000, 20000, 60000)
        for field in SIX_CARD_FIELDS:
            assert r[field] >= 0, f"{field} 不应为负数"

    def test_six_fields_with_zero_provident_fund(self, minimal_config):
        """零公积金时 6 个字段均应正常存在。"""
        calc = TaxCalculator(minimal_config)
        r = result_from_salary_bonus_split(calc, 120000, 10000, 0)
        for field in SIX_CARD_FIELDS:
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
        0 < 15000 ≤ 38000：cum_tax = 15000 × 3% = 450
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
        """月度税额之和应等于 total_tax_and_social_security 的综合所得税。"""
        calc = TaxCalculator(full_config)
        comp_tax, _, _, _, ss = calc.total_tax_and_social_security(20000, 0)
        details = calc.monthly_details(20000, ss)
        assert sum(d["tax"] for d in details) == pytest.approx(comp_tax, abs=0.01)

    def test_monthly_detail_has_required_keys(self, full_config):
        """每行明细需含网页表格所需的全部字段。"""
        required = {
            "month", "salary", "social_security", "tax",
            "after_tax_salary", "after_tax_including_provident_fund",
        }
        calc = TaxCalculator(full_config)
        details = calc.monthly_details(20000)
        for row in details:
            assert required.issubset(row.keys()), f"第 {row.get('month')} 月明细缺字段"
